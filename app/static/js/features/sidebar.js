/**
 * Sidebar component. The Images tab owns the global image collection;
 * the Folders tab only selects the central folder collection.
 */

import {
    images,
    activeIndex,
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
        item.innerHTML = `
            <div class="folder-item-content">
                <div class="folder-item-icon">📁</div>
                <div class="folder-item-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
                ${folder.scanned_at ? `<div class="folder-item-meta"><span class="folder-item-count">${folder.image_count}</span></div>` : ''}
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

        item.querySelector('.folder-delete-btn').onclick = async event => {
            event.stopPropagation();
            const confirmed = await customConfirm('Delete Folder', `Are you sure you want to remove folder "${folder.name}" from the database? This does not delete any files from your disk.`);
            if (!confirmed) return;

            const { deleteFolderFromServer, getFolders, loadFolderImages } = await import('../api.js');
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

            await renderFoldersList(updatedFolders);
            const { showToast } = await import('../state.js');
            showToast('Folder deleted from database');
        };

        dom.folderList.appendChild(item);
    });
}
