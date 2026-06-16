# Sprint: Object Cutout

**Status:** In progress  
**Start:** 2026-06-16  
**Goal:** Add an Object Cutout workflow so a user can isolate a generated subject/object and reuse it as a transparent PNG or future generation input.

---

## Product Goal

ComfyUI Meta Viewer already helps inspect generated images and export originals. The next useful step is to let the user select the useful object from a generation, remove the background, and save the result as a reusable asset.

Target workflow:

1. User opens an image in lightbox.
2. User clicks `Select Object`.
3. MVP extracts the main foreground subject automatically.
4. A cutout panel shows transparent-background preview.
5. User can download the cutout PNG.
6. Later iterations add click-to-select, mask refinement, and "Add to Gallery".

---

## UX Scope

### MVP

- Add `Select Object` action in lightbox controls.
- Open a cutout side panel/modal with:
  - processing state;
  - preview on checkerboard background;
  - `Download PNG`;
  - `Reset / close`.
- Keep original images safe. Cutout generation must not mutate the source image.
- Store generated cutouts in a local cache folder so repeat downloads are fast.

### Next Iteration

- Click-to-select object by point.
- Positive/negative selection points.
- Mask preview overlay on the original image.
- Add cutout as a new gallery item.
- Export mask PNG separately.

---

## Technical Approach

### Phase 1: Dependency-Light MVP

Use a backend API that accepts an image id and returns a transparent PNG cutout.

Initial strategy options:

1. **Local rembg/U2Net-style foreground extraction**
   - Best MVP if dependency is acceptable.
   - Strong for central characters/products.
   - Weak when multiple objects overlap or background is complex.

2. **Fallback heuristic segmentation**
   - No heavy dependency.
   - Use image alpha if present; otherwise simple edge/border/background estimate.
   - Good as a graceful fallback, not as the primary quality target.

3. **SAM-style click segmentation**
   - Best long-term UX.
   - Heavier model/runtime.
   - Better as Phase 2 after MVP UI and API are stable.

### Proposed API

| Method | Path | Description |
|---|---|---|
| `POST` | `/api/cutout/<image_id>` | Generate or return cached transparent PNG cutout |
| `GET` | `/api/cutout/<image_id>` | Return cached cutout if it exists |
| `DELETE` | `/api/cutout/<image_id>` | Clear cached cutout |

MVP response for `POST`:

```json
{
  "ok": true,
  "image_id": 123,
  "cutout_url": "/api/cutout/123",
  "cached": false
}
```

### File Layout

Suggested new files:

- `app/cutout.py` - cutout generation and cache helpers.
- `cache/cutouts/<image_id>.png` - transparent PNG cache.
- `app/static/js/features/cutout.js` - cutout panel and API calls.
- `app/static/css/features/cutout.css` - panel, preview, checkerboard.

Suggested updated files:

- `app/main.py` - API endpoints.
- `app/templates/index.html` - lightbox button and cutout panel root.
- `app/static/js/lightbox.js` - initialize/open cutout workflow.
- `app/static/css/features/lightbox.css` - control layout if needed.

---

## Acceptance Criteria

### MVP Done

- [ ] Lightbox has a `Select Object` button.
- [ ] Clicking it shows a cutout panel with loading state.
- [ ] Backend generates transparent PNG for image ids stored in DB.
- [ ] Cutout preview renders on checkerboard background.
- [ ] User can download the cutout PNG.
- [ ] Repeated cutout requests reuse cache.
- [ ] Errors are visible and non-destructive.
- [ ] Source image file/data remains unchanged.

### Verification

- [ ] `python -m compileall app` passes.
- [ ] `/api/cutout/<image_id>` returns `404` before generation or if source is missing.
- [ ] `POST /api/cutout/<image_id>` returns JSON with `cutout_url`.
- [ ] In-app browser: button opens panel, preview appears, download link is valid.
- [ ] Works for uploaded images stored as DB blobs.
- [ ] Works for scanned images loaded from disk.

---

## Sprint Plan

### Step 0: Architecture Spike

- [x] Inspect current image serving helpers.
- [x] Confirm where to reuse original bytes/path loading.
- [x] Check available Python dependencies.
- [x] Decide MVP cutout engine and fallback.

Findings:

- Existing source loading can reuse `db.get_image_original_data(image_id)` for uploaded files and `db.get_image_path(image_id)` for scanned folder files.
- Current `.venv` has Pillow only. No numpy, cv2, rembg, onnxruntime, torch, or skimage.
- MVP starts with a dependency-light Pillow fallback: alpha reuse when present, otherwise border-color foreground mask.
- API/cache boundaries are intentionally engine-agnostic so rembg/SAM can replace the fallback later.

### Step 1: Backend Skeleton

- [x] Add `app/cutout.py`.
- [x] Add cache path helper.
- [x] Add API endpoints.
- [x] Return meaningful errors for missing source/cutout.

### Step 2: MVP Cutout Engine

- [x] Implement dependency-light foreground extraction fallback.
- [ ] Add optional rembg path if dependency is installed.
- [x] Save transparent PNG to cache.

### Step 3: Frontend Panel

- [ ] Add lightbox `Select Object` button.
- [ ] Add cutout panel markup and CSS.
- [ ] Add JS module for request/preview/download.

### Step 4: Polish

- [ ] Add retry/reset.
- [ ] Add cache clear button.
- [ ] Add Help Center note for Object Cutout.
- [ ] Browser verification.

### Step 5: Phase 2 Planning

- [ ] Evaluate click-to-select model path.
- [ ] Decide SAM/SAM2/ONNX runtime strategy.
- [ ] Add positive/negative point UX design.

---

## Risks

- High-quality segmentation may require heavy ML dependencies and model downloads.
- Browser-only canvas segmentation would be lighter but likely lower quality.
- CPU-only inference may be slow on large images.
- Scanned source files may move/delete after scan; API must report this clearly.

---

## Notes

MVP should optimize for a useful, reliable workflow rather than perfect object boundaries. The UI/API boundaries should be designed so the segmentation engine can be swapped later without reworking the lightbox experience.
