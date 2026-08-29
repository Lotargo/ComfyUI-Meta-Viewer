from __future__ import annotations

import ast
import json
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
OPENAPI_PATH = ROOT / "site" / "api" / "openapi.json"

# These modules define the supported public HTTP contract. The pre-Simple-Mode
# app/comfyui/editor_routes.py surface is intentionally legacy/internal and is
# therefore not part of the public OpenAPI coverage gate.
PUBLIC_ROUTE_FILES = (
    ROOT / "app" / "main.py",
    ROOT / "app" / "ai" / "routes.py",
    ROOT / "app" / "comfyui" / "routes.py",
    ROOT / "app" / "comfyui" / "simple_routes.py",
    ROOT / "app" / "integrations" / "social" / "routes.py",
)

HTTP_METHODS = {
    "GET",
    "POST",
    "PUT",
    "PATCH",
    "DELETE",
    "OPTIONS",
    "HEAD",
    "TRACE",
}
FLASK_PARAMETER_RE = re.compile(r"<(?:[^:<>]+:)?([^<>]+)>")
OPENAPI_PARAMETER_RE = re.compile(r"\{([^{}]+)\}")


def _normalize_flask_path(path: str) -> str:
    return FLASK_PARAMETER_RE.sub(r"{\1}", path)


def _decorator_methods(call: ast.Call) -> set[str]:
    for keyword in call.keywords:
        if keyword.arg != "methods":
            continue
        value = ast.literal_eval(keyword.value)
        return {str(method).upper() for method in value}
    return {"GET"}


def _routes_from_source(path: Path) -> set[tuple[str, str]]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    routes: set[tuple[str, str]] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for decorator in node.decorator_list:
            if not isinstance(decorator, ast.Call):
                continue
            if not isinstance(decorator.func, ast.Attribute):
                continue
            if decorator.func.attr != "route" or not decorator.args:
                continue

            try:
                raw_path = ast.literal_eval(decorator.args[0])
            except (ValueError, SyntaxError):
                continue
            if not isinstance(raw_path, str) or not raw_path.startswith("/api/"):
                continue

            normalized_path = _normalize_flask_path(raw_path)
            for method in _decorator_methods(decorator):
                if method in HTTP_METHODS:
                    routes.add((normalized_path, method))

    return routes


def _source_routes() -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for route_file in PUBLIC_ROUTE_FILES:
        routes.update(_routes_from_source(route_file))
    return routes


def _load_openapi() -> dict:
    return json.loads(OPENAPI_PATH.read_text(encoding="utf-8"))


def _openapi_routes(spec: dict) -> set[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for path, path_item in spec.get("paths", {}).items():
        for method in path_item:
            normalized_method = method.upper()
            if normalized_method in HTTP_METHODS:
                routes.add((path, normalized_method))
    return routes


def _format_routes(routes: set[tuple[str, str]]) -> str:
    return "\n".join(f"  {method:6} {path}" for path, method in sorted(routes))


def _walk(value, location: str = "$"):
    yield location, value
    if isinstance(value, dict):
        for key, child in value.items():
            yield from _walk(child, f"{location}.{key}")
    elif isinstance(value, list):
        for index, child in enumerate(value):
            yield from _walk(child, f"{location}[{index}]")


def test_public_openapi_matches_supported_flask_routes() -> None:
    """Every supported non-legacy Flask route must be present in public OpenAPI."""
    source_routes = _source_routes()
    documented_routes = _openapi_routes(_load_openapi())

    missing = source_routes - documented_routes
    stale = documented_routes - source_routes

    assert not missing and not stale, (
        "Public Flask/OpenAPI route drift detected.\n"
        f"\nMissing from site/api/openapi.json:\n{_format_routes(missing) or '  (none)'}\n"
        f"\nDocumented but not implemented:\n{_format_routes(stale) or '  (none)'}"
    )


def test_openapi_operations_have_navigation_metadata() -> None:
    """Keep Scalar navigation stable and generated clients deterministic."""
    spec = _load_openapi()
    assert spec.get("openapi") == "3.1.0"

    operation_ids: set[str] = set()
    for path, path_item in spec["paths"].items():
        for method, operation in path_item.items():
            if method.upper() not in HTTP_METHODS:
                continue

            assert operation.get("summary"), f"{method.upper()} {path} has no summary"
            assert operation.get("tags"), f"{method.upper()} {path} has no tags"

            operation_id = operation.get("operationId")
            assert operation_id, f"{method.upper()} {path} has no operationId"
            assert operation_id not in operation_ids, f"Duplicate operationId: {operation_id}"
            operation_ids.add(operation_id)

            declared_path_parameters = {
                parameter.get("name")
                for parameter in operation.get("parameters", [])
                if parameter.get("in") == "path"
            }
            expected_path_parameters = set(OPENAPI_PARAMETER_RE.findall(path))
            assert declared_path_parameters == expected_path_parameters, (
                f"{method.upper()} {path} path parameters differ: "
                f"expected {sorted(expected_path_parameters)}, "
                f"declared {sorted(declared_path_parameters)}"
            )


def test_openapi_component_references_use_real_ref_keys() -> None:
    """Catch the broken empty-key component references that Scalar cannot resolve."""
    spec = _load_openapi()
    invalid_locations: list[str] = []

    for location, value in _walk(spec):
        if not isinstance(value, dict):
            continue
        empty_value = value.get("")
        if isinstance(empty_value, str) and empty_value.startswith("#/components/"):
            invalid_locations.append(location)

    assert not invalid_locations, (
        "Found component references stored under an empty key instead of $ref:\n  "
        + "\n  ".join(invalid_locations)
    )
