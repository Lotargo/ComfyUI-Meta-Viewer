# Configuration

> Runtime configuration for ComfyUI Meta Viewer.

The application is designed to run locally with a small set of environment variables. Most users can run it with the defaults.

---

## Table of Contents

- [Environment Variables](#environment-variables)
- [Ports and Addresses](#ports-and-addresses)
- [Storage Paths](#storage-paths)
- [Supported File Extensions](#supported-file-extensions)
- [SQLite Settings](#sqlite-settings)
- [Thumbnail Cache](#thumbnail-cache)
- [Cutout Cache](#cutout-cache)
- [CLI Flags](#cli-flags)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_META_PORT` | `7860` | HTTP server port |
| `COMFY_META_UPLOAD` | `.comfy_meta_uploads` | Directory for uploaded originals and the SQLite database |

### Examples

```bash
# Windows CMD
set COMFY_META_PORT=8080
set COMFY_META_UPLOAD=D:\my_data
start.bat

# Linux/macOS
COMFY_META_PORT=8080 COMFY_META_UPLOAD=/data/comfy-meta ./start.sh

# Poetry run with a custom port
COMFY_META_PORT=8080 poetry run python -m app.main
```

---

## Ports and Addresses

| Resource | URL |
|----------|-----|
| Web UI | `http://localhost:7860` |
| API Base | `http://localhost:7860/api/` |
| Static files | `http://localhost:7860/static/` |

By default, the Flask server binds to `127.0.0.1`, so it is intended for local use rather than network exposure.

---

## Storage Paths

### Default Layout

```
ComfyUI-Meta-Viewer/
├── .comfy_meta_uploads/
│   └── meta.db                    # SQLite database
├── cache/
│   ├── thumbnails/
│   │   ├── 1.jpg                  # JPEG thumbnails
│   │   └── ...
│   └── cutouts/
│       ├── 1.png                  # Transparent PNG cutouts
│       └── ...
└── .venv/                         # Poetry virtualenv when configured in-project
```

### Description

| Path | Contents | Cleared by reset |
|------|----------|------------------|
| `.comfy_meta_uploads/meta.db` | SQLite database | yes |
| `cache/thumbnails/` | Generated JPEG thumbnails | yes |
| `cache/cutouts/` | Generated transparent PNG cutouts | yes |

Scanned folder images are not copied. The database stores their metadata and local path references. Uploaded files are stored as BLOBs in SQLite.

---

## Supported File Extensions

| Extension | Metadata Support | Notes |
|-----------|------------------|-------|
| `.png` | Full | PNG `tEXt` / `iTXt` chunks and ComfyUI workflow JSON |
| `.jpg` | Basic/EXIF | EXIF and common image metadata |
| `.jpeg` | Basic/EXIF | EXIF and common image metadata |
| `.webp` | Basic | Pillow-dependent metadata support |
| `.bmp` | Dimensions only | No rich ComfyUI metadata expected |
| `.tiff` | Basic/EXIF | EXIF when available |
| `.tif` | Basic/EXIF | Served as TIFF by the API MIME map |

Folder scans filter by supported extensions case-insensitively.

---

## SQLite Settings

The application enables:

- **WAL mode** for better local read/write behavior.
- **Foreign keys** for relational integrity.
- **Folder/image indexes** for pagination and incremental scan checks.

Relevant indexes:

```sql
idx_images_folder        -- Folder-based image listing
idx_images_folder_mtime  -- Incremental scan checks
```

---

## Thumbnail Cache

| Setting | Value |
|---------|-------|
| Format | JPEG |
| Quality | Implementation-defined by Pillow helper |
| Path | `cache/thumbnails/{image_id}.jpg` |
| Generation | Lazy, on first thumbnail request |
| Source | Uploaded BLOB or original scanned file path |

---

## Cutout Cache

| Setting | Value |
|---------|-------|
| Format | PNG (RGBA) |
| Path | `cache/cutouts/{image_id}.png` |
| Generation | On `POST /api/cutout/{image_id}` |
| Caching | Persistent until deleted/reset |
| Algorithm | Alpha channel handling + background estimation heuristic |

---

## CLI Flags

```bash
python -m app.main [--no-browser]
```

| Flag | Description |
|------|-------------|
| `--no-browser` | Start the server without automatically opening the browser |

### Examples

```bash
# Normal launch
poetry run python -m app.main

# Start without opening a browser
poetry run python -m app.main --no-browser

# Windows launcher
start.bat
```
