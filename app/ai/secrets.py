from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

try:
    import keyring
    from keyring.errors import KeyringError, PasswordDeleteError
except ImportError:  # pragma: no cover - dependency diagnostics only
    keyring = None

    class KeyringError(Exception):
        pass

    class PasswordDeleteError(KeyringError):
        pass


SERVICE_NAME = "comfyui-meta-viewer"


class SecretStoreError(RuntimeError):
    """Raised when a provider secret cannot be accessed safely."""


@dataclass(frozen=True)
class SecretStoreStatus:
    available: bool
    backend: str | None
    message: str

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "available": self.available,
            "backend": self.backend,
            "message": self.message,
        }


class SecretStore(Protocol):
    def status(self) -> SecretStoreStatus: ...

    def get(self, profile_id: str) -> str | None: ...

    def set(self, profile_id: str, value: str) -> None: ...

    def delete(self, profile_id: str) -> None: ...


class SystemSecretStore:
    """Keep API keys in the OS keychain instead of application JSON or SQLite."""

    @staticmethod
    def _username(profile_id: str) -> str:
        return f"ai-provider:{profile_id}"

    def status(self) -> SecretStoreStatus:
        if keyring is None:
            return SecretStoreStatus(
                available=False,
                backend=None,
                message="The system keyring dependency is not installed.",
            )
        try:
            backend = keyring.get_keyring()
            backend_name = (
                f"{backend.__class__.__module__}.{backend.__class__.__name__}"
            )
            priority = float(getattr(backend, "priority", 0))
            unavailable = (
                priority <= 0
                or backend.__class__.__module__.endswith(".fail")
                or backend.__class__.__module__.endswith(".null")
            )
            if unavailable:
                return SecretStoreStatus(
                    available=False,
                    backend=backend_name,
                    message=(
                        "No supported system credential store is available. "
                        "Use an environment variable or configure the desktop keyring."
                    ),
                )
            return SecretStoreStatus(
                available=True,
                backend=backend_name,
                message="API keys are stored in the operating system credential store.",
            )
        except Exception as exc:  # pragma: no cover - backend-specific behavior
            return SecretStoreStatus(
                available=False,
                backend=None,
                message=f"Cannot initialize the system credential store: {exc}",
            )

    def _require_available(self) -> None:
        status = self.status()
        if not status.available:
            raise SecretStoreError(status.message)

    def get(self, profile_id: str) -> str | None:
        self._require_available()
        try:
            return keyring.get_password(SERVICE_NAME, self._username(profile_id))
        except KeyringError as exc:
            raise SecretStoreError(
                "Cannot read the API key from the system credential store."
            ) from exc

    def set(self, profile_id: str, value: str) -> None:
        self._require_available()
        if not value:
            raise SecretStoreError("API key cannot be empty.")
        try:
            keyring.set_password(SERVICE_NAME, self._username(profile_id), value)
        except KeyringError as exc:
            raise SecretStoreError(
                "Cannot save the API key in the system credential store."
            ) from exc

    def delete(self, profile_id: str) -> None:
        self._require_available()
        try:
            if keyring.get_password(
                SERVICE_NAME, self._username(profile_id)
            ) is None:
                return
            keyring.delete_password(SERVICE_NAME, self._username(profile_id))
        except (KeyringError, PasswordDeleteError) as exc:
            raise SecretStoreError(
                "Cannot delete the API key from the system credential store."
            ) from exc
