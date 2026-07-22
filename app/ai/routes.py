from __future__ import annotations

from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request

from .adaptation import PromptAdaptationService
from .cli import (
    CLI_SPECS,
    CLIIntegrationError,
    cli_catalog,
    discover_cli_integrations,
    list_cli_models,
    probe_cli,
)
from .execution import ExecutionRouter
from .job_store import AIJobStore, AIJobStoreError
from .profiles import AIProfileStore, AIProfileStoreError
from .prompting import PromptFamily, PromptOperation, PromptScenario, PromptTask, SceneSpec
from .ranking import AIRank, AIRankingError, AIRankingService, AIRatingStore
from .reconstruction import PromptReconstructionService
from .remix import RemixPromptSource, RemixRequest, RemixService
from .resources import CapabilityResolver, ModelResource, ModelResourceCatalog, ResourceType
from .secrets import SecretStoreError
from .transport import AIProviderRequestError, test_profile
from .translation import PromptText, PromptTranslationService


ai_blueprint = Blueprint("ai", __name__)


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


@ai_blueprint.route("/api/ai/translate", methods=["POST"])
def ai_translate():
    payload = _json_object()
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raise AIProfileStoreError("profile dictionary is required.")
    task_data = payload.get("task") or {}
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
        asset_id=payload.get("asset_id"),
    )
    return jsonify(outcome.model_dump(mode="json"))


@ai_blueprint.route("/api/ai/adapt", methods=["POST"])
def ai_adapt():
    payload = _json_object()
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raise AIProfileStoreError("profile dictionary is required.")
    task_data = payload.get("task") or {}
    task = PromptTask.model_validate({**task_data, "operation": "adapt"})
    source_data = payload.get("source") or {}
    source = PromptText.model_validate(source_data)

    target_family = payload.get("target_family", PromptFamily.FLUX)
    checkpoint_profile = payload.get("checkpoint_profile")

    service = PromptAdaptationService()
    outcome = service.adapt(
        profile=profile,
        task=task,
        source=source,
        target_family=target_family,
        checkpoint_profile=checkpoint_profile,
        asset_id=payload.get("asset_id"),
    )
    return jsonify(outcome.model_dump(mode="json"))


@ai_blueprint.route("/api/ai/reconstruct", methods=["POST"])
def ai_reconstruct():
    payload = _json_object()
    profile = payload.get("profile")
    if not isinstance(profile, dict):
        raise AIProfileStoreError("profile dictionary is required.")
    task_data = payload.get("task") or {}
    task = PromptTask.model_validate({**task_data, "operation": "reconstruct"})

    scene_spec_data = payload.get("scene_spec")
    service = PromptReconstructionService()
    if scene_spec_data:
        scene_spec = SceneSpec.model_validate(scene_spec_data)
        outcome = service.render_from_scene_spec(
            profile=profile,
            task=task,
            scene_spec=scene_spec,
            asset_id=payload.get("asset_id"),
        )
    else:
        router = ExecutionRouter()
        outcome = router.execute(
            profile=profile,
            task=task,
            user_input=payload.get("user_input", "Reconstruct prompt from asset"),
            asset_id=payload.get("asset_id"),
        )
    return jsonify(outcome.model_dump(mode="json"))


@ai_blueprint.route("/api/ai/remix", methods=["POST"])
def ai_remix():
    payload = _json_object()
    request_data = RemixRequest.model_validate(payload)
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

