"""Unit tests for the VK social-provider auth flow (VK ID + PKCE).

``VKPublisher`` performs a real HTTP exchange against id.vk.ru, so every test
drives it through a fake ``post`` callable and a fake secret store. The
``_credentials`` resolver is monkeypatched to avoid app-context/network I/O.
"""

from __future__ import annotations

import unittest
from unittest.mock import patch

from app.integrations.social.base import SocialNotImplementedError
from app.integrations.social.contract import PublishRequest
from app.integrations.social.vk import (
    AUTH_PENDING,
    CONNECTED,
    ERROR,
    IDLE,
    VK_ID_AUTHORIZE_URL,
    VK_ID_TOKEN_URL,
    VKAuthError,
    VKPublisher,
    _sha256_b64url,
)


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


class _FakeCredentialsContext:
    """Context manager that makes _credentials() return fixed values."""

    def __init__(self, client_id, client_secret, problem=""):
        self.client_id = client_id
        self.client_secret = client_secret
        self.problem = problem

    def __enter__(self):
        self.patcher = patch.object(
            VKPublisher,
            "_credentials",
            return_value=(self.client_id, self.client_secret, self.problem),
        )
        self.patcher.start()
        return self

    def __exit__(self, *exc):
        self.patcher.stop()


class VKAuthFlowTest(unittest.TestCase):
    def make_publisher(self, responses=None, on_post=None):
        store = _FakeStore()
        calls = []

        def post(url, fields):
            calls.append((url, dict(fields)))
            if on_post:
                return on_post(url, fields)
            if responses:
                response = responses.pop(0)
                if isinstance(response, Exception):
                    raise response
                return response
            return {"error": "unknown"}

        publisher = VKPublisher(store=store, post=post)
        return publisher, store, calls

    def test_auth_start_missing_credentials(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext(None, None, "not configured"):
            status, payload = publisher.auth_start()
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "credentials_missing")
        self.assertIn("not configured", payload["error"])
        self.assertEqual(publisher._state, IDLE)

    def test_auth_start_builds_authorize_url(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", "sekrit"):
            status, payload = publisher.auth_start()
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], AUTH_PENDING)
        url = payload["authorize_url"]
        self.assertTrue(url.startswith(VK_ID_AUTHORIZE_URL))
        from urllib.parse import parse_qs, urlparse

        query = parse_qs(urlparse(url).query)
        self.assertEqual(query["response_type"], ["code"])
        self.assertEqual(query["client_id"], ["1234567"])
        self.assertEqual(query["code_challenge_method"], ["S256"])
        self.assertEqual(query["prompt"], ["login"])
        self.assertIn("vkid:openid", query["scope"][0])
        self.assertEqual(query["state"], [publisher._state_param])
        # PKCE verifier round-trips to the challenge in the URL
        self.assertEqual(query["code_challenge"], [_sha256_b64url(publisher._verifier)])
        self.assertIsNotNone(publisher._device_id)

    def test_auth_start_already_connected(self):
        publisher, store, _ = self.make_publisher()
        store.set("vk", '{"access_token": "t1", "user_id": 42}')
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_state()
            self.assertEqual(publisher._state, CONNECTED)
            status, payload = publisher.auth_start()
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], CONNECTED)
        self.assertIsNone(payload["authorize_url"])

    def test_submit_code_without_flow(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", None):
            status, payload = publisher.auth_submit_code("abc")
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "not_in_flow")

    def test_submit_code_state_mismatch(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status, payload = publisher.auth_submit_code("abc", state="bogus")
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "state_mismatch")

    def test_submit_code_empty(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status, payload = publisher.auth_submit_code("   ")
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "invalid_payload")

    def test_submit_code_success(self):
        token_payload = {
            "access_token": "vk1.a.tok",
            "refresh_token": "refresh-1",
            "expires_in": 86400,
            "scope": "vkid:openid",
            "token_type": "Bearer",
            "user_id": 12345,
        }
        publisher, store, calls = self.make_publisher(responses=[token_payload])
        with _FakeCredentialsContext("1234567", "sekrit"):
            publisher.auth_start()
            verifier = publisher._verifier
            code = "the-code"
            status, payload = publisher.auth_submit_code(code, state=publisher._state_param)

        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], CONNECTED)
        self.assertEqual(payload["user_id"], 12345)
        self.assertEqual(len(calls), 1)
        url, fields = calls[0]
        self.assertEqual(url, VK_ID_TOKEN_URL)
        self.assertEqual(fields["grant_type"], "authorization_code")
        self.assertEqual(fields["code"], "the-code")
        self.assertEqual(fields["code_verifier"], verifier)
        self.assertEqual(fields["client_id"], "1234567")
        self.assertEqual(fields["client_secret"], "sekrit")
        # token persisted in the store
        import json

        stored = json.loads(store.data["vk"])
        self.assertEqual(stored["access_token"], "vk1.a.tok")
        self.assertEqual(stored["user_id"], 12345)
        self.assertIsNotNone(stored["device_id"])

    def test_submit_code_omits_secret_when_absent(self):
        token_payload = {"access_token": "vk1.a.tok", "user_id": 7}
        publisher, _, calls = self.make_publisher(responses=[token_payload])
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status, _ = publisher.auth_submit_code("c", state=publisher._state_param)
        self.assertEqual(status, 200)
        _, fields = calls[0]
        self.assertNotIn("client_secret", fields)

    def test_submit_code_error_payload(self):
        publisher, _, _ = self.make_publisher(
            responses=[{"error": "invalid_grant", "error_description": "bad code"}]
        )
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status, payload = publisher.auth_submit_code("c", state=publisher._state_param)
        self.assertEqual(status, 400)
        self.assertEqual(payload["code"], "auth_error")
        self.assertIn("bad code", payload["error"])

    def test_submit_code_transport_failure(self):
        publisher, _, _ = self.make_publisher(
            responses=[VKAuthError("VK ID returned HTTP 500.")]
        )
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status, payload = publisher.auth_submit_code("c", state=publisher._state_param)
        self.assertEqual(status, 502)
        self.assertEqual(payload["code"], "exchange_failed")
        self.assertIn("500", payload["error"])

    def test_auth_state_restores_from_store(self):
        publisher, store, _ = self.make_publisher()
        store.set(
            "vk",
            '{"access_token": "t1", "user_id": 99, "device_id": "d1"}',
        )
        state = publisher.auth_state()
        self.assertEqual(state["state"], CONNECTED)
        self.assertEqual(state["user_id"], 99)
        self.assertEqual(state["device_id"], "d1")

    def test_auth_disconnect_clears(self):
        publisher, store, _ = self.make_publisher()
        store.set("vk", '{"access_token": "t1", "user_id": 1}')
        publisher.auth_state()
        self.assertEqual(publisher._state, CONNECTED)
        status, payload = publisher.auth_disconnect()
        self.assertEqual(status, 200)
        self.assertEqual(payload["state"], IDLE)
        self.assertEqual(store.data.get("vk"), None)
        self.assertIn("vk", store.deleted)

    def test_status_shape(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", None):
            publisher.auth_start()
            status = publisher.status()
        self.assertEqual(status["provider"], "vk")
        self.assertEqual(status["label"], "ВКонтакте")
        self.assertEqual(status["state"], AUTH_PENDING)
        self.assertTrue(status["configured"])

    def test_publish_not_implemented(self):
        publisher, _, _ = self.make_publisher()
        request = PublishRequest(
            provider="vk",
            target={"type": "group_wall", "id": "123"},
            assets=[{"asset_id": "a1", "kind": "image"}],
            text="hello",
        )
        with self.assertRaises(SocialNotImplementedError):
            publisher.publish(request)

    def test_configured_flag(self):
        publisher, _, _ = self.make_publisher()
        with _FakeCredentialsContext("1234567", None):
            state = publisher.auth_state()
        self.assertTrue(state["configured"])
        with _FakeCredentialsContext(None, None, "missing"):
            state = publisher.auth_state()
        self.assertFalse(state["configured"])

    def test_error_state_exposed(self):
        publisher, _, _ = self.make_publisher()
        publisher._state = ERROR
        publisher._error = "boom"
        state = publisher.auth_state()
        self.assertEqual(state["state"], ERROR)
        self.assertEqual(state["error"], "boom")


if __name__ == "__main__":
    unittest.main()
