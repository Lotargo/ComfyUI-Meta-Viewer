from __future__ import annotations

import os
import unittest
from unittest import mock

from pydantic import ValidationError

from app.integrations.social.contract import (
    MAX_ASSETS,
    PublishAsset,
    PublishRequest,
    PublishResult,
    PublishTarget,
    SocialContractError,
    validate_publish_payload,
)

from app.main import app


def _target(provider: str, target_id: str | None = None) -> PublishTarget:
    type_by_provider = {
        "telegram": "saved",
        "vk": "wall",
        "instagram": "feed",
    }
    return PublishTarget(
        type=type_by_provider[provider],
        id=target_id,
        title=target_id,
    )


def _assets(count: int) -> list[PublishAsset]:
    return [
        PublishAsset(asset_id=f"asset-{index}", kind="image")
        for index in range(count)
    ]


def _payload(
    provider: str = "telegram",
    asset_count: int = 1,
    text: str | None = "post",
    target_id: str | None = None,
) -> dict:
    return {
        "provider": provider,
        "target": _target(provider, target_id).model_dump(),
        "assets": [asset.model_dump() for asset in _assets(asset_count)],
        "text": text,
    }


class PublishResultTest(unittest.TestCase):
    def test_ok_construction(self) -> None:
        target = _target("telegram")
        result = PublishResult.ok(
            provider="telegram",
            target=target,
            published=["asset-0"],
            external_url="https://t.me/c/1/2",
        )
        self.assertEqual(result.status, "ok")
        self.assertEqual(result.published, ["asset-0"])
        self.assertEqual(result.failed, [])
        self.assertIsNone(result.error)
        self.assertEqual(result.external_url, "https://t.me/c/1/2")

    def test_partial_construction(self) -> None:
        result = PublishResult.partial(
            provider="vk",
            target=_target("vk"),
            published=["asset-0"],
            failed=[{"asset_id": "asset-1", "reason": "upload rejected"}],
        )
        self.assertEqual(result.status, "partial")
        self.assertEqual(result.published, ["asset-0"])
        self.assertEqual(len(result.failed), 1)
        self.assertEqual(result.failed[0].asset_id, "asset-1")

    def test_failed_construction(self) -> None:
        result = PublishResult.failure(
            provider="instagram",
            target=_target("instagram"),
            error="session expired",
        )
        self.assertEqual(result.status, "failed")
        self.assertEqual(result.published, [])
        self.assertEqual(result.error, "session expired")

    def test_results_round_trip_through_model_dump(self) -> None:
        result = PublishResult.ok(
            provider="telegram",
            target=_target("telegram"),
            published=["asset-0"],
        )
        restored = PublishResult.model_validate(result.model_dump())
        self.assertEqual(restored, result)


class PublishRequestValidationTest(unittest.TestCase):
    def test_valid_payload_parses(self) -> None:
        request_data = PublishRequest.model_validate(_payload())
        self.assertEqual(request_data.provider, "telegram")
        self.assertEqual(len(request_data.assets), 1)
        self.assertEqual(request_data.text, "post")

    def test_empty_assets_rejected(self) -> None:
        with self.assertRaises(ValidationError):
            PublishRequest.model_validate(_payload(asset_count=0))

    def test_max_asset_limit_enforced(self) -> None:
        request_data = PublishRequest.model_validate(
            _payload(asset_count=MAX_ASSETS)
        )
        self.assertEqual(len(request_data.assets), MAX_ASSETS)
        with self.assertRaises(ValidationError):
            PublishRequest.model_validate(_payload(asset_count=MAX_ASSETS + 1))

    def test_whitespace_text_normalized_to_none(self) -> None:
        request_data = PublishRequest.model_validate(
            _payload(text="   \n\t  ")
        )
        self.assertIsNone(request_data.text)

    def test_provider_target_type_validation(self) -> None:
        # feed is a valid Instagram target but not a Telegram target.
        payload = _payload(provider="telegram")
        payload["target"] = PublishTarget(type="feed").model_dump()
        with self.assertRaisesRegex(ValidationError, "not supported by provider"):
            PublishRequest.model_validate(payload)

    def test_validator_rejects_provider_mismatch(self) -> None:
        with self.assertRaisesRegex(SocialContractError, "provider mismatch"):
            validate_publish_payload(_payload(provider="telegram"), provider="vk")

    def test_validator_accepts_matching_provider(self) -> None:
        request_data = validate_publish_payload(
            _payload(provider="vk"),
            provider="vk",
        )
        self.assertEqual(request_data.provider, "vk")


class SocialRoutesTest(unittest.TestCase):
    def setUp(self) -> None:
        self.client = app.test_client()

    def test_status_lists_all_providers(self) -> None:
        response = self.client.get("/api/social/status")
        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertEqual(
            set(body["providers"]),
            {"telegram", "vk", "instagram"},
        )
        for provider in body["providers"].values():
            self.assertIn("label", provider)
            self.assertIn("implemented", provider)
            self.assertIn("available", provider)
            self.assertIn("connected", provider)

    def test_provider_status_unknown_provider(self) -> None:
        response = self.client.get("/api/social/twitter/status")
        self.assertEqual(response.status_code, 404)

    def test_publish_returns_501_until_implemented(self) -> None:
        response = self.client.post(
            "/api/social/publish",
            json=_payload(provider="instagram"),
        )
        self.assertEqual(response.status_code, 501)
        self.assertEqual(response.get_json()["code"], "not_implemented")

    def test_publish_rejects_empty_body(self) -> None:
        response = self.client.post("/api/social/publish", json=None)
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid_payload")

    def test_provider_publish_rejects_provider_mismatch(self) -> None:
        response = self.client.post(
            "/api/social/vk/publish",
            json=_payload(provider="telegram"),
        )
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["code"], "invalid_payload")

    def test_provider_publish_unknown_provider(self) -> None:
        response = self.client.post(
            "/api/social/twitter/publish",
            json=_payload(),
        )
        self.assertEqual(response.status_code, 404)

    def test_telegram_disabled_by_default(self) -> None:
        response = self.client.get("/api/social/status")
        body = response.get_json()["providers"]
        self.assertIs(body["telegram"]["enabled"], False)
        self.assertIs(body["vk"]["enabled"], True)
        self.assertIs(body["instagram"]["enabled"], True)

    def test_telegram_auth_gated_when_disabled(self) -> None:
        response = self.client.post("/api/social/telegram/auth/start", json={})
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "not_enabled")
        for path in (
            "/api/social/telegram/auth/state",
            "/api/social/telegram/auth/qr.png",
        ):
            self.assertEqual(
                self.client.get(path).status_code,
                404,
                f"{path} should be gated",
            )

    def test_telegram_auth_enabled_via_env(self) -> None:
        with mock.patch.dict(os.environ, {"SOCIAL_TELEGRAM_ENABLED": "1"}):
            response = self.client.post("/api/social/telegram/auth/start", json={})
            # Gate is open; without credentials the flow reports them missing.
            self.assertNotEqual(response.status_code, 404)
            body = response.get_json()
            self.assertEqual(body["code"], "credentials_missing")

    def test_telegram_publish_gated_when_disabled(self) -> None:
        response = self.client.post("/api/social/publish", json=_payload())
        self.assertEqual(response.status_code, 404)
        self.assertEqual(response.get_json()["code"], "not_enabled")


if __name__ == "__main__":
    unittest.main()
