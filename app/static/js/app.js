import { saveState, dom, images, setImages, sessions, setSessions, setActiveSessionId, setTotalImages, setAllLoaded, setCurrentPage, activeIndex, setActiveIndex, currentFolderId, setCurrentFolderId } from './state.js';
import { createSession, fetchSessionsFromServer } from './sessions.js';
import { initEvents, setViewMode } from './events.js';
import { initLightboxEvents } from './lightbox.js';
import { renderSidebar, initSidebarResize, toggleSidebar } from './features/sidebar.js';
import { initSearch } from './components/search-bar.js';
import { initKeyboardShortcuts } from './features/keyboard.js';

async function restoreState() {
    try {
        const serverSessions = await fetchSessionsFromServer();
        if (!serverSessions.length) {
            // Try legacy sessionStorage restore
            const saved = sessionStorage.getItem('cmv_state');
            if (saved) {
                const state = JSON.parse(saved);
                if (state.folderId) {
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
                        // Persist to backend
                        const { createSessionOnServer } = await import('./sessions.js');
                        await createSessionOnServer(session.name, currentFolderId);
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
                    return;
                }
            }
            return;
        }

        // Load sessions from backend
        setImages([]);
        setSessions([]);
        setActiveSessionId(0);

        for (const srvSession of serverSessions) {
            const localSession = createSession(srvSession.name);
            localSession.serverId = srvSession.id;
            localSession.folderId = srvSession.folder_id;

            if (srvSession.folder_id && srvSession.image_count > 0) {
                let page = 1;
                let total = srvSession.image_count;
                do {
                    const resp = await fetch(`/api/images?folder_id=${srvSession.folder_id}&page=${page}&per_page=100`);
                    const data = await resp.json();
                    if (data.images && data.images.length) {
                        for (const img of data.images) {
                            images.push(img);
                            localSession.images.push(img);
                        }
                        total = data.total || 0;
                        page++;
                    } else {
                        break;
                    }
                } while (localSession.images.length < total);
            }
        }

        setTotalImages(images.length);
        setAllLoaded(true);
        setCurrentPage(1);

        if (images.length > 0) {
            setActiveIndex(0);
        }

        renderSidebar();

        if (activeIndex >= 0 && images[activeIndex]) {
            const { renderMeta } = await import('./meta-view.js');
            renderMeta(images[activeIndex]);
        }
    } catch (e) {
        console.warn('State restore failed:', e);
    }
}

// Initialize
initEvents();
initLightboxEvents();
initSidebarResize();
initSearch();
initKeyboardShortcuts();
restoreState();

// Sidebar toggle
document.getElementById('sidebar-toggle')?.addEventListener('click', toggleSidebar);
