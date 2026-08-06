from __future__ import annotations

from .base import SocialNotImplementedError, SocialPublisher
from .contract import PublishRequest, PublishResult


class InstagramPublisher(SocialPublisher):
    provider = "instagram"
    label = "Instagram"

    def status(self) -> dict:
        return {"provider": self.provider, "label": self.label}

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            "Instagram publishing is implemented in a later stage."
        )
