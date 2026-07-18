import {
    dom,
    galleryActive,
    setViewModeValue,
    setGalleryActive,
    images,
    activeIndex,
    viewMode,
    currentCollection,
    setActiveSidebarTab,
    saveState,
    clearStoredPreferences,
} from './state.js';
import { loadFromFiles, loadFromPaths, scanFolder, invalidateApiCache } from './api.js';
import { renderSidebar } from './features/sidebar.js';
import { customConfirm, customPrompt } from './utils.js';

function syncViewerContext() {
    if (!dom.viewerCollectionName) return;
    dom.viewerCollectionName.textContent = viewMode === 'upload'
        ? 'Drop zone'
        : (currentCollection.name || 'Gallery');
}

function initHeaderMenus() {
    const menus = [...document.querySelectorAll('[data-header-menu]')];
    if (!menus.length) return;

    const closeMenu = (menu, { restoreFocus = false } = {}) => {
        const trigger = menu.querySelector('[data-header-menu-trigger]');
        const dropdown = menu.querySelector('.header-dropdown');
        menu.classList.remove('open');
        trigger?.setAttribute('aria-expanded', 'false');
        if (dropdown) dropdown.hidden = true;
        if (restoreFocus) trigger?.focus();
    };

    const closeAll = except => {
        menus.forEach(menu => {
            if (menu !== except) closeMenu(menu);
        });
    };

    menus.forEach(menu => {
        const trigger = menu.querySelector('[data-header-menu-trigger]');
        const dropdown = menu.querySelector('.header-dropdown');
        if (!trigger || !dropdown) return;

        trigger.addEventListener('click', event => {
            event.stopPropagation();
            const willOpen = dropdown.hidden;
            closeAll(menu);
            dropdown.hidden = !willOpen;
            menu.classList.toggle('open', willOpen);
            trigger.setAttribute('aria-expanded', String(willOpen));
        });

        dropdown.addEventListener('click', event => event.stopPropagation());
        dropdown.querySelectorAll('[data-header-menu-action]').forEach(action => {
            action.addEventListener('click', () => closeMenu(menu));
            if (action.tagName !== 'LABEL') return;
            action.addEventListener('keydown', event => {
                if (event.key !== 'Enter' && event.key !== ' ') return;
                event.preventDefault();
                action.click();
            });
        });
    });

    document.addEventListener('click', () => closeAll());
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        const openMenu = menus.find(menu => menu.classList.contains('open'));
        if (openMenu) closeMenu(openMenu, { restoreFocus: true });
    });
}

export async function renderCurrentContent() {
    syncViewerContext();
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
    const showAlbums = tab === 'albums';
    dom.tabFolders?.classList.toggle('active', showFolders);
    dom.tabAlbums?.classList.toggle('active', showAlbums);
    dom.tabImages?.classList.toggle('active', !showFolders && !showAlbums);
    dom.panelFolders?.classList.toggle('active', showFolders);
    dom.panelAlbums?.classList.toggle('active', showAlbums);
    dom.panelImages?.classList.toggle('active', !showFolders && !showAlbums);
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
    initHeaderMenus();
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
            if (!response.ok) throw new Error(data.error || 'Folder picker is unavailable');
            if (data.path) {
                await scanFolder(data.path);
            }
        } catch (err) {
            console.warn('Using manual folder path fallback:', err);
            const input = await customPrompt('Open Folder', 'Enter folder path:');
            const path = input?.trim();
            if (path) await scanFolder(path);
        }
    });

    dom.btnViewUpload?.addEventListener('click', () => setViewMode('upload'));
    dom.btnViewList.addEventListener('click', () => setViewMode('list'));
    dom.btnViewGallery.addEventListener('click', () => setViewMode('gallery'));


    dom.btnResetIndex?.addEventListener('click', () => performReset({
        factoryReset: false,
        title: 'Reset Index',
        message: 'Delete the SQLite index and all generated caches? Saved source folders will be reindexed. Source files stay untouched, but virtual albums, favorites, ratings, tags, notes, and uploaded originals stored only in CMV will be permanently deleted.',
    }));

    dom.btnFactoryReset?.addEventListener('click', () => performReset({
        factoryReset: true,
        title: 'Factory Reset',
        message: 'Delete the index, virtual library organization, generated caches, saved source folders, uploaded originals, and browser preferences? Source files in scanned folders stay untouched. This cannot be undone.',
    }));

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
    dom.tabAlbums?.addEventListener('click', () => switchSidebarTab('albums'));
    dom.tabImages?.addEventListener('click', () => switchSidebarTab('images'));

    dom.foldersViewBtn?.addEventListener('click', async () => {
        const { foldersViewMode, setFoldersViewMode } = await import('./state.js');
        const { renderFoldersList } = await import('./features/sidebar.js');
        setFoldersViewMode(foldersViewMode === 'list' ? 'tile' : 'list');
        saveState();
        await renderFoldersList();
    });

    dom.albumsViewBtn?.addEventListener('click', async () => {
        const { albumsViewMode, setAlbumsViewMode } = await import('./state.js');
        const { renderAlbumsList } = await import('./features/sidebar.js');
        setAlbumsViewMode(albumsViewMode === 'list' ? 'tile' : 'list');
        saveState();
        await renderAlbumsList();
    });
}

async function performReset({ factoryReset, title, message }) {
    const ok = await customConfirm(title, message);
    if (!ok) return;

    const { showLoading, showError } = await import('./utils.js');
    const endpoint = factoryReset ? '/api/factory-reset' : '/api/reset-index';
    const confirm = factoryReset ? 'factory-reset' : 'reset-index';
    showLoading(factoryReset ? 'Restoring factory defaults...' : 'Recreating index...');

    try {
        const response = await fetch(endpoint, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ confirm }),
        });
        const data = await response.json();
        if (!response.ok || data.error) {
            showError(`${title} failed: ${data.error || response.statusText}`);
            return;
        }

        invalidateApiCache();
        if (factoryReset) clearStoredPreferences();
        window.location.reload();
    } catch (error) {
        showError(`${title} failed: ${error.message}`);
    }
}

export function setViewMode(mode, { render = true, persist = true } = {}) {
    const normalized = mode === 'list' ? 'list' : (mode === 'upload' ? 'upload' : 'gallery');
    setViewModeValue(normalized);
    setGalleryActive(normalized === 'gallery');
    dom.btnViewList.classList.toggle('active', normalized === 'list');
    dom.btnViewGallery.classList.toggle('active', normalized === 'gallery');
    dom.btnViewUpload?.classList.toggle('active', normalized === 'upload');
    syncViewerContext();
    if (persist) saveState();
    if (render) renderCurrentContent();
}

export async function switchSidebarTab(tab, { render = true, load = true, persist = true } = {}) {
    const normalized = ['folders', 'albums'].includes(tab) ? tab : 'images';
    setActiveSidebarTab(normalized);
    applySidebarTabClasses(normalized);
    if (persist) saveState();

    if (!render) return;
    if (normalized === 'folders') {
        const { renderFoldersList } = await import('./features/sidebar.js');
        await renderFoldersList();
        return;
    }

    if (normalized === 'albums') {
        const { renderAlbumsList } = await import('./features/sidebar.js');
        await renderAlbumsList();
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
