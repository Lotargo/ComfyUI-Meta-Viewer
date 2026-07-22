from __future__ import annotations

import json
from typing import Any

from .execution import ExecutionRouter, PromptExecutionOutcome
from .prompting import PromptOperation, PromptTask, SceneSpec


class PromptReconstructionError(RuntimeError):
    def __init__(self, message: str, *, code: str):
        self.code = code
        super().__init__(message)


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


__all__ = ["PromptReconstructionError", "PromptReconstructionService"]
