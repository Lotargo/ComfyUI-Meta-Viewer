from __future__ import annotations

import asyncio
import os
import threading
from typing import Any, Callable

from flask import current_app

from telethon import TelegramClient
from telethon.errors import (
    ApiIdInvalidError,
    AuthKeyUnregisteredError,
    FloodWaitError,
    PasswordHashInvalidError,
    PhoneCodeExpiredError,
    PhoneCodeInvalidError,
    PhoneNumberInvalidError,
    SessionPasswordNeededError,
)
from telethon.sessions import StringSession

from .base import SocialNotImplementedError, SocialPublisher
from .contract import PublishRequest, PublishResult
from .secrets import SocialSecretStore

TELEGRAM_ENV_API_ID = "TELEGRAM_API_ID"
TELEGRAM_ENV_API_HASH = "TELEGRAM_API_HASH"

IDLE = "idle"
QR_WAITING = "qr_waiting"
CODE_REQUESTED = "code_requested"
PASSWORD_REQUIRED = "password_required"
CONNECTED = "connected"
ERROR = "error"

_loop_lock = threading.Lock()
_module_loop: asyncio.AbstractEventLoop | None = None


def _start_loop(loop: asyncio.AbstractEventLoop) -> None:
    loop.run_forever()


def _ensure_loop() -> asyncio.AbstractEventLoop:
    """Return a daemon background event loop shared by all publishers."""
    global _module_loop
    with _loop_lock:
        if _module_loop is None or _module_loop.is_closed():
            loop = asyncio.new_event_loop()
            thread = threading.Thread(
                target=_start_loop,
                args=(loop,),
                name="telegram-loop",
                daemon=True,
            )
            thread.start()
            _module_loop = loop
        return _module_loop


class TelegramPublisher(SocialPublisher):
    provider = "telegram"
    label = "Telegram"

    def __init__(
        self,
        *,
        loop: asyncio.AbstractEventLoop | None = None,
        client_factory: Callable[[str | None, int, str, asyncio.AbstractEventLoop], Any] | None = None,
        store: SocialSecretStore | None = None,
    ) -> None:
        self._loop = loop
        self._client_factory = client_factory or self._default_client_factory
        self._store = store or SocialSecretStore()
        self._lock = threading.RLock()
        self._client: Any | None = None
        self._state: str = IDLE
        self._error: str | None = None
        self._qr: Any | None = None
        self._qr_task: Any | None = None
        self._phone: str | None = None
        self._phone_code_hash: str | None = None
        self._user: dict[str, Any] | None = None

    # ------------------------------------------------------------------
    # Construction helpers
    # ------------------------------------------------------------------

    def _default_client_factory(
        self,
        session: str | None,
        api_id: int,
        api_hash: str,
        loop: asyncio.AbstractEventLoop,
    ) -> TelegramClient:
        return TelegramClient(
            StringSession(session or ""),
            api_id,
            api_hash,
            loop=loop,
        )

    def _ensure_loop(self) -> asyncio.AbstractEventLoop:
        if self._loop is None:
            self._loop = _ensure_loop()
        return self._loop

    def _run(self, coro: Any) -> Any:
        loop = self._ensure_loop()
        future = asyncio.run_coroutine_threadsafe(coro, loop)
        return future.result()

    def _ensure_client(self, api_id: int, api_hash: str) -> Any:
        if self._client is not None:
            return self._client
        loop = self._ensure_loop()
        session = None
        try:
            session = self._store.get(self.provider)
        except Exception:
            session = None
        self._client = self._client_factory(session, api_id, api_hash, loop)
        return self._client

    # ------------------------------------------------------------------
    # Credentials
    # ------------------------------------------------------------------

    def _credentials(self) -> tuple[int | None, str | None, str]:
        """Resolve api_id/api_hash from the app config store, then env.

        Returns (api_id, api_hash, problem); problem is empty when resolved.
        """
        api_id: str | None = None
        api_hash: str | None = None
        try:
            store = current_app.config.get("CONFIG_STORE")
        except RuntimeError:  # pragma: no cover - outside request context
            store = None
        if store is not None:
            telegram = store.social_settings().get("telegram", {})
            api_id = telegram.get("api_id") or None
            api_hash = telegram.get("api_hash") or None
        api_id = api_id or os.environ.get(TELEGRAM_ENV_API_ID)
        api_hash = api_hash or os.environ.get(TELEGRAM_ENV_API_HASH)
        if not api_id or not api_hash:
            return (
                None,
                None,
                "Telegram API credentials are not configured. Set "
                f"{TELEGRAM_ENV_API_ID} and {TELEGRAM_ENV_API_HASH} in the app "
                "settings or the environment.",
            )
        try:
            parsed_id = int(str(api_id))
        except (TypeError, ValueError):
            return None, None, f"{TELEGRAM_ENV_API_ID} must be an integer."
        if parsed_id <= 0:
            return None, None, f"{TELEGRAM_ENV_API_ID} must be a positive integer."
        return parsed_id, api_hash, ""

    # ------------------------------------------------------------------
    # Async primitives (thin wrappers so tests can drive them directly)
    # ------------------------------------------------------------------

    @staticmethod
    async def _validate_client(client: Any) -> Any:
        await client.connect()
        return await client.get_me()

    @staticmethod
    async def _send_code(client: Any, phone: str) -> Any:
        return await client.send_code_request(phone)

    @staticmethod
    async def _qr_login(client: Any) -> Any:
        return await client.qr_login()

    @staticmethod
    async def _qr_recreate(qr: Any) -> None:
        await qr.recreate()

    @staticmethod
    async def _sign_in_code(
        client: Any,
        phone: str | None,
        code: str,
        phone_code_hash: str | None,
    ) -> Any:
        return await client.sign_in(
            phone=phone,
            code=code,
            phone_code_hash=phone_code_hash,
        )

    @staticmethod
    async def _sign_in_password(client: Any, password: str) -> Any:
        return await client.sign_in(password=password)

    @staticmethod
    async def _disconnect_client(client: Any) -> None:
        try:
            await client.disconnect()
        except Exception:
            pass

    # ------------------------------------------------------------------
    # State helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _user_dict(user: Any) -> dict[str, Any]:
        return {
            "id": getattr(user, "id", None),
            "username": getattr(user, "username", None),
            "first_name": getattr(user, "first_name", None),
            "last_name": getattr(user, "last_name", None),
            "phone": getattr(user, "phone", None),
        }

    def _persist_session(self, client: Any) -> None:
        try:
            saved = client.session.save()
        except Exception:
            return
        if not saved:
            return
        try:
            self._store.set(self.provider, saved)
        except Exception:
            pass

    def _forget_invalid_client(self) -> None:
        client = self._client
        self._client = None
        if client is not None:
            try:
                self._run(self._disconnect_client(client))
            except Exception:
                pass
        try:
            self._store.delete(self.provider)
        except Exception:
            pass

    def _connected(self, client: Any, user: Any) -> None:
        self._client = client
        self._state = CONNECTED
        self._error = None
        self._qr = None
        self._qr_task = None
        self._phone = None
        self._phone_code_hash = None
        self._user = self._user_dict(user)
        self._persist_session(client)

    def _set_state(self, state: str, error: str | None) -> None:
        with self._lock:
            self._state = state
            self._error = error
            if state != QR_WAITING:
                self._qr = None
            self._qr_task = None

    def _schedule_qr_wait(self) -> None:
        if self._qr_task is not None and not self._qr_task.done():
            self._qr_task.cancel()
        self._qr_task = asyncio.run_coroutine_threadsafe(
            self._watch_qr(self._qr),
            self._ensure_loop(),
        )

    async def _watch_qr(self, qr: Any) -> None:
        try:
            user = await qr.wait()
        except SessionPasswordNeededError:
            self._set_state(PASSWORD_REQUIRED, None)
        except asyncio.TimeoutError:
            self._set_state(QR_WAITING, "QR code expired. Start the flow again.")
        except FloodWaitError as exc:
            self._set_state(ERROR, f"Flood wait: retry in {exc.seconds}s")
        except Exception as exc:  # pragma: no cover - transport specific
            self._set_state(ERROR, str(exc))
        else:
            with self._lock:
                if self._client is not None:
                    self._connected(self._client, user)

    def _view(self) -> dict[str, Any]:
        qr_url = None
        qr_expires = None
        if self._state == QR_WAITING and self._qr is not None:
            try:
                qr_url = self._qr.url
            except Exception:
                qr_url = None
            try:
                qr_expires = self._qr.expires.isoformat()
            except Exception:
                qr_expires = None
        try:
            _api_id, _api_hash, problem = self._credentials()
            configured = not problem
        except Exception:  # pragma: no cover - defensive
            configured = False
        return {
            "state": self._state,
            "error": self._error,
            "qr_url": qr_url,
            "qr_expires": qr_expires,
            "phone": self._phone,
            "user": self._user,
            "connected": self._state == CONNECTED,
            "configured": configured,
        }

    # ------------------------------------------------------------------
    # Public auth API
    # ------------------------------------------------------------------

    def auth_state(self) -> dict[str, Any]:
        with self._lock:
            return self._view()

    def auth_start(self, phone: str | None = None) -> tuple[int, dict[str, Any]]:
        with self._lock:
            api_id, api_hash, problem = self._credentials()
            if api_id is None:
                return 400, {"code": "credentials_missing", "error": problem}
            if self._state == CONNECTED and self._client is not None:
                return 200, self._view()
            if self._state in (CODE_REQUESTED, PASSWORD_REQUIRED):
                return 200, self._view()
            if self._state == QR_WAITING:
                if self._qr is not None:
                    return 200, self._view()
                client = self._client or self._ensure_client(api_id, api_hash)
                return self._start_qr_flow(client)

            client = self._ensure_client(api_id, api_hash)
            try:
                user = self._run(self._validate_client(client))
            except AuthKeyUnregisteredError:
                self._forget_invalid_client()
                client = self._ensure_client(api_id, api_hash)
                user = None
            except FloodWaitError as exc:
                return 429, {
                    "code": "flood_wait",
                    "seconds": exc.seconds,
                    "error": f"Flood wait: retry in {exc.seconds}s",
                }
            except Exception as exc:
                return 503, {"code": "connect_failed", "error": str(exc)}
            if user is not None:
                self._connected(client, user)
                return 200, self._view()
            self._error = None
            phone = (phone or "").strip() or None
            if phone is not None:
                return self._start_code_flow(client, phone)
            return self._start_qr_flow(client)

    def _start_code_flow(self, client: Any, phone: str) -> tuple[int, dict[str, Any]]:
        try:
            sent = self._run(self._send_code(client, phone))
        except PhoneNumberInvalidError:
            return 400, {"code": "invalid_phone", "error": "Unrecognized phone number."}
        except ApiIdInvalidError:
            return 400, {
                "code": "invalid_credentials",
                "error": "Invalid Telegram API credentials.",
            }
        except FloodWaitError as exc:
            return 429, {
                "code": "flood_wait",
                "seconds": exc.seconds,
                "error": f"Flood wait: retry in {exc.seconds}s",
            }
        except Exception as exc:
            return 400, {"code": "auth_error", "error": str(exc)}
        self._state = CODE_REQUESTED
        self._phone = phone
        self._phone_code_hash = getattr(sent, "phone_code_hash", None)
        self._error = None
        return 200, self._view()

    def _start_qr_flow(self, client: Any) -> tuple[int, dict[str, Any]]:
        try:
            qr = self._run(self._qr_login(client))
        except ApiIdInvalidError:
            return 400, {
                "code": "invalid_credentials",
                "error": "Invalid Telegram API credentials.",
            }
        except FloodWaitError as exc:
            return 429, {
                "code": "flood_wait",
                "seconds": exc.seconds,
                "error": f"Flood wait: retry in {exc.seconds}s",
            }
        except Exception as exc:
            return 400, {"code": "auth_error", "error": str(exc)}
        self._qr = qr
        self._state = QR_WAITING
        self._error = None
        self._schedule_qr_wait()
        return 200, self._view()

    def auth_submit_code(self, code: str) -> tuple[int, dict[str, Any]]:
        with self._lock:
            code = (code or "").strip()
            if not code:
                return 400, {"code": "invalid_payload", "error": "code is required."}
            if self._state != CODE_REQUESTED or self._client is None:
                return 400, {
                    "code": "not_in_flow",
                    "error": "Start the phone code flow first.",
                }
            client = self._client
            try:
                user = self._run(
                    self._sign_in_code(client, self._phone, code, self._phone_code_hash)
                )
            except SessionPasswordNeededError:
                self._state = PASSWORD_REQUIRED
                self._error = None
                return 200, self._view()
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                return 400, {
                    "code": "invalid_code",
                    "error": "Invalid or expired verification code.",
                }
            except FloodWaitError as exc:
                return 429, {
                    "code": "flood_wait",
                    "seconds": exc.seconds,
                    "error": f"Flood wait: retry in {exc.seconds}s",
                }
            except Exception as exc:
                return 400, {"code": "auth_error", "error": str(exc)}
            self._connected(client, user)
            return 200, self._view()

    def auth_submit_password(self, password: str) -> tuple[int, dict[str, Any]]:
        with self._lock:
            password = password or ""
            if self._state != PASSWORD_REQUIRED or self._client is None:
                return 400, {
                    "code": "not_in_flow",
                    "error": "Two-factor authentication was not requested.",
                }
            client = self._client
            try:
                user = self._run(self._sign_in_password(client, password))
            except PasswordHashInvalidError:
                return 400, {
                    "code": "invalid_password",
                    "error": "Incorrect two-factor password.",
                }
            except (PhoneCodeInvalidError, PhoneCodeExpiredError):
                self._state = CODE_REQUESTED
                self._error = "The session expired; enter a new verification code."
                return 400, {
                    "code": "invalid_code",
                    "error": "The verification code expired. Start again.",
                }
            except FloodWaitError as exc:
                return 429, {
                    "code": "flood_wait",
                    "seconds": exc.seconds,
                    "error": f"Flood wait: retry in {exc.seconds}s",
                }
            except Exception as exc:
                return 400, {"code": "auth_error", "error": str(exc)}
            self._connected(client, user)
            return 200, self._view()

    def auth_cancel(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._cancel_flow()
            self._client = None
            self._state = IDLE
            self._error = None
            self._user = None
            return 200, self._view()

    def auth_disconnect(self) -> tuple[int, dict[str, Any]]:
        with self._lock:
            self._cancel_flow()
            if self._client is not None:
                try:
                    self._run(self._disconnect_client(self._client))
                except Exception:
                    pass
            self._client = None
            try:
                self._store.delete(self.provider)
            except Exception:
                pass
            self._state = IDLE
            self._error = None
            self._phone = None
            self._phone_code_hash = None
            self._user = None
            return 200, self._view()

    def _cancel_flow(self) -> None:
        if self._qr_task is not None and not self._qr_task.done():
            self._qr_task.cancel()
        self._qr_task = None
        self._qr = None
        self._phone = None
        self._phone_code_hash = None

    # ------------------------------------------------------------------
    # SocialPublisher interface (publishing lands in a later stage)
    # ------------------------------------------------------------------

    def status(self) -> dict:
        return {"provider": self.provider, "label": self.label, **self.auth_state()}

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            "Telegram publishing is implemented in a later stage."
        )
