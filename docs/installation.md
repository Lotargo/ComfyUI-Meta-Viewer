# Installation

## Prerequisites

- **Python 3.10+** (3.12 recommended)
- **Poetry** package manager

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
| `COMFY_META_UPLOAD` | `.comfy_meta_uploads` | Upload/database directory |

### Command Line Flags

```bash
# Start without opening browser
poetry run python -m app.main --no-browser
```

## Directory Structure

After first run:

```
comfy-meta-viewer/
├── .comfy_meta_uploads/
│   └── meta.db          ← SQLite database
├── cache/
│   ├── thumbnails/      ← Generated JPEG thumbnails
│   └── cutouts/         ← Generated transparent PNGs
├── app/
│   ├── main.py
│   ├── database.py
│   ├── extractor.py
│   ├── cutout.py
│   ├── schemas.py
│   ├── templates/
│   └── static/
├── docs/
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
Close other instances of the app, or delete `.comfy_meta_uploads/meta.db` and restart.

**Thumbnails not loading:**
Delete `cache/thumbnails/` and restart. Thumbnails are auto-regenerated on request.
