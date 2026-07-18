import {
    activeSidebarTab,
    currentCollection,
    dom,
    loadState,
    resetRuntimeState,
    saveState,
    setActiveIndex,
    setAllLoaded,
    setCurrentCollection,
    setCurrentPage,
    setFolders,
    setAlbums,
    setImages,
    setIsLoading,
    setSidebarAllLoaded,
    setSidebarImages,
    setSidebarPage,
    setSidebarTotalImages,
    setTotalImages,
    viewMode,
} from './state.js';
import { initEvents, renderCurrentContent, setViewMode, switchSidebarTab } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { applySidebarLayout, renderSidebar, initSidebarResize, toggleSidebar, renderAlbumsList, renderFoldersList } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';
import { initCentralCollectionShortcuts } from './central-shortcuts.js';
import { loadBootstrap } from './api.js';
import { initSorting } from './features/sorting.js';
import { initRatingFilter } from './features/rating-filter.js';

function finishBoot() {
    requestAnimationFrame(() => {
        requestAnimationFrame(() => {
            document.documentElement.classList.add('app-ready');
        });
    });
}

async function bootstrapApplication() {
    setIsLoading(true);
    resetRuntimeState();
    loadState();
    initRatingFilter();
    const preferredCollection = { type: currentCollection.type, id: currentCollection.id };

    applySidebarLayout();
    setViewMode(viewMode, { render: false, persist: false });
    await switchSidebarTab(activeSidebarTab, { render: false, load: false, persist: false });

    try {
        const data = await loadBootstrap({ preferredCollection });
        const folderList = data.folders || [];
        const albumList = data.albums || [];
        const globalPage = data.global_images || {};
        const collectionPage = data.collection_images || {};
        const defaultCollection = data.default_collection || null;

        setFolders(folderList);
        setAlbums(albumList);
        setSidebarImages(globalPage.images || []);
        setSidebarTotalImages(globalPage.total || 0);
        setSidebarPage(globalPage.page || 1);
        setSidebarAllLoaded((globalPage.images || []).length >= (globalPage.total || 0));

        if (defaultCollection) {
            setCurrentCollection(defaultCollection);
            dom.folderNameEl.textContent = defaultCollection.name || '';
            setImages(collectionPage.images || []);
            setTotalImages(collectionPage.total || 0);
            setCurrentPage(collectionPage.page || 1);
            setAllLoaded((collectionPage.images || []).length >= (collectionPage.total || 0));
            setActiveIndex((collectionPage.images || []).length ? 0 : -1);
        } else {
            setCurrentCollection({ type: 'folder', id: null, name: '' });
            dom.folderNameEl.textContent = '';
            setImages([]);
            setTotalImages(0);
            setCurrentPage(0);
            setAllLoaded(true);
            setActiveIndex(-1);
        }

        // Re-save the validated selection so a deleted folder ID cannot linger.
        saveState();

        await renderFoldersList(folderList);
        await renderAlbumsList(albumList);
        renderSidebar();
        await renderCurrentContent();
    } catch (error) {
        console.error('Application bootstrap failed:', error);
        await renderFoldersList([]);
        await renderAlbumsList([]);
        renderSidebar();
        dom.contentArea.innerHTML = `
            <div class="empty-state" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-dim); text-align: center; padding: 24px;">
                <p style="font-weight: 600; margin-bottom: 8px;">Failed to load the image library</p>
                <p style="font-size: 12px;">${String(error.message || error)}</p>
            </div>
        `;
    } finally {
        setIsLoading(false);
        finishBoot();
    }
}

// Initialize event handlers before loading data. The boot layer keeps intermediate DOM hidden.
initEvents();
initLightboxEvents();
initSidebarResize();
initSearch();
initCentralCollectionShortcuts();
initKeyboardShortcuts();
initSorting();
bootstrapApplication();

dom.sidebarToggle?.addEventListener('click', toggleSidebar);
