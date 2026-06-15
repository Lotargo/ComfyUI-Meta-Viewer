import { saveState, dom, images, setImages, sessions, setSessions, setActiveSessionId, setTotalImages, setAllLoaded, setCurrentPage, activeIndex, setActiveIndex, currentFolderId, setCurrentFolderId } from './state.js';
import { createSession } from './sessions.js';
import { initEvents, setViewMode } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar } from './sidebar.js';

async function restoreState() {
    try {
        const saved = sessionStorage.getItem('cmv_state');
        if (!saved) return;
        const state = JSON.parse(saved);
        if (!state.folderId) return;

        setCurrentFolderId(state.folderId);
        if (state.viewMode) setViewMode(state.viewMode);
        if (state.folderName) dom.folderNameEl.textContent = state.folderName;

        setImages([]);
        setSessions([]);
        setActiveSessionId(0);
        let page = 1;
        let total = 0;
        do {
            const resp = await fetch(`/api/images?folder_id=${currentFolderId}&page=${page}&per_page=100`);
            const data = await resp.json();
            if (data.images && data.images.length) {
                for (const img of data.images) images.push(img);
                total = data.total || 0;
                page++;
            } else {
                break;
            }
        } while (images.length < total);

        setTotalImages(images.length);
        setAllLoaded(true);
        setCurrentPage(page - 1);

        if (images.length > 0) {
            const session = createSession(state.folderName || 'Session');
            session.images = [...images];
        }

        if (state.activeIndex >= 0 && state.activeIndex < images.length) {
            setActiveIndex(state.activeIndex);
        } else if (images.length > 0) {
            setActiveIndex(0);
        }

        renderSidebar();

        if (activeIndex >= 0 && images[activeIndex]) {
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
        }
    } catch(e) {
        console.warn('State restore failed:', e);
    }
}

initEvents();
initLightboxEvents();
restoreState();
