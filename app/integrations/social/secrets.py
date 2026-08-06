from __future__ import annotations

from dataclasses import dataclass

from app.ai.secrets import SecretStoreStatus, SystemSecretStore


class SocialSecretStoreError(RuntimeError):
    """Raised when a social provider secret cannot be accessed safely."""


@dataclass(frozen=True)
class SocialSecretStoreStatus:
    available: bool
    backend: str | None
    message: str
    connected: bool

    def to_dict(self) -> dict[str, str | bool | None]:
        return {
            "available": self.available,
            "backend": self.backend,
            "message": self.message,
            "connected": self.connected,
        }


class SocialSecretStore:
    """Store social provider secrets in the OS keychain via keyring.

    Reuses the same system credential store as AI provider keys, but keeps
    social secrets under their own namespace (`social:<provider>`) so the two
    groups never collide.
    """

    def __init__(self, store: SystemSecretStore | None = None) -> None:
        self._store = store or SystemSecretStore()

    @staticmethod
    def _username(provider: str) -> str:
        return f"social:{provider}"

    def status(self, provider: str) -> SocialSecretStoreStatus:
        core = self._store.status()
        connected = False
        if core.available:
            try:
                connected = self.get(provider) is not None
            except Exception:
                connected = False
        return SocialSecretStoreStatus(
            available=core.available,
            backend=core.backend,
            message=core.message,
            connected=connected,
        )

    def get(self, provider: str) -> str | None:
        return self._store.get(self._username(provider))

    def set(self, provider: str, value: str) -> None:
        if not value:
            raise SocialSecretStoreError(
                "Provider secret cannot be empty."
            )
        self._store.set(self._username(provider), value)

    def delete(self, provider: str) -> None:
        self._store.delete(self._username(provider))
