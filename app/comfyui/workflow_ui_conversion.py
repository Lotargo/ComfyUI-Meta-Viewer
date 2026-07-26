from __future__ import annotations

from dataclasses import dataclass
from typing import Any


FRONTEND_ONLY_NODE_TYPES = {"MarkdownNote", "Note", "PrimitiveNode", "Reroute"}
DISABLED_NODE_MODE = 2
BYPASS_NODE_MODE = 4
SEED_CONTROL_VALUES = {"decrement", "fixed", "increment", "randomize"}


class UIWorkflowConversionError(ValueError):
    def __init__(self, message: str, *, code: str = "ui_workflow_conversion_failed"):
        self.code = code
        super().__init__(message)


@dataclass(frozen=True)
class UIWorkflowConversionResult:
    workflow: dict[str, Any]
    warnings: list[str]


def unwrap_ui_workflow(payload: Any) -> dict[str, Any] | None:
    if _is_ui_workflow(payload):
        return payload
    if not isinstance(payload, dict):
        return None
    for key in ("workflow", "workflow_data"):
        candidate = payload.get(key)
        if _is_ui_workflow(candidate):
            return candidate
    return None


def convert_ui_workflow(
    payload: dict[str, Any],
    *,
    object_info: dict[str, Any] | None = None,
) -> UIWorkflowConversionResult:
    """Convert a self-describing ComfyUI UI graph into prompt API format.

    Current ComfyUI workflow files preserve input names and widget ownership on
    every node. That information is sufficient for a deterministic conversion.
    Older files that only contain positional ``widgets_values`` can use matching
    node contracts from ``/object_info``. Without those contracts they are
    rejected so an incorrectly shifted sampler or model value is never registered.
    """

    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list) or not raw_nodes:
        raise UIWorkflowConversionError(
            "The ComfyUI UI workflow does not contain any nodes.",
            code="ui_workflow_empty",
        )

    nodes: dict[str, dict[str, Any]] = {}
    for index, raw_node in enumerate(raw_nodes):
        if not isinstance(raw_node, dict):
            raise UIWorkflowConversionError(
                f"UI workflow node at position {index} is not an object."
            )
        node_id = _node_id(raw_node.get("id"), label=f"node at position {index}")
        if node_id in nodes:
            raise UIWorkflowConversionError(
                f"UI workflow contains duplicate node ID '{node_id}'."
            )
        node_type = raw_node.get("type")
        if not isinstance(node_type, str) or not node_type.strip():
            raise UIWorkflowConversionError(
                f"UI workflow node '{node_id}' does not declare a node type."
            )
        nodes[node_id] = raw_node

    links = _link_index(payload.get("links"))
    warnings: list[str] = []
    converted: dict[str, Any] = {}

    for node_id, node in nodes.items():
        node_type = str(node["type"])
        mode = _node_mode(node)
        if mode in {DISABLED_NODE_MODE, BYPASS_NODE_MODE} or node_type in FRONTEND_ONLY_NODE_TYPES:
            continue
        if mode != 0:
            raise UIWorkflowConversionError(
                f"Node {node_id} · {node_type} uses unsupported execution mode {mode}. "
                "Set it to Always before importing."
            )

        raw_inputs = node.get("inputs") or []
        if not isinstance(raw_inputs, list):
            raise UIWorkflowConversionError(
                f"Node {node_id} · {node_type} has an invalid inputs list."
            )

        api_inputs: dict[str, Any] = {}
        embedded_widget_inputs: list[dict[str, Any]] = []
        for input_index, input_spec in enumerate(raw_inputs):
            if not isinstance(input_spec, dict):
                raise UIWorkflowConversionError(
                    f"Input {input_index} of node {node_id} · {node_type} is invalid."
                )
            input_name = input_spec.get("name")
            if not isinstance(input_name, str) or not input_name:
                raise UIWorkflowConversionError(
                    f"Input {input_index} of node {node_id} · {node_type} has no name."
                )
            link_id = input_spec.get("link")
            if link_id is not None:
                api_inputs[input_name] = _resolve_link_source(
                    link_id,
                    nodes=nodes,
                    links=links,
                    seen=set(),
                )
            elif input_spec.get("widget") is not None:
                embedded_widget_inputs.append(input_spec)

        widget_values = node.get("widgets_values") or []
        widget_inputs = _widget_inputs(
            node_type,
            raw_inputs,
            embedded_widget_inputs,
            object_info=object_info,
        )
        if isinstance(widget_values, dict):
            for input_spec in widget_inputs:
                input_name = str(input_spec["name"])
                widget_name = _widget_name(input_spec)
                if widget_name in widget_values:
                    api_inputs[input_name] = widget_values[widget_name]
                elif input_name in widget_values:
                    api_inputs[input_name] = widget_values[input_name]
                else:
                    raise UIWorkflowConversionError(
                        f"Node {node_id} · {node_type} has no serialized value for widget '{input_name}'."
                    )
        elif isinstance(widget_values, list):
            if widget_values and not widget_inputs:
                raise UIWorkflowConversionError(
                    f"Node {node_id} · {node_type} uses positional widget values without input metadata. "
                    "Connect its ComfyUI installation, or open and save the workflow in a current "
                    "ComfyUI version, then import it again.",
                    code="ui_workflow_missing_input_metadata",
                )
            assigned, ignored = _assign_widget_values(
                node_id,
                node_type,
                widget_inputs,
                widget_values,
            )
            api_inputs.update(assigned)
            if ignored:
                warnings.append(
                    f"Node {node_id} · {node_type}: ignored {ignored} frontend-only widget value(s)."
                )
        else:
            raise UIWorkflowConversionError(
                f"Node {node_id} · {node_type} has invalid serialized widget values."
            )

        api_node: dict[str, Any] = {"class_type": node_type, "inputs": api_inputs}
        title = node.get("title")
        if isinstance(title, str) and title.strip() and title.strip() != node_type:
            api_node["_meta"] = {"title": title.strip()}
        converted[node_id] = api_node

    if not converted:
        raise UIWorkflowConversionError(
            "The UI workflow contains no executable nodes after disabled and frontend-only nodes are removed.",
            code="ui_workflow_empty",
        )
    return UIWorkflowConversionResult(workflow=converted, warnings=warnings)


def ui_workflow_needs_object_info(payload: dict[str, Any]) -> bool:
    """Return whether executable nodes have values but no widget ownership metadata."""

    raw_nodes = payload.get("nodes")
    if not isinstance(raw_nodes, list):
        return False
    for node in raw_nodes:
        if not isinstance(node, dict):
            continue
        if node.get("type") in FRONTEND_ONLY_NODE_TYPES or node.get("mode", 0) != 0:
            continue
        values = node.get("widgets_values")
        if not values:
            continue
        raw_inputs = node.get("inputs") or []
        if not isinstance(raw_inputs, list) or not any(
            isinstance(item, dict) and item.get("widget") is not None
            for item in raw_inputs
        ):
            return True
    return False


def _is_ui_workflow(payload: Any) -> bool:
    return (
        isinstance(payload, dict)
        and isinstance(payload.get("nodes"), list)
        and isinstance(payload.get("links"), list)
    )


def _node_id(value: Any, *, label: str) -> str:
    if isinstance(value, bool) or not isinstance(value, (int, str)) or str(value).strip() == "":
        raise UIWorkflowConversionError(f"UI workflow {label} has an invalid ID.")
    return str(value)


def _node_mode(node: dict[str, Any]) -> int:
    value = node.get("mode", 0)
    if isinstance(value, bool) or not isinstance(value, int):
        raise UIWorkflowConversionError(
            f"UI workflow node '{node.get('id')}' has an invalid execution mode."
        )
    return value


def _link_index(raw_links: Any) -> dict[str, dict[str, Any]]:
    if not isinstance(raw_links, list):
        raise UIWorkflowConversionError("The UI workflow has an invalid links list.")
    links: dict[str, dict[str, Any]] = {}
    for index, raw_link in enumerate(raw_links):
        if isinstance(raw_link, list) and len(raw_link) >= 6:
            link_id, origin_id, origin_slot, target_id, target_slot, link_type = raw_link[:6]
        elif isinstance(raw_link, dict):
            link_id = raw_link.get("id")
            origin_id = raw_link.get("origin_id")
            origin_slot = raw_link.get("origin_slot")
            target_id = raw_link.get("target_id")
            target_slot = raw_link.get("target_slot")
            link_type = raw_link.get("type")
        else:
            raise UIWorkflowConversionError(f"UI workflow link at position {index} is invalid.")
        clean_id = _node_id(link_id, label=f"link at position {index}")
        if clean_id in links:
            raise UIWorkflowConversionError(f"UI workflow contains duplicate link ID '{clean_id}'.")
        if isinstance(origin_slot, bool) or not isinstance(origin_slot, int) or origin_slot < 0:
            raise UIWorkflowConversionError(f"UI workflow link '{clean_id}' has an invalid origin slot.")
        links[clean_id] = {
            "origin_id": _node_id(origin_id, label=f"link '{clean_id}' origin"),
            "origin_slot": origin_slot,
            "target_id": _node_id(target_id, label=f"link '{clean_id}' target"),
            "target_slot": target_slot,
            "type": link_type,
        }
    return links


def _resolve_link_source(
    link_id: Any,
    *,
    nodes: dict[str, dict[str, Any]],
    links: dict[str, dict[str, Any]],
    seen: set[str],
) -> Any:
    clean_link_id = str(link_id)
    if clean_link_id in seen:
        raise UIWorkflowConversionError(
            f"UI workflow contains a cycle while resolving link '{clean_link_id}'."
        )
    link = links.get(clean_link_id)
    if link is None:
        raise UIWorkflowConversionError(
            f"UI workflow input refers to missing link '{clean_link_id}'."
        )
    origin_id = link["origin_id"]
    origin = nodes.get(origin_id)
    if origin is None:
        raise UIWorkflowConversionError(
            f"UI workflow link '{clean_link_id}' refers to missing node '{origin_id}'."
        )
    origin_type = str(origin["type"])
    mode = _node_mode(origin)
    if mode == DISABLED_NODE_MODE:
        raise UIWorkflowConversionError(
            f"Link '{clean_link_id}' depends on disabled node {origin_id} · {origin_type}. "
            "Reconnect or enable that node before importing."
        )
    if origin_type == "PrimitiveNode":
        values = origin.get("widgets_values") or []
        if not isinstance(values, list) or not values:
            raise UIWorkflowConversionError(
                f"Primitive node {origin_id} has no serialized value for link '{clean_link_id}'."
            )
        return values[0]
    if origin_type == "Reroute" or mode == BYPASS_NODE_MODE:
        upstream = _bypass_input_link(origin, link.get("type"))
        if upstream is None:
            raise UIWorkflowConversionError(
                f"Cannot resolve bypassed node {origin_id} · {origin_type}; its matching input is not connected."
            )
        return _resolve_link_source(
            upstream,
            nodes=nodes,
            links=links,
            seen={*seen, clean_link_id},
        )
    if origin_type in FRONTEND_ONLY_NODE_TYPES:
        raise UIWorkflowConversionError(
            f"Link '{clean_link_id}' depends on unsupported frontend-only node "
            f"{origin_id} · {origin_type}."
        )
    if mode != 0:
        raise UIWorkflowConversionError(
            f"Link '{clean_link_id}' depends on node {origin_id} · {origin_type} with unsupported mode {mode}."
        )
    return [origin_id, link["origin_slot"]]


def _bypass_input_link(node: dict[str, Any], output_type: Any) -> Any | None:
    raw_inputs = node.get("inputs") or []
    if not isinstance(raw_inputs, list):
        return None
    connected = [item for item in raw_inputs if isinstance(item, dict) and item.get("link") is not None]
    matching = [item for item in connected if item.get("type") == output_type]
    candidates = matching or connected
    return candidates[0].get("link") if len(candidates) == 1 else None


def _widget_name(input_spec: dict[str, Any]) -> str:
    widget = input_spec.get("widget")
    if isinstance(widget, dict) and isinstance(widget.get("name"), str):
        return widget["name"]
    return str(input_spec["name"])


def _widget_inputs(
    node_type: str,
    raw_inputs: list[Any],
    embedded: list[dict[str, Any]],
    *,
    object_info: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(object_info, dict):
        return embedded
    definition = object_info.get(node_type)
    if not isinstance(definition, dict):
        return embedded
    input_contract = definition.get("input")
    if not isinstance(input_contract, dict):
        return embedded

    linked_names = {
        str(item.get("name"))
        for item in raw_inputs
        if isinstance(item, dict) and item.get("link") is not None
    }
    declared: list[dict[str, Any]] = []
    for section in ("required", "optional"):
        definitions = input_contract.get(section)
        if not isinstance(definitions, dict):
            continue
        for name, config in definitions.items():
            if str(name) in linked_names or not _definition_is_widget(config):
                continue
            declared.append({
                "name": str(name),
                "type": _definition_widget_type(config),
                "link": None,
                "widget": {"name": str(name)},
            })

    if not declared:
        return embedded
    declared_names = {item["name"] for item in declared}
    declared.extend(item for item in embedded if item.get("name") not in declared_names)
    return declared


def _definition_is_widget(config: Any) -> bool:
    if not isinstance(config, (list, tuple)) or not config:
        return False
    input_type = config[0]
    if isinstance(input_type, list):
        return True
    return str(input_type).upper() in {"BOOL", "BOOLEAN", "COMBO", "FLOAT", "INT", "INTEGER", "NUMBER", "STRING"}


def _definition_widget_type(config: Any) -> Any:
    input_type = config[0]
    if isinstance(input_type, list):
        return input_type
    return str(input_type)


def _assign_widget_values(
    node_id: str,
    node_type: str,
    widget_inputs: list[dict[str, Any]],
    values: list[Any],
) -> tuple[dict[str, Any], int]:
    assigned: dict[str, Any] = {}
    cursor = 0
    ignored = 0
    for input_spec in widget_inputs:
        expected_type = input_spec.get("type")
        match_index = next(
            (
                index
                for index in range(cursor, len(values))
                if _matches_widget_type(values[index], expected_type)
            ),
            None,
        )
        if match_index is None:
            raise UIWorkflowConversionError(
                f"Node {node_id} · {node_type} has no compatible serialized value for widget "
                f"'{input_spec['name']}'."
            )
        ignored += match_index - cursor
        assigned[str(input_spec["name"])] = values[match_index]
        cursor = match_index + 1
    ignored += len(values) - cursor
    return assigned, ignored


def _matches_widget_type(value: Any, expected_type: Any) -> bool:
    if value is None:
        return True
    if isinstance(expected_type, list):
        return value in expected_type
    clean_type = str(expected_type or "").upper()
    if clean_type in {"INT", "INTEGER"}:
        return isinstance(value, int) and not isinstance(value, bool)
    if clean_type in {"FLOAT", "NUMBER"}:
        return isinstance(value, (int, float)) and not isinstance(value, bool)
    if clean_type in {"BOOLEAN", "BOOL"}:
        return isinstance(value, bool)
    if clean_type in {"STRING", "COMBO"}:
        return isinstance(value, str)
    # Custom widgets commonly serialize JSON objects or arrays. Their embedded
    # input metadata is still authoritative even when the type is extension-defined.
    return value not in SEED_CONTROL_VALUES


__all__ = [
    "UIWorkflowConversionError",
    "UIWorkflowConversionResult",
    "convert_ui_workflow",
    "ui_workflow_needs_object_info",
    "unwrap_ui_workflow",
]
