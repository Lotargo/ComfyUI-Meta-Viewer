from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .models import (
    CapabilityStatus,
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptScenario,
    PromptTask,
)


CONTENT_DIR = Path(__file__).parent / "content"


class PromptRegistryError(ValueError):
    """Raised when a prompt profile or manifest cannot be resolved."""


@dataclass(frozen=True)
class ManifestDefinition:
    manifest_id: str
    version: str
    path: Path
    families: frozenset[PromptFamily] | None = None

    def supports_family(self, family: PromptFamily) -> bool:
        return self.families is None or family in self.families


@dataclass(frozen=True)
class FamilyProfile:
    family: PromptFamily
    version: str
    legacy_skill_name: str
    capabilities: dict[PromptScenario, CapabilityStatus]

    def capability_for(self, scenario: PromptScenario) -> CapabilityStatus:
        return self.capabilities.get(scenario, CapabilityStatus.UNSUPPORTED)


_ALL_FAMILIES = frozenset(PromptFamily)


FAMILY_PROFILES: dict[PromptFamily, FamilyProfile] = {
    PromptFamily.FLUX: FamilyProfile(
        family=PromptFamily.FLUX,
        version="legacy-1",
        legacy_skill_name="flux",
        capabilities={
            PromptScenario.PORTRAIT: CapabilityStatus.SUPPORTED,
            PromptScenario.SINGLE_CHARACTER: CapabilityStatus.SUPPORTED,
            PromptScenario.PRODUCT_OBJECT: CapabilityStatus.SUPPORTED,
            PromptScenario.ARCHITECTURE_INTERIOR: CapabilityStatus.SUPPORTED,
            PromptScenario.LANDSCAPE_ENVIRONMENT: CapabilityStatus.SUPPORTED,
            PromptScenario.ILLUSTRATION_ART: CapabilityStatus.SUPPORTED,
            PromptScenario.GRAPHIC_DESIGN_TEXT: CapabilityStatus.SUPPORTED,
            PromptScenario.MULTI_CHARACTER: CapabilityStatus.CHECKPOINT_ONLY,
        },
    ),
    PromptFamily.SDXL: FamilyProfile(
        family=PromptFamily.SDXL,
        version="legacy-1",
        legacy_skill_name="sdxl",
        capabilities={
            PromptScenario.PORTRAIT: CapabilityStatus.SUPPORTED,
            PromptScenario.SINGLE_CHARACTER: CapabilityStatus.SUPPORTED,
            PromptScenario.PRODUCT_OBJECT: CapabilityStatus.SUPPORTED,
            PromptScenario.ARCHITECTURE_INTERIOR: CapabilityStatus.SUPPORTED,
            PromptScenario.LANDSCAPE_ENVIRONMENT: CapabilityStatus.SUPPORTED,
            PromptScenario.ILLUSTRATION_ART: CapabilityStatus.SUPPORTED,
            PromptScenario.GRAPHIC_DESIGN_TEXT: CapabilityStatus.LIMITED,
            PromptScenario.MULTI_CHARACTER: CapabilityStatus.CHECKPOINT_ONLY,
        },
    ),
    PromptFamily.PONY: FamilyProfile(
        family=PromptFamily.PONY,
        version="legacy-1",
        legacy_skill_name="pony",
        capabilities={
            PromptScenario.PORTRAIT: CapabilityStatus.SUPPORTED,
            PromptScenario.SINGLE_CHARACTER: CapabilityStatus.SUPPORTED,
            PromptScenario.PRODUCT_OBJECT: CapabilityStatus.LIMITED,
            PromptScenario.ARCHITECTURE_INTERIOR: CapabilityStatus.LIMITED,
            PromptScenario.LANDSCAPE_ENVIRONMENT: CapabilityStatus.SUPPORTED,
            PromptScenario.ILLUSTRATION_ART: CapabilityStatus.SUPPORTED,
            PromptScenario.GRAPHIC_DESIGN_TEXT: CapabilityStatus.UNSUPPORTED,
            PromptScenario.MULTI_CHARACTER: CapabilityStatus.UNSUPPORTED,
        },
    ),
}


OPERATION_MANIFESTS: dict[PromptOperation, ManifestDefinition] = {
    operation: ManifestDefinition(
        manifest_id=operation.value,
        version="1",
        path=CONTENT_DIR / "operations" / f"{operation.value}.md",
        families=_ALL_FAMILIES,
    )
    for operation in PromptOperation
}


SCENARIO_MANIFESTS: dict[PromptScenario, ManifestDefinition] = {
    PromptScenario.PORTRAIT: ManifestDefinition(
        manifest_id=PromptScenario.PORTRAIT.value,
        version="1",
        path=CONTENT_DIR / "scenarios" / "portrait.md",
        families=_ALL_FAMILIES,
    ),
    PromptScenario.SINGLE_CHARACTER: ManifestDefinition(
        manifest_id=PromptScenario.SINGLE_CHARACTER.value,
        version="1",
        path=CONTENT_DIR / "scenarios" / "single_character.md",
        families=_ALL_FAMILIES,
    ),
    PromptScenario.PRODUCT_OBJECT: ManifestDefinition(
        manifest_id=PromptScenario.PRODUCT_OBJECT.value,
        version="1",
        path=CONTENT_DIR / "scenarios" / "product_object.md",
        families=_ALL_FAMILIES,
    ),
    PromptScenario.GRAPHIC_DESIGN_TEXT: ManifestDefinition(
        manifest_id=PromptScenario.GRAPHIC_DESIGN_TEXT.value,
        version="1",
        path=CONTENT_DIR / "scenarios" / "graphic_design_text.md",
        families=frozenset({PromptFamily.FLUX, PromptFamily.SDXL}),
    ),
}


MODIFIER_MANIFESTS: dict[PromptModifier, ManifestDefinition] = {
    modifier: ManifestDefinition(
        manifest_id=modifier.value,
        version="1",
        path=CONTENT_DIR / "modifiers" / f"{modifier.value}.md",
        families=_ALL_FAMILIES,
    )
    for modifier in PromptModifier
}


OUTPUT_CONTRACTS: dict[str, ManifestDefinition] = {
    "prompt_result": ManifestDefinition(
        manifest_id="prompt_result",
        version="1",
        path=CONTENT_DIR / "output_contracts" / "prompt_result.md",
        families=_ALL_FAMILIES,
    )
}


def get_family_profile(family: PromptFamily) -> FamilyProfile:
    try:
        return FAMILY_PROFILES[family]
    except KeyError as exc:
        raise PromptRegistryError(f"Unknown prompt family: {family!s}") from exc


def get_operation_manifest(operation: PromptOperation) -> ManifestDefinition:
    try:
        return OPERATION_MANIFESTS[operation]
    except KeyError as exc:
        raise PromptRegistryError(f"Unknown prompt operation: {operation!s}") from exc


def get_scenario_manifest(scenario: PromptScenario) -> ManifestDefinition:
    try:
        return SCENARIO_MANIFESTS[scenario]
    except KeyError as exc:
        raise PromptRegistryError(
            f"Scenario manifest '{scenario.value}' has not been migrated yet."
        ) from exc


def get_modifier_manifest(modifier: PromptModifier) -> ManifestDefinition:
    try:
        return MODIFIER_MANIFESTS[modifier]
    except KeyError as exc:
        raise PromptRegistryError(f"Unknown prompt modifier: {modifier!s}") from exc


def get_output_contract(contract_id: str) -> ManifestDefinition:
    try:
        return OUTPUT_CONTRACTS[contract_id]
    except KeyError as exc:
        raise PromptRegistryError(f"Unknown output contract: {contract_id}") from exc


def resolve_capability(task: PromptTask) -> CapabilityStatus:
    profile = get_family_profile(task.family)
    status = profile.capability_for(task.scenario)

    if status is CapabilityStatus.UNSUPPORTED:
        raise PromptRegistryError(
            f"Scenario '{task.scenario.value}' is unsupported for family "
            f"'{task.family.value}'."
        )
    if status is CapabilityStatus.CHECKPOINT_ONLY:
        target = task.checkpoint_profile or "the selected checkpoint"
        raise PromptRegistryError(
            f"Scenario '{task.scenario.value}' requires an explicit tested "
            f"checkpoint capability profile; no override exists for {target}."
        )

    manifest = get_scenario_manifest(task.scenario)
    if not manifest.supports_family(task.family):
        raise PromptRegistryError(
            f"Scenario manifest '{task.scenario.value}' is not available for "
            f"family '{task.family.value}'."
        )
    return status
