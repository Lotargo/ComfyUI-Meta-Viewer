from __future__ import annotations

import hashlib
from pathlib import Path

from .models import (
    CapabilityStatus,
    InstructionBundle,
    InstructionSection,
    PromptTask,
)
from .registry import (
    ManifestDefinition,
    PromptRegistryError,
    get_family_profile,
    get_modifier_manifest,
    get_operation_manifest,
    get_output_contract,
    get_scenario_manifest,
    resolve_capability,
)


class PromptCompilerError(RuntimeError):
    """Raised when an instruction bundle cannot be compiled."""


class PromptCompiler:
    """Compile researched prompt knowledge into a deterministic instruction bundle.

    Every section is loaded from the canonical prompting content directory.
    The legacy ``load_skill()`` API resolves the same family-base files so old
    consumers remain compatible without keeping a second copy of prompt knowledge.
    """

    def compile(self, task: PromptTask) -> InstructionBundle:
        try:
            family_profile = get_family_profile(task.family)
            capability = resolve_capability(task)
            operation = get_operation_manifest(task.operation)
            scenario = get_scenario_manifest(task.scenario)
            modifiers = tuple(
                get_modifier_manifest(modifier) for modifier in task.modifiers
            )
            output_contract = get_output_contract(task.output_contract)
        except PromptRegistryError as exc:
            raise PromptCompilerError(str(exc)) from exc

        try:
            family_content = family_profile.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptCompilerError(
                f"Cannot read family base '{family_profile.path}'."
            ) from exc

        sections = [
            self._build_section(
                section_id=task.family.value,
                kind="family_base",
                version=family_profile.version,
                source=self._display_path(family_profile.path),
                content=family_content,
            ),
            self._load_manifest(operation, kind="operation"),
            self._load_manifest(scenario, kind="scenario"),
        ]
        sections.extend(
            self._load_manifest(manifest, kind="modifier")
            for manifest in modifiers
        )
        sections.append(self._load_manifest(output_contract, kind="output_contract"))

        warnings: list[str] = []
        if capability is CapabilityStatus.LIMITED:
            warnings.append(
                f"Scenario '{task.scenario.value}' has limited support for "
                f"family '{task.family.value}'. Keep the result editable and "
                "do not present the capability as reliable."
            )
        elif capability is CapabilityStatus.EXPERIMENTAL:
            warnings.append(
                f"Scenario '{task.scenario.value}' is experimental for family "
                f"'{task.family.value}'. Practical verification is required."
            )

        versions = {
            "family": family_profile.version,
            "operation": operation.version,
            "scenario": scenario.version,
            "output_contract": output_contract.version,
        }
        versions.update({
            f"modifier:{manifest.manifest_id}": manifest.version
            for manifest in modifiers
        })

        return InstructionBundle(
            task=task,
            capability_status=capability,
            sections=tuple(sections),
            versions=versions,
            warnings=tuple(warnings),
        )

    @staticmethod
    def _load_manifest(
        definition: ManifestDefinition,
        *,
        kind: str,
    ) -> InstructionSection:
        path = definition.path
        try:
            content = path.read_text(encoding="utf-8")
        except OSError as exc:
            raise PromptCompilerError(
                f"Cannot read {kind} manifest '{definition.manifest_id}' "
                f"from {PromptCompiler._display_path(path)}."
            ) from exc
        return PromptCompiler._build_section(
            section_id=definition.manifest_id,
            kind=kind,
            version=definition.version,
            source=PromptCompiler._display_path(path),
            content=content,
        )

    @staticmethod
    def _build_section(
        *,
        section_id: str,
        kind: str,
        version: str,
        source: str,
        content: str,
    ) -> InstructionSection:
        normalized = content.strip()
        if not normalized:
            raise PromptCompilerError(
                f"The {kind} instruction section '{section_id}' is empty."
            )
        digest = hashlib.sha256(normalized.encode("utf-8")).hexdigest()
        return InstructionSection(
            section_id=section_id,
            kind=kind,
            version=version,
            source=source,
            content_sha256=digest,
            content=normalized,
        )

    @staticmethod
    def _display_path(path: Path) -> str:
        project_root = Path(__file__).resolve().parents[3]
        try:
            return path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            return path.as_posix()
