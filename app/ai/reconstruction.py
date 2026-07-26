from __future__ import annotations

import hashlib
import json
from typing import Any

from pydantic import Field

from .execution.direct import DirectPromptExecutionError, DirectPromptExecutor
from .execution import ExecutionRouter, PromptExecutionOutcome
from .job_store import AIJobStore, AIJobStoreError
from .prompting import (
    PromptContractError,
    PromptOperation,
    PromptTask,
    SceneSpec,
    parse_scene_spec,
)
from .prompting.models import StrictModel
from .transport import (
    AIProviderRequestError,
    OpenAICompatibleResponse,
    run_openai_compatible_chat,
)


SCENE_ANALYSIS_INSTRUCTIONS = """You analyze one image for prompt reconstruction.
Return only one strict JSON object matching this SceneSpec contract:
{
  "schema_version": "1",
  "recommended_scenario": "portrait|single_character|product_object|landscape_environment|architecture_interior|graphic_design_text|illustration_art|multi_character|null",
  "subjects": [{"kind": "text", "position": "text or null", "attributes": {"name": "value"}, "confidence": 0.0}],
  "composition": {"shot": "text or null", "camera_angle": "text or null", "background": "text or null"},
  "visible_text": [{"text": "exact visible text", "placement": "text or null", "confidence": 0.0}],
  "uncertain_details": ["brief uncertainty"]
}
Describe only observable visual evidence. Do not infer identity, hidden content, model names,
generation metadata, or artistic intent. Preserve exact visible text when legible. Use null or
uncertain_details instead of inventing details. Do not return Markdown or a PromptResult."""


class PromptReconstructionError(RuntimeError):
    def __init__(
        self,
        message: str,
        *,
        code: str,
        stage: str = "input",
        job_id: int | None = None,
        technical_error: str | None = None,
    ):
        self.code = code
        self.stage = stage
        self.job_id = job_id
        self.technical_error = technical_error
        super().__init__(message)


class SceneAnalysisOutcome(StrictModel):
    job_id: int
    scene_spec: SceneSpec
    latency_ms: int = Field(ge=0)
    raw_response_sha256: str = Field(pattern=r"^[0-9a-f]{64}$")


class SceneAnalysisService:
    def __init__(
        self,
        *,
        job_store: AIJobStore | None = None,
        chat_runner=run_openai_compatible_chat,
    ):
        self.job_store = job_store or AIJobStore()
        self.chat_runner = chat_runner

    def analyze(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        image_data_url: str,
        api_key: str | None = None,
        asset_id: int | None = None,
    ) -> SceneAnalysisOutcome:
        if task.operation is not PromptOperation.RECONSTRUCT:
            raise PromptReconstructionError(
                "Scene analysis requires operation='reconstruct'.",
                code="invalid_reconstruction_operation",
            )
        if profile.get("kind") != "openai_compatible" or profile.get("multimodal") is not True:
            raise PromptReconstructionError(
                "Choose an OpenAI-compatible profile marked as multimodal for image analysis.",
                code="incompatible_vision_profile",
            )
        try:
            image = DirectPromptExecutor._validate_image_data_url(image_data_url)
        except DirectPromptExecutionError as exc:
            raise PromptReconstructionError(
                str(exc),
                code=getattr(exc, "code", "invalid_image"),
                stage=getattr(exc, "stage", "input"),
                technical_error=getattr(exc, "technical_error", None),
            ) from exc
        job = self.job_store.create(
            task=task.model_copy(update={"output_contract": "scene_spec"}),
            execution_backend="vision-openai-compatible",
            provider_profile_id=profile.get("id"),
            model_id=profile.get("model"),
            asset_id=asset_id,
            user_input="Analyze the selected asset into an editable SceneSpec.",
        )
        try:
            self.job_store.mark_running(job.id)
            response: OpenAICompatibleResponse = self.chat_runner(
                profile,
                api_key=api_key,
                messages=[
                    {"role": "system", "content": SCENE_ANALYSIS_INSTRUCTIONS},
                    {
                        "role": "user",
                        "content": [
                            {"type": "text", "text": "Analyze this image into SceneSpec JSON."},
                            {"type": "image_url", "image_url": {"url": image, "detail": "high"}},
                        ],
                    },
                ],
            )
            scene_spec = parse_scene_spec(response.text)
            composition = scene_spec.composition
            if not (
                scene_spec.subjects
                or scene_spec.visible_text
                or scene_spec.uncertain_details
                or composition.shot
                or composition.camera_angle
                or composition.background
            ):
                raise PromptContractError(
                    "The AI returned an empty SceneSpec.",
                    code="empty_scene_spec",
                    technical_error=response.text[:16_000],
                )
            self.job_store.save_scene_spec(job.id, scene_spec)
            self.job_store.wait_for_scene_review(job.id)
        except (AIProviderRequestError, PromptContractError, AIJobStoreError) as exc:
            try:
                self.job_store.fail(job.id, getattr(exc, "technical_error", None) or str(exc))
            except AIJobStoreError:
                pass
            raise PromptReconstructionError(
                str(exc),
                code=getattr(exc, "code", "reconstruction_persistence_error"),
                stage=(
                    "contract" if isinstance(exc, PromptContractError)
                    else "persistence" if isinstance(exc, AIJobStoreError)
                    else "transport"
                ),
                job_id=job.id,
                technical_error=getattr(exc, "technical_error", None),
            ) from exc
        return SceneAnalysisOutcome(
            job_id=job.id,
            scene_spec=scene_spec,
            latency_ms=response.latency_ms,
            raw_response_sha256=hashlib.sha256(response.text.encode("utf-8")).hexdigest(),
        )


class PromptReconstructionService:
    """Render an editable SceneSpec without repeating image analysis."""

    def __init__(self, *, router: ExecutionRouter | None = None):
        self.router = router or ExecutionRouter()

    def render_from_scene_spec(
        self,
        *,
        profile: dict[str, Any],
        task: PromptTask,
        scene_spec: SceneSpec,
        api_key: str | None = None,
        asset_id: int | None = None,
    ) -> PromptExecutionOutcome:
        if task.operation is not PromptOperation.RECONSTRUCT:
            raise PromptReconstructionError(
                "SceneSpec rendering requires operation='reconstruct'.",
                code="invalid_reconstruction_operation",
            )
        user_input = (
            "REVIEWED SCENE SPEC JSON\n"
            + json.dumps(
                scene_spec.model_dump(mode="json"),
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            )
        )
        return self.router.execute(
            profile=profile,
            task=task,
            user_input=user_input,
            api_key=api_key,
            asset_id=asset_id,
            scene_spec=scene_spec,
        )


__all__ = [
    "PromptReconstructionError",
    "PromptReconstructionService",
    "SceneAnalysisOutcome",
    "SceneAnalysisService",
]
