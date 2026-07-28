import io
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from PIL import Image

from app import database
from app.ai.profiles import AIProfileStore
from app.ai.ranking import AIRankingService
from app.comfyui.workflow_execution import WorkflowExecutionService
from app.comfyui.workflow_store import WorkflowStore
from app.main import app


def _valid_png_bytes() -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (10, 10), color="blue").save(buf, format="PNG")
    return buf.getvalue()


@pytest.fixture
def db_env():
    temp_dir = tempfile.TemporaryDirectory()
    old_db = database.get_db_path()
    db_path = Path(temp_dir.name) / "cmv.sqlite3"
    database.set_db_path(db_path)
    database.init_db()
    old_config = {
        "TESTING": app.config.get("TESTING"),
        "CONFIG_FILE": app.config.get("CONFIG_FILE"),
    }
    app.config.update(
        TESTING=True,
        CONFIG_FILE=str(Path(temp_dir.name) / "config.json"),
    )

    yield {"temp_dir": temp_dir, "db_path": db_path}

    database.set_db_path(old_db)
    app.config.update(old_config)
    temp_dir.cleanup()


def test_workflow_draft_and_run_auto_rate(db_env):
    store = WorkflowStore()
    draft = store.create_draft(
        template_id="core-image",
        template_version="1",
        values={"positive_prompt": "a beautiful scenery"},
        resource_selections={},
        auto_rate=True,
    )
    assert draft.auto_rate is True

    run = store.create_run(
        draft_id=draft.id,
        prompt_id="prompt-test-auto-rate-1",
        client_id="client-1",
        auto_rate=True,
    )
    assert run.auto_rate is True

    fetched_draft = store.get_draft(draft.id)
    assert fetched_draft.auto_rate is True

    fetched_run = store.get_run(run.id)
    assert fetched_run.auto_rate is True


def test_auto_rating_lifecycle_trigger_on_completed_run(db_env):
    mock_client = MagicMock()
    mock_client.get_job.return_value = {
        "status": "completed",
        "outputs": {
            "9": {"images": [{"filename": "out_001.png", "subfolder": "", "type": "output"}]}
        },
    }
    mock_client.download_output.return_value = _valid_png_bytes()

    store = WorkflowStore()
    draft = store.create_draft(
        template_id="core-image",
        template_version="1",
        values={"positive_prompt": "test scenery"},
        resource_selections={},
        auto_rate=True,
    )
    run = store.create_run(
        draft_id=draft.id,
        prompt_id="prompt-auto-rate-trigger-1",
        client_id="client-test",
        auto_rate=True,
    )

    mock_profile = {
        "id": "test-multimodal",
        "kind": "openai_compatible",
        "multimodal": True,
        "api_key_source": "none",
    }
    mock_profile_store = MagicMock()
    mock_profile_store.get_defaults.return_value = {"multimodal_profile_id": "test-multimodal", "rating_auto_enabled": True}
    mock_profile_store.get.return_value = mock_profile
    mock_profile_store.resolve_api_key.return_value = None

    with patch.object(AIRankingService, "evaluate_asset") as mock_eval:
        service = WorkflowExecutionService(store=store, client=mock_client, profile_store=mock_profile_store)
        completed_run = service.refresh(run.id)

        assert completed_run.status == "completed"
        assert len(completed_run.output_asset_ids) == 1
        assert mock_eval.called
        assert mock_eval.call_args[1]["image_id"] == completed_run.output_asset_ids[0]


def test_auto_rating_failure_does_not_crash_refresh(db_env):
    mock_client = MagicMock()
    mock_client.get_job.return_value = {
        "status": "completed",
        "outputs": {
            "9": {"images": [{"filename": "out_002.png", "subfolder": "", "type": "output"}]}
        },
    }
    mock_client.download_output.return_value = _valid_png_bytes()

    store = WorkflowStore()
    draft = store.create_draft(
        template_id="core-image",
        template_version="1",
        values={"positive_prompt": "test scenery"},
        resource_selections={},
        auto_rate=True,
    )
    run = store.create_run(
        draft_id=draft.id,
        prompt_id="prompt-auto-rate-failure-1",
        client_id="client-test",
        auto_rate=True,
    )

    mock_profile_store = MagicMock()
    mock_profile_store.get_defaults.return_value = {"multimodal_profile_id": "test-multimodal", "rating_auto_enabled": True}
    mock_profile_store.get.return_value = {"id": "test-multimodal", "kind": "openai_compatible", "multimodal": True, "api_key_source": "none"}
    mock_profile_store.resolve_api_key.return_value = None

    with patch.object(AIRankingService, "evaluate_asset", side_effect=Exception("Rating service error")):
        service = WorkflowExecutionService(store=store, client=mock_client, profile_store=mock_profile_store)
        completed_run = service.refresh(run.id)
        assert completed_run.status == "completed"
