from __future__ import annotations

import io
import json
import os
import base64
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app.ai.cli import CommandResult, run_cli_test
from app.ai.profiles import AIProfileStore, AIProfileStoreError
from app.ai.secrets import SecretStoreStatus
from app.ai.transport import (
    AIProviderRequestError,
    CONTENT_REJECTED_MESSAGE,
    run_openai_compatible_test,
    TEST_PNG_BASE64,
)
from app.main import app
from PIL import Image


class MemorySecretStore:
    def __init__(self, *, available: bool = True):
        self.values: dict[str, str] = {}
        self.available = available

    def status(self) -> SecretStoreStatus:
        return SecretStoreStatus(
            available=self.available,
            backend="tests.MemorySecretStore" if self.available else None,
            message="Test credential store",
        )

    def _check(self) -> None:
        if not self.available:
            from app.ai.secrets import SecretStoreError

            raise SecretStoreError("Test credential store is unavailable")

    def get(self, profile_id: str) -> str | None:
        self._check()
        return self.values.get(profile_id)

    def set(self, profile_id: str, value: str) -> None:
        self._check()
        self.values[profile_id] = value

    def delete(self, profile_id: str) -> None:
        self._check()
        self.values.pop(profile_id, None)


def direct_payload(**overrides):
    payload = {
        "kind": "openai_compatible",
        "name": "Test provider",
        "base_url": "https://provider.example/v1",
        "api_key_source": "system",
        "api_key": "top-secret-test-key",
        "model": "vision-model-1",
        "timeout_seconds": 30,
        "multimodal": True,
        "extra_body": {"temperature": 0.2},
    }
    payload.update(overrides)
    return payload


class AIProfileStoreTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.config_path = Path(self.temp_dir.name) / "config.json"
        self.secrets = MemorySecretStore()
        self.store = AIProfileStore(
            self.config_path, secret_store=self.secrets
        )

    def test_system_key_is_never_persisted_or_returned(self):
        created = self.store.create(direct_payload())
        self.assertTrue(created["has_credentials"])
        self.assertNotIn("api_key", created)
        raw = self.config_path.read_text(encoding="utf-8")
        self.assertNotIn("top-secret-test-key", raw)
        self.assertNotIn("api_key\"", raw)
        self.assertEqual(self.secrets.values[created["id"]], "top-secret-test-key")

        updated = self.store.update(created["id"], {
            "name": "Renamed provider",
            "api_key": "",
        })
        self.assertEqual(updated["name"], "Renamed provider")
        self.assertEqual(self.secrets.values[created["id"]], "top-secret-test-key")

        self.store.delete(created["id"])
        self.assertNotIn(created["id"], self.secrets.values)

    def test_environment_and_no_key_profiles_do_not_touch_keyring(self):
        with patch.dict(os.environ, {"CMV_TEST_PROVIDER_KEY": "from-env"}):
            profile = self.store.create(direct_payload(
                api_key_source="environment",
                api_key_env="CMV_TEST_PROVIDER_KEY",
                api_key="",
            ))
            self.assertTrue(profile["has_credentials"])
            stored = self.store.get(profile["id"])
            self.assertEqual(self.store.resolve_api_key(stored), "from-env")
        local = self.store.create(direct_payload(
            name="LM Studio",
            base_url="http://127.0.0.1:1234/v1",
            api_key_source="none",
            api_key="",
        ))
        self.assertTrue(local["has_credentials"])
        self.assertEqual(self.secrets.values, {})

    def test_insecure_remote_keys_and_embedded_secrets_are_rejected(self):
        with self.assertRaises(AIProfileStoreError):
            self.store.create(direct_payload(base_url="http://provider.example/v1"))
        with self.assertRaises(AIProfileStoreError):
            self.store.create(direct_payload(
                extra_body={"headers": {"Authorization": "Bearer secret"}}
            ))

    def test_defaults_require_a_multimodal_profile(self):
        text_profile = self.store.create(direct_payload(
            name="Text only",
            multimodal=False,
        ))
        vision_profile = self.store.create(direct_payload(name="Vision"))
        with self.assertRaises(AIProfileStoreError):
            self.store.set_defaults({
                "multimodal_profile_id": text_profile["id"]
            })
        defaults = self.store.set_defaults({
            "text_profile_id": text_profile["id"],
            "multimodal_profile_id": vision_profile["id"],
        })
        self.assertEqual(defaults["text_profile_id"], text_profile["id"])
        self.store.delete(vision_profile["id"])
        self.assertIsNone(self.store.list()["defaults"]["multimodal_profile_id"])


class AIRoutesTest(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.old_config = dict(app.config)
        self.addCleanup(self._restore_config)
        self.secrets = MemorySecretStore()
        app.config.update(
            TESTING=True,
            CONFIG_FILE=str(Path(self.temp_dir.name) / "config.json"),
            AI_SECRET_STORE=self.secrets,
        )
        self.client = app.test_client()

    def _restore_config(self):
        app.config.clear()
        app.config.update(self.old_config)

    def test_profile_api_masks_secrets_and_exposes_settings_page(self):
        page = self.client.get("/settings/ai")
        self.assertEqual(page.status_code, 200)
        self.assertIn(b"AI connections", page.data)

        created_response = self.client.post("/api/ai/profiles", json=direct_payload())
        self.assertEqual(created_response.status_code, 201)
        created = created_response.get_json()["profile"]
        self.assertNotIn("api_key", created)
        profile_id = created["id"]

        listed = self.client.get("/api/ai/profiles").get_json()
        self.assertTrue(listed["secret_store"]["available"])
        self.assertEqual(len(listed["profiles"]), 1)

        with patch("app.ai.routes.test_profile", return_value={
            "ok": True,
            "transport": "openai_compatible",
            "latency_ms": 12,
            "response_preview": "CMV_OK",
        }):
            tested = self.client.post(
                f"/api/ai/profiles/{profile_id}/test",
                json={"multimodal": True},
            )
        self.assertEqual(tested.status_code, 200)
        self.assertEqual(tested.get_json()["response_preview"], "CMV_OK")

        removed = self.client.delete(f"/api/ai/profiles/{profile_id}")
        self.assertEqual(removed.status_code, 200)
        self.assertEqual(self.secrets.values, {})

    def test_cli_discovery_response_does_not_require_credentials(self):
        discovered = [{
            "type": "opencode",
            "label": "OpenCode",
            "installed": True,
            "executable": "C:/tools/opencode.cmd",
            "authentication": {"status": "available", "message": "Configured"},
        }]
        with patch("app.ai.routes.discover_cli_integrations", return_value=discovered):
            response = self.client.get("/api/ai/cli-integrations")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["integrations"], discovered)


class AITransportTest(unittest.TestCase):
    def test_multimodal_probe_is_a_valid_one_pixel_png(self):
        image = Image.open(io.BytesIO(base64.b64decode(TEST_PNG_BASE64)))
        image.load()
        self.assertEqual(image.size, (1, 1))

    def test_openai_compatible_test_parses_standard_response(self):
        profile = direct_payload()
        profile.update({"id": "test-id", "extra_body": {}})

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read(_maximum):
                return json.dumps({
                    "choices": [{"message": {"content": "CMV_OK"}}]
                }).encode()

        with patch("app.ai.transport._open_url", return_value=FakeResponse()):
            result = run_openai_compatible_test(
                profile, api_key="test-key", multimodal=True
            )
        self.assertTrue(result["ok"])
        self.assertEqual(result["response_preview"], "CMV_OK")

    def test_content_policy_errors_have_a_stable_user_message(self):
        profile = direct_payload()
        profile.update({"id": "test-id", "extra_body": {}})
        body = json.dumps({
            "error": {
                "code": "content_policy_violation",
                "message": "Image blocked by safety policy",
            }
        }).encode()
        error = urllib.error.HTTPError(
            "https://provider.example/v1/chat/completions",
            400,
            "Bad Request",
            {},
            io.BytesIO(body),
        )
        with patch("app.ai.transport._open_url", side_effect=error):
            with self.assertRaises(AIProviderRequestError) as caught:
                run_openai_compatible_test(
                    profile, api_key="test-key", multimodal=True
                )
        self.assertEqual(caught.exception.code, "content_rejected")
        self.assertEqual(str(caught.exception), CONTENT_REJECTED_MESSAGE)

    def test_opencode_json_events_are_parsed_without_reading_auth_files(self):
        profile = {
            "cli_type": "opencode",
            "executable": "C:/tools/opencode.cmd",
            "model": "provider/model",
            "timeout_seconds": 20,
        }
        output = json.dumps({"part": {"text": "CMV_OK"}})
        with (
            patch("app.ai.cli.find_executable", return_value=profile["executable"]),
            patch("app.ai.cli.run_command", return_value=CommandResult(
                returncode=0,
                stdout=output,
                stderr="",
                elapsed_ms=15,
            )),
        ):
            result = run_cli_test(profile)
        self.assertEqual(result["response_preview"], "CMV_OK")


if __name__ == "__main__":
    unittest.main()
