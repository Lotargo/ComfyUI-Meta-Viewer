from __future__ import annotations

from typing import Any, Literal

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


class AssetInsertRow(BaseModel):
    """Input for the asset index, shared by images and videos."""
    rel_path: str
    file_name: str
    file_size: int = 0
    file_mtime: float = 0
    media_type: Literal["image", "video"] = "image"
    mime_type: str = "application/octet-stream"
    format: str | None = None
    width: int = 0
    height: int = 0
    mode: str | None = None
    duration: float | None = None
    frame_rate: float | None = None
    codec: str | None = None
    error: str | None = None
    metadata_json: str | None = None
    thumbnail_b64: str | None = None
    content_fingerprint: str | None = None
    preview_status: Literal["pending", "ready", "unavailable", "error"] = "pending"
    preview_error: str | None = None


class ImageInsertRow(AssetInsertRow):
    """Compatibility name for callers that still use the image interface."""


class FolderInfo(BaseModel):
    """Folder metadata from DB."""
    id: int
    path: str
    name: str
    scanned_at: str | None = None
    created_at: str | None = None
    image_count: int = 0
    asset_count: int = 0
    video_count: int = 0
    status: str = "idle"
    processed_count: int = 0
    processed_asset_count: int = 0
    enabled: bool = True
    recursive: bool = False
    source_status: Literal[
        "disabled",
        "available",
        "partially_available",
        "unavailable",
        "reconnecting",
        "error",
    ] = "available"
    last_error: str | None = None
    revision: int = 0


# ── API Request models ──────────────────────────────────────────

class ScanRequest(BaseModel):
    path: str = Field(..., min_length=1)
    name: str | None = Field(default=None, min_length=1, max_length=200)
    recursive: bool = False


class SourceUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    enabled: bool | None = None
    recursive: bool | None = None


class AlbumCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=120)


class AlbumUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=120)
    cover_image_id: int | None = Field(default=None, ge=1)
    clear_cover: bool = False


class LibraryAssetUpdateRequest(BaseModel):
    favorite: bool | None = None
    rating: int | None = Field(default=None, ge=0, le=5)
    note: str | None = Field(default=None, max_length=5000)
    tags: list[str] | None = Field(default=None, max_length=50)
    file_name: str | None = Field(default=None, min_length=1, max_length=255)


class LibraryBulkRequest(BaseModel):
    asset_ids: list[int] = Field(..., min_length=1, max_length=1000)
    action: Literal[
        "favorite",
        "unfavorite",
        "add_to_album",
        "remove_from_album",
        "remove_from_index",
        "set_rating",
    ]
    album_id: int | None = Field(default=None, ge=1)
    rating: int | None = Field(default=None, ge=0, le=5)


class LibraryAssetIdsRequest(BaseModel):
    asset_ids: list[int] = Field(..., min_length=1, max_length=1000)


class ExtractRequest(BaseModel):
    paths: list[str] = Field(..., min_length=1)


# ── API Response models ─────────────────────────────────────────

class ImageListItem(BaseModel):
    """Paginated image entry."""
    id: int | None = None
    file_name: str
    media_type: Literal["image", "video"] = "image"
    mime_type: str = "application/octet-stream"
    format: str | None = None
    size: list[int] | None = None
    mode: str | None = None
    duration: float | None = None
    frame_rate: float | None = None
    codec: str | None = None
    preview_status: Literal["pending", "ready", "unavailable", "error"] | None = None
    preview_error: str | None = None
    error: str | None = None
    thumbnail: str | None = None
    file: str | None = None
    path: str | None = None
    has_local_file: bool | None = None
    rating: int | None = Field(default=None, ge=0, le=5)
    prompt_parameters: dict[str, Any] | None = None


class ImageDetail(ImageListItem):
    """Full image metadata."""
    prompt_parameters: dict[str, Any] | None = None
    workflow: dict[str, Any] | None = None
    workflow_ui_json: dict[str, Any] | None = None
    exif: dict[str, str] | None = None
    raw_chunks: dict[str, Any] | None = None
    raw_parameters: str | None = None
    raw_params: str | None = None
    folder_id: int | None = None
    embedded_metadata: dict[str, Any] | None = None
    user_metadata: dict[str, Any] | None = None
    ai_annotations: dict[str, Any] | None = None


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
