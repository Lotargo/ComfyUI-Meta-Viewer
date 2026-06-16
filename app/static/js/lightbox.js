/**
 * Lightbox component with improvements
 * - Toggleable metadata panel
 * - Download button
 * - Better navigation
 */

import { images, lightboxIndex, totalImages, galleryActive, detailCache, dom, setLightboxIndex, setActiveIndex, saveState } from './state.js';
import { escapeHtml, originalUrl, thumbUrl, copyText } from './utils.js';
import { initCutoutEvents, resetCutoutPanel } from './features/cutout.js';

let metaPanelOpen = true;
let zoomLevel = 1;
let rotation = 0;
const ZOOM_MIN = 0.1;
const ZOOM_MAX = 10;
const ZOOM_STEP = 0.15;

function applyImageTransform() {
    if (!dom.lbImg) return;
    dom.lbImg.style.transform = `scale(${zoomLevel}) rotate(${rotation}deg)`;
    const indicator = document.getElementById('lb-zoom-level');
    if (indicator) {
        indicator.textContent = `${Math.round(zoomLevel * 100)}%`;
    }
}

export function resetZoom() {
    zoomLevel = 1;
    rotation = 0;
    applyImageTransform();
}

export function zoomIn() {
    zoomLevel = Math.min(ZOOM_MAX, zoomLevel + ZOOM_STEP);
    applyImageTransform();
}

export function zoomOut() {
    zoomLevel = Math.max(ZOOM_MIN, zoomLevel - ZOOM_STEP);
    applyImageTransform();
}

export function rotateClockwise() {
    rotation = (rotation + 90) % 360;
    applyImageTransform();
}

export function rotateCounterClockwise() {
    rotation = (rotation - 90 + 360) % 360;
    applyImageTransform();
}

export async function openLightbox(idx) {
    if (idx < 0 || idx >= images.length) return;
    setLightboxIndex(idx);
    const img = images[idx];

    // Load detail if needed
    if (img && img.id && !detailCache[img.id]) {
        try {
            const resp = await fetch(`/api/images/${img.id}`);
            if (resp.ok) detailCache[img.id] = await resp.json();
        } catch (e) { /* ignore */ }
    }

    dom.lightbox.classList.add('open');
    document.body.style.overflow = 'hidden';
    resetZoom();
    resetCutoutPanel();
    updateLightbox();
}

export function closeLightbox() {
    dom.lightbox.classList.remove('open');
    document.body.style.overflow = '';
    setLightboxIndex(-1);
    resetCutoutPanel();
}

function getDetailForLightbox() {
    const img = images[lightboxIndex];
    if (!img) return null;
    if (img.id && detailCache[img.id]) return detailCache[img.id];
    return img;
}

export function updateLightbox() {
    const img = getDetailForLightbox();
    if (!img) { closeLightbox(); return; }

    setActiveIndex(lightboxIndex);
    saveState();

    if (galleryActive) {
        import('./gallery.js').then(m => m.renderGallery());
    } else {
        import('./features/sidebar.js').then(m => m.renderSidebar());
    }

    const fileName = img.file_name || img.file || '';
    dom.lbTitle.textContent = fileName;
    dom.lbCounter.textContent = `${lightboxIndex + 1} / ${totalImages || images.length}`;
    dom.lbImg.src = originalUrl(img);

    // Update meta panel visibility
    const metaPanel = document.getElementById('lb-meta');
    if (metaPanel) {
        metaPanel.classList.toggle('open', metaPanelOpen);
    }

    // Build metadata HTML
    let html = '';

    // Prompts
    if (img.prompt_parameters) {
        const pp = img.prompt_parameters;
        if (pp.positive_prompt) {
            html += `
                <div class="lb-meta-section">
                    <div class="lb-prompt-label"><svg viewBox="0 0 24 24" width="12" height="12" stroke="var(--green)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><polyline points="20 6 9 17 4 12"></polyline></svg>Positive Prompt</div>
                    <div class="lb-prompt-box">${escapeHtml(pp.positive_prompt)}</div>
                </div>
            `;
        }
        if (pp.negative_prompt) {
            html += `
                <div class="lb-meta-section">
                    <div class="lb-prompt-label"><svg viewBox="0 0 24 24" width="12" height="12" stroke="var(--red)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>Negative Prompt</div>
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
            html += '<div class="lb-meta-section"><h4><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle; margin-right: 4px; opacity: 0.8;"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>Settings</h4>';
            Object.entries(settings).forEach(([k, v]) => {
                html += `
                    <div class="lb-meta-row">
                        <span class="lb-key">${escapeHtml(k)}</span>
                        <span class="lb-val">${escapeHtml(String(v))}</span>
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
                            <span class="lb-val">${escapeHtml(String(v))}</span>
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
                    <span class="lb-val">${escapeHtml(String(v))}</span>
                </div>
            `;
        });
        html += '</div>';
    }

    dom.lbMeta.innerHTML = html || '<div class="lb-no-meta">No metadata</div>';
}

export function lbNav(dir) {
    const next = lightboxIndex + dir;
    if (next >= 0 && next < images.length) {
        resetZoom();
        resetCutoutPanel();
        openLightbox(next);
    }
}

export function toggleMetaPanel() {
    metaPanelOpen = !metaPanelOpen;
    const metaPanel = document.getElementById('lb-meta');
    if (metaPanel) {
        metaPanel.classList.toggle('open', metaPanelOpen);
    }
}

export function downloadImage() {
    const img = images[lightboxIndex];
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

export function initLightboxEvents() {
    initCutoutEvents();

    // Close button
    document.getElementById('lb-close')?.addEventListener('click', closeLightbox);

    // Navigation
    document.getElementById('lb-prev')?.addEventListener('click', () => lbNav(-1));
    document.getElementById('lb-next')?.addEventListener('click', () => lbNav(1));

    // Copy all
    document.getElementById('lb-copy')?.addEventListener('click', () => {
        const img = getDetailForLightbox();
        if (img) copyText(JSON.stringify(img, null, 2));
    });

    // Toggle meta panel
    document.getElementById('lb-toggle-meta')?.addEventListener('click', toggleMetaPanel);

    // Download
    document.getElementById('lb-download')?.addEventListener('click', downloadImage);

    document.getElementById('lb-delete')?.addEventListener('click', async () => {
        const currentIndex = lightboxIndex;
        const { deleteImageAt } = await import('./api.js');
        const deleted = await deleteImageAt(currentIndex);
        if (!deleted) return;
        if (images.length === 0) {
            closeLightbox();
            return;
        }
        setLightboxIndex(Math.min(currentIndex, images.length - 1));
        updateLightbox();
    });

    // Zoom controls
    document.getElementById('lb-zoom-in')?.addEventListener('click', zoomIn);
    document.getElementById('lb-zoom-out')?.addEventListener('click', zoomOut);
    document.getElementById('lb-rotate-cw')?.addEventListener('click', rotateClockwise);
    document.getElementById('lb-rotate-ccw')?.addEventListener('click', rotateCounterClockwise);
    document.getElementById('lb-zoom-reset')?.addEventListener('click', resetZoom);

    // Mouse wheel zoom on image area
    const imageArea = document.querySelector('.lightbox-image-area');
    imageArea?.addEventListener('wheel', e => {
        e.preventDefault();
        if (e.deltaY < 0) {
            zoomLevel = Math.min(ZOOM_MAX, zoomLevel + ZOOM_STEP);
        } else {
            zoomLevel = Math.max(ZOOM_MIN, zoomLevel - ZOOM_STEP);
        }
        applyImageTransform();
    }, { passive: false });

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
