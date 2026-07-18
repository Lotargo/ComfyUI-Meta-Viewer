from __future__ import annotations

import io
import json
import os
import base64
import sys
import tempfile
import time
import unittest
import urllib.error
from pathlib import Path
from unittest.mock import patch

from app.ai.cli import (
    CLIIntegrationError,
    CommandResult,
    VISION_TEST_IMAGE,
    cli_catalog,
    detect_ide_installation,
    find_executable,
    list_cli_models,
    probe_cli,
    run_command,
    run_cli_test,
)
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
        self.assertIn(b"AI providers", page.data)
        self.assertIn(b'id="secret-store-status"', page.data)
        self.assertIn(b'id="profile-model-provider"', page.data)
        self.assertIn(b'id="profile-model-name"', page.data)
        self.assertIn(b'id="model-catalog-dialog"', page.data)
        self.assertIn(b"components/toast.css", page.data)
        settings_css = (
            Path(__file__).parents[1]
            / "app"
            / "static"
            / "css"
            / "features"
            / "ai-settings.css"
        ).read_text(encoding="utf-8")
        self.assertIn("overflow-y: auto", settings_css)
        self.assertIn(".status-pill", settings_css)
        self.assertIn(".cli-install", settings_css)

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

    def test_cli_catalog_route_skips_probing(self):
        response = self.client.get("/api/ai/cli-integrations?probe=0")
        self.assertEqual(response.status_code, 200)
        integrations = response.get_json()["integrations"]
        self.assertEqual(
            {item["type"] for item in integrations},
            {"opencode", "claude", "antigravity"},
        )
        for item in integrations:
            self.assertNotIn("installed", item)
            self.assertNotIn("authentication", item)
        antigravity = next(
            item for item in integrations if item["type"] == "antigravity"
        )
        self.assertIn("install", antigravity)

    def test_single_cli_probe_route(self):
        probed = {
            "type": "claude",
            "label": "Claude Code",
            "installed": True,
            "executable": "C:/tools/claude.cmd",
            "authentication": {"status": "error", "message": "No access"},
        }
        with patch("app.ai.routes.probe_cli", return_value=probed) as probe:
            response = self.client.get("/api/ai/cli-integrations/claude")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json()["integration"], probed)
        probe.assert_called_once_with("claude")

    def test_single_cli_probe_route_rejects_unknown_type(self):
        response = self.client.get("/api/ai/cli-integrations/not-a-cli")
        self.assertEqual(response.status_code, 404)

    def test_cli_models_route_forwards_provider_filter(self):
        result = {
            "models": ["deepseek/deepseek-chat"],
            "providers": ["deepseek"],
        }
        with patch("app.ai.routes.list_cli_models", return_value=result) as models:
            response = self.client.get(
                "/api/ai/cli-integrations/opencode/models?provider=deepseek"
            )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), result)
        models.assert_called_once_with("opencode", provider="deepseek")


class CLIDetectionTest(unittest.TestCase):
    def test_catalog_is_static_and_carries_install_metadata(self):
        catalog = cli_catalog()
        self.assertEqual(
            {item["type"] for item in catalog},
            {"opencode", "claude", "antigravity"},
        )
        for item in catalog:
            self.assertNotIn("installed", item)
            self.assertNotIn("authentication", item)
        antigravity = next(
            item for item in catalog if item["type"] == "antigravity"
        )
        install = antigravity["install"]
        self.assertIn("winget", install["windows"]["command"])
        self.assertIn("brew", install["macos"]["command"])
        self.assertTrue(install["docs_url"].startswith("https://"))

    def test_command_timeout_terminates_the_process(self):
        started = time.monotonic()
        with self.assertRaises(CLIIntegrationError) as caught:
            run_command(
                [sys.executable, "-c", "import time; time.sleep(30)"],
                timeout=1,
            )
        self.assertEqual(caught.exception.code, "timeout")
        self.assertLess(time.monotonic() - started, 8)

    def test_opencode_models_can_be_filtered_by_provider(self):
        command_result = CommandResult(
            returncode=0,
            stdout=(
                "deepseek/deepseek-chat\n"
                "deepseek/deepseek-reasoner\n"
            ),
            stderr="",
            elapsed_ms=5,
        )
        with (
            patch("app.ai.cli.find_executable", return_value="C:/tools/opencode.cmd"),
            patch("app.ai.cli.run_command", return_value=command_result) as command,
        ):
            result = list_cli_models("opencode", provider="deepseek")
        command.assert_called_once_with(
            ["C:/tools/opencode.cmd", "models", "deepseek"], timeout=30
        )
        self.assertEqual(result["providers"], ["deepseek"])
        self.assertEqual(result["requested_provider"], "deepseek")
        self.assertEqual(len(result["models"]), 2)

    def test_opencode_model_provider_rejects_command_arguments(self):
        with patch("app.ai.cli.find_executable", return_value="C:/tools/opencode.cmd"):
            with self.assertRaises(CLIIntegrationError):
                list_cli_models("opencode", provider="deepseek --refresh")

    def test_provider_filter_is_rejected_for_other_clis(self):
        with patch("app.ai.cli.find_executable", return_value="C:/tools/claude.cmd"):
            with self.assertRaises(CLIIntegrationError):
                list_cli_models("claude", provider="anthropic")

    @unittest.skipUnless(os.name == "nt", "Windows-only fallback layout")
    def test_find_executable_falls_back_to_npm_shim_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            shim_dir = Path(temp_dir) / "npm"
            shim_dir.mkdir()
            shim = shim_dir / "opencode.cmd"
            shim.write_text("@echo off\n", encoding="utf-8")
            with (
                patch("app.ai.cli.shutil.which", return_value=None),
                patch.dict(os.environ, {"APPDATA": temp_dir}),
            ):
                found = find_executable("opencode")
        self.assertIsNotNone(found)
        self.assertTrue(found.endswith("opencode.cmd"))

    def test_ide_detection_via_path_shim(self):
        with patch(
            "app.ai.cli.shutil.which",
            side_effect=lambda name: (
                "C:/Tools/antigravity-ide.cmd" if name == "antigravity-ide" else None
            ),
        ):
            ide = detect_ide_installation("antigravity")
        self.assertTrue(ide["installed"])
        self.assertIn("antigravity-ide", ide["location"])

    def test_ide_detection_via_install_directory(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            ide_exe = Path(temp_dir) / "Antigravity IDE.exe"
            ide_exe.write_bytes(b"")
            with (
                patch("app.ai.cli.shutil.which", return_value=None),
                patch(
                    "app.ai.cli._ide_candidate_paths",
                    return_value=[ide_exe],
                ),
            ):
                ide = detect_ide_installation("antigravity")
        self.assertTrue(ide["installed"])
        self.assertIn("Antigravity IDE", ide["location"])

    def test_ide_detection_absent_for_other_integrations(self):
        ide = detect_ide_installation("opencode")
        self.assertFalse(ide["installed"])
        self.assertIsNone(ide["location"])

    def test_antigravity_probe_reports_ide_and_install_when_cli_missing(self):
        with (
            patch("app.ai.cli.find_executable", return_value=None),
            patch(
                "app.ai.cli.detect_ide_installation",
                return_value={
                    "installed": True,
                    "location": "C:/Programs/Antigravity IDE",
                    "label": "Antigravity IDE",
                },
            ),
        ):
            result = probe_cli("antigravity")
        self.assertFalse(result["installed"])
        self.assertTrue(result["ide"]["installed"])
        self.assertIn("Antigravity IDE", result["authentication"]["message"])
        self.assertIn("winget", result["install"]["windows"]["command"])

    def test_probe_without_ide_has_no_ide_payload(self):
        with (
            patch("app.ai.cli.find_executable", return_value=None),
            patch(
                "app.ai.cli.detect_ide_installation",
                return_value={"installed": False, "location": None, "label": "Antigravity IDE"},
            ),
        ):
            result = probe_cli("antigravity")
        self.assertFalse(result["installed"])
        self.assertNotIn("ide", result)
        self.assertIn("install", result)


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

    def test_opencode_multimodal_test_attaches_bundled_image_as_one_argument(self):
        profile = {
            "cli_type": "opencode",
            "executable": "C:/tools/opencode.cmd",
            "model": "provider/model",
            "timeout_seconds": 20,
        }
        output = json.dumps({"part": {"text": "CMV_OK"}})
        with (
            patch("app.ai.cli.find_executable", return_value=profile["executable"]),
            patch(
                "app.ai.cli.run_command",
                return_value=CommandResult(
                    returncode=0,
                    stdout=output,
                    stderr="",
                    elapsed_ms=15,
                ),
            ) as command,
        ):
            result = run_cli_test(profile, multimodal=True)

        args = command.call_args.args[0]
        file_args = [arg for arg in args if arg.startswith("--file=")]
        self.assertEqual(file_args, [f"--file={VISION_TEST_IMAGE}"])
        self.assertNotIn("--file", args)
        self.assertTrue(VISION_TEST_IMAGE.is_file())
        with Image.open(VISION_TEST_IMAGE) as image:
            self.assertEqual(image.format, "JPEG")
            self.assertGreater(image.width, 1)
            self.assertGreater(image.height, 1)
        self.assertTrue(any("attached garden image" in arg for arg in args))
        self.assertEqual(result["response_preview"], "CMV_OK")


if __name__ == "__main__":
    unittest.main()
