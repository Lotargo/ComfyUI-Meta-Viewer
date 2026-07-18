# API Reference

> REST API reference for ComfyUI Meta Viewer.

Base URL: `http://localhost:7860`

The API is intentionally local-first and single-user oriented. Responses are JSON unless an endpoint explicitly returns image bytes.

---

## Table of Contents

- [Folders](#folders)
- [Scanning and Uploads](#scanning-and-uploads)
- [Images](#images)
- [Library and Albums](#library-and-albums)
- [Thumbnails and Originals](#thumbnails-and-originals)
- [Cutouts](#cutouts)
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

## Images

### `GET /api/images`

Returns a paginated folder, album, or global image list. Images from disabled sources are
omitted. `folder_id` and `album_id` are mutually exclusive.

**Query Parameters:**

| Parameter | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `folder_id` | int | -- | no | Folder ID to load |
| `album_id` | int | -- | no | Virtual album ID to load |
| `page` | int | `1` | no | Page number |
| `per_page` | int | `50` | no | Images per page |
| `sort_by` | string | `date` | no | `name`, `date`, `size`, or `type` |
| `sort_dir` | string | `desc` | no | `asc` or `desc` |
| `rating` | int | -- | no | Exact rating from `0` (unrated) through `5` |

**Response:**

```json
{
  "images": [
    {
      "id": 1,
      "file_name": "image.png",
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
