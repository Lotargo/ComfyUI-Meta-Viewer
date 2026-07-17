from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from typing import Any, Iterable

from .paths import normalize_path


CONFIG_VERSION = 1
_config_lock = threading.RLock()


class ConfigStoreError(RuntimeError):
    """Raised when the persistent application configuration cannot be used."""


def _default_config() -> dict[str, Any]:
    return {
        "version": CONFIG_VERSION,
        "sources": [],
    }


class ConfigStore:
    """Persist source paths separately from the disposable SQLite index."""

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

            if not isinstance(raw, dict) or raw.get("version") != CONFIG_VERSION:
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
                sources.append({
                    "path": normalized,
                    "active": item.get("active") is not False,
                })

            return {
                "version": CONFIG_VERSION,
                "sources": sources,
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
            if item["active"]
        ]

    def add_sources(self, paths: Iterable[str | Path]) -> None:
        with _config_lock:
            config = self.load()
            sources = config["sources"]
            existing = {item["path"]: item for item in sources}
            changed = False
            for path in paths:
                normalized = str(normalize_path(path))
                if normalized in existing:
                    if not existing[normalized]["active"]:
                        existing[normalized]["active"] = True
                        changed = True
                    continue
                item = {"path": normalized, "active": True}
                sources.append(item)
                existing[normalized] = item
                changed = True
            if changed:
                self.save(config)

    def add_source(self, path: str | Path) -> None:
        self.add_sources([path])

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
