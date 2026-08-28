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
    assert "model_01" in APPROVED_PROFILES
    assert "model_02" in APPROVED_PROFILES
    assert len(APPROVED_PROFILES) >= 3

    model_1 = APPROVED_PROFILES["model_01"]
    assert model_1.prompt_family == PromptFamily.SDXL
    assert model_1.vram_min_gb > 0
    assert "standard" in model_1.quality_preset_ids
    assert len(model_1.aspect_ratios) > 0


def test_load_simple_workflows():
    flow = load_simple_workflow_json("model_01")
    assert isinstance(flow, dict)
    assert "3" in flow  # KSampler
    assert "6" in flow  # CLIPTextEncode (positive)


def test_compile_simple_workflow_model_01():
    profile = APPROVED_PROFILES["model_01"]
    workflow = compile_simple_workflow(
        profile,
        positive_prompt="A realistic forest at sunset",
        negative_prompt="blurry, distorted",
        aspect_ratio="16:9",
        quality=QualityPresetLevel.STANDARD,
        batch_size=2,
        seed=42,
    )

    ksampler = workflow["3"]["inputs"]
    assert ksampler["steps"] == 32
    assert ksampler["seed"] == 42

    latent = workflow["5"]["inputs"]
    assert latent["width"] == 1152
    assert latent["height"] == 640
    assert latent["batch_size"] == 2

    assert workflow["6"]["inputs"]["text"] == "A realistic forest at sunset"
    assert workflow["7"]["inputs"]["text"] == "blurry, distorted"


def test_serialize_approved_profile():
    profile = APPROVED_PROFILES["model_01"]
    serialized = serialize_approved_profile(profile)
    assert serialized["id"] == "model_01"
    assert serialized["name"] == "Model 1"
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
    assert data["default_profile_id"] == "model_01"
    assert "ai_status" in data

    # Test Profile status API
    resp_status = client.get("/api/simple/profiles/model_01/status")
    assert resp_status.status_code == 200
    status_data = json.loads(resp_status.data)
    assert status_data["profile_id"] == "model_01"
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
        json={"message": "Draw a dragon", "profile_id": "model_01"},
    )
    assert resp.status_code == 200
    data = json.loads(resp.data)
    assert data["reply"] == "Enhanced prompt suggestion"
    assert data["profile_id"] == "model_01"

