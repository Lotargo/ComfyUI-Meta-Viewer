import {
    images,
    activeIndex,
    currentCollection,
    currentPage,
    totalImages,
    allLoaded,
    detailCache,
    galleryActive,
    dom,
    setImages,
    setActiveIndex,
    setCurrentCollection,
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
    setAlbums,
    sortKey,
    sortDir,
    sidebarSortKey,
    sidebarSortDir,
    ratingFilter,
    mediaTypeFilter,
    saveState,
    sidebarActiveImageId,
    setSidebarActiveImageId,
    isBrowsableCollection,
} from './state.js';
import { imageRenderSignature, showLoading, showError, customConfirm } from './utils.js';
import { isSupportedMediaFile } from './media-files.js';

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

function collectionFilter(collection = currentCollection) {
    if (collection?.type === 'media' || !collection?.id) return '';
    return collection.type === 'album'
        ? `album_id=${collection.id}`
        : `folder_id=${collection.id}`;
}

function selectedMediaTypes() {
    return [
        mediaTypeFilter.images ? 'image' : null,
        mediaTypeFilter.videos ? 'video' : null,
    ].filter(Boolean).join(',');
}

function collectionImagesUrl(collection, page, perPage) {
    const filter = collectionFilter(collection);
    const rating = ratingFilter === null ? '' : `&rating=${ratingFilter}`;
    return `/api/images?${filter}&page=${page}&per_page=${perPage}&sort_by=${sortKey}&sort_dir=${sortDir}&media_type=${selectedMediaTypes()}${rating}`;
}

function sidebarImagesUrl(page, perPage) {
    const rating = ratingFilter === null ? '' : `&rating=${ratingFilter}`;
    return `/api/images?page=${page}&per_page=${perPage}&sort_by=${sidebarSortKey}&sort_dir=${sidebarSortDir}&media_type=${selectedMediaTypes()}${rating}`;
}

async function renderCurrentContent({ reconcileGallery = false } = {}) {
    const { viewMode } = await import('./state.js');
    if (viewMode === 'upload') {
        const { setViewMode } = await import('./events.js');
        setViewMode('gallery', { render: false });
    }
    if (galleryActive) {
        const { renderGallery } = await import('./gallery.js');
        renderGallery({ reconcile: reconcileGallery });
        return;
    }
    const { renderImageMeta } = await import('./detail-loader.js');
    await renderImageMeta(images[activeIndex] || images[0] || null);
}

export async function loadBootstrap({ preferredCollection = null } = {}) {
    // Build one coherent startup snapshot without rendering intermediate states.
    const [folderData, albumData, globalPage] = await Promise.all([
        fetchJson('/api/folders', { force: true }),
        fetchJson('/api/albums', { force: true }),
        fetchJson(sidebarImagesUrl(1, PAGE_SIZE), { force: true }),
    ]);
    const folderList = folderData.folders || [];
    const albumList = albumData.albums || [];
    const preferredId = Number.isInteger(preferredCollection?.id) ? preferredCollection.id : null;
    const preferredMedia = preferredCollection?.type === 'media';
    const preferredAlbum = preferredCollection?.type === 'album'
        ? albumList.find(album => album.id === preferredId)
        : null;
    const preferredFolder = preferredCollection?.type !== 'album'
        ? folderList.find(folder => folder.id === preferredId && folder.enabled)
        : null;
    const fallbackFolder = folderList.find(folder => folder.enabled) || null;
    const defaultItem = preferredAlbum
        ? { type: 'album', item: preferredAlbum }
        : preferredFolder
            ? { type: 'folder', item: preferredFolder }
            : fallbackFolder
                ? { type: 'folder', item: fallbackFolder }
                : albumList[0]
                    ? { type: 'album', item: albumList[0] }
                    : null;
    const defaultCollection = preferredMedia
        ? { type: 'media', id: null, name: 'All Media' }
        : defaultItem
            ? { type: defaultItem.type, id: defaultItem.item.id, name: defaultItem.item.name }
            : null;
    const collectionPage = defaultCollection
        ? await fetchJson(collectionImagesUrl(defaultCollection, 1, PAGE_SIZE), { force: true })
        : { images: [], total: 0, page: 0, per_page: PAGE_SIZE };

    return {
        folders: folderList,
        albums: albumList,
        default_collection: defaultCollection,
        global_images: globalPage,
        collection_images: collectionPage,
    };
}

export async function scanFolder(path, { recursive = false } = {}) {
    showLoading('Scanning folder...');
    try {
        const data = await fetchJson('/api/scan', {
            options: {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ path, recursive }),
            },
        });

        invalidateApiCache();
        setCurrentCollection({ type: 'folder', id: data.folder_id, name: data.folder?.name || '' });
        setImages(data.images || []);
        setTotalImages(data.total || 0);
        setCurrentPage(data.page || 1);
        setAllLoaded((data.images || []).length >= (data.total || 0));
        setActiveIndex((data.images || []).length ? 0 : -1);
        setDetailCache({});
        dom.folderNameEl.textContent = data.folder?.name || '';
        saveState();

        const refreshes = [
            getFolders({ force: true }),
            loadSidebarImages({ force: true, render: false }),
            loadCollectionImages(
                { ...currentCollection },
                { force: true, render: false },
            ),
        ];
        const [folders] = await Promise.all(refreshes);
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
        setCurrentCollection({ type: 'temporary', id: null, name: 'Temporary' });
        dom.folderNameEl.textContent = 'Temporary';
        setImages(data.images);
        setTotalImages(data.images.length);
        setAllLoaded(true);
        setCurrentPage(1);
        setActiveIndex(0);
        setDetailCache({});
        saveState();
        await renderCurrentContent();
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadFromFiles(files) {
    const validFiles = Array.from(files).filter(isSupportedMediaFile);

    if (validFiles.length === 0) {
        showError('No supported media files found');
        return;
    }

    const formData = new FormData();
    for (const file of validFiles) formData.append('files', file);
    showLoading('Adding ' + validFiles.length + ' files...');
    try {
        const data = await fetchJson('/api/upload', {
            options: { method: 'POST', body: formData },
        });
        const addedAssets = (data.assets || data.images || []).filter(asset => !asset.error);
        if (!addedAssets.length) {
            showError('No media files were added');
            return;
        }

        invalidateApiCache();
        const folders = await getFolders({ force: true });
        setFolders(folders);
        const primaryAsset = addedAssets[0];
        const uploadFolder = folders.find(folder => folder.id === primaryAsset?.folder_id);
        const refreshTasks = [loadSidebarImages({ force: true, render: false })];
        if (primaryAsset?.folder_id) {
            refreshTasks.push(loadFolderImages(
                primaryAsset.folder_id,
                uploadFolder?.name || 'Uploads',
                { force: true, render: false },
            ));
        }
        await Promise.all(refreshTasks);

        const { renderFoldersList, renderSidebar } = await import('./features/sidebar.js');
        await renderFoldersList(folders);
        renderSidebar();
        await renderCurrentContent();
        const videoCount = addedAssets.filter(asset => asset.media_type === 'video').length;
        if (videoCount) {
            showToast(`${videoCount} video file(s) added`);
        }
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadMore() {
    if (isLoading || allLoaded || !isBrowsableCollection(currentCollection)) return false;
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
        const data = await fetchJson(collectionImagesUrl(currentCollection, nextPage, PAGE_SIZE));
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

export async function loadSidebarImages({ force = false, render = true, preserveCount = false } = {}) {
    const limit = preserveCount ? Math.max(PAGE_SIZE, sidebarPage * PAGE_SIZE) : PAGE_SIZE;
    const data = await fetchJson(sidebarImagesUrl(1, limit), { force });
    const nextImages = data.images || [];
    const previousSignatures = new Map(sidebarImages.map(img => [img.id, imageRenderSignature(img)]));
    const changedImageIds = new Set(
        nextImages
            .filter(img => previousSignatures.has(img.id) && previousSignatures.get(img.id) !== imageRenderSignature(img))
            .map(img => img.id),
    );
    const activeImageId = sidebarActiveImageId;
    
    setSidebarImages(nextImages);
    setSidebarTotalImages(data.total || 0);
    
    if (!preserveCount) {
        setSidebarPage(data.page || 1);
        setSidebarAllLoaded((data.images || []).length >= (data.total || 0));
    } else {
        setSidebarAllLoaded(sidebarImages.length >= (data.total || 0));
        if (activeImageId) {
            const newIdx = sidebarImages.findIndex(img => img.id === activeImageId);
            if (newIdx >= 0) {
                setSidebarActiveImageId(sidebarImages[newIdx].id);
            }
        }
    }

    if (preserveCount) {
        const retainedIds = new Set([...images, ...nextImages].map(img => img.id));
        setDetailCache(Object.fromEntries(
            Object.entries(detailCache).filter(([imageId]) => {
                const numericId = Number(imageId);
                return retainedIds.has(numericId) && !changedImageIds.has(numericId);
            }),
        ));
    }
    
    if (render) {
        const { renderSidebar } = await import('./features/sidebar.js');
        renderSidebar({ reconcile: preserveCount });
    }
    if (preserveCount && dom.lightbox.classList.contains('open')) {
        const { syncLightboxAfterCollectionChange } = await import('./lightbox.js');
        syncLightboxAfterCollectionChange({ changedImageIds });
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
        const data = await fetchJson(sidebarImagesUrl(nextPage, PAGE_SIZE));
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

export async function getAlbums({ force = false } = {}) {
    const data = await fetchJson('/api/albums', { force });
    return data.albums || [];
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

export async function updateSourceOnServer(folderId, patch) {
    const data = await fetchJson(`/api/folders/${folderId}`, {
        options: {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(patch),
        },
    });
    invalidateApiCache();
    return data.folder;
}

export async function reconcileSource(folderId) {
    await fetchJson(`/api/folders/${folderId}/reconcile`, {
        options: { method: 'POST' },
    });
    invalidateApiCache();
}

function removeImageFromRuntime(imageId) {
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
}

async function renderAfterImageRemoval() {
    const [updatedAlbums, updatedFolders] = await Promise.all([
        getAlbums({ force: true }),
        getFolders({ force: true }),
    ]);
    setAlbums(updatedAlbums);
    setFolders(updatedFolders);
    const {
        renderAlbumsList,
        renderFoldersList,
        renderSidebar,
    } = await import('./features/sidebar.js');
    renderSidebar();
    await Promise.all([
        renderAlbumsList(updatedAlbums),
        renderFoldersList(updatedFolders),
    ]);
    await renderCurrentContent();
}

export async function removeAssetFromIndexById(imageId) {
    const asset = images.find(item => item.id === imageId)
        || sidebarImages.find(item => item.id === imageId);
    if (!asset) return false;

    const assetLabel = asset.media_type === 'video' ? 'video' : 'image';
    const fileName = asset.file_name || asset.file || `this ${assetLabel}`;
    const isUploadedAsset = asset.has_local_file === false;
    const title = isUploadedAsset
        ? `Delete Uploaded ${assetLabel === 'video' ? 'Video' : 'Image'}`
        : `Remove ${assetLabel === 'video' ? 'Video' : 'Image'} from Index`;
    const message = isUploadedAsset
        ? `Delete "${fileName}"? This uploaded original is stored inside the app and will be permanently removed with its metadata and cached previews.`
        : `Remove "${fileName}" from the index? The physical file will remain on disk and may be indexed again during source reconciliation.`;
    const ok = await customConfirm(title, message);
    if (!ok) return false;

    try {
        await fetchJson(`/api/images/${imageId}`, { options: { method: 'DELETE' } });
        removeImageFromRuntime(imageId);
        await renderAfterImageRemoval();
        showToast(isUploadedAsset
            ? `Uploaded ${assetLabel} deleted`
            : `${assetLabel === 'video' ? 'Video' : 'Image'} removed from index`);
        return true;
    } catch(e) {
        showToast('Remove failed: ' + e.message);
        return false;
    }
}

export async function deleteAssetFileById(imageId) {
    const asset = images.find(item => item.id === imageId)
        || sidebarImages.find(item => item.id === imageId);
    const assetLabel = asset?.media_type === 'video' ? 'video' : 'image';
    if (!asset?.has_local_file) {
        showToast(`This ${assetLabel} has no available physical file`);
        return false;
    }

    try {
        const result = await fetchJson('/api/library/assets/trash', {
            options: {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ asset_ids: [imageId] }),
            },
        });
        if (!(result.removed_ids || []).includes(imageId)) {
            throw new Error(result.failures?.[0]?.error || 'The physical file could not be deleted');
        }
        removeImageFromRuntime(imageId);
        await renderAfterImageRemoval();
        showToast('File moved to the Recycle Bin / Trash');
        return true;
    } catch (error) {
        showToast('Delete failed: ' + error.message);
        return false;
    }
}

// Compatibility exports for code and extensions using the former image-only names.
export const deleteImageById = removeAssetFromIndexById;
export const deleteImageFileById = deleteAssetFileById;

export async function applyImageRename(renamedAsset) {
    const imageId = Number(renamedAsset?.id);
    const fileName = renamedAsset?.file_name;
    if (!Number.isInteger(imageId) || !fileName) return;

    [...images, ...sidebarImages].forEach(image => {
        if (image.id === imageId) image.file_name = fileName;
    });
    if (detailCache[imageId]) detailCache[imageId].file_name = fileName;
    invalidateApiCache();
    saveState();

    const { renderSidebar } = await import('./features/sidebar.js');
    renderSidebar({ reconcile: true });
    await renderCurrentContent({ reconcileGallery: true });

    if (dom.lightbox.classList.contains('open')) {
        const { syncLightboxAfterCollectionChange } = await import('./lightbox.js');
        syncLightboxAfterCollectionChange({ changedImageIds: new Set([imageId]) });
    }
}

export async function applyImageRating(ratedAsset) {
    const imageId = Number(ratedAsset?.id);
    const rating = Number(ratedAsset?.rating) || null;
    if (!Number.isInteger(imageId)) return;

    [...images, ...sidebarImages].forEach(image => {
        if (image.id === imageId) image.rating = rating;
    });
    if (detailCache[imageId]) detailCache[imageId].rating = rating;
    invalidateApiCache();

    if (ratingFilter !== null && (rating || 0) !== ratingFilter) {
        const loads = [loadSidebarImages({ force: true, render: false, preserveCount: true })];
        if (isBrowsableCollection(currentCollection)) {
            loads.push(loadCollectionImages(
                { ...currentCollection },
                { force: true, render: false, preserveCount: true },
            ));
        }
        await Promise.all(loads);
    }

    const { renderSidebar } = await import('./features/sidebar.js');
    renderSidebar({ reconcile: true });
    await renderCurrentContent({ reconcileGallery: true });

    if (dom.lightbox.classList.contains('open')) {
        const { syncLightboxAfterCollectionChange } = await import('./lightbox.js');
        syncLightboxAfterCollectionChange({ changedImageIds: new Set([imageId]) });
    }
}

export function deleteImageAt(index) {
    const asset = images[index];
    return asset ? removeAssetFromIndexById(asset.id) : Promise.resolve(false);
}

export async function loadCollectionImages(collection, { force = false, render = true, preserveCount = false } = {}) {
    setIsLoading(true);
    const collectionLabel = collection.type === 'album'
        ? 'album'
        : (collection.type === 'media' ? 'all' : 'folder');
    if (render && !preserveCount) showLoading(`Loading ${collectionLabel} media...`);
    try {
        const limit = preserveCount ? Math.max(PAGE_SIZE, currentPage * PAGE_SIZE) : PAGE_SIZE;
        const data = await fetchJson(collectionImagesUrl(collection, 1, limit), { force });
        const nextImages = data.images || [];
        const previousSignatures = new Map(images.map(img => [img.id, imageRenderSignature(img)]));
        const changedImageIds = new Set(
            nextImages
                .filter(img => previousSignatures.has(img.id) && previousSignatures.get(img.id) !== imageRenderSignature(img))
                .map(img => img.id),
        );
        const activeImageId = images[activeIndex]?.id;
        
        setCurrentCollection(collection);
        dom.folderNameEl.textContent = collection.name || '';
        setImages(nextImages);
        setTotalImages(data.total || 0);
        
        if (!preserveCount) {
            setCurrentPage(data.page || 1);
            setAllLoaded(nextImages.length >= (data.total || 0));
            setActiveIndex(nextImages.length ? 0 : -1);
        } else {
            setAllLoaded(images.length >= (data.total || 0));
            if (activeImageId) {
                const newIdx = images.findIndex(img => img.id === activeImageId);
                if (newIdx >= 0) {
                    setActiveIndex(newIdx);
                } else {
                    setActiveIndex(images.length ? 0 : -1);
                }
            }
        }
        if (preserveCount) {
            const nextIds = new Set([...nextImages, ...sidebarImages].map(img => img.id));
            setDetailCache(Object.fromEntries(
                Object.entries(detailCache).filter(([imageId]) => {
                    const numericId = Number(imageId);
                    return nextIds.has(numericId) && !changedImageIds.has(numericId);
                }),
            ));
        } else {
            setDetailCache({});
        }
        saveState();
        if (render) await renderCurrentContent({ reconcileGallery: preserveCount });
        
        if (preserveCount && dom.lightbox.classList.contains('open')) {
            const { syncLightboxAfterCollectionChange } = await import('./lightbox.js');
            syncLightboxAfterCollectionChange({ changedImageIds });
        }
        
        return data;
    } catch(e) {
        if (render) showError(`Error loading ${collection.type}: ` + e.message);
        throw e;
    } finally {
        setIsLoading(false);
    }
}

export function loadFolderImages(folderId, folderName, options = {}) {
    return loadCollectionImages({ type: 'folder', id: folderId, name: folderName || '' }, options);
}

export function loadAlbumImages(albumId, albumName, options = {}) {
    return loadCollectionImages({ type: 'album', id: albumId, name: albumName || '' }, options);
}

export function loadMediaCollection(options = {}) {
    return loadCollectionImages({ type: 'media', id: null, name: 'All Media' }, options);
}
