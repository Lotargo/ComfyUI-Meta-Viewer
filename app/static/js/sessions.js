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
    const { renderSidebar } = await import('./features/sidebar.js');
    renderSidebar();
    const contentArea = document.getElementById('content-area');
    if (activeIndex >= 0) {
        const { renderMeta } = await import('./meta-view.js');
        renderMeta(images[activeIndex]);
    } else {
        contentArea.innerHTML = '<div class="empty-state anim-fade-in"><div class="icon"><svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg></div><p>No images loaded</p></div>';
    }
    // Sync with backend
    if (session.serverId) {
        try { await fetch(`/api/sessions/${session.serverId}`, { method: 'DELETE' }); } catch (e) { /* ignore */ }
    }
}

export async function fetchSessionsFromServer() {
    try {
        const resp = await fetch('/api/sessions');
        const data = await resp.json();
        return data.sessions || [];
    } catch (e) {
        return [];
    }
}

export async function createSessionOnServer(name, folderId) {
    try {
        const resp = await fetch('/api/sessions', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name: name || '', folder_id: folderId || null })
        });
        if (resp.ok) return await resp.json();
    } catch (e) { /* ignore */ }
    return null;
}

export async function deleteSessionOnServer(sessionId) {
    try { await fetch(`/api/sessions/${sessionId}`, { method: 'DELETE' }); } catch (e) { /* ignore */ }
}

export async function renameSessionOnServer(sessionId, name) {
    try {
        const resp = await fetch(`/api/sessions/${sessionId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ name })
        });
        if (resp.ok) return await resp.json();
    } catch (e) { /* ignore */ }
    return null;
}
