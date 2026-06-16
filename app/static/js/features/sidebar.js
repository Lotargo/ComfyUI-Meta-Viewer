/**
 * Sidebar component - handles image list rendering and resize
 */

import { images, activeIndex, galleryActive, currentFolderId, allLoaded, detailCache, scrollObserver, totalImages, dom, setActiveIndex, setScrollObserver, saveState } from '../state.js';
import { escapeHtml, customConfirm, formatImageCountLabel } from '../utils.js';
import { createSidebarItem } from '../components/sidebar-item.js';

export function renderSidebar() {
    if (galleryActive) return;
    dom.imageList.innerHTML = '';
    dom.imageCount.textContent = formatImageCountLabel(images.length, totalImages);

    images.forEach((img, i) => {
        const div = createSidebarItem(img, i, i === activeIndex);
        div.onclick = () => selectImage(i);
        div.querySelector('.sidebar-delete')?.addEventListener('click', (e) => {
            e.stopPropagation();
            import('../api.js').then(m => m.deleteImageAt(i));
        });
        dom.imageList.appendChild(div);
    });

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
    if (galleryActive) {
        dom.imageList.querySelectorAll('.image-item').forEach((el, i) => {
            el.classList.toggle('active', i === idx);
        });
        import('../lightbox.js').then(m => m.openLightbox(idx));
        return;
    }
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
        if (window.matchMedia('(max-width: 768px)').matches) {
            sidebar.classList.toggle('open');
            sidebar.classList.remove('collapsed');
        } else {
            sidebar.classList.toggle('collapsed');
            sidebar.classList.remove('open');
        }
    }
}

export async function renderFoldersList() {
    const folderListEl = document.getElementById('folder-list');
    const foldersCountEl = document.getElementById('folders-count');
    if (!folderListEl) return;

    folderListEl.innerHTML = '<div style="padding: 12px; color: var(--text-dim)">Loading folders...</div>';

    const { getFolders } = await import('../api.js');
    const folders = await getFolders();

    if (foldersCountEl) {
        foldersCountEl.textContent = `(${folders.length})`;
    }

    if (folders.length === 0) {
        folderListEl.innerHTML = `
            <div style="padding: 24px; text-align: center; color: var(--text-muted)">
                <div style="font-size: 24px; margin-bottom: 8px;">&#128193;</div>
                <p style="font-size: 12px;">No scanned folders yet.</p>
                <p style="font-size: 11px; margin-top: 4px;">Click "Open Folder" in the top bar to scan a directory.</p>
            </div>
        `;
        return;
    }

    folderListEl.innerHTML = '';
    folders.forEach(folder => {
        const div = document.createElement('div');
        div.className = 'folder-item' + (folder.id === currentFolderId ? ' active' : '');

        const dateStr = folder.scanned_at ? new Date(folder.scanned_at).toLocaleString() : '';
        const isUploads = folder.path === '__uploads__';
        const displayPath = isUploads ? 'Stored inside app library' : folder.path;
        const folderType = isUploads ? 'Uploads' : 'Folder';

        div.innerHTML = `
            <div class="folder-item-content">
                <div class="folder-item-topline">
                    <span class="folder-item-icon" aria-hidden="true">
                        <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path></svg>
                    </span>
                    <div class="folder-item-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
                    <span class="folder-item-type">${folderType}</span>
                </div>
                <div class="folder-item-path" title="${escapeHtml(displayPath)}">${escapeHtml(displayPath)}</div>
                <div class="folder-item-meta">
                    <span class="folder-item-count">${folder.image_count} image${folder.image_count === 1 ? '' : 's'}</span>
                    <span class="folder-item-time">${escapeHtml(dateStr)}</span>
                </div>
            </div>
            <button class="folder-delete-btn" title="Delete from database">&times;</button>
        `;

        div.onclick = async () => {
            const { loadFolderImages } = await import('../api.js');
            await loadFolderImages(folder.id, folder.name);
        };

        const deleteBtn = div.querySelector('.folder-delete-btn');
        deleteBtn.onclick = async (e) => {
            e.stopPropagation();
            const ok = await customConfirm('Delete Folder', `Are you sure you want to remove folder "${folder.name}" from the database? This does not delete any files from your disk.`);
            if (ok) {
                const { deleteFolderFromServer } = await import('../api.js');
                const ok = await deleteFolderFromServer(folder.id);
                if (ok) {
                    const { setImages, setTotalImages, setCurrentFolderId } = await import('../state.js');
                    if (currentFolderId === folder.id) {
                        setImages([]);
                        setTotalImages(0);
                        setCurrentFolderId(null);
                    }
                    await renderFoldersList();
                    const { showToast } = await import('../state.js');
                    showToast('Folder deleted from database');
                }
            }
        };

        folderListEl.appendChild(div);
    });
}
