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
- [Display Preview Cache](#display-preview-cache)
- [Cutout Cache](#cutout-cache)
- [CLI Flags](#cli-flags)

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_META_PORT` | `7860` | HTTP server port |
| `COMFY_META_DATA_DIR` | `.comfy_meta_uploads` | Directory for the SQLite database and application data |
| `COMFY_META_CACHE_DIR` | `cache` | Directory for thumbnails, previews, and cutouts |
| `COMFY_META_UPLOAD` | — | Backward-compatible alias for `COMFY_META_DATA_DIR` |

### Examples

```bash
# Windows CMD
set COMFY_META_PORT=8080
set COMFY_META_DATA_DIR=D:\my_data
set COMFY_META_CACHE_DIR=D:\my_cache
start.bat

# Linux/macOS
COMFY_META_PORT=8080 COMFY_META_DATA_DIR=/data/comfy-meta ./start.sh

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
│   ├── config.json                # Saved source directories
│   └── meta.db                    # Disposable SQLite index
├── cache/
│   ├── thumbnails/
│   │   ├── 1.jpg                  # JPEG thumbnails
│   │   └── ...
│   ├── previews/
│   │   ├── 1-<version>-4096.jpg   # Opaque lightbox previews
│   │   └── 2-<version>-4096.webp  # Transparent lightbox previews
│   └── cutouts/
│       ├── 1.png                  # Transparent PNG cutouts
│       └── ...
└── .venv/                         # Poetry virtualenv when configured in-project
```

### Description

| Path | Contents | Reset Index | Factory Reset |
|------|----------|-------------|---------------|
| `.comfy_meta_uploads/config.json` | Source paths, names, enabled flags, and recursion settings | preserved | deleted |
| `.comfy_meta_uploads/meta.db` | Disposable SQLite index, virtual library data, and uploaded BLOBs | recreated | recreated |
| `.comfy_meta_uploads/meta.db-wal` / `-shm` | SQLite WAL sidecars | deleted | deleted |
| `cache/thumbnails/` | Generated JPEG thumbnails | cleared | cleared |
| `cache/previews/` | Generated lightbox previews up to 4096 px | cleared | cleared |
| `cache/cutouts/` | Generated transparent PNG cutouts | cleared | cleared |

All default and relative service paths are anchored to the project root rather than the
process working directory. Absolute Windows drive and UNC paths, Linux paths, and macOS
paths are handled by the native `pathlib` implementation on each operating system.

Folder paths selected for scanning are expanded, normalized to an absolute native path,
and checked before they are saved. The application indexes source files in place and does
not create cache files, marker files, or watcher scripts inside a selected source folder.
If the system folder dialog is unavailable (for example, Tk is missing in a minimal Linux
environment), the web interface asks for the path manually.

Scanned folder media is not copied. The database stores embedded metadata, local path
references, albums, favorites, ratings, tags, and notes. Uploaded files are stored as BLOBs
in SQLite; their metadata is extracted only when an image is first opened. Because virtual
library organization and uploaded originals live inside the disposable index, both reset
operations permanently remove them. Source files in scanned directories are never deleted.

Enabled sources use native filesystem events plus a periodic five-minute reconciliation.
Bursts are debounced and two filesystem snapshots must agree before changed files enter the
metadata queue. Missing roots are retried without treating their indexed contents as deleted.

---

## Supported File Extensions

| Extension | Metadata Support | Notes |
|-----------|------------------|-------|
| `.png` | Full | PNG `tEXt` / `iTXt` chunks and ComfyUI workflow JSON |
| `.jpg` | EXIF/XMP | Generation parameters in UserComment, XMP, and comment blocks |
| `.jpeg` | EXIF/XMP | Generation parameters in UserComment, XMP, and comment blocks |
| `.webp` | EXIF/XMP | Generation parameters in EXIF and XMP container chunks |
| `.bmp` | Dimensions only | No rich ComfyUI metadata expected |
| `.tiff` | Basic/EXIF | EXIF when available |
| `.tif` | Basic/EXIF | Served as TIFF by the API MIME map |
| `.mp4`, `.m4v`, `.mov` | ffprobe | Video stream/container metadata; JPEG preview via ffmpeg |
| `.webm`, `.mkv`, `.avi` | ffprobe | Video stream/container metadata; JPEG preview via ffmpeg |

Folder scans filter by supported extensions case-insensitively. FFmpeg and ffprobe are optional:
without them video rows remain available for albums, favorites, filtering, and original-file
access while their technical metadata or preview status is marked `unavailable`.

---

## SQLite Settings

The application enables:

- **WAL mode** for better local read/write behavior.
- **Foreign keys** for relational integrity.
- **Folder/image indexes** for pagination and incremental scan checks.

Relevant indexes:

```sql
idx_images_folder        -- Folder-based asset listing (legacy table name)
idx_images_folder_mtime  -- Incremental scan checks
idx_images_media_type    -- Image/video collection filtering
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

## Display Preview Cache

| Setting | Value |
|---------|-------|
| Maximum side | 4096 pixels |
| Format | JPEG for opaque images, WebP for transparency |
| Path | `cache/previews/{image_id}-{source_version}-4096.{ext}` |
| Generation | Lazy, after the lightbox thumbnail is visible |
| Concurrency | One uncached preview generation at a time |

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
python -m app.main [--no-browser | --reset-index | --factory-reset]
```

| Flag | Description |
|------|-------------|
| `--no-browser` | Start the server without automatically opening the browser |
| `--reset-index` | Physically recreate SQLite and generated caches, preserving and reindexing saved sources |
| `--factory-reset` | Recreate the index and caches and delete saved application configuration |

### Examples

```bash
# Normal launch
poetry run python -m app.main

# Start without opening a browser
poetry run python -m app.main --no-browser

# Recover even when a corrupt database prevents the web interface from starting
poetry run python -m app.main --reset-index

# Remove saved sources as well as the disposable index
poetry run python -m app.main --factory-reset

# Windows launcher
start.bat
```
