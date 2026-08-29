# Installation

## Prerequisites

- **Python 3.10+** (3.12 recommended)
- **Poetry** package manager
- **FFmpeg / ffprobe** (optional, for video technical metadata and preview frames)

Images and the rest of the library continue to work when FFmpeg is absent. Video cards remain
indexed and explain that preview or technical metadata is unavailable. Install both executables
on `PATH` to enable those features; see the official [FFmpeg download page](https://ffmpeg.org/download.html).

## Quick Start

### Windows

```bash
# Clone or download the project
cd comfy-meta-viewer

# Run (installs dependencies automatically)
start.bat
```

### Linux / macOS

```bash
cd comfy-meta-viewer
chmod +x start.sh
./start.sh
```

### Manual

```bash
# Install dependencies
poetry install --no-root

# Start the server
poetry run python -m app.main
```

The app opens at `http://127.0.0.1:7860`.

## Configuration

### Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `COMFY_META_PORT` | `7860` | Server port |
| `COMFY_META_DATA_DIR` | `.comfy_meta_uploads` | Database/application data directory |
| `COMFY_META_CACHE_DIR` | `cache` | Generated cache directory |
| `COMFY_META_UPLOAD` | — | Legacy alias for `COMFY_META_DATA_DIR` |

Relative data and cache overrides are resolved from the project root, so launching the
application from another working directory does not create data in an unexpected location.

### Command Line Flags

```bash
# Start without opening browser
poetry run python -m app.main --no-browser

# Recreate a corrupt or stale local index
poetry run python -m app.main --reset-index

# Also forget saved source folders
poetry run python -m app.main --factory-reset
```

## Directory Structure

After first run:

```
comfy-meta-viewer/
├── .comfy_meta_uploads/
│   ├── config.json      <- Saved source folders
│   └── meta.db          <- Disposable SQLite index
├── cache/
│   ├── thumbnails/      <- Generated JPEG thumbnails
│   ├── previews/        <- Generated high-res display previews
│   └── cutouts/         <- Generated transparent PNGs
├── app/
│   ├── main.py          <- Flask application and routes
│   ├── database.py      <- SQLite persistence and schemas
│   ├── library.py       <- Virtual albums, favorites, filters
│   ├── extractor.py     <- Metadata parsing (PNG/EXIF/ComfyUI)
│   ├── cutout.py        <- Background removal
│   ├── schemas.py       <- Pydantic request/response models
│   ├── source_monitor.py<- Source observation and reconciliation
│   ├── ai/              <- AI prompt compilation, adapters, and jobs
│   ├── comfyui/         <- ComfyUI runtime and workflow editor
│   ├── templates/       <- HTML templates
│   └── static/          <- Frontend JS/CSS assets
├── dev_docs/            <- Internal technical specifications and roadmap
├── docs/                <- Technical documentation
├── site/                <- Public website and interactive Scalar API portal
├── pyproject.toml
├── start.bat
└── start.sh
```

## Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| Flask | ^3.1 | Web server |
| Pillow | ^11.0 | Image processing, metadata extraction |
| Pydantic | ^2.0 | Data validation, API schemas |
| FFmpeg / ffprobe | optional | Video preview frames and technical metadata |
| Fuse.js | 7.0.0 | Client-side fuzzy search (vendored) |

## Troubleshooting

**Poetry not found:**
```bash
pip install poetry
```

**Port already in use:**
```bash
COMFY_META_PORT=7861 poetry run python -m app.main
```

**Database locked:**
Close other instances of the app, then run `poetry run python -m app.main --reset-index`.
The command reports the exact file if the database, WAL, SHM, or cache remains locked.

**Database corrupt / app does not start:**
Run `poetry run python -m app.main --reset-index`. This command does not need to open the
existing database before removing it and retains source paths previously saved in
`.comfy_meta_uploads/config.json`.

**Thumbnails not loading:**
Delete `cache/thumbnails/` and restart. Thumbnails are auto-regenerated on request.
