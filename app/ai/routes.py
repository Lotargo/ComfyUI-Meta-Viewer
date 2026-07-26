from __future__ import annotations

import base64
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request
from pydantic import ValidationError

from app import database

from .adaptation import PromptAdaptationError, PromptAdaptationService
from .cli import (
    CLI_SPECS,
    CLIIntegrationError,
    cli_catalog,
    discover_cli_integrations,
    list_cli_models,
    probe_cli,
)
from .execution import ExecutionRouter, ExecutionRouterError
from .job_store import AIJobStatus, AIJobStore, AIJobStoreError
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import PromptFamily, PromptOperation, PromptScenario, PromptTask, SceneSpec
from .prompting.registry import FAMILY_PROFILES, SCENARIO_MANIFESTS
from .ranking import AIRank, AIRankingError, AIRankingService, AIRatingStore
from .reconstruction import (
    PromptReconstructionError,
    PromptReconstructionService,
    SceneAnalysisService,
)
from .remix import RemixError, RemixPromptSource, RemixRequest, RemixService
from .resources import (
    CapabilityResolver,
    ModelEcosystem,
    ModelResource,
    ModelResourceCatalog,
    ModelResourceError,
    ResourceType,
)
from .secrets import SecretStoreError
from .transport import AIProviderRequestError, test_profile
from .translation import PromptText, PromptTranslationError, PromptTranslationService


ai_blueprint = Blueprint("ai", __name__)
MAX_RECONSTRUCTION_IMAGE_BYTES = 20 * 1024 * 1024


def _store() -> AIProfileStore:
    return AIProfileStore(
        Path(current_app.config["CONFIG_FILE"]),
        secret_store=current_app.config.get("AI_SECRET_STORE"),
    )


def _json_object() -> dict:
    payload = request.get_json(silent=True)
    if not isinstance(payload, dict):
        raise AIProfileStoreError("A JSON object is required.")
    return payload


def _job_store() -> AIJobStore:
    return AIJobStore()


def _resolved_text_profile(payload: dict) -> tuple[AIProfileStore, dict]:
    profile_store = _store()
    profile_id = payload.get("profile_id")
    if profile_id is None:
        profile_id = profile_store.list()["defaults"].get("text_profile_id")
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise AIProfileStoreError(
            "Choose an AI text profile before running this operation.",
            code="missing_profile",
        )
    return profile_store, profile_store.get(profile_id)


def _asset_image_data_url(asset_id: int) -> str:
    source = database.get_asset_source_info(asset_id)
    if source is None:
        raise AIJobStoreError(f"Asset {asset_id} does not exist.")
    if source.get("media_type") != "image":
        raise AIJobStoreError("Scene reconstruction currently requires an image asset.")
    if int(source.get("file_size") or 0) > MAX_RECONSTRUCTION_IMAGE_BYTES:
        raise AIJobStoreError("The source image exceeds the 20 MB analysis limit.")
    try:
        if source.get("has_original_data"):
            data = database.get_asset_original_data(asset_id)
        else:
            path = Path(str(source.get("path") or ""))
            if not path.is_file():
                raise OSError("The indexed image file is unavailable.")
            if path.stat().st_size > MAX_RECONSTRUCTION_IMAGE_BYTES:
                raise AIJobStoreError("The source image exceeds the 20 MB analysis limit.")
            data = path.read_bytes()
    except OSError as exc:
        raise AIJobStoreError(f"Cannot read source image: {exc}") from exc
    if not data:
        raise AIJobStoreError("The source image is empty or unavailable.")
    if len(data) > MAX_RECONSTRUCTION_IMAGE_BYTES:
        raise AIJobStoreError("The source image exceeds the 20 MB analysis limit.")
    mime_type = str(source.get("mime_type") or "image/png").lower()
    if mime_type not in {"image/png", "image/jpeg", "image/jpg", "image/webp", "image/gif"}:
        suffix = Path(str(source.get("file_name") or "")).suffix.lower()
        mime_type = {
            ".png": "image/png",
            ".jpg": "image/jpeg",
            ".jpeg": "image/jpeg",
            ".webp": "image/webp",
            ".gif": "image/gif",
        }.get(suffix, "application/octet-stream")
    if not mime_type.startswith("image/"):
        raise AIJobStoreError("The source asset has an unsupported image format.")
    return f"data:{mime_type};base64,{base64.b64encode(data).decode('ascii')}"


@ai_blueprint.errorhandler(AIProfileStoreError)
def profile_error(error: AIProfileStoreError):
    if error.code == "profile_not_found":
        status = 404
    elif error.code == "missing_credentials":
        status = 409
    else:
        status = 400
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(SecretStoreError)
def secret_store_error(error: SecretStoreError):
    return jsonify({"error": str(error), "code": "secret_store_unavailable"}), 503


@ai_blueprint.errorhandler(CLIIntegrationError)
def cli_error(error: CLIIntegrationError):
    status = 404 if error.code == "cli_unavailable" else 422
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(AIJobStoreError)
def ai_job_error(error: AIJobStoreError):
    status = 404 if "does not exist" in str(error) else 422
    return jsonify({"error": str(error), "code": "ai_job_store_error"}), status


@ai_blueprint.errorhandler(RemixError)
def ai_remix_error(error: RemixError):
    status = 404 if error.code == "asset_not_found" else 422
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(PromptTranslationError)
def ai_translation_error(error: PromptTranslationError):
    status = 404 if error.code == "translation_not_found" else 422
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(PromptAdaptationError)
def ai_adaptation_error(error: PromptAdaptationError):
    status = 404 if error.code == "adaptation_not_found" else 422
    return jsonify({"error": str(error), "code": error.code}), status


@ai_blueprint.errorhandler(PromptReconstructionError)
def ai_reconstruction_error(error: PromptReconstructionError):
    status = 502 if error.stage in {"transport", "host", "contract"} else 422
    return jsonify({
        "error": str(error),
        "code": error.code,
        "stage": error.stage,
        "job_id": error.job_id,
        "technical_error": error.technical_error,
    }), status


@ai_blueprint.errorhandler(ExecutionRouterError)
def ai_execution_error(error: ExecutionRouterError):
    status = 502 if error.stage in {"transport", "contract"} else 422
    return jsonify({
        "error": str(error),
        "code": error.code,
        "stage": error.stage,
        "job_id": error.job_id,
        "technical_error": error.technical_error,
    }), status


@ai_blueprint.errorhandler(ValidationError)
def ai_validation_error(error: ValidationError):
    first = error.errors()[0] if error.errors() else {"msg": str(error)}
    return jsonify({
        "error": first.get("msg", str(error)),
        "code": "invalid_prompt_task",
    }), 422


@ai_blueprint.errorhandler(AIRankingError)
def ai_ranking_error(error: AIRankingError):
    status = 404 if "not found" in str(error) else 422
    return jsonify({"error": str(error), "code": "ai_ranking_error"}), status


@ai_blueprint.route("/settings/ai")
def ai_settings_page():
    return render_template("ai_settings.html")


@ai_blueprint.route("/api/ai/profiles", methods=["GET", "POST"])
def ai_profiles():
    store = _store()
    if request.method == "GET":
        return jsonify(store.list())
    return jsonify({"profile": store.create(_json_object())}), 201


@ai_blueprint.route("/api/ai/profiles/<profile_id>", methods=["PATCH", "DELETE"])
def ai_profile(profile_id: str):
    store = _store()
    if request.method == "DELETE":
        store.delete(profile_id)
        return jsonify({"ok": True})
    return jsonify({"profile": store.update(profile_id, _json_object())})


@ai_blueprint.route("/api/ai/defaults", methods=["PATCH"])
def ai_defaults():
    return jsonify({"defaults": _store().set_defaults(_json_object())})


@ai_blueprint.route("/api/ai/profiles/<profile_id>/test", methods=["POST"])
def ai_profile_test(profile_id: str):
    store = _store()
    profile = store.get(profile_id)
    payload = request.get_json(silent=True) or {}
    if not isinstance(payload, dict):
        raise AIProfileStoreError("A JSON object is required.")
    try:
        result = test_profile(
            store,
            profile,
            multimodal=payload.get("multimodal") is True,
        )
    except AIProviderRequestError as exc:
        status = 504 if exc.code == "timeout" else 422
        return jsonify({
            "error": str(exc),
            "code": exc.code,
            "technical_error": exc.technical_error,
        }), status
    return jsonify(result)


@ai_blueprint.route("/api/ai/cli-integrations", methods=["GET"])
def ai_cli_integrations():
    if request.args.get("probe", "").lower() in {"0", "false", "no"}:
        return jsonify({"integrations": cli_catalog()})
    return jsonify({"integrations": discover_cli_integrations()})


@ai_blueprint.route("/api/ai/cli-integrations/<cli_type>", methods=["GET"])
def ai_cli_integration(cli_type: str):
    if cli_type not in CLI_SPECS:
        raise CLIIntegrationError(
            "Unsupported CLI integration.", code="cli_unavailable"
        )
    return jsonify({"integration": probe_cli(cli_type)})


@ai_blueprint.route("/api/ai/cli-integrations/<cli_type>/models", methods=["GET"])
def ai_cli_models(cli_type: str):
    return jsonify(list_cli_models(cli_type, provider=request.args.get("provider")))


@ai_blueprint.route("/api/ai/jobs/<int:job_id>", methods=["GET"])
def ai_job(job_id: int):
    snapshot = _job_store().get(job_id)
    return jsonify(snapshot.model_dump(mode="json"))


@ai_blueprint.route("/api/ai/jobs/<int:job_id>/review", methods=["POST"])
def ai_job_review(job_id: int):
    payload = request.get_json(silent=True)
    if payload is None:
        payload = {}
    if not isinstance(payload, dict):
        raise AIJobStoreError("A JSON object is required.")
    unexpected = set(payload) - {"draft_id"}
    if unexpected:
        raise AIJobStoreError(
            "Unsupported review fields: " + ", ".join(sorted(unexpected))
        )
    draft_id = payload.get("draft_id")
    if draft_id is not None and (
        isinstance(draft_id, bool) or not isinstance(draft_id, int)
    ):
        raise AIJobStoreError("draft_id must be an integer.")
    snapshot = _job_store().accept_draft(job_id, draft_id=draft_id)
    return jsonify(snapshot.model_dump(mode="json"))


@ai_blueprint.route("/api/ai/jobs/<int:job_id>/cancel", methods=["POST"])
def ai_job_cancel(job_id: int):
    job = _job_store().cancel(job_id)
    return jsonify({"job": job.model_dump(mode="json")})


@ai_blueprint.route("/api/ai/prompt-drafts/<int:draft_id>", methods=["GET", "PATCH"])
def ai_prompt_draft(draft_id: int):
    store = _job_store()
    if request.method == "GET":
        draft = store.get_draft(draft_id)
    else:
        payload = _json_object()
        unexpected = set(payload) - {"positive_prompt", "negative_prompt"}
        if unexpected:
            raise AIJobStoreError(
                "Unsupported prompt draft fields: " + ", ".join(sorted(unexpected))
            )
        draft = store.revise_draft(
            draft_id,
            positive_prompt=payload.get("positive_prompt"),
            negative_prompt=payload.get("negative_prompt"),
        )
    job = store.get(draft.job_id).job
    return jsonify({
        "draft": draft.model_dump(mode="json"),
        "context": store.draft_context(draft, job).model_dump(mode="json"),
    })


@ai_blueprint.route("/api/ai/prompt-capabilities", methods=["GET"])
def ai_prompt_capabilities():
    families = []
    for family, profile in FAMILY_PROFILES.items():
        scenarios = []
        for scenario, status in profile.capabilities.items():
            manifest = SCENARIO_MANIFESTS.get(scenario)
            if manifest is None or not manifest.supports_family(family):
                continue
            scenarios.append({
                "id": scenario.value,
                "status": status.value,
            })
        families.append({
            "id": family.value,
            "version": profile.version,
            "scenarios": scenarios,
        })
    return jsonify({"families": families})


@ai_blueprint.route("/api/ai/generate", methods=["POST"])
def ai_generate():
    payload = _json_object()
    profile_store, profile = _resolved_text_profile(payload)
    task_data = payload.get("task") or {}
    if not isinstance(task_data, dict):
        raise AIProfileStoreError("task dictionary is required.")
    task = PromptTask.model_validate({**task_data, "operation": "generate"})
    user_input = payload.get("user_input", "")

    outcome = ExecutionRouter().execute(
        profile=profile,
        api_key=profile_store.resolve_api_key(profile),
        task=task,
        user_input=user_input,
    )
    snapshot = _job_store().get(outcome.job_id)
    if not snapshot.drafts:
        raise AIJobStoreError(
            f"AI job {outcome.job_id} completed without a prompt draft."
        )
    prompt_draft = snapshot.drafts[-1]
    return jsonify({
        "job": snapshot.job.model_dump(mode="json"),
        "prompt_draft": prompt_draft.model_dump(mode="json"),
        "context": _job_store().draft_context(
            prompt_draft, snapshot.job
        ).model_dump(mode="json"),
    }), 201


@ai_blueprint.route("/api/ai/translate", methods=["POST"])
def ai_translate():
    payload = _json_object()
    profile_store, profile = _resolved_text_profile(payload)
    task_data = payload.get("task") or {}
    if not isinstance(task_data, dict):
        raise AIProfileStoreError("task dictionary is required.")
    task = PromptTask.model_validate({**task_data, "operation": "translate"})
    source_data = payload.get("source") or {}
    source = PromptText.model_validate(source_data)

    target_lang = payload.get("target_language") or "en"
    source_lang = payload.get("source_language")

    service = PromptTranslationService()
    outcome = service.translate(
        profile=profile,
        task=task,
        source=source,
        target_language=target_lang,
        source_language=source_lang,
        api_key=profile_store.resolve_api_key(profile),
        asset_id=payload.get("asset_id"),
    )
    snapshot = _job_store().get(outcome.execution.job_id)
    if not snapshot.drafts:
        raise AIJobStoreError(
            f"AI job {outcome.execution.job_id} completed without a prompt draft."
        )
    prompt_draft = snapshot.drafts[-1]
    return jsonify({
        "job": snapshot.job.model_dump(mode="json"),
        "prompt_draft": prompt_draft.model_dump(mode="json"),
        "context": _job_store().draft_context(
            prompt_draft, snapshot.job
        ).model_dump(mode="json"),
        "translation": outcome.translation.model_dump(mode="json"),
    }), 201


@ai_blueprint.route("/api/ai/adapt", methods=["POST"])
def ai_adapt():
    payload = _json_object()
    profile_store, profile = _resolved_text_profile(payload)
    task_data = payload.get("task") or {}
    if not isinstance(task_data, dict):
        raise AIProfileStoreError("task dictionary is required.")
    task = PromptTask.model_validate({**task_data, "operation": "adapt"})
    source_data = payload.get("source") or {}
    source = PromptText.model_validate(source_data)

    target_family = payload.get("target_family", PromptFamily.FLUX)
    checkpoint_profile = payload.get("checkpoint_profile")
    checkpoint_resource = _adaptation_checkpoint_resource(
        payload.get("checkpoint_resource_hash"),
        target_family=target_family,
    )

    service = PromptAdaptationService()
    outcome = service.adapt(
        profile=profile,
        task=task,
        source=source,
        target_family=target_family,
        checkpoint_profile=checkpoint_profile,
        checkpoint_resource=checkpoint_resource,
        api_key=profile_store.resolve_api_key(profile),
        asset_id=payload.get("asset_id"),
    )
    snapshot = _job_store().get(outcome.execution.job_id)
    if not snapshot.drafts:
        raise AIJobStoreError(
            f"AI job {outcome.execution.job_id} completed without a prompt draft."
        )
    prompt_draft = snapshot.drafts[-1]
    return jsonify({
        "job": snapshot.job.model_dump(mode="json"),
        "prompt_draft": prompt_draft.model_dump(mode="json"),
        "context": _job_store().draft_context(
            prompt_draft, snapshot.job
        ).model_dump(mode="json"),
        "adaptation": outcome.adaptation.model_dump(mode="json"),
    }), 201


def _adaptation_checkpoint_resource(
    content_hash: object,
    *,
    target_family: PromptFamily | str,
) -> ModelResource | None:
    if content_hash is None or content_hash == "":
        return None
    if not isinstance(content_hash, str):
        raise PromptAdaptationError(
            "checkpoint_resource_hash must be a model resource identity.",
            code="invalid_checkpoint_resource",
        )
    try:
        family = PromptFamily(target_family)
    except ValueError as exc:
        raise PromptAdaptationError(
            "target_family must be one of: flux, sdxl, pony.",
            code="invalid_target_family",
        ) from exc
    try:
        resource = ModelResourceCatalog().get_by_hash(content_hash.strip())
    except ModelResourceError as exc:
        raise PromptAdaptationError(
            "The selected checkpoint resource is unavailable.",
            code="invalid_checkpoint_resource",
        ) from exc
    if resource.resource_type is not ResourceType.CHECKPOINT or not resource.is_available:
        raise PromptAdaptationError(
            "The selected model resource is not an available checkpoint.",
            code="invalid_checkpoint_resource",
        )
    compatible_architectures = {
        PromptFamily.FLUX: {ModelEcosystem.FLUX_1, ModelEcosystem.OTHER},
        PromptFamily.SDXL: {
            ModelEcosystem.SDXL,
            ModelEcosystem.ILLUSTRIOUS,
            ModelEcosystem.OTHER,
        },
        PromptFamily.PONY: {ModelEcosystem.PONY, ModelEcosystem.OTHER},
    }
    if (
        resource.architecture not in compatible_architectures[family]
        and resource.prompt_family != family.value
    ):
        raise PromptAdaptationError(
            "The selected checkpoint does not match the target prompt family.",
            code="incompatible_checkpoint_resource",
        )
    return resource


@ai_blueprint.route("/api/ai/reconstruct", methods=["POST"])
def ai_reconstruct():
    payload = _json_object()
    profile_store, profile = _resolved_text_profile(payload)
    task_data = payload.get("task") or {}
    if not isinstance(task_data, dict):
        raise AIProfileStoreError("task dictionary is required.")
    task = PromptTask.model_validate({**task_data, "operation": "reconstruct"})

    scene_spec_data = payload.get("scene_spec")
    scene_spec_job_id = payload.get("scene_spec_job_id")
    asset_id = payload.get("asset_id")
    if asset_id is not None and (
        isinstance(asset_id, bool) or not isinstance(asset_id, int) or asset_id <= 0
    ):
        raise AIJobStoreError("asset_id must be a positive integer.")
    if scene_spec_job_id is not None:
        if isinstance(scene_spec_job_id, bool) or not isinstance(scene_spec_job_id, int):
            raise AIJobStoreError("scene_spec_job_id must be an integer.")
        source_snapshot = _job_store().get(scene_spec_job_id)
        if source_snapshot.scene_spec is None:
            raise AIJobStoreError(
                f"AI job {scene_spec_job_id} has no saved SceneSpec."
            )
        scene_spec = source_snapshot.scene_spec
        source_asset_id = source_snapshot.job.asset_id
        if asset_id is not None and source_asset_id is not None and asset_id != source_asset_id:
            raise AIJobStoreError(
                "asset_id does not match the asset attached to the saved SceneSpec."
            )
        asset_id = source_asset_id or asset_id
    elif scene_spec_data:
        scene_spec = SceneSpec.model_validate(scene_spec_data)
    else:
        raise AIJobStoreError(
            "scene_spec_job_id or scene_spec is required; run vision analysis first."
        )
    service = PromptReconstructionService()
    outcome = service.render_from_scene_spec(
        profile=profile,
        task=task,
        scene_spec=scene_spec,
        api_key=profile_store.resolve_api_key(profile),
        asset_id=asset_id,
    )
    snapshot = _job_store().get(outcome.job_id)
    if not snapshot.drafts:
        raise AIJobStoreError(f"AI job {outcome.job_id} completed without a prompt draft.")
    prompt_draft = snapshot.drafts[-1]
    return jsonify({
        "job": snapshot.job.model_dump(mode="json"),
        "scene_spec": snapshot.scene_spec.model_dump(mode="json"),
        "prompt_draft": prompt_draft.model_dump(mode="json"),
        "context": _job_store().draft_context(
            prompt_draft, snapshot.job
        ).model_dump(mode="json"),
    }), 201


@ai_blueprint.route("/api/ai/reconstruct/analyze", methods=["POST"])
def ai_reconstruct_analyze():
    payload = _json_object()
    profile_store = _store()
    profile_id = payload.get("profile_id") or profile_store.list()["defaults"].get(
        "multimodal_profile_id"
    )
    if not isinstance(profile_id, str) or not profile_id.strip():
        raise AIProfileStoreError(
            "Choose a multimodal AI profile before analyzing an image.",
            code="missing_profile",
        )
    profile = profile_store.get(profile_id)
    asset_id = payload.get("asset_id")
    if isinstance(asset_id, bool) or not isinstance(asset_id, int):
        raise AIJobStoreError("asset_id must be an integer.")
    image_data_url = _asset_image_data_url(asset_id)
    task_data = payload.get("task") or {}
    if not isinstance(task_data, dict):
        raise AIProfileStoreError("task dictionary is required.")
    task = PromptTask.model_validate({**task_data, "operation": "reconstruct"})
    outcome = SceneAnalysisService().analyze(
        profile=profile,
        task=task,
        image_data_url=image_data_url,
        api_key=profile_store.resolve_api_key(profile),
        asset_id=asset_id,
    )
    snapshot = _job_store().get(outcome.job_id)
    return jsonify({
        "job": snapshot.job.model_dump(mode="json"),
        "scene_spec": outcome.scene_spec.model_dump(mode="json"),
        "analysis": outcome.model_dump(mode="json"),
    }), 201


@ai_blueprint.route("/api/ai/jobs/<int:job_id>/scene-spec", methods=["PATCH"])
def ai_scene_spec_update(job_id: int):
    payload = _json_object()
    unexpected = set(payload) - {"scene_spec"}
    if unexpected:
        raise AIJobStoreError(
            "Unsupported SceneSpec fields: " + ", ".join(sorted(unexpected))
        )
    scene_spec = SceneSpec.model_validate(payload.get("scene_spec"))
    store = _job_store()
    job = store.get(job_id).job
    if job.task.operation is not PromptOperation.RECONSTRUCT:
        raise AIJobStoreError("SceneSpec can only be attached to reconstruct jobs.")
    if job.status is not AIJobStatus.WAITING_FOR_REVIEW:
        raise AIJobStoreError("Only a SceneSpec waiting for review can be edited.")
    store.save_scene_spec(job_id, scene_spec)
    return jsonify({
        "job": store.get(job_id).job.model_dump(mode="json"),
        "scene_spec": scene_spec.model_dump(mode="json"),
    })


@ai_blueprint.route("/api/ai/remix", methods=["POST"])
def ai_remix():
    payload = _json_object()
    request_data = RemixRequest.model_validate({
        key: value
        for key, value in payload.items()
        if key in RemixRequest.model_fields
    })
    service = RemixService()
    outcome = service.create_remix_draft(
        request=request_data,
        execution_backend=payload.get("execution_backend", "direct"),
        provider_profile_id=payload.get("provider_profile_id"),
        model_id=payload.get("model_id"),
    )
    return jsonify(outcome.model_dump(mode="json")), 201


@ai_blueprint.route("/api/ai/resources", methods=["GET", "POST"])
def ai_resources():
    catalog = ModelResourceCatalog()
    if request.method == "POST":
        payload = _json_object()
        resource = ModelResource.model_validate(payload)
        saved = catalog.register(resource)
        return jsonify({"resource": saved.model_dump(mode="json")}), 201

    rt_arg = request.args.get("resource_type")
    arch_arg = request.args.get("architecture")
    resources = catalog.list_resources(
        resource_type=rt_arg,
        architecture=arch_arg,
    )
    return jsonify({"resources": [r.model_dump(mode="json") for r in resources]})


@ai_blueprint.route("/api/ai/resources/resolve", methods=["POST"])
def ai_resources_resolve():
    payload = _json_object()
    ckpt_arch = payload.get("checkpoint_architecture", "sdxl")
    raw_resources = payload.get("resources") or []
    resources = [ModelResource.model_validate(r) for r in raw_resources]
    evaluations = CapabilityResolver.resolve_selection(
        checkpoint_architecture=ckpt_arch,
        resources=resources,
    )
    return jsonify({"evaluations": [e.model_dump(mode="json") for e in evaluations]})


@ai_blueprint.route("/api/ai/evaluate", methods=["POST"])
def ai_evaluate():
    payload = _json_object()
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raise AIProfileStoreError("profile dictionary is required.")
    image_id = payload.get("image_id")
    if not isinstance(image_id, int):
        raise AIRankingError("image_id integer is required.")

    service = AIRankingService()
    rating = service.evaluate_asset(
        profile=profile,
        image_id=image_id,
        prompt_text=payload.get("prompt_text", ""),
        enabled=payload.get("enabled", True),
    )
    return jsonify({"rating": rating.model_dump(mode="json")})


@ai_blueprint.route("/api/ai/ratings/<int:image_id>", methods=["GET", "PATCH"])
def ai_rating(image_id: int):
    store = AIRatingStore()
    if request.method == "GET":
        rating = store.get_by_image_id(image_id)
    else:
        payload = _json_object()
        rank_override = payload.get("rank_override")
        rating = store.set_manual_override(image_id, rank_override)
    return jsonify({"rating": rating.model_dump(mode="json")})
