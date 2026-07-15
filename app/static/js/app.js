import {
    dom,
    loadState,
    resetRuntimeState,
    setActiveIndex,
    setAllLoaded,
    setCurrentFolderId,
    setCurrentPage,
    setFolders,
    setImages,
    setIsLoading,
    setSidebarAllLoaded,
    setSidebarImages,
    setSidebarPage,
    setSidebarTotalImages,
    setTotalImages,
} from './state.js';
import { initEvents, setViewMode, switchSidebarTab } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar, initSidebarResize, toggleSidebar, renderFoldersList } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';
import { initCentralCollectionShortcuts } from './central-shortcuts.js';
import { loadBootstrap } from './api.js';

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

    // Navigation is intentionally not restored between page loads.
    setViewMode('gallery', { render: false });
    await switchSidebarTab('images', { render: false, load: false });

    try {
        const data = await loadBootstrap();
        const folderList = data.folders || [];
        const globalPage = data.global_images || {};
        const folderPage = data.folder_images || {};
        const defaultFolder = data.default_folder || null;

        setFolders(folderList);
        setSidebarImages(globalPage.images || []);
        setSidebarTotalImages(globalPage.total || 0);
        setSidebarPage(globalPage.page || 1);
        setSidebarAllLoaded((globalPage.images || []).length >= (globalPage.total || 0));

        if (defaultFolder) {
            setCurrentFolderId(defaultFolder.id);
            dom.folderNameEl.textContent = defaultFolder.name || '';
            setImages(folderPage.images || []);
            setTotalImages(folderPage.total || 0);
            setCurrentPage(folderPage.page || 1);
            setAllLoaded((folderPage.images || []).length >= (folderPage.total || 0));
            setActiveIndex((folderPage.images || []).length ? 0 : -1);
        } else {
            setCurrentFolderId(null);
            dom.folderNameEl.textContent = '';
            setImages([]);
            setTotalImages(0);
            setCurrentPage(0);
            setAllLoaded(true);
            setActiveIndex(-1);
        }

        await renderFoldersList(folderList);
        renderSidebar();
        const { renderGallery } = await import('./gallery.js');
        renderGallery();
    } catch (error) {
        console.error('Application bootstrap failed:', error);
        await renderFoldersList([]);
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
bootstrapApplication();

dom.sidebarToggle?.addEventListener('click', toggleSidebar);
