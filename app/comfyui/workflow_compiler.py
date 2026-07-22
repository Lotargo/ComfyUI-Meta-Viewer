from __future__ import annotations

import copy
import secrets
from collections.abc import Iterable
from typing import Any

from app.ai.resources import (
    CapabilityResolver,
    CompatibilityStatus,
    ModelResource,
    ModelResourceCatalog,
    ResourceType,
)

from .workflow_models import (
    CompatibilityIssue,
    DependencyReport,
    MissingResource,
    ResourceBinding,
    ResourceSelection,
    RuntimeInventory,
    WorkflowTemplate,
)


class WorkflowCompilerError(RuntimeError):
    def __init__(self, message: str, *, code: str = "workflow_compile_error"):
        self.code = code
        super().__init__(message)


RESOURCE_MODEL_FOLDERS: dict[ResourceType, tuple[str, ...]] = {
    ResourceType.CHECKPOINT: ("checkpoints",),
    ResourceType.LORA: ("loras",),
    ResourceType.LOCON: ("loras",),
    ResourceType.DORA: ("loras",),
    ResourceType.VAE: ("vae",),
    ResourceType.EMBEDDING: ("embeddings",),
    ResourceType.DIFFUSION_MODEL: ("diffusion_models", "unet"),
    ResourceType.TEXT_ENCODER: ("text_encoders", "clip"),
    ResourceType.CLIP_VISION: ("clip_vision",),
    ResourceType.CONTROLNET: ("controlnet",),
    ResourceType.UPSCALE_MODEL: ("upscale_models",),
}


AUTO_NODE_BINDINGS: dict[ResourceType, tuple[str, str]] = {
    ResourceType.CHECKPOINT: ("CheckpointLoaderSimple", "ckpt_name"),
    ResourceType.VAE: ("VAELoader", "vae_name"),
    ResourceType.DIFFUSION_MODEL: ("UNETLoader", "unet_name"),
    ResourceType.TEXT_ENCODER: ("CLIPLoader", "clip_name"),
    ResourceType.CLIP_VISION: ("CLIPVisionLoader", "clip_name"),
    ResourceType.CONTROLNET: ("ControlNetLoader", "control_net_name"),
    ResourceType.UPSCALE_MODEL: ("UpscaleModelLoader", "model_name"),
}


def default_field_values(template: WorkflowTemplate) -> dict[str, Any]:
    return {field.id: copy.deepcopy(field.default) for field in template.manifest.fields}


def normalize_resource_selections(raw: Any, *, multiple: bool) -> list[ResourceSelection]:
    if raw is None or raw == "" or raw == []:
        return []
    items: list[Any]
    if multiple:
        items = raw if isinstance(raw, list) else [raw]
    else:
        items = [raw[0] if isinstance(raw, list) and raw else raw]
    normalized: list[ResourceSelection] = []
    for item in items:
        if isinstance(item, str):
            normalized.append(ResourceSelection(name=item))
        elif isinstance(item, dict):
            normalized.append(ResourceSelection.model_validate(item))
        else:
            raise WorkflowCompilerError(
                "Resource selections must contain names or selection objects.",
                code="invalid_resource_selection",
            )
    return normalized


class WorkflowCompiler:
    def compile(
        self,
        template: WorkflowTemplate,
        *,
        values: dict[str, Any] | None = None,
        resource_selections: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        graph = copy.deepcopy(template.workflow)
        resolved_values = default_field_values(template)
        resolved_values.update(values or {})
        selections = resource_selections or {}

        for field in template.manifest.fields:
            value = self._validate_field_value(field, resolved_values.get(field.id))
            if field.kind == "seed" and value == -1:
                value = secrets.randbelow(2**50)
            for binding in field.bindings:
                self._set_node_input(graph, binding.node_id, binding.input, value)

        for slot_id, slot in template.manifest.resource_slots.items():
            selected = normalize_resource_selections(
                selections.get(slot_id),
                multiple=slot.multiple,
            )
            if not selected:
                continue
            binding = self._resolve_resource_binding(
                graph,
                slot.accepts,
                slot.binding,
            )
            if binding.kind == "lora_chain":
                self._inject_lora_chain(graph, binding, selected)
            else:
                if len(selected) != 1:
                    raise WorkflowCompilerError(
                        f"Resource slot '{slot_id}' accepts only one selection.",
                        code="invalid_resource_selection",
                    )
                assert binding.node_id is not None and binding.input is not None
                self._set_node_input(
                    graph,
                    binding.node_id,
                    binding.input,
                    selected[0].name,
                )
        return graph

    @staticmethod
    def _validate_field_value(field: Any, value: Any) -> Any:
        if field.required and (value is None or value == ""):
            raise WorkflowCompilerError(
                f"Field '{field.label}' is required.",
                code="required_workflow_field",
            )
        if field.kind in {"number", "seed"}:
            if isinstance(value, bool):
                raise WorkflowCompilerError(
                    f"Field '{field.label}' must be numeric.",
                    code="invalid_workflow_field",
                )
            try:
                number = float(value)
            except (TypeError, ValueError) as exc:
                raise WorkflowCompilerError(
                    f"Field '{field.label}' must be numeric.",
                    code="invalid_workflow_field",
                ) from exc
            if field.minimum is not None and number < field.minimum:
                raise WorkflowCompilerError(
                    f"Field '{field.label}' must be at least {field.minimum}.",
                    code="invalid_workflow_field",
                )
            if field.maximum is not None and number > field.maximum:
                raise WorkflowCompilerError(
                    f"Field '{field.label}' must be at most {field.maximum}.",
                    code="invalid_workflow_field",
                )
            if field.kind == "seed" or (field.step is not None and float(field.step).is_integer()):
                return int(number)
            return number
        if field.kind == "select":
            allowed = {option.value for option in field.options}
            if value not in allowed:
                raise WorkflowCompilerError(
                    f"Field '{field.label}' contains an unsupported option.",
                    code="invalid_workflow_field",
                )
        return value

    @staticmethod
    def _set_node_input(graph: dict[str, Any], node_id: str, input_name: str, value: Any) -> None:
        node = graph.get(node_id)
        if not isinstance(node, dict):
            raise WorkflowCompilerError(
                f"Binding references missing node '{node_id}'.",
                code="invalid_workflow_binding",
            )
        inputs = node.get("inputs")
        if not isinstance(inputs, dict):
            raise WorkflowCompilerError(
                f"Binding references invalid inputs on node '{node_id}'.",
                code="invalid_workflow_binding",
            )
        if input_name not in inputs:
            raise WorkflowCompilerError(
                f"Binding references missing input '{input_name}' on node '{node_id}'.",
                code="invalid_workflow_binding",
            )
        inputs[input_name] = value

    def _resolve_resource_binding(
        self,
        graph: dict[str, Any],
        accepts: list[ResourceType],
        binding: ResourceBinding,
    ) -> ResourceBinding:
        if binding.kind != "auto":
            return binding

        if any(resource_type in {ResourceType.LORA, ResourceType.LOCON, ResourceType.DORA} for resource_type in accepts):
            source = self._unique_node_id(graph, "CheckpointLoaderSimple")
            return ResourceBinding(kind="lora_chain", source_node_id=source)

        candidates = [AUTO_NODE_BINDINGS[item] for item in accepts if item in AUTO_NODE_BINDINGS]
        if not candidates:
            raise WorkflowCompilerError(
                "This resource slot requires an explicit graph binding.",
                code="ambiguous_resource_binding",
            )
        node_type, input_name = candidates[0]
        node_id = self._unique_node_id(graph, node_type)
        return ResourceBinding(kind="node_input", node_id=node_id, input=input_name)

    @staticmethod
    def _unique_node_id(graph: dict[str, Any], class_type: str) -> str:
        matches = [
            node_id
            for node_id, node in graph.items()
            if isinstance(node, dict) and node.get("class_type") == class_type
        ]
        if len(matches) != 1:
            raise WorkflowCompilerError(
                f"Expected exactly one {class_type} node, found {len(matches)}; add an explicit binding.",
                code="ambiguous_resource_binding",
            )
        return matches[0]

    @staticmethod
    def _inject_lora_chain(
        graph: dict[str, Any],
        binding: ResourceBinding,
        selections: list[ResourceSelection],
    ) -> None:
        source = binding.source_node_id
        if not source or source not in graph:
            raise WorkflowCompilerError(
                "LoRA chain source node does not exist.",
                code="invalid_workflow_binding",
            )
        original_node_ids = list(graph)
        previous = source
        injected_ids: list[str] = []
        for index, selection in enumerate(selections, start=1):
            node_id = f"cmv_lora_{index}"
            suffix = index
            while node_id in graph:
                suffix += 1
                node_id = f"cmv_lora_{suffix}"
            graph[node_id] = {
                "class_type": "LoraLoader",
                "inputs": {
                    "lora_name": selection.name,
                    "strength_model": selection.strength_model,
                    "strength_clip": selection.strength_clip,
                    "model": [previous, binding.model_output],
                    "clip": [previous, binding.clip_output],
                },
                "_meta": {"title": f"CMV LoRA · {selection.name}"},
            }
            previous = node_id
            injected_ids.append(node_id)

        if not injected_ids:
            return
        replacement_model = [previous, 0]
        replacement_clip = [previous, 1]
        for node_id in original_node_ids:
            if node_id == source:
                continue
            node = graph.get(node_id)
            if not isinstance(node, dict):
                continue
            node["inputs"] = WorkflowCompiler._rewrite_link(
                node.get("inputs", {}),
                source=source,
                model_output=binding.model_output,
                clip_output=binding.clip_output,
                replacement_model=replacement_model,
                replacement_clip=replacement_clip,
            )

    @staticmethod
    def _rewrite_link(
        value: Any,
        *,
        source: str,
        model_output: int,
        clip_output: int,
        replacement_model: list[Any],
        replacement_clip: list[Any],
    ) -> Any:
        if (
            isinstance(value, list)
            and len(value) == 2
            and value[0] == source
            and isinstance(value[1], int)
        ):
            if value[1] == model_output:
                return list(replacement_model)
            if value[1] == clip_output:
                return list(replacement_clip)
            return value
        if isinstance(value, list):
            return [
                WorkflowCompiler._rewrite_link(
                    item,
                    source=source,
                    model_output=model_output,
                    clip_output=clip_output,
                    replacement_model=replacement_model,
                    replacement_clip=replacement_clip,
                )
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: WorkflowCompiler._rewrite_link(
                    item,
                    source=source,
                    model_output=model_output,
                    clip_output=clip_output,
                    replacement_model=replacement_model,
                    replacement_clip=replacement_clip,
                )
                for key, item in value.items()
            }
        return value


class WorkflowDependencyValidator:
    def __init__(self, *, catalog: ModelResourceCatalog | None = None):
        self.catalog = catalog

    def validate(
        self,
        template: WorkflowTemplate,
        *,
        resource_selections: dict[str, Any] | None,
        inventory: RuntimeInventory,
    ) -> DependencyReport:
        selections = resource_selections or {}
        node_types = set(inventory.node_types)
        required_nodes = set(template.manifest.required_nodes)
        if any(
            normalize_resource_selections(selections.get(slot_id), multiple=slot.multiple)
            and slot.binding.kind == "lora_chain"
            for slot_id, slot in template.manifest.resource_slots.items()
        ):
            required_nodes.add("LoraLoader")
        missing_nodes = sorted(required_nodes - node_types) if inventory.online else sorted(required_nodes)

        missing_resources: list[MissingResource] = []
        compatibility_issues: list[CompatibilityIssue] = []
        selected_by_slot: dict[str, list[ResourceSelection]] = {}
        for slot_id, slot in template.manifest.resource_slots.items():
            selected = normalize_resource_selections(
                selections.get(slot_id),
                multiple=slot.multiple,
            )
            selected_by_slot[slot_id] = selected
            if not selected and slot.required:
                missing_resources.append(MissingResource(
                    slot=slot_id,
                    label=slot.label,
                    accepts=slot.accepts,
                    requested=[],
                    reason="No resource selected.",
                ))
                continue
            available = self._available_names(inventory, slot.accepts)
            unavailable = [item.name for item in selected if item.name not in available]
            if unavailable:
                missing_resources.append(MissingResource(
                    slot=slot_id,
                    label=slot.label,
                    accepts=slot.accepts,
                    requested=unavailable,
                    reason="The selected resource is not exposed by the connected ComfyUI runtime.",
                ))

        compatibility_issues.extend(self._compatibility_issues(template, selected_by_slot))
        return DependencyReport(
            runtime_online=inventory.online,
            runtime_error=inventory.error,
            missing_nodes=missing_nodes,
            missing_resources=missing_resources,
            compatibility_issues=compatibility_issues,
        )

    @staticmethod
    def _available_names(inventory: RuntimeInventory, accepts: Iterable[ResourceType]) -> set[str]:
        available: set[str] = set()
        for resource_type in accepts:
            for folder in RESOURCE_MODEL_FOLDERS.get(resource_type, ()):
                available.update(inventory.models.get(folder, []))
        return available

    def _compatibility_issues(
        self,
        template: WorkflowTemplate,
        selected_by_slot: dict[str, list[ResourceSelection]],
    ) -> list[CompatibilityIssue]:
        if self.catalog is None:
            return []
        try:
            resources = self.catalog.list_resources(only_available=True)
        except Exception:
            return []
        by_name: dict[str, ModelResource] = {}
        for resource in resources:
            by_name[resource.file_path] = resource
            by_name[resource.display_name] = resource

        checkpoint: ModelResource | None = None
        for slot_id, slot in template.manifest.resource_slots.items():
            if ResourceType.CHECKPOINT not in slot.accepts:
                continue
            selected = selected_by_slot.get(slot_id, [])
            if selected and selected[0].name in by_name:
                checkpoint = by_name[selected[0].name]
                break
        if checkpoint is None:
            return []

        issues: list[CompatibilityIssue] = []
        for slot_id, slot in template.manifest.resource_slots.items():
            if not any(item in {ResourceType.LORA, ResourceType.LOCON, ResourceType.DORA} for item in slot.accepts):
                continue
            for selection in selected_by_slot.get(slot_id, []):
                resource = by_name.get(selection.name)
                if resource is None:
                    continue
                evaluation = CapabilityResolver.evaluate(
                    checkpoint_architecture=checkpoint.architecture,
                    resource=resource,
                )
                if evaluation.status is not CompatibilityStatus.SUPPORTED:
                    issues.append(CompatibilityIssue(
                        slot=slot_id,
                        resource_name=selection.name,
                        status=evaluation.status,
                        reason=evaluation.reason or "Compatibility requires review.",
                    ))
        return issues


__all__ = [
    "RESOURCE_MODEL_FOLDERS",
    "WorkflowCompiler",
    "WorkflowCompilerError",
    "WorkflowDependencyValidator",
    "default_field_values",
    "normalize_resource_selections",
]
