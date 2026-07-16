import {
    dom,
    galleryActive,
    setViewModeValue,
    setGalleryActive,
    images,
    activeIndex,
    viewMode,
    refreshCacheBuster,
    setActiveSidebarTab,
    setSidebarImages,
    setSidebarTotalImages,
    setSidebarPage,
    setSidebarAllLoaded,
    setFolders,
    resetRuntimeState,
} from './state.js';
import { loadFromFiles, loadFromPaths, scanFolder, invalidateApiCache } from './api.js';
import { renderSidebar } from './features/sidebar.js';
import { customConfirm, customPrompt } from './utils.js';

function renderEmptyContent() {
    dom.contentArea.innerHTML = `
        <div class="empty-state" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-dim);">
            <div class="empty-state-icon" style="margin-bottom: 16px;">
                <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
            </div>
            <p>No images found</p>
        </div>
    `;
}

async function renderCurrentContent() {
    if (viewMode === 'upload') {
        const { renderUploadView } = await import('./meta-view.js');
        renderUploadView();
        return;
    }
    if (galleryActive) {
        const { renderGallery } = await import('./gallery.js');
        renderGallery();
        return;
    }
    const { renderImageMeta } = await import('./detail-loader.js');
    await renderImageMeta(images[activeIndex] || images[0] || null);
}

function applySidebarTabClasses(tab) {
    const showFolders = tab === 'folders';
    dom.tabFolders?.classList.toggle('active', showFolders);
    dom.tabImages?.classList.toggle('active', !showFolders);
    dom.panelFolders?.classList.toggle('active', showFolders);
    dom.panelImages?.classList.toggle('active', !showFolders);
}

async function scanDragAndDropItems(items) {
    /* eslint-disable no-await-in-loop */
    const files = [];
    const queue = [];
    for (let i = 0; i < items.length; i++) {
        const item = items[i];
        if (item.kind === 'file') {
            const entry = item.webkitGetAsEntry();
            if (entry) {
                queue.push(entry);
            }
        }
    }

    const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'];

    while (queue.length > 0) {
        const entry = queue.shift();
        if (entry.isFile) {
            const file = await new Promise((resolve) => {
                entry.file(resolve, () => resolve(null));
            });
            if (file) {
                const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
                if (SUPPORTED_EXTENSIONS.includes(ext)) {
                    files.push(file);
                }
            }
        } else if (entry.isDirectory) {
            const reader = entry.createReader();
            const readBatch = () => {
                return new Promise((resolve) => {
                    reader.readEntries(resolve, () => resolve([]));
                });
            };
            let batch;
            do {
                batch = await readBatch();
                if (batch && batch.length > 0) {
                    queue.push(...batch);
                }
            } while (batch && batch.length > 0);
        }
    }
    return files;
}

export function initEvents() {
    let isInternalDrag = false;
    window.addEventListener('dragstart', () => { isInternalDrag = true; });
    window.addEventListener('dragend', () => { isInternalDrag = false; });

    document.addEventListener('dragover', e => e.preventDefault());
    document.addEventListener('drop', async e => {
        e.preventDefault();
        if (isInternalDrag) {
            isInternalDrag = false;
            return;
        }
        if (e.dataTransfer.items && e.dataTransfer.items.length) {
            try {
                const files = await scanDragAndDropItems(e.dataTransfer.items);
                if (files.length) {
                    loadFromFiles(files);
                } else {
                    const { showError } = await import('./utils.js');
                    showError('No supported images found in dropped files/folders');
                }
            } catch (err) {
                console.error('Error scanning dropped items:', err);
                if (e.dataTransfer.files.length) loadFromFiles(e.dataTransfer.files);
            }
        } else if (e.dataTransfer.files.length) {
            loadFromFiles(e.dataTransfer.files);
        }
    });

    dom.addFileInput.addEventListener('change', () => {
        if (dom.addFileInput.files.length) loadFromFiles(dom.addFileInput.files);
        dom.addFileInput.value = '';
    });

    dom.btnOpenFolder?.addEventListener('click', async () => {
        try {
            const response = await fetch('/api/choose-folder', { method: 'POST' });
            const data = await response.json();
            if (data.path) {
                await scanFolder(data.path);
            }
        } catch (err) {
            console.error('Error choosing folder:', err);
            const input = await customPrompt('Open Folder', 'Enter folder path:');
            const path = input?.trim();
            if (path) scanFolder(path);
        }
    });

    dom.btnViewUpload?.addEventListener('click', () => setViewMode('upload'));
    dom.btnViewList.addEventListener('click', () => setViewMode('list'));
    dom.btnViewGallery.addEventListener('click', () => setViewMode('gallery'));


    dom.btnHardReset?.addEventListener('click', async () => {
        const ok = await customConfirm('Hard Reset', 'Are you sure you want to perform a hard reset? This will clear all folders, database entries, and thumbnail cache.');
        if (!ok) return;

        const { showLoading, showError } = await import('./utils.js');
        const { showToast } = await import('./state.js');
        showLoading('Resetting database and cache...');

        try {
            const resp = await fetch('/api/reset', { method: 'POST' });
            const data = await resp.json();
            if (!resp.ok || data.error) {
                showError('Reset failed: ' + (data.error || resp.statusText));
                return;
            }

            invalidateApiCache();
            resetRuntimeState();
            setFolders([]);
            setSidebarImages([]);
            setSidebarTotalImages(0);
            setSidebarPage(0);
            setSidebarAllLoaded(true);
            refreshCacheBuster();
            setViewMode('gallery', { render: false });
            await switchSidebarTab('images', { render: false, load: false });

            renderSidebar();
            const { renderFoldersList } = await import('./features/sidebar.js');
            await renderFoldersList([]);
            renderEmptyContent();
            showToast('Database reset successfully!');
        } catch (e) {
            showError('Error during reset: ' + e.message);
        }
    });

    document.querySelectorAll('.btn-paste').forEach(el => {
        el.addEventListener('click', async () => {
            const input = await customPrompt('Paste Paths', 'Enter file/folder path(s), separated by newlines:');
            if (!input) return;
            const paths = input.split('\n').map(s => s.trim()).filter(Boolean);
            if (!paths.length) return;
            if (paths.length === 1 && paths[0].length > 3) await scanFolder(paths[0]);
            else await loadFromPaths(paths);
        });
    });

    dom.btnPaste.addEventListener('click', async () => {
        const input = await customPrompt('Paste Path', 'Enter file/folder path:');
        const path = input?.trim();
        if (path) scanFolder(path);
    });

    document.addEventListener('paste', e => {
        if (dom.lightbox.classList.contains('open')) return;
        if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') return;
        const text = e.clipboardData?.getData('text');
        if (!text) return;
        const paths = text.split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('http'));
        if (paths.length) loadFromPaths(paths);
    });

    dom.tabFolders?.addEventListener('click', () => switchSidebarTab('folders'));
    dom.tabImages?.addEventListener('click', () => switchSidebarTab('images'));

    dom.foldersViewBtn?.addEventListener('click', async () => {
        const { foldersViewMode, setFoldersViewMode } = await import('./state.js');
        const { renderFoldersList } = await import('./features/sidebar.js');
        setFoldersViewMode(foldersViewMode === 'list' ? 'tile' : 'list');
        await renderFoldersList();
    });
}

export function setViewMode(mode, { render = true } = {}) {
    const normalized = mode === 'list' ? 'list' : (mode === 'upload' ? 'upload' : 'gallery');
    setViewModeValue(normalized);
    setGalleryActive(normalized === 'gallery');
    dom.btnViewList.classList.toggle('active', normalized === 'list');
    dom.btnViewGallery.classList.toggle('active', normalized === 'gallery');
    dom.btnViewUpload?.classList.toggle('active', normalized === 'upload');
    if (render) renderCurrentContent();
}

export async function switchSidebarTab(tab, { render = true, load = true } = {}) {
    const normalized = tab === 'folders' ? 'folders' : 'images';
    setActiveSidebarTab(normalized);
    applySidebarTabClasses(normalized);

    if (!render) return;
    if (normalized === 'folders') {
        const { renderFoldersList } = await import('./features/sidebar.js');
        await renderFoldersList();
        return;
    }

    if (load) {
        const { sidebarImages } = await import('./state.js');
        if (sidebarImages.length === 0) {
            const { loadSidebarImages } = await import('./api.js');
            await loadSidebarImages({ render: false });
        }
    }
    renderSidebar();
}
