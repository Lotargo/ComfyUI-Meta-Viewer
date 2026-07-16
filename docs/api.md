# API Reference

> REST API reference for ComfyUI Meta Viewer.

Base URL: `http://localhost:7860`

The API is intentionally local-first and single-user oriented. Responses are JSON unless an endpoint explicitly returns image bytes.

---

## Table of Contents

- [Folders](#folders)
- [Scanning and Uploads](#scanning-and-uploads)
- [Images](#images)
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
      "image_count": 42
    }
  ]
}
```

---

### `DELETE /api/folders/{folder_id}`

Deletes a folder record and all related image rows.

**Response:**

```json
{ "ok": true }
```

---

## Scanning and Uploads

### `POST /api/scan`

Scans a local folder in-place. Existing rows are reused when the file `mtime` did not change.

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
      "path": null
    }
  ],
  "cached": 40,
  "processed": 2
}
```

**Behavior:**

- Scans files in the selected folder.
- Supports `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`, and `.tif` when supported by the parser.
- Skips unchanged files using stored `mtime` values.
- Stores metadata in SQLite.
- Returns the first paginated page of indexed images.

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

Uploads image files through `multipart/form-data`. Uploaded originals are stored as SQLite BLOBs. A lightweight format-aware probe checks PNG text keys and JPEG/WebP EXIF, XMP, or comment blocks to place each file in `Uploads` or `Uploads (no metadata)`. It does not decode image pixels or create a preview. Full metadata extraction is deferred until `GET /api/images/{image_id}` is called.

**Request:** `multipart/form-data` with one or more `files` fields.

**Response:**

```json
{
  "images": [
    {
      "id": 1,
      "folder_id": 1,
      "file_name": "uploaded.png",
      "file_size": 123456
    }
  ],
  "count": 1,
  "folder_id": 1
}
```

---

## Images

### `GET /api/images`

Returns a paginated list of images for a folder.

**Query Parameters:**

| Parameter | Type | Default | Required | Description |
|----------|------|---------|----------|-------------|
| `folder_id` | int | -- | yes | Folder ID to load |
| `page` | int | `1` | no | Page number |
| `per_page` | int | `50` | no | Images per page |

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
      "path": null
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

Deletes an image row and clears related thumbnail/cutout cache files.

**Response:**

```json
{ "ok": true }
```

---

## Thumbnails and Originals

### `GET /api/thumbnail/{image_id}`

Returns a JPEG thumbnail. If the cached file is missing, the thumbnail is generated lazily from the uploaded BLOB or original scanned file.

**Response:** `image/jpeg`

---

### `GET /api/original/{image_id}`

Returns the original image bytes. Uploaded files are served from SQLite BLOB storage; scanned files are read from their original local path.

**Response:** `image/png`, `image/jpeg`, `image/webp`, `image/bmp`, `image/tiff`, or `application/octet-stream`.

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

### `POST /api/reset`

Clears the SQLite database and thumbnail/cutout caches.

**Response:**

```json
{ "ok": true }
```

---

### `GET /api/diagnostics`

Returns local diagnostics and cache statistics.

**Response:**

```json
{
  "db_path": ".comfy_meta_uploads/meta.db",
  "folders": 3,
  "images": 150,
  "uploads": 12,
  "thumbnail_dir": "cache/thumbnails",
  "thumbnail_count": 138,
  "cutout_dir": "cache/cutouts",
  "cutout_count": 5,
  "upload_dir": ".comfy_meta_uploads"
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
  "path": "string | null"
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
