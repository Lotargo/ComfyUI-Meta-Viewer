import { sessions, activeSessionId, images, setActiveSessionId, setSessions, setImages, setTotalImages, activeIndex, setActiveIndex, setAllLoaded, saveState } from './state.js';

export function createSession(name) {
    const newId = activeSessionId + 1;
    setActiveSessionId(newId);
    const session = { id: newId, name: name || formatSessionName(), images: [], startIdx: images.length };
    sessions.push(session);
    return session;
}

export function formatSessionName() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' });
}

export function getActiveSession() {
    return sessions.find(s => s.id === activeSessionId);
}

export async function removeSession(sessionId) {
    const idx = sessions.findIndex(s => s.id === sessionId);
    if (idx < 0) return;
    const session = sessions[idx];
    const removedCount = session.images.length;
    images.splice(session.startIdx, removedCount);
    sessions.splice(idx, 1);
    let offset = 0;
    for (const s of sessions) {
        s.startIdx = offset;
        offset += s.images.length;
    }
    let newActiveIndex = activeIndex;
    if (newActiveIndex >= images.length) newActiveIndex = images.length > 0 ? images.length - 1 : -1;
    setActiveIndex(newActiveIndex);
    setTotalImages(images.length);
    saveState();
    const { renderSidebar } = await import('./sidebar.js');
    renderSidebar();
    const contentArea = document.getElementById('content-area');
    if (activeIndex >= 0) {
        const { renderMeta } = await import('./meta-view.js');
        renderMeta(images[activeIndex]);
    } else {
        contentArea.innerHTML = '<div class="empty-state anim-fade-in"><div class="icon">&#128444;</div><p>No images loaded</p></div>';
    }
}
