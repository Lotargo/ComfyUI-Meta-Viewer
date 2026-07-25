from __future__ import annotations

import base64
import io
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from app import database
from app.ai.resources import (
    CompatibilityStatus,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
    ResourceType,
)
from app.comfyui.workflow_compiler import (
    WorkflowCompiler,
    WorkflowCompilerError,
    WorkflowDependencyValidator,
    default_field_values,
)
from app.comfyui.workflow_execution import WorkflowExecutionService
from app.comfyui.workflow_models import RuntimeInventory, WorkflowTemplateManifest
from app.comfyui.workflow_registry import WorkflowTemplateError, WorkflowTemplateRegistry
from app.comfyui.workflow_registry_status import (
    WorkflowRegistryStatusStore,
    inventory_fingerprint,
    validate_registry_template,
)
from app.comfyui.sampling_options import CORE_SAMPLER_OPTIONS, CORE_SCHEDULER_OPTIONS
from app.comfyui.workflow_store import WorkflowStore
from app.config_store import ConfigStore
from app.main import app


PNG_1X1 = base64.b64decode(
    "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAusB9Y9Z1XcAAAAASUVORK5CYII="
)


def ready_inventory(template) -> RuntimeInventory:
    return RuntimeInventory(
        online=True,
        node_types=sorted(set(template.manifest.required_nodes) | {"LoraLoader"}),
        models={
            "checkpoints": ["models/base-xl.safetensors", "models/refiner-xl.safetensors"],
            "loras": ["styles/ink.safetensors", "styles/light.safetensors"],
            "vae": ["video_vae.safetensors"],
            "diffusion_models": ["hunyuan_video.safetensors"],
            "text_encoders": ["clip_l.safetensors", "llava_llama3_fp8.safetensors"],
        },
        source="api",
    )


class WorkflowTemplateRegistryTest(unittest.TestCase):
    def test_builtin_templates_cover_initial_categories(self) -> None:
        templates = WorkflowTemplateRegistry().list_templates()

        self.assertEqual(
            {item.manifest.category.value for item in templates},
            {"simple", "reference", "video", "advanced"},
        )
        self.assertTrue(all(item.manifest.resource_slots for item in templates))
        self.assertTrue(all(item.workflow for item in templates))
        self.assertTrue(all(item.manifest.schema_version == "2" for item in templates))
        self.assertTrue(all(item.manifest.supported_ecosystems for item in templates))

    def test_builtin_templates_expose_complete_comfyui_sampling_catalog(self) -> None:
        expected_samplers = [value for value, _label in CORE_SAMPLER_OPTIONS]
        expected_schedulers = [value for value, _label in CORE_SCHEDULER_OPTIONS]

        for template in WorkflowTemplateRegistry().list_templates():
            fields = {field.id: field for field in template.manifest.fields}
            self.assertEqual(
                [option.value for option in fields["sampler"].options],
                expected_samplers,
            )
            self.assertEqual(
                [option.value for option in fields["scheduler"].options],
                expected_schedulers,
            )

    def test_builtin_image_templates_cover_distinct_loader_families(self) -> None:
        registry = WorkflowTemplateRegistry()
        checkpoint = registry.get("core-image")
        separate = registry.get("core-flux")
        gguf = registry.get("core-flux-gguf")
        pony_gguf = registry.get("core-pony-gguf")

        self.assertEqual(checkpoint.manifest.loader_family.value, "checkpoint")
        self.assertEqual(separate.manifest.loader_family.value, "separate_components")
        self.assertEqual(gguf.manifest.loader_family.value, "gguf")
        self.assertEqual(pony_gguf.manifest.loader_family.value, "gguf")
        self.assertEqual(
            [item.value for item in separate.manifest.resource_slots["diffusion_model"].accepts],
            ["diffusion_model"],
        )
        self.assertEqual(
            [item.value for item in gguf.manifest.resource_slots["diffusion_model"].accepts],
            ["diffusion_model_gguf"],
        )
        self.assertEqual(
            {item.value for item in gguf.manifest.resource_slots["t5xxl"].accepts},
            {"text_encoder", "text_encoder_gguf"},
        )
        self.assertEqual(
            [item.value for item in pony_gguf.manifest.resource_slots["conditioning_checkpoint"].accepts],
            ["checkpoint"],
        )
        for template in (separate, gguf):
            field_ids = {field.id for field in template.manifest.fields}
            self.assertIn("guidance", field_ids)
            self.assertNotIn("cfg", field_ids)
            self.assertNotIn("clip_skip", field_ids)

    def test_json_bundle_import_is_immediately_loadable(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            source = registry.get("core-image")
            manifest = source.manifest.model_dump(mode="json")
            manifest.update({"id": "custom-image", "name": "Custom image", "version": "2.0.0"})
            bundle = json.dumps({"manifest": manifest, "workflow": source.workflow}).encode("utf-8")

            imported = registry.import_bundle("custom.json", bundle)

            self.assertEqual(imported.manifest.id, "custom-image")
            self.assertEqual(registry.get("custom-image").source, "user")
            self.assertTrue((Path(temp_dir) / "custom-image" / "manifest.json").is_file())

    def test_api_workflow_is_analyzed_and_registered_with_persisted_mappings(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            workflow = registry.get("core-image").workflow
            data = json.dumps(workflow).encode("utf-8")

            plan = registry.analyze_import("cinematic_landscape.json", data)

            self.assertTrue(plan.ready)
            self.assertEqual(plan.source_format, "api_workflow")
            self.assertEqual(plan.manifest.id, "cinematic-landscape")
            self.assertEqual(plan.manifest.loader_family.value, "checkpoint")
            self.assertEqual(
                plan.manifest.resource_slots["checkpoint"].binding.model_dump(),
                {
                    "kind": "node_input",
                    "node_id": "1",
                    "input": "ckpt_name",
                    "source_node_id": None,
                    "model_output": 0,
                    "clip_output": 1,
                },
            )
            self.assertEqual(
                plan.manifest.fields[0].bindings[0].model_dump(),
                {"node_id": "2", "input": "text"},
            )

            imported = registry.import_bundle(
                "cinematic_landscape.json",
                data,
                manifest_overrides={
                    "id": "my-cinematic-workflow",
                    "name": "My cinematic workflow",
                },
            )
            stored = json.loads(
                (Path(temp_dir) / "my-cinematic-workflow" / "manifest.json").read_text(
                    encoding="utf-8"
                )
            )

            self.assertEqual(imported.source, "user")
            self.assertEqual(stored["fields"][0]["bindings"], [{"node_id": "2", "input": "text"}])
            self.assertEqual(
                stored["resource_slots"]["checkpoint"]["binding"]["input"],
                "ckpt_name",
            )

    def test_api_workflow_with_multiple_pipelines_requires_mapping(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            workflow = registry.get("core-image").workflow
            workflow = {**workflow, "8": {**workflow["5"], "inputs": dict(workflow["5"]["inputs"])}}
            data = json.dumps({"prompt": workflow}).encode("utf-8")

            plan = registry.analyze_import("two-pipelines.json", data)

            self.assertFalse(plan.ready)
            self.assertIn("Multiple sampler pipelines", plan.warnings[0])
            with self.assertRaises(WorkflowTemplateError) as caught:
                registry.import_bundle("two-pipelines.json", data)
            self.assertEqual(caught.exception.code, "workflow_mapping_required")

    def test_manual_mapping_resolves_sampler_prompts_output_and_field_visibility(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        workflow = registry.get("core-image").workflow
        workflow = {
            **workflow,
            "8": {**workflow["5"], "inputs": dict(workflow["5"]["inputs"])},
            "9": {
                "class_type": "SaveImage",
                "inputs": {"filename_prefix": "Mapped", "images": ["6", 0]},
            },
        }

        plan = registry.analyze_import(
            "mapped.json",
            json.dumps(workflow).encode("utf-8"),
            mapping_overrides={
                "sampler_node_id": "8",
                "positive_binding": "2:text",
                "negative_binding": "__none__",
                "output_node_id": "9",
                "field_options": {
                    "width": {"hidden": True},
                    "steps": {"advanced": False},
                },
            },
        )

        self.assertTrue(plan.ready)
        self.assertEqual(plan.manifest.output_nodes, ["9"])
        fields = {field.id: field for field in plan.manifest.fields}
        self.assertEqual(fields["positive_prompt"].bindings[0].node_id, "2")
        self.assertNotIn("negative_prompt", fields)
        self.assertTrue(fields["width"].hidden)
        self.assertFalse(fields["steps"].advanced)
        self.assertEqual(
            next(item for item in plan.mappings if item["semantic_id"] == "positive_prompt")["confidence"],
            "manual",
        )

    def test_manual_model_role_registers_unknown_loader(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        workflow = registry.get("core-image").workflow
        workflow = {
            **workflow,
            "1": {
                "class_type": "AcmeModelLoader",
                "inputs": {"model_name": "acme-model.gguf"},
            },
        }
        data = json.dumps(workflow).encode("utf-8")

        unmapped = registry.analyze_import("custom-loader.json", data)
        mapped = registry.analyze_import(
            "custom-loader.json",
            data,
            mapping_overrides={
                "model_roles": {"1:model_name": "diffusion_model_gguf"},
            },
        )

        self.assertFalse(unmapped.ready)
        self.assertEqual(unmapped.candidates["model_inputs"][0]["value"], "1:model_name")
        self.assertTrue(mapped.ready)
        self.assertEqual(mapped.manifest.loader_family.value, "gguf")
        self.assertEqual(
            mapped.manifest.resource_slots["diffusion_model"].binding.node_id,
            "1",
        )

    def test_manual_prompt_binding_supports_custom_encoder_input(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        workflow = registry.get("core-image").workflow
        workflow = {
            **workflow,
            "2": {
                "class_type": "AcmePromptEncoder",
                "inputs": {"prompt": "custom prompt", "clip": ["1", 1]},
            },
        }
        data = json.dumps(workflow).encode("utf-8")

        unmapped = registry.analyze_import("custom-prompt.json", data)
        mapped = registry.analyze_import(
            "custom-prompt.json",
            data,
            mapping_overrides={"positive_binding": "2:prompt"},
        )

        self.assertFalse(unmapped.ready)
        self.assertTrue(any(
            item["value"] == "2:prompt"
            for item in unmapped.candidates["prompt_inputs"]
        ))
        self.assertTrue(mapped.ready)
        positive = next(field for field in mapped.manifest.fields if field.id == "positive_prompt")
        self.assertEqual(positive.bindings[0].input, "prompt")

    def test_gguf_api_workflow_maps_wrapped_prompt_and_component_loaders(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        workflow = registry.get("core-flux-gguf").workflow

        plan = registry.analyze_import(
            "flux-gguf.json",
            json.dumps(workflow).encode("utf-8"),
        )

        self.assertTrue(plan.ready)
        self.assertEqual(plan.manifest.loader_family.value, "gguf")
        self.assertEqual(
            {item.value for item in plan.manifest.resource_slots["diffusion_model"].accepts},
            {"diffusion_model_gguf"},
        )
        self.assertEqual(plan.manifest.component_policy.clip.value, "required")
        field_ids = [field.id for field in plan.manifest.fields]
        self.assertIn("positive_prompt", field_ids)
        self.assertNotIn("negative_prompt", field_ids)

    def test_api_workflow_maps_existing_standard_lora_loader(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        workflow = registry.get("core-image").workflow
        workflow = {
            **workflow,
            "8": {
                "class_type": "LoraLoader",
                "inputs": {
                    "model": ["1", 0],
                    "clip": ["1", 1],
                    "lora_name": "style.safetensors",
                    "strength_model": 0.8,
                    "strength_clip": 0.8,
                },
            },
        }

        plan = registry.analyze_import(
            "lora-workflow.json",
            json.dumps(workflow).encode("utf-8"),
        )

        self.assertTrue(plan.ready)
        self.assertEqual(
            {item.value for item in plan.manifest.resource_slots["lora"].accepts},
            {"lora", "locon", "dora"},
        )
        self.assertEqual(
            plan.manifest.resource_slots["lora"].binding.input,
            "lora_name",
        )

    def test_ui_workflow_explains_api_format_requirement(self) -> None:
        registry = WorkflowTemplateRegistry(user_root="unused")
        data = json.dumps({"nodes": [], "links": []}).encode("utf-8")

        with self.assertRaises(WorkflowTemplateError) as caught:
            registry.analyze_import("ui-workflow.json", data)

        self.assertEqual(caught.exception.code, "ui_workflow_requires_api_format")

    def test_invalid_user_template_is_listed_without_breaking_valid_templates(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            invalid_dir = root / "broken-template"
            invalid_dir.mkdir()
            (invalid_dir / "manifest.json").write_text("{not-json", encoding="utf-8")
            registry = WorkflowTemplateRegistry(user_root=root)

            templates = registry.list_templates()
            entries = registry.list_management_entries(WorkflowRegistryStatusStore(root))

            self.assertTrue(any(item.manifest.id == "core-image" for item in templates))
            broken = next(item for item in entries if item["id"] == "broken-template")
            self.assertEqual(broken["source"], "user")
            self.assertEqual(broken["validation"]["status"], "invalid")
            self.assertIn("Cannot read workflow manifest", broken["validation"]["reason"])

    def test_registry_validation_status_is_persisted_by_inventory_fingerprint(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry()
            template = registry.get("core-image")
            inventory = ready_inventory(template)
            status = validate_registry_template(template, inventory)
            store = WorkflowRegistryStatusStore(temp_dir)

            store.set(template.manifest.id, status)
            restored = store.get(template.manifest.id)

            self.assertEqual(status.status, "ready")
            self.assertEqual(restored.inventory_fingerprint, inventory_fingerprint(inventory))
            self.assertIsNotNone(restored.last_validated_at)

    def test_registry_validation_distinguishes_warning_expert_and_partial(self) -> None:
        source = WorkflowTemplateRegistry().get("core-image")
        offline = validate_registry_template(
            source,
            RuntimeInventory(online=False, error="runtime offline"),
        )
        expert_manifest = WorkflowTemplateManifest.model_validate({
            **source.manifest.model_dump(mode="json"),
            "id": "expert-template",
            "loader_family": "custom",
        })
        partial_manifest = WorkflowTemplateManifest.model_validate({
            **expert_manifest.model_dump(mode="json"),
            "id": "partial-template",
            "fields": [],
        })
        expert = validate_registry_template(
            source.model_copy(update={"manifest": expert_manifest}),
            ready_inventory(source),
        )
        partial = validate_registry_template(
            source.model_copy(update={"manifest": partial_manifest}),
            ready_inventory(source),
        )

        self.assertEqual(offline.status, "warning")
        self.assertEqual(expert.status, "expert")
        self.assertEqual(partial.status, "partially_mapped")

    def test_delete_user_template_does_not_touch_sibling_model_files(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            registry = WorkflowTemplateRegistry(user_root=root)
            source = registry.get("core-image")
            manifest = source.manifest.model_dump(mode="json")
            manifest.update({"id": "delete-me", "name": "Delete me"})
            registry.import_bundle(
                "delete-me.json",
                json.dumps({"manifest": manifest, "workflow": source.workflow}).encode("utf-8"),
            )
            model_file = root / "models" / "keep.safetensors"
            model_file.parent.mkdir()
            model_file.write_bytes(b"model")

            registry.delete_user_template("delete-me")

            self.assertFalse((root / "delete-me").exists())
            self.assertEqual(model_file.read_bytes(), b"model")

    def test_v1_bundle_is_migrated_and_persisted_as_schema_v2(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            registry = WorkflowTemplateRegistry(user_root=temp_dir)
            source = registry.get("core-image")
            manifest = source.manifest.model_dump(mode="json")
            manifest.update({
                "schema_version": "1",
                "id": "legacy-v1-image",
                "name": "Legacy v1 image",
                "version": "1.0.0",
            })
            for key in (
                "supported_ecosystems",
                "loader_family",
                "component_policy",
                "capability_notes",
                "limitation_notes",
            ):
                manifest.pop(key)
            bundle = json.dumps({"manifest": manifest, "workflow": source.workflow}).encode("utf-8")

            imported = registry.import_bundle("legacy.json", bundle)
            stored = json.loads(
                (Path(temp_dir) / "legacy-v1-image" / "manifest.json").read_text(encoding="utf-8")
            )

            self.assertEqual(imported.manifest.schema_version, "2")
            self.assertEqual(imported.manifest.loader_family.value, "checkpoint")
            self.assertEqual(imported.manifest.component_policy.clip.value, "embedded")
            self.assertEqual(stored["schema_version"], "2")
            self.assertIn("ecosystem compatibility", stored["limitation_notes"][0])

    def test_v2_manifest_rejects_component_policy_without_matching_slot(self) -> None:
        source = WorkflowTemplateRegistry().get("core-image")
        payload = source.manifest.model_dump(mode="json")
        payload["component_policy"]["clip"] = "required"

        with self.assertRaisesRegex(ValueError, "required clip policy"):
            WorkflowTemplateManifest.model_validate(payload)

    def test_resource_options_filter_standard_and_gguf_files_by_slot(self) -> None:
        from app.comfyui.editor_routes import _resource_options

        source = WorkflowTemplateRegistry().get("core-image")
        manifest = WorkflowTemplateManifest.model_validate({
            "id": "taxonomy-filter",
            "name": "Taxonomy filter",
            "version": "1.0.0",
            "category": "simple",
            "media_type": "image",
            "supported_ecosystems": ["flux_1"],
            "loader_family": "custom",
            "component_policy": {"clip": "embedded", "vae": "embedded"},
            "resource_slots": {
                "standard": {"label": "Standard", "accepts": ["diffusion_model"]},
                "gguf": {"label": "GGUF", "accepts": ["diffusion_model_gguf"]},
            },
            "output_nodes": ["7"],
        })
        template = source.model_copy(update={"manifest": manifest})
        inventory = RuntimeInventory(
            online=True,
            models={
                "diffusion_models": ["flux.safetensors", "flux.Q4_K_M.gguf"],
                "unet": ["legacy.ckpt", "legacy.Q5_K_S.GGUF"],
            },
            source="api",
        )

        options = _resource_options(template, inventory)

        self.assertEqual(
            [item["name"] for item in options["standard"]],
            ["flux.safetensors", "legacy.ckpt"],
        )
        self.assertEqual(
            [item["name"] for item in options["gguf"]],
            ["flux.Q4_K_M.gguf", "legacy.Q5_K_S.GGUF"],
        )


class WorkflowCompilerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.template = WorkflowTemplateRegistry().get("core-image")

    def test_fields_and_generic_lora_chain_are_compiled(self) -> None:
        graph = WorkflowCompiler().compile(
            self.template,
            values={"positive_prompt": "A glass observatory", "width": 768, "seed": 42},
            resource_selections={
                "checkpoint": "models/base-xl.safetensors",
                "loras": [
                    {"name": "styles/ink.safetensors", "strength_model": 0.7, "strength_clip": 0.6},
                    "styles/light.safetensors",
                ],
            },
        )

        self.assertEqual(graph["1"]["inputs"]["ckpt_name"], "models/base-xl.safetensors")
        self.assertEqual(graph["2"]["inputs"]["text"], "A glass observatory")
        self.assertEqual(graph["4"]["inputs"]["width"], 768)
        self.assertEqual(graph["5"]["inputs"]["seed"], 42)
        self.assertEqual(graph["cmv_lora_1"]["inputs"]["strength_model"], 0.7)
        self.assertEqual(graph["cmv_lora_2"]["inputs"]["model"], ["cmv_lora_1", 0])
        self.assertEqual(graph["5"]["inputs"]["model"], ["cmv_lora_2", 0])
        self.assertEqual(graph["2"]["inputs"]["clip"], ["cmv_lora_2", 1])
        self.assertEqual(graph["6"]["inputs"]["vae"], ["1", 2])

    def test_extended_sampler_and_scheduler_are_compiled(self) -> None:
        graph = WorkflowCompiler().compile(
            self.template,
            values={
                "sampler": "sa_solver_pece",
                "scheduler": "kl_optimal",
            },
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )

        self.assertEqual(graph["5"]["inputs"]["sampler_name"], "sa_solver_pece")
        self.assertEqual(graph["5"]["inputs"]["scheduler"], "kl_optimal")

    def test_separate_flux_components_compile_to_distinct_loaders(self) -> None:
        template = WorkflowTemplateRegistry().get("core-flux")

        graph = WorkflowCompiler().compile(
            template,
            values={"positive_prompt": "A glass observatory", "guidance": 4.2},
            resource_selections={
                "diffusion_model": "flux1-dev.safetensors",
                "clip_l": "clip_l.safetensors",
                "t5xxl": "t5xxl_fp16.safetensors",
                "vae": "ae.safetensors",
            },
        )

        self.assertEqual(graph["1"]["class_type"], "UNETLoader")
        self.assertEqual(graph["1"]["inputs"]["unet_name"], "flux1-dev.safetensors")
        self.assertEqual(graph["2"]["class_type"], "DualCLIPLoader")
        self.assertEqual(graph["2"]["inputs"]["clip_name1"], "clip_l.safetensors")
        self.assertEqual(graph["2"]["inputs"]["clip_name2"], "t5xxl_fp16.safetensors")
        self.assertEqual(graph["4"]["inputs"]["guidance"], 4.2)
        self.assertEqual(graph["7"]["inputs"]["cfg"], 1.0)
        self.assertEqual(graph["8"]["inputs"]["vae_name"], "ae.safetensors")

    def test_gguf_flux_components_compile_mixed_text_encoder_formats(self) -> None:
        template = WorkflowTemplateRegistry().get("core-flux-gguf")

        graph = WorkflowCompiler().compile(
            template,
            resource_selections={
                "diffusion_model": "flux1-dev.Q4_K_M.gguf",
                "clip_l": "clip_l.safetensors",
                "t5xxl": "t5-v1_1-xxl.Q5_K_M.gguf",
                "vae": "ae.safetensors",
            },
        )

        self.assertEqual(graph["1"]["class_type"], "UnetLoaderGGUF")
        self.assertEqual(graph["1"]["inputs"]["unet_name"], "flux1-dev.Q4_K_M.gguf")
        self.assertEqual(graph["2"]["class_type"], "DualCLIPLoaderGGUF")
        self.assertEqual(graph["2"]["inputs"]["clip_name1"], "clip_l.safetensors")
        self.assertEqual(graph["2"]["inputs"]["clip_name2"], "t5-v1_1-xxl.Q5_K_M.gguf")

    def test_pony_gguf_compiles_model_with_checkpoint_clip_and_vae(self) -> None:
        template = WorkflowTemplateRegistry().get("core-pony-gguf")

        graph = WorkflowCompiler().compile(
            template,
            values={"positive_prompt": "score_9, portrait", "steps": 12},
            resource_selections={
                "diffusion_model": "babesByStableYogi_v65Q4Q8.gguf",
                "conditioning_checkpoint": "cyberrealisticPony_v150.safetensors",
            },
        )

        self.assertEqual(graph["1"]["inputs"]["unet_name"], "babesByStableYogi_v65Q4Q8.gguf")
        self.assertEqual(graph["2"]["inputs"]["ckpt_name"], "cyberrealisticPony_v150.safetensors")
        self.assertEqual(graph["3"]["inputs"]["clip"], ["2", 1])
        self.assertEqual(graph["7"]["inputs"]["vae"], ["2", 2])
        self.assertEqual(graph["6"]["inputs"]["steps"], 12)

    def test_gguf_flux_dependencies_accept_mixed_encoder_inventory(self) -> None:
        template = WorkflowTemplateRegistry().get("core-flux-gguf")
        inventory = RuntimeInventory(
            online=True,
            node_types=template.manifest.required_nodes,
            models={
                "diffusion_models": ["flux1-dev.safetensors", "flux1-dev.Q4_K_M.gguf"],
                "text_encoders": ["clip_l.safetensors", "t5-v1_1-xxl.Q5_K_M.gguf"],
                "vae": ["ae.safetensors"],
            },
            source="api",
        )

        report = WorkflowDependencyValidator().validate(
            template,
            resource_selections={
                "diffusion_model": "flux1-dev.Q4_K_M.gguf",
                "clip_l": "clip_l.safetensors",
                "t5xxl": "t5-v1_1-xxl.Q5_K_M.gguf",
                "vae": "ae.safetensors",
            },
            inventory=inventory,
        )

        self.assertTrue(report.ready)

    def test_ambiguous_auto_binding_requires_declarative_binding(self) -> None:
        template = self.template.model_copy(deep=True)
        template.workflow["8"] = {
            "class_type": "CheckpointLoaderSimple",
            "inputs": {"ckpt_name": ""},
        }
        slot = template.manifest.resource_slots["checkpoint"]
        template.manifest.resource_slots["checkpoint"] = slot.model_copy(
            update={"binding": slot.binding.model_copy(update={"kind": "auto", "node_id": None, "input": None})}
        )

        with self.assertRaisesRegex(WorkflowCompilerError, "exactly one"):
            WorkflowCompiler().compile(
                template,
                resource_selections={"checkpoint": "models/base-xl.safetensors"},
            )

    def test_dependency_report_separates_nodes_and_models(self) -> None:
        report = WorkflowDependencyValidator().validate(
            self.template,
            resource_selections={"checkpoint": "missing.safetensors"},
            inventory=RuntimeInventory(
                online=True,
                node_types=["CheckpointLoaderSimple"],
                models={"checkpoints": []},
                source="api",
            ),
        )

        self.assertIn("KSampler", report.missing_nodes)
        self.assertEqual(report.missing_resources[0].slot, "checkpoint")
        self.assertFalse(report.ready)

    def test_dependency_report_is_ready_for_resolved_runtime(self) -> None:
        report = WorkflowDependencyValidator().validate(
            self.template,
            resource_selections={
                "checkpoint": "models/base-xl.safetensors",
                "loras": ["styles/ink.safetensors"],
            },
            inventory=ready_inventory(self.template),
        )

        self.assertTrue(report.ready)

    def test_unknown_primary_model_is_an_experimental_warning(self) -> None:
        resource = ModelResource(
            content_hash="unknown-model-123",
            file_path="models/mystery.safetensors",
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.OTHER,
            display_name="Mystery model",
        )
        catalog = type("Catalog", (), {"list_resources": lambda self, **_kwargs: [resource]})()
        inventory = ready_inventory(self.template)
        inventory.models["checkpoints"] = ["models/mystery.safetensors"]

        report = WorkflowDependencyValidator(catalog=catalog).validate(
            self.template,
            resource_selections={"checkpoint": "models/mystery.safetensors"},
            inventory=inventory,
        )

        self.assertTrue(report.ready)
        self.assertEqual(report.compatibility_issues[0].status.value, "experimental")
        self.assertIn("architecture is unknown", report.compatibility_issues[0].reason)

    def test_known_template_ecosystem_mismatch_is_incompatible(self) -> None:
        resource = ModelResource(
            content_hash="known-flux-model-123",
            file_path="models/flux-checkpoint.safetensors",
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.FLUX_1,
            display_name="Flux checkpoint",
        )
        catalog = type("Catalog", (), {"list_resources": lambda self, **_kwargs: [resource]})()
        inventory = ready_inventory(self.template)
        inventory.models["checkpoints"] = [resource.file_path]

        report = WorkflowDependencyValidator(catalog=catalog).validate(
            self.template,
            resource_selections={"checkpoint": resource.file_path},
            inventory=inventory,
        )

        self.assertFalse(report.ready)
        self.assertEqual(report.compatibility_issues[0].status.value, "incompatible")
        self.assertIn("not supported by this workflow", report.compatibility_issues[0].reason)

    def test_unspecified_template_ecosystem_warns_without_blocking(self) -> None:
        template = self.template.model_copy(update={
            "manifest": self.template.manifest.model_copy(update={
                "supported_ecosystems": [ModelEcosystem.OTHER],
            }),
        })
        resource = ModelResource(
            content_hash="known-sdxl-model-123",
            file_path="models/base-xl.safetensors",
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.SDXL,
            display_name="SDXL checkpoint",
        )
        catalog = type("Catalog", (), {"list_resources": lambda self, **_kwargs: [resource]})()

        report = WorkflowDependencyValidator(catalog=catalog).validate(
            template,
            resource_selections={"checkpoint": resource.file_path},
            inventory=ready_inventory(template),
        )

        self.assertTrue(report.ready)
        self.assertEqual(report.compatibility_issues[0].status.value, "experimental")
        self.assertIn("does not declare", report.compatibility_issues[0].reason)


class WorkflowEditorRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()
        self.old_upload_folder = app.config.get("UPLOAD_FOLDER")
        self.old_config_store = app.config.get("CONFIG_STORE")
        app.config.update(
            TESTING=True,
            UPLOAD_FOLDER=str(Path(self.temp_dir.name) / "uploads"),
            CONFIG_STORE=ConfigStore(Path(self.temp_dir.name) / "config.json"),
        )
        Path(app.config["UPLOAD_FOLDER"]).mkdir(parents=True, exist_ok=True)
        self.client = app.test_client()
        self.template = WorkflowTemplateRegistry().get("core-image")
        self.inventory = ready_inventory(self.template)
        self.inventory.models["checkpoints"] = ["models/base-xl.safetensors"]

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        app.config["UPLOAD_FOLDER"] = self.old_upload_folder
        app.config["CONFIG_STORE"] = self.old_config_store
        self.temp_dir.cleanup()

    def test_editor_page_uses_beginner_path_and_separate_advanced_settings(self) -> None:
        response = self.client.get("/editor")

        self.assertEqual(response.status_code, 200)
        html = response.get_data(as_text=True)
        self.assertIn("What will you create?", html)
        self.assertIn("Describe your idea in everyday language", html)
        self.assertIn('id="advanced-settings-dialog"', html)
        self.assertIn('id="advanced-fields"', html)
        self.assertIn('id="template-import-mapping"', html)
        self.assertIn('id="template-manifest-preview"', html)
        self.assertIn('id="workflow-management-dialog"', html)
        self.assertIn('id="workflow-management-body"', html)
        self.assertIn("Check dependencies and preview graph", html)
        self.assertNotIn("Manifest controls", html)

    @patch("app.comfyui.editor_routes._inventory")
    def test_manifest_driven_draft_preview_round_trip(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        bootstrap = self.client.get("/api/editor/bootstrap")
        self.assertEqual(bootstrap.status_code, 200)
        self.assertEqual(len(bootstrap.get_json()["templates"]), 7)

        created = self.client.post(
            "/api/editor/drafts",
            json={
                "template_id": "core-image",
                "values": {"positive_prompt": "A copper automaton"},
                "resource_selections": {"checkpoint": "models/base-xl.safetensors"},
            },
        )
        self.assertEqual(created.status_code, 201)
        draft = created.get_json()["draft"]

        updated = self.client.patch(
            f"/api/editor/drafts/{draft['id']}",
            json={"values": {"steps": 36}},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["draft"]["values"]["positive_prompt"], "A copper automaton")
        self.assertEqual(updated.get_json()["draft"]["values"]["steps"], 36)

        preview = self.client.post(f"/api/editor/drafts/{draft['id']}/preview")
        self.assertEqual(preview.status_code, 200)
        payload = preview.get_json()
        self.assertTrue(payload["dependencies"]["ready"])
        self.assertEqual(payload["workflow"]["5"]["inputs"]["steps"], 36)

    @patch("app.comfyui.editor_routes._inventory")
    def test_api_workflow_import_preview_and_registration(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        data = json.dumps(self.template.workflow).encode("utf-8")

        analyzed = self.client.post(
            "/api/editor/templates/import/analyze",
            data={"file": (io.BytesIO(data), "route-workflow.json")},
            content_type="multipart/form-data",
        )

        self.assertEqual(analyzed.status_code, 200)
        analysis = analyzed.get_json()
        self.assertTrue(analysis["ready"])
        self.assertEqual(analysis["source_format"], "api_workflow")
        self.assertTrue(any(item["semantic_id"] == "positive_prompt" for item in analysis["mappings"]))

        imported = self.client.post(
            "/api/editor/templates/import",
            data={
                "file": (io.BytesIO(data), "route-workflow.json"),
                "id": "registered-route-workflow",
                "name": "Registered route workflow",
                "description": "Imported in a route test.",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(imported.status_code, 201)
        payload = imported.get_json()
        self.assertEqual(payload["manifest"]["id"], "registered-route-workflow")
        self.assertEqual(payload["source"], "user")
        self.assertTrue(
            Path(app.config["UPLOAD_FOLDER"], "workflow_templates", "registered-route-workflow", "manifest.json").is_file()
        )

    @patch("app.comfyui.editor_routes._inventory")
    def test_mapping_wizard_registers_custom_model_loader(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        workflow = {
            **self.template.workflow,
            "1": {
                "class_type": "AcmeModelLoader",
                "inputs": {"model_name": "acme.gguf"},
            },
        }
        data = json.dumps(workflow).encode("utf-8")
        mapping = {
            "model_roles": {"1:model_name": "diffusion_model_gguf"},
            "field_options": {"steps": {"advanced": False, "hidden": True}},
        }

        analyzed = self.client.post(
            "/api/editor/templates/import/analyze",
            data={
                "file": (io.BytesIO(data), "custom-loader.json"),
                "mapping": json.dumps(mapping),
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(analyzed.status_code, 200)
        analysis = analyzed.get_json()
        self.assertTrue(analysis["ready"])
        self.assertEqual(analysis["manifest"]["loader_family"], "gguf")
        self.assertEqual(
            next(field for field in analysis["manifest"]["fields"] if field["id"] == "steps")["hidden"],
            True,
        )

        imported = self.client.post(
            "/api/editor/templates/import",
            data={
                "file": (io.BytesIO(data), "custom-loader.json"),
                "mapping": json.dumps(mapping),
                "id": "mapped-custom-loader",
                "name": "Mapped custom loader",
            },
            content_type="multipart/form-data",
        )

        self.assertEqual(imported.status_code, 201)
        manifest = imported.get_json()["manifest"]
        self.assertEqual(manifest["resource_slots"]["diffusion_model"]["binding"]["node_id"], "1")
        self.assertTrue(next(field for field in manifest["fields"] if field["id"] == "steps")["hidden"])

    @patch("app.comfyui.editor_routes._inventory")
    def test_workflow_management_lists_revalidates_edits_and_deletes_import(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        registry = WorkflowTemplateRegistry(
            user_root=Path(app.config["UPLOAD_FOLDER"]) / "workflow_templates",
        )
        manifest = self.template.manifest.model_dump(mode="json")
        manifest.update({"id": "managed-workflow", "name": "Managed workflow"})
        registry.import_bundle(
            "managed.json",
            json.dumps({"manifest": manifest, "workflow": self.template.workflow}).encode("utf-8"),
        )

        listed = self.client.get("/api/editor/workflows")
        self.assertEqual(listed.status_code, 200)
        managed = next(
            item for item in listed.get_json()["workflows"]
            if item["id"] == "managed-workflow"
        )
        self.assertEqual(managed["source"], "user")
        self.assertEqual(managed["validation"]["status"], "warning")
        self.assertIsNone(managed["validation"]["last_validated_at"])

        revalidated = self.client.post("/api/editor/workflows/managed-workflow/revalidate")
        self.assertEqual(revalidated.status_code, 200)
        self.assertEqual(revalidated.get_json()["validation"]["status"], "ready")
        self.assertTrue(revalidated.get_json()["validation"]["inventory_fingerprint"])

        updated = self.client.patch(
            "/api/editor/templates/managed-workflow",
            json={"name": "Renamed workflow", "description": "Managed from the registry."},
        )
        self.assertEqual(updated.status_code, 200)
        self.assertEqual(updated.get_json()["manifest"]["name"], "Renamed workflow")

        deleted = self.client.delete("/api/editor/templates/managed-workflow")
        self.assertEqual(deleted.status_code, 200)
        self.assertFalse(
            (Path(app.config["UPLOAD_FOLDER"]) / "workflow_templates" / "managed-workflow").exists()
        )
        remaining_ids = {
            item["id"]
            for item in self.client.get("/api/editor/workflows").get_json()["workflows"]
        }
        self.assertNotIn("managed-workflow", remaining_ids)

    def test_builtin_workflow_cannot_be_edited_or_deleted(self) -> None:
        edited = self.client.patch(
            "/api/editor/templates/core-image",
            json={"name": "Changed"},
        )
        deleted = self.client.delete("/api/editor/templates/core-image")

        self.assertEqual(edited.status_code, 422)
        self.assertEqual(edited.get_json()["code"], "builtin_template_read_only")
        self.assertEqual(deleted.status_code, 422)
        self.assertEqual(deleted.get_json()["code"], "builtin_template_read_only")

    @patch("app.comfyui.editor_routes._inventory")
    def test_bootstrap_filters_resources_for_standard_and_gguf_slots(self, inventory_mock) -> None:
        inventory_mock.return_value = RuntimeInventory(
            online=True,
            node_types=[],
            models={
                "diffusion_models": ["flux.safetensors", "flux.Q4_K_M.gguf"],
                "unet_gguf": ["pony.Q4_K_M.gguf"],
                "text_encoders": ["clip_l.safetensors", "t5xxl.Q5_K_M.gguf"],
                "vae": ["ae.safetensors"],
            },
            source="api",
        )

        response = self.client.get("/api/editor/bootstrap")

        self.assertEqual(response.status_code, 200)
        templates = {
            item["manifest"]["id"]: item
            for item in response.get_json()["templates"]
        }
        self.assertEqual(
            [item["name"] for item in templates["core-flux"]["resource_options"]["diffusion_model"]],
            ["flux.safetensors"],
        )
        self.assertEqual(
            [item["name"] for item in templates["core-flux-gguf"]["resource_options"]["diffusion_model"]],
            ["flux.Q4_K_M.gguf", "pony.Q4_K_M.gguf"],
        )
        self.assertEqual(
            [item["name"] for item in templates["core-pony-gguf"]["resource_options"]["diffusion_model"]],
            ["flux.Q4_K_M.gguf", "pony.Q4_K_M.gguf"],
        )
        self.assertEqual(
            [item["name"] for item in templates["core-flux-gguf"]["resource_options"]["t5xxl"]],
            ["clip_l.safetensors", "t5xxl.Q5_K_M.gguf"],
        )

    @patch("app.comfyui.editor_routes._inventory")
    def test_bootstrap_and_preflight_explain_incompatible_model(self, inventory_mock) -> None:
        inventory_mock.return_value = self.inventory
        ModelResourceCatalog().register(ModelResource(
            content_hash="flux-checkpoint-123",
            file_path="models/base-xl.safetensors",
            resource_type=ResourceType.CHECKPOINT,
            architecture=ModelEcosystem.FLUX_1,
            display_name="Flux checkpoint in checkpoint folder",
            technical_status=CompatibilityStatus.INCOMPATIBLE,
            restriction_reason="This checkpoint requires a separate-components Flux workflow.",
        ))

        bootstrap = self.client.get("/api/editor/bootstrap")
        templates = {
            item["manifest"]["id"]: item
            for item in bootstrap.get_json()["templates"]
        }
        option = templates["core-image"]["resource_options"]["checkpoint"][0]
        self.assertEqual(option["compatibility_status"], "incompatible")
        self.assertEqual(
            option["compatibility_reason"],
            "This checkpoint requires a separate-components Flux workflow.",
        )

        draft = WorkflowStore().create_draft(
            template_id="core-image",
            template_version="1.0.0",
            values=default_field_values(self.template),
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )
        preview = self.client.post(f"/api/editor/drafts/{draft.id}/preview")
        dependencies = preview.get_json()["dependencies"]

        self.assertFalse(dependencies["ready"])
        self.assertEqual(dependencies["compatibility_issues"][0]["status"], "incompatible")
        self.assertEqual(
            dependencies["compatibility_issues"][0]["reason"],
            "This checkpoint requires a separate-components Flux workflow.",
        )

    @patch("app.comfyui.editor_routes._inventory")
    def test_run_is_blocked_when_runtime_dependencies_are_missing(self, inventory_mock) -> None:
        inventory_mock.return_value = RuntimeInventory(online=False, error="offline")
        draft = WorkflowStore().create_draft(
            template_id="core-image",
            template_version="1.0.0",
            values=default_field_values(self.template),
            resource_selections={},
        )

        response = self.client.post(f"/api/editor/drafts/{draft.id}/run")

        self.assertEqual(response.status_code, 409)
        payload = response.get_json()
        self.assertEqual(payload["code"], "workflow_dependencies_missing")
        self.assertTrue(payload["dependencies"]["missing_nodes"])
        self.assertTrue(payload["dependencies"]["missing_resources"])

    def test_run_results_exclude_assets_deleted_from_library(self) -> None:
        store = WorkflowStore()
        draft = store.create_draft(
            template_id="core-image",
            template_version="1.0.0",
            values=default_field_values(self.template),
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )
        run = store.create_run(
            draft_id=draft.id,
            prompt_id="prompt-deleted-output",
            client_id="editor-test",
        )
        asset_id, _ = database.insert_upload_asset(
            "temporary-result.png",
            PNG_1X1,
            media_type="image",
            has_generation_metadata=True,
        )
        store.update_run(
            run.id,
            status="completed",
            output_asset_ids=[asset_id],
        )

        self.assertTrue(database.delete_image(asset_id))
        response = self.client.get("/api/editor/runs")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["runs"][0]["output_asset_ids"], [])
        self.assertEqual(store.get_run(run.id).output_asset_ids, [asset_id])

    @patch("app.comfyui.editor_routes.client_from_store")
    def test_remix_creates_manual_reference_draft_without_running(self, client_mock) -> None:
        runtime = client_mock.return_value
        runtime.upload_image.return_value = {
            "name": "source.png",
            "subfolder": "cmv/remix",
            "type": "input",
        }
        asset_id, _ = database.insert_upload_asset(
            "source.png",
            PNG_1X1,
            media_type="image",
            has_generation_metadata=True,
            embedded_metadata={
                "prompt_parameters": {
                    "positive_prompt": "A lantern floating over a frozen lake",
                    "negative_prompt": "blurry",
                }
            },
        )

        response = self.client.post("/api/editor/remix", json={"asset_id": asset_id})

        self.assertEqual(response.status_code, 201)
        payload = response.get_json()
        self.assertEqual(payload["draft"]["template_id"], "core-reference")
        self.assertEqual(payload["draft"]["status"], "editing")
        self.assertEqual(payload["draft"]["source_asset_id"], asset_id)
        self.assertEqual(
            payload["draft"]["values"]["positive_prompt"],
            "A lantern floating over a frozen lake",
        )
        self.assertEqual(payload["draft"]["values"]["reference_image"], "cmv/remix/source.png")
        self.assertEqual(WorkflowStore().list_runs(), [])


class FakeCompletedClient:
    def get_job(self, prompt_id):
        return {
            "status": "completed",
            "workflow": {"prompt": {"1": {"class_type": "SaveImage", "inputs": {}}}},
            "outputs": {
                "7": {
                    "images": [{"filename": "result.png", "subfolder": "", "type": "output"}],
                }
            },
        }

    def download_output(self, output):
        return PNG_1X1


class WorkflowExecutionTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.old_db_path = database.get_db_path()
        database.set_db_path(Path(self.temp_dir.name) / "cmv.sqlite3")
        database.init_db()

    def tearDown(self) -> None:
        database.set_db_path(self.old_db_path)
        self.temp_dir.cleanup()

    def test_completed_output_is_imported_into_library(self) -> None:
        store = WorkflowStore()
        template = WorkflowTemplateRegistry().get("core-image")
        draft = store.create_draft(
            template_id=template.manifest.id,
            template_version=template.manifest.version,
            values=default_field_values(template),
            resource_selections={"checkpoint": "models/base-xl.safetensors"},
        )
        run = store.create_run(draft_id=draft.id, prompt_id="prompt-1", client_id="client-1")

        completed = WorkflowExecutionService(store=store, client=FakeCompletedClient()).refresh(run.id)

        self.assertEqual(completed.status, "completed")
        self.assertEqual(len(completed.output_asset_ids), 1)
        detail = database.get_asset_detail(completed.output_asset_ids[0])
        self.assertIsNotNone(detail)
        self.assertEqual(detail.media_type, "image")
        self.assertEqual(detail.embedded_metadata["generation"]["template_id"], "core-image")


if __name__ == "__main__":
    unittest.main()
