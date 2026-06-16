/**
 * Lightbox component with improvements
 * - Toggleable metadata panel
 * - Download button
 * - Better navigation
 */

import { images, lightboxIndex, totalImages, galleryActive, detailCache, dom, setLightboxIndex, setActiveIndex, saveState } from './state.js';
import { escapeHtml, originalUrl, thumbUrl, copyText } from './utils.js';

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
    updateLightbox();
}

export function closeLightbox() {
    dom.lightbox.classList.remove('open');
    document.body.style.overflow = '';
    setLightboxIndex(-1);
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
        import('./sidebar.js').then(m => m.renderSidebar());
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
                    <div class="lb-prompt-label">&#10003; Positive Prompt</div>
                    <div class="lb-prompt-box">${escapeHtml(pp.positive_prompt)}</div>
                </div>
            `;
        }
        if (pp.negative_prompt) {
            html += `
                <div class="lb-meta-section">
                    <div class="lb-prompt-label">&#10007; Negative Prompt</div>
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
            html += '<div class="lb-meta-section"><h4>&#9881; Settings</h4>';
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
        html += '<div class="lb-meta-section"><h4>&#128196; EXIF</h4>';
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
