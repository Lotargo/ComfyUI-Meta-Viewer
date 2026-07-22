/**
 * Lightbox component with improvements
 * - Toggleable metadata panel
 * - Download button
 * - Better navigation
 */

import {
    images,
    sidebarImages,
    sidebarTotalImages,
    lightboxIndex,
    totalImages,
    allLoaded,
    currentCollection,
    galleryActive,
    detailCache,
    dom,
    showToast,
    lightboxMetaOpen,
    setLightboxMetaOpen,
    setLightboxIndex,
    setActiveIndex,
    setSidebarActiveImageId,
    saveState,
    isBrowsableCollection,
} from './state.js';
import {
    escapeHtml,
    getMetadataStringValue,
    getStringValue,
    thumbUrl,
    previewUrl,
    originalUrl,
    copyText,
} from './utils.js';
import { initCutoutEvents, openCutoutPanel, resetCutoutPanel } from './features/cutout.js';
import { showImageContextMenu } from './components/image-context-menu.js';

let zoomLevel = 1;
let rotation = 0;
let panX = 0;
let panY = 0;
let imageArea = null;
let panPointerId = null;
let panLastX = 0;
let panLastY = 0;
let imageLoadToken = 0;
let previewAbortController = null;
let displayedPreviewObjectUrl = null;
let displayedPreviewToken = -1;
let displayedImageId = null;
let currentImagesArray = [];
let usesGalleryPagination = false;
let fileDeleteInProgress = false;
const ZOOM_MIN = 0.1;
const ZOOM_MAX = 10;
const ZOOM_STEP = 0.15;
const PREVIEW_RETRY_DELAY = 500;
const THUMBNAIL_FALLBACK_DELAY = 250;
const GALLERY_PREFETCH_THRESHOLD = 5;

function canLoadNextGalleryPage() {
    return usesGalleryPagination && isBrowsableCollection(currentCollection) && !allLoaded;
}

function visibleCollectionTotal() {
    return currentImagesArray === sidebarImages ? sidebarTotalImages : totalImages;
}

function isCurrentVideo() {
    return getDetailForLightbox()?.media_type === 'video';
}

function syncLightboxDeleteButton(asset) {
    if (!dom.lbDelete) return;
    dom.lbDelete.disabled = !asset?.id || fileDeleteInProgress;
    if (!asset?.id) {
        dom.lbDelete.title = 'No indexed asset to delete';
        return;
    }
    const assetLabel = asset.media_type === 'video' ? 'video' : 'image';
    dom.lbDelete.title = asset.has_local_file
        ? `Delete ${assetLabel} file from computer (Delete) — moves it to the Recycle Bin / Trash`
        : `Delete uploaded ${assetLabel} from the app (Delete)`;
}

async function loadNextGalleryPage() {
    if (!canLoadNextGalleryPage()) return false;
    const gallery = await import('./gallery.js');
    return gallery.loadNextGalleryPage();
}

function prefetchNextGalleryPage() {
    const remainingLoadedImages = currentImagesArray.length - lightboxIndex - 1;
    if (remainingLoadedImages > GALLERY_PREFETCH_THRESHOLD || !canLoadNextGalleryPage()) return;
    loadNextGalleryPage().catch(() => { /* navigation retries at the page boundary */ });
}

function getPanBounds() {
    if (!dom.lbImg || !imageArea) return { x: 0, y: 0 };

    const areaRect = imageArea.getBoundingClientRect();
    const quarterTurns = Math.abs(rotation / 90) % 2;
    const imageWidth = quarterTurns ? dom.lbImg.offsetHeight : dom.lbImg.offsetWidth;
    const imageHeight = quarterTurns ? dom.lbImg.offsetWidth : dom.lbImg.offsetHeight;

    return {
        x: Math.max(0, (imageWidth * zoomLevel - areaRect.width) / 2),
        y: Math.max(0, (imageHeight * zoomLevel - areaRect.height) / 2),
    };
}

function clampPan() {
    const bounds = getPanBounds();
    panX = Math.max(-bounds.x, Math.min(bounds.x, panX));
    panY = Math.max(-bounds.y, Math.min(bounds.y, panY));
    return bounds;
}

function stopPanning(pointerId = panPointerId) {
    if (pointerId !== null && dom.lbImg?.hasPointerCapture(pointerId)) {
        dom.lbImg.releasePointerCapture(pointerId);
    }
    panPointerId = null;
    dom.lbImg?.classList.remove('is-panning');
}

function applyImageTransform() {
    if (!dom.lbImg) return;
    const bounds = clampPan();
    dom.lbImg.style.transform = `translate3d(${panX}px, ${panY}px, 0) scale(${zoomLevel}) rotate(${rotation}deg)`;
    dom.lbImg.classList.toggle('is-pannable', bounds.x > 0 || bounds.y > 0);
    if (dom.lbZoomLevel) {
        dom.lbZoomLevel.textContent = `${Math.round(zoomLevel * 100)}%`;
    }
}

function setZoom(nextZoom, focalPoint = null) {
    const clampedZoom = Math.max(ZOOM_MIN, Math.min(ZOOM_MAX, nextZoom));
    if (clampedZoom === zoomLevel) return;

    if (focalPoint && imageArea && zoomLevel > 0) {
        const areaRect = imageArea.getBoundingClientRect();
        const focalX = focalPoint.x - (areaRect.left + areaRect.width / 2);
        const focalY = focalPoint.y - (areaRect.top + areaRect.height / 2);
        const zoomRatio = clampedZoom / zoomLevel;
        panX += (focalX - panX) * (1 - zoomRatio);
        panY += (focalY - panY) * (1 - zoomRatio);
    }

    zoomLevel = clampedZoom;
    applyImageTransform();
}

function cancelImageLoad({ clearSource = false } = {}) {
    imageLoadToken += 1;
    previewAbortController?.abort();
    previewAbortController = null;

    if (clearSource) {
        dom.lbImg?.removeAttribute('src');
        if (displayedPreviewObjectUrl) {
            URL.revokeObjectURL(displayedPreviewObjectUrl);
            displayedPreviewObjectUrl = null;
        }
        displayedPreviewToken = -1;
    }
}

function revokeObjectUrlAfterPaint(objectUrl) {
    if (!objectUrl) return;
    requestAnimationFrame(() => {
        requestAnimationFrame(() => URL.revokeObjectURL(objectUrl));
    });
}

async function decodeImageSource(source) {
    const preloader = new Image();
    preloader.decoding = 'async';
    await new Promise((resolve, reject) => {
        preloader.addEventListener('load', resolve, { once: true });
        preloader.addEventListener('error', reject, { once: true });
        preloader.src = source;
    });
    if (typeof preloader.decode === 'function') {
        await preloader.decode().catch(() => { /* the completed image remains usable */ });
    }
}

function commitDecodedImage(source, token, { previewObjectUrl = null } = {}) {
    if (token !== imageLoadToken || !dom.lbImg) return false;

    const previousObjectUrl = displayedPreviewObjectUrl;
    dom.lbImg.src = source;
    displayedPreviewObjectUrl = previewObjectUrl;
    if (previewObjectUrl) displayedPreviewToken = token;
    if (previousObjectUrl && previousObjectUrl !== previewObjectUrl) {
        revokeObjectUrlAfterPaint(previousObjectUrl);
    }
    return true;
}

async function fetchDisplayPreview(img, token, controller) {
    if (token !== imageLoadToken || controller.signal.aborted) return null;

    const response = await fetch(previewUrl(img), {
        signal: controller.signal,
        cache: 'no-cache',
    });
    if (response.status !== 202) return response;

    const retryHeader = response.headers.get('Retry-After');
    const retrySeconds = retryHeader ? Number(retryHeader) : Number.NaN;
    const retryDelay = Number.isFinite(retrySeconds)
        ? retrySeconds * 1000
        : PREVIEW_RETRY_DELAY;
    await new Promise(resolve => setTimeout(resolve, retryDelay));
    return fetchDisplayPreview(img, token, controller);
}

async function loadDisplayPreview(img, token) {
    const controller = new AbortController();
    previewAbortController = controller;
    let objectUrl = null;

    try {
        const response = await fetchDisplayPreview(img, token, controller);
        if (!response?.ok) return;

        const previewBlob = await response.blob();
        if (token !== imageLoadToken || controller.signal.aborted) return;

        objectUrl = URL.createObjectURL(previewBlob);
        if (token !== imageLoadToken || controller.signal.aborted) {
            return;
        }

        await decodeImageSource(objectUrl);
        if (token !== imageLoadToken || controller.signal.aborted) return;
        if (commitDecodedImage(objectUrl, token, { previewObjectUrl: objectUrl })) {
            objectUrl = null; // Ownership moves to the visible lightbox image.
        }
    } catch (error) {
        if (error.name !== 'AbortError') {
            // Keep the already visible decoded frame if preview generation fails.
        }
    } finally {
        if (objectUrl) URL.revokeObjectURL(objectUrl);
        if (previewAbortController === controller) {
            previewAbortController = null;
        }
    }
}

function loadLightboxImage(img) {
    const hadVisibleImage = Boolean(dom.lbImg?.getAttribute('src'));
    cancelImageLoad();
    const token = imageLoadToken;

    if (img.id) loadDisplayPreview(img, token);

    const fallbackDelay = hadVisibleImage && img.id ? THUMBNAIL_FALLBACK_DELAY : 0;
    (async () => {
        if (fallbackDelay) {
            await new Promise(resolve => setTimeout(resolve, fallbackDelay));
        }
        if (token !== imageLoadToken || displayedPreviewToken === token) return;

        const thumbnail = thumbUrl(img);
        try {
            await decodeImageSource(thumbnail);
            if (token !== imageLoadToken || displayedPreviewToken === token) return;
            commitDecodedImage(thumbnail, token);
        } catch (_error) {
            // Keep the previous decoded frame until a preview is available.
        }
    })();
}

function stopLightboxVideo({ clearSource = false } = {}) {
    if (!dom.lbVideo) return;
    dom.lbVideo.pause();
    if (clearSource) {
        dom.lbVideo.removeAttribute('src');
        dom.lbVideo.load();
    }
}

function syncMediaControls(isVideo) {
    [dom.lbZoomIn, dom.lbZoomOut, dom.lbZoomReset, dom.lbRotateCw, dom.lbRotateCcw]
        .forEach(button => { if (button) button.disabled = isVideo; });
    if (dom.lbCutout) {
        dom.lbCutout.disabled = isVideo;
        dom.lbCutout.title = isVideo ? 'Object cutout is available for images' : 'Select object';
    }
}

function loadLightboxMedia(asset) {
    const isVideo = asset.media_type === 'video';
    syncMediaControls(isVideo);
    if (isVideo) {
        cancelImageLoad({ clearSource: true });
        stopPanning();
        if (dom.lbImg) dom.lbImg.hidden = true;
        if (dom.lbVideo) {
            dom.lbVideo.hidden = false;
            dom.lbVideo.src = originalUrl(asset);
        }
        return;
    }

    stopLightboxVideo({ clearSource: true });
    if (dom.lbVideo) dom.lbVideo.hidden = true;
    if (dom.lbImg) dom.lbImg.hidden = false;
    loadLightboxImage(asset);
}

export function resetZoom() {
    stopPanning();
    zoomLevel = 1;
    rotation = 0;
    panX = 0;
    panY = 0;
    applyImageTransform();
}

export function zoomIn() {
    if (isCurrentVideo()) return;
    setZoom(zoomLevel + ZOOM_STEP);
}

export function zoomOut() {
    if (isCurrentVideo()) return;
    setZoom(zoomLevel - ZOOM_STEP);
}

export function rotateClockwise() {
    if (isCurrentVideo()) return;
    rotation = (rotation + 90) % 360;
    applyImageTransform();
}

export function rotateCounterClockwise() {
    if (isCurrentVideo()) return;
    rotation = (rotation - 90 + 360) % 360;
    applyImageTransform();
}

export async function openLightbox(index, imagesArray = null) {
    if (imagesArray) {
        currentImagesArray = imagesArray;
        usesGalleryPagination = imagesArray === images;
    }
    setLightboxIndex(index);
    const img = currentImagesArray[index];
    if (!img) return;

    // Load detail if needed
    if (img && img.id && !detailCache[img.id]) {
        try {
            const resp = await fetch(`/api/assets/${img.id}`);
            if (resp.ok) detailCache[img.id] = await resp.json();
        } catch (_e) { /* ignore */ }
    }

    dom.lightbox.classList.add('open');
    document.body.style.overflow = 'hidden';
    resetZoom();
    resetCutoutPanel();
    updateLightbox();
    prefetchNextGalleryPage();
}

export function closeLightbox() {
    stopPanning();
    cancelImageLoad({ clearSource: true });
    stopLightboxVideo({ clearSource: true });
    dom.lightbox.classList.remove('open');
    document.body.style.overflow = '';
    setLightboxIndex(-1);
    displayedImageId = null;
    resetCutoutPanel();
}

function getDetailForLightbox() {
    const img = currentImagesArray[lightboxIndex];
    if (!img) return null;
    if (img.id && detailCache[img.id]) return detailCache[img.id];
    return img;
}

export function updateLightbox() {
    const img = getDetailForLightbox();
    if (!img) { closeLightbox(); return; }

    const nextImageId = img.id ?? null;

    setActiveIndex(lightboxIndex);

    if (currentImagesArray === sidebarImages) {
        setSidebarActiveImageId(nextImageId);
        import('./features/sidebar.js').then(module => module.renderSidebar());
    } else if (galleryActive) {
        import('./gallery.js').then(m => m.updateActiveGalleryCard(lightboxIndex));
    } else {
        import('./features/sidebar.js').then(m => m.renderSidebar());
    }

    const fileName = img.file_name || img.file || '';
    dom.lbTitle.textContent = fileName;
    dom.lbCounter.textContent = `${lightboxIndex + 1} / ${visibleCollectionTotal() || currentImagesArray.length}`;
    loadLightboxMedia(img);
    displayedImageId = nextImageId;
    if (dom.lbViewOriginal) dom.lbViewOriginal.disabled = !img.id;
    syncLightboxDeleteButton(img);

    // Update meta panel visibility
    if (dom.lbMeta) {
        dom.lbMeta.classList.toggle('open', lightboxMetaOpen);
    }

    // Build metadata HTML
    let html = '';

    if (img.media_type === 'video') {
        const videoRows = [
            ['Type', 'Video'],
            ['Container', img.format],
            ['Dimensions', img.size ? `${img.size[0]} × ${img.size[1]}` : null],
            ['Duration', Number.isFinite(img.duration) ? `${img.duration.toFixed(2)} s` : null],
            ['Frame rate', Number.isFinite(img.frame_rate) ? `${img.frame_rate.toFixed(3)} fps` : null],
            ['Codec', img.codec],
            ['Pixel format', img.mode],
            ['Preview', img.preview_status],
        ].filter(([, value]) => value !== null && value !== undefined && value !== '');
        html += '<div class="lb-meta-section"><h4>Video details</h4>';
        videoRows.forEach(([key, value]) => {
            html += `<div class="lb-meta-row"><span class="lb-key">${escapeHtml(key)}</span><span class="lb-val">${escapeHtml(value)}</span></div>`;
        });
        if (img.preview_error) {
            html += `<div class="lb-meta-row"><span class="lb-key">Preview error</span><span class="lb-val">${escapeHtml(img.preview_error)}</span></div>`;
        }
        html += '</div>';
    }

    // Prompts
    if (img.prompt_parameters) {
        const pp = img.prompt_parameters;
        if (pp.positive_prompt) {
            html += `
                <div class="lb-meta-section">
                    <div class="lb-prompt-label" style="display: flex; justify-content: space-between; align-items: center;">
                        <span><svg viewBox="0 0 24 24" width="12" height="12" stroke="var(--green)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><polyline points="20 6 9 17 4 12"></polyline></svg>Positive Prompt</span>
                        <button class="btn btn-sm btn-ghost lb-copy-prompt" style="padding: 2px 6px; font-size: 11px;" data-copy-value="${escapeHtml(pp.positive_prompt).replace(/"/g, '&quot;')}">Copy</button>
                    </div>
                    <div class="lb-prompt-box">${escapeHtml(pp.positive_prompt)}</div>
                </div>
            `;
        }
        if (pp.negative_prompt) {
            html += `
                <div class="lb-meta-section">
                    <div class="lb-prompt-label" style="display: flex; justify-content: space-between; align-items: center;">
                        <span><svg viewBox="0 0 24 24" width="12" height="12" stroke="var(--red)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Negative Prompt</span>
                        <button class="btn btn-sm btn-ghost lb-copy-prompt" style="padding: 2px 6px; font-size: 11px;" data-copy-value="${escapeHtml(pp.negative_prompt).replace(/"/g, '&quot;')}">Copy</button>
                    </div>
                    <div class="lb-prompt-box">${escapeHtml(pp.negative_prompt)}</div>
                </div>
            `;
        }

        // Settings
        const settings = {};
        Object.entries(pp).forEach(([k, v]) => {
            if (!['generation_settings', 'extra_settings', 'workflow_nodes', 'positive_prompt', 'negative_prompt'].includes(k)) {
                settings[k] = v;
            }
        });
        if (pp.generation_settings) Object.assign(settings, pp.generation_settings);

        if (Object.keys(settings).length) {
            html += '<div class="lb-meta-section"><h4><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px; opacity: 0.8;"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06-.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>Settings</h4>';
            Object.entries(settings).forEach(([k, v]) => {
                html += `
                    <div class="lb-meta-row">
                        <span class="lb-key">${escapeHtml(k)}</span>
                        <span class="lb-val">${escapeHtml(getMetadataStringValue(k, v))}</span>
                    </div>
                `;
            });
            html += '</div>';
        }
    }

    // Workflow nodes
    if (img.workflow && img.workflow.workflow_nodes) {
        const order = ['Models', 'Prompts', 'Sampler', 'Image Settings', 'Post Processing', 'LoRA', 'Other'];
        order.forEach(catName => {
            const nodes = img.workflow.workflow_nodes[catName];
            if (!nodes || !nodes.length) return;
            html += `<div class="lb-meta-section"><h4>${escapeHtml(catName)} (${nodes.length})</h4>`;
            nodes.forEach(n => {
                html += `
                    <div class="lb-node">
                        <div class="lb-node-header">
                            <span class="lb-node-type">${escapeHtml(n.class_type)}</span>
                            <span class="lb-node-id">#${n.node_id}</span>
                        </div>
                `;
                Object.entries(n.inputs || {}).forEach(([k, v]) => {
                    html += `
                        <div class="lb-meta-row">
                            <span class="lb-key">${escapeHtml(k)}</span>
                            <span class="lb-val">${escapeHtml(getStringValue(v))}</span>
                        </div>
                    `;
                });
                html += '</div>';
            });
            html += '</div>';
        });
    }

    // EXIF
    if (img.exif && Object.keys(img.exif).length) {
        html += '<div class="lb-meta-section"><h4><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px; opacity: 0.8;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>EXIF</h4>';
        Object.entries(img.exif).forEach(([k, v]) => {
            html += `
                <div class="lb-meta-row">
                    <span class="lb-key">${escapeHtml(k)}</span>
                    <span class="lb-val">${escapeHtml(getStringValue(v))}</span>
                </div>
            `;
        });
        html += '</div>';
    }

    dom.lbMeta.innerHTML = html || '<div class="lb-no-meta">No metadata</div>';
    
    // Attach event listeners for copy buttons in lightbox meta
    dom.lbMeta.querySelectorAll('.lb-copy-prompt').forEach(btn => {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            copyText(btn.dataset.copyValue || '');
        });
    });
}

export function syncLightboxAfterCollectionChange({ changedImageIds = new Set() } = {}) {
    if (!dom.lightbox.classList.contains('open')) return;

    const previousImageId = displayedImageId;
    const nextIndex = previousImageId === null
        ? -1
        : currentImagesArray.findIndex(img => img.id === previousImageId);
    if (nextIndex >= 0) {
        setLightboxIndex(nextIndex);
        if (changedImageIds.has(previousImageId)) {
            updateLightbox();
            return;
        }

        setActiveIndex(nextIndex);
        const img = currentImagesArray[nextIndex];
        dom.lbTitle.textContent = img.file_name || img.file || '';
        dom.lbCounter.textContent = `${nextIndex + 1} / ${visibleCollectionTotal() || currentImagesArray.length}`;
        if (currentImagesArray === sidebarImages) {
            setSidebarActiveImageId(img.id);
            import('./features/sidebar.js').then(module => module.renderSidebar());
        } else if (galleryActive) {
            import('./gallery.js').then(module => module.updateActiveGalleryCard(nextIndex));
        }
        return;
    }

    setLightboxIndex(Math.min(Math.max(lightboxIndex, 0), currentImagesArray.length - 1));
    updateLightbox();
}

async function navigateLightbox(dir, { wrap = false } = {}) {
    let next = lightboxIndex + dir;
    if (dir > 0 && next >= currentImagesArray.length) {
        await loadNextGalleryPage();
    }

    if (next >= 0 && next < currentImagesArray.length) {
        resetZoom();
        resetCutoutPanel();
        await openLightbox(next);
        return;
    }

    if (!wrap || currentImagesArray.length === 0 || canLoadNextGalleryPage()) return;
    next = dir > 0 ? 0 : currentImagesArray.length - 1;
    await openLightbox(next);
}

export function lbNav(dir) {
    return navigateLightbox(dir);
}

export function nextLightbox() {
    return navigateLightbox(1, { wrap: true });
}

export function prevLightbox() {
    return navigateLightbox(-1, { wrap: true });
}

export function toggleMetaPanel() {
    setLightboxMetaOpen(!lightboxMetaOpen);
    if (dom.lbMeta) {
        dom.lbMeta.classList.toggle('open', lightboxMetaOpen);
    }
    saveState();
}

export function downloadImage() {
    const img = currentImagesArray[lightboxIndex];
    if (!img) return;

    const url = originalUrl(img);
    const fileName = img.file_name || img.file || 'image.png';

    const a = document.createElement('a');
    a.href = url;
    a.download = fileName;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

async function remixCurrentAsset() {
    const img = getDetailForLightbox();
    if (!img?.id || dom.lbRemix?.disabled) return;
    dom.lbRemix.disabled = true;
    try {
        const response = await fetch('/api/editor/remix', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset_id: img.id }),
        });
        const payload = await response.json();
        if (!response.ok) throw new Error(payload.error || 'Could not create a remix draft');
        window.location.assign(payload.editor_url);
    } catch (error) {
        showToast(error.message || String(error));
        dom.lbRemix.disabled = false;
    }
}

async function removeCurrentLightboxAsset(removeAsset) {
    if (fileDeleteInProgress) return false;
    const currentIndex = lightboxIndex;
    const img = currentImagesArray[currentIndex];
    if (!img?.id) return false;

    fileDeleteInProgress = true;
    if (dom.lbDelete) dom.lbDelete.disabled = true;
    try {
        const deleted = await removeAsset(img.id);
        if (!deleted) return false;
        if (currentImagesArray.length === 0) {
            closeLightbox();
            return true;
        }
        setLightboxIndex(Math.min(currentIndex, currentImagesArray.length - 1));
        resetZoom();
        resetCutoutPanel();
        updateLightbox();
        return true;
    } finally {
        fileDeleteInProgress = false;
        syncLightboxDeleteButton(currentImagesArray[lightboxIndex]);
    }
}

export async function deleteCurrentLightboxFile() {
    const img = currentImagesArray[lightboxIndex];
    if (!img?.id || !img.has_local_file) {
        const assetLabel = img?.media_type === 'video' ? 'video' : 'image';
        showToast(`This ${assetLabel} has no available physical file`);
        return false;
    }
    const { deleteAssetFileById } = await import('./api.js');
    return removeCurrentLightboxAsset(deleteAssetFileById);
}

export async function removeCurrentLightboxAssetFromIndex() {
    const { removeAssetFromIndexById } = await import('./api.js');
    return removeCurrentLightboxAsset(removeAssetFromIndexById);
}

export function deleteCurrentLightboxAsset() {
    const img = currentImagesArray[lightboxIndex];
    if (!img?.id) return false;
    return img.has_local_file
        ? deleteCurrentLightboxFile()
        : removeCurrentLightboxAssetFromIndex();
}

export function viewOriginal() {
    const img = getDetailForLightbox();
    if (!img?.id) return;
    window.open(originalUrl(img), '_blank', 'noopener,noreferrer');
}

export function initLightboxEvents() {
    initCutoutEvents({ getActiveImage: getDetailForLightbox });
    imageArea = document.querySelector('.lightbox-image-area');

    // Close button
    dom.lbClose?.addEventListener('click', closeLightbox);

    // Navigation
    dom.lbPrev?.addEventListener('click', () => lbNav(-1));
    dom.lbNext?.addEventListener('click', () => lbNav(1));

    // Copy all
    dom.lbCopy?.addEventListener('click', () => {
        const img = getDetailForLightbox();
        if (img) copyText(JSON.stringify(img, null, 2));
    });

    // Toggle meta panel
    dom.lbToggleMeta?.addEventListener('click', toggleMetaPanel);

    // Download
    dom.lbViewOriginal?.addEventListener('click', viewOriginal);
    dom.lbDownload?.addEventListener('click', downloadImage);
    dom.lbRemix?.addEventListener('click', remixCurrentAsset);

    dom.lbDelete?.addEventListener('click', deleteCurrentLightboxAsset);

    // Zoom controls
    dom.lbZoomIn?.addEventListener('click', zoomIn);
    dom.lbZoomOut?.addEventListener('click', zoomOut);
    dom.lbRotateCw?.addEventListener('click', rotateClockwise);
    dom.lbRotateCcw?.addEventListener('click', rotateCounterClockwise);
    dom.lbZoomReset?.addEventListener('click', resetZoom);

    // Mouse wheel zoom on image area
    imageArea?.addEventListener('wheel', e => {
        if (isCurrentVideo()) return;
        e.preventDefault();
        const direction = e.deltaY < 0 ? 1 : -1;
        setZoom(zoomLevel + direction * ZOOM_STEP, {
            x: e.clientX,
            y: e.clientY,
        });
    }, { passive: false });

    // Drag a zoomed image with the primary mouse button.
    dom.lbImg?.addEventListener('pointerdown', e => {
        if (e.button !== 0 || (e.pointerType !== 'mouse' && e.pointerType !== 'pen')) return;
        const bounds = getPanBounds();
        if (bounds.x === 0 && bounds.y === 0) return;

        e.preventDefault();
        e.stopPropagation();
        panPointerId = e.pointerId;
        panLastX = e.clientX;
        panLastY = e.clientY;
        dom.lbImg.setPointerCapture(e.pointerId);
        dom.lbImg.classList.add('is-panning');
    });

    dom.lbImg?.addEventListener('pointermove', e => {
        if (e.pointerId !== panPointerId) return;
        if ((e.buttons & 1) === 0) {
            stopPanning(e.pointerId);
            return;
        }

        e.preventDefault();
        panX += e.clientX - panLastX;
        panY += e.clientY - panLastY;
        panLastX = e.clientX;
        panLastY = e.clientY;
        applyImageTransform();
    });

    dom.lbImg?.addEventListener('pointerup', e => {
        if (e.pointerId === panPointerId) stopPanning(e.pointerId);
    });
    dom.lbImg?.addEventListener('pointercancel', e => {
        if (e.pointerId === panPointerId) stopPanning(e.pointerId);
    });
    dom.lbImg?.addEventListener('lostpointercapture', e => {
        if (e.pointerId === panPointerId) stopPanning(null);
    });
    dom.lbImg?.addEventListener('dragstart', e => e.preventDefault());
    dom.lbImg?.addEventListener('load', applyImageTransform);
    const showCurrentAssetContextMenu = event => {
        const img = getDetailForLightbox();
        if (!img?.id) return;
        const actionSections = [];
        if (img.media_type !== 'video') {
            actionSections.push([{
                label: 'Create transparent PNG',
                icon: 'cutout',
                run: openCutoutPanel,
            }]);
        }
        showImageContextMenu(event, {
            imageId: img.id,
            fileName: img.file_name || img.file || '',
            sourceUrl: originalUrl(img),
            mediaType: img.media_type || 'image',
            canAccessOriginal: true,
            hasLocalFile: Boolean(img.id && img.has_local_file),
            isUploadedAsset: img.has_local_file === false,
            rating: img.rating,
            detail: img,
            onDeleteFile: deleteCurrentLightboxFile,
            onRemoveFromIndex: removeCurrentLightboxAssetFromIndex,
            onRenamed: renamed => import('./api.js').then(module => module.applyImageRename(renamed)),
            onRatingChanged: asset => import('./api.js').then(module => module.applyImageRating(asset)),
            extraSections: actionSections,
            notify: showToast,
        });
    };
    dom.lbImg?.addEventListener('contextmenu', showCurrentAssetContextMenu);
    dom.lbVideo?.addEventListener('contextmenu', showCurrentAssetContextMenu);

    // Keep the image within the viewport after fullscreen/layout changes.
    window.addEventListener('resize', applyImageTransform);
    dom.lbMeta?.addEventListener('transitionend', e => {
        if (e.propertyName === 'width') applyImageTransform();
    });

    // Double-click to reset zoom
    dom.lbImg?.addEventListener('dblclick', e => {
        e.stopPropagation();
        resetZoom();
    });

    // Click outside to close
    dom.lightbox?.addEventListener('click', e => {
        if (e.target === dom.lightbox || e.target.classList.contains('lightbox-body')) {
            closeLightbox();
        }
    });

    // Touch swipe support
    let touchStartX = 0;
    let touchStartY = 0;

    dom.lightbox?.addEventListener('touchstart', e => {
        touchStartX = e.touches[0].clientX;
        touchStartY = e.touches[0].clientY;
    }, { passive: true });

    dom.lightbox?.addEventListener('touchend', e => {
        const touchEndX = e.changedTouches[0].clientX;
        const touchEndY = e.changedTouches[0].clientY;
        const diffX = touchEndX - touchStartX;
        const diffY = touchEndY - touchStartY;

        // Only handle horizontal swipes
        if (Math.abs(diffX) > Math.abs(diffY) && Math.abs(diffX) > 50) {
            if (diffX > 0) {
                lbNav(-1); // Swipe right = previous
            } else {
                lbNav(1); // Swipe left = next
            }
        }
    }, { passive: true });
}
