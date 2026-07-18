import {
    PREFERENCES_VERSION,
    PREFERENCES_STORAGE_KEY,
    LEGACY_PREFERENCES_STORAGE_KEY,
    createDefaultPreferences,
    normalizePreferences,
    parsePreferences,
} from './preferences.js';

export const dom = {
    contentArea: document.getElementById('content-area'),
    imageList: document.getElementById('image-list'),
    imageCount: document.getElementById('image-count'),
    folderNameEl: document.getElementById('folder-name'),
    viewerCollectionName: document.getElementById('viewer-collection-name'),
    collectionKindEl: document.getElementById('collection-kind'),
    addFileInput: document.getElementById('add-file-input'),
    btnOpenFolder: document.getElementById('btn-open-folder'),
    toast: document.getElementById('toast'),
    btnViewUpload: document.getElementById('btn-view-upload'),
    btnViewList: document.getElementById('btn-view-list'),
    btnViewGallery: document.getElementById('btn-view-gallery'),
    lightbox: document.getElementById('lightbox'),
    lbTitle: document.getElementById('lb-title'),
    lbCounter: document.getElementById('lb-counter'),
    lbImg: document.getElementById('lb-img'),
    lbMeta: document.getElementById('lb-meta'),
    btnResetIndex: document.getElementById('btn-reset-index'),
    btnFactoryReset: document.getElementById('btn-factory-reset'),
    btnPaste: document.getElementById('btn-paste'),
    tabFolders: document.getElementById('tab-folders'),
    tabAlbums: document.getElementById('tab-albums'),
    tabImages: document.getElementById('tab-images'),
    panelFolders: document.getElementById('panel-folders'),
    panelAlbums: document.getElementById('panel-albums'),
    panelImages: document.getElementById('panel-images'),
    sidebar: document.getElementById('sidebar'),
    sidebarResize: document.getElementById('sidebar-resize'),
    sidebarToggle: document.getElementById('sidebar-toggle'),
    folderList: document.getElementById('folder-list'),
    albumList: document.getElementById('viewer-album-list'),
    foldersCount: document.getElementById('folders-count'),
    albumsCount: document.getElementById('viewer-albums-count'),
    foldersViewBtn: document.getElementById('folders-view-btn'),
    albumsViewBtn: document.getElementById('viewer-albums-view-btn'),
    foldersSortBtn: document.getElementById('folders-sort-btn'),
    foldersSortDropdown: document.getElementById('folders-sort-dropdown-menu'),
    albumsSortBtn: document.getElementById('viewer-albums-sort-btn'),
    albumsSortDropdown: document.getElementById('viewer-albums-sort-dropdown-menu'),
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
    lbViewOriginal: document.getElementById('lb-view-original'),
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

/**
 * Central content collection. It changes when a folder or album is selected.
 * @type {const Array} Must NOT be reassigned to preserve references in consumers.
 */
export const images = [];
export let activeIndex = -1;
export const currentCollection = { type: 'folder', id: null, name: '' };
export let currentFolderId = null;
export let currentPage = 0;
export let totalImages = 0;
export let allLoaded = true;

/**
 * Global Images sidebar collection. It never controls the central gallery.
 * @type {const Array} Must NOT be reassigned to preserve references in consumers.
 */
export const sidebarImages = [];
export let sidebarPage = 0;
export let sidebarTotalImages = 0;
export let sidebarAllLoaded = true;
export let sidebarActiveImageId = null;
export let activeSidebarTab = 'images';

/**
 * Read-only collection pickers used by the Viewer sidebar.
 * @type {const Array} Must NOT be reassigned to preserve references.
 */
export const folders = [];
export const albums = [];
export let viewMode = 'gallery';
export let galleryActive = true;
export let lightboxIndex = -1;
export let isLoading = false;
export let detailCache = {};
export let scrollObserver = null; // legacy observer used by older modules
export let galleryScrollObserver = null;
export let sidebarScrollObserver = null;
export let cacheBuster = Date.now();

export let sortKey = 'date';
export let sortDir = 'desc';
export let sidebarSortKey = 'date';
export let sidebarSortDir = 'desc';
export let foldersSortKey = 'scanned_at';
export let foldersSortDir = 'desc';
export let foldersViewMode = 'list';
export let albumsSortKey = 'name';
export let albumsSortDir = 'asc';
export let albumsViewMode = 'list';
export let sidebarWidth = 360;
export let sidebarCollapsed = false;
export let lightboxMetaOpen = true;
export let metadataTab = 'summary';

export function setSortKey(v) { sortKey = v; }
export function setSortDir(v) { sortDir = v; }
export function setSidebarSortKey(v) { sidebarSortKey = v; }
export function setSidebarSortDir(v) { sidebarSortDir = v; }
export function setFoldersSortKey(v) { foldersSortKey = v; }
export function setFoldersSortDir(v) { foldersSortDir = v; }
export function setFoldersViewMode(v) { foldersViewMode = v === 'list' ? 'list' : 'tile'; }
export function setAlbumsSortKey(v) { albumsSortKey = ['name', 'updated_at', 'asset_count'].includes(v) ? v : 'name'; }
export function setAlbumsSortDir(v) { albumsSortDir = v === 'desc' ? 'desc' : 'asc'; }
export function setAlbumsViewMode(v) { albumsViewMode = v === 'list' ? 'list' : 'tile'; }
export function setSidebarWidth(v) { sidebarWidth = Number.isFinite(v) ? Math.min(500, Math.max(280, Math.round(v))) : 360; }
export function setSidebarCollapsed(v) { sidebarCollapsed = Boolean(v); }
export function setLightboxMetaOpen(v) { lightboxMetaOpen = Boolean(v); }
export function setMetadataTab(v) { metadataTab = ['workflow', 'raw'].includes(v) ? v : 'summary'; }

export function setImages(v) {
    if (v === images) return;
    images.length = 0;
    if (Array.isArray(v)) images.push(...v);
}
export function setSidebarImages(v) {
    if (v === sidebarImages) return;
    sidebarImages.length = 0;
    if (Array.isArray(v)) sidebarImages.push(...v);
}
export function setFolders(v) {
    if (v === folders) return;
    folders.length = 0;
    if (Array.isArray(v)) folders.push(...v);
}
export function setAlbums(v) {
    if (v === albums) return;
    albums.length = 0;
    if (Array.isArray(v)) albums.push(...v);
}
export function setActiveIndex(v) { activeIndex = Number.isInteger(v) ? v : -1; }
export function setViewModeValue(v) { viewMode = v === 'list' ? 'list' : (v === 'upload' ? 'upload' : 'gallery'); }
export function setGalleryActive(v) { galleryActive = Boolean(v); }
export function setLightboxIndex(v) { lightboxIndex = v; }
export function setCurrentCollection(value) {
    const type = value?.type === 'album' ? 'album' : (value?.type === 'temporary' ? 'temporary' : 'folder');
    const id = Number.isInteger(value?.id) && value.id > 0 ? value.id : null;
    currentCollection.type = type;
    currentCollection.id = id;
    currentCollection.name = typeof value?.name === 'string' ? value.name : '';
    currentFolderId = type === 'folder' ? id : null;
    if (dom.collectionKindEl) {
        dom.collectionKindEl.textContent = id || currentCollection.name
            ? (type === 'album' ? 'Album' : (type === 'temporary' ? 'Temporary' : 'Folder'))
            : '';
    }
}
export function setCurrentFolderId(v) {
    const id = Number.isInteger(v) && v > 0 ? v : null;
    setCurrentCollection({
        type: 'folder',
        id,
        name: id && currentCollection.type === 'folder' ? currentCollection.name : '',
    });
}
export function setCurrentPage(v) { currentPage = Number.isInteger(v) ? v : 0; }
export function setSidebarPage(v) { sidebarPage = Number.isInteger(v) ? v : 0; }
export function setTotalImages(v) { totalImages = Number.isFinite(v) ? v : 0; }
export function setSidebarTotalImages(v) { sidebarTotalImages = Number.isFinite(v) ? v : 0; }
export function setAllLoaded(v) { allLoaded = Boolean(v); }
export function setSidebarAllLoaded(v) { sidebarAllLoaded = Boolean(v); }
export function setSidebarActiveImageId(v) { sidebarActiveImageId = v ?? null; }
export function setActiveSidebarTab(v) { activeSidebarTab = ['folders', 'albums'].includes(v) ? v : 'images'; }
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
    searchSettings = normalizePreferences({ searchSettings: v }).searchSettings;
}

export function addImage(img) { images.push(img); }
export function addImages(imgs) { for (const img of imgs) images.push(img); }

function getStoredPreferences() {
    try {
        const stored = localStorage.getItem(PREFERENCES_STORAGE_KEY);
        if (stored) return { preferences: parsePreferences(stored), migrated: false };

        const legacy = sessionStorage.getItem(LEGACY_PREFERENCES_STORAGE_KEY)
            || localStorage.getItem(LEGACY_PREFERENCES_STORAGE_KEY);
        if (legacy) return { preferences: parsePreferences(legacy), migrated: true };
    } catch (_error) {
        // Storage can be unavailable in hardened browser contexts.
    }
    return { preferences: createDefaultPreferences(), migrated: false };
}

function applyPreferences(preferences) {
    setCurrentCollection(preferences.navigation.selectedCollection);
    setViewModeValue(preferences.navigation.viewMode);
    setGalleryActive(preferences.navigation.viewMode === 'gallery');
    setActiveSidebarTab(preferences.navigation.sidebarTab);
    setSidebarWidth(preferences.layout.sidebarWidth);
    setSidebarCollapsed(preferences.layout.sidebarCollapsed);
    setFoldersViewMode(preferences.layout.foldersViewMode);
    setAlbumsViewMode(preferences.layout.albumsViewMode);
    setLightboxMetaOpen(preferences.layout.lightboxMetaOpen);
    setMetadataTab(preferences.layout.metadataTab);
    setSortKey(preferences.sorting.gallery.key);
    setSortDir(preferences.sorting.gallery.direction);
    setSidebarSortKey(preferences.sorting.images.key);
    setSidebarSortDir(preferences.sorting.images.direction);
    setFoldersSortKey(preferences.sorting.folders.key);
    setFoldersSortDir(preferences.sorting.folders.direction);
    setAlbumsSortKey(preferences.sorting.albums.key);
    setAlbumsSortDir(preferences.sorting.albums.direction);
    setSearchSettings(preferences.searchSettings);
}

export function loadState() {
    const { preferences, migrated } = getStoredPreferences();
    applyPreferences(preferences);
    if (migrated) saveState();
    return preferences;
}

export function saveState() {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION,
        navigation: {
            selectedCollection: { type: currentCollection.type, id: currentCollection.id },
            selectedFolderId: currentFolderId,
            viewMode,
            sidebarTab: activeSidebarTab,
        },
        layout: {
            sidebarWidth,
            sidebarCollapsed,
            foldersViewMode,
            albumsViewMode,
            lightboxMetaOpen,
            metadataTab,
        },
        sorting: {
            gallery: { key: sortKey, direction: sortDir },
            images: { key: sidebarSortKey, direction: sidebarSortDir },
            folders: { key: foldersSortKey, direction: foldersSortDir },
            albums: { key: albumsSortKey, direction: albumsSortDir },
        },
        searchSettings,
    });
    try {
        localStorage.setItem(PREFERENCES_STORAGE_KEY, JSON.stringify(preferences));
        localStorage.removeItem(LEGACY_PREFERENCES_STORAGE_KEY);
        localStorage.removeItem('cmv_state');
        sessionStorage.removeItem(LEGACY_PREFERENCES_STORAGE_KEY);
        sessionStorage.removeItem('cmv_state');
    } catch (_error) {
        // Preference persistence must never break the application runtime.
    }
    return preferences;
}

export function clearStoredPreferences() {
    try {
        localStorage.removeItem(PREFERENCES_STORAGE_KEY);
        localStorage.removeItem(LEGACY_PREFERENCES_STORAGE_KEY);
        localStorage.removeItem('cmv_state');
        sessionStorage.removeItem(LEGACY_PREFERENCES_STORAGE_KEY);
        sessionStorage.removeItem('cmv_state');
    } catch (_error) {
        // A factory reset must still succeed when browser storage is unavailable.
    }
}

export function resetRuntimeState() {
    const defaults = createDefaultPreferences();
    setImages([]);
    setSidebarImages([]);
    setFolders([]);
    setAlbums([]);
    setActiveIndex(-1);
    setSidebarActiveImageId(null);
    setCurrentCollection(defaults.navigation.selectedCollection);
    setCurrentPage(0);
    setSidebarPage(0);
    setTotalImages(0);
    setSidebarTotalImages(0);
    setAllLoaded(true);
    setSidebarAllLoaded(true);
    setActiveSidebarTab(defaults.navigation.sidebarTab);
    setViewModeValue(defaults.navigation.viewMode);
    setGalleryActive(true);
    setDetailCache({});
    if (scrollObserver) scrollObserver.disconnect();
    if (galleryScrollObserver) galleryScrollObserver.disconnect();
    if (sidebarScrollObserver) sidebarScrollObserver.disconnect();
    setScrollObserver(null);
    setGalleryScrollObserver(null);
    setSidebarScrollObserver(null);
    if (dom.folderNameEl) dom.folderNameEl.textContent = '';
    setSortKey(defaults.sorting.gallery.key);
    setSortDir(defaults.sorting.gallery.direction);
    setSidebarSortKey(defaults.sorting.images.key);
    setSidebarSortDir(defaults.sorting.images.direction);
    setFoldersSortKey(defaults.sorting.folders.key);
    setFoldersSortDir(defaults.sorting.folders.direction);
    setFoldersViewMode(defaults.layout.foldersViewMode);
    setAlbumsSortKey(defaults.sorting.albums.key);
    setAlbumsSortDir(defaults.sorting.albums.direction);
    setAlbumsViewMode(defaults.layout.albumsViewMode);
    setSidebarWidth(defaults.layout.sidebarWidth);
    setSidebarCollapsed(defaults.layout.sidebarCollapsed);
    setLightboxMetaOpen(defaults.layout.lightboxMetaOpen);
    setMetadataTab(defaults.layout.metadataTab);
    setSearchSettings(defaults.searchSettings);
}

export function showToast(msg) {
    if (!dom.toast) return;
    dom.toast.textContent = msg;
    dom.toast.classList.add('show');
    setTimeout(() => dom.toast.classList.remove('show'), 3000);
}
