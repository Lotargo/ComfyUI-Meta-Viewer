/**
 * Keyboard shortcuts handler
 */

import { images, sidebarImages, activeIndex, detailCache, dom, totalImages, currentFolderId, showToast } from '../state.js';
import { toggleSidebar } from './sidebar.js';
import { copyText } from '../utils.js';

const shortcuts = {
    'arrowleft': { description: 'Previous image', action: prevImage },
    'arrowright': { description: 'Next image', action: nextImage },
    'escape': { description: 'Close lightbox', action: closeLightbox },
    'b': { description: 'Toggle sidebar', action: toggleSidebar },
    '/': { description: 'Focus search', action: focusSearch, preventDefault: true },
    '?': { description: 'Show shortcuts', action: toggleShortcuts },
    'c': { description: 'Copy metadata', action: copyMetadata },
    '1': { description: 'Summary tab', action: () => switchTab('summary') },
    '2': { description: 'Workflow tab', action: () => switchTab('workflow') },
    '3': { description: 'Raw tab', action: () => switchTab('raw') },
    'f': { description: 'Toggle fullscreen', action: toggleFullscreen },
    '+': { description: 'Zoom in', action: zoomIn },
    '-': { description: 'Zoom out', action: zoomOut },
    '0': { description: 'Reset zoom', action: resetZoom },
    'm': { description: 'Toggle metadata panel', action: toggleMetaPanel }
};

export function initKeyboardShortcuts() {
    initHelpCenter();
    document.addEventListener('keydown', handleKeydown);
}

function handleKeydown(e) {
    if (e.key === 'Escape' && document.getElementById('shortcuts-overlay')?.classList.contains('open')) {
        e.preventDefault();
        toggleShortcuts(false);
        return;
    }

    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
            e.target.blur();
        }
        return;
    }

    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        focusSearch();
        return;
    }

    if (e.ctrlKey && e.key === 'c') {
        return;
    }

    const key = e.key.toLowerCase();
    const shortcut = shortcuts[key];

    if (shortcut) {
        if (shortcut.preventDefault) {
            e.preventDefault();
        }
        shortcut.action();
    }
}

function prevImage() {
    if (dom.lightbox.classList.contains('open')) {
        import('../lightbox.js').then(m => m.prevLightbox());
        return;
    }
    if (activeIndex > 0) {
        import('./sidebar.js').then(m => m.selectImage(activeIndex - 1));
    }
}

function nextImage() {
    if (dom.lightbox.classList.contains('open')) {
        import('../lightbox.js').then(m => m.nextLightbox());
        return;
    }
    const isImagesTab = document.getElementById('tab-images')?.classList.contains('active');
    const currentList = isImagesTab ? sidebarImages : images;
    if (activeIndex < currentList.length - 1) {
        import('./sidebar.js').then(m => m.selectImage(activeIndex + 1));
    }
}

function closeLightbox() {
    dom.lightbox.classList.remove('open');
}

function focusSearch() {
    document.getElementById('search-input')?.focus();
}

function toggleShortcuts(forceOpen) {
    const overlay = document.getElementById('shortcuts-overlay');
    if (!overlay) return;
    const shouldOpen = forceOpen === undefined ? !overlay.classList.contains('open') : Boolean(forceOpen);
    overlay.classList.toggle('open', shouldOpen);
    if (shouldOpen) {
        refreshDiagnostics();
    }
}

function copyMetadata() {
    const isImagesTab = document.getElementById('tab-images')?.classList.contains('active');
    const currentList = isImagesTab ? sidebarImages : images;
    const img = currentList[activeIndex];
    if (!img) return;

    const detail = (img.id && detailCache[img.id]) || img;
    if (detail) {
        copyText(JSON.stringify(detail, null, 2));
    }
}

function switchTab(tabName) {
    const tab = document.querySelector(`.content-tab[data-tab="${tabName}"]`);
    if (tab) {
        tab.click();
    }
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

function zoomIn() {
    import('../lightbox.js').then(m => m.zoomIn());
}

function zoomOut() {
    import('../lightbox.js').then(m => m.zoomOut());
}

function resetZoom() {
    import('../lightbox.js').then(m => m.resetZoom());
}

function toggleMetaPanel() {
    import('../lightbox.js').then(m => m.toggleMetaPanel());
}

export function getShortcutsList() {
    return Object.entries(shortcuts).map(([key, { description }]) => ({
        key,
        description
    }));
}

function initHelpCenter() {
    const overlay = document.getElementById('shortcuts-overlay');
    if (!overlay) return;

    overlay.innerHTML = `
        <div class="shortcuts-modal" role="dialog" aria-modal="true" aria-labelledby="help-center-title">
            <div class="shortcuts-header">
                <div>
                    <h3 id="help-center-title">Help Center</h3>
                    <p class="help-subtitle">Shortcuts, metadata notes, cutout workflow, local storage rules, and quick diagnostics.</p>
                </div>
                <button class="icon-btn" id="shortcuts-close" title="Close help">
                    <svg viewBox="0 0 24 24" width="18" height="18" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
                </button>
            </div>
            <div class="help-tabs" role="tablist" aria-label="Help center sections">
                <button class="help-tab active" type="button" data-help-tab="shortcuts" role="tab" aria-selected="true">Shortcuts</button>
                <button class="help-tab" type="button" data-help-tab="workflow" role="tab" aria-selected="false">Workflow</button>
                <button class="help-tab" type="button" data-help-tab="storage" role="tab" aria-selected="false">Storage</button>
                <button class="help-tab" type="button" data-help-tab="diagnostics" role="tab" aria-selected="false">Diagnostics</button>
            </div>
            <div class="shortcuts-content">
                <section class="help-panel active" data-help-panel="shortcuts" role="tabpanel">
                    <div class="help-grid">
                        <div class="shortcut-group">
                            <h4>Navigation</h4>
                            <div class="shortcut-row"><span><kbd>Left</kbd> <kbd>Right</kbd></span><span>Previous / next image</span></div>
                            <div class="shortcut-row"><span><kbd>B</kbd></span><span>Toggle sidebar</span></div>
                            <div class="shortcut-row"><span><kbd>/</kbd></span><span>Focus search</span></div>
                            <div class="shortcut-row"><span><kbd>Esc</kbd></span><span>Close overlays</span></div>
                        </div>
                        <div class="shortcut-group">
                            <h4>Metadata</h4>
                            <div class="shortcut-row"><span><kbd>1</kbd></span><span>Summary tab</span></div>
                            <div class="shortcut-row"><span><kbd>2</kbd></span><span>Workflow graph tab</span></div>
                            <div class="shortcut-row"><span><kbd>3</kbd></span><span>Raw chunks tab</span></div>
                            <div class="shortcut-row"><span><kbd>C</kbd></span><span>Copy active metadata</span></div>
                        </div>
                        <div class="shortcut-group">
                            <h4>Lightbox</h4>
                            <div class="shortcut-row"><span><kbd>+</kbd> <kbd>-</kbd></span><span>Zoom in / out</span></div>
                            <div class="shortcut-row"><span><kbd>0</kbd></span><span>Reset zoom</span></div>
                            <div class="shortcut-row"><span><kbd>M</kbd></span><span>Toggle metadata panel</span></div>
                            <div class="shortcut-row"><span><kbd>?</kbd></span><span>Open this Help Center</span></div>
                        </div>
                    </div>
                </section>
                <section class="help-panel" data-help-panel="workflow" role="tabpanel">
                    <div class="help-grid">
                        <div class="shortcut-group">
                            <h4>What CMV Reads</h4>
                            <p class="help-text">ComfyUI Meta Viewer extracts generation metadata embedded inside image files: prompts, sampler settings, models, LoRA entries, EXIF fields, raw chunks, and ComfyUI workflow data when present.</p>
                        </div>
                        <div class="shortcut-group">
                            <h4>Workflow Graph</h4>
                            <p class="help-text">The Workflow tab reconstructs node information from embedded ComfyUI metadata. Use it to inspect which nodes, models, prompts, and post-processing steps were involved in generation.</p>
                        </div>
                        <div class="shortcut-group">
                            <h4>Missing Metadata</h4>
                            <p class="help-text">Some images have no embedded workflow or prompt chunks. CMV still shows file info and available EXIF/raw metadata, but generation details may be empty.</p>
                        </div>
                        <div class="shortcut-group">
                            <h4>Object Cutout</h4>
                            <p class="help-text">Open an image in the lightbox and use Select Object to create a transparent PNG. The MVP uses a lightweight local background estimate, so simple subjects work best and source images stay unchanged.</p>
                        </div>
                    </div>
                </section>
                <section class="help-panel" data-help-panel="storage" role="tabpanel">
                    <div class="help-grid">
                        <div class="shortcut-group">
                            <h4>Scanned Folders</h4>
                            <p class="help-text">Opening a folder stores the folder path and extracted metadata in the local SQLite database. Deleting a folder or image from CMV removes the database entry, not the original file on disk.</p>
                        </div>
                        <div class="shortcut-group">
                            <h4>Uploaded Files</h4>
                            <p class="help-text">Files added through Open Files or drag-and-drop are stored inside the app database as originals, so they can be previewed later even without a source folder path.</p>
                        </div>
                        <div class="shortcut-group">
                            <h4>Cache And Reset</h4>
                            <p class="help-text">Thumbnails and object cutouts are cached on disk for speed. Hard Reset clears folders, image records, thumbnail cache, and cutout cache, but it does not delete source images from scanned folders.</p>
                        </div>
                    </div>
                </section>
                <section class="help-panel" data-help-panel="diagnostics" role="tabpanel">
                    <div class="diagnostics-header">
                        <p class="help-text">Use this when something looks stale, paths are confusing, or you need to share local app state while debugging.</p>
                        <button class="btn btn-sm" id="copy-diagnostics">Copy Debug Info</button>
                    </div>
                    <div class="diagnostics-grid">
                        <div class="diagnostic-card"><span>Folders</span><strong id="diag-folders">-</strong></div>
                        <div class="diagnostic-card"><span>Images</span><strong id="diag-images">-</strong></div>
                        <div class="diagnostic-card"><span>Uploads</span><strong id="diag-uploads">-</strong></div>
                        <div class="diagnostic-card"><span>Thumbnails</span><strong id="diag-thumbnails">-</strong></div>
                        <div class="diagnostic-card"><span>Cutouts</span><strong id="diag-cutouts">-</strong></div>
                        <div class="diagnostic-card"><span>Loaded Now</span><strong id="diag-loaded">-</strong></div>
                    </div>
                    <div class="diagnostics-paths">
                        <div><span>Database</span><code id="diag-db-path">-</code></div>
                        <div><span>Uploads</span><code id="diag-upload-dir">-</code></div>
                        <div><span>Thumbnail Cache</span><code id="diag-thumb-dir">-</code></div>
                        <div><span>Cutout Cache</span><code id="diag-cutout-dir">-</code></div>
                    </div>
                </section>
            </div>
        </div>
    `;

    document.addEventListener('click', e => {
        if (e.target.closest('#shortcuts-btn')) {
            e.preventDefault();
            toggleShortcuts(true);
        }
    });
    document.getElementById('shortcuts-close')?.addEventListener('click', () => toggleShortcuts(false));
    overlay.addEventListener('click', e => {
        if (e.target === overlay) toggleShortcuts(false);
    });

    overlay.querySelectorAll('.help-tab').forEach(tab => {
        tab.addEventListener('click', () => activateHelpTab(tab.dataset.helpTab));
    });

    document.getElementById('copy-diagnostics')?.addEventListener('click', copyDiagnostics);
}

function activateHelpTab(tabName) {
    document.querySelectorAll('.help-tab').forEach(tab => {
        const active = tab.dataset.helpTab === tabName;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', String(active));
    });
    document.querySelectorAll('.help-panel').forEach(panel => {
        panel.classList.toggle('active', panel.dataset.helpPanel === tabName);
    });
    if (tabName === 'diagnostics') refreshDiagnostics();
}

async function getDiagnostics() {
    const resp = await fetch('/api/diagnostics');
    if (!resp.ok) throw new Error('diagnostics request failed');
    const data = await resp.json();
    return {
        ...data,
        loaded_images: images.length,
        total_images: totalImages,
        active_index: activeIndex,
        current_folder_id: currentFolderId,
        view: document.querySelector('.view-toggle button.active')?.id || 'unknown',
    };
}

async function refreshDiagnostics() {
    const setText = (id, value) => {
        const el = document.getElementById(id);
        if (el) el.textContent = value;
    };

    try {
        const data = await getDiagnostics();
        setText('diag-folders', data.folders);
        setText('diag-images', data.images);
        setText('diag-uploads', data.uploads);
        setText('diag-thumbnails', data.thumbnail_count);
        setText('diag-cutouts', data.cutout_count);
        setText('diag-loaded', `${data.loaded_images}/${data.total_images || data.loaded_images}`);
        setText('diag-db-path', data.db_path || '-');
        setText('diag-upload-dir', data.upload_dir || '-');
        setText('diag-thumb-dir', data.thumbnail_dir || '-');
        setText('diag-cutout-dir', data.cutout_dir || '-');
    } catch (e) {
        setText('diag-db-path', 'Diagnostics unavailable');
    }
}

async function copyDiagnostics() {
    try {
        const data = await getDiagnostics();
        await copyText(JSON.stringify(data, null, 2));
        showToast('Debug info copied');
    } catch (e) {
        showToast('Diagnostics unavailable');
    }
}
