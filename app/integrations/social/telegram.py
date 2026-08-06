from __future__ import annotations

from .base import SocialNotImplementedError, SocialPublisher
from .contract import PublishRequest, PublishResult


class TelegramPublisher(SocialPublisher):
    provider = "telegram"
    label = "Telegram"

    def status(self) -> dict:
        return {"provider": self.provider, "label": self.label}

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            "Telegram publishing is implemented in a later stage."
        )
