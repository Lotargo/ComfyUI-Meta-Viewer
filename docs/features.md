# Features

> Feature overview for ComfyUI Meta Viewer.

ComfyUI Meta Viewer is a local-first metadata browser for AI-generated images. It focuses on practical workflows: scan a folder, inspect prompts/workflows, search across a library, and export useful image derivatives such as transparent cutouts.

---

## Table of Contents

- [Metadata Extraction](#metadata-extraction)
- [ComfyUI Workflow Inspection](#comfyui-workflow-inspection)
- [Source Monitoring](#source-monitoring)
- [SQLite Persistence](#sqlite-persistence)
- [Media Library](#media-library)
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
- [Index and Factory Reset](#index-and-factory-reset)
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

## Source Monitoring

**Main route:** `POST /api/scan`

Source monitoring indexes images in-place. Original files are not copied during a scan; the database stores metadata and references to their normalized absolute local paths. Cache and database files remain in application-owned directories rather than the selected source folder. This works with ordinary folders and directories synchronized by desktop clients such as OneDrive, Google Drive, Dropbox, Syncthing, or Яндекс Диск.

### Behavior

- Reads a local folder path.
- Creates or updates a folder row.
- Supports optional recursive subfolder scanning.
- Compares current file size and `mtime` with cached database rows.
- Reprocesses only new or changed files.
- Stores normalized metadata in SQLite.
- Returns the first paginated page of results.
- Uses native filesystem events for fast create/modify/rename/delete updates.
- Coalesces event bursts and waits for files to become stable before indexing.
- Runs periodic reconciliation to recover missed events and reconnect changes.
- Keeps indexed rows when a source becomes unavailable.
- Lets the user disable a source without deleting its rows, then reconciles on re-enable.

---

## SQLite Persistence

**Main file:** `app/database.py`

SQLite stores the local media index, folder list, embedded metadata JSON, upload BLOBs, user data, AI annotations, and cache-related references.

### Tables

| Table | Purpose |
|-------|---------|
| `folders` | Indexed local folders and the special `Uploads` collection |
| `images` | Legacy-named shared asset rows for images and videos, technical fields, embedded metadata, AI annotations, and uploaded media BLOBs |
| `albums` / `album_images` | Virtual many-to-many collections and cover selection |
| `tags` / `image_tags` | Normalized user tags attached to indexed assets |

### Notes

- WAL mode is enabled for better local read/write behavior.
- Foreign keys are enabled.
- Folder deletion removes related image rows.
- Uploaded images are categorized by a lightweight PNG/JPEG/WebP generation-marker probe and stored as `original_data` BLOBs without eager metadata extraction.
- Uploaded videos are stored as `original_data` BLOBs; technical metadata and a JPEG poster are prepared during import when ffprobe/ffmpeg are available.
- Scanned images remain on disk and are served from their original local paths.
- Uploaded metadata is extracted and cached when the image is first opened.
- Content fingerprints let a unique rename retain the same image ID and virtual relations.
- `media_type` and `mime_type` identify every asset; video rows add duration, frame rate, codec, and preview status.
- Embedded source metadata stays in `metadata_json`, user data stays in relational fields, and derived AI results stay in `ai_annotations_json`.

---

## Media Library

**Page:** `/library`

**Main files:** `app/library.py`, `app/static/js/library.js`

The Library is a separate page for organizing indexed assets without changing their source
directories. One asset can belong to multiple albums and can independently carry a favorite
flag, zero-to-five-star rating, tags, and a note.

### Capabilities

- Create, rename, and delete virtual albums.
- Add or remove many selected assets at once.
- Set a member asset as the album cover.
- Favorite, rate, tag, and annotate assets.
- Filter through system collections: Favorites, Without metadata, Recently added,
  Unavailable, Images, Videos, and Not rated.
- Search names, notes, and tags; sort by name, file date, indexed date, size, or rating.
- Keep album and favorite relations while a source is disabled or temporarily unavailable.
- Preserve the indexed identity across an unambiguous content-matched file rename.
- Browse MP4, WebM, MOV, M4V, MKV, and AVI files alongside images, including preview frames and a basic video preview.

Removing an asset from an album changes only the album membership. Removing it from the
index also clears its virtual relations and generated caches, but still leaves the physical
file untouched. A remaining file can be discovered again during source reconciliation.
Explicit physical deletion moves supported local files to the operating system Trash or Recycle Bin.

### Video indexing

The source scanner recognizes images and videos as the same asset entity. `ffprobe` reads
container and stream metadata; `ffmpeg` decodes one bounded JPEG preview frame. Both tools are
optional. A missing tool produces `unavailable` metadata/preview state on the video card and
does not stop the worker or affect image indexing.

### Viewer Media sidebar

The Viewer sidebar uses one `Media` tab for the global asset stream. Images and videos are
enabled by default; a checkbox filter can show only images or only videos, and the selection
is persisted with the other UI preferences. The same filter is applied to the open central
folder or album. At least one type must remain enabled. Video items carry a visible badge and
open in the same lightbox with native playback and technical metadata, while image-only
workflow and cutout behavior remains unchanged.

---

## Gallery View

**Main file:** `app/static/js/gallery.js`

The gallery provides a visual browsing mode for indexed images and videos in the selected
folder or album.

### Capabilities

- Masonry-style layout.
- Lazy image thumbnails and video poster frames, with a video placeholder when no poster is available.
- Infinite scrolling through paginated results.
- List/gallery switching.
- Quick preview through the lightbox flow.
- Media context menu for opening/copying the original and local-file actions; cutout remains image-only.

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
- The same media context menu used by gallery cards and Library previews.

### Media Context Menu

Right-clicking an indexed image or video in Viewer or Library exposes a compact shared menu:

- Open a gallery or sidebar asset in the fullscreen Viewer.
- Open the original in a new tab.
- Download the untouched original.
- Copy the filename or resolved local file path.
- Copy images to the system clipboard as PNG; this image-only action is hidden for videos.
- Show a scanned source in the operating system's file manager.
- Rename an available file through a modal while keeping its extension unchanged.
- Copy positive/negative prompts and workflow JSON when present.
- Set or clear a 1–5 star rating without leaving the current view.
- Create a transparent PNG cutout directly from Viewer for images only.
- Remove an image or video from the index while keeping a scanned physical source.
- Delete a physical image or video from any Viewer context menu by moving it to the
  operating system's Recycle Bin or Trash.

Viewer can filter folders, albums, and the global Images feed by an exact rating or show
only unrated images. The selected rating filter is retained with the other local viewer
preferences and applies to subsequent pages as they load.

Library additionally provides contextual organization actions: toggle favorite, add to an
album through a submenu, and edit asset details. `Delete file from computer` is separate
from `Remove from index`: it moves a physical source file to the system Recycle Bin or
Trash and removes its index entry without an additional confirmation dialog. For originals
uploaded into the app, the destructive index action is labeled
`Delete uploaded asset` and explicitly warns that the stored original will be removed.

Physical-path actions are disabled for uploaded originals stored inside the app and for
unavailable sources.

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
| `←` / `→` | Navigate visible media |
| `Enter` | Open lightbox |
| `Escape` | Close lightbox or active panel |
| `Delete` | Move the current fullscreen file or selected Library files to the system Recycle Bin / Trash |
| `Ctrl+F` | Focus/open search |
| `G` | Toggle gallery/list view |
| `?` | Open Help Center |
| `1` / `2` / `3` | Switch metadata tabs |
| `D` | Toggle metadata panel |
| `S` | Toggle sidebar |

---

## Resizable Sidebar

**Main file:** `app/static/js/features/sidebar.js`

The sidebar contains folder navigation, a unified media list, and pagination/infinite-scroll controls.

### Capabilities

- Resizable width.
- Folder browser.
- Image/video list with thumbnails, video badges, and media-type checkboxes.
- Delete actions.
- Infinite scroll sentinel.

---

## Persistent UI Preferences

**Main files:** `app/static/js/state.js`, `app/static/js/preferences.js`, `app/static/js/app.js`

Stable interface preferences survive reloads and browser restarts through a versioned `localStorage` document. The app restores the selected folder, main view, sidebar tab/width/collapsed state, media-type and rating filters, folder layout, sorting, search options, metadata tab, and lightbox metadata-panel visibility.

Every field is validated independently and the saved folder ID is checked against the server during startup. Runtime collections, pagination, open overlays, zoom/pan, scroll positions, and search text are intentionally never persisted.

---

## Drag-and-Drop Upload

**Main files:** `app/static/js/events.js`, `POST /api/upload`

The app supports adding images and videos through the browser UI.

### Supported Flows

- Drag and drop image or video files.
- File input upload.
- Folder drag-and-drop where supported by the browser.
- Local path extraction through the `/api/extract` flow.

Uploaded originals are stored immediately as SQLite BLOBs and can be served later through `/api/original/{asset_id}`. Image import checks known PNG text-chunk keys plus generation markers in JPEG/WebP EXIF, XMP, and comment blocks so it can separate `Uploads` from `Uploads (no metadata)`; image pixels and full metadata remain lazy. Video import accepts MP4, WebM, MOV, M4V, MKV, and AVI, extracts technical metadata with ffprobe, and caches a poster frame with ffmpeg. Without either tool, the original is still added and its corresponding status is marked `unavailable`.

---

## Thumbnails and Originals

**Main routes:** `GET /api/thumbnail/{image_id}`, `GET /api/preview/{image_id}`, `GET /api/original/{image_id}`

### Thumbnails

- Generated lazily.
- Stored as JPEG files under `cache/thumbnails/`.
- Served from cache on later requests.
- Video thumbnails are decoded by FFmpeg and report a clear `503` state when the tool is unavailable.

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

## Index and Factory Reset

**Main routes:** `POST /api/reset-index`, `POST /api/factory-reset`

Reset Index physically removes the SQLite database, WAL/SHM sidecars, thumbnails, previews,
and cutouts. It then creates a clean schema and reindexes active source directories saved in
the separate `config.json` file. This also removes virtual library organization and uploaded
originals stored inside SQLite.

Factory Reset is a separate, more destructive action. It additionally forgets saved source
directories and clears browser preferences after a successful reset. Both actions require
distinct confirmation tokens and neither action deletes files from scanned source folders.

If SQLite corruption prevents the web app from starting, the same operations are available
through `python -m app.main --reset-index` and `--factory-reset`.

---

## Responsive Design

The UI is built as a local desktop-first tool, but the CSS includes responsive rules for narrower screens. The main surfaces are:

- Sidebar.
- Gallery/list area.
- Lightbox.
- Metadata panel.
- Help/diagnostic panels.
