# Features

> Feature overview for ComfyUI Meta Viewer.

ComfyUI Meta Viewer is a local-first metadata browser for AI-generated images. It focuses on practical workflows: scan a folder, inspect prompts/workflows, search across a library, and export useful image derivatives such as transparent cutouts.

---

## Table of Contents

- [Metadata Extraction](#metadata-extraction)
- [ComfyUI Workflow Inspection](#comfyui-workflow-inspection)
- [Folder Scanning](#folder-scanning)
- [SQLite Persistence](#sqlite-persistence)
- [Gallery View](#gallery-view)
- [Lightbox](#lightbox)
- [Fuzzy Search](#fuzzy-search)
- [Object Cutout](#object-cutout)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Resizable Sidebar](#resizable-sidebar)
- [Persistent UI Preferences](#persistent-ui-preferences)
- [Drag-and-Drop Upload](#drag-and-drop-upload)
- [Thumbnails and Originals](#thumbnails-and-originals)
- [Diagnostics](#diagnostics)
- [Hard Reset](#hard-reset)
- [Responsive Design](#responsive-design)

---

## Metadata Extraction

**Main file:** `app/extractor.py`

The extractor reads image metadata and normalizes it into a Pydantic model used by both the REST API and the frontend.

### Supported Formats

| Format | Metadata Source | Support Level |
|--------|-----------------|---------------|
| PNG | `tEXt` / `iTXt` chunks, ComfyUI JSON | Full |
| JPEG/JPG | EXIF and general image metadata | Basic |
| WEBP | Pillow-dependent metadata | Basic |
| BMP | Dimensions and image mode | Basic |
| TIFF/TIF | EXIF when available | Basic |

### Extracted Data

| Category | Examples |
|----------|----------|
| Prompts | Positive prompt, negative prompt, raw parameter text |
| Generation settings | Steps, sampler, schedule, CFG, seed, model, VAE, denoise |
| Workflow | ComfyUI API prompt JSON and UI workflow JSON |
| Node summary | Model, prompt, sampler, image settings, LoRA, post-processing nodes |
| EXIF | Camera/image metadata when present |
| Raw data | Original text chunks and raw parameter strings |

---

## ComfyUI Workflow Inspection

**Main file:** `app/static/js/features/workflow-graph.js`

The Workflow tab renders parsed ComfyUI nodes as an SVG graph and groups known node types into readable categories.

### Capabilities

- Interactive SVG node graph.
- Color-coded node categories.
- Pan/zoom navigation.
- Node selection and parameter inspection.
- Support for both ComfyUI API-style prompt JSON and UI workflow JSON where available.

### Node Categories

| Category | Examples |
|----------|----------|
| Models | `CheckpointLoaderSimple`, `UNETLoader`, `VAELoader`, `CLIPLoader` |
| Prompts | `CLIPTextEncode`, `CLIPTextEncodeSDXL`, `CLIPTextEncodeFlux` |
| Sampler | `KSampler`, `KSamplerAdvanced`, `SamplerCustom`, schedulers |
| Image Settings | Latent/image size and scaling nodes |
| Post Processing | Decode, encode, save, preview, composite nodes |
| LoRA | `LoraLoader`, `LoraLoaderModelOnly` |
| Other | Nodes not covered by the known classifier |

---

## Folder Scanning

**Main route:** `POST /api/scan`

Folder scanning indexes images in-place. Original files are not copied during a scan; the database stores metadata and references to their local paths.

### Behavior

- Reads a local folder path.
- Creates or updates a folder row.
- Compares current file `mtime` values with cached database rows.
- Reprocesses only new or changed files.
- Stores normalized metadata in SQLite.
- Returns the first paginated page of results.

---

## SQLite Persistence

**Main file:** `app/database.py`

SQLite stores the local image index, folder list, metadata JSON, upload BLOBs, and cache-related references.

### Tables

| Table | Purpose |
|-------|---------|
| `folders` | Indexed local folders and the special `Uploads` collection |
| `images` | Image rows, metadata JSON, thumbnails, uploaded BLOBs |

### Notes

- WAL mode is enabled for better local read/write behavior.
- Foreign keys are enabled.
- Folder deletion removes related image rows.
- Uploaded images are categorized by a lightweight PNG/JPEG/WebP generation-marker probe and stored as `original_data` BLOBs without eager metadata extraction.
- Scanned images remain on disk and are served from their original local paths.
- Uploaded metadata is extracted and cached when the image is first opened.

---

## Gallery View

**Main file:** `app/static/js/gallery.js`

The gallery provides a visual browsing mode for indexed images.

### Capabilities

- Masonry-style layout.
- Lazy thumbnail loading.
- Infinite scrolling through paginated results.
- List/gallery switching.
- Quick preview through the lightbox flow.

---

## Lightbox

**Main file:** `app/static/js/lightbox.js`

The lightbox is the main inspection surface for a selected image.

### Capabilities

- Fullscreen-style image viewing.
- Previous/next navigation.
- Cursor-centered mouse-wheel zoom and rotation controls.
- Click-and-drag panning while the image is larger than the viewport.
- Immediate thumbnail display followed by a cached preview up to 4096 px.
- Explicit `View Original` action that opens the untouched source in a new tab.
- Metadata panel toggle.
- Summary, Workflow, and Raw metadata tabs.
- Touch-friendly navigation where supported by the browser.

---

## Fuzzy Search

**Main file:** `app/static/js/components/search-bar.js`

Search is handled client-side with Fuse.js, vendored under `app/static/js/vendor/` for offline local use.

### Typical Search Fields

- Filename.
- Format.
- Prompt text.
- Model/sampler fields when present in extracted metadata.

---

## Object Cutout

**Main files:** `app/cutout.py`, `app/static/js/features/cutout.js`

The cutout feature generates a transparent PNG from a selected image.

### Algorithm Overview

1. Load the source image from either an uploaded BLOB or a scanned file path.
2. Use alpha-channel information when available.
3. Estimate background from border pixels when needed.
4. Build a foreground mask using color distance.
5. Smooth the mask and save a transparent PNG.
6. Cache the generated cutout under `cache/cutouts/`.

### User Flow

- Open/select an image.
- Run cutout generation.
- Preview the transparent result.
- Download or delete the cached cutout.

---

## Keyboard Shortcuts

**Main file:** `app/static/js/features/keyboard.js`

Keyboard shortcuts are designed for fast browsing and metadata inspection.

| Key | Action |
|-----|--------|
| `←` / `→` | Navigate images |
| `Enter` | Open lightbox |
| `Escape` | Close lightbox or active panel |
| `Delete` | Delete selected image |
| `Ctrl+F` | Focus/open search |
| `G` | Toggle gallery/list view |
| `?` | Open Help Center |
| `1` / `2` / `3` | Switch metadata tabs |
| `D` | Toggle metadata panel |
| `S` | Toggle sidebar |

---

## Resizable Sidebar

**Main file:** `app/static/js/features/sidebar.js`

The sidebar contains folder navigation, image lists, and pagination/infinite-scroll controls.

### Capabilities

- Resizable width.
- Folder browser.
- Image list with thumbnails and metadata badges.
- Delete actions.
- Infinite scroll sentinel.

---

## Persistent UI Preferences

**Main files:** `app/static/js/state.js`, `app/static/js/preferences.js`, `app/static/js/app.js`

Stable interface preferences survive reloads and browser restarts through a versioned `localStorage` document. The app restores the selected folder, main view, sidebar tab/width/collapsed state, folder layout, sorting, search options, metadata tab, and lightbox metadata-panel visibility.

Every field is validated independently and the saved folder ID is checked against the server during startup. Runtime collections, pagination, open overlays, zoom/pan, scroll positions, and search text are intentionally never persisted.

---

## Drag-and-Drop Upload

**Main files:** `app/static/js/events.js`, `POST /api/upload`

The app supports adding images through the browser UI.

### Supported Flows

- Drag and drop image files.
- File input upload.
- Folder drag-and-drop where supported by the browser.
- Local path extraction through the `/api/extract` flow.

Uploaded originals are stored immediately as SQLite BLOBs and can be served later through `/api/original/{image_id}`. Import checks known PNG text-chunk keys plus generation markers in JPEG/WebP EXIF, XMP, and comment blocks so it can separate `Uploads` from `Uploads (no metadata)`. It does not decode pixels or create a base64 thumbnail. Full metadata is processed only when the image detail is opened.

---

## Thumbnails and Originals

**Main routes:** `GET /api/thumbnail/{image_id}`, `GET /api/preview/{image_id}`, `GET /api/original/{image_id}`

### Thumbnails

- Generated lazily.
- Stored as JPEG files under `cache/thumbnails/`.
- Served from cache on later requests.

### Display previews

- Generated lazily with a maximum side of 4096 pixels.
- Stored as JPEG for opaque images or WebP for transparent images.
- Loaded into the lightbox instead of the full-resolution source.
- Serialized so rapid navigation cannot start several high-memory resizes concurrently.

### Originals

- Uploaded images are streamed from SQLite BLOB storage in chunks.
- Scanned images are streamed from their original filesystem path with range support.
- The lightbox opens an original only through the explicit new-tab button or download action.

---

## Diagnostics

**Main route:** `GET /api/diagnostics`

Diagnostics expose basic local runtime information:

- Database path.
- Folder count.
- Image count.
- Uploaded image count.
- Thumbnail cache path/count.
- Preview cache path/count.
- Cutout cache path/count.
- Upload directory.

---

## Hard Reset

**Main route:** `POST /api/reset`

Hard reset clears:

- SQLite database tables.
- Thumbnail cache files.
- Cutout cache files.

It does not delete original scanned images from their source folders.

---

## Responsive Design

The UI is built as a local desktop-first tool, but the CSS includes responsive rules for narrower screens. The main surfaces are:

- Sidebar.
- Gallery/list area.
- Lightbox.
- Metadata panel.
- Help/diagnostic panels.
