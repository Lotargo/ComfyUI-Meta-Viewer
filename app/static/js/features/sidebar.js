/**
 * Sidebar component - handles image list rendering and resize
 */

import { images, activeIndex, viewMode, galleryActive, currentFolderId, allLoaded, detailCache, scrollObserver, sessions, totalImages, dom, setActiveIndex, setScrollObserver, saveState } from '../state.js';
import { escapeHtml, thumbUrl } from '../utils.js';
import { createSidebarItem, createSessionHeader } from '../components/sidebar-item.js';

export function renderSidebar() {
    if (galleryActive) return;
    dom.imageList.innerHTML = '';
    dom.imageCount.textContent = totalImages ? `(${images.length}/${totalImages})` : '';
    const isGrid = viewMode === 'grid';

    if (sessions.length > 0) {
        for (const session of sessions) {
            const hdr = createSessionHeader(session);
            hdr.querySelector('.session-remove').addEventListener('click', (e) => {
                e.stopPropagation();
                import('../sessions.js').then(m => m.removeSession(session.id));
            });
            dom.imageList.appendChild(hdr);
            session.images.forEach(img => {
                const i = images.indexOf(img);
                if (i < 0) return;
                const div = createSidebarItem(img, i, i === activeIndex, isGrid);
                div.onclick = () => selectImage(i);
                dom.imageList.appendChild(div);
            });
        }
    } else {
        images.forEach((img, i) => {
            const div = createSidebarItem(img, i, i === activeIndex, isGrid);
            div.onclick = () => selectImage(i);
            dom.imageList.appendChild(div);
        });
    }

    appendSentinel();
}

export function appendSentinel() {
    if (scrollObserver) scrollObserver.disconnect();
    const existing = document.getElementById('scroll-sentinel');
    if (existing) existing.remove();
    if (allLoaded) return;
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.height = '1px';
    dom.imageList.appendChild(sentinel);
    setScrollObserver(new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            import('../api.js').then(m => m.loadMore());
        }
    }, { root: dom.imageList, threshold: 0.1 }));
    scrollObserver.observe(sentinel);
}

export async function selectImage(idx) {
    setActiveIndex(idx);
    saveState();
    renderSidebar();
    const img = images[idx];
    if (!img) {
        const { renderMeta } = await import('../meta-view.js');
        return renderMeta(null);
    }
    if (galleryActive) return;
    const { renderMeta } = await import('../meta-view.js');
    renderMeta(img);
    if (img.id && !detailCache[img.id]) {
        try {
            const resp = await fetch(`/api/images/${img.id}`);
            if (resp.ok) detailCache[img.id] = await resp.json();
        } catch (e) { /* ignore */ }
    }
}

/**
 * Initialize sidebar resize functionality
 */
export function initSidebarResize() {
    const sidebar = document.getElementById('sidebar');
    const handle = document.getElementById('sidebar-resize');
    if (!sidebar || !handle) return;

    let startX, startWidth;

    handle.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startX = e.clientX;
        startWidth = sidebar.offsetWidth;
        handle.classList.add('active');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    function onMouseMove(e) {
        const diff = e.clientX - startX;
        const newWidth = Math.min(Math.max(startWidth + diff, 280), 500);
        sidebar.style.width = newWidth + 'px';
    }

    function onMouseUp() {
        handle.classList.remove('active');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
}

/**
 * Toggle sidebar visibility
 */
export function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    if (sidebar) {
        sidebar.classList.toggle('collapsed');
    }
}
