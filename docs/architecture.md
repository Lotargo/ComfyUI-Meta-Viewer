# Architecture

> ComfyUI Meta Viewer -- project architecture, data flow, and extension points.

## Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Sidebar  │  │ Gallery  │  │ Lightbox │  │  Meta Panel   │  │
│  │          │  │          │  │          │  │ Summary/WF/Raw│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Search  │  │ Cutout   │  │ Workflow │  │ Keyboard/Help │  │
│  │  (Fuse)  │  │  Panel   │  │  Graph   │  │   Center      │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API (JSON)
┌───────────────────────────┴─────────────────────────────────────┐
│                     Flask Backend (Python)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  main.py │  │database.py│ │extractor │  │   cutout.py   │  │
│  │  Routes  │  │  SQLite  │  │ Metadata │  │ BG Removal    │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │   SQLite Database     │
                │  ┌───────┐ ┌───────┐  │
                │  │folders│ │images │  │
                │  └───────┘ └───────┘  │
                │  ┌────────────────┐   │
                │  │    sessions    │   │
                │  └────────────────┘   │
                └───────────────────────┘
```

ComfyUI Meta Viewer is a local-first web application. The browser hosts a single-page interface, while the Flask backend exposes a small REST API for scanning folders, extracting metadata, serving thumbnails/previews/original images, and managing cached cutouts. SQLite stores the indexed metadata and folder state.

## Technology Stack

| Layer | Technology | Version | Purpose |
|------|------------|---------|---------|
| Backend | Python | 3.10+ | Server-side application logic |
| HTTP Framework | Flask | 3.1 | REST API and static file serving |
| Database | SQLite3 | Built-in | Metadata persistence |
| Validation | Pydantic | 2.x | Request and response models |
| Images | Pillow | 11.x | Metadata extraction, thumbnails, display previews, cutouts |
| Frontend | Vanilla JS | ES Modules | SPA without a frontend framework |
| CSS | Custom Properties | -- | Modular styling system |
| Search | Fuse.js | 7.x | Client-side fuzzy search |
| Dependencies | Poetry | -- | Python dependency management |

## Directory Structure

```
comfy-meta-viewer/
├── app/                          # Python backend + frontend static assets
│   ├── main.py                   # Flask app, API routes, startup wiring
│   ├── database.py               # SQLite CRUD and persistence helpers
│   ├── extractor.py              # Metadata parsing for PNG/JPG/WEBP/etc.
│   ├── cutout.py                 # Heuristic background removal
│   ├── schemas.py                # Pydantic request/response models
│   ├── static/
│   │   ├── css/                  # Modular CSS
│   │   │   ├── base/             # Variables, reset, typography
│   │   │   ├── layout/           # App shell, sidebar, content
│   │   │   ├── components/       # Buttons, cards, inputs, etc.
│   │   │   ├── features/         # Meta panel, workflow, gallery
│   │   │   └── utils/            # Responsive breakpoints
│   │   └── js/                   # Modular JavaScript
│   │       ├── app.js            # Entry point
│   │       ├── state.js          # Reactive store
│   │       ├── api.js            # HTTP client
│   │       ├── events.js         # DOM event handlers
│   │       ├── gallery.js        # Masonry layout
│   │       ├── lightbox.js       # Fullscreen viewer
│   │       ├── meta-view.js      # Metadata tabs
│   │       ├── sessions.js       # Session management
│   │       ├── utils.js          # Helpers
│   │       ├── components/       # Reusable UI components
│   │       ├── features/         # Feature modules
│   │       └── vendor/           # Third-party frontend dependencies
│   └── templates/
│       └── index.html            # SPA entry template
├── cache/
│   ├── thumbnails/               # JPEG thumbnails (*.jpg)
│   ├── previews/                 # Bounded JPEG/WebP lightbox previews
│   └── cutouts/                  # Transparent PNG cutouts (*.png)
├── .comfy_meta_uploads/
│   └── meta.db                   # SQLite database by default
├── dev_docs/                     # Internal development notes and sprint docs
├── docs/                         # Public documentation
├── pyproject.toml                # Poetry configuration
├── start.bat                     # Windows launcher
└── start.sh                      # Linux/macOS launcher
```

## Data Flow

### 1. Folder Scanning

```
User selects or drops a folder
       │
       ▼
  POST /api/scan {"path": "..."}
       │
       ▼
  database.py: upsert_folder()
       │
       ▼
  main.py: compare file mtimes with cached rows
       │
       ├──► Reuse unchanged rows
       │
       └──► For changed/new images:
             extractor.extract_metadata(path)
               ├──► PNG: read tEXt/iTXt chunks
               ├──► JPG/TIFF: read EXIF
               └──► Parse ComfyUI workflow JSON
       │
       ▼
  database.py: insert_images(rows)
       │
       ▼
  Return {folder_id, images, cached, processed, page}
```

The scanner works in-place: original files are not copied when a folder is indexed. The database stores metadata and file timestamps so unchanged files can be skipped on later scans.

### 2. Image Uploads

```
User drops image files
       │
       ▼
  POST /api/upload (multipart/form-data)
       │
       ▼
  extractor.py: probe container metadata only
       │
       ├──► PNG prompt/workflow/parameters → Uploads
       ├──► JPEG/WebP generation markers → Uploads
       └──► no known generation marker → Uploads (no metadata)
       │
       ▼
  database.py: store original_data BLOB + basic file fields
       │
       └──► Return {images: [...], folder_id}
```

Uploaded files are stored as BLOBs in SQLite without eager metadata extraction, while scanned folder images remain referenced by their original local paths. The upload probe recognizes known PNG text keys and generation-specific markers inside JPEG/WebP EXIF, XMP, and comment blocks. Ordinary camera EXIF alone does not classify an image as generated metadata. Duplicate uploaded names receive unique internal `rel_path` values so every original is retained.

### 3. Metadata Viewing

```
User clicks an image
       │
       ▼
  GET /api/images/{id}
       │
       ▼
  database.py: get_image_detail(id)
       │
       ├──► Ensure metadata exists
       │      ├──► Use cached metadata when present
       │      └──► Otherwise extract from the selected path/BLOB and cache it
       ├──► Deserialize metadata_json
       ├──► Attach prompt parameters
       ├──► Attach parsed workflow data
       └──► Return ImageDetail
```

The frontend renders the response in three main views: Summary, Workflow, and Raw metadata.

### 4. Thumbnail, Preview, and Original Image Serving

```
Browser requests thumbnail/preview/original
       │
       ├──► GET /api/thumbnail/{id}
       │      ├──► Return cached JPEG if present
       │      └──► Generate from original path or BLOB
       │
       ├──► GET /api/preview/{id}
       │      ├──► Return cached 4096px JPEG/WebP if present
       │      └──► Serialize one large preview generation at a time
       │
       └──► GET /api/original/{id}
              ├──► Stream uploaded BLOB in chunks
              └──► Stream the scanned file with range support
```

The lightbox displays the thumbnail immediately, then replaces it with a cached preview. The full original is never loaded into the lightbox automatically and is available through an explicit new-tab action. Thumbnails and previews are regenerated lazily when missing.

### 5. Cutout Generation

```
User clicks Cutout
       │
       ▼
  POST /api/cutout/{id}
       │
       ▼
  cutout.py: make_cutout_png()
       │
       ├──► Load source image from BLOB or local path
       ├──► Remove background with heuristic processing
       ├──► Save transparent PNG to cache/cutouts/
       └──► Return cutout URL
```

Cutouts are cached and can be deleted independently from the source image.

## Database Schema

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL DEFAULT '',
    scanned_at TEXT DEFAULT (datetime('now')),
    created_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    rel_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER DEFAULT 0,
    file_mtime REAL DEFAULT 0,
    format TEXT,
    width INTEGER DEFAULT 0,
    height INTEGER DEFAULT 0,
    mode TEXT,
    error TEXT,
    metadata_json TEXT,
    thumbnail_b64 TEXT,
    original_data BLOB,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(folder_id, rel_path)
);

CREATE INDEX idx_images_folder ON images(folder_id);
CREATE INDEX idx_images_folder_mtime ON images(folder_id, file_mtime);
```

The schema is intentionally small. The application stores rich metadata as JSON while keeping folder/image identity and pagination fields relational.

## Frontend Modules

### State Management (`state.js`)

```
state.js
  ├── images[]           -- current page/list of images
  ├── activeIndex        -- selected image index
  ├── sessions[]         -- available local sessions
  ├── currentSession     -- current session state
  ├── viewMode           -- 'list' | 'gallery'
  ├── folderId           -- active folder ID
  ├── folders[]          -- indexed folders
  ├── page / perPage     -- pagination state
  ├── hasMore            -- infinite-scroll flag
  └── isLoading          -- request/loading flag
```

State is persisted in `sessionStorage`, allowing the interface to recover after a page refresh.

### API Client (`api.js`)

```
api.js
  ├── scanFolder(path)           -- POST /api/scan
  ├── loadFromPaths(paths)       -- POST /api/extract
  ├── loadFromFiles(files)       -- POST /api/upload
  ├── loadMore()                 -- GET  /api/images?page=N
  ├── deleteImageAt(id)          -- DELETE /api/images/{id}
  ├── loadFolderImages(id)       -- GET  /api/images?folder_id=N
  ├── getFolders()               -- GET  /api/folders
  ├── deleteFolderFromServer(id) -- DELETE /api/folders/{id}
  ├── getCutout(id)              -- GET  /api/cutout/{id}
  ├── createCutout(id)           -- POST /api/cutout/{id}
  ├── deleteCutout(id)           -- DELETE /api/cutout/{id}
  └── getThumbnail(id)           -- GET  /api/thumbnail/{id}
```

### Feature Modules

| Module | File | Description |
|--------|------|-------------|
| Sidebar | `features/sidebar.js` | Resizable sidebar, image list, folder browser |
| Workflow Graph | `features/workflow-graph.js` | SVG visualization of ComfyUI node graphs |
| Keyboard | `features/keyboard.js` | 14 shortcuts + Help Center |
| Cutout | `features/cutout.js` | Background-removal panel |
| Gallery | `gallery.js` | Masonry layout + lazy loading |
| Lightbox | `lightbox.js` | Fullscreen viewer + cursor zoom/pan/rotate |
| Meta View | `meta-view.js` | 3 tabs: Summary, Workflow, Raw |
| Search | `components/search-bar.js` | Fuse.js fuzzy search |

## Security Model

- The app is designed as a local single-user tool.
- No authentication layer is included by default.
- The Flask server binds to `127.0.0.1` in the default launcher.
- Uploaded originals are stored as SQLite BLOBs.
- Uploaded metadata is extracted lazily when an image is opened.
- Scanned folder files are not copied; only metadata and file references are stored.
- Thumbnail, display preview, and cutout caches are stored on disk.

## Extensibility

- **New image formats:** add parsing support in `extractor.py`.
- **New API endpoints:** add a Flask route in `main.py`, a Pydantic model in `schemas.py`, and a client wrapper in `api.js`.
- **New frontend features:** create a module in `app/static/js/features/` and matching styles in `app/static/css/features/`.
- **New UI components:** add reusable JavaScript/CSS modules under `components/`.
