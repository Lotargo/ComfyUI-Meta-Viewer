import tempfile
from pathlib import Path
from PIL import Image

import pytest
from app import database as db
from app.indexing import index_source_directory
from app.main import app
from app.paths import build_runtime_paths
from app.reset_service import reset_application_index
from app.comfyui.workflow_store import WorkflowStore
from app.ai.remix import RemixService, RemixRequest, RemixPromptSource


@pytest.fixture
def temp_environment():
    temp_dir = tempfile.TemporaryDirectory()
    root = Path(temp_dir.name)
    paths = build_runtime_paths(
        {
            "COMFY_META_DATA_DIR": str(root / "data"),
            "COMFY_META_CACHE_DIR": str(root / "cache"),
        },
        project_root=root,
    )
    paths.ensure_directories()
    old_db = db.get_db_path()
    db.set_db_path(paths.database)
    db.init_db()

    source = root / "source_folder"
    source.mkdir(parents=True)
    img_file = source / "test_image.png"
    Image.new("RGB", (10, 10), color="blue").save(img_file)

    index_source_directory(
        source,
        thumbnail_dir=paths.thumbnails,
        preview_dir=paths.previews,
        cutout_dir=paths.cutouts,
    )

    yield {
        "root": root,
        "source": source,
        "img_file": img_file,
        "paths": paths,
    }

    db.set_db_path(old_db)
    temp_dir.cleanup()


def test_reset_index_preserves_source_files(temp_environment):
    img_file = temp_environment["img_file"]
    paths = temp_environment["paths"]
    assert img_file.exists()

    # Perform index reset
    result = reset_application_index(paths)
    assert result.to_dict()["ok"] is True

    # Source file MUST still exist unharmed
    assert img_file.exists()
    assert img_file.stat().st_size > 0


def test_virtual_album_deletion_does_not_delete_physical_assets(temp_environment):
    conn = db.get_conn()
    try:
        # Create virtual album using name column
        cur = conn.execute("INSERT INTO albums (name) VALUES (?)", ("Test Album",))
        album_id = cur.lastrowid

        img_row = conn.execute("SELECT id FROM images LIMIT 1").fetchone()
        assert img_row is not None
        image_id = img_row["id"]

        conn.execute("INSERT INTO album_images (album_id, image_id) VALUES (?, ?)", (album_id, image_id))
        conn.commit()

        # Verify album_images exists
        link = conn.execute("SELECT * FROM album_images WHERE album_id=?", (album_id,)).fetchone()
        assert link is not None

        # Delete virtual album
        conn.execute("DELETE FROM albums WHERE id=?", (album_id,))
        conn.execute("DELETE FROM album_images WHERE album_id=?", (album_id,))
        conn.commit()

        # Image record must still exist
        assert conn.execute("SELECT id FROM images WHERE id=?", (image_id,)).fetchone() is not None
    finally:
        conn.close()

    # Physical file on disk MUST still exist
    assert temp_environment["img_file"].exists()


def test_remix_creates_draft_without_triggering_execution(temp_environment):
    conn = db.get_conn()
    try:
        img_row = conn.execute("SELECT id FROM images LIMIT 1").fetchone()
        assert img_row is not None
        asset_id = img_row["id"]
    finally:
        conn.close()

    remix_service = RemixService()
    sources = remix_service.list_prompt_sources(asset_id)
    assert len(sources) > 0

    request = RemixRequest(
        asset_id=asset_id,
        prompt_source=RemixPromptSource.USER_EDITED,
        override_positive_prompt="a majestic mountain sunset",
        workflow_template_id="core-reference",
    )
    draft_outcome = remix_service.create_remix_draft(request=request)
    assert draft_outcome is not None
    assert draft_outcome.draft.id > 0

    # Confirm no workflow runs were created automatically in ComfyUI
    store = WorkflowStore()
    runs = store.list_runs(limit=10)
    assert len(runs) == 0
