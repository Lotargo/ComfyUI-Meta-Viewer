/**
 * Sidebar component - handles image list rendering and resize
 */

import { images, activeIndex, galleryActive, currentFolderId, sidebarAllLoaded, scrollObserver, sidebarTotalImages, dom, setActiveIndex, setScrollObserver, saveState, sidebarImages } from '../state.js';
import { escapeHtml, customConfirm, formatImageCountLabel } from '../utils.js';
import { createSidebarItem } from '../components/sidebar-item.js';

export function renderSidebar() {
    dom.imageList.innerHTML = '';
    dom.imageCount.textContent = formatImageCountLabel(sidebarImages.length, sidebarTotalImages);

    sidebarImages.forEach((img, i) => {
        // activeIndex in sidebar only makes sense if it's the exact same image
        // but we won't highlight activeIndex here unless we do a deep match.
        // For simplicity, we can pass false for isActive, or check img.id
        const currentActiveImg = images[activeIndex];
        const isActive = currentActiveImg && currentActiveImg.id === img.id;
        const div = createSidebarItem(img, i, isActive);
        
        div.onclick = () => selectSidebarImage(i);
        
        div.querySelector('.sidebar-delete')?.addEventListener('click', (e) => {
            e.stopPropagation();
            import('../api.js').then(m => m.deleteImageAt(images.findIndex(x => x.id === img.id)));
        });
        dom.imageList.appendChild(div);
    });

    appendSentinel();
    import('../components/search-bar.js').then(m => m.applySearchFilter());
}

export function appendSentinel() {
    if (scrollObserver) scrollObserver.disconnect();
    const existing = dom.imageList.querySelector('#scroll-sentinel');
    if (existing) existing.remove();
    if (sidebarAllLoaded) return;
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.height = '1px';
    dom.imageList.appendChild(sentinel);
    setScrollObserver(new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            import('../api.js').then(m => m.loadMoreSidebarImages());
        }
    }, { root: dom.imageList, threshold: 0.1 }));
    scrollObserver.observe(sentinel);
}

export async function selectImage(idx) {
    setActiveIndex(idx);
    saveState();
    
    // update active class in sidebar if possible
    const isImagesTab = dom.tabImages?.classList.contains('active');
    const currentList = isImagesTab ? sidebarImages : images;
    const currentActiveImg = currentList[idx];
    if (currentActiveImg) {
        dom.imageList.querySelectorAll('.image-item').forEach((el, i) => {
            const img = currentList[i];
            el.classList.toggle('active', img && img.id === currentActiveImg.id);
        });
    }

    const img = currentList[idx];
    if (!img) {
        const { renderMeta } = await import('../meta-view.js');
        return renderMeta(null);
    }
    if (galleryActive) {
        import('../lightbox.js').then(m => m.openLightbox(idx, currentList));
        return;
    }
    const { renderMeta } = await import('../meta-view.js');
    renderMeta(img);
}

export async function selectSidebarImage(idx) {
    const isImagesTab = dom.tabImages?.classList.contains('active');
    const currentList = isImagesTab ? sidebarImages : images;
    const img = currentList[idx];
    if (!img) return;

    if (galleryActive) {
        import('../lightbox.js').then(m => m.openLightbox(idx, currentList));
    } else {
        setActiveIndex(idx);
        saveState();

        // Update active class in sidebar
        dom.imageList.querySelectorAll('.image-item').forEach((el, i) => {
            el.classList.toggle('active', i === idx);
        });

        const { renderMeta } = await import('../meta-view.js');
        renderMeta(img);
    }
}

/**
 * Initialize sidebar resize functionality
 */
export function initSidebarResize() {
    if (!dom.sidebar || !dom.sidebarResize) return;

    let startX, startWidth;

    dom.sidebarResize.addEventListener('mousedown', (e) => {
        e.preventDefault();
        startX = e.clientX;
        startWidth = dom.sidebar.offsetWidth;
        dom.sidebarResize.classList.add('active');
        document.addEventListener('mousemove', onMouseMove);
        document.addEventListener('mouseup', onMouseUp);
        document.body.style.cursor = 'col-resize';
        document.body.style.userSelect = 'none';
    });

    function onMouseMove(e) {
        const diff = e.clientX - startX;
        const newWidth = Math.min(Math.max(startWidth + diff, 280), 500);
        dom.sidebar.style.width = newWidth + 'px';
    }

    function onMouseUp() {
        dom.sidebarResize.classList.remove('active');
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
    if (dom.sidebar) {
        if (window.matchMedia('(max-width: 768px)').matches) {
            dom.sidebar.classList.toggle('open');
            dom.sidebar.classList.remove('collapsed');
        } else {
            dom.sidebar.classList.toggle('collapsed');
            dom.sidebar.classList.remove('open');
        }
    }
}

export async function renderFoldersList() {
    if (!dom.folderList) return;

    const { getFolders } = await import('../api.js');
    const folders = await getFolders();

    if (dom.foldersCount) {
        dom.foldersCount.textContent = `(${folders.length})`;
    }

    if (folders.length === 0) {
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
    folders.forEach(folder => {
        const div = document.createElement('div');
        div.className = 'folder-item' + (folder.id === currentFolderId ? ' active' : '');

        div.innerHTML = `
            <div class="folder-item-content">
                <div class="folder-item-icon">📁</div>
                <div class="folder-item-name" title="${escapeHtml(folder.name)}">${escapeHtml(folder.name)}</div>
                
                ${folder.scanned_at ? `<div class="folder-item-meta">
                    <span class="folder-item-count">${folder.image_count}</span>
                </div>` : ''}
            </div>
            <button class="folder-delete-btn" data-id="${folder.id}" title="Delete folder" aria-label="Delete folder ${escapeHtml(folder.name)}">
                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="3 6 5 6 21 6"></polyline>
                    <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
                </svg>
            </button>
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

        dom.folderList.appendChild(div);
    });
}
