from __future__ import annotations

from .contract import PublishRequest, PublishResult


class SocialNotImplementedError(RuntimeError):
    """Raised by publisher skeletons until the transport is implemented."""


class SocialPublisher:
    provider: str = ""
    label: str = ""
    implemented: bool = False

    def status(self) -> dict:
        raise SocialNotImplementedError(
            f"{self.label} status is not implemented yet."
        )

    def publish(self, request: PublishRequest) -> PublishResult:
        raise SocialNotImplementedError(
            f"{self.label} publishing is not implemented yet."
        )
