from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

from app.ai.cli import CommandResult
from app.ai.execution import (
    OpenCodePromptExecutionError,
    OpenCodePromptExecutionResult,
    OpenCodePromptExecutor,
)
from app.ai.opencode_smoke import (
    resolve_opencode_profile,
    run_opencode_smoke_scenario,
)
from app.ai.profiles import AIProfileStore
from app.ai.prompting import (
    PromptCompiler,
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptResult,
    PromptScenario,
    PromptTask,
)
from app.ai.secrets import SecretStoreStatus


class MemorySecretStore:
    def status(self) -> SecretStoreStatus:
        return SecretStoreStatus(
            available=True,
            backend="tests.MemorySecretStore",
            message="Test credential store",
        )

    def get(self, _profile_id: str) -> str | None:
        return None

    def set(self, _profile_id: str, _value: str) -> None:
        return None

    def delete(self, _profile_id: str) -> None:
        return None


def opencode_profile(**overrides) -> dict:
    profile = {
        "id": "opencode-profile",
        "kind": "cli",
        "name": "OpenCode Smoke",
        "model": "provider/model",
        "timeout_seconds": 60,
        "multimodal": True,
        "cli_type": "opencode",
        "executable": "C:/tools/opencode.cmd",
    }
    profile.update(overrides)
    return profile


def portrait_task() -> PromptTask:
    return PromptTask(
        family=PromptFamily.FLUX,
        operation=PromptOperation.GENERATE,
        scenario=PromptScenario.PORTRAIT,
        modifiers=(PromptModifier.SAFE,),
    )


class OpenCodePromptExecutorTest(unittest.TestCase):
    def test_execute_uses_isolated_tool_denied_agent_and_task_attachment(self) -> None:
        raw_result = json.dumps({
            "schema_version": "1",
            "positive_prompt": "studio portrait, warm side light",
            "negative_prompt": "watermark",
        })
        event_output = json.dumps({"part": {"text": raw_result}})
        captured: dict = {}

        def fake_run_command(args, *, timeout, cwd=None):
            workspace = Path(cwd)
            captured["args"] = list(args)
            captured["timeout"] = timeout
            captured["workspace_exists"] = workspace.is_dir()
            captured["config"] = json.loads(
                (workspace / "opencode.json").read_text(encoding="utf-8")
            )
            captured["task"] = (workspace / "cmv-task.md").read_text(
                encoding="utf-8"
            )
            task_arg = next(
                arg
                for arg in args
                if arg.startswith("--file=") and arg.endswith("cmv-task.md")
            )
            captured["task_arg_exists"] = Path(
                task_arg.split("=", 1)[1]
            ).is_file()
            return CommandResult(
                returncode=0,
                stdout=event_output,
                stderr="",
                elapsed_ms=41,
            )

        with (
            patch(
                "app.ai.execution.opencode.find_executable",
                return_value="C:/tools/opencode.cmd",
            ),
            patch(
                "app.ai.execution.opencode.run_command",
                side_effect=fake_run_command,
            ),
        ):
            executed = OpenCodePromptExecutor().execute(
                profile=opencode_profile(multimodal=False),
                task=portrait_task(),
                user_input="Create a calm studio portrait.",
            )

        self.assertEqual(executed.transport, "opencode")
        self.assertEqual(executed.latency_ms, 41)
        self.assertEqual(
            executed.result.positive_prompt,
            "studio portrait, warm side light",
        )
        self.assertEqual(executed.response_normalizations, ())
        self.assertRegex(executed.raw_response_sha256, r"^[0-9a-f]{64}$")
        self.assertTrue(captured["workspace_exists"])
        self.assertTrue(captured["task_arg_exists"])
        self.assertEqual(
            captured["config"]["agent"]["cmv-prompt-smoke"]["permission"],
            {"*": "deny"},
        )
        self.assertEqual(captured["config"]["share"], "disabled")
        self.assertIn("INSTRUCTION PRECEDENCE", captured["task"])
        self.assertIn("USER TASK INPUT", captured["task"])
        self.assertIn("Create a calm studio portrait.", captured["task"])
        self.assertIn("--pure", captured["args"])
        self.assertIn("cmv-prompt-smoke", captured["args"])
        self.assertIn("provider/model", captured["args"])
        self.assertEqual(captured["timeout"], 300)

    def test_legacy_timeout_is_extended_but_explicit_values_are_preserved(self) -> None:
        self.assertEqual(
            OpenCodePromptExecutor._resolve_timeout(opencode_profile()),
            300,
        )
        self.assertEqual(
            OpenCodePromptExecutor._resolve_timeout(
                opencode_profile(timeout_seconds=420)
            ),
            420,
        )

    def test_invalid_profile_is_rejected_before_cli_lookup(self) -> None:
        with patch("app.ai.execution.opencode.find_executable") as executable:
            with self.assertRaises(OpenCodePromptExecutionError) as caught:
                OpenCodePromptExecutor().execute(
                    profile=opencode_profile(kind="openai_compatible"),
                    task=portrait_task(),
                    user_input="Create a portrait.",
                )
        self.assertEqual(caught.exception.code, "incompatible_profile")
        self.assertEqual(caught.exception.stage, "input")
        executable.assert_not_called()

    def test_single_markdown_json_fence_is_normalized_at_host_boundary(self) -> None:
        output = json.dumps({
            "part": {
                "text": (
                    '```json\n'
                    '{"schema_version":"1","positive_prompt":"portrait",'
                    '"negative_prompt":""}\n'
                    '```'
                )
            }
        })
        with (
            patch(
                "app.ai.execution.opencode.find_executable",
                return_value="C:/tools/opencode.cmd",
            ),
            patch(
                "app.ai.execution.opencode.run_command",
                return_value=CommandResult(
                    returncode=0,
                    stdout=output,
                    stderr="",
                    elapsed_ms=20,
                ),
            ),
        ):
            executed = OpenCodePromptExecutor().execute(
                profile=opencode_profile(multimodal=False),
                task=portrait_task(),
                user_input="Create a portrait.",
            )
        self.assertEqual(executed.result.positive_prompt, "portrait")
        self.assertEqual(
            executed.response_normalizations,
            ("markdown_json_fence_removed",),
        )
        self.assertEqual(
            executed.metadata()["response_normalizations"],
            ["markdown_json_fence_removed"],
        )

    def test_markdown_fence_with_commentary_remains_a_contract_failure(self) -> None:
        output = json.dumps({
            "part": {
                "text": (
                    'Here is the result:\n```json\n'
                    '{"schema_version":"1","positive_prompt":"portrait",'
                    '"negative_prompt":""}\n```'
                )
            }
        })
        with (
            patch(
                "app.ai.execution.opencode.find_executable",
                return_value="C:/tools/opencode.cmd",
            ),
            patch(
                "app.ai.execution.opencode.run_command",
                return_value=CommandResult(
                    returncode=0,
                    stdout=output,
                    stderr="",
                    elapsed_ms=20,
                ),
            ),
        ):
            with self.assertRaises(OpenCodePromptExecutionError) as caught:
                OpenCodePromptExecutor().execute(
                    profile=opencode_profile(multimodal=False),
                    task=portrait_task(),
                    user_input="Create a portrait.",
                )
        self.assertEqual(caught.exception.code, "markdown_wrapped_json")
        self.assertEqual(caught.exception.stage, "contract")

    def test_nonzero_cli_result_preserves_authentication_category(self) -> None:
        with (
            patch(
                "app.ai.execution.opencode.find_executable",
                return_value="C:/tools/opencode.cmd",
            ),
            patch(
                "app.ai.execution.opencode.run_command",
                return_value=CommandResult(
                    returncode=1,
                    stdout="",
                    stderr="Authentication required: run opencode auth login",
                    elapsed_ms=12,
                ),
            ),
        ):
            with self.assertRaises(OpenCodePromptExecutionError) as caught:
                OpenCodePromptExecutor().execute(
                    profile=opencode_profile(multimodal=False),
                    task=portrait_task(),
                    user_input="Create a portrait.",
                )
        self.assertEqual(caught.exception.code, "cli_authentication")
        self.assertEqual(caught.exception.stage, "host")


class OpenCodeSmokeRunnerTest(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp_dir.cleanup)
        self.store = AIProfileStore(
            Path(self.temp_dir.name) / "config.json",
            secret_store=MemorySecretStore(),
        )

    def test_resolver_uses_saved_opencode_profile(self) -> None:
        created = self.store.create({
            "kind": "cli",
            "name": "Local OpenCode",
            "model": "provider/model",
            "timeout_seconds": 60,
            "multimodal": True,
            "cli_type": "opencode",
            "executable": "C:/tools/opencode.cmd",
        })
        self.store.set_defaults({
            "text_profile_id": created["id"],
            "multimodal_profile_id": created["id"],
        })

        text = resolve_opencode_profile(
            self.store,
            selector=None,
            requires_image=False,
        )
        vision = resolve_opencode_profile(
            self.store,
            selector=None,
            requires_image=True,
        )

        self.assertEqual(text.profile["id"], created["id"])
        self.assertEqual(text.selected_by, "text_profile_id")
        self.assertEqual(vision.profile["id"], created["id"])
        self.assertEqual(vision.selected_by, "multimodal_profile_id")

    def test_runner_uses_fake_host_executor_without_network(self) -> None:
        profile = opencode_profile(multimodal=False)

        class FakeExecutor:
            def execute(self, **kwargs):
                bundle = PromptCompiler().compile(kwargs["task"])
                return OpenCodePromptExecutionResult(
                    result=PromptResult(
                        positive_prompt="studio portrait",
                        negative_prompt="",
                    ),
                    bundle=bundle,
                    latency_ms=9,
                    raw_response_sha256="3" * 64,
                )

        report = run_opencode_smoke_scenario(
            scenario_id="flux-portrait-generate",
            profile=profile,
            executor=FakeExecutor(),
            checkpoint_profile="host-checkpoint",
        )

        self.assertFalse(report.failed)
        self.assertEqual(report.execution.transport, "opencode")
        self.assertEqual(
            report.execution.bundle.task.checkpoint_profile,
            "host-checkpoint",
        )
        serialized = report.to_dict()
        self.assertEqual(serialized["execution"]["transport"], "opencode")
        self.assertNotIn("api_key", serialized["profile"])


if __name__ == "__main__":
    unittest.main()
