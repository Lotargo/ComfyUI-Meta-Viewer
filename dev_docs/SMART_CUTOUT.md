# Smart Cutout: Interactive Object Extraction

## Status

Planned feature. This document defines the replacement for the current cutout implementation.

## Product goal

Smart Cutout must provide a simple object-extraction workflow similar to modern mobile photo viewers:

1. Open an image.
2. Activate Smart Cutout.
3. Double-click or double-tap the desired object.
4. The model identifies that object and displays its mask.
5. Confirm the selection and save a transparent PNG.

The feature is intended primarily for extracting characters and other useful assets from ComfyUI-generated images without requiring a Photoshop-style editor.

## Mandatory replacement of the current implementation

The existing cutout implementation must be removed completely. It must not remain as a fallback, alternative mode, compatibility option, or hidden legacy path.

The following behavior must be deleted:

- estimating the background color from border pixels;
- generating a mask from color difference;
- threshold-based foreground detection;
- mask expansion, contraction, and blur used to imitate background removal;
- automatic reuse of an existing alpha channel as a completed cutout;
- the current server-side `make_cutout_png()` generation flow;
- the current behavior where opening the Cutout panel immediately generates a mask;
- the old `cache/cutouts` output cache and its image-ID-only cache naming.

The implementation currently located in `app/cutout.py`, including `estimate_background_color()`, `make_foreground_mask()`, and the existing mask-generation path, must be deleted rather than adapted.

Old cached cutouts must not be migrated into the new asset library. They are temporary results produced by the obsolete algorithm and may be removed during migration or startup cleanup.

## Non-goals

Smart Cutout is not intended to become a full image editor.

The first implementation must not include:

- Photoshop-style layers;
- freehand painting tools;
- clone stamp, text, shapes, or photo filters;
- a full manual mask editor;
- server-side ML inference;
- automatic background removal without an object prompt;
- preservation of the legacy heuristic algorithm.

Small interaction improvements, such as positive and negative correction points, are allowed when they directly improve object selection.

## Segmentation approach

Use promptable object segmentation in the browser through ONNX Runtime Web.

Candidate models:

- MobileSAM;
- EfficientSAM-Ti.

The final model must be selected through a small benchmark on representative ComfyUI images rather than by model size alone. The benchmark set should include anime characters, realistic people, complex backgrounds, multiple nearby subjects, hair, thin accessories, objects touching image borders, and partially occluded characters.

### Split encoder and decoder

The model pipeline must be divided into two sessions:

- **image encoder**: runs once when an image is prepared for Smart Cutout;
- **prompt decoder**: runs after each user point and returns candidate masks.

This separation is required for responsive interaction. Re-running the full model after every click is not acceptable.

### Execution providers

Preferred execution order:

1. WebGPU;
2. WebAssembly fallback.

Failure to initialize WebGPU must not break the feature. The application should transparently retry with WASM and expose the active backend in diagnostics or status text.

### Worker isolation

All ONNX Runtime Web sessions and tensor processing must run in a dedicated Web Worker.

The main UI thread is responsible only for:

- pointer and touch input;
- coordinate transformation;
- mask overlay rendering;
- selection status;
- confirmation and export controls.

The worker is responsible for:

- image preprocessing;
- encoder inference;
- embedding storage;
- decoder inference;
- candidate-mask scoring;
- conversion of the selected tensor into a transferable mask bitmap or pixel buffer.

## User interaction

### Primary flow

1. The user opens an image in the lightbox.
2. Smart Cutout begins preparing the image embedding.
3. The interface shows a non-blocking preparation state.
4. When ready, the user double-clicks or double-taps inside the desired object.
5. The click is sent as a positive point prompt.
6. The best candidate mask is rendered as a translucent overlay with an outline.
7. The user confirms the result.
8. A transparent PNG is generated and persisted in the dedicated Cutouts folder.

The initial version should keep the visible controls minimal:

- Save cutout;
- Select another object;
- Cancel.

### Optional correction interaction

The architecture should allow later support for:

- click to add another positive point;
- Alt-click or a dedicated Remove mode to add a negative point;
- switching between alternative masks when confidence scores are close.

These corrections must remain secondary to the main double-click workflow.

### Coordinate handling

Pointer coordinates must be transformed through all display stages:

1. browser viewport coordinates;
2. rendered image bounds;
3. zoom, pan, and rotation state;
4. original-image coordinates;
5. resized and padded model-input coordinates.

Using raw `offsetX` and `offsetY` without accounting for image fitting and transforms is not acceptable.

## Browser-side rendering and export

The original image and predicted mask should be composed in the browser with Canvas or OffscreenCanvas.

The generated PNG must:

- preserve the original visible RGB pixels;
- use the predicted mask as the alpha channel;
- retain partial alpha values when the model provides them;
- contain a genuinely transparent background;
- be generated from the original-resolution image, not from the lightbox preview.

The final Blob is then uploaded to the local Flask application for persistent storage.

## Model and embedding caching

### Model files

ONNX files must use versioned or content-hashed URLs and long-lived immutable browser caching.

Model files must not inherit the current `no-store` policy used for ordinary static development assets.

Example:

```text
/models/mobile-sam/encoder.int8.<hash>.onnx
/models/mobile-sam/decoder.int8.<hash>.onnx
```

### Embeddings

Image embeddings are runtime data and should initially remain in memory only.

Use a small LRU cache for the current image and a limited number of adjacent images. Embeddings must not be written into the image library or treated as user assets.

## Persistent Cutouts folder

All confirmed cutouts must be stored in a separate persistent application-managed folder.

The folder must not be located under `cache/`.

Recommended configuration:

```text
COMFY_META_CUTOUT_DIR=.comfy_meta_cutouts
```

On startup, the application must:

1. create the directory if it does not exist;
2. ensure a corresponding system-folder record exists in SQLite;
3. expose that folder in the Folders section of the sidebar under the visible name **Cutouts**.

The system folder should have a stable internal key, for example `cutouts`, so renaming the visible label does not break routing.

### File naming

Multiple objects may be extracted from the same source image. File names must therefore be collision-safe.

Recommended format:

```text
<source-stem>__cutout_<short-id>.png
```

Do not overwrite an earlier cutout when the user extracts another object from the same image.

## Strict gallery isolation

Cutouts are derived assets and must not be mixed with source images.

This is a mandatory product rule.

### Images tab

The Images tab in the sidebar must display source images only.

It must exclude every record whose asset type is `cutout`, regardless of creation date, active search query, pagination state, or source folder.

### Default central gallery

The normal central gallery must display source images only.

Saving a cutout must not append it to the active source-image array, increase the source-image count, or cause it to appear beside generated originals.

### Folders tab

The Folders section must include the dedicated **Cutouts** system folder.

Selecting this folder is the only normal navigation action that displays cutout assets in the central gallery.

When the Cutouts folder is selected:

- the central gallery displays cutouts only;
- source images are excluded;
- pagination and counts are calculated only for cutouts;
- folder-scoped search operates only on cutouts;
- opening a cutout shows derived-asset information rather than pretending it is an untouched ComfyUI generation.

Leaving the Cutouts folder returns the gallery to normal source-image behavior.

### Global search

Global source-image search must not return cutouts.

Cutouts may be searched only while the Cutouts folder is active. Their searchable fields should be limited to safe derived-asset data such as file name, source file name, and creation date.

## Metadata and provenance rules

A cutout is not an original ComfyUI generation. Its source prompt, tags, workflow, and generation parameters may no longer describe the visible result accurately.

Therefore:

- do not copy source prompts into the cutout's active prompt fields;
- do not copy source tags into the cutout's active tag fields;
- do not index cutouts in normal prompt, model, sampler, LoRA, or workflow search;
- do not count cutouts in statistics describing generated source images;
- do not display inherited source metadata as though it belongs directly to the cutout.

The application should preserve provenance separately:

- source image ID;
- source file name;
- source folder ID when available;
- extraction operation: `smart_cutout`;
- model identifier and model version;
- creation timestamp;
- optional selection-point data for diagnostics;
- output width and height.

The UI may provide a link such as **Open source image**, but provenance must remain distinct from generation metadata.

## Database changes

The exact migration may follow the existing schema style, but the data model must distinguish source images from derived cutouts.

Recommended fields:

### `folders`

```text
kind: source | system_cutouts
system_key: nullable stable identifier
```

### `images`

```text
asset_kind: source | cutout
source_image_id: nullable foreign key
operation: nullable string
operation_metadata_json: nullable JSON
```

Required behavior:

- existing records migrate to `asset_kind = source`;
- the Cutouts folder uses `kind = system_cutouts`;
- cutouts use `asset_kind = cutout`;
- deleting a source image must not silently delete saved cutouts;
- use `ON DELETE SET NULL` or equivalent provenance-preserving behavior;
- deleting a cutout removes its own file and database record only.

## API changes

Inference remains browser-side. The backend is responsible for persistence, browsing, and deletion.

Recommended endpoints:

```text
POST   /api/cutouts
GET    /api/cutouts/{id}
DELETE /api/cutouts/{id}
GET    /api/models/<model-file>
```

`POST /api/cutouts` should accept:

- transparent PNG Blob;
- source image ID;
- model ID and version;
- output dimensions;
- optional operation metadata.

The response should include:

- created cutout image ID;
- Cutouts folder ID;
- persistent image URL;
- file name;
- source-image reference when available.

The existing `POST /api/cutout/{image_id}` mask-generation endpoint must be removed rather than retained alongside the new flow.

The normal `/api/images` behavior must enforce source-only results unless the request explicitly targets the Cutouts system folder through normal folder navigation.

## Frontend structure

Recommended module layout:

```text
app/static/js/features/smart-cutout/
├── smart-cutout.js
├── smart-cutout-worker.js
├── model-session.js
├── image-preprocess.js
├── coordinate-transform.js
├── prompt-decoder.js
├── mask-renderer.js
├── embedding-cache.js
└── cutout-export.js
```

The old `features/cutout.js` workflow should be removed or replaced entirely. It must not continue calling the obsolete server-side generator.

## Save behavior

Confirming a cutout must first persist it in the Cutouts folder.

After persistence, the UI may offer actions such as:

- Open Cutouts folder;
- Download PNG;
- Copy image.

The application should not automatically switch folders after every save. A toast or completion state may provide an **Open Cutouts** action.

Cancelling a selection before confirmation creates no file and no database record.

## Error handling

Required states:

- model loading;
- image encoding;
- ready for selection;
- decoding selection;
- saving cutout;
- WebGPU unavailable, using WASM;
- model initialization failed;
- image cannot be decoded;
- persistence failed.

A failed save must not create a partial database record. Temporary files must be removed after an error.

## Testing requirements

### Legacy removal

- No calls remain to the old threshold-based mask generator.
- `estimate_background_color()` and `make_foreground_mask()` no longer exist.
- Opening Smart Cutout does not call the old `POST /api/cutout/{id}` endpoint.
- Old cached cutouts are not imported as new assets.

### Segmentation

- Double-clicking inside a clear object returns a mask containing the clicked point.
- WebGPU inference works where supported.
- WASM fallback works when WebGPU is unavailable or session creation fails.
- Encoder inference runs once per cached image rather than once per click.
- Multiple selections on one source image can produce separate saved assets.
- Export uses original resolution and valid PNG transparency.

### Isolation

- Saving a cutout does not add it to the Images tab.
- Saving a cutout does not add it to the currently open source gallery.
- Source-image totals remain unchanged after saving cutouts.
- Global prompt search does not return cutouts.
- The Cutouts folder appears in the Folders sidebar.
- Selecting Cutouts displays only cutouts in the central gallery.
- Leaving Cutouts restores source-only gallery behavior.
- Reloading the application preserves the Cutouts folder and its assets.

### Metadata

- Cutouts do not inherit active prompt or tag fields.
- Cutouts are excluded from generation metadata statistics.
- Provenance links to the source image are retained separately.
- Deleting a source image does not automatically delete its saved cutouts.

## Implementation order

1. Remove the legacy cutout generator, endpoints, UI calls, and cache behavior.
2. Add database support for source and derived asset types.
3. Add the persistent Cutouts system folder and source-only query filters.
4. Add cutout persistence APIs.
5. Add ONNX Runtime Web and the dedicated worker.
6. Benchmark MobileSAM and EfficientSAM-Ti and select the default model.
7. Implement image encoding and embedding caching.
8. Implement double-click and double-tap point prompting.
9. Render candidate masks and confirmation UI.
10. Export and persist transparent PNG files.
11. Add Cutouts-folder browsing and derived-asset metadata UI.
12. Add tests for segmentation, fallback, persistence, and strict gallery isolation.
13. Remove obsolete documentation and replace old Cutout descriptions with Smart Cutout behavior.

## Definition of done

Smart Cutout is complete when a user can open a source image, double-click or double-tap a character or object, receive an interactive model-generated selection in the browser, save a transparent PNG, and later browse that result only through the dedicated Cutouts folder.

No legacy color-threshold mask generation remains, and no derived cutout can leak into the normal source-image gallery, Images tab, prompt search, or generation statistics.
