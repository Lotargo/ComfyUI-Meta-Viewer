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

export function addImage(img) { images.push(img); }
export function addImages(imgs) { for (const img of imgs) images.push(img); }

export function showToast(msg) {
    dom.toast.textContent = msg;
    dom.toast.classList.add('show');
    setTimeout(() => dom.toast.classList.remove('show'), 1800);
}

export function saveState() {
    try {
        sessionStorage.setItem('cmv_state', JSON.stringify({
            folderId: currentFolderId,
            page: currentPage,
            activeIndex: activeIndex,
            viewMode: viewMode,
            totalImages: totalImages,
            allLoaded: allLoaded,
            folderName: dom.folderNameEl.textContent,
        }));
    } catch(e) { /* ignore quota errors */ }
}
