import { dom, images, setImages, setTotalImages, setAllLoaded, setCurrentPage, activeIndex, setActiveIndex, setCurrentFolderId, galleryActive, sidebarImages, setIsLoading } from './state.js';
import { initEvents, setViewMode } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar, initSidebarResize, toggleSidebar, renderFoldersList } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';

import { getFolders } from './api.js';

async function restoreState() {
    setIsLoading(true);
    try {
        const saved = sessionStorage.getItem('cmv_state');
        let folderId = null;
        let folderName = '';
        let restoredState = null;

        if (saved) {
            restoredState = JSON.parse(saved);
            folderId = restoredState.folderId;
            folderName = restoredState.folderName;
        }

        await renderFoldersList();

        // If no folderId was saved, fetch folders and use the first one
        if (!folderId) {
            try {
                const folders = await getFolders();
                if (folders && folders.length > 0) {
                    folderId = folders[0].id;
                    folderName = folders[0].name;
                }
            } catch (e) {
                console.warn('Failed to fetch folders for default selection:', e);
            }
        }

        if (folderId) {
            setCurrentFolderId(folderId);
            if (folderName) dom.folderNameEl.textContent = folderName;
            if (restoredState && restoredState.viewMode) setViewMode(restoredState.viewMode);

            setImages([]);
            let page = 1;
            let total = 0;
            const restoredImages = [];
            do {
                const resp = await fetch(`/api/images?folder_id=${folderId}&page=${page}&per_page=100`); // eslint-disable-line no-await-in-loop -- sequential pagination required
                const data = await resp.json(); // eslint-disable-line no-await-in-loop
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

            if (restoredState && restoredState.activeIndex >= 0 && restoredState.activeIndex < restoredImages.length) {
                setActiveIndex(restoredState.activeIndex);
            } else if (restoredImages.length > 0) {
                setActiveIndex(0);
            }

            if (!galleryActive) {
                renderSidebar();
                const isImagesTab = dom.tabImages?.classList.contains('active');
                const currentList = isImagesTab ? sidebarImages : images;
                if (activeIndex >= 0 && currentList[activeIndex]) {
                    const { renderMeta } = await import('./meta-view.js');
                    renderMeta(currentList[activeIndex]);
                }
            } else {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            }
        }

        // Always show the 'Images' tab in the sidebar by default
        const { switchSidebarTab } = await import('./events.js');
        await switchSidebarTab('images');

    } catch (e) {
        console.warn('State restore failed:', e);
    } finally {
        setIsLoading(false);
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
dom.sidebarToggle?.addEventListener('click', toggleSidebar);
