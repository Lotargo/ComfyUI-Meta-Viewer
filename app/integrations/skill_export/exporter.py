from __future__ import annotations

import hashlib
import json
import os
import shutil
import tempfile
from enum import Enum
from pathlib import Path
from typing import Any

from pydantic import Field

from ...ai.prompting import PromptResult, SceneSpec
from ...ai.prompting.models import StrictModel
from ...ai.prompting.registry import (
    FAMILY_PROFILES,
    MODIFIER_MANIFESTS,
    OPERATION_MANIFESTS,
    OUTPUT_CONTRACTS,
    SCENARIO_MANIFESTS,
)


class PromptSkillExportError(RuntimeError):
    """Raised when a native agent-host package cannot be exported safely."""


class SkillExportHost(str, Enum):
    OPENCODE = "opencode"
    CLAUDE_CODE = "claude_code"
    ANTIGRAVITY = "antigravity"
    CODEX = "codex"


class ExportedSkillPackage(StrictModel):
    host: SkillExportHost
    path: Path
    manifest_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")
    files: tuple[str, ...]


_HOST_LABELS = {
    SkillExportHost.OPENCODE: "OpenCode",
    SkillExportHost.CLAUDE_CODE: "Claude Code",
    SkillExportHost.ANTIGRAVITY: "Antigravity",
    SkillExportHost.CODEX: "Codex",
}


class PromptSkillExporter:
    """Generate native skill references without owning any prompt-family rules."""

    package_version = "1"

    def export(
        self,
        destination: str | Path,
        *,
        host: SkillExportHost | str,
    ) -> ExportedSkillPackage:
        try:
            normalized_host = SkillExportHost(host)
        except ValueError as exc:
            raise PromptSkillExportError(f"Unsupported skill export host: {host}") from exc

        target = Path(destination).expanduser().resolve(strict=False)
        if target.exists():
            if not target.is_dir():
                raise PromptSkillExportError(f"Export destination is not a directory: {target}")
            if any(target.iterdir()):
                raise PromptSkillExportError(
                    f"Export destination must be empty: {target}"
                )
        target.parent.mkdir(parents=True, exist_ok=True)

        temp_root = Path(
            tempfile.mkdtemp(prefix=f".{target.name}-", dir=target.parent)
        )
        try:
            files = self._write_package(temp_root, normalized_host)
            manifest_bytes = (temp_root / "manifest.json").read_bytes()
            manifest_sha256 = hashlib.sha256(manifest_bytes).hexdigest()
            if target.exists():
                target.rmdir()
            os.replace(temp_root, target)
        except Exception as exc:
            shutil.rmtree(temp_root, ignore_errors=True)
            if isinstance(exc, PromptSkillExportError):
                raise
            raise PromptSkillExportError(f"Cannot export prompt skill: {exc}") from exc

        return ExportedSkillPackage(
            host=normalized_host,
            path=target,
            manifest_sha256=manifest_sha256,
            files=tuple(files),
        )

    def _write_package(self, root: Path, host: SkillExportHost) -> list[str]:
        payloads = self._canonical_reference_payloads()
        payloads["SKILL.md"] = self._render_skill(host).encode("utf-8")
        payloads["scripts/validate_prompt_result.py"] = (
            self._validator_script().encode("utf-8")
        )

        reference_manifest: dict[str, dict[str, str]] = {}
        for relative_path, content in sorted(payloads.items()):
            self._write(root, relative_path, content)
            if relative_path.startswith("references/"):
                reference_manifest[relative_path] = {
                    "sha256": hashlib.sha256(content).hexdigest(),
                }

        manifest: dict[str, Any] = {
            "package_version": self.package_version,
            "host": host.value,
            "generated_from": "app/ai/prompting",
            "references": reference_manifest,
        }
        manifest_bytes = (
            json.dumps(manifest, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")
        self._write(root, "manifest.json", manifest_bytes)
        return sorted((*payloads.keys(), "manifest.json"))

    @staticmethod
    def _canonical_reference_payloads() -> dict[str, bytes]:
        payloads: dict[str, bytes] = {}
        for family, profile in FAMILY_PROFILES.items():
            payloads[f"references/families/{family.value}-base.md"] = (
                PromptSkillExporter._read_canonical(profile.path)
            )
        for operation, definition in OPERATION_MANIFESTS.items():
            payloads[f"references/operations/{operation.value}.md"] = (
                PromptSkillExporter._read_canonical(definition.path)
            )
        for scenario, definition in SCENARIO_MANIFESTS.items():
            payloads[f"references/scenarios/{scenario.value}.md"] = (
                PromptSkillExporter._read_canonical(definition.path)
            )
        for modifier, definition in MODIFIER_MANIFESTS.items():
            payloads[f"references/modifiers/{modifier.value}.md"] = (
                PromptSkillExporter._read_canonical(definition.path)
            )
        for contract_id, definition in OUTPUT_CONTRACTS.items():
            payloads[f"references/output_contracts/{contract_id}.md"] = (
                PromptSkillExporter._read_canonical(definition.path)
            )
        payloads["references/schemas/scene_spec.schema.json"] = (
            PromptSkillExporter._schema_bytes(SceneSpec.model_json_schema())
        )
        payloads["references/schemas/prompt_result.schema.json"] = (
            PromptSkillExporter._schema_bytes(PromptResult.model_json_schema())
        )
        return payloads

    @staticmethod
    def _read_canonical(path: Path) -> bytes:
        try:
            return path.read_bytes()
        except OSError as exc:
            raise PromptSkillExportError(f"Cannot read canonical prompt file: {path}") from exc

    @staticmethod
    def _schema_bytes(schema: dict[str, Any]) -> bytes:
        return (
            json.dumps(schema, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        ).encode("utf-8")

    @staticmethod
    def _write(root: Path, relative_path: str, content: bytes) -> None:
        path = root / relative_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(content)

    @staticmethod
    def _render_skill(host: SkillExportHost) -> str:
        label = _HOST_LABELS[host]
        return f"""---
name: cmv-prompt-profiles
description: Compile and validate ComfyUI Meta Viewer prompt tasks in {label}.
metadata:
  package_version: \"1\"
  host: {host.value}
---

# ComfyUI Meta Viewer prompt profiles

Use this package when a user asks to generate, reconstruct, adapt, or translate
an image-generation prompt for a supported family.

## Workflow

1. Determine the family, operation, scenario, optional modifiers, and checkpoint.
2. Read exactly one matching file from each applicable directory under
   `references/`: family base, operation, scenario, modifiers, and output contract.
3. Treat `references/output_contracts/prompt_result.md` and hard content boundaries
   as highest priority. Then apply checkpoint overrides, scenario, operation, and
   family defaults in that order.
4. For image reconstruction, represent observations as a `SceneSpec`; preserve
   uncertainty and never invent hidden or unreadable details.
5. Return one strict `PromptResult` JSON object. Run
   `scripts/validate_prompt_result.py <result.json>` before completion when scripts
   are available.

## Selection rules

- Do not use `multi_character` unless an explicit tested checkpoint profile permits it.
- Never infer unsupported capability from model size alone.
- Do not combine `safe` and `adult_only`.
- Do not browse for or invent checkpoint trigger words.
- The files in `references/` are generated from the canonical application registry;
  do not maintain host-specific prompt-rule copies.
"""

    @staticmethod
    def _validator_script() -> str:
        return '''#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: validate_prompt_result.py <result.json>", file=sys.stderr)
        return 2
    try:
        value = json.loads(Path(sys.argv[1]).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"invalid JSON: {exc}", file=sys.stderr)
        return 1
    required = {"schema_version", "positive_prompt", "negative_prompt"}
    if not isinstance(value, dict) or set(value) != required:
        print("result must contain exactly schema_version, positive_prompt, and negative_prompt", file=sys.stderr)
        return 1
    if value["schema_version"] != "1":
        print("unsupported schema_version", file=sys.stderr)
        return 1
    if not isinstance(value["positive_prompt"], str) or not value["positive_prompt"].strip():
        print("positive_prompt must be non-empty text", file=sys.stderr)
        return 1
    if not isinstance(value["negative_prompt"], str):
        print("negative_prompt must be text", file=sys.stderr)
        return 1
    print("valid PromptResult v1")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
'''


__all__ = [
    "ExportedSkillPackage",
    "PromptSkillExportError",
    "PromptSkillExporter",
    "SkillExportHost",
]
