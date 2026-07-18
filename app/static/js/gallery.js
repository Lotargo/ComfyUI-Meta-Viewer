/**
 * Central gallery view. The source collection is always the currently selected folder.
 */

import {
    images,
    activeIndex,
    currentCollection,
    allLoaded,
    galleryScrollObserver,
    dom,
    setGalleryScrollObserver,
} from './state.js';
import { escapeHtml, thumbUrl } from './utils.js';
import { skeletonGalleryCard } from './components/skeleton.js';

let resizeTimeout = null;
export function resizeAllGridItems() {
    if (resizeTimeout) cancelAnimationFrame(resizeTimeout);
    resizeTimeout = requestAnimationFrame(() => {
        const grid = document.querySelector('.gallery-masonry');
        if (!grid) return;
        const items = grid.querySelectorAll('.gallery-card');
        items.forEach(item => {
            const wrapper = item.querySelector('.img-wrapper');
            if (!wrapper) return;
            const cardHeight = wrapper.getBoundingClientRect().height;
            const rowHeight = 10;
            const rowGap = 14;
            // Add 2px to account for borders (1px top + 1px bottom)
            const rowSpan = Math.ceil((cardHeight + 2 + rowGap) / (rowHeight + rowGap));
            item.style.gridRowEnd = `span ${rowSpan}`;
        });
        resizeTimeout = null;
    });
}

window.addEventListener('resize', resizeAllGridItems);

let nextGalleryPagePromise = null;

export function loadNextGalleryPage() {
    if (nextGalleryPagePromise) return nextGalleryPagePromise;

    nextGalleryPagePromise = (async () => {
        const startIndex = images.length;
        const { loadMore } = await import('./api.js');
        const didLoad = await loadMore();
        if (didLoad) {
            renderGallery({ appendOnly: true, startIndex });
        }
        return didLoad;
    })().finally(() => {
        nextGalleryPagePromise = null;
    });

    return nextGalleryPagePromise;
}

export function renderGallery({ appendOnly = false, startIndex = 0 } = {}) {
    if (galleryScrollObserver) galleryScrollObserver.disconnect();

    if (images.length === 0) {
        if (!allLoaded && currentCollection.id) {
            renderGallerySkeleton();
            return;
        }
        dom.contentArea.innerHTML = `
            <div class="empty-state" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-dim);">
                <div class="empty-state-icon" style="margin-bottom: 16px;">
                    <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                </div>
                <p>No images found</p>
            </div>
        `;
        return;
    }

    const masonry = dom.contentArea.querySelector('.gallery-masonry');
    if (appendOnly && masonry) {
        let newHtml = '';
        for (let index = startIndex; index < images.length; index++) {
            const img = images[index];
            const src = thumbUrl(img);
            const isActive = index === activeIndex ? ' active' : '';
            const hasError = img.error ? '<div class="card-error"><svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>' : '';
            const fmt = img.format || '';
            const dims = img.size ? `${img.size[0]}x${img.size[1]}` : '';
            const size = img.size && img.size[0] > 0 && img.size[1] > 0 ? img.size : [4, 3];
            const ratioStyle = ` style="aspect-ratio: ${size[0]} / ${size[1]}; position: relative; width: 100%; background: var(--surface2);"`;
            const imgStyle = ` style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain;"`;
            const fileName = img.file_name || img.file || '';

            newHtml += `
                <div class="gallery-card${isActive}" data-index="${index}">
                    <div class="img-wrapper"${ratioStyle}>
                        <img src="${src}" alt="${escapeHtml(fileName)}" loading="lazy" draggable="false"${imgStyle} onload="if(this.naturalWidth){this.parentElement.style.aspectRatio=this.naturalWidth+'/'+this.naturalHeight;window.dispatchEvent(new Event('resize'));}">
                    </div>
                    <button class="image-delete-btn gallery-delete" data-index="${index}" title="Delete image" aria-label="Delete ${escapeHtml(fileName)}">
                        <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
                    </button>
                    ${hasError}
                    <div class="card-info">
                        <div class="card-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                        <div class="card-meta">${fmt} ${dims}</div>
                    </div>
                </div>
            `;
        }

        const tempDiv = document.createElement('div');
        tempDiv.innerHTML = newHtml;
        const newCards = Array.from(tempDiv.children);
        newCards.forEach(card => {
            masonry.appendChild(card);
            
            card.addEventListener('click', () => {
                const index = Number.parseInt(card.dataset.index, 10);
                import('./lightbox.js').then(module => module.openLightbox(index, images));
            });

            const deleteBtn = card.querySelector('.gallery-delete');
            if (deleteBtn) {
                deleteBtn.addEventListener('click', event => {
                    event.stopPropagation();
                    const index = Number.parseInt(deleteBtn.dataset.index, 10);
                    const imageId = images[index]?.id;
                    if (imageId) import('./api.js').then(module => module.deleteImageById(imageId));
                });
            }
        });

        resizeAllGridItems();
        import('./components/search-bar.js').then(module => module.applySearchFilter());
    } else {
        const folderName = dom.folderNameEl ? dom.folderNameEl.textContent : '';
        const toolbarHtml = `
            <div class="content-toolbar">
                <div class="toolbar-title">${escapeHtml(folderName || 'Gallery')}</div>
                <div class="toolbar-actions">
                    <div class="sort-container">
                        <button class="btn btn-sm btn-secondary sort-btn" id="sort-btn">
                            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" style="margin-right: 6px;"><path d="M3 9l4-4 4 4M7 5v14M21 15l-4 4-4-4M17 19V5"/></svg>
                            <span>Sort</span>
                            <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" style="margin-left: 4px;"><polyline points="6 9 12 15 18 9"></polyline></svg>
                        </button>
                        <div class="dropdown-menu" id="sort-dropdown-menu" style="display: none;"></div>
                    </div>
                </div>
            </div>
        `;

        let html = toolbarHtml + '<div class="gallery-masonry">';
        images.forEach((img, index) => {
            const src = thumbUrl(img);
            const isActive = index === activeIndex ? ' active' : '';
            const hasError = img.error ? '<div class="card-error"><svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>' : '';
            const fmt = img.format || '';
            const dims = img.size ? `${img.size[0]}x${img.size[1]}` : '';
            const size = img.size && img.size[0] > 0 && img.size[1] > 0 ? img.size : [4, 3];
            const ratioStyle = ` style="aspect-ratio: ${size[0]} / ${size[1]}; position: relative; width: 100%; background: var(--surface2);"`;
            const imgStyle = ` style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain;"`;
            const fileName = img.file_name || img.file || '';

            html += `
                <div class="gallery-card${isActive}" data-index="${index}">
                    <div class="img-wrapper"${ratioStyle}>
                        <img src="${src}" alt="${escapeHtml(fileName)}" loading="lazy" draggable="false"${imgStyle} onload="if(this.naturalWidth){this.parentElement.style.aspectRatio=this.naturalWidth+'/'+this.naturalHeight;window.dispatchEvent(new Event('resize'));}">
                    </div>
                    <button class="image-delete-btn gallery-delete" data-index="${index}" title="Delete image" aria-label="Delete ${escapeHtml(fileName)}">
                        <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
                    </button>
                    ${hasError}
                    <div class="card-info">
                        <div class="card-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                        <div class="card-meta">${fmt} ${dims}</div>
                    </div>
                </div>
            `;
        });
        html += '</div>';
        dom.contentArea.innerHTML = html;
        import('./components/search-bar.js').then(module => module.applySearchFilter());

        dom.contentArea.querySelectorAll('.gallery-card').forEach(card => {
            card.addEventListener('click', () => {
                const index = Number.parseInt(card.dataset.index, 10);
                import('./lightbox.js').then(module => module.openLightbox(index, images));
            });
        });

        dom.contentArea.querySelectorAll('.gallery-delete').forEach(button => {
            button.addEventListener('click', event => {
                event.stopPropagation();
                const index = Number.parseInt(button.dataset.index, 10);
                const imageId = images[index]?.id;
                if (imageId) import('./api.js').then(module => module.deleteImageById(imageId));
            });
        });

        resizeAllGridItems();
        import('./features/sorting.js').then(module => module.bindCentralSortEvents());
    }

    if (!allLoaded && currentCollection.id) {
        let sentinel = document.querySelector('#gallery-sentinel');
        if (!sentinel) {
            sentinel = document.createElement('div');
            sentinel.id = 'gallery-sentinel';
            sentinel.style.height = '1px';
            dom.contentArea.appendChild(sentinel);
        } else {
            dom.contentArea.appendChild(sentinel);
        }

        const observer = new IntersectionObserver(entries => {
            if (!entries[0].isIntersecting) return;
            loadNextGalleryPage();
        }, { root: dom.contentArea, threshold: 0.1 });
        setGalleryScrollObserver(observer);
        observer.observe(sentinel);
    }
}

export function updateActiveGalleryCard(index) {
    const masonry = document.querySelector('.gallery-masonry');
    if (!masonry) return;
    const prevActive = masonry.querySelector('.gallery-card.active');
    if (prevActive) {
        prevActive.classList.remove('active');
    }
    const newActive = masonry.querySelector(`.gallery-card[data-index="${index}"]`);
    if (newActive) {
        newActive.classList.add('active');
    }
}

export function renderGallerySkeleton() {
    let html = '<div class="gallery-masonry">';
    for (let i = 0; i < 12; i++) html += skeletonGalleryCard();
    html += '</div>';
    dom.contentArea.innerHTML = html;
    resizeAllGridItems();
}
