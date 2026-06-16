import { images, activeIndex, currentFolderId, currentPage, totalImages, allLoaded, detailCache, galleryActive, sessions, activeSessionId, dom, setImages, setActiveIndex, setCurrentFolderId, setCurrentPage, setTotalImages, setAllLoaded, setDetailCache, setGalleryActive, setIsLoading, isLoading, saveState } from './state.js';
import { createSession, getActiveSession, createSessionOnServer } from './sessions.js';
import { escapeHtml, thumbUrl, showLoading, showError } from './utils.js';

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
        const session = createSession(data.folder ? data.folder.name : path.split(/[/\\]/).pop());
        session.images = newImages;
        for (const img of newImages) images.push(img);
        // Sync with backend
        const srvSession = await createSessionOnServer(session.name, data.folder_id);
        if (srvSession) session.serverId = srvSession.id;
        setTotalImages(data.total || images.length);
        setCurrentPage(1);
        setAllLoaded(images.length >= totalImages);
        if (activeIndex < 0) setActiveIndex(images.length > 0 ? 0 : -1);
        setDetailCache({});
        dom.folderNameEl.textContent = data.folder ? data.folder.name : '';
        saveState();
        if (galleryActive) {
            const { renderGallery } = await import('./gallery.js');
            renderGallery();
        } else {
            const { renderSidebar } = await import('./sidebar.js');
            renderSidebar();
        }
        if (activeIndex >= 0) {
            const { selectImage } = await import('./sidebar.js');
            selectImage(activeIndex);
        }
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
            const session = createSession();
            session.images = data.images;
            for (const img of data.images) images.push(img);
            // Sync with backend
            const srvSession = await createSessionOnServer(session.name);
            if (srvSession) session.serverId = srvSession.id;
            setTotalImages(images.length);
            if (activeIndex < 0) setActiveIndex(0);
            saveState();
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                const { renderSidebar } = await import('./sidebar.js');
                renderSidebar();
            }
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
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
            if (data.folder_id) setCurrentFolderId(data.folder_id);
            const session = createSession();
            session.images = data.images;
            for (const img of data.images) images.push(img);
            // Sync with backend
            const srvSession = await createSessionOnServer(session.name, data.folder_id || null);
            if (srvSession) session.serverId = srvSession.id;
            setTotalImages(images.length);
            if (activeIndex < 0) setActiveIndex(0);
            saveState();
            if (galleryActive) {
                const { renderGallery } = await import('./gallery.js');
                renderGallery();
            } else {
                const { renderSidebar } = await import('./sidebar.js');
                renderSidebar();
            }
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
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
            const session = getActiveSession();
            for (const img of data.images) {
                images.push(img);
                if (session) session.images.push(img);
            }
            setCurrentPage(nextPage);
            setTotalImages(data.total);
            setAllLoaded(images.length >= data.total);
            saveState();
            const { renderSidebar } = await import('./sidebar.js');
            renderSidebar();
        }
    } catch(e) {
        console.error('loadMore error:', e);
    }
    setIsLoading(false);
}
