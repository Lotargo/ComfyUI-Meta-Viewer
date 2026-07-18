/**
 * Sidebar component. The Images tab owns the global image collection;
 * the Folders and Albums tabs select the central Viewer collection.
 */

import {
    images,
    galleryActive,
    currentFolderId,
    sidebarAllLoaded,
    sidebarScrollObserver,
    sidebarTotalImages,
    dom,
    showToast,
    setActiveIndex,
    setSidebarScrollObserver,
    sidebarImages,
    sidebarActiveImageId,
    setSidebarActiveImageId,
    folders,
    albums,
    currentCollection,
    setFolders,
    setAlbums,
    setImages,
    setTotalImages,
    setCurrentFolderId,
    setCurrentPage,
    setAllLoaded,
    viewMode,
    foldersSortKey,
    foldersSortDir,
    foldersViewMode,
    albumsSortKey,
    albumsSortDir,
    albumsViewMode,
    saveState,
    setSidebarCollapsed,
    setSidebarWidth,
    sidebarCollapsed,
    sidebarWidth,
    refreshCacheBuster,
} from '../state.js';
import { escapeHtml, customConfirm, formatImageCountLabel, imageRenderSignature, originalUrl } from '../utils.js';
import { createSidebarItem } from '../components/sidebar-item.js';
import { showImageContextMenu } from '../components/image-context-menu.js';

function bindSidebarItem(item) {
    item.onclick = () => selectSidebarImage(Number.parseInt(item.dataset.index, 10));
    item.querySelector('.sidebar-delete')?.addEventListener('click', event => {
        event.stopPropagation();
        const index = Number.parseInt(item.dataset.index, 10);
        const imageId = sidebarImages[index]?.id;
        if (imageId) import('../api.js').then(module => module.deleteImageById(imageId));
    });
    item.addEventListener('contextmenu', event => {
        const index = Number.parseInt(item.dataset.index, 10);
        const img = sidebarImages[index];
        if (!img?.id) return;
        showImageContextMenu(event, {
            imageId: img.id,
            fileName: img.file_name || img.file || '',
            sourceUrl: originalUrl(img),
            canAccessOriginal: true,
            hasLocalFile: Boolean(img.id && img.has_local_file),
            extraSections: [[{
                label: 'Select object',
                icon: 'cutout',
                run: async () => {
                    const lightbox = await import('../lightbox.js');
                    await lightbox.openLightbox(index, sidebarImages);
                    const cutout = await import('./cutout.js');
                    cutout.openCutoutPanel();
                },
            }]],
            notify: showToast,
        });
    });
}

function reconcileSidebarItems() {
    const existingById = new Map(
        [...dom.imageList.querySelectorAll('.image-item[data-image-id]')]
            .map(item => [item.dataset.imageId, item]),
    );
    let cursor = dom.imageList.firstElementChild;

    sidebarImages.forEach((img, index) => {
        const imageId = String(img.id ?? '');
        const signature = imageRenderSignature(img);
        let item = existingById.get(imageId);
        if (!item || item.dataset.renderSignature !== signature) {
            const replacement = createSidebarItem(img, index, sidebarActiveImageId === img.id);
            bindSidebarItem(replacement);
            if (item) {
                const replacesCursor = item === cursor;
                item.replaceWith(replacement);
                if (replacesCursor) cursor = replacement;
                existingById.delete(imageId);
            }
            item = replacement;
        } else {
            existingById.delete(imageId);
            item.dataset.index = String(index);
            item.classList.toggle('active', sidebarActiveImageId === img.id);
            const deleteButton = item.querySelector('.sidebar-delete');
            if (deleteButton) deleteButton.dataset.index = String(index);
        }

        if (item !== cursor) dom.imageList.insertBefore(item, cursor);
        cursor = item.nextElementSibling;
    });

    existingById.forEach(item => item.remove());
}

export function renderSidebar({ reconcile = false } = {}) {
    dom.imageCount.textContent = formatImageCountLabel(sidebarImages.length, sidebarTotalImages);

    if (reconcile) {
        dom.imageList.querySelector('#scroll-sentinel')?.remove();
        reconcileSidebarItems();
    } else {
        dom.imageList.innerHTML = '';
        const fragment = document.createDocumentFragment();
        sidebarImages.forEach((img, index) => {
            const item = createSidebarItem(img, index, sidebarActiveImageId === img.id);
            bindSidebarItem(item);
            fragment.appendChild(item);
        });
        dom.imageList.appendChild(fragment);
    }

    appendSentinel();
    import('../components/search-bar.js').then(module => module.applySearchFilter());
}

export function appendSentinel() {
    if (sidebarScrollObserver) sidebarScrollObserver.disconnect();
    dom.imageList.querySelector('#scroll-sentinel')?.remove();
    if (sidebarAllLoaded) return;

    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.height = '1px';
    dom.imageList.appendChild(sentinel);

    const observer = new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            import('../api.js').then(module => module.loadMoreSidebarImages());
        }
    }, { root: dom.imageList, threshold: 0.1 });
    setSidebarScrollObserver(observer);
    observer.observe(sentinel);
}

// Central-image selection helper retained for list/detail interactions.
export async function selectImage(index) {
    const img = images[index];
    if (!img) {
        const { renderImageMeta } = await import('../detail-loader.js');
        await renderImageMeta(null);
        return;
    }
    setActiveIndex(index);
    if (galleryActive) {
        const { openLightbox } = await import('../lightbox.js');
        openLightbox(index, images);
        return;
    }
    const { renderImageMeta } = await import('../detail-loader.js');
    await renderImageMeta(img);
}

export async function selectSidebarImage(index) {
    const img = sidebarImages[index];
    if (!img) return;

    setSidebarActiveImageId(img.id);
    dom.imageList.querySelectorAll('.image-item').forEach((element, itemIndex) => {
        element.classList.toggle('active', itemIndex === index);
    });

    if (viewMode === 'upload') {
        const { setViewMode } = await import('../events.js');
        setViewMode('list', { render: false });
    }

    if (galleryActive) {
        const { openLightbox } = await import('../lightbox.js');
        openLightbox(index, sidebarImages);
        return;
    }

    const { renderImageMeta } = await import('../detail-loader.js');
    await renderImageMeta(img);
}

export function initSidebarResize() {
    if (!dom.sidebar || !dom.sidebarResize) return;
    let startX;
    let startWidth;

    dom.sidebarResize.addEventListener('mousedown', event => {
        event.preventDefault();
        startX = event.clientX;
        startWidth = dom.sidebar.offsetWidth;
        dom.sidebarResize.classList.add('active');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    function onMouseMove(event) {
        const diff = event.clientX - startX;
        dom.sidebar.style.width = Math.min(Math.max(startWidth + diff, 280), 500) + 'px';
    }

    function onMouseUp() {
        setSidebarWidth(dom.sidebar.offsetWidth);
        saveState();
        dom.sidebarResize.classList.remove('active');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }

    window.matchMedia('(max-width: 768px)').addEventListener?.('change', applySidebarLayout);
}

export function applySidebarLayout() {
    if (!dom.sidebar) return;
    dom.sidebar.style.width = `${sidebarWidth}px`;
    dom.sidebar.classList.remove('open');
    if (window.matchMedia('(max-width: 768px)').matches) {
        dom.sidebar.classList.remove('collapsed');
        return;
    }
    dom.sidebar.classList.toggle('collapsed', sidebarCollapsed);
}

export function toggleSidebar() {
    if (!dom.sidebar) return;
    if (window.matchMedia('(max-width: 768px)').matches) {
        dom.sidebar.classList.toggle('open');
        dom.sidebar.classList.remove('collapsed');
    } else {
        setSidebarCollapsed(!sidebarCollapsed);
        applySidebarLayout();
        saveState();
    }
}

export async function renderAlbumsList(albumList = null) {
    if (!dom.albumList) return;

    let visibleAlbums = Array.isArray(albumList) ? albumList : albums;
    if (!Array.isArray(albumList) && visibleAlbums.length === 0) {
        const { getAlbums } = await import('../api.js');
        visibleAlbums = await getAlbums();
        setAlbums(visibleAlbums);
    } else if (Array.isArray(albumList)) {
        setAlbums(albumList);
    }

    dom.albumList.classList.toggle('view-list', albumsViewMode === 'list');
    if (dom.albumsCount) dom.albumsCount.textContent = `(${visibleAlbums.length})`;
    if (dom.albumsViewBtn) {
        const listMode = albumsViewMode === 'list';
        dom.albumsViewBtn.innerHTML = listMode
            ? '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>'
            : '<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>';
        dom.albumsViewBtn.title = listMode ? 'Switch to Tile View' : 'Switch to List View';
    }

    if (visibleAlbums.length === 0) {
        dom.albumList.innerHTML = `
            <div class="viewer-albums-empty">
                <div class="viewer-albums-empty-icon" aria-hidden="true">
                    <svg viewBox="0 0 32 32" width="32" height="32" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="8" y="6" width="18" height="20" rx="3"></rect><path d="M8 22H6a3 3 0 0 1-3-3V7a3 3 0 0 1 3-3h14a3 3 0 0 1 3 3v1"></path><circle cx="14" cy="12" r="2"></circle><path d="m11 21 4-4 3 3 2.5-2.5L24 21"></path></svg>
                </div>
                <strong>No albums yet</strong>
                <p>Create and organize albums in Library.</p>
                <a class="btn btn-sm btn-secondary" href="/library">Open Library</a>
            </div>`;
        return;
    }

    const sortedAlbums = [...visibleAlbums].sort((a, b) => {
        const valueA = a[albumsSortKey] ?? '';
        const valueB = b[albumsSortKey] ?? '';
        if (typeof valueA === 'string' && typeof valueB === 'string') {
            const compared = valueA.localeCompare(valueB, undefined, { sensitivity: 'base' });
            return albumsSortDir === 'asc' ? compared : -compared;
        }
        const compared = Number(valueA) - Number(valueB);
        return albumsSortDir === 'asc' ? compared : -compared;
    });

    dom.albumList.innerHTML = '';
    sortedAlbums.forEach(album => {
        const item = document.createElement('button');
        item.type = 'button';
        item.className = [
            'folder-item',
            'album-item',
            !album.display_cover_image_id ? 'empty-album' : '',
            currentCollection.type === 'album' && currentCollection.id === album.id ? 'active' : '',
        ].filter(Boolean).join(' ');
        item.setAttribute('aria-label', `Open album ${album.name}`);
        const cover = album.display_cover_image_id
            ? `<img src="/api/thumbnail/${album.display_cover_image_id}" alt="" loading="lazy" draggable="false">`
            : `<span class="viewer-album-placeholder" aria-hidden="true">
                <svg viewBox="0 0 24 24" width="28" height="28" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="5" width="18" height="15" rx="2"></rect><path d="M3 9h18"></path><path d="m8 16 2.5-3 2 2 2.5-3 3 4"></path></svg>
            </span>`;
        const count = Number(album.asset_count) || 0;
        const countLabel = `${count.toLocaleString()} image${count === 1 ? '' : 's'}`;
        item.innerHTML = `
            <span class="folder-item-content">
                <span class="viewer-album-stack" aria-hidden="true">
                    <span class="viewer-album-cover">${cover}</span>
                </span>
                <span class="folder-item-details">
                    <span class="folder-item-name" title="${escapeHtml(album.name)}">${escapeHtml(album.name)}</span>
                    <span class="viewer-album-meta"><svg viewBox="0 0 16 16" width="12" height="12" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="4" y="3" width="9" height="10" rx="1.5"></rect><path d="M4 11H3a1.5 1.5 0 0 1-1.5-1.5v-6A1.5 1.5 0 0 1 3 2h7a1.5 1.5 0 0 1 1.5 1.5"></path></svg>${countLabel}</span>
                </span>
            </span>`;
        item.addEventListener('click', async () => {
            const { loadAlbumImages } = await import('../api.js');
            await loadAlbumImages(album.id, album.name);
            await renderAlbumsList();
        });
        dom.albumList.appendChild(item);
    });
}

export async function renderFoldersList(folderList = null) {
    if (!dom.folderList) return;

    let visibleFolders = Array.isArray(folderList) ? folderList : folders;
    if (!Array.isArray(folderList) && visibleFolders.length === 0) {
        const { getFolders } = await import('../api.js');
        visibleFolders = await getFolders();
        setFolders(visibleFolders);
    } else if (Array.isArray(folderList)) {
        setFolders(folderList);
    }

    // Toggle view-list class on folder list based on view mode
    dom.folderList.classList.toggle('view-list', foldersViewMode === 'list');
    if (dom.foldersViewBtn) {
        dom.foldersViewBtn.classList.toggle('active', foldersViewMode === 'list');
        if (foldersViewMode === 'list') {
            dom.foldersViewBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2" fill="none"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>`;
            dom.foldersViewBtn.title = 'Switch to Grid View';
        } else {
            dom.foldersViewBtn.innerHTML = `<svg viewBox="0 0 24 24" width="16" height="16" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" class="icon-list"><line x1="8" y1="6" x2="21" y2="6"></line><line x1="8" y1="12" x2="21" y2="12"></line><line x1="8" y1="18" x2="21" y2="18"></line><line x1="3" y1="6" x2="3.01" y2="6"></line><line x1="3" y1="12" x2="3.01" y2="12"></line><line x1="3" y1="18" x2="3.01" y2="18"></line></svg>`;
            dom.foldersViewBtn.title = 'Switch to List View';
        }
    }

    if (dom.foldersCount) dom.foldersCount.textContent = `(${visibleFolders.length})`;

    if (visibleFolders.length === 0) {
        dom.folderList.innerHTML = `
            <div style="grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: var(--text-muted); text-align: center;">
                <div style="font-size: 48px; margin-bottom: 16px;">&#128193;</div>
                <p style="font-size: 14px; font-weight: 600; margin-bottom: 8px; color: var(--text);">No sources yet.</p>
                <p style="font-size: 12px; line-height: 1.5; max-width: 200px;">Click "Open Folder" to connect a directory.</p>
            </div>
        `;
        return;
    }

    // Sort visibleFolders
    const sortedFolders = [...visibleFolders].sort((a, b) => {
        let valA = a[foldersSortKey];
        let valB = b[foldersSortKey];

        if (valA === undefined || valA === null) valA = '';
        if (valB === undefined || valB === null) valB = '';

        if (typeof valA === 'string' && typeof valB === 'string') {
            return foldersSortDir === 'asc' 
                ? valA.localeCompare(valB) 
                : valB.localeCompare(valA);
        }

        // For numbers like image_count
        if (valA < valB) return foldersSortDir === 'asc' ? -1 : 1;
        if (valA > valB) return foldersSortDir === 'asc' ? 1 : -1;
        return 0;
    });

    const statusLabels = {
        disabled: 'Disabled',
        available: 'Available',
        partially_available: 'Partial',
        unavailable: 'Unavailable',
        reconnecting: 'Reconnecting',
        error: 'Error',
    };

    dom.folderList.innerHTML = '';
    sortedFolders.forEach(folder => {
        const item = document.createElement('div');
        const isSource = !String(folder.path || '').startsWith('__uploads');
        const sourceStatus = folder.source_status || (folder.enabled ? 'available' : 'disabled');
        item.className = [
            'folder-item',
            'source-folder-item',
            folder.id === currentFolderId ? 'active' : '',
            isSource ? 'physical-source' : '',
            !isSource ? 'virtual-source' : '',
            !folder.enabled ? 'source-disabled' : '',
            folder.enabled && folder.status === 'processing' ? 'source-processing' : '',
            `source-${sourceStatus}`,
        ].filter(Boolean).join(' ');

        const imageCount = Number(folder.image_count) || 0;
        const imageCountLabel = `${imageCount.toLocaleString()} image${imageCount === 1 ? '' : 's'}`;
        const percentage = imageCount > 0
            ? Math.round((folder.processed_count / imageCount) * 100)
            : 0;
        const progressHtml = folder.enabled && folder.status === 'processing' ? `
            <div class="folder-progress-wrapper">
                <div class="folder-progress-label"><span>Indexing</span><span>${percentage}%</span></div>
                <div class="folder-progress-track"><div style="width: ${percentage}%"></div></div>
            </div>
        ` : '';
        const errorTitle = folder.last_error ? ` title="${escapeHtml(folder.last_error)}"` : '';
        const sourceActions = isSource ? `
            <div class="source-actions">
                <button class="source-action-btn source-toggle-btn ${folder.enabled ? 'active' : ''}"
                    title="${folder.enabled ? 'Disable source' : 'Enable source'}"
                    aria-label="${folder.enabled ? 'Disable' : 'Enable'} ${escapeHtml(folder.name)}">
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round"><path d="M12 2v10"></path><path d="M18.4 6.6a8 8 0 1 1-12.8 0"></path></svg>
                </button>
                <button class="source-action-btn source-recursive-btn ${folder.recursive ? 'active' : ''}"
                    title="${folder.recursive ? 'Disable subfolder scanning' : 'Include subfolders'}"
                    aria-label="Toggle recursive scanning for ${escapeHtml(folder.name)}">
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M6 3v8a4 4 0 0 0 4 4h8"></path><path d="m15 12 3 3-3 3"></path></svg>
                </button>
                <button class="source-action-btn source-reconcile-btn" title="Reconcile now"
                    aria-label="Reconcile ${escapeHtml(folder.name)}" ${folder.enabled ? '' : 'disabled'}>
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6v5h-5"></path><path d="M4 18v-5h5"></path><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11"></path><path d="M5.5 15A7 7 0 0 0 18 17.5l2-4.5"></path></svg>
                </button>
            </div>
        ` : '';

        item.innerHTML = `
            ${sourceActions}
            <div class="folder-item-content">
                <div class="folder-item-icon" aria-hidden="true">
                    <svg viewBox="0 0 24 24" width="17" height="17" stroke="currentColor" stroke-width="1.8" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M3 7.5A2.5 2.5 0 0 1 5.5 5H9l2 2h7.5A2.5 2.5 0 0 1 21 9.5v7A2.5 2.5 0 0 1 18.5 19h-13A2.5 2.5 0 0 1 3 16.5z"></path></svg>
                </div>
                <div class="folder-item-details">
                    <div class="folder-item-name" title="${escapeHtml(folder.path || folder.name)}">${escapeHtml(folder.name)}</div>
                    <div class="source-badges">
                        ${isSource ? `<span class="source-status source-status-${sourceStatus}"${errorTitle}>${statusLabels[sourceStatus] || sourceStatus}</span>` : ''}
                        ${folder.recursive && isSource ? '<span class="source-recursive-badge" title="Includes subfolders" aria-label="Includes subfolders"><svg viewBox="0 0 16 16" width="12" height="12" stroke="currentColor" stroke-width="1.7" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M4 2v5a3 3 0 0 0 3 3h5"></path><path d="m9.5 7.5 2.5 2.5-2.5 2.5"></path></svg></span>' : ''}
                    </div>
                    ${progressHtml}
                </div>
                ${folder.scanned_at ? `<div class="folder-item-meta"><span class="folder-item-count"><svg viewBox="0 0 16 16" width="12" height="12" stroke="currentColor" stroke-width="1.6" fill="none" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><rect x="2" y="3" width="12" height="10" rx="2"></rect><path d="m4.5 10 2.3-2.5 1.8 1.8 1.6-1.6 2.3 2.3"></path></svg>${imageCountLabel}</span></div>` : ''}
            </div>
            <button class="folder-delete-btn" data-id="${folder.id}" title="Forget source" aria-label="Forget ${escapeHtml(folder.name)}">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;

        item.onclick = async () => {
            if (!folder.enabled) {
                const { showToast } = await import('../state.js');
                showToast('Enable the source to view its images');
                return;
            }
            const { loadFolderImages } = await import('../api.js');
            await loadFolderImages(folder.id, folder.name);
            await renderFoldersList(visibleFolders);
        };

        item.querySelector('.source-toggle-btn')?.addEventListener('click', async event => {
            event.stopPropagation();
            const { updateSourceOnServer } = await import('../api.js');
            await updateSourceOnServer(folder.id, { enabled: !folder.enabled });
            await refreshAfterSourceMutation(folder.id);
            const { showToast } = await import('../state.js');
            showToast(folder.enabled ? 'Source disabled' : 'Source enabled; reconciling changes');
        });

        item.querySelector('.source-recursive-btn')?.addEventListener('click', async event => {
            event.stopPropagation();
            const { updateSourceOnServer } = await import('../api.js');
            await updateSourceOnServer(folder.id, { recursive: !folder.recursive });
            await refreshAfterSourceMutation(folder.id);
            const { showToast } = await import('../state.js');
            showToast(folder.recursive ? 'Subfolder scanning disabled' : 'Subfolder scanning enabled');
        });

        item.querySelector('.source-reconcile-btn')?.addEventListener('click', async event => {
            event.stopPropagation();
            const { reconcileSource } = await import('../api.js');
            await reconcileSource(folder.id);
            const { showToast } = await import('../state.js');
            showToast('Source reconciliation queued');
        });

        const deleteBtn = item.querySelector('.folder-delete-btn');
        if (deleteBtn) {
            deleteBtn.onclick = async event => {
                event.stopPropagation();
                const confirmed = await customConfirm('Delete Folder', `Are you sure you want to remove folder "${folder.name}" from the database? This does not delete any files from your disk.`);
                if (!confirmed) return;

                const { deleteFolderFromServer, getFolders, loadFolderImages, loadSidebarImages } = await import('../api.js');
                if (!await deleteFolderFromServer(folder.id)) return;

                const updatedFolders = await getFolders({ force: true });
                setFolders(updatedFolders);

                if (currentFolderId === folder.id) {
                    const nextFolder = updatedFolders.find(candidate => candidate.enabled);
                    if (nextFolder) {
                        await loadFolderImages(nextFolder.id, nextFolder.name, { force: true });
                    } else {
                        setImages([]);
                        setTotalImages(0);
                        setCurrentFolderId(null);
                        setCurrentPage(0);
                        setAllLoaded(true);
                        setActiveIndex(-1);
                        dom.folderNameEl.textContent = '';
                        saveState();
                        if (galleryActive) {
                            const { renderGallery } = await import('../gallery.js');
                            renderGallery();
                        } else {
                            const { renderImageMeta } = await import('../detail-loader.js');
                            await renderImageMeta(null);
                        }
                    }
                }

                // Refresh the global Images tab list
                await loadSidebarImages({ force: true });

                await renderFoldersList(updatedFolders);
                const { showToast } = await import('../state.js');
                showToast('Folder deleted from database');
            };
        }

        dom.folderList.appendChild(item);
    });

    initFoldersSSE();
}

async function refreshAfterSourceMutation(folderId) {
    const { getFolders, loadFolderImages, loadSidebarImages } = await import('../api.js');
    const updatedFolders = await getFolders({ force: true });
    setFolders(updatedFolders);
    const changedFolder = updatedFolders.find(folder => folder.id === folderId);

    if (currentFolderId === folderId) {
        if (changedFolder?.enabled) {
            await loadFolderImages(folderId, changedFolder.name, { force: true });
        } else {
            const nextFolder = updatedFolders.find(folder => folder.enabled);
            if (nextFolder) {
                await loadFolderImages(nextFolder.id, nextFolder.name, { force: true });
            } else {
                setImages([]);
                setTotalImages(0);
                setCurrentFolderId(null);
                setCurrentPage(0);
                setAllLoaded(true);
                setActiveIndex(-1);
                dom.folderNameEl.textContent = '';
                saveState();
                const { renderCurrentContent } = await import('../events.js');
                await renderCurrentContent();
            }
        }
    }

    await loadSidebarImages({ force: true });
    await renderFoldersList(updatedFolders);
}

let foldersEventSource = null;

function initFoldersSSE() {
    if (foldersEventSource) return;

    foldersEventSource = new EventSource('/api/folders/events');
    foldersEventSource.onmessage = async (event) => {
        try {
            const state = JSON.parse(event.data);

            // Source rows can appear or disappear after add/remove/reset operations.
            const serverIds = new Set(Object.keys(state));
            const localIds = new Set(folders.map(f => String(f.id)));
            const idsChanged = serverIds.size !== localIds.size || [...serverIds].some(id => !localIds.has(id));

            if (idsChanged) {
                const { getFolders } = await import('../api.js');
                const freshFolders = await getFolders({ force: true });
                setFolders(freshFolders);
                await renderFoldersList(freshFolders);
                return;
            }
            
            let changed = false;
            const contentChangedSourceIds = new Set();
            let activeSourceDisabled = false;
            const trackedFields = [
                'status',
                'processed_count',
                'image_count',
                'enabled',
                'recursive',
                'source_status',
                'last_error',
                'revision',
                'name',
            ];
            const updatedFolders = folders.map(f => {
                const update = state[String(f.id)];
                if (update) {
                    if (trackedFields.some(field => f[field] !== update[field])) {
                        changed = true;
                        if (
                            f.revision !== update.revision
                            || f.processed_count !== update.processed_count
                            || f.image_count !== update.image_count
                        ) {
                            contentChangedSourceIds.add(f.id);
                        }
                        activeSourceDisabled ||= f.id === currentFolderId && !update.enabled;
                        return { ...f, ...update };
                    }
                }
                return f;
            });

            if (changed) {
                setFolders(updatedFolders);
                await renderFoldersList(updatedFolders);
            }
            if (activeSourceDisabled) {
                await refreshAfterSourceMutation(currentFolderId);
                return;
            }
            if (contentChangedSourceIds.size > 0) {
                refreshCacheBuster();
                const { invalidateApiCache, loadFolderImages, loadSidebarImages } = await import('../api.js');
                invalidateApiCache();
                await loadSidebarImages({ force: true, preserveCount: true });
                const activeFolder = updatedFolders.find(folder => folder.id === currentFolderId && folder.enabled);
                if (activeFolder && contentChangedSourceIds.has(activeFolder.id)) {
                    await loadFolderImages(activeFolder.id, activeFolder.name, { force: true, preserveCount: true });
                }
            }
        } catch (e) {
            console.error('SSE message parsing error:', e);
        }
    };
    
    foldersEventSource.onerror = (e) => {
        console.warn('SSE connection error, closing...', e);
        foldersEventSource.close();
        foldersEventSource = null;
        setTimeout(initFoldersSSE, 5000);
    };
}
