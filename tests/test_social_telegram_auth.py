"""Unit tests for the Telegram social-provider auth flow.

Telethon is async and requires network credentials, so every test drives
``TelegramPublisher`` through a fake async client and a fake secret store.
The publisher's thin async wrappers (``_validate_client``, ``_qr_login``,
``_sign_in_code``, ...) are monkeypatched to avoid real network I/O.
"""

from __future__ import annotations

import asyncio
import unittest
from unittest.mock import patch

from telethon.errors import (
    PasswordHashInvalidError,
    PhoneCodeInvalidError,
    SessionPasswordNeededError,
)

from app.integrations.social.telegram import (
    CODE_REQUESTED,
    CONNECTED,
    ERROR,
    IDLE,
    PASSWORD_REQUIRED,
    QR_WAITING,
    TelegramPublisher,
)


class _SentCode:
    phone_code_hash = "hash-1"


class _FakeUser:
    id = 111
    username = "oleg_test"
    first_name = "Oleg"
    last_name = None
    phone = "79990000000"


class _FakeQR:
    url = "tg://login?token=abc"
    expires = None

    def __init__(self):
        self.signed_in = False
        self.recreated = 0

    async def wait(self):
        if not self.signed_in:
            self.signed_in = True
            return _FakeUser()
        return _FakeUser()

    async def recreate(self):
        self.recreated += 1


class _FakeSession:
    def __init__(self):
        self.data = "session-data"

    def save(self):
        return self.data


class _FakeClient:
    def __init__(self):
        self.connected = False
        self.me = None
        self.session = _FakeSession()
        self.sent_code_requests = []
        self.sign_in_calls = []
        self.disconnected = False

    async def connect(self):
        self.connected = True

    async def get_me(self):
        return self.me

    async def send_code_request(self, phone):
        self.sent_code_requests.append(phone)
        return _SentCode()

    async def qr_login(self):
        self.qr = _FakeQR()
        return self.qr

    async def sign_in(self, *, phone=None, code=None, phone_code_hash=None, password=None):
        self.sign_in_calls.append(
            (phone, code, phone_code_hash, password)
        )
        if password is not None:
            raise PasswordHashInvalidError(request=None)
        return _FakeUser()

    async def disconnect(self):
        self.disconnected = True


class _FakeStore:
    def __init__(self):
        self.data: dict[str, str] = {}
        self.deleted = []

    def get(self, provider):
        return self.data.get(provider)

    def set(self, provider, value):
        self.data[provider] = value

    def delete(self, provider):
        self.data.pop(provider, None)
        self.deleted.append(provider)


def _run(coro):
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


class _FakeCredentialsContext:
    """Context manager that makes _credentials() return fixed values."""

    def __init__(self, api_id, api_hash, problem=""):
        self.api_id = api_id
        self.api_hash = api_hash
        self.problem = problem

    def __enter__(self):
        self.patcher = patch.object(
            TelegramPublisher, "_credentials", return_value=(
                self.api_id, self.api_hash, self.problem
            )
        )
        self.patcher.start()
        return self

    def __exit__(self, *exc):
        self.patcher.stop()


class TelegramAuthFlowTest(unittest.TestCase):
    def make_publisher(self):
        client = _FakeClient()
        store = _FakeStore()

        async def _validate(client):
            await client.connect()
            return await client.get_me()

        async def _qr_login(client):
            return await client.qr_login()

        async def _send_code(client, phone):
            return await client.send_code_request(phone)

        async def _sign_in_code(client, phone, code, phone_code_hash):
            return await client.sign_in(
                phone=phone, code=code, phone_code_hash=phone_code_hash
            )

        async def _sign_in_password(client, password):
            return await client.sign_in(password=password)

        publisher = TelegramPublisher(store=store)
        publisher._client_factory = lambda session, api_id, api_hash, loop: client
        publisher._validate_client = _validate
        publisher._qr_login = _qr_login
        publisher._send_code = _send_code
        publisher._sign_in_code = _sign_in_code
        publisher._sign_in_password = _sign_in_password
        return publisher, client, store

    def assert_no_pending_task(self, publisher):
        self.assertIsNone(publisher._qr_task)

    def test_start_without_credentials_reports_missing(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(None, None, "Telegram API credentials are not configured."):
            code, payload = publisher.auth_start()
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "credentials_missing")
        self.assertIn("credentials", payload["error"])

    def test_phone_code_flow_with_2fa(self):
        publisher, client, store = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start(phone="+79990000000")
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CODE_REQUESTED)
        self.assertEqual(client.sent_code_requests, ["+79990000000"])

        code, payload = publisher.auth_submit_code("12345")
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CONNECTED)
        self.assertEqual(payload["user"]["username"], "oleg_test")
        self.assertEqual(client.sign_in_calls, [("+79990000000", "12345", "hash-1", None)])
        self.assertTrue(store.data.get("telegram"))
        self.assert_no_pending_task(publisher)

    def test_code_with_2fa_password(self):
        publisher, client, store = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            code, _ = publisher.auth_start(phone="+79990000000")
        self.assertEqual(code, 200)

        async def _sign_in_code(client, phone, code, phone_code_hash):
            raise SessionPasswordNeededError(request=None)

        publisher._sign_in_code = _sign_in_code
        code, payload = publisher.auth_submit_code("12345")
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], PASSWORD_REQUIRED)

        code, payload = publisher.auth_submit_password("secret")
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "invalid_password")

        async def _sign_in_password(client, password):
            return _FakeUser()

        publisher._sign_in_password = _sign_in_password
        code, payload = publisher.auth_submit_password("secret")
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CONNECTED)
        self.assertTrue(store.data.get("telegram"))

    def test_code_flow_resumes_on_second_start(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start(phone="+79990000000")
        self.assertEqual(payload["state"], CODE_REQUESTED)

        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start(phone="+79990000000")
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CODE_REQUESTED)
        self.assertEqual(payload.get("error"), None)

    def test_invalid_code_rejected(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            publisher.auth_start(phone="+79990000000")

        async def _sign_in_code(client, phone, code, phone_code_hash):
            raise PhoneCodeInvalidError(request=None)

        publisher._sign_in_code = _sign_in_code
        code, payload = publisher.auth_submit_code("0000")
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "invalid_code")

    def test_qr_flow(self):
        publisher, client, _ = self.make_publisher()
        scheduled = []
        publisher._schedule_qr_wait = lambda: scheduled.append(True)
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start()
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], QR_WAITING)
        self.assertEqual(payload["qr_url"], "tg://login?token=abc")
        self.assertEqual(scheduled, [True])
        self.assert_no_pending_task(publisher)

    def test_qr_watcher_connects_on_scan(self):
        publisher, _, _ = self.make_publisher()
        publisher._client = _FakeClient()
        publisher._qr = _FakeQR()
        publisher._state = QR_WAITING
        _run(publisher._watch_qr(publisher._qr))
        self.assertEqual(publisher._state, CONNECTED)
        self.assertIsNotNone(publisher._user)

    def test_qr_watcher_requests_2fa(self):
        publisher, _, _ = self.make_publisher()
        publisher._client = _FakeClient()

        class _FakeQr2fa(_FakeQR):
            async def wait(self):
                raise SessionPasswordNeededError(request=None)

        publisher._qr = _FakeQr2fa()
        publisher._state = QR_WAITING
        _run(publisher._watch_qr(publisher._qr))
        self.assertEqual(publisher._state, PASSWORD_REQUIRED)

    def test_submit_code_when_not_in_flow(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            publisher.auth_start()
        code, payload = publisher.auth_submit_code("12345")
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "not_in_flow")

    def test_password_when_not_in_flow(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            publisher.auth_start(phone="+79990000000")
        code, payload = publisher.auth_submit_password("x")
        self.assertEqual(code, 400)
        self.assertEqual(payload["code"], "not_in_flow")

    def test_start_when_already_connected_returns_view(self):
        publisher, client, _ = self.make_publisher()
        async def _validate(client):
            await client.connect()
            return _FakeUser()

        publisher._validate_client = _validate
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start()
        self.assertEqual(payload["state"], CONNECTED)

        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start()
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CONNECTED)

    def test_disconnect_clears_session(self):
        publisher, client, store = self.make_publisher()
        store.data["telegram"] = "1e2e3e"
        publisher._client = client
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_disconnect()
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], IDLE)
        self.assertNotIn("telegram", store.data)
        self.assertTrue(client.disconnected)

    def test_cancel_returns_idle(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start(phone="+79990000000")
        self.assertEqual(payload["state"], CODE_REQUESTED)
        code, payload = publisher.auth_cancel()
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], IDLE)
        self.assertIsNone(payload.get("user"))

    def test_restore_from_saved_session(self):
        publisher, client, store = self.make_publisher()
        store.data["telegram"] = "saved-session"
        async def _validate(client):
            await client.connect()
            return _FakeUser()

        publisher._validate_client = _validate
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start()
        self.assertEqual(code, 200)
        self.assertEqual(payload["state"], CONNECTED)
        self.assertEqual(payload["user"]["username"], "oleg_test")

    def test_error_state_reported(self):
        publisher, _, _ = self.make_publisher()
        async def _validate(client):
            raise Exception("boom")

        publisher._validate_client = _validate
        with _FakeCredentialsContext(123456, "hash"):
            code, payload = publisher.auth_start()
        self.assertEqual(code, 503)
        self.assertEqual(payload["code"], "connect_failed")
        self.assertEqual(payload["error"], "boom")


if __name__ == "__main__":
    unittest.main()
