import { saveState, dom, images, setImages, setTotalImages, setAllLoaded, setCurrentPage, activeIndex, setActiveIndex, currentFolderId, setCurrentFolderId } from './state.js';
import { initEvents, setViewMode } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar, initSidebarResize, toggleSidebar, renderFoldersList } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';

async function restoreState() {
    try {
        await renderFoldersList();
        const saved = sessionStorage.getItem('cmv_state');
        if (!saved) return;

        const state = JSON.parse(saved);
        if (!state.folderId) {
            return;
        }

        setCurrentFolderId(state.folderId);
        if (state.viewMode) setViewMode(state.viewMode);
        if (state.folderName) dom.folderNameEl.textContent = state.folderName;

        setImages([]);
        let page = 1;
        let total = 0;
        do {
            const resp = await fetch(`/api/images?folder_id=${state.folderId}&page=${page}&per_page=100`);
            const data = await resp.json();
            if (data.images && data.images.length) {
                images.push(...data.images);
                total = data.total || 0;
                page++;
            } else {
                break;
            }
        } while (images.length < total);

        setTotalImages(images.length);
        setAllLoaded(true);
        setCurrentPage(page - 1);

        if (state.activeIndex >= 0 && state.activeIndex < images.length) {
            setActiveIndex(state.activeIndex);
        } else if (images.length > 0) {
            setActiveIndex(0);
        }

        renderSidebar();

        if (activeIndex >= 0 && images[activeIndex]) {
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
        }
        if (images.length > 0) {
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
