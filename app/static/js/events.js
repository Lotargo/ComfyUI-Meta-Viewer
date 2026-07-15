import { dom, galleryActive, setViewModeValue, setGalleryActive, images, activeIndex, scrollObserver, setImages, setActiveIndex, setCurrentFolderId, setCurrentPage, setTotalImages, setAllLoaded, setDetailCache, saveState } from './state.js';
import { loadFromFiles, loadFromPaths, scanFolder } from './api.js';
import { renderSidebar } from './features/sidebar.js';
import { customConfirm, customPrompt } from './utils.js';

export function initEvents() {
    document.addEventListener('dragover', e => e.preventDefault());
    document.addEventListener('drop', e => {
        e.preventDefault();
        if (e.dataTransfer.files.length) loadFromFiles(e.dataTransfer.files);
    });

    dom.fileInput.addEventListener('change', () => {
        if (dom.fileInput.files.length) loadFromFiles(dom.fileInput.files);
        dom.fileInput.value = '';
    });

    dom.addFileInput.addEventListener('change', () => {
        if (dom.addFileInput.files.length) loadFromFiles(dom.addFileInput.files);
        dom.addFileInput.value = '';
    });

    dom.folderInput.addEventListener('change', () => {
        if (dom.folderInput.files.length) {
            const paths = Array.from(dom.folderInput.files).map(f => f.webkitRelativePath || f.name);
            const dir = paths[0]?.split('/')[0];
            if (dir) scanFolder(dir);
        }
        dom.folderInput.value = '';
    });

    dom.btnViewList.addEventListener('click', () => setViewMode('list'));
    dom.btnViewGallery.addEventListener('click', () => setViewMode('gallery'));

    document.getElementById('btn-clear').addEventListener('click', async () => {
        if (scrollObserver) scrollObserver.disconnect();
        setImages([]);
        setActiveIndex(-1);
        setGalleryActive(false);
        setCurrentFolderId(null);
        setCurrentPage(0);
        setTotalImages(0);
        setAllLoaded(false);
        setDetailCache({});
        dom.folderNameEl.textContent = '';
        sessionStorage.removeItem('cmv_state');
        renderSidebar();
        dom.contentArea.innerHTML = `<div class="drop-zone anim-scale-in" id="drop-zone">
            <div class="icon">
                <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
            </div>
            <h2>Drop images here</h2>
            <p>or use buttons above / paste path</p>
            <div class="hint">Supports PNG, JPG, WEBP, BMP, TIFF</div>
        </div>`;
    });

    document.getElementById('btn-hard-reset')?.addEventListener('click', async () => {
        const ok = await customConfirm('Hard Reset', 'Are you sure you want to perform a hard reset? This will clear all folders, database entries, and thumbnail cache.');
        if (!ok) {
            return;
        }

        if (scrollObserver) scrollObserver.disconnect();
        
        const { showLoading, showError } = await import('./utils.js');
        const { showToast } = await import('./state.js');
        showLoading('Resetting database and cache...');

        try {
            const resp = await fetch('/api/reset', { method: 'POST' });
            const data = await resp.json();
            if (data.error) {
                showError('Reset failed: ' + data.error);
                return;
            }

            setImages([]);
            setActiveIndex(-1);
            setGalleryActive(false);
            setCurrentFolderId(null);
            setCurrentPage(0);
            setTotalImages(0);
            setAllLoaded(false);
            setDetailCache({});
            dom.folderNameEl.textContent = '';
            sessionStorage.removeItem('cmv_state');
            
            renderSidebar();
            try {
                const { renderFoldersList } = await import('./features/sidebar.js');
                await renderFoldersList();
            } catch (e) {
                console.error(e);
            }
            
            dom.contentArea.innerHTML = `<div class="drop-zone anim-scale-in" id="drop-zone">
                <div class="icon">
                    <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                </div>
                <h2>Drop images here</h2>
                <p>or use buttons above / paste path</p>
                <div class="hint">Supports PNG, JPG, WEBP, BMP, TIFF</div>
            </div>`;
            
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
            if (paths.length) {
                if (paths.length === 1 && paths[0].length > 3) {
                    await scanFolder(paths[0]);
                } else {
                    await loadFromPaths(paths);
                }
            }
        });
    });

    document.getElementById('btn-paste').addEventListener('click', async function() {
        const input = await customPrompt('Paste Path', 'Enter file/folder path:');
        if (!input) return;
        const path = input.trim();
        if (path) scanFolder(path);
    });

    document.addEventListener('paste', e => {
        if (dom.lightbox.classList.contains('open')) return;
        const text = e.clipboardData?.getData('text');
        if (text) {
            const paths = text.split('\n').map(s => s.trim()).filter(s => s && !s.startsWith('http'));
            if (paths.length) {
                loadFromPaths(paths);
            }
        }
    });

    // Sidebar tabs switching
    document.getElementById('tab-folders')?.addEventListener('click', () => switchSidebarTab('folders'));
    document.getElementById('tab-images')?.addEventListener('click', () => switchSidebarTab('images'));
}

export function setViewMode(mode) {
    setViewModeValue(mode);
    dom.btnViewList.classList.toggle('active', mode === 'list');
    dom.btnViewGallery.classList.toggle('active', mode === 'gallery');
    setGalleryActive(mode === 'gallery');
    saveState();
    if (galleryActive) {
        import('./gallery.js').then(m => m.renderGallery());
    } else {
        renderSidebar();
        import('./meta-view.js').then(m => m.renderMeta(images[activeIndex]));
    }
}

export async function switchSidebarTab(tab) {
    const foldersTab = document.getElementById('tab-folders');
    const imagesTab = document.getElementById('tab-images');
    const foldersPanel = document.getElementById('panel-folders');
    const imagesPanel = document.getElementById('panel-images');
    
    if (!foldersTab || !imagesTab || !foldersPanel || !imagesPanel) return;
    
    if (tab === 'folders') {
        foldersTab.classList.add('active');
        imagesTab.classList.remove('active');
        foldersPanel.classList.add('active');
        imagesPanel.classList.remove('active');
        const { renderFoldersList } = await import('./features/sidebar.js');
        await renderFoldersList();
    } else {
        imagesTab.classList.add('active');
        foldersTab.classList.remove('active');
        imagesPanel.classList.add('active');
        foldersPanel.classList.remove('active');
        const { renderSidebar } = await import('./features/sidebar.js');
        renderSidebar();
    }
}
