from __future__ import annotations

import base64
import hashlib
import json
import os
import secrets
import threading
import urllib.error
import urllib.parse
import urllib.request
import uuid
from typing import Any, Callable

from flask import current_app

from .base import SocialNotImplementedError, SocialPublisher
from .contract import PublishRequest, PublishResult
from .secrets import SocialSecretStore

VK_ENV_CLIENT_ID = "VK_CLIENT_ID"
VK_ENV_CLIENT_SECRET = "VK_CLIENT_SECRET"

VK_ID_AUTHORIZE_URL = "https://id.vk.ru/authorize"
VK_ID_TOKEN_URL = "https://id.vk.ru/oauth2/auth"

# VK ID trusts the localhost base domain on port 80 only. The app normally
# runs on a high port (5055/7860), so this callback can only fire when the
# app is reachable on port 80. Revisit once real credentials land.
VK_REDIRECT_URI = "http://localhost/api/social/vk/auth/callback"

IDLE = "idle"
AUTH_PENDING = "auth_pending"
CONNECTED = "connected"
ERROR = "error"


class VKAuthError(RuntimeError):
    pass


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _sha256_b64url(value: str) -> str:
    return _b64url(hashlib.sha256(value.encode("utf-8")).digest())


def _post_form(url: str, fields: dict[str, str]) -> dict[str, Any]:
    """POST an OAuth form and return the parsed JSON response."""
    body = urllib.parse.urlencode(fields).encode("utf-8")
    request = urllib.request.Request(url, data=body, method="POST")
    request.add_header("Content-Type", "application/x-www-form-urlencoded")
    try:
        with urllib.request.urlopen(request, timeout=30) as response:
            raw = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        if not raw:
            raise VKAuthError(f"VK ID returned HTTP {exc.code}.") from exc
    try:
        payload = json.loads(raw)
    except ValueError:
        raise VKAuthError(f"VK ID returned a non-JSON response: {raw[:200]}") from None
    if not isinstance(payload, dict):
        raise VKAuthError(f"VK ID returned an unexpected response: {raw[:200]}")
    return payload


class VKPublisher(SocialPublisher):
    provider = "vk"
    label = "ВКонтакте"

    def __init__(
        self,
        *,
        store: SocialSecretStore | None = None,
        post: Callable[[str, dict[str, str]], dict[str, Any]] | None = None,
        redirect_uri: str | None = None,
    ) -> None:
        self._store = store or SocialSecretStore()
        self._post = post or _post_form
        self._redirect_uri = redirect_uri or VK_REDIRECT_URI
        self._lock = threading.RLock()
        self._state: str = IDLE
        self._error: str | None = None
        self._verifier: str | None = None
        self._state_param: str | None = None
        self._device_id: str | None = None
        self._authorize_url: str | None = None
        self._token: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    def _credentials(self) -> tuple[str | None, str | None, str]:
        """Resolve client_id/client_secret from config store, then env."""
        client_id: str | None = None
        client_secret: str | None = None
        try:
            store = current_app.config.get("CONFIG_STORE")
        except RuntimeError:  # pragma: no cover - outside request context
            store = None
        if store is not None:
            vk = store.social_settings().get("vk", {})
            client_id = vk.get("client_id") or None
            client_secret = vk.get("client_secret") or None
        client_id = client_id or os.environ.get(VK_ENV_CLIENT_ID)
        client_secret = client_secret or os.environ.get(VK_ENV_CLIENT_SECRET)
        if not client_id:
            return None, None, (
                "VK application is not configured. Set "
                f"{VK_ENV_CLIENT_ID} in the app settings or the environment."
            )
        return client_id, client_secret, ""

    # ------------------------------------------------------------------
    # Token storage
    # ------------------------------------------------------------------

    def _load_token(self) -> dict[str, Any] | None:
        try:
            raw = self._store.get(self.provider)
        except Exception:
            return None
        if not raw:
            return None
        try:
            payload = json.loads(raw)
        except ValueError:
            return None
        if not isinstance(payload, dict) or not payload.get("access_token"):
            return None
        return payload

    def _persist_token(self, payload: dict[str, Any]) -> None:
        try:
            self._store.set(self.provider, json.dumps(payload))
        except Exception:
            pass

    def _load_connected(self) -> bool:
        token = self._load_token()
        if token is None:
            return False
        try:
            self._token = token
            self._device_id = token.get("device_id")
            self._state = CONNECTED
            self._error = None
            return True
        except Exception:  # pragma: no cover - defensive
            return False

    # ------------------------------------------------------------------
    # View
    # ------------------------------------------------------------------

    def _view(self) -> dict[str, Any]:
        token = self._token or self._load_token()
        try:
            client_id, _client_secret, problem = self._credentials()
            configured = client_id is not None
        except Exception:  # pragma: no cover - defensive
            configured = False
        return {
            "state": self._state,
            "error": self._error,
            "authorize_url": self._authorize_url,
            "device_id": self._device_id,
            "user_id": (token or {}).get("user_id"),
            "connected": self._state == CONNECTED,
            "configured": configured,
        }

    # ------------------------------------------------------------------
    # Public auth API
    # ------------------------------------------------------------------

    def auth_state(self) -> dict[str, Any]:
        with self._lock:
            if self._state == CONNECTED:
                return self._view()
            if self._load_connected():
                return self._view()
            return self._view()

    def auth_start(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            client_id, _client_secret, problem = self._credentials()
            if client_id is None:
                return 400, {"code": "credentials_missing", "error": problem}
            if self._state == CONNECTED:
                return 200, self._view()
            verifier = secrets.token_urlsafe(48)
            challenge = _sha256_b64url(verifier)
            state_param = secrets.token_urlsafe(24)
            device_id = str(uuid.uuid4())
            query = urllib.parse.urlencode({
                "response_type": "code",
                "client_id": client_id,
                "redirect_uri": self._redirect_uri,
                "scope": "vkid:openid email phone",
                "state": state_param,
                "code_challenge": challenge,
                "code_challenge_method": "S256",
                "device_id": device_id,
                "prompt": "login",
            })
            self._verifier = verifier
            self._state_param = state_param
            self._device_id = device_id
            self._authorize_url = f"{VK_ID_AUTHORIZE_URL}?{query}"
            self._state = AUTH_PENDING
            self._error = None
            return 200, self._view()

    def auth_submit_code(self, code: str, state: str | None = None) -> tuple[int, dict[str, Any]]:
        with self._lock:
            code = (code or "").strip()
            if not code:
                return 400, {"code": "invalid_payload", "error": "code is required."}
            if self._state != AUTH_PENDING or not self._verifier:
                return 400, {
                    "code": "not_in_flow",
                    "error": "Start the VK authorization flow first.",
                }
            if state and state != self._state_param:
                return 400, {
                    "code": "state_mismatch",
                    "error": "The authorization state does not match.",
                }
            client_id, client_secret, problem = self._credentials()
            if client_id is None:
                return 400, {"code": "credentials_missing", "error": problem}
            fields = {
                "grant_type": "authorization_code",
                "code": code,
                "code_verifier": self._verifier,
                "redirect_uri": self._redirect_uri,
                "client_id": client_id,
                "device_id": self._device_id or "",
            }
            if client_secret:
                fields["client_secret"] = client_secret
            try:
                payload = self._post(VK_ID_TOKEN_URL, fields)
            except VKAuthError as exc:
                return 502, {"code": "exchange_failed", "error": str(exc)}
            except Exception as exc:
                return 502, {"code": "exchange_failed", "error": str(exc)}
            access_token = payload.get("access_token")
            if not access_token:
                error = payload.get("error_description") or payload.get("error")
                return 400, {
                    "code": "auth_error",
                    "error": error or "VK ID did not return an access token.",
                }
            token = {
                "access_token": access_token,
                "refresh_token": payload.get("refresh_token"),
                "expires_in": payload.get("expires_in"),
                "scope": payload.get("scope"),
                "token_type": payload.get("token_type"),
                "user_id": payload.get("user_id"),
                "device_id": self._device_id,
            }
            self._persist_token(token)
            self._token = token
            self._state = CONNECTED
            self._error = None
            self._authorize_url = None
            self._verifier = None
            self._state_param = None
            return 200, self._view()

    def auth_disconnect(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._clear()
            return 200, self._view()

    def _clear(self) -> None:
        try:
            self._store.delete(self.provider)
        except Exception:
            pass
        self._state = IDLE
        self._error = None
        self._verifier = None
        self._state_param = None
        self._device_id = None
        self._authorize_url = None
        self._token = None

    # ------------------------------------------------------------------
    # SocialPublisher interface (publishing lands in a later stage)
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {"provider": self.provider, "label": self.label, **self.auth_state()}

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            "VK publishing is implemented in a later stage."
        )
