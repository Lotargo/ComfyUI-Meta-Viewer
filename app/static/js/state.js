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
    btnClear: document.getElementById('btn-clear'),
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

export let images = [];
export let sidebarImages = [];
export let activeIndex = -1;
export let viewMode = 'gallery';
export let galleryActive = true;
export let lightboxIndex = -1;
export let currentFolderId = null;
export let currentPage = 0;
export let sidebarPage = 0;
export let totalImages = 0;
export let sidebarTotalImages = 0;
export let allLoaded = false;
export let sidebarAllLoaded = false;
export let isLoading = false;
export let detailCache = {};
export let scrollObserver = null;
export let cacheBuster = Date.now();

export function setImages(v) { images = v; }
export function setSidebarImages(v) { sidebarImages = v; }
export function setActiveIndex(v) { activeIndex = v; }
export function setViewModeValue(v) { viewMode = v; }
export function setGalleryActive(v) { galleryActive = v; }
export function setLightboxIndex(v) { lightboxIndex = v; }
export function setCurrentFolderId(v) { currentFolderId = v; }
export function setCurrentPage(v) { currentPage = v; }
export function setSidebarPage(v) { sidebarPage = v; }
export function setTotalImages(v) { totalImages = v; }
export function setSidebarTotalImages(v) { sidebarTotalImages = v; }
export function setAllLoaded(v) { allLoaded = v; }
export function setSidebarAllLoaded(v) { sidebarAllLoaded = v; }
export function setIsLoading(v) { isLoading = v; }
export function setDetailCache(v) { detailCache = v; }
export function setScrollObserver(v) { scrollObserver = v; }
export function refreshCacheBuster() { cacheBuster = Date.now(); }
export let searchSettings = {
    exactMatch: false,
    fields: {
        positive_prompt: true,
        negative_prompt: true,
        model: true,
        sampler: true,
        resolution: true
    }
};

export function setSearchSettings(v) { searchSettings = v; }

export function addImage(img) { images.push(img); }
export function addImages(imgs) { for (const img of imgs) images.push(img); }

export function loadState() {
    try {
        const str = sessionStorage.getItem('cmv_state');
        if (str) {
            const st = JSON.parse(str);
            if (st.viewMode) setViewModeValue(st.viewMode);
            if (st.searchSettings) setSearchSettings(st.searchSettings);
        }
    } catch(_e) { /* ignore parse errors */ }
}

export function showToast(msg) {
    dom.toast.textContent = msg;
    dom.toast.classList.add('show');
    setTimeout(() => dom.toast.classList.remove('show'), 3000);
}

export function saveState() {
    try {
        sessionStorage.setItem('cmv_state', JSON.stringify({
            page: currentPage,
            activeIndex: activeIndex,
            viewMode: viewMode,
            totalImages: totalImages,
            allLoaded: allLoaded,
            folderId: currentFolderId,
            folderName: dom.folderNameEl.textContent,
            searchSettings: searchSettings
        }));
    } catch(_e) { /* ignore quota errors */ }
}
