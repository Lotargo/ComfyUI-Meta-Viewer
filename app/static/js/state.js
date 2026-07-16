export const dom = {
    contentArea: document.getElementById('content-area'),
    imageList: document.getElementById('image-list'),
    imageCount: document.getElementById('image-count'),
    folderNameEl: document.getElementById('folder-name'),
    fileInput: document.getElementById('file-input'),
    addFileInput: document.getElementById('add-file-input'),
    folderInput: document.getElementById('folder-input'),
    toast: document.getElementById('toast'),
    btnViewList: document.getElementById('btn-view-list'),
    btnViewGallery: document.getElementById('btn-view-gallery'),
    lightbox: document.getElementById('lightbox'),
    lbTitle: document.getElementById('lb-title'),
    lbCounter: document.getElementById('lb-counter'),
    lbImg: document.getElementById('lb-img'),
    lbMeta: document.getElementById('lb-meta'),
    btnHardReset: document.getElementById('btn-hard-reset'),
    btnPaste: document.getElementById('btn-paste'),
    tabFolders: document.getElementById('tab-folders'),
    tabImages: document.getElementById('tab-images'),
    panelFolders: document.getElementById('panel-folders'),
    panelImages: document.getElementById('panel-images'),
    sidebar: document.getElementById('sidebar'),
    sidebarResize: document.getElementById('sidebar-resize'),
    sidebarToggle: document.getElementById('sidebar-toggle'),
    folderList: document.getElementById('folder-list'),
    foldersCount: document.getElementById('folders-count'),
    searchInput: document.getElementById('search-input'),
    searchSettingsBtn: document.getElementById('search-settings-btn'),
    searchSettingsDropdown: document.getElementById('search-settings-dropdown'),
    shortcutsOverlay: document.getElementById('shortcuts-overlay'),
    shortcutsClose: document.getElementById('shortcuts-close'),
    copyDiagnostics: document.getElementById('copy-diagnostics'),
    workflowGraph: document.getElementById('workflow-graph'),
    cutoutPanel: document.getElementById('cutout-panel'),
    cutoutPreview: document.getElementById('cutout-preview'),
    cutoutStatus: document.getElementById('cutout-status'),
    cutoutDownload: document.getElementById('cutout-download'),
    cutoutRegenerate: document.getElementById('cutout-regenerate'),
    cutoutClear: document.getElementById('cutout-clear'),
    cutoutClose: document.getElementById('cutout-close'),
    lbClose: document.getElementById('lb-close'),
    lbPrev: document.getElementById('lb-prev'),
    lbNext: document.getElementById('lb-next'),
    lbCopy: document.getElementById('lb-copy'),
    lbToggleMeta: document.getElementById('lb-toggle-meta'),
    lbDownload: document.getElementById('lb-download'),
    lbDelete: document.getElementById('lb-delete'),
    lbZoomIn: document.getElementById('lb-zoom-in'),
    lbZoomOut: document.getElementById('lb-zoom-out'),
    lbZoomReset: document.getElementById('lb-zoom-reset'),
    lbZoomLevel: document.getElementById('lb-zoom-level'),
    lbRotateCw: document.getElementById('lb-rotate-cw'),
    lbRotateCcw: document.getElementById('lb-rotate-ccw'),
    lbCutout: document.getElementById('lb-cutout'),
};

// Central content collection. It changes only when a folder is explicitly selected.
export let images = [];
export let activeIndex = -1;
export let currentFolderId = null;
export let currentPage = 0;
export let totalImages = 0;
export let allLoaded = true;

// Global Images sidebar collection. It never controls the central gallery.
export let sidebarImages = [];
export let sidebarPage = 0;
export let sidebarTotalImages = 0;
export let sidebarAllLoaded = true;
export let sidebarActiveImageId = null;
export let activeSidebarTab = 'images';

export let folders = [];
export let viewMode = 'gallery';
export let galleryActive = true;
export let lightboxIndex = -1;
export let isLoading = false;
export let detailCache = {};
export let scrollObserver = null; // legacy observer used by older modules
export let galleryScrollObserver = null;
export let sidebarScrollObserver = null;
export let cacheBuster = Date.now();

export let sortKey = 'name';
export let sortDir = 'asc';
export let sidebarSortKey = 'name';
export let sidebarSortDir = 'asc';

export function setSortKey(v) { sortKey = v; }
export function setSortDir(v) { sortDir = v; }
export function setSidebarSortKey(v) { sidebarSortKey = v; }
export function setSidebarSortDir(v) { sidebarSortDir = v; }


export function setImages(v) { images = Array.isArray(v) ? [...v] : []; }
export function setSidebarImages(v) { sidebarImages = Array.isArray(v) ? [...v] : []; }
export function setFolders(v) { folders = Array.isArray(v) ? [...v] : []; }
export function setActiveIndex(v) { activeIndex = Number.isInteger(v) ? v : -1; }
export function setViewModeValue(v) { viewMode = v === 'list' ? 'list' : 'gallery'; }
export function setGalleryActive(v) { galleryActive = Boolean(v); }
export function setLightboxIndex(v) { lightboxIndex = v; }
export function setCurrentFolderId(v) { currentFolderId = v ?? null; }
export function setCurrentPage(v) { currentPage = Number.isInteger(v) ? v : 0; }
export function setSidebarPage(v) { sidebarPage = Number.isInteger(v) ? v : 0; }
export function setTotalImages(v) { totalImages = Number.isFinite(v) ? v : 0; }
export function setSidebarTotalImages(v) { sidebarTotalImages = Number.isFinite(v) ? v : 0; }
export function setAllLoaded(v) { allLoaded = Boolean(v); }
export function setSidebarAllLoaded(v) { sidebarAllLoaded = Boolean(v); }
export function setSidebarActiveImageId(v) { sidebarActiveImageId = v ?? null; }
export function setActiveSidebarTab(v) { activeSidebarTab = v === 'folders' ? 'folders' : 'images'; }
export function setIsLoading(v) { isLoading = Boolean(v); }
export function setDetailCache(v) { detailCache = v && typeof v === 'object' ? v : {}; }
export function setScrollObserver(v) { scrollObserver = v; }
export function setGalleryScrollObserver(v) { galleryScrollObserver = v; }
export function setSidebarScrollObserver(v) { sidebarScrollObserver = v; }
export function refreshCacheBuster() { cacheBuster = Date.now(); }

export let searchSettings = {
    exactMatch: false,
    fields: {
        positive_prompt: true,
        negative_prompt: true,
        model: true,
        sampler: true,
        resolution: true,
    },
};

export function setSearchSettings(v) {
    if (v && typeof v === 'object') searchSettings = v;
}

export function addImage(img) { images.push(img); }
export function addImages(imgs) { for (const img of imgs) images.push(img); }

// Only preferences are persisted. Navigation always starts from deterministic defaults.
export function loadState() {
    try {
        const str = sessionStorage.getItem('cmv_preferences');
        if (!str) return;
        const preferences = JSON.parse(str);
        if (preferences.searchSettings) setSearchSettings(preferences.searchSettings);
    } catch (_e) { /* ignore parse errors */ }
}

export function saveState() {
    try {
        sessionStorage.setItem('cmv_preferences', JSON.stringify({
            searchSettings,
        }));
        sessionStorage.removeItem('cmv_state');
    } catch (_e) { /* ignore quota errors */ }
}

export function resetRuntimeState() {
    setImages([]);
    setSidebarImages([]);
    setFolders([]);
    setActiveIndex(-1);
    setSidebarActiveImageId(null);
    setCurrentFolderId(null);
    setCurrentPage(0);
    setSidebarPage(0);
    setTotalImages(0);
    setSidebarTotalImages(0);
    setAllLoaded(true);
    setSidebarAllLoaded(true);
    setActiveSidebarTab('images');
    setViewModeValue('gallery');
    setGalleryActive(true);
    setDetailCache({});
    if (scrollObserver) scrollObserver.disconnect();
    if (galleryScrollObserver) galleryScrollObserver.disconnect();
    if (sidebarScrollObserver) sidebarScrollObserver.disconnect();
    setScrollObserver(null);
    setGalleryScrollObserver(null);
    setSidebarScrollObserver(null);
    if (dom.folderNameEl) dom.folderNameEl.textContent = '';
    sortKey = 'name';
    sortDir = 'asc';
    sidebarSortKey = 'name';
    sidebarSortDir = 'asc';
}

export function showToast(msg) {
    if (!dom.toast) return;
    dom.toast.textContent = msg;
    dom.toast.classList.add('show');
    setTimeout(() => dom.toast.classList.remove('show'), 3000);
}
