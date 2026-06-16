import { saveState, dom, images, setImages, setTotalImages, setAllLoaded, setCurrentPage, activeIndex, setActiveIndex, currentFolderId, setCurrentFolderId } from './state.js';
import { initEvents, setViewMode } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar, initSidebarResize, toggleSidebar, renderFoldersList } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';

async function restoreState() {
    try {
        const saved = sessionStorage.getItem('cmv_state');
        if (!saved) {
            await renderFoldersList();
            return;
        }

        const state = JSON.parse(saved);
        if (!state.folderId) {
            await renderFoldersList();
            return;
        }

        setCurrentFolderId(state.folderId);
        if (state.folderName) dom.folderNameEl.textContent = state.folderName;
        await renderFoldersList();
        if (state.viewMode) setViewMode(state.viewMode);

        setImages([]);
        let page = 1;
        let total = 0;
        const restoredImages = [];
        do {
            const resp = await fetch(`/api/images?folder_id=${state.folderId}&page=${page}&per_page=100`);
            const data = await resp.json();
            if (data.images && data.images.length) {
                restoredImages.push(...data.images);
                total = data.total || 0;
                page++;
            } else {
                break;
            }
        } while (restoredImages.length < total);

        setImages(restoredImages);
        setTotalImages(total || restoredImages.length);
        setAllLoaded(restoredImages.length >= (total || restoredImages.length));
        setCurrentPage(page - 1);

        if (state.activeIndex >= 0 && state.activeIndex < restoredImages.length) {
            setActiveIndex(state.activeIndex);
        } else if (restoredImages.length > 0) {
            setActiveIndex(0);
        }

        if (state.viewMode === 'gallery') {
            const { renderGallery } = await import('./gallery.js');
            renderGallery();
        } else {
            renderSidebar();
            if (activeIndex >= 0 && images[activeIndex]) {
                const { renderMeta } = await import('./meta-view.js');
                renderMeta(images[activeIndex]);
            }
        }

        if (restoredImages.length > 0) {
            const { switchSidebarTab } = await import('./events.js');
            switchSidebarTab('images');
        }
    } catch (e) {
        console.warn('State restore failed:', e);
    }
}

// Initialize
initEvents();
initLightboxEvents();
initSidebarResize();
initSearch();
initKeyboardShortcuts();
restoreState();

// Sidebar toggle
document.getElementById('sidebar-toggle')?.addEventListener('click', toggleSidebar);
