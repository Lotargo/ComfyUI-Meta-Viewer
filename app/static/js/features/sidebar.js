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
        dom.sidebarResize.classList.remove('active');
        document.removeEventListener('mousemove', onMouseMove);
        document.removeEventListener('mouseup', onMouseUp);
        document.body.style.cursor = '';
        document.body.style.userSelect = '';
    }
}

export function toggleSidebar() {
    if (!dom.sidebar) return;
    if (window.matchMedia('(max-width: 768px)').matches) {
        dom.sidebar.classList.toggle('open');
        dom.sidebar.classList.remove('collapsed');
    } else {
        dom.sidebar.classList.toggle('collapsed');
        dom.sidebar.classList.remove('open');
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

    if (dom.foldersCount) dom.foldersCount.textContent = `(${visibleFolders.length})`;

    if (visibleFolders.length === 0) {
        dom.folderList.innerHTML = `
            <div style="grid-column: 1 / -1; display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 60px 20px; color: var(--text-muted); text-align: center;">
                <div style="font-size: 48px; margin-bottom: 16px;">&#128193;</div>
                <p style="font-size: 14px; font-weight: 600; margin-bottom: 8px; color: var(--text);">No scanned folders yet.</p>
                <p style="font-size: 12px; line-height: 1.5; max-width: 200px;">Click "Open Folder" in the top bar to scan a directory.</p>
            </div>
        `;
        return;
    }

    dom.folderList.innerHTML = '';
    visibleFolders.forEach(folder => {
        const item = document.createElement('div');
        item.className = 'folder-item' + (folder.id === currentFolderId ? ' active' : '');
        
        const percentage = folder.image_count > 0 ? Math.round((folder.processed_count / folder.image_count) * 100) : 0;
        let progressHtml = '';
        let controlBtnHtml = '';
        
        if (folder.status === 'processing') {
            controlBtnHtml = `
                <button class="folder-control-btn folder-pause-btn" data-id="${folder.id}" title="Pause processing" aria-label="Pause processing ${escapeHtml(folder.name)}">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="6" y="4" width="4" height="16"></rect><rect x="14" y="4" width="4" height="16"></rect></svg>
                </button>
            `;
            progressHtml = `
                <div class="folder-progress-wrapper" style="width: 100%; display: flex; flex-direction: column; gap: 4px; margin-top: 4px; align-items: center;">
                    <div style="font-size: 9px; color: var(--text-dim); display: flex; justify-content: space-between; width: 100%;">
                        <span>Scanning...</span>
                        <span>${percentage}%</span>
                    </div>
                    <div style="width: 100%; height: 4px; background: var(--surface3); border-radius: 2px; overflow: hidden; position: relative;">
                        <div style="width: ${percentage}%; height: 100%; background: var(--accent); transition: width 0.3s ease;"></div>
                    </div>
                </div>
            `;
        } else if (folder.status === 'paused') {
            controlBtnHtml = `
                <button class="folder-control-btn folder-resume-btn" data-id="${folder.id}" title="Resume processing" aria-label="Resume processing ${escapeHtml(folder.name)}">
                    <svg viewBox="0 0 24 24" width="12" height="12" fill="currentColor" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                </button>
            `;
            progressHtml = `
                <div class="folder-progress-wrapper" style="width: 100%; display: flex; flex-direction: column; gap: 4px; margin-top: 4px; align-items: center;">
                    <div style="font-size: 9px; color: var(--text-muted); display: flex; justify-content: space-between; width: 100%;">
                        <span>Paused</span>
                        <span>${percentage}%</span>
                    </div>
                    <div style="width: 100%; height: 4px; background: var(--surface3); border-radius: 2px; overflow: hidden; position: relative;">
                        <div style="width: ${percentage}%; height: 100%; background: var(--text-muted); transition: width 0.3s ease;"></div>
                    </div>
                </div>
            `;
        }

        item.innerHTML = `
            ${controlBtnHtml}
            <div class="folder-item-content">
                <div class="folder-item-icon">📁</div>
                <div class="folder-item-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
                ${folder.scanned_at ? `<div class="folder-item-meta"><span class="folder-item-count">${folder.image_count}</span></div>` : ''}
                ${progressHtml}
            </div>
            <button class="folder-delete-btn" data-id="${folder.id}" title="Delete folder" aria-label="Delete folder ${escapeHtml(folder.name)}">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
            </button>
        `;

        item.onclick = async () => {
            const { loadFolderImages } = await import('../api.js');
            await loadFolderImages(folder.id, folder.name);
            await renderFoldersList(visibleFolders);
        };

        const pauseBtn = item.querySelector('.folder-pause-btn');
        if (pauseBtn) {
            pauseBtn.onclick = async event => {
                event.stopPropagation();
                try {
                    await fetch(`/api/folders/${folder.id}/pause`, { method: 'POST' });
                    const { getFolders } = await import('../api.js');
                    const list = await getFolders({ force: true });
                    await renderFoldersList(list);
                } catch (e) {
                    console.error(e);
                }
            };
        }

        const resumeBtn = item.querySelector('.folder-resume-btn');
        if (resumeBtn) {
            resumeBtn.onclick = async event => {
                event.stopPropagation();
                try {
                    await fetch(`/api/folders/${folder.id}/resume`, { method: 'POST' });
                    const { getFolders } = await import('../api.js');
                    const list = await getFolders({ force: true });
                    await renderFoldersList(list);
                } catch (e) {
                    console.error(e);
                }
            };
        }

        item.querySelector('.folder-delete-btn').onclick = async event => {
            event.stopPropagation();
            const confirmed = await customConfirm('Delete Folder', `Are you sure you want to remove folder "${folder.name}" from the database? This does not delete any files from your disk.`);
            if (!confirmed) return;

            const { deleteFolderFromServer, getFolders, loadFolderImages, loadSidebarImages } = await import('../api.js');
            if (!await deleteFolderFromServer(folder.id)) return;

            const updatedFolders = await getFolders({ force: true });
            setFolders(updatedFolders);

            if (currentFolderId === folder.id) {
                if (updatedFolders.length) {
                    await loadFolderImages(updatedFolders[0].id, updatedFolders[0].name, { force: true });
                } else {
                    setImages([]);
                    setTotalImages(0);
                    setCurrentFolderId(null);
                    setCurrentPage(0);
                    setAllLoaded(true);
                    setActiveIndex(-1);
                    dom.folderNameEl.textContent = '';
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

        dom.folderList.appendChild(item);
    });

    initFoldersSSE();
}

let foldersEventSource = null;

function initFoldersSSE() {
    if (foldersEventSource) return;

    foldersEventSource = new EventSource('/api/folders/events');
    foldersEventSource.onmessage = async (event) => {
        try {
            const state = JSON.parse(event.data);
            
            let changed = false;
            const updatedFolders = folders.map(f => {
                const update = state[String(f.id)];
                if (update) {
                    if (f.status !== update.status || f.processed_count !== update.processed_count || f.image_count !== update.image_count) {
                        changed = true;
                        return {
                            ...f,
                            status: update.status,
                            processed_count: update.processed_count,
                            image_count: update.image_count
                        };
                    }
                }
                return f;
            });
            
            if (changed) {
                setFolders(updatedFolders);
                await renderFoldersList(updatedFolders);
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
