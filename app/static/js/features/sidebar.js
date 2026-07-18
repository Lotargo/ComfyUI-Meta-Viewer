/**
 * Sidebar component. The Images tab owns the global image collection;
 * the Folders tab only selects the central folder collection.
 */

import {
    images,
    galleryActive,
    currentFolderId,
    sidebarAllLoaded,
    sidebarScrollObserver,
    sidebarTotalImages,
    dom,
    setActiveIndex,
    setSidebarScrollObserver,
    sidebarImages,
    sidebarActiveImageId,
    setSidebarActiveImageId,
    folders,
    setFolders,
    setImages,
    setTotalImages,
    setCurrentFolderId,
    setCurrentPage,
    setAllLoaded,
    viewMode,
    foldersSortKey,
    foldersSortDir,
    foldersViewMode,
    saveState,
    setSidebarCollapsed,
    setSidebarWidth,
    sidebarCollapsed,
    sidebarWidth,
    refreshCacheBuster,
} from '../state.js';
import { escapeHtml, customConfirm, formatImageCountLabel } from '../utils.js';
import { createSidebarItem } from '../components/sidebar-item.js';

export function renderSidebar() {
    dom.imageList.innerHTML = '';
    dom.imageCount.textContent = formatImageCountLabel(sidebarImages.length, sidebarTotalImages);

    sidebarImages.forEach((img, index) => {
        const isActive = sidebarActiveImageId === img.id;
        const item = createSidebarItem(img, index, isActive);
        item.onclick = () => selectSidebarImage(index);
        item.querySelector('.sidebar-delete')?.addEventListener('click', event => {
            event.stopPropagation();
            import('../api.js').then(module => module.deleteImageById(img.id));
        });
        dom.imageList.appendChild(item);
    });

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
            folder.id === currentFolderId ? 'active' : '',
            isSource ? 'physical-source' : '',
            !folder.enabled ? 'source-disabled' : '',
            `source-${sourceStatus}`,
        ].filter(Boolean).join(' ');

        const percentage = folder.image_count > 0
            ? Math.round((folder.processed_count / folder.image_count) * 100)
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
                    aria-label="Toggle recursive scanning for ${escapeHtml(folder.name)}">R</button>
                <button class="source-action-btn source-reconcile-btn" title="Reconcile now"
                    aria-label="Reconcile ${escapeHtml(folder.name)}" ${folder.enabled ? '' : 'disabled'}>
                    <svg viewBox="0 0 24 24" width="13" height="13" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M20 6v5h-5"></path><path d="M4 18v-5h5"></path><path d="M18.5 9A7 7 0 0 0 6 6.5L4 11"></path><path d="M5.5 15A7 7 0 0 0 18 17.5l2-4.5"></path></svg>
                </button>
            </div>
        ` : '';

        item.innerHTML = `
            ${sourceActions}
            <div class="folder-item-content">
                <div class="folder-item-icon">📁</div>
                <div class="folder-item-details">
                    <div class="folder-item-name" title="${escapeHtml(folder.path || folder.name)}">${escapeHtml(folder.name)}</div>
                    <div class="source-badges">
                        ${isSource ? `<span class="source-status source-status-${sourceStatus}"${errorTitle}>${statusLabels[sourceStatus] || sourceStatus}</span>` : ''}
                        ${folder.recursive && isSource ? '<span class="source-recursive-badge">Subfolders</span>' : ''}
                    </div>
                    ${progressHtml}
                </div>
                ${folder.scanned_at ? `<div class="folder-item-meta"><span class="folder-item-count">${folder.image_count}</span></div>` : ''}
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
            let revisionChanged = false;
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
                        revisionChanged ||= f.revision !== update.revision;
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
            if (revisionChanged) {
                refreshCacheBuster();
                const { invalidateApiCache, loadFolderImages, loadSidebarImages } = await import('../api.js');
                invalidateApiCache();
                await loadSidebarImages({ force: true, preserveCount: true });
                const activeFolder = updatedFolders.find(folder => folder.id === currentFolderId && folder.enabled);
                if (activeFolder) {
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
