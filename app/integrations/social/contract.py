from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict, field_validator, model_validator

Provider = Literal["telegram", "vk", "instagram"]
AssetKind = Literal["image", "video"]
TargetType = Literal["contact", "saved", "group", "wall", "group_wall", "feed"]
PublishStatus = Literal["ok", "partial", "failed"]

PROVIDERS: tuple[str, ...] = ("telegram", "vk", "instagram")

PROVIDER_TARGET_TYPES: dict[str, frozenset[str]] = {
    "telegram": frozenset({"contact", "saved", "group"}),
    "vk": frozenset({"wall", "group_wall"}),
    "instagram": frozenset({"feed"}),
}

MAX_ASSETS = 10


class SocialContractError(RuntimeError):
    """Raised when a publish payload violates the shared contract."""


class PublishTarget(BaseModel):
    model_config = ConfigDict(frozen=True)

    type: TargetType
    id: str | None = None
    title: str | None = None


class PublishAsset(BaseModel):
    model_config = ConfigDict(frozen=True)

    asset_id: str
    kind: AssetKind


class PublishRequest(BaseModel):
    provider: Provider
    target: PublishTarget
    assets: list[PublishAsset]
    text: str | None = None

    @field_validator("text")
    @classmethod
    def _normalize_text(cls, value: str | None) -> str | None:
        if value is not None and not value.strip():
            return None
        return value

    @model_validator(mode="after")
    def _validate_batch(self) -> "PublishRequest":
        if not self.assets:
            raise ValueError("assets must contain at least one item")
        if len(self.assets) > MAX_ASSETS:
            raise ValueError(f"assets must not exceed {MAX_ASSETS} items")
        allowed = PROVIDER_TARGET_TYPES[self.provider]
        if self.target.type not in allowed:
            raise ValueError(
                f"target type {self.target.type!r} is not supported by "
                f"provider {self.provider!r} "
                f"(allowed: {', '.join(sorted(allowed))})"
            )
        return self


class FailedAsset(BaseModel):
    asset_id: str
    reason: str


class PublishResult(BaseModel):
    status: PublishStatus
    provider: Provider
    target: PublishTarget
    published: list[str] = []
    failed: list[FailedAsset] = []
    external_url: str | None = None
    error: str | None = None

    @classmethod
    def ok(
        cls,
        *,
        provider: Provider,
        target: PublishTarget,
        published: list[str],
        external_url: str | None = None,
    ) -> "PublishResult":
        return cls(
            status="ok",
            provider=provider,
            target=target,
            published=list(published),
            external_url=external_url,
        )

    @classmethod
    def partial(
        cls,
        *,
        provider: Provider,
        target: PublishTarget,
        published: list[str],
        failed: list[FailedAsset],
        external_url: str | None = None,
    ) -> "PublishResult":
        return cls(
            status="partial",
            provider=provider,
            target=target,
            published=list(published),
            failed=list(failed),
            external_url=external_url,
        )

    @classmethod
    def failure(
        cls,
        *,
        provider: Provider,
        target: PublishTarget,
        error: str,
        failed: list[FailedAsset] | None = None,
    ) -> "PublishResult":
        return cls(
            status="failed",
            provider=provider,
            target=target,
            failed=list(failed or []),
            error=error,
        )


def validate_publish_payload(
    payload: dict,
    *,
    provider: Provider | None = None,
) -> PublishRequest:
    request = PublishRequest.model_validate(payload)
    if provider is not None and request.provider != provider:
        raise SocialContractError(
            f"provider mismatch: the URL declares {provider!r} but the "
            f"payload declares {request.provider!r}"
        )
    return request
