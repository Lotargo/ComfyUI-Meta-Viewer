# API Reference

> REST API reference for ComfyUI Meta Viewer.

Base URL: `http://localhost:7860`

The API is intentionally local-first and single-user oriented. Responses are JSON unless an endpoint explicitly returns media bytes.

`site/api/openapi.json` is the machine-readable public contract rendered by the Scalar portal. It contains every supported non-legacy `/api/*` route. This document is the detailed human reference with behavior, examples, compatibility notes, and retained legacy implementation notes. Public Flask routes and OpenAPI are kept synchronized by `tests/test_openapi_contract.py`.

The pre-Simple-Mode `/api/editor/*` workflow-editor surface is intentionally **legacy/internal**. It remains documented below for implementation history and possible future Advanced Mode reuse, but it is not part of the public OpenAPI contract or its coverage gate.

---

## Table of Contents

- [Folders](#folders)
- [Scanning and Uploads](#scanning-and-uploads)
- [Viewer media list](#viewer-media-list)
- [Library and Albums](#library-and-albums)
- [Thumbnails and Originals](#thumbnails-and-originals)
- [Cutouts](#cutouts)
- [AI Providers](#ai-providers)
- [AI Prompt Drafts](#ai-prompt-drafts)
- [AI Prompt Operations](#ai-prompt-operations)
- [ComfyUI Runtime and Legacy Workflow Editor](#comfyui-runtime-and-legacy-workflow-editor)
- [Create (Simple) API](#create-simple-api)
- [Social API](#social-api)
- [System](#system)
- [Data Models](#data-models)

---

## Folders

### `GET /api/folders`

Returns all indexed folders, including the special `Uploads` folder when uploaded images exist.

**Response:**

```json
{
  "folders": [
    {
      "id": 1,
      "path": "/path/to/images",
      "name": "images",
      "scanned_at": "2026-06-17 12:00:00",
      "created_at": "2026-06-17 12:00:00",
      "image_count": 42,
      "asset_count": 45,
      "video_count": 3,
      "enabled": true,
      "recursive": true,
      "source_status": "available",
      "last_error": null,
      "revision": 4
    }
  ]
}
```

---

### `PATCH /api/folders/{folder_id}`

Updates a physical source. Every field is optional, but at least one must be present.
Disabling a source stops observation and hides its images without deleting indexed rows.
Enabling it queues a reconciliation.

```json
{ "enabled": true, "recursive": true, "name": "ComfyUI Output" }
```

`source_status` is one of `disabled`, `available`, `partially_available`, `unavailable`,
`reconnecting`, or `error`.

---

### `POST /api/folders/{folder_id}/reconcile`

Queues an immediate full reconciliation for an enabled source.

```json
{ "ok": true }
```

---

### `DELETE /api/folders/{folder_id}`

Forgets a source, stops its watcher, and deletes its indexed rows. Source files are untouched.

**Response:**

```json
{ "ok": true }
```

---

### `GET /api/folders/events`

Server-Sent Events stream of the live folder state instead of one-off JSON snapshots. Each event
carries a JSON object keyed by folder ID and is emitted whenever any folder state changes. While a
folder is processing or reconnecting, events are pushed every second; otherwise every five seconds.

```json
data: {"1": {"status": "processing", "source_status": "available", "enabled": true, "image_count": 42}}
```

### `POST /api/folders/{folder_id}/pause`

Temporarily pauses observation and reconciliation for one source. The watch is stopped, and the
source can be resumed later without re-adding it.

**Response:** `{ "ok": true }`

### `POST /api/folders/{folder_id}/resume`

Resumes the paused source and restarts the background worker.

**Response:** `{ "ok": true }`

---

## Scanning and Uploads

### `POST /api/scan`

Connects and scans a local folder in-place. Existing rows are reused when file size and `mtime` did not change. The saved source is then maintained automatically by filesystem events and periodic reconciliation.

**Request:**

```json
{ "path": "/path/to/folder" }
```

**Response:**

```json
{
  "folder_id": 1,
  "folder": {
    "id": 1,
    "path": "/path/to/folder",
    "name": "folder",
    "scanned_at": "2026-06-17 12:00:00",
    "created_at": "2026-06-17 12:00:00",
    "image_count": 42
  },
  "page": 1,
  "per_page": 50,
  "total": 42,
  "images": [
    {
      "id": 1,
      "file_name": "image.png",
      "format": "PNG",
      "size": [1024, 768],
      "mode": "RGBA",
      "error": null,
      "thumbnail": null,
      "file": null,
      "path": null,
      "has_local_file": true
    }
  ],
  "cached": 40,
  "processed": 2
}
```

**Behavior:**

- Scans files in the selected folder, optionally including subfolders.
- Expands and normalizes the folder to an absolute path before saving it.
- Supports `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, and `.tif` when supported by the parser.
- Skips unchanged files using stored size and `mtime` values.
- Stores metadata in SQLite.
- Returns the first paginated page of indexed images.
- Debounces event bursts and waits for size/mtime stability before processing copied files.
- Treats a temporarily unavailable root as offline rather than deleting its indexed rows.

---

### `POST /api/choose-folder`

Opens the local operating system's folder dialog. A successful selection returns an
absolute native path; cancellation returns `null`.

```json
{ "path": "/path/to/folder", "name": "My source", "recursive": true }
```

If a graphical picker is unavailable, the endpoint returns HTTP `503` and the web client
falls back to a manual path prompt:

```json
{
  "error": "Tk folder picker is not installed",
  "code": "folder_picker_unavailable",
  "fallback": "Enter the folder path manually"
}
```

---

### `POST /api/extract`

Extracts metadata from explicit local file paths without indexing them into the SQLite library.

**Request:**

```json
{
  "paths": [
    "/path/to/image1.png",
    "/path/to/image2.png"
  ]
}
```

**Response:**

```json
{
  "images": [
    {
      "file": "image1.png",
      "path": "/path/to/image1.png",
      "format": "PNG",
      "size": [1024, 768],
      "mode": "RGBA",
      "error": null,
      "exif": {},
      "prompt_parameters": {},
      "workflow": {},
      "prompt_api_json": {},
      "workflow_ui_json": {},
      "raw_parameters": null,
      "thumbnail": "data:image/jpeg;base64,..."
    }
  ],
  "count": 1
}
```

---

### `POST /api/upload`

Uploads image or video files through `multipart/form-data`. Uploaded originals are stored as SQLite BLOBs. Images use a lightweight format-aware probe for PNG text keys and JPEG/WebP EXIF, XMP, or comment blocks, then defer full extraction until `GET /api/images/{image_id}` is called. Videos are stored in `Uploads`; ffprobe extracts technical metadata and ffmpeg creates a cached JPEG poster during import. Missing FFmpeg tools leave the original available with an `unavailable` metadata or preview status.

**Request:** `multipart/form-data` with one or more `files` fields.

**Response:**

```json
{
  "assets": [
    {
      "id": 1,
      "folder_id": 1,
      "file_name": "uploaded.mp4",
      "file_size": 123456,
      "media_type": "video",
      "preview_status": "ready"
    }
  ],
  "images": [
    {
      "id": 1,
      "folder_id": 1,
      "file_name": "uploaded.mp4",
      "file_size": 123456,
      "media_type": "video",
      "preview_status": "ready"
    }
  ],
  "count": 1,
  "folder_id": 1
}
```

---

## Viewer media list

### `GET /api/images`

Returns a paginated folder, album, or global media list. The route remains named `/api/images`
for compatibility and defaults to images only. Pass `media_type=image,video` for a unified
list or `media_type=video` for videos only. Assets from disabled sources are omitted;
`folder_id` and `album_id` are mutually exclusive.

The Viewer always supplies its persisted image/video checkbox selection through this
parameter for both the global Media sidebar and the central folder or album gallery.

**Query Parameters:**

| Parameter | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `folder_id` | int | -- | no | Folder ID to load |
| `album_id` | int | -- | no | Virtual album ID to load |
| `page` | int | `1` | no | Page number |
| `per_page` | int | `50` | no | Assets per page |
| `sort_by` | string | `date` | no | `name`, `date`, `size`, or `type` |
| `sort_dir` | string | `desc` | no | `asc` or `desc` |
| `rating` | int | -- | no | Exact rating from `0` (unrated) through `5` |
| `media_type` | string | `image` | no | Comma-separated `image`, `video`, or both |

**Response:**

```json
{
  "images": [
    {
      "id": 1,
      "file_name": "image.png",
      "media_type": "image",
      "format": "PNG",
      "size": [1024, 768],
      "mode": null,
      "error": null,
      "thumbnail": null,
      "file": null,
      "path": null,
      "rating": 4
    }
  ],
  "total": 200,
  "page": 1,
  "per_page": 50
}
```

---

### `GET /api/images/{image_id}`

Returns full metadata for a single image. If an uploaded image has not been opened before, this request extracts its metadata from the stored original and caches the resulting JSON in SQLite. Other uploaded images remain unprocessed.

**Response:**

```json
{
  "id": 1,
  "file_name": "image.png",
  "format": "PNG",
  "size": [1024, 768],
  "mode": "RGBA",
  "error": null,
  "thumbnail": null,
  "file": null,
  "path": null,
  "has_local_file": true,
  "prompt_parameters": {
    "positive_prompt": "a beautiful landscape",
    "negative_prompt": "blurry",
    "generation_settings": {
      "Steps": 20,
      "Sampler": "euler",
      "CFG scale": 7.0,
      "Seed": 12345
    }
  },
  "workflow": {},
  "exif": {},
  "raw_chunks": null,
  "raw_parameters": null,
  "raw_params": null,
  "folder_id": null
}
```

---

### `DELETE /api/images/{image_id}`

Deletes an image row, its virtual library relations, and related thumbnail/preview/cutout
cache files. The physical source file is not deleted.

**Response:**

```json
{ "ok": true }
```

---

### `GET /api/images/{image_id}/file-location`

Returns the resolved physical path for a scanned local image. Uploaded originals stored
inside the app return `409 no_local_file`; missing physical sources return
`404 local_file_unavailable`.

```json
{ "path": "C:\\images\\image.png" }
```

### `POST /api/images/{image_id}/reveal`

Opens the operating system's file manager for a scanned local image. Windows Explorer
and macOS Finder select the file; Linux opens the containing directory through
`xdg-open`.

```json
{ "ok": true }
```

---

## Library and Albums

The separate `/library` page uses these endpoints for virtual organization. Library reads
include disabled and temporarily unavailable sources so album membership, favorites, tags,
notes, and ratings remain visible while a drive or cloud mirror is offline.

### `GET /api/library`

Returns system collection definitions, summary counts, and the current album list.

### `GET /api/library/assets`

Returns paginated library cards. Supported query parameters are `collection`, `album_id`,
`page`, `per_page`, `sort_by`, `sort_dir`, `q`, `source_id`, and `tag`. `collection` is one
of `all`, `favorites`, `without_metadata`, `recently_added`, `unavailable`, `images`,
`videos`, `not_rated`, or `album`.

Each asset includes source/availability fields, `has_local_file`, favorite/rating/note/tags,
all album IDs, thumbnail/original URLs, `media_type`, MIME type, video technical fields, and
`preview_status` / `preview_error`.

### `GET /api/assets/{asset_id}`

Returns details for either an image or video. `/api/images/{image_id}` remains as a compatible
alias. The response exposes three distinct metadata layers:

- `embedded_metadata`: data extracted from the original file;
- `user_metadata`: favorites, rating, note, and tags;
- `ai_annotations`: derived AI results, never presented as embedded generator metadata.

Video details additionally include `duration`, `frame_rate`, `codec`, `mime_type`, and preview state.

### `PATCH /api/library/assets/{asset_id}`

Updates any combination of virtual per-asset fields:

```json
{
  "favorite": true,
  "rating": 4,
  "note": "Primary launch direction",
  "tags": ["hero", "approved"]
}
```

`images` remains a compatibility alias for `assets` in this response.

A rating of `0` clears the rating.

### `POST /api/library/assets/bulk`

Applies a mass action to as many as 1,000 selected assets. Actions are `favorite`,
`unfavorite`, `add_to_album`, `remove_from_album`, `set_rating`, and `remove_from_index`.
Album actions require `album_id`; rating requires `rating`.

```json
{
  "asset_ids": [12, 13, 14],
  "action": "add_to_album",
  "album_id": 3
}
```

`remove_from_album` changes only the join table. `remove_from_index` deletes database rows,
virtual relations, and generated caches. Neither action deletes physical source files.
An indexed file that remains inside an enabled monitored source can be discovered again by
a later reconciliation.

### `POST /api/library/assets/trash`

Moves the physical files for up to 1,000 indexed assets to the operating system's Recycle
Bin or Trash, then removes successfully moved assets and generated caches from the index.
Uploaded originals stored inside the app and unavailable local files are not removed. A
mixed request can therefore return both `removed_ids` and per-asset `failures`.

```json
{
  "asset_ids": [12, 13, 14]
}
```

This endpoint does not require a confirmation token. Recovery is handled by the operating
system's Recycle Bin or Trash.

### Album endpoints

| Method and path | Behavior |
|-----------------|----------|
| `GET /api/albums` | List albums with asset counts and resolved cover IDs |
| `POST /api/albums` | Create an album from `{ "name": "..." }` |
| `PATCH /api/albums/{album_id}` | Rename it or set/clear a member asset as its cover |
| `DELETE /api/albums/{album_id}` | Delete only the virtual album |
| `POST /api/albums/{album_id}/assets` | Add `asset_ids` without copying files |
| `DELETE /api/albums/{album_id}/assets` | Remove `asset_ids` from the album only |
| `POST /api/albums/{album_id}/reorder` | Persist a custom manual order from `{ "asset_ids": [...] }` |

---

## Thumbnails and Originals

### `GET /api/thumbnail/{asset_id}`

Returns a JPEG thumbnail. Images use Pillow; videos use `ffmpeg`. If FFmpeg is unavailable,
video requests return `503` with `code: video_preview_tool_unavailable` while image requests
and indexing continue normally.

**Response:** `image/jpeg`

---

### `GET /api/preview/{image_id}`

Returns a display-oriented image whose longest side is at most 4096 pixels. The preview is generated lazily, cached under `cache/previews/`, and does not trigger metadata extraction. JPEG is used for opaque images and WebP for images with transparency. Only one large preview is generated at a time; concurrent uncached requests receive `202` with `Retry-After`.

---

### `GET /api/original/{asset_id}`

Returns the untouched original image or video for inline viewing or download. Uploaded SQLite BLOBs are streamed in chunks; scanned files use a conditional file response with range support instead of being copied fully into Python memory.

**Response:** the indexed MIME type, including supported `image/*` and `video/*` values, or `application/octet-stream`.

---

## Cutouts

### `GET /api/cutout/{image_id}`

Returns an existing transparent PNG cutout. If no cutout exists, the endpoint returns `404`.

**Response:** `image/png`

**Error:**

```json
{ "error": "Cutout not found" }
```

---

### `POST /api/cutout/{image_id}`

Generates a transparent PNG cutout or returns the cached result metadata when it already exists.

**Response:**

```json
{
  "ok": true,
  "image_id": 1,
  "cutout_url": "/api/cutout/1",
  "cached": false
}
```

---

### `DELETE /api/cutout/{image_id}`

Deletes the cached cutout file for an image.

**Response:**

```json
{
  "ok": true,
  "deleted": true
}
```

---

## AI Providers

The management UI is available at `GET /settings/ai`. Provider APIs never return API key
values. A `has_credentials` flag reports only whether the selected system entry or environment
variable is currently available.

### `GET /api/ai/profiles`

Lists sanitized profiles, default assignments, and the system credential-store status.

```json
{
  "profiles": [
    {
      "id": "3ea89b7d-3bd5-40ed-8486-86aa8e600711",
      "kind": "openai_compatible",
      "name": "Local vision",
      "base_url": "http://127.0.0.1:1234/v1",
      "model": "local-vision-model",
      "api_key_source": "none",
      "api_key_env": null,
      "timeout_seconds": 90,
      "multimodal": true,
      "extra_body": {},
      "has_credentials": true
    }
  ],
  "defaults": {
    "text_profile_id": null,
    "multimodal_profile_id": "3ea89b7d-3bd5-40ed-8486-86aa8e600711"
  },
  "secret_store": {
    "available": true,
    "backend": "keyring.backends.Windows.WinVaultKeyring",
    "message": "API keys are stored in the operating system credential store."
  }
}
```

### `POST /api/ai/profiles`

Creates an OpenAI-compatible or CLI profile. For `api_key_source: "system"`, `api_key` is
required on creation and is handed directly to the OS keyring. It is not written into the JSON
configuration.

```json
{
  "kind": "openai_compatible",
  "name": "Example provider",
  "base_url": "https://provider.example/v1",
  "api_key_source": "system",
  "api_key": "secret value",
  "model": "exact-model-id",
  "timeout_seconds": 60,
  "multimodal": true,
  "extra_body": { "temperature": 0.2 }
}
```

A local CLI profile delegates authorization to the executable:

```json
{
  "kind": "cli",
  "name": "OpenCode vision",
  "cli_type": "opencode",
  "executable": "C:\\Users\\me\\AppData\\Roaming\\npm\\opencode.cmd",
  "model": "provider/model",
  "timeout_seconds": 120,
  "multimodal": true
}
```

### `PATCH /api/ai/profiles/{profile_id}`

Updates supplied fields. Omitting `api_key`, or sending it as an empty string while retaining
system storage, preserves the current key. Changing away from system storage deletes the old
keyring entry after the new configuration is saved.

### `DELETE /api/ai/profiles/{profile_id}`

Deletes the profile, clears any default assignment using it, and removes its system-keyring
entry. It does not modify credentials owned by external CLI tools.

### `PATCH /api/ai/defaults`

Assigns default text and multimodal profiles. Either value can be `null`; the multimodal default
must refer to a profile explicitly marked `multimodal: true`.

```json
{
  "text_profile_id": "2e62129d-3f6b-4370-8204-e53087229acf",
  "multimodal_profile_id": "3ea89b7d-3bd5-40ed-8486-86aa8e600711"
}
```

### `POST /api/ai/profiles/{profile_id}/test`

Performs a minimal real request using the exact configured model. `{ "multimodal": true }`
adds a generated one-pixel PNG for OpenAI-compatible and OpenCode profiles. Known failures use
distinct codes including `authentication_error`, `content_rejected`, `incompatible_format`,
`network_error`, `timeout`, `cli_authentication`, and `provider_error`.

### `GET /api/ai/cli-integrations`

Detects `opencode`, `claude`, and `agy`/`antigravity` through PATH and invokes documented version
and authorization-status commands. The response includes executable path, version, capability
flags, and an authorization state. No credential file is opened. `?probe=0` skips the live probe and
returns the static catalog instead.

### `GET /api/ai/cli-integrations/{cli_type}`

Probes one integration (`opencode`, `claude`, or `agy`) and returns its singular `integration`
object. Unsupported CLI types answer with `code: cli_unavailable`.

### `GET /api/ai/cli-integrations/{cli_type}/models`

Asks the installed CLI for model IDs when it exposes a model-list command. OpenCode IDs use the
`provider/model` form. Claude Code currently returns `source: "manual"`; enter an exact model ID
or supported alias. Antigravity support is experimental because its documented print mode does
not expose a stable JSON response protocol.

---

## System

### `POST /api/reset-index`

Stops background indexing, waits for application SQLite connections to close, physically
deletes `meta.db`, `meta.db-wal`, `meta.db-shm`, and generated caches, creates a fresh
schema, and queues saved active source directories for reindexing. `/api/reset` is retained
as a compatibility alias. Virtual albums, favorites, ratings, tags, notes, and uploaded
originals stored as SQLite BLOBs are permanently deleted; files in scanned source
directories are not modified.

**Request:**

```json
{ "confirm": "reset-index" }
```

**Response:**

```json
{
  "ok": true,
  "factory_reset": false,
  "deleted": ["/path/to/meta.db", "/path/to/cache/thumbnails/1.jpg"],
  "reindexed_sources": ["/path/to/source"],
  "skipped_sources": []
}
```

Saved sources that are temporarily unavailable remain in `config.json` and are returned in
`skipped_sources`. A file deletion failure returns HTTP `500` with an explicit `failures`
array instead of being ignored.

---

### `POST /api/factory-reset`

Performs Reset Index and additionally deletes `config.json`. The web client also clears its
versioned browser preferences after a successful response. This endpoint requires its own
confirmation token.

```json
{ "confirm": "factory-reset" }
```

---

### `GET /api/diagnostics`

Returns local diagnostics and cache statistics.

**Response:**

```json
{
  "db_path": "/absolute/path/to/project/.comfy_meta_uploads/meta.db",
  "folders": 3,
  "images": 150,
  "uploads": 12,
  "thumbnail_dir": "/absolute/path/to/project/cache/thumbnails",
  "thumbnail_count": 138,
  "preview_dir": "/absolute/path/to/project/cache/previews",
  "preview_count": 7,
  "cutout_dir": "/absolute/path/to/project/cache/cutouts",
  "cutout_count": 5,
  "upload_dir": "/absolute/path/to/project/.comfy_meta_uploads"
}
```

---

## AI Prompt Drafts

`POST /api/ai/adapt` creates a family-aware prompt adaptation. In addition to `source`, `task`,
`target_family`, and the optional tested `checkpoint_profile`, the caller can send
`checkpoint_resource_hash` when the selected checkpoint exists in the local model catalog. Trusted
catalog trigger words that are already present in the source prompt are protected across normalized
execution and recorded in the adaptation as `protected_triggers`; catalog triggers absent from the
source are not injected.

`GET /api/ai/jobs/{job_id}` returns the durable job snapshot, including the current `SceneSpec`,
all prompt draft revisions, the normalized result, and execution metadata.

`GET /api/ai/prompt-drafts/{draft_id}` returns one draft plus its execution context.

`PATCH /api/ai/prompt-drafts/{draft_id}` accepts `positive_prompt` and/or `negative_prompt`.
It creates and returns an append-only manual revision; the original AI output is not overwritten.

`POST /api/ai/jobs/{job_id}/review` promotes the latest draft to the final result. Pass an optional
`draft_id` to accept a specific revision. `POST /api/ai/jobs/{job_id}/cancel` cancels a queued,
running, or review-waiting job.

```json
{
  "positive_prompt": "edited prompt",
  "negative_prompt": "edited negative prompt"
}
```

---

## AI Prompt Operations

The operation endpoints parse the profile, task, and source the same way and return a durable
`job`, the latest normalized `prompt_draft`, and a `context` (the full message exchange). Job IDs
can be followed through [AI Prompt Drafts](#ai-prompt-drafts).

### `GET /api/ai/prompt-capabilities`

Returns the compiled capability matrix: for every registered prompt family (`flux`, `sdxl`,
`pony`), the declared version and the scenarios (`portrait`, `single_character`, `product_object`,
`architecture_interior`, `landscape_environment`, `illustration_art`, `graphic_design_text`) with
their tested status (`complete`, `partial`, `planned`).

### `POST /api/ai/generate`

Runs a direct raw `generate` operation. The task dictionary must include a scenario; `family` and
`model_style` fall back to the selected profile. Returns `201`.

```json
{
  "profile_id": "…",
  "task": { "family": "flux", "scenario": "portrait" },
  "user_input": "…"
}
```

### `POST /api/ai/translate`

Translates `source` text. `target_language` defaults to `en`; `source_language` is optional. A
reference `asset_id` can be attached for provenance. When `?stream=1`, the `Accept` header requests
`text/event-stream`, or the payload sets `stream: true`, the endpoint streams SSE events
(`status`, `chunk`, `error`/`result`).

### `POST /api/ai/adapt`

Family-aware adaptation. `target_family` and the optional tested `checkpoint_profile` configure the
destination; `checkpoint_resource_hash` resolves the local checkpoint from the model catalog when
present. Trusted catalog trigger words already in the source are preserved as `protected_triggers` -
catalog triggers absent from the source are not injected. Returns `201`.

### `POST /api/ai/enhance`

Enhances a prompt toward stronger composition, lighting, and subject detail. Accepts an optional
`wishes` directive, `checkpoint_profile`, and `checkpoint_resource_hash`. Returns `201`.

### `POST /api/ai/reconstruct`

Renders a full prompt from a saved `SceneSpec`, supplied either directly in `scene_spec` or via a
`scene_spec_job_id` returned by vision analysis. A `scene_spec_job_id` keeps the operation consistent:
if both are given at once, `asset_id` must match the asset attached to the saved `SceneSpec`. Returns
`201` with the job, `scene_spec`, prompt draft, and context.

### `POST /api/ai/reconstruct/analyze`

Runs multimodal vision analysis over an existing asset and returns a `SceneSpec` (the "analyze first"
step). Requires a multimodal profile: `profile_id` defaults to the multimodal default. `asset_id` is
required; `task` follows the same shape as other operations. Returns `201`.

### `PATCH /api/ai/jobs/{job_id}/scene-spec`

Replaces the editable `SceneSpec` of a reconstruct job. Only a job in `WAITING_FOR_REVIEW` whose
operation is `reconstruct` accepts edits.

```json
{ "scene_spec": { "…": "valid SceneSpec" } }
```

### `POST /api/ai/remix`

Creates a remix draft from `asset_id` and a chosen `prompt_source`, using direct or CLI execution.
Additional `execution_backend`, `provider_profile_id`, and `model_id` fields select the runtime. The
created draft links to its parent asset for provenance. The legacy workflow editor exposes a separate
`POST /api/editor/remix` route; that legacy route is not part of the public OpenAPI contract.

### `GET /api/ai/resources`

Lists model resources from the catalog, optionally filtered by `resource_type` and `architecture`.

### `POST /api/ai/resources`

Registers a model resource in the catalog. Returns `201` with the saved resource.

### `POST /api/ai/resources/resolve`

Validates a proposed model selection against a checkpoint architecture and returns per-resource
`evaluations` (coverage and compatibility decisions).

### `POST /api/ai/evaluate`

Runs AI ranking for one asset: requires a multimodal `profile_id`, the target `image_id`, and an
optional `prompt_text`. Returns the derived `rating` (never stored back into generator metadata).

### `GET /api/ai/ratings/{image_id}`

Returns the stored AI rating for an asset, or `404` when none exists.

### `PATCH /api/ai/ratings/{image_id}`

Sets a manual rank override (`rank_override`) on top of the stored AI rating.

### `DELETE /api/ai/ratings/{image_id}`

Deletes the stored AI rating and any manual override for the asset.

```json
{ "ok": true }
```

---

## ComfyUI Runtime and Legacy Workflow Editor

`GET /create` and `GET /editor` now open the Simple Mode Create workspace. The pre-Simple-Mode workflow editor is retained at `GET /editor/legacy`; `GET /settings/comfyui` also renders that legacy workflow tooling while exposing runtime configuration.

The `/api/comfyui/*` runtime routes below are part of the supported public OpenAPI contract. The `/api/editor/*` endpoints in the legacy subsections are intentionally excluded from `site/api/openapi.json` and from the public route/OpenAPI coverage gate. They remain here for implementation history and possible future Advanced Mode reuse. Runtime configuration is stored outside SQLite; legacy workflow drafts and runs are durable SQLite records.

### Runtime control

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET/POST` | `/api/comfyui/config` | Read or update installation path, host, port, interpreter, and launch arguments |
| `POST` | `/api/comfyui/detect` | Validate a standard or Windows Portable installation |
| `GET` | `/api/comfyui/status` | Return managed/external mode, health, queue, installation, and hardware data |
| `POST` | `/api/comfyui/start` | Start the detected local installation |
| `POST` | `/api/comfyui/stop` | Stop only the CMV-managed process |
| `POST` | `/api/comfyui/restart` | Restart the managed process |
| `POST` | `/api/comfyui/interrupt` | Interrupt active ComfyUI execution |
| `GET` | `/api/comfyui/logs` | Return captured managed-process output |
| `POST` | `/api/comfyui/launcher` | Generate a platform-specific launcher script |

### Legacy templates and drafts

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/editor/bootstrap` | Return all manifests, defaults, local resource options, and runtime inventory |
| `GET` | `/api/editor/templates` | Refresh templates and resource inventory |
| `GET` | `/api/editor/templates/{template_id}` | Return one manifest-driven template |
| `PATCH/DELETE` | `/api/editor/templates/{template_id}` | Edit metadata or delete an imported template; built-ins are read-only |
| `POST` | `/api/editor/templates/{template_id}/duplicate` | Create an independent imported copy, choosing a unique ID when none is supplied |
| `GET` | `/api/editor/templates/{template_id}/export` | Download an importable ZIP containing the manifest, API graph, and optional preview |
| `POST` | `/api/editor/templates/import` | Import a multipart JSON bundle or ZIP archive |
| `POST` | `/api/editor/templates/import/analyze` | Analyze an upload and return inferred semantic mappings without saving it |
| `GET` | `/api/editor/workflows` | List built-in and imported templates with persisted validation status |
| `POST` | `/api/editor/workflows/revalidate` | Revalidate every registered template against current ComfyUI inventory |
| `POST` | `/api/editor/workflows/{template_id}/revalidate` | Revalidate one registered template |
| `GET/POST/PUT` | `/api/editor/workflows/{template_id}/mapping` | Read, preview, or save imported-template mapping changes |
| `POST` | `/api/editor/drafts` | Create an editing draft from a template |
| `GET/PATCH` | `/api/editor/drafts/{draft_id}` | Read or update declared values and resource selections |
| `POST` | `/api/editor/drafts/{draft_id}/preview` | Compile the API graph and return dependency preflight data |
| `POST` | `/api/editor/inputs` | Upload a reference image to ComfyUI input storage |

Preview responses keep node and resource failures separate:

```json
{
  "workflow": { "1": { "class_type": "CheckpointLoaderSimple", "inputs": {} } },
  "dependencies": {
    "runtime_online": true,
    "missing_nodes": [],
    "missing_resources": [],
    "compatibility_issues": [],
    "ready": true
  }
}
```

### Legacy runs, output, and Remix

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/editor/drafts/{draft_id}/run` | Revalidate and queue the compiled graph; returns `409` when dependencies are unresolved |
| `GET` | `/api/editor/runs` | List recent durable runs |
| `GET` | `/api/editor/runs/{run_id}` | Refresh remote state and import completed outputs |
| `POST` | `/api/editor/runs/{run_id}/cancel` | Cancel a pending/running prompt |
| `POST` | `/api/editor/remix` | Create a manual draft from `asset_id`; does not queue it |
| `GET` | `/api/editor/assets/{asset_id}/workflow` | Compare an embedded API/UI workflow with installed node types |

Imported output metadata records the template/draft/run/prompt identity and the executed API
workflow. If a draft originated from Remix, the new asset also references its source asset.

### Legacy model scanner

| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/editor/models/rescan` | Trigger a background model rescan; returns `started` or `already_running` |
| `GET` | `/api/editor/models/scan_status` | Return the current scan status snapshot (counts, current file, scanning flag) |
| `GET` | `/api/editor/models/scan_stream` | SSE stream of progress updates for an active rescan |

---

## Create (Simple) API

The Create workspace (`GET /create` or `GET /editor`) is driven by a curated catalog of bundled
generation models (Simple Mode profiles). Only profiles with a ready `workflow.json` and
`bindings.json` can generate; calibration placeholders report status but reject generation.

### `GET /api/simple/models`

Returns the creation-model catalog and the default profile ID.

```json
{
  "models": [ { "id": "model_01", "name": "…", "family": "flux", "…": "…" } ],
  "default_model_id": "model_01"
}
```

### `GET /api/simple/ambient`

Returns up to `limit` (1-72, default 36) curated candidate images: favorites and highly rated
assets, recent generations, and random older works. Candidate lists are cached for 45 seconds and
fall back to recent library images when empty.

```json
{
  "items": [ { "id": 3, "file_name": "x.png", "original_url": "/api/original/3",
               "preview_url": "/api/preview/3", "thumbnail_url": "/api/thumbnail/3",
               "width": 1024, "height": 1024 } ]
}
```

### `GET /api/simple/ai-status`

Reports whether any AI provider is available and whether it can serve text and vision roles.

```json
{ "available": true, "has_text": true, "has_vision": true, "profile_count": 2 }
```

### `GET /api/simple/bootstrap`

One-shot bootstrap for the Create page: the model catalog, the default profile ID, `ambient_candidates`,
and `ai_status`.

### `GET /api/simple/models/{profile_id}/status`

Health of one creation model: installed resources and missing components against the current ComfyUI
inventory. `profiles/{profile_id}/status` is an alias. Pass `?refresh=1` to invalidate the cached
runtime inventory first. Unknown profiles return `404`.

```json
{ "profile_id": "model_01", "health": { "status": "ready", "missing_resources": [] } }
```

### `POST /api/simple/models/{profile_id}/install`

Queues downloads for every missing required resource of the model. When the ComfyUI path is not
configured it answers `409` with `code: comfyui_path_required` and `open_settings: true`, so the
client shows integration settings first.

**Response (`202` when downloads were queued):**

```json
{
  "ok": true,
  "profile_id": "model_01",
  "model_root": "C:\\ComfyUI\\models",
  "downloads": [ { "id": 12, "filename": "model.safetensors", "display_name": "…" } ],
  "unavailable": []
}
```

### `GET /api/simple/downloads`

Lists active and finished downloads, optionally filtered by `?profile_id=`.

```json
{ "items": [ { "id": 12, "filename": "model.safetensors", "status": "downloading",
               "downloaded_bytes": 1048576, "total_bytes": 8388608 } ] }
```

### `POST /api/simple/downloads/{download_id}/pause`

Pauses a download. Unknown IDs return `404`.

**Response:** `{ "item": { "…": "…" } }`

### `POST /api/simple/downloads/{download_id}/resume`

Resumes a paused download. `/retry` is an alias that also restarts a failed download.

### `POST /api/simple/downloads/{download_id}/cancel`

Cancels and removes a download.

### `POST /api/simple/pick-comfyui-directory`

Opens a native folder picker on the same machine. Remote callers receive `403`. On success
`detection` mirrors the result of `POST /api/comfyui/detect`.

```json
{ "cancelled": false, "path": "C:\\ComfyUI_windows_portable", "detection": { "valid": true } }
```

When the user cancels the dialog the response is `{ "cancelled": true }`. If a native picker is not
available the endpoint answers `503` with `code: directory_picker_unavailable`.

### `POST /api/simple/generate`

Queues a generation for one creation model.

```json
{
  "profile_id": "model_01",
  "prompt": "portrait, studio light",
  "negative_prompt": "blurry",
  "improve_with_ai": true,
  "aspect_ratio": "1:1",
  "quality": "standard",
  "batch_size": 1,
  "seed": -1,
  "reference_image": "data:image/png;base64,…"
}
```

Prompt preparation happens server-side: a `reference_image` data URL triggers multimodal
reconstruction from the default vision profile, else `improve_with_ai` runs the prompt compiler
enhancement pass. The command is then compiled into the model API workflow, ComfyUI is auto-started
if needed, and a durable run is created.

**Response (`200`):**

```json
{
  "ok": true,
  "run_id": 7,
  "prompt_id": "a1b2…",
  "positive_prompt": "…",
  "negative_prompt": "…",
  "ai_improved": true,
  "ai_explanation": "Enhanced with AI prompt compiler"
}
```

Errors: `409` `code: workflow_pending` for calibration placeholders, `409` `code: model_not_installed`
with `missing_resources`, `502` `code: comfyui_rejected`, and `503` `code: comfyui_connection_failed`.

### `GET /api/simple/runs/{run_id}`

Refreshes remote ComfyUI state and returns the run plus imported output assets.

```json
{
  "run": { "id": 7, "status": "completed", "output_asset_ids": [42], "…": "…" },
  "status": "completed",
  "outputs": [ { "id": 42, "filename": "…", "preview_url": "/api/preview/42",
                 "thumbnail_url": "/api/thumbnail/42", "width": 1024, "height": 1024 } ],
  "is_complete": true
}
```

### `POST /api/simple/runs/{run_id}/cancel`

Cancels a pending or running generation for this run.

**Response:** `{ "ok": true, "run": { "…": "…" } }`

### `POST /api/simple/assistant/chat`

Single-turn AI assistant for prompt refinement inside Create. Requires a text AI provider; without
one it answers `400` with `code: no_ai_profile`. The assistant receives the selected creation model
and the last eight history turns.

```json
{
  "message": "Add cinematic rim light",
  "profile_id": "model_01",
  "history": [ { "role": "user", "content": "…" } ],
  "current_prompt": "portrait, studio light"
}
```

**Response:** `{ "reply": "refined prompt text…", "profile_id": "model_01" }`

---

## Social API

Social routes are present, but publishing is **not implemented for any provider**; every publisher
reports `implemented: false` and publish requests answer `501` with `code: not_implemented`. The
integration page shows provider cards and authentication flows only.

### `GET /api/social/status`

Returns capability and credential status for all providers.

```json
{
  "providers": {
    "telegram": { "label": "Telegram", "implemented": false, "enabled": true, "publisher": null },
    "vk": { "label": "VK", "implemented": false, "enabled": false, "publisher": null }
  }
}
```

### `GET /api/social/{provider}/status`

Same payload for one provider. Unknown providers return `404` with `code: unknown_provider`.

### `POST /api/social/publish` and `POST /api/social/{provider}/publish`

Validate and dispatch a publish request. Payload validation failures return `400` with
`code: invalid_payload`; unimplemented publishers return `501` with `code: not_implemented`.

The request contract is shared by both routes and includes `provider`, `target`, one to ten `assets`, and optional `text`. The path-selected route additionally verifies that the URL provider matches the payload provider.

### Telegram auth flow

`POST /api/social/telegram/auth/start`, `GET /api/social/telegram/auth/state`,
`GET /api/social/telegram/auth/qr.png`, `POST /api/social/telegram/auth/code`,
`POST /api/social/telegram/auth/password`, `POST /api/social/telegram/auth/cancel`, and
`POST /api/social/telegram/auth/disconnect` implement the phone/QR login sequence. They require
Telegram API credentials (`TELEGRAM_API_ID` / `TELEGRAM_API_HASH`).

### VK auth flow

`POST /api/social/vk/auth/start`, `GET /api/social/vk/auth/callback`, and
`POST /api/social/vk/auth/disconnect` handle the OAuth exchange. VK OAuth is limited to port `80`
on `localhost`, which the app cannot self-host.

---

## Data Models

### `ImageMetadata`

```json
{
  "file": "string",
  "path": "string",
  "format": "string | null",
  "size": "int[] | null",
  "mode": "string | null",
  "error": "string | null",
  "exif": "object | null",
  "prompt_parameters": "object | null",
  "workflow": "object | null",
  "prompt_api_json": "object | null",
  "workflow_ui_json": "object | null",
  "raw_parameters": "string | null"
}
```

### `ImageListItem`

```json
{
  "id": "int | null",
  "file_name": "string",
  "format": "string | null",
  "size": "int[] | null",
  "mode": "string | null",
  "error": "string | null",
  "thumbnail": "string | null",
  "file": "string | null",
  "path": "string | null",
  "rating": "int | null"
}
```

### `ImageDetail`

`ImageDetail` extends `ImageListItem` with:

```json
{
  "prompt_parameters": "object | null",
  "workflow": "object | null",
  "exif": "object | null",
  "raw_chunks": "object | null",
  "raw_parameters": "string | null",
  "raw_params": "string | null",
  "folder_id": "int | null"
}
```

### `ScanResponse`

```json
{
  "folder_id": "int",
  "folder": "FolderInfo | null",
  "page": "int",
  "per_page": "int",
  "total": "int",
  "images": "ImageListItem[]",
  "cached": "int",
  "processed": "int"
}
```
