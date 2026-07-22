from __future__ import annotations

import hashlib
import json
import sqlite3
from enum import Enum
from pathlib import Path
from typing import Any, Sequence

from pydantic import Field, field_validator

from .. import database
from .prompting.models import StrictModel


class ModelResourceError(RuntimeError):
    """Raised when a model resource operation fails."""


class ResourceType(str, Enum):
    CHECKPOINT = "checkpoint"
    LORA = "lora"
    LOCON = "locon"
    DORA = "dora"
    VAE = "vae"
    EMBEDDING = "embedding"
    UNKNOWN = "unknown"


class ModelEcosystem(str, Enum):
    SD15 = "sd15"
    SDXL = "sdxl"
    FLUX_1 = "flux_1"
    PONY = "pony"
    ILLUSTRIOUS = "illustrious"
    OTHER = "other"


class CompatibilityStatus(str, Enum):
    SUPPORTED = "supported"
    LIMITED = "limited"
    EXPERIMENTAL = "experimental"
    INCOMPATIBLE = "incompatible"


class ModelResource(StrictModel):
    id: int | None = None
    content_hash: str = Field(min_length=8, max_length=128)
    file_path: str = Field(min_length=1, max_length=1000)
    resource_type: ResourceType = ResourceType.UNKNOWN
    architecture: ModelEcosystem = ModelEcosystem.OTHER
    prompt_family: str = Field(default="generic", max_length=100)
    display_name: str = Field(min_length=1, max_length=300)
    version: str = Field(default="", max_length=100)
    preview_url: str | None = Field(default=None, max_length=1000)
    metadata_source: str = Field(default="local", max_length=100)
    trigger_words: list[str] = Field(default_factory=list)
    default_strength: float = Field(default=1.0, ge=-5.0, le=5.0)
    min_strength: float = Field(default=0.0, ge=-5.0, le=5.0)
    max_strength: float = Field(default=2.0, ge=-5.0, le=5.0)
    technical_status: CompatibilityStatus = CompatibilityStatus.SUPPORTED
    restriction_reason: str | None = Field(default=None, max_length=500)
    is_available: bool = True

    @field_validator("content_hash", "display_name", "file_path")
    @classmethod
    def strip_text(cls, value: str) -> str:
        return value.strip()


class CapabilityEvaluation(StrictModel):
    resource_hash: str
    resource_name: str
    resource_type: ResourceType
    checkpoint_architecture: ModelEcosystem
    resource_architecture: ModelEcosystem
    status: CompatibilityStatus
    reason: str | None = None


class CapabilityResolver:
    """Evaluate compatibility between checkpoint architectures and secondary model resources (e.g. LoRAs)."""

    # Ecosystem relationship map: (checkpoint_ecosystem, resource_ecosystem) -> (status, reason)
    CROSS_ECOSYSTEM_RULES: dict[tuple[ModelEcosystem, ModelEcosystem], tuple[CompatibilityStatus, str]] = {
        (ModelEcosystem.PONY, ModelEcosystem.SDXL): (
            CompatibilityStatus.LIMITED,
            "Pony checkpoint is built on SDXL architecture; SDXL LoRAs have limited compatibility.",
        ),
        (ModelEcosystem.SDXL, ModelEcosystem.PONY): (
            CompatibilityStatus.EXPERIMENTAL,
            "Pony LoRAs on standard SDXL checkpoints are experimental.",
        ),
        (ModelEcosystem.ILLUSTRIOUS, ModelEcosystem.SDXL): (
            CompatibilityStatus.LIMITED,
            "Illustrious checkpoint is derived from SDXL; SDXL LoRAs have limited compatibility.",
        ),
    }

    @classmethod
    def evaluate(
        cls,
        *,
        checkpoint_architecture: ModelEcosystem | str,
        resource: ModelResource,
    ) -> CapabilityEvaluation:
        ckpt_arch = (
            ModelEcosystem(checkpoint_architecture)
            if isinstance(checkpoint_architecture, str) and checkpoint_architecture in ModelEcosystem._value2member_map_
            else ModelEcosystem.OTHER
        )

        res_arch = resource.architecture
        res_type = resource.resource_type

        # If matching architecture, it is fully supported
        if ckpt_arch == res_arch or res_arch == ModelEcosystem.OTHER or ckpt_arch == ModelEcosystem.OTHER:
            return CapabilityEvaluation(
                resource_hash=resource.content_hash,
                resource_name=resource.display_name,
                resource_type=res_type,
                checkpoint_architecture=ckpt_arch,
                resource_architecture=res_arch,
                status=CompatibilityStatus.SUPPORTED,
                reason="Matching model ecosystem architecture.",
            )

        # Check explicit cross-ecosystem rules
        rule_key = (ckpt_arch, res_arch)
        if rule_key in cls.CROSS_ECOSYSTEM_RULES:
            status, reason = cls.CROSS_ECOSYSTEM_RULES[rule_key]
            return CapabilityEvaluation(
                resource_hash=resource.content_hash,
                resource_name=resource.display_name,
                resource_type=res_type,
                checkpoint_architecture=ckpt_arch,
                resource_architecture=res_arch,
                status=status,
                reason=reason,
            )

        # Incompatible by default if different architectures (e.g. SDXL vs SD1.5 or Flux vs SDXL)
        reason = f"Resource architecture '{res_arch.value}' is incompatible with checkpoint architecture '{ckpt_arch.value}'."
        return CapabilityEvaluation(
            resource_hash=resource.content_hash,
            resource_name=resource.display_name,
            resource_type=res_type,
            checkpoint_architecture=ckpt_arch,
            resource_architecture=res_arch,
            status=CompatibilityStatus.INCOMPATIBLE,
            reason=reason,
        )

    @classmethod
    def resolve_selection(
        cls,
        *,
        checkpoint_architecture: ModelEcosystem | str,
        resources: Sequence[ModelResource],
    ) -> list[CapabilityEvaluation]:
        """Re-validate a collection of selected resources against a target checkpoint without deleting them."""
        return [
            cls.evaluate(
                checkpoint_architecture=checkpoint_architecture,
                resource=resource,
            )
            for resource in resources
        ]


class ModelResourceCatalog:
    """SQLite-backed catalog of model resources (checkpoints, LoRAs, VAEs, etc.)."""

    def register(self, resource: ModelResource) -> ModelResource:
        conn = database.get_conn()
        try:
            conn.execute(
                """INSERT INTO model_resources (
                    content_hash, file_path, resource_type, architecture, prompt_family,
                    display_name, version, preview_url, metadata_source, trigger_words_json,
                    default_strength, min_strength, max_strength, technical_status,
                    restriction_reason, is_available
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ON CONFLICT(content_hash) DO UPDATE SET
                    file_path=excluded.file_path,
                    resource_type=excluded.resource_type,
                    architecture=excluded.architecture,
                    prompt_family=excluded.prompt_family,
                    display_name=excluded.display_name,
                    version=excluded.version,
                    preview_url=excluded.preview_url,
                    trigger_words_json=excluded.trigger_words_json,
                    default_strength=excluded.default_strength,
                    min_strength=excluded.min_strength,
                    max_strength=excluded.max_strength,
                    technical_status=excluded.technical_status,
                    restriction_reason=excluded.restriction_reason,
                    is_available=excluded.is_available,
                    updated_at=datetime('now')""",
                (
                    resource.content_hash,
                    resource.file_path,
                    resource.resource_type.value,
                    resource.architecture.value,
                    resource.prompt_family,
                    resource.display_name,
                    resource.version,
                    resource.preview_url,
                    resource.metadata_source,
                    json.dumps(resource.trigger_words, ensure_ascii=False),
                    resource.default_strength,
                    resource.min_strength,
                    resource.max_strength,
                    resource.technical_status.value,
                    resource.restriction_reason,
                    1 if resource.is_available else 0,
                ),
            )
            conn.commit()
        except sqlite3.Error as exc:
            conn.rollback()
            raise ModelResourceError(f"Failed to register model resource: {exc}") from exc
        finally:
            conn.close()
        return self.get_by_hash(resource.content_hash)

    def get_by_hash(self, content_hash: str) -> ModelResource:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM model_resources WHERE content_hash=?", (content_hash.strip(),)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise ModelResourceError(f"Model resource with hash '{content_hash}' not found.")
        return self._row_to_model(row)

    def get_by_id(self, resource_id: int) -> ModelResource:
        conn = database.get_conn()
        try:
            row = conn.execute(
                "SELECT * FROM model_resources WHERE id=?", (resource_id,)
            ).fetchone()
        finally:
            conn.close()
        if row is None:
            raise ModelResourceError(f"Model resource with ID {resource_id} not found.")
        return self._row_to_model(row)

    def list_resources(
        self,
        *,
        resource_type: ResourceType | str | None = None,
        architecture: ModelEcosystem | str | None = None,
        only_available: bool = True,
    ) -> list[ModelResource]:
        conn = database.get_conn()
        try:
            query = "SELECT * FROM model_resources WHERE 1=1"
            params: list[Any] = []
            if resource_type:
                rt_val = resource_type.value if isinstance(resource_type, ResourceType) else str(resource_type)
                query += " AND resource_type=?"
                params.append(rt_val)
            if architecture:
                arch_val = architecture.value if isinstance(architecture, ModelEcosystem) else str(architecture)
                query += " AND architecture=?"
                params.append(arch_val)
            if only_available:
                query += " AND is_available=1"
            query += " ORDER BY display_name ASC"
            rows = conn.execute(query, params).fetchall()
        finally:
            conn.close()
        return [self._row_to_model(row) for row in rows]

    @staticmethod
    def _row_to_model(row: sqlite3.Row) -> ModelResource:
        triggers = []
        if row["trigger_words_json"]:
            try:
                triggers = json.loads(row["trigger_words_json"])
            except (json.JSONDecodeError, TypeError):
                triggers = []

        return ModelResource(
            id=row["id"],
            content_hash=row["content_hash"],
            file_path=row["file_path"],
            resource_type=ResourceType(row["resource_type"]),
            architecture=ModelEcosystem(row["architecture"]),
            prompt_family=row["prompt_family"],
            display_name=row["display_name"],
            version=row["version"],
            preview_url=row["preview_url"],
            metadata_source=row["metadata_source"],
            trigger_words=triggers,
            default_strength=float(row["default_strength"]),
            min_strength=float(row["min_strength"]),
            max_strength=float(row["max_strength"]),
            technical_status=CompatibilityStatus(row["technical_status"]),
            restriction_reason=row["restriction_reason"],
            is_available=bool(row["is_available"]),
        )


__all__ = [
    "CapabilityEvaluation",
    "CapabilityResolver",
    "CompatibilityStatus",
    "ModelEcosystem",
    "ModelResource",
    "ModelResourceCatalog",
    "ModelResourceError",
    "ResourceType",
]
