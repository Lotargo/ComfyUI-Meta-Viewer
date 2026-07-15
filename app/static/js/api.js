import { images, activeIndex, currentFolderId, currentPage, totalImages, allLoaded, detailCache, galleryActive, dom, setImages, setActiveIndex, setCurrentFolderId, setCurrentPage, setTotalImages, setAllLoaded, setDetailCache, setIsLoading, isLoading, saveState, showToast, sidebarImages, setSidebarImages, setSidebarTotalImages, sidebarTotalImages, setSidebarPage, sidebarPage, setSidebarAllLoaded, sidebarAllLoaded } from './state.js';
import { showLoading, showError, customConfirm } from './utils.js';

function switchToImagesTab() {
    document.getElementById('tab-images')?.classList.add('active');
    document.getElementById('tab-folders')?.classList.remove('active');
    document.getElementById('panel-images')?.classList.add('active');
    document.getElementById('panel-folders')?.classList.remove('active');
}

export async function scanFolder(path) {
    showLoading('Scanning folder...');
    try {
        const resp = await fetch('/api/scan', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({path})
        });
        const data = await resp.json();
        if (data.error) { showError(data.error); return; }

        setCurrentFolderId(data.folder_id);
        const newImages = data.images || [];
        setImages(newImages);
        setTotalImages(data.total || images.length);
        setCurrentPage(1);
        setAllLoaded(images.length >= totalImages);
        setActiveIndex(images.length > 0 ? 0 : -1);
        setDetailCache({});
        dom.folderNameEl.textContent = data.folder ? data.folder.name : '';
        saveState();
        switchToImagesTab();
        
        await loadSidebarImages();
        
        const { renderSidebar } = await import('./features/sidebar.js');
        
        if (galleryActive) {
            const { renderGallery } = await import('./gallery.js');
            renderGallery();
        } else {
            renderSidebar();
            if (activeIndex >= 0) {
                const { renderMeta } = await import('./meta-view.js');
                renderMeta(images[activeIndex]);
            }
        }
        
        const { renderFoldersList } = await import('./features/sidebar.js');
        await renderFoldersList();
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadFromPaths(paths) {
    showLoading('Loading...');
    try {
        const resp = await fetch('/api/extract', {
            method: 'POST',
            headers: {'Content-Type':'application/json'},
            body: JSON.stringify({paths})
        });
        const data = await resp.json();
        if (data.images && data.images.length) {
            for (const img of data.images) images.push(img);
            setTotalImages(images.length);
            setAllLoaded(true);
            setCurrentPage(1);
            if (activeIndex < 0) setActiveIndex(0);
            saveState();
            
            await loadSidebarImages();
            
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                switchToImagesTab();
                const { renderSidebar } = await import('./features/sidebar.js');
                renderSidebar();
            }
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
            
            const { renderFoldersList } = await import('./features/sidebar.js');
            await renderFoldersList();
        } else {
            showError('No images found');
        }
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadFromFiles(files) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    showLoading('Processing ' + files.length + ' files...');
    try {
        const resp = await fetch('/api/upload', { method: 'POST', body: formData });
        const data = await resp.json();
        if (data.images && data.images.length) {
            if (data.folder_id) {
                setCurrentFolderId(data.folder_id);
                dom.folderNameEl.textContent = 'Uploads';
            }
            for (const img of data.images) images.push(img);
            setTotalImages(images.length);
            setAllLoaded(true);
            setCurrentPage(1);
            if (activeIndex < 0) setActiveIndex(0);
            saveState();
            
            await loadSidebarImages();
            
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                switchToImagesTab();
                const { renderSidebar } = await import('./features/sidebar.js');
                renderSidebar();
            }
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
            
            const { renderFoldersList } = await import('./features/sidebar.js');
            await renderFoldersList();
        } else {
            showError('No images found');
        }
    } catch(e) {
        showError('Error: ' + e.message);
    }
}

export async function loadMore() {
    if (isLoading || allLoaded || !currentFolderId) return;
    setIsLoading(true);
    const nextPage = currentPage + 1;
    try {
        const resp = await fetch(`/api/images?folder_id=${currentFolderId}&page=${nextPage}&per_page=50`);
        const data = await resp.json();
        if (data.images && data.images.length) {
            for (const img of data.images) {
                images.push(img);
            }
            setCurrentPage(nextPage);
            setTotalImages(data.total);
            setAllLoaded(images.length >= data.total);
            saveState();
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                const { renderSidebar } = await import('./features/sidebar.js');
                renderSidebar();
            }
        }
    } catch(e) {
        console.error('loadMore error:', e);
    }
    setIsLoading(false);
}

export async function loadSidebarImages() {
    setIsLoading(true);
    try {
        let page = 1;
        const resp = await fetch(`/api/images?page=${page}&per_page=100`);
        const data = await resp.json();
        if (data.images && data.images.length) {
            setSidebarImages(data.images);
            setSidebarTotalImages(data.total);
            setSidebarPage(page);
            setSidebarAllLoaded(data.images.length >= data.total);
        } else {
            setSidebarImages([]);
            setSidebarTotalImages(0);
            setSidebarAllLoaded(true);
        }
    } catch(e) {
        console.error('loadSidebarImages error:', e);
    } finally {
        setIsLoading(false);
    }
}

export async function loadMoreSidebarImages() {
    if (isLoading || sidebarAllLoaded) return;
    setIsLoading(true);
    const nextPage = sidebarPage + 1;
    try {
        const resp = await fetch(`/api/images?page=${nextPage}&per_page=50`);
        const data = await resp.json();
        if (data.images && data.images.length) {
            for (const img of data.images) {
                sidebarImages.push(img);
            }
            setSidebarPage(nextPage);
            setSidebarTotalImages(data.total);
            setSidebarAllLoaded(sidebarImages.length >= data.total);
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                const { renderSidebar } = await import('./features/sidebar.js');
                renderSidebar();
            }
        }
    } catch(e) {
        console.error('loadMoreSidebarImages error:', e);
    }
    setIsLoading(false);
}

export async function getFolders() {
    try {
        const resp = await fetch('/api/folders');
        const data = await resp.json();
        return data.folders || [];
    } catch (e) {
        console.error('Failed to fetch folders:', e);
        return [];
    }
}

export async function deleteFolderFromServer(folderId) {
    try {
        const resp = await fetch(`/api/folders/${folderId}`, { method: 'DELETE' });
        return resp.ok;
    } catch (e) {
        console.error('Failed to delete folder:', e);
        return false;
    }
}

export async function deleteImageAt(index) {
    const img = images[index];
    if (!img) return false;

    const fileName = img.file_name || img.file || 'this image';
    const ok = await customConfirm(
        'Delete Image',
        `Remove "${fileName}" from the viewer? Files scanned from disk will not be deleted from the folder.`
    );
    if (!ok) return false;

    try {
        if (img.id) {
            const resp = await fetch(`/api/images/${img.id}`, { method: 'DELETE' });
            if (!resp.ok) {
                const data = await resp.json().catch(() => ({}));
                showError(data.error || 'Failed to delete image');
                return false;
            }
            delete detailCache[img.id];
        }

        images.splice(index, 1);
        setTotalImages(Math.max(0, totalImages - 1));

        if (images.length === 0) {
            setActiveIndex(-1);
        } else if (activeIndex >= images.length) {
            setActiveIndex(images.length - 1);
        } else if (index <= activeIndex) {
            setActiveIndex(Math.max(0, activeIndex - 1));
        }

        saveState();

        if (galleryActive) {
            const { renderGallery } = await import('./gallery.js');
            renderGallery();
        } else {
            const { renderSidebar } = await import('./features/sidebar.js');
            renderSidebar();
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex] || null);
        }

        showToast('Image removed');
        return true;
    } catch(e) {
        showError('Delete failed: ' + e.message);
        return false;
    }
}

export async function loadFolderImages(folderId, folderName) {
    showLoading('Loading folder images...');
    setIsLoading(true);
    try {
        setCurrentFolderId(folderId);
        setImages([]);
        setDetailCache({});
        dom.folderNameEl.textContent = folderName || '';
        
        let page = 1;
        let total = 0;
        const loadedImages = [];
        
        do {
            const resp = await fetch(`/api/images?folder_id=${folderId}&page=${page}&per_page=100`);
            const data = await resp.json();
            if (data.images && data.images.length) {
                loadedImages.push(...data.images);
                total = data.total || 0;
                page++;
            } else {
                break;
            }
        } while (loadedImages.length < total);
        
        setImages(loadedImages);
        setTotalImages(total || loadedImages.length);
        setCurrentPage(page - 1);
        setAllLoaded(loadedImages.length >= (total || loadedImages.length));
        
        if (loadedImages.length > 0) {
            setActiveIndex(0);
        } else {
            setActiveIndex(-1);
        }
        
        saveState();
        
        if (galleryActive) {
            const { renderGallery } = await import('./gallery.js');
            renderGallery();
        } else {
            switchToImagesTab();
            const { renderSidebar } = await import('./features/sidebar.js');
            renderSidebar();
            if (activeIndex >= 0) {
                const { renderMeta } = await import('./meta-view.js');
                renderMeta(images[activeIndex]);
            }
        }
    } catch(e) {
        showError('Error loading folder: ' + e.message);
    } finally {
        setIsLoading(false);
    }
}
