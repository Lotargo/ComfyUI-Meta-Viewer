from __future__ import annotations

import json
import os
import re
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from ..config_store import ConfigStore
from .secrets import SecretStore, SecretStoreError, SystemSecretStore


PROFILE_KINDS = {"openai_compatible", "cli"}
CLI_TYPES = {"opencode", "claude", "antigravity"}
API_KEY_SOURCES = {"system", "environment", "none"}
ENVIRONMENT_NAME_RE = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
_profile_lock = threading.RLock()


class AIProfileStoreError(RuntimeError):
    """Raised for invalid or unavailable AI provider profiles."""

    def __init__(self, message: str, *, code: str = "invalid_profile"):
        self.code = code
        super().__init__(message)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _clean_text(value: Any, field: str, *, maximum: int) -> str:
    if not isinstance(value, str) or not value.strip():
        raise AIProfileStoreError(f"{field} is required.")
    cleaned = value.strip()
    if "\x00" in cleaned:
        raise AIProfileStoreError(f"{field} contains an invalid character.")
    if len(cleaned) > maximum:
        raise AIProfileStoreError(f"{field} is too long.")
    return cleaned


def _contains_secret_field(value: Any) -> bool:
    forbidden = {
        "api_key",
        "apikey",
        "authorization",
        "access_token",
        "refresh_token",
        "password",
        "secret",
    }
    if isinstance(value, dict):
        return any(
            (
                str(key).lower().replace("-", "_") in forbidden
                or str(key).lower().replace("-", "_") == "headers"
                or str(key).lower().replace("-", "_").endswith("_api_key")
                or str(key).lower().replace("-", "_").endswith("_token")
            )
            or _contains_secret_field(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(_contains_secret_field(item) for item in value)
    return False


def _validate_extra_body(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise AIProfileStoreError("Additional request parameters must be a JSON object.")
    try:
        encoded = json.dumps(value, ensure_ascii=False)
    except (TypeError, ValueError) as exc:
        raise AIProfileStoreError(
            "Additional request parameters must contain valid JSON values."
        ) from exc
    if len(encoded.encode("utf-8")) > 32 * 1024:
        raise AIProfileStoreError("Additional request parameters are too large.")
    if _contains_secret_field(value):
        raise AIProfileStoreError(
            "Secrets and authorization headers cannot be stored in request parameters."
        )
    return json.loads(encoded)


def _validate_base_url(value: Any, *, api_key_source: str) -> str:
    base_url = _clean_text(value, "Base URL", maximum=2048).rstrip("/")
    parsed = urlparse(base_url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise AIProfileStoreError("Base URL must be an absolute HTTP or HTTPS URL.")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise AIProfileStoreError(
            "Base URL cannot contain credentials, query parameters, or a fragment."
        )
    local_hosts = {"localhost", "127.0.0.1", "::1"}
    if (
        parsed.scheme != "https"
        and parsed.hostname.lower() not in local_hosts
        and api_key_source != "none"
    ):
        raise AIProfileStoreError(
            "API keys can only be sent over HTTPS or to a local endpoint."
        )
    return base_url


def _validate_profile(
    payload: dict[str, Any],
    *,
    profile_id: str,
    created_at: str | None = None,
) -> dict[str, Any]:
    kind = payload.get("kind", "openai_compatible")
    if kind not in PROFILE_KINDS:
        raise AIProfileStoreError("Unsupported AI profile type.")

    name = _clean_text(payload.get("name"), "Profile name", maximum=80)
    model = _clean_text(payload.get("model"), "Model ID", maximum=200)
    try:
        timeout_seconds = int(payload.get("timeout_seconds", 60))
    except (TypeError, ValueError) as exc:
        raise AIProfileStoreError("Timeout must be a whole number of seconds.") from exc
    if not 5 <= timeout_seconds <= 600:
        raise AIProfileStoreError("Timeout must be between 5 and 600 seconds.")

    profile: dict[str, Any] = {
        "id": profile_id,
        "kind": kind,
        "name": name,
        "model": model,
        "timeout_seconds": timeout_seconds,
        "multimodal": payload.get("multimodal") is True,
        "created_at": created_at or _now(),
        "updated_at": _now(),
    }

    if kind == "openai_compatible":
        api_key_source = payload.get("api_key_source", "system")
        if api_key_source not in API_KEY_SOURCES:
            raise AIProfileStoreError("Unsupported API key source.")
        api_key_env = payload.get("api_key_env")
        if api_key_source == "environment":
            api_key_env = _clean_text(
                api_key_env, "Environment variable", maximum=100
            )
            if not ENVIRONMENT_NAME_RE.fullmatch(api_key_env):
                raise AIProfileStoreError("Environment variable name is invalid.")
        else:
            api_key_env = None
        profile.update({
            "base_url": _validate_base_url(
                payload.get("base_url"), api_key_source=api_key_source
            ),
            "api_key_source": api_key_source,
            "api_key_env": api_key_env,
            "extra_body": _validate_extra_body(payload.get("extra_body")),
        })
    else:
        cli_type = payload.get("cli_type")
        if cli_type not in CLI_TYPES:
            raise AIProfileStoreError("Unsupported CLI integration.")
        if profile["multimodal"] and cli_type != "opencode":
            raise AIProfileStoreError(
                "Only the OpenCode CLI adapter currently supports image input."
            )
        executable = payload.get("executable")
        if executable is not None:
            executable = _clean_text(executable, "CLI executable", maximum=4096)
        profile.update({
            "cli_type": cli_type,
            "executable": executable,
        })
    return profile


class AIProfileStore:
    """Persist non-secret profile settings and coordinate their keyring entries."""

    def __init__(
        self,
        config_path: str | Path,
        *,
        secret_store: SecretStore | None = None,
    ):
        self.config = ConfigStore(config_path)
        self.secrets = secret_store or SystemSecretStore()

    def _load_profiles(self) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        config = self.config.load()
        profiles: list[dict[str, Any]] = []
        seen: set[str] = set()
        for raw in config["ai"]["profiles"]:
            profile_id = raw.get("id") if isinstance(raw.get("id"), str) else ""
            if not profile_id or profile_id in seen:
                continue
            try:
                profile = _validate_profile(
                    raw,
                    profile_id=profile_id,
                    created_at=(
                        raw.get("created_at")
                        if isinstance(raw.get("created_at"), str)
                        else None
                    ),
                )
            except AIProfileStoreError:
                continue
            if isinstance(raw.get("updated_at"), str):
                profile["updated_at"] = raw["updated_at"]
            seen.add(profile_id)
            profiles.append(profile)
        config["ai"]["profiles"] = profiles
        return config, profiles

    def _secret_state(self, profile: dict[str, Any]) -> tuple[bool, str | None]:
        if profile["kind"] != "openai_compatible":
            return True, None
        source = profile["api_key_source"]
        if source == "none":
            return True, None
        if source == "environment":
            return bool(os.environ.get(profile["api_key_env"])), None
        try:
            return bool(self.secrets.get(profile["id"])), None
        except SecretStoreError as exc:
            return False, str(exc)

    def public_profile(self, profile: dict[str, Any]) -> dict[str, Any]:
        result = dict(profile)
        has_credentials, credential_error = self._secret_state(profile)
        result["has_credentials"] = has_credentials
        if credential_error:
            result["credential_error"] = credential_error
        return result

    def list(self) -> dict[str, Any]:
        with _profile_lock:
            config, profiles = self._load_profiles()
            profile_ids = {profile["id"] for profile in profiles}
            defaults = dict(config["ai"]["defaults"])
            for key in ("text_profile_id", "multimodal_profile_id"):
                if defaults.get(key) not in profile_ids:
                    defaults[key] = None
            return {
                "profiles": [self.public_profile(profile) for profile in profiles],
                "defaults": defaults,
                "secret_store": self.secrets.status().to_dict(),
            }

    def get(self, profile_id: str) -> dict[str, Any]:
        _, profiles = self._load_profiles()
        profile = next(
            (item for item in profiles if item["id"] == profile_id), None
        )
        if profile is None:
            raise AIProfileStoreError("AI profile not found.", code="profile_not_found")
        return profile

    def create(self, payload: dict[str, Any]) -> dict[str, Any]:
        with _profile_lock:
            config, profiles = self._load_profiles()
            profile_id = str(uuid.uuid4())
            profile = _validate_profile(payload, profile_id=profile_id)
            secret_saved = False
            if (
                profile["kind"] == "openai_compatible"
                and profile["api_key_source"] == "system"
            ):
                api_key = payload.get("api_key")
                if not isinstance(api_key, str) or not api_key.strip():
                    raise AIProfileStoreError(
                        "API key is required for system credential storage.",
                        code="missing_credentials",
                    )
                self.secrets.set(profile_id, api_key.strip())
                secret_saved = True
            profiles.append(profile)
            config["ai"]["profiles"] = profiles
            try:
                self.config.save(config)
            except Exception:
                if secret_saved:
                    self.secrets.delete(profile_id)
                raise
            return self.public_profile(profile)

    def update(self, profile_id: str, payload: dict[str, Any]) -> dict[str, Any]:
        with _profile_lock:
            config, profiles = self._load_profiles()
            index = next(
                (i for i, item in enumerate(profiles) if item["id"] == profile_id),
                None,
            )
            if index is None:
                raise AIProfileStoreError(
                    "AI profile not found.", code="profile_not_found"
                )
            old = profiles[index]
            merged = dict(old)
            merged.update({
                key: value
                for key, value in payload.items()
                if key not in {"id", "created_at", "updated_at", "api_key"}
            })
            updated = _validate_profile(
                merged,
                profile_id=profile_id,
                created_at=old["created_at"],
            )

            old_secret: str | None = None
            old_used_system = (
                old["kind"] == "openai_compatible"
                and old["api_key_source"] == "system"
            )
            new_uses_system = (
                updated["kind"] == "openai_compatible"
                and updated["api_key_source"] == "system"
            )
            if old_used_system:
                old_secret = self.secrets.get(profile_id)
            api_key = payload.get("api_key")
            new_secret = api_key.strip() if isinstance(api_key, str) else ""
            if new_uses_system:
                if new_secret:
                    self.secrets.set(profile_id, new_secret)
                elif not old_secret:
                    raise AIProfileStoreError(
                        "API key is required for system credential storage.",
                        code="missing_credentials",
                    )
            elif old_used_system:
                self.secrets.delete(profile_id)

            profiles[index] = updated
            config["ai"]["profiles"] = profiles
            try:
                self.config.save(config)
            except Exception:
                if old_used_system and old_secret:
                    self.secrets.set(profile_id, old_secret)
                elif new_uses_system and new_secret:
                    self.secrets.delete(profile_id)
                raise
            return self.public_profile(updated)

    def delete(self, profile_id: str) -> None:
        with _profile_lock:
            config, profiles = self._load_profiles()
            profile = next(
                (item for item in profiles if item["id"] == profile_id), None
            )
            if profile is None:
                raise AIProfileStoreError(
                    "AI profile not found.", code="profile_not_found"
                )
            old_secret: str | None = None
            uses_system = (
                profile["kind"] == "openai_compatible"
                and profile["api_key_source"] == "system"
            )
            if uses_system:
                old_secret = self.secrets.get(profile_id)
                self.secrets.delete(profile_id)
            config["ai"]["profiles"] = [
                item for item in profiles if item["id"] != profile_id
            ]
            for key, value in config["ai"]["defaults"].items():
                if value == profile_id:
                    config["ai"]["defaults"][key] = None
            try:
                self.config.save(config)
            except Exception:
                if old_secret:
                    self.secrets.set(profile_id, old_secret)
                raise

    def set_defaults(self, payload: dict[str, Any]) -> dict[str, str | None]:
        with _profile_lock:
            config, profiles = self._load_profiles()
            by_id = {profile["id"]: profile for profile in profiles}
            defaults = dict(config["ai"]["defaults"])
            for key in ("text_profile_id", "multimodal_profile_id"):
                if key not in payload:
                    continue
                value = payload[key]
                if value is not None and value not in by_id:
                    raise AIProfileStoreError("Selected AI profile does not exist.")
                if (
                    key == "multimodal_profile_id"
                    and value is not None
                    and not by_id[value]["multimodal"]
                ):
                    raise AIProfileStoreError(
                        "The default multimodal profile must be marked as multimodal."
                    )
                defaults[key] = value
            config["ai"]["defaults"] = defaults
            self.config.save(config)
            return defaults

    def resolve_api_key(self, profile: dict[str, Any]) -> str | None:
        if profile["kind"] != "openai_compatible":
            return None
        source = profile["api_key_source"]
        if source == "none":
            return None
        if source == "environment":
            value = os.environ.get(profile["api_key_env"])
        else:
            value = self.secrets.get(profile["id"])
        if not value:
            raise AIProfileStoreError(
                "No API key is available for this profile.",
                code="missing_credentials",
            )
        return value

    def delete_all_secrets(self) -> None:
        with _profile_lock:
            _, profiles = self._load_profiles()
            entries: list[tuple[str, str]] = []
            for profile in profiles:
                if (
                    profile["kind"] == "openai_compatible"
                    and profile["api_key_source"] == "system"
                ):
                    value = self.secrets.get(profile["id"])
                    if value:
                        entries.append((profile["id"], value))
            deleted: list[tuple[str, str]] = []
            try:
                for profile_id, value in entries:
                    self.secrets.delete(profile_id)
                    deleted.append((profile_id, value))
            except Exception:
                for profile_id, value in deleted:
                    self.secrets.set(profile_id, value)
                raise
