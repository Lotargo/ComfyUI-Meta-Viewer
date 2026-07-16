import {
    images,
    activeIndex,
    currentFolderId,
    currentPage,
    totalImages,
    allLoaded,
    detailCache,
    galleryActive,
    dom,
    setImages,
    setActiveIndex,
    setCurrentFolderId,
    setCurrentPage,
    setTotalImages,
    setAllLoaded,
    setDetailCache,
    setIsLoading,
    isLoading,
    showToast,
    sidebarImages,
    setSidebarImages,
    setSidebarTotalImages,
    setSidebarPage,
    sidebarPage,
    setSidebarAllLoaded,
    sidebarAllLoaded,
    sidebarTotalImages,
    setFolders,
    sortKey,
    sortDir,
    sidebarSortKey,
    sidebarSortDir,
} from './state.js';
import { showLoading, showError, customConfirm } from './utils.js';

const PAGE_SIZE = 50;
const responseCache = new Map();
const pendingRequests = new Map();

function requestKey(url) {
    return url;
}

async function fetchJson(url, { force = false, options = undefined } = {}) {
    await Promise.resolve();
    const key = requestKey(url);
    const method = options?.method || 'GET';

    if (method === 'GET' && !force && responseCache.has(key)) {
        return responseCache.get(key);
    }
    if (method === 'GET' && pendingRequests.has(key)) {
        return pendingRequests.get(key);
    }

    const request = fetch(url, options).then(async response => {
        const data = await response.json().catch(() => ({}));
        if (!response.ok || data.error) {
            throw new Error(data.error || `${response.status} ${response.statusText}`);
        }
        if (method === 'GET') responseCache.set(key, data);
        return data;
    }).finally(() => {
        if (method === 'GET') pendingRequests.delete(key);
    });

    if (method === 'GET') pendingRequests.set(key, request);
    return request;
}

export function invalidateApiCache() {
    responseCache.clear();
    pendingRequests.clear();
}

async function renderCurrentContent() {
    const { viewMode } = await import('./state.js');
    if (viewMode === 'upload') {
        const { setViewMode } = await import('./events.js');
        setViewMode('gallery', { render: false });
    }
    if (galleryActive) {
        const { renderGallery } = await import('./gallery.js');
        renderGallery();
        return;
    }
    const { renderImageMeta } = await import('./detail-loader.js');
    await renderImageMeta(images[activeIndex] || images[0] || null);
}

export async function loadBootstrap() {
    // Build one coherent startup snapshot without rendering intermediate states.
    const [folderData, globalPage] = await Promise.all([
        fetchJson('/api/folders', { force: true }),
        fetchJson(`/api/images?page=1&per_page=${PAGE_SIZE}`, { force: true }),
    ]);
    const folderList = folderData.folders || [];
    const defaultFolder = folderList[0] || null;
    const folderPage = defaultFolder
        ? await fetchJson(`/api/images?folder_id=${defaultFolder.id}&page=1&per_page=${PAGE_SIZE}`, { force: true })
        : { images: [], total: 0, page: 0, per_page: PAGE_SIZE };

    return {
        folders: folderList,
        default_folder: defaultFolder,
        global_images: globalPage,
        folder_images: folderPage,
    };
}

export async function scanFolder(path) {
    showLoading('Scanning folder...');
    try {
        const data = await fetchJson('/api/scan', {
            options: {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({path}),
            },
        });

        invalidateApiCache();
        setCurrentFolderId(data.folder_id);
        setImages(data.images || []);
        setTotalImages(data.total || 0);
        setCurrentPage(data.page || 1);
        setAllLoaded((data.images || []).length >= (data.total || 0));
        setActiveIndex((data.images || []).length ? 0 : -1);
        setDetailCache({});
        dom.folderNameEl.textContent = data.folder?.name || '';

        const [folders] = await Promise.all([
            getFolders({ force: true }),
            loadSidebarImages({ force: true, render: false }),
        ]);
        setFolders(folders);

        const { renderFoldersList, renderSidebar } = await import('./features/sidebar.js');
        await renderFoldersList(folders);
        renderSidebar();
        await renderCurrentContent();
    } catch (e) {
        showError('Error: ' + e.message);
    }
}

export async function loadFromPaths(paths) {
    showLoading('Loading...');
    try {
        const data = await fetchJson('/api/extract', {
            options: {
                method: 'POST',
                headers: {'Content-Type':'application/json'},
                body: JSON.stringify({paths}),
            },
        });
        if (!data.images?.length) {
            showError('No images found');
            return;
        }
        setCurrentFolderId(null);
        dom.folderNameEl.textContent = 'Temporary';
        setImages(data.images);
        setTotalImages(data.images.length);
        setAllLoaded(true);
        setCurrentPage(1);
        setActiveIndex(0);
        setDetailCache({});
        await renderCurrentContent();
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadFromFiles(files) {
    const formData = new FormData();
    for (const file of files) formData.append('files', file);
    showLoading('Processing ' + files.length + ' files...');
    try {
        const data = await fetchJson('/api/upload', {
            options: { method: 'POST', body: formData },
        });
        if (!data.images?.length) {
            showError('No images found');
            return;
        }

        invalidateApiCache();
        const folders = await getFolders({ force: true });
        setFolders(folders);
        const uploadFolder = folders.find(folder => folder.id === data.folder_id);
        await Promise.all([
            loadFolderImages(data.folder_id, uploadFolder?.name || 'Uploads', { force: true, render: false }),
            loadSidebarImages({ force: true, render: false }),
        ]);

        const { renderFoldersList, renderSidebar } = await import('./features/sidebar.js');
        await renderFoldersList(folders);
        renderSidebar();
        await renderCurrentContent();
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadMore() {
    if (isLoading || allLoaded || !currentFolderId) return false;
    setIsLoading(true);
    let spinner = document.querySelector('#gallery-load-more-spinner');
    if (!spinner && dom.contentArea) {
        spinner = document.createElement('div');
        spinner.id = 'gallery-load-more-spinner';
        spinner.style.cssText = 'display: flex; justify-content: center; padding: 24px; width: 100%;';
        spinner.innerHTML = `
            <svg viewBox="0 0 24 24" width="24" height="24" stroke="var(--accent)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" class="anim-spin">
                <line x1="12" y1="2" x2="12" y2="6"></line>
                <line x1="12" y1="18" x2="12" y2="22"></line>
                <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                <line x1="2" y1="12" x2="6" y2="12"></line>
                <line x1="18" y1="12" x2="22" y2="12"></line>
                <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
            </svg>
        `;
        dom.contentArea.appendChild(spinner);
    }
    const nextPage = currentPage + 1;
    let didLoad = false;
    try {
        const data = await fetchJson(`/api/images?folder_id=${currentFolderId}&page=${nextPage}&per_page=${PAGE_SIZE}&sort_by=${sortKey}&sort_dir=${sortDir}`);
        if (data.images?.length) {
            images.push(...data.images);
            setCurrentPage(nextPage);
            setTotalImages(data.total || totalImages);
            setAllLoaded(images.length >= (data.total || 0));
            didLoad = true;
        } else {
            setAllLoaded(true);
        }
    } catch(e) {
        console.error('loadMore error:', e);
    } finally {
        setIsLoading(false);
        if (spinner) spinner.remove();
    }
    return didLoad;
}

export async function loadSidebarImages({ force = false, render = true } = {}) {
    const data = await fetchJson(`/api/images?page=1&per_page=${PAGE_SIZE}&sort_by=${sidebarSortKey}&sort_dir=${sidebarSortDir}`, { force });
    setSidebarImages(data.images || []);
    setSidebarTotalImages(data.total || 0);
    setSidebarPage(data.page || 1);
    setSidebarAllLoaded((data.images || []).length >= (data.total || 0));
    if (render) {
        const { renderSidebar } = await import('./features/sidebar.js');
        renderSidebar();
    }
    return data;
}

export async function loadMoreSidebarImages() {
    if (isLoading || sidebarAllLoaded) return;
    setIsLoading(true);
    let spinner = document.querySelector('#sidebar-load-more-spinner');
    if (!spinner && dom.imageList) {
        spinner = document.createElement('div');
        spinner.id = 'sidebar-load-more-spinner';
        spinner.style.cssText = 'display: flex; justify-content: center; padding: 12px; width: 100%;';
        spinner.innerHTML = `
            <svg viewBox="0 0 24 24" width="16" height="16" stroke="var(--accent)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" class="anim-spin">
                <line x1="12" y1="2" x2="12" y2="6"></line>
                <line x1="12" y1="18" x2="12" y2="22"></line>
                <line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line>
                <line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line>
                <line x1="2" y1="12" x2="6" y2="12"></line>
                <line x1="18" y1="12" x2="22" y2="12"></line>
                <line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line>
                <line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line>
            </svg>
        `;
        dom.imageList.appendChild(spinner);
    }
    const nextPage = sidebarPage + 1;
    try {
        const data = await fetchJson(`/api/images?page=${nextPage}&per_page=${PAGE_SIZE}&sort_by=${sidebarSortKey}&sort_dir=${sidebarSortDir}`);
        if (data.images?.length) {
            sidebarImages.push(...data.images);
            setSidebarPage(nextPage);
            setSidebarTotalImages(data.total || sidebarTotalImages);
            setSidebarAllLoaded(sidebarImages.length >= (data.total || 0));
            const { renderSidebar } = await import('./features/sidebar.js');
            renderSidebar();
        } else {
            setSidebarAllLoaded(true);
        }
    } catch(e) {
        console.error('loadMoreSidebarImages error:', e);
    } finally {
        setIsLoading(false);
        if (spinner) spinner.remove();
    }
}

export async function getFolders({ force = false } = {}) {
    const data = await fetchJson('/api/folders', { force });
    return data.folders || [];
}

export async function deleteFolderFromServer(folderId) {
    try {
        await fetchJson(`/api/folders/${folderId}`, { options: { method: 'DELETE' } });
        invalidateApiCache();
        return true;
    } catch (e) {
        console.error('Failed to delete folder:', e);
        return false;
    }
}

export async function deleteImageById(imageId) {
    const img = images.find(item => item.id === imageId) || sidebarImages.find(item => item.id === imageId);
    if (!img) return false;

    const fileName = img.file_name || img.file || 'this image';
    const ok = await customConfirm('Delete Image', `Remove "${fileName}" from the viewer? Files scanned from disk will not be deleted from the folder.`);
    if (!ok) return false;

    try {
        await fetchJson(`/api/images/${imageId}`, { options: { method: 'DELETE' } });
        invalidateApiCache();
        delete detailCache[imageId];

        const centralIndex = images.findIndex(item => item.id === imageId);
        if (centralIndex >= 0) {
            images.splice(centralIndex, 1);
            setTotalImages(Math.max(0, totalImages - 1));
            if (!images.length) setActiveIndex(-1);
            else if (activeIndex >= images.length) setActiveIndex(images.length - 1);
            else if (centralIndex < activeIndex) setActiveIndex(activeIndex - 1);
        }

        const sidebarIndex = sidebarImages.findIndex(item => item.id === imageId);
        if (sidebarIndex >= 0) {
            sidebarImages.splice(sidebarIndex, 1);
            setSidebarTotalImages(Math.max(0, sidebarTotalImages - 1));
        }

        const { renderSidebar } = await import('./features/sidebar.js');
        renderSidebar();
        await renderCurrentContent();
        showToast('Image removed');
        return true;
    } catch(e) {
        showError('Delete failed: ' + e.message);
        return false;
    }
}

export function deleteImageAt(index) {
    const img = images[index];
    return img ? deleteImageById(img.id) : Promise.resolve(false);
}

export async function loadFolderImages(folderId, folderName, { force = false, render = true } = {}) {
    setIsLoading(true);
    if (render) showLoading('Loading folder images...');
    try {
        const data = await fetchJson(`/api/images?folder_id=${folderId}&page=1&per_page=${PAGE_SIZE}&sort_by=${sortKey}&sort_dir=${sortDir}`, { force });
        setCurrentFolderId(folderId);
        dom.folderNameEl.textContent = folderName || '';
        setImages(data.images || []);
        setTotalImages(data.total || 0);
        setCurrentPage(data.page || 1);
        setAllLoaded((data.images || []).length >= (data.total || 0));
        setActiveIndex((data.images || []).length ? 0 : -1);
        setDetailCache({});
        if (render) await renderCurrentContent();
        return data;
    } catch(e) {
        if (render) showError('Error loading folder: ' + e.message);
        throw e;
    } finally {
        setIsLoading(false);
    }
}
