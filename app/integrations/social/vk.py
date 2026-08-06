from __future__ import annotations

from .base import SocialNotImplementedError, SocialPublisher
from .contract import PublishRequest, PublishResult


class VKPublisher(SocialPublisher):
    provider = "vk"
    label = "ВКонтакте"

    def status(self) -> dict:
        return {"provider": self.provider, "label": self.label}

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            "VK publishing is implemented in a later stage."
        )
