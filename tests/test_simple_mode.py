from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

from app.ai.prompting import PromptFamily
from app.comfyui.simple_profiles import (
    APPROVED_PROFILES,
    ApprovedProfile,
    QualityPresetLevel,
    check_profile_health,
    compile_simple_workflow,
    load_simple_workflow_json,
    serialize_approved_profile,
)
from app.main import app


def test_approved_profiles_catalog():
    assert "realism" in APPROVED_PROFILES
    assert "anime" in APPROVED_PROFILES
    assert "universal" in APPROVED_PROFILES

    realism = APPROVED_PROFILES["realism"]
    assert realism.flow_id == "sdxl_pony"
    assert realism.prompt_family == PromptFamily.SDXL
    assert len(realism.strengths) > 0
    assert len(realism.weaknesses) > 0
    assert realism.vram_min_gb > 0
    assert QualityPresetLevel.STANDARD in realism.quality_presets

    anime = APPROVED_PROFILES["anime"]
    assert anime.flow_id == "sdxl_pony"
    assert anime.prompt_family == PromptFamily.PONY

    universal = APPROVED_PROFILES["universal"]
    assert universal.flow_id == "flux"
    assert universal.prompt_family == PromptFamily.FLUX


def test_load_simple_workflows():
    sdxl_flow = load_simple_workflow_json("sdxl_pony")
    assert isinstance(sdxl_flow, dict)
    assert "3" in sdxl_flow  # KSampler
    assert "6" in sdxl_flow  # CLIPTextEncode (positive)

    flux_flow = load_simple_workflow_json("flux")
    assert isinstance(flux_flow, dict)
    assert "7" in flux_flow  # KSampler
    assert "4" in flux_flow  # FluxGuidance


def test_compile_simple_workflow_sdxl_pony():
    profile = APPROVED_PROFILES["realism"]
    workflow = compile_simple_workflow(
        profile,
        positive_prompt="A realistic forest at sunset",
        negative_prompt="blurry, distorted",
        aspect_ratio="16:9",
        quality=QualityPresetLevel.HIGH,
        batch_size=2,
        seed=42,
    )

    ksampler = workflow["3"]["inputs"]
    assert ksampler["steps"] == profile.quality_presets[QualityPresetLevel.HIGH].steps
    assert ksampler["seed"] == 42

    latent = workflow["5"]["inputs"]
    assert latent["width"] == 1216
    assert latent["height"] == 704
    assert latent["batch_size"] == 2

    assert workflow["6"]["inputs"]["text"] == "A realistic forest at sunset"
    assert workflow["7"]["inputs"]["text"] == "blurry, distorted"


def test_compile_simple_workflow_flux():
    profile = APPROVED_PROFILES["universal"]
    workflow = compile_simple_workflow(
        profile,
        positive_prompt="A cinematic robot portrait in glass cafe",
        aspect_ratio="3:4",
        quality=QualityPresetLevel.FAST,
        batch_size=1,
        seed=1234,
    )

    ksampler = workflow["7"]["inputs"]
    assert ksampler["steps"] == profile.quality_presets[QualityPresetLevel.FAST].steps
    assert ksampler["seed"] == 1234

    latent = workflow["6"]["inputs"]
    assert latent["width"] == 896
    assert latent["height"] == 1152

    assert workflow["3"]["inputs"]["text"] == "A cinematic robot portrait in glass cafe"
    assert workflow["4"]["inputs"]["guidance"] == profile.quality_presets[QualityPresetLevel.FAST].guidance


def test_serialize_approved_profile():
    profile = APPROVED_PROFILES["realism"]
    serialized = serialize_approved_profile(profile)
    assert serialized["id"] == "realism"
    assert serialized["name"] == "Realism"
    assert "quality_presets" in serialized
    assert "aspect_ratios" in serialized
    assert "health" in serialized


def test_simple_mode_routes(monkeypatch):
    client = app.test_client()

    # Test Create page HTML response
    resp = client.get("/create")
    assert resp.status_code == 200
    assert b"studio-workspace" in resp.data

    # Test /editor route also returns Simple Mode
    resp_editor = client.get("/editor")
    assert resp_editor.status_code == 200
    assert b"studio-workspace" in resp_editor.data

    # Test Bootstrap API
    resp_boot = client.get("/api/simple/bootstrap")
    assert resp_boot.status_code == 200
    data = json.loads(resp_boot.data)
    assert "profiles" in data
    assert len(data["profiles"]) >= 3
    assert data["default_profile_id"] == "realism"
    assert "ai_status" in data

    # Test Profile status API
    resp_status = client.get("/api/simple/profiles/realism/status")
    assert resp_status.status_code == 200
    status_data = json.loads(resp_status.data)
    assert status_data["profile_id"] == "realism"
    assert "health" in status_data


def test_simple_assistant_chat(monkeypatch):
    from app.ai.transport import OpenAICompatibleResponse
    import app.comfyui.simple_routes as simple_routes

    monkeypatch.setattr(
        simple_routes,
        "_list_ai_profiles",
        lambda: [{"id": "mock-ai", "roles": ["text"], "kind": "openai_compatible", "base_url": "http://mock", "model": "mock-model"}],
    )

    class MockAIStore:
        def resolve_api_key(self, profile):
            return "sk-mock"

    monkeypatch.setattr(simple_routes, "_ai_profile_store", lambda: MockAIStore())

    import app.ai.transport as transport
    monkeypatch.setattr(
        transport,
        "run_openai_compatible_chat",
        lambda **kwargs: OpenAICompatibleResponse(text="Enhanced prompt suggestion", latency_ms=100),
    )

    client = app.test_client()
    resp = client.post(
        "/api/simple/assistant/chat",
        json={"message": "Draw a dragon", "profile_id": "anime"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["reply"] == "Enhanced prompt suggestion"
    assert data["profile_id"] == "anime"

