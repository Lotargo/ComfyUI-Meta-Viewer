from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Internal models ──────────────────────────────────────────────

class ImageMetadata(BaseModel):
    """Result of extract_metadata()."""
    file: str
    path: str
    format: str | None = None
    size: list[int] | None = None
    mode: str | None = None
    error: str | None = None
    exif: dict[str, str] | None = None
    prompt_parameters: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    prompt_api_json: dict[str, Any] | None = None
    workflow_ui_json: dict[str, Any] | None = None
    raw_parameters: str | None = None


class ImageInsertRow(BaseModel):
    """Input for database.insert_images()."""
    rel_path: str
    file_name: str
    file_size: int = 0
    file_mtime: float = 0
    format: str | None = None
    width: int = 0
    height: int = 0
    mode: str | None = None
    error: str | None = None
    metadata_json: str | None = None
    thumbnail_b64: str | None = None


class FolderInfo(BaseModel):
    """Folder metadata from DB."""
    id: int
    path: str
    name: str
    scanned_at: str | None = None
    created_at: str | None = None
    image_count: int = 0


# ── API Request models ──────────────────────────────────────────

class ScanRequest(BaseModel):
    path: str = Field(..., min_length=1)


class ExtractRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)


# ── API Response models ─────────────────────────────────────────

class ImageListItem(BaseModel):
    """Paginated image entry."""
    id: int | None = None
    file_name: str
    format: str | None = None
    size: list[int] | None = None
    mode: str | None = None
    error: str | None = None
    thumbnail: str | None = None
    file: str | None = None
    path: str | None = None
    prompt_parameters: dict[str, Any] | None = None


class ImageDetail(ImageListItem):
    """Full image metadata."""
    prompt_parameters: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    exif: dict[str, str] | None = None
    raw_chunks: dict[str, Any] | None = None
    raw_parameters: str | None = None
    raw_params: str | None = None
    folder_id: int | None = None


class ScanResponse(BaseModel):
    folder_id: int
    folder: FolderInfo | None = None
    page: int = 1
    per_page: int = 50
    total: int = 0
    images: list[ImageListItem] = []
    cached: int = 0
    processed: int = 0


class ImagesResponse(BaseModel):
    images: list[ImageListItem] = []
    total: int = 0
    page: int = 1
    per_page: int = 50


class UploadResponse(BaseModel):
    images: list[dict[str, Any]] = []
    count: int = 0
    folder_id: int | None = None


class ExtractResponse(BaseModel):
    images: list[dict[str, Any]] = []
    count: int = 0


class FolderListResponse(BaseModel):
    folders: list[FolderInfo] = []


class OkResponse(BaseModel):
    ok: bool = True

