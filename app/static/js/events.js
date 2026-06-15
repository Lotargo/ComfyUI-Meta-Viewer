import { dom, galleryActive, setViewModeValue, setGalleryActive, images, activeIndex, sessions, activeSessionId, currentFolderId, currentPage, totalImages, allLoaded, detailCache, scrollObserver, setImages, setActiveIndex, setSessions, setActiveSessionId, setCurrentFolderId, setCurrentPage, setTotalImages, setAllLoaded, setDetailCache, setScrollObserver, saveState } from './state.js';
import { loadFromFiles, loadFromPaths, scanFolder } from './api.js';
import { renderSidebar } from './sidebar.js';

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
    dom.btnViewGrid.addEventListener('click', () => setViewMode('grid'));
    dom.btnViewGallery.addEventListener('click', () => setViewMode('gallery'));

    document.getElementById('btn-clear').addEventListener('click', () => {
        if (scrollObserver) scrollObserver.disconnect();
        setImages([]);
        setSessions([]);
        setActiveSessionId(0);
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
            <div class="icon">&#128444;</div>
            <h2>Drop images here</h2>
            <p>or use buttons above / paste path</p>
            <div class="hint">Supports PNG, JPG, WEBP, BMP, TIFF</div>
        </div>`;
    });

    document.querySelectorAll('.btn-paste').forEach(el => {
        el.addEventListener('click', async () => {
            const input = prompt('Enter file/folder path(s), separated by newlines:');
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

    document.getElementById('btn-paste').addEventListener('click', function() {
        const input = prompt('Enter file/folder path:');
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
}

export function setViewMode(mode) {
    setViewModeValue(mode);
    dom.btnViewList.classList.toggle('active', mode === 'list');
    dom.btnViewGrid.classList.toggle('active', mode === 'grid');
    dom.btnViewGallery.classList.toggle('active', mode === 'gallery');
    dom.imageList.classList.toggle('grid-mode', mode === 'grid');
    setGalleryActive(mode === 'gallery');
    saveState();
    if (galleryActive) {
        import('./gallery.js').then(m => m.renderGallery());
    } else {
        renderSidebar();
    }
}