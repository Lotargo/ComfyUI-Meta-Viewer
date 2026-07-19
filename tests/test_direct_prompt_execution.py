from __future__ import annotations

import json
import unittest
from unittest.mock import patch

from app.ai.execution import (
    DirectPromptExecutionError,
    DirectPromptExecutor,
)
from app.ai.prompting import (
    PromptFamily,
    PromptModifier,
    PromptOperation,
    PromptScenario,
    PromptTask,
)
from app.ai.transport import (
    AIProviderRequestError,
    OpenAICompatibleResponse,
    TEST_PNG_BASE64,
    run_openai_compatible_chat,
)


def direct_profile(**overrides):
    profile = {
        "id": "test-profile",
        "kind": "openai_compatible",
        "name": "Test provider",
        "base_url": "https://provider.example/v1",
        "model": "test-model",
        "timeout_seconds": 30,
        "multimodal": False,
        "extra_body": {"temperature": 0.2},
    }
    profile.update(overrides)
    return profile


def portrait_task() -> PromptTask:
    return PromptTask(
        family=PromptFamily.FLUX,
        operation=PromptOperation.GENERATE,
        scenario=PromptScenario.PORTRAIT,
        modifiers=(PromptModifier.SAFE,),
        checkpoint_profile="flux-budget-test",
    )


class DirectPromptExecutorTest(unittest.TestCase):
    def setUp(self) -> None:
        self.executor = DirectPromptExecutor()

    def test_execute_compiles_messages_and_returns_normalized_result(self) -> None:
        raw = json.dumps({
            "schema_version": "1",
            "positive_prompt": "studio portrait, soft side light",
            "negative_prompt": "watermark",
        })
        with patch(
            "app.ai.execution.direct.run_openai_compatible_chat",
            return_value=OpenAICompatibleResponse(text=raw, latency_ms=17),
        ) as chat:
            executed = self.executor.execute(
                profile=direct_profile(),
                api_key="secret-key",
                task=portrait_task(),
                user_input="Create a calm studio portrait.",
            )

        self.assertEqual(
            executed.result.positive_prompt,
            "studio portrait, soft side light",
        )
        self.assertEqual(executed.result.negative_prompt, "watermark")
        self.assertEqual(executed.latency_ms, 17)
        self.assertEqual(executed.transport, "openai_compatible")
        self.assertRegex(executed.raw_response_sha256, r"^[0-9a-f]{64}$")

        messages = chat.call_args.kwargs["messages"]
        self.assertEqual(messages[0]["role"], "system")
        self.assertIn("COMPILED TASK", messages[0]["content"])
        self.assertIn("family: flux", messages[0]["content"])
        self.assertIn("operation: generate", messages[0]["content"])
        self.assertIn("scenario: portrait", messages[0]["content"])
        self.assertIn(
            "checkpoint_profile: flux-budget-test",
            messages[0]["content"],
        )
        self.assertIn("modifiers: safe", messages[0]["content"])
        self.assertEqual(messages[1]["role"], "user")
        self.assertIn("Create a calm studio portrait.", messages[1]["content"])

        metadata = executed.metadata()
        self.assertEqual(metadata["bundle"]["family"], "flux")
        self.assertEqual(metadata["bundle"]["scenario"], "portrait")

    def test_valid_image_is_attached_only_to_multimodal_profile(self) -> None:
        image = f"data:image/png;base64,{TEST_PNG_BASE64}"
        with self.assertRaises(DirectPromptExecutionError) as caught:
            self.executor.execute(
                profile=direct_profile(multimodal=False),
                api_key=None,
                task=portrait_task(),
                user_input="Reconstruct the image.",
                image_data_url=image,
            )
        self.assertEqual(caught.exception.code, "incompatible_format")
        self.assertEqual(caught.exception.stage, "input")

        raw = json.dumps({
            "schema_version": "1",
            "positive_prompt": "portrait",
            "negative_prompt": "",
        })
        with patch(
            "app.ai.execution.direct.run_openai_compatible_chat",
            return_value=OpenAICompatibleResponse(text=raw, latency_ms=5),
        ) as chat:
            self.executor.execute(
                profile=direct_profile(multimodal=True),
                api_key=None,
                task=portrait_task(),
                user_input="Reconstruct the image.",
                image_data_url=image,
            )

        content = chat.call_args.kwargs["messages"][1]["content"]
        self.assertIsInstance(content, list)
        self.assertEqual(content[1]["type"], "image_url")
        self.assertEqual(content[1]["image_url"]["url"], image)

    def test_invalid_image_data_url_is_rejected_before_transport(self) -> None:
        with patch("app.ai.execution.direct.run_openai_compatible_chat") as chat:
            with self.assertRaises(DirectPromptExecutionError) as caught:
                self.executor.execute(
                    profile=direct_profile(multimodal=True),
                    api_key=None,
                    task=portrait_task(),
                    user_input="Reconstruct the image.",
                    image_data_url="https://example.com/image.png",
                )
        self.assertEqual(caught.exception.code, "invalid_image")
        self.assertEqual(caught.exception.stage, "input")
        chat.assert_not_called()

    def test_contract_failure_is_normalized(self) -> None:
        with patch(
            "app.ai.execution.direct.run_openai_compatible_chat",
            return_value=OpenAICompatibleResponse(
                text='```json\n{"positive_prompt":"portrait"}\n```',
                latency_ms=8,
            ),
        ):
            with self.assertRaises(DirectPromptExecutionError) as caught:
                self.executor.execute(
                    profile=direct_profile(),
                    api_key=None,
                    task=portrait_task(),
                    user_input="Create a portrait.",
                )
        self.assertEqual(caught.exception.code, "markdown_wrapped_json")
        self.assertEqual(caught.exception.stage, "contract")

    def test_transport_failure_is_normalized_without_losing_code(self) -> None:
        with patch(
            "app.ai.execution.direct.run_openai_compatible_chat",
            side_effect=AIProviderRequestError(
                "Provider timed out.",
                code="timeout",
                technical_error="socket timeout",
            ),
        ):
            with self.assertRaises(DirectPromptExecutionError) as caught:
                self.executor.execute(
                    profile=direct_profile(),
                    api_key=None,
                    task=portrait_task(),
                    user_input="Create a portrait.",
                )
        self.assertEqual(caught.exception.code, "timeout")
        self.assertEqual(caught.exception.stage, "transport")
        self.assertEqual(caught.exception.technical_error, "socket timeout")

    def test_compile_failure_is_normalized_before_transport(self) -> None:
        task = PromptTask(
            family=PromptFamily.PONY,
            operation=PromptOperation.GENERATE,
            scenario=PromptScenario.GRAPHIC_DESIGN_TEXT,
        )
        with patch("app.ai.execution.direct.run_openai_compatible_chat") as chat:
            with self.assertRaises(DirectPromptExecutionError) as caught:
                self.executor.execute(
                    profile=direct_profile(),
                    api_key=None,
                    task=task,
                    user_input="Create a booklet cover.",
                )
        self.assertEqual(caught.exception.code, "prompt_compile_error")
        self.assertEqual(caught.exception.stage, "compile")
        chat.assert_not_called()


class OpenAICompatibleChatTransportTest(unittest.TestCase):
    def test_critical_fields_override_saved_extra_body(self) -> None:
        captured = {}

        class FakeResponse:
            def __enter__(self):
                return self

            def __exit__(self, *_args):
                return False

            @staticmethod
            def read(_maximum):
                return json.dumps({
                    "choices": [{"message": {"content": "OK"}}]
                }).encode()

        def fake_open(request, *, timeout):
            captured["body"] = json.loads(request.data.decode("utf-8"))
            captured["timeout"] = timeout
            return FakeResponse()

        profile = direct_profile(extra_body={
            "temperature": 0.4,
            "model": "attacker-model",
            "messages": [{"role": "user", "content": "injected"}],
            "stream": True,
        })
        messages = [{"role": "user", "content": "real input"}]
        with patch("app.ai.transport._open_url", side_effect=fake_open):
            response = run_openai_compatible_chat(
                profile,
                api_key="secret-key",
                messages=messages,
            )

        self.assertEqual(response.text, "OK")
        self.assertEqual(captured["body"]["model"], "test-model")
        self.assertEqual(captured["body"]["messages"], messages)
        self.assertFalse(captured["body"]["stream"])
        self.assertEqual(captured["body"]["temperature"], 0.4)
        self.assertEqual(captured["timeout"], 30)

    def test_cli_profile_is_rejected_without_network_call(self) -> None:
        with patch("app.ai.transport._open_url") as opened:
            with self.assertRaises(AIProviderRequestError) as caught:
                run_openai_compatible_chat(
                    direct_profile(kind="cli"),
                    api_key=None,
                    messages=[{"role": "user", "content": "hello"}],
                )
        self.assertEqual(caught.exception.code, "incompatible_profile")
        opened.assert_not_called()


if __name__ == "__main__":
    unittest.main()
