from __future__ import annotations

import json
import os
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from .paths import normalize_path


CONFIG_VERSION = 3
_config_lock = threading.RLock()


class ConfigStoreError(RuntimeError):
    """Raised when the persistent application configuration cannot be used."""


@dataclass(frozen=True)
class SourceSettings:
    path: Path
    name: str
    enabled: bool = True
    recursive: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "path": str(self.path),
            "name": self.name,
            "enabled": self.enabled,
            "recursive": self.recursive,
        }


def _default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "sources": [],
        "ai": {
            "profiles": [],
            "defaults": {
                "text_profile_id": None,
                "multimodal_profile_id": None,
            },
        },
    }


class ConfigStore:
    """Persist durable app settings separately from the disposable SQLite index."""

    def __init__(self, path: str | Path):
        self.path = normalize_path(path)
        self.temporary_path = self.path.with_suffix(f"{self.path.suffix}.tmp")

    def load(self) -> dict[str, Any]:
        with _config_lock:
            if not self.path.exists():
                return _default_config()
            try:
                raw = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, json.JSONDecodeError) as exc:
                raise ConfigStoreError(
                    f"Cannot read application configuration: {self.path}: {exc}"
                ) from exc

            if not isinstance(raw, dict) or raw.get("version") not in (
                1,
                2,
                CONFIG_VERSION,
            ):
                raise ConfigStoreError(
                    f"Unsupported application configuration: {self.path}"
                )

            raw_sources = raw.get("sources", [])
            if not isinstance(raw_sources, list):
                raise ConfigStoreError(
                    f"Invalid source list in application configuration: {self.path}"
                )

            sources: list[dict[str, Any]] = []
            seen: set[str] = set()
            for item in raw_sources:
                if not isinstance(item, dict) or not isinstance(item.get("path"), str):
                    continue
                normalized = str(normalize_path(item["path"]))
                if normalized in seen:
                    continue
                seen.add(normalized)
                default_name = Path(normalized).name or normalized
                sources.append({
                    "path": normalized,
                    "name": (
                        item["name"].strip()
                        if isinstance(item.get("name"), str) and item["name"].strip()
                        else default_name
                    ),
                    "enabled": item.get("enabled", item.get("active", True)) is not False,
                    "recursive": item.get("recursive") is True,
                })

            raw_ai = raw.get("ai")
            ai = raw_ai if isinstance(raw_ai, dict) else {}
            raw_profiles = ai.get("profiles")
            profiles = (
                [dict(item) for item in raw_profiles if isinstance(item, dict)]
                if isinstance(raw_profiles, list)
                else []
            )
            raw_defaults = ai.get("defaults")
            defaults = raw_defaults if isinstance(raw_defaults, dict) else {}

            return {
                "version": CONFIG_VERSION,
                "sources": sources,
                "ai": {
                    "profiles": profiles,
                    "defaults": {
                        "text_profile_id": defaults.get("text_profile_id"),
                        "multimodal_profile_id": defaults.get(
                            "multimodal_profile_id"
                        ),
                    },
                },
            }

    def save(self, config: dict[str, Any]) -> None:
        with _config_lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            payload = json.dumps(config, ensure_ascii=False, indent=2) + "\n"
            try:
                with self.temporary_path.open("w", encoding="utf-8", newline="\n") as file:
                    file.write(payload)
                    file.flush()
                    os.fsync(file.fileno())
                self.temporary_path.replace(self.path)
            except OSError as exc:
                raise ConfigStoreError(
                    f"Cannot save application configuration: {self.path}: {exc}"
                ) from exc

    def active_sources(self) -> list[Path]:
        return [
            normalize_path(item["path"])
            for item in self.load()["sources"]
            if item["enabled"]
        ]

    def sources(self) -> list[SourceSettings]:
        return [
            SourceSettings(
                path=normalize_path(item["path"]),
                name=item["name"],
                enabled=item["enabled"],
                recursive=item["recursive"],
            )
            for item in self.load()["sources"]
        ]

    def add_sources(
        self,
        paths: Iterable[str | Path],
        *,
        reactivate: bool = True,
    ) -> None:
        with _config_lock:
            config = self.load()
            sources = config["sources"]
            existing = {item["path"]: item for item in sources}
            changed = False
            for path in paths:
                normalized = str(normalize_path(path))
                if normalized in existing:
                    if reactivate and not existing[normalized]["enabled"]:
                        existing[normalized]["enabled"] = True
                        changed = True
                    continue
                item = SourceSettings(
                    path=Path(normalized),
                    name=Path(normalized).name or normalized,
                ).to_dict()
                sources.append(item)
                existing[normalized] = item
                changed = True
            if changed:
                self.save(config)

    def add_source(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        recursive: bool = False,
    ) -> SourceSettings:
        normalized = normalize_path(path)
        with _config_lock:
            config = self.load()
            sources = config["sources"]
            item = next(
                (entry for entry in sources if entry["path"] == str(normalized)),
                None,
            )
            source_name = (name or "").strip() or normalized.name or str(normalized)
            if item is None:
                item = SourceSettings(
                    path=normalized,
                    name=source_name,
                    recursive=recursive,
                ).to_dict()
                sources.append(item)
            else:
                item.update({
                    "name": source_name if name is not None else item["name"],
                    "enabled": True,
                    "recursive": recursive,
                })
            self.save(config)
        return SourceSettings(
            path=normalized,
            name=item["name"],
            enabled=True,
            recursive=item["recursive"],
        )

    def update_source(
        self,
        path: str | Path,
        *,
        name: str | None = None,
        enabled: bool | None = None,
        recursive: bool | None = None,
    ) -> SourceSettings | None:
        normalized = str(normalize_path(path))
        with _config_lock:
            config = self.load()
            item = next(
                (entry for entry in config["sources"] if entry["path"] == normalized),
                None,
            )
            if item is None:
                return None
            if name is not None:
                item["name"] = name.strip()
            if enabled is not None:
                item["enabled"] = enabled
            if recursive is not None:
                item["recursive"] = recursive
            self.save(config)
            return SourceSettings(
                path=Path(item["path"]),
                name=item["name"],
                enabled=item["enabled"],
                recursive=item["recursive"],
            )

    def remove_source(self, path: str | Path) -> bool:
        normalized = str(normalize_path(path))
        with _config_lock:
            config = self.load()
            sources = config["sources"]
            kept = [item for item in sources if item["path"] != normalized]
            if len(kept) == len(sources):
                return False
            config["sources"] = kept
            self.save(config)
            return True

    def remove_source_for_index_path(self, path: str | Path) -> bool:
        """Remove a source represented by a normal or derived no-metadata folder."""
        normalized = str(normalize_path(path))
        with _config_lock:
            config = self.load()
            sources = config["sources"]
            kept = [
                item
                for item in sources
                if normalized not in (item["path"], f"{item['path']} (no metadata)")
            ]
            if len(kept) == len(sources):
                return False
            config["sources"] = kept
            self.save(config)
            return True

    def delete(self) -> None:
        with _config_lock:
            errors: list[str] = []
            for path in (self.temporary_path, self.path):
                try:
                    path.unlink(missing_ok=True)
                except OSError as exc:
                    errors.append(f"{path}: {exc}")
            if errors:
                raise ConfigStoreError(
                    "Cannot delete application configuration: " + "; ".join(errors)
                )
