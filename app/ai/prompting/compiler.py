from __future__ import annotations

from pathlib import Path

from ..skills import load_skill
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

    The first migration slice keeps the existing ``app/ai/skills/*.txt`` files as
    the family-base source. Operation, scenario, modifier, and output layers are
    loaded from the new canonical prompting directory. This preserves
    ``load_skill()`` compatibility while the family bases are migrated gradually.
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

        sections = [
            InstructionSection(
                section_id=task.family.value,
                kind="family_base",
                version=family_profile.version,
                source=f"app/ai/skills/{family_profile.legacy_skill_name}.txt",
                content=load_skill(family_profile.legacy_skill_name),
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
        if not content.strip():
            raise PromptCompilerError(
                f"The {kind} manifest '{definition.manifest_id}' is empty."
            )
        return InstructionSection(
            section_id=definition.manifest_id,
            kind=kind,
            version=definition.version,
            source=PromptCompiler._display_path(path),
            content=content,
        )

    @staticmethod
    def _display_path(path: Path) -> str:
        project_root = Path(__file__).resolve().parents[3]
        try:
            return path.resolve().relative_to(project_root).as_posix()
        except ValueError:
            return path.as_posix()
