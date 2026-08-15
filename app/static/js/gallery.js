/**
 * Central mixed-media gallery for the currently selected folder or album.
 */

import {
    images,
    activeIndex,
    currentCollection,
    allLoaded,
    galleryScrollObserver,
    dom,
    showToast,
    setGalleryScrollObserver,
    isBrowsableCollection,
    sortKey,
    setSortKey,
    saveState,
} from './state.js';
import { escapeHtml, imageRenderSignature, originalUrl, thumbUrl } from './utils.js';
import { skeletonGalleryCard } from './components/skeleton.js';
import { showImageContextMenu } from './components/image-context-menu.js';
import { traceSpan } from './tracing.js';
import { applySearchFilter } from './components/search-bar.js';
import { bindCentralSortEvents } from './features/sorting.js';

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error) {
        throw new Error(data.error || `${response.status} ${response.statusText}`);
    }
    return data;
}

const GALLERY_ORDER_KEY = 'cmv_gallery_order';

function galleryOrderStorageKey(collection) {
    return `${collection.type || 'media'}:${collection.id ?? 'all'}`;
}

function loadAllGalleryOrders() {
    try {
        return JSON.parse(localStorage.getItem(GALLERY_ORDER_KEY)) || {};
    } catch (_e) {
        return {};
    }
}

function saveAllGalleryOrders(orders) {
    try {
        localStorage.setItem(GALLERY_ORDER_KEY, JSON.stringify(orders));
    } catch (_e) {
        // Storage quota or persistence unavailable — order is kept in-memory only.
    }
}

function saveGalleryOrder(collection, imageIds) {
    const orders = loadAllGalleryOrders();
    orders[galleryOrderStorageKey(collection)] = imageIds;
    saveAllGalleryOrders(orders);
}

function loadGalleryOrder(collection) {
    const orders = loadAllGalleryOrders();
    return orders[galleryOrderStorageKey(collection)] || null;
}

let hasCustomOrder = false;

export function applySavedCustomOrder() {
    if (sortKey !== 'custom') {
        hasCustomOrder = false;
        return;
    }
    const span = traceSpan("gallery.applySavedCustomOrder", {
        collection: currentCollection.type,
        collection_id: currentCollection.id ?? "all",
        image_count: images.length,
    });
    try {
        const saved = loadGalleryOrder(currentCollection);
        if (!saved || saved.length < 2) {
            hasCustomOrder = false;
            span.setAttribute("custom_order.active", false);
            span.setAttribute("reason", "no_saved_order");
            return;
        }
        if (images.length < 2) {
            hasCustomOrder = false;
            span.setAttribute("custom_order.active", false);
            span.setAttribute("reason", "too_few_images");
            return;
        }

        hasCustomOrder = true;
        const imgMap = new Map();
        for (const img of images) {
            imgMap.set(Number(img.id), img);
        }
        const savedSet = new Set(saved.map(Number));
        const newItemsAtTop = [];
        const newItemsAtBottom = [];

        const firstSavedIdx = images.findIndex(img => savedSet.has(Number(img.id)));
        images.forEach((img, idx) => {
            if (!savedSet.has(Number(img.id))) {
                if (firstSavedIdx === -1 || idx < firstSavedIdx) {
                    newItemsAtTop.push(img);
                } else {
                    newItemsAtBottom.push(img);
                }
            }
        });

        const reordered = [];
        for (const id of saved) {
            const numId = Number(id);
            if (imgMap.has(numId)) {
                reordered.push(imgMap.get(numId));
                imgMap.delete(numId);
            }
        }
        images.length = 0;
        images.push(...newItemsAtTop, ...reordered, ...newItemsAtBottom);
        span.setAttribute("custom_order.active", true);
        span.setAttribute("saved_order_length", saved.length);
        span.setAttribute("reordered_count", images.length);
    } finally {
        span.end();
    }
}

export function mergeCustomOrderOnPageLoad(newImageIds) {
    const span = traceSpan("gallery.mergeCustomOrderOnPageLoad", {
        new_count: newImageIds.length,
        has_custom_order: hasCustomOrder,
    });
    try {
        if (!hasCustomOrder) {
            span.setAttribute("reason", "no_custom_order");
            return;
        }
        const saved = loadGalleryOrder(currentCollection);
        if (!saved) {
            span.setAttribute("reason", "no_saved_order");
            return;
        }
        const merged = [...saved.map(Number)];
        for (const id of newImageIds) {
            const numId = Number(id);
            if (!merged.includes(numId)) merged.push(numId);
        }
        saveGalleryOrder(currentCollection, merged);
        span.setAttribute("merged_length", merged.length);
    } finally {
        span.end();
    }
}

export function isCustomOrderActive() {
    return hasCustomOrder;
}

let resizeTimeout = null;
export function resizeAllGridItems(targetCards = null) {
    if (resizeTimeout) cancelAnimationFrame(resizeTimeout);
    resizeTimeout = requestAnimationFrame(() => {
        const grid = document.querySelector('.gallery-masonry');
        if (!grid) return;
        const items = targetCards || grid.querySelectorAll('.gallery-card');
        const len = items.length;
        if (!len) return;

        const rowHeight = 10;
        const rowGap = 14;
        const spans = new Uint16Array(len);

        // Phase 1: Pure Read phase (no DOM writes)
        for (let i = 0; i < len; i++) {
            const wrapper = items[i].firstElementChild;
            if (wrapper) {
                spans[i] = Math.ceil((wrapper.offsetHeight + 2 + rowGap) / (rowHeight + rowGap));
            }
        }

        // Phase 2: Pure Write phase (no DOM reads)
        for (let i = 0; i < len; i++) {
            if (spans[i] > 0) {
                items[i].style.gridRowEnd = `span ${spans[i]}`;
            }
        }
        resizeTimeout = null;
    });
}

window.addEventListener('resize', () => resizeAllGridItems());

let nextGalleryPagePromise = null;

function galleryCardHtml(img, index) {
    const src = thumbUrl(img);
    const isActive = index === activeIndex ? ' active' : '';
    const hasError = img.error ? '<div class="card-error"><svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>' : '';
    const fmt = img.format || '';
    const dims = img.size ? `${img.size[0]}x${img.size[1]}` : '';
    const size = img.size && img.size[0] > 0 && img.size[1] > 0 ? img.size : [4, 3];
    const ratioStyle = ` style="aspect-ratio: ${size[0]} / ${size[1]}; position: relative; width: 100%; background: var(--surface2);"`;
    const imgStyle = ' style="position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: contain;"';
    const fileName = img.file_name || img.file || '';
    const isVideo = img.media_type === 'video';
    const removeLabel = img.has_local_file === false ? 'Delete uploaded asset' : 'Remove from index';
    const mediaBadge = isVideo
        ? `<span class="media-type-badge gallery-media-type-badge" aria-label="Video">
            <svg viewBox="0 0 16 16" width="9" height="9" fill="currentColor" aria-hidden="true"><path d="M5 3.5v9l7-4.5z"></path></svg>Video
        </span>`
        : '';
    const videoPlaceholder = isVideo
        ? '<span class="gallery-video-placeholder" aria-hidden="true"></span>'
        : '';
    const videoPlayOverlay = isVideo
        ? `<span class="gallery-video-play" aria-hidden="true">
            <svg viewBox="0 0 24 24" width="26" height="26" fill="currentColor"><path d="m9 7 8 5-8 5z"></path></svg>
        </span>`
        : '';

    return `
        <div class="gallery-card${isActive}" data-index="${index}" data-image-id="${img.id ?? ''}">
            <div class="img-wrapper"${ratioStyle}>
                ${videoPlaceholder}
                <img src="${src}" alt="${escapeHtml(fileName)}" loading="lazy" decoding="async" draggable="false"${imgStyle} onload="if(this.naturalWidth && !this.parentElement.style.aspectRatio){this.parentElement.style.aspectRatio=this.naturalWidth+'/'+this.naturalHeight;}" onerror="if(this.dataset.mediaType==='video'){this.hidden=true;}" data-media-type="${isVideo ? 'video' : 'image'}">
                ${videoPlayOverlay}
                ${mediaBadge}
            </div>
            <button class="image-delete-btn gallery-delete" data-index="${index}" title="${removeLabel}" aria-label="${removeLabel}: ${escapeHtml(fileName)}">
                <svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
            </button>
            ${hasError}
            <div class="card-info">
                <div class="card-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                <div class="card-meta">${isVideo ? 'Video · ' : ''}${fmt} ${dims}</div>
            </div>
        </div>
    `;
}

function createGalleryCard(img, index) {
    const template = document.createElement('template');
    template.innerHTML = galleryCardHtml(img, index).trim();
    const card = template.content.firstElementChild;
    card.dataset.renderSignature = imageRenderSignature(img);
    bindGalleryCard(card);
    return card;
}

let suppressNextClick = false;

function bindGalleryCard(card) {
    card.addEventListener('click', event => {
        if (suppressNextClick) {
            suppressNextClick = false;
            event.stopPropagation();
            return;
        }
        const index = Number.parseInt(card.dataset.index, 10);
        import('./lightbox.js').then(module => module.openLightbox(index, images));
    });

    card.querySelector('.gallery-delete')?.addEventListener('click', event => {
        event.stopPropagation();
        const index = Number.parseInt(card.dataset.index, 10);
        const imageId = images[index]?.id;
        if (imageId) import('./api.js').then(module => module.removeAssetFromIndexById(imageId));
    });

    card.addEventListener('contextmenu', event => {
        const index = Number.parseInt(card.dataset.index, 10);
        const img = images[index];
        if (!img?.id) return;
        showImageContextMenu(event, {
            imageId: img.id,
            fileName: img.file_name || img.file || '',
            sourceUrl: originalUrl(img),
            mediaType: img.media_type || 'image',
            canAccessOriginal: true,
            hasLocalFile: Boolean(img.id && img.has_local_file),
            isUploadedAsset: img.has_local_file === false,
            rating: img.rating,
            onOpenInViewer: () => import('./lightbox.js')
                .then(module => module.openLightbox(index, images)),
            onDeleteFile: () => import('./api.js')
                .then(module => module.deleteAssetFileById(img.id)),
            onRemoveFromIndex: () => import('./api.js')
                .then(module => module.removeAssetFromIndexById(img.id)),
            onRenamed: renamed => import('./api.js').then(module => module.applyImageRename(renamed)),
            onRatingChanged: asset => import('./api.js').then(module => module.applyImageRating(asset)),
            extraSections: img.media_type === 'video' ? [] : [[{
                label: 'Create transparent PNG',
                icon: 'cutout',
                run: async () => {
                    const lightbox = await import('./lightbox.js');
                    await lightbox.openLightbox(index, images);
                    const cutout = await import('./features/cutout.js');
                    cutout.openCutoutPanel();
                },
            }]],
            notify: showToast,
        });
    });
}

function reconcileGalleryCards(masonry) {
    const existingById = new Map(
        [...masonry.querySelectorAll('.gallery-card[data-image-id]')]
            .map(card => [card.dataset.imageId, card]),
    );
    let cursor = masonry.firstElementChild;

    images.forEach((img, index) => {
        const imageId = String(img.id ?? '');
        const signature = imageRenderSignature(img);
        let card = existingById.get(imageId);

        if (!card || card.dataset.renderSignature !== signature) {
            const replacement = createGalleryCard(img, index);
            if (card) {
                const replacesCursor = card === cursor;
                card.replaceWith(replacement);
                if (replacesCursor) cursor = replacement;
                existingById.delete(imageId);
            }
            card = replacement;
        } else {
            existingById.delete(imageId);
            card.dataset.index = String(index);
            card.classList.toggle('active', index === activeIndex);
            const deleteButton = card.querySelector('.gallery-delete');
            if (deleteButton) deleteButton.dataset.index = String(index);
        }

        if (card !== cursor) masonry.insertBefore(card, cursor);
        cursor = card.nextElementSibling;
    });

    existingById.forEach(card => card.remove());
}

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

export function renderGallerySkeleton() {
    let html = '<div class="gallery-masonry">';
    for (let i = 0; i < 12; i++) html += skeletonGalleryCard();
    html += '</div>';
    dom.contentArea.innerHTML = html;
    resizeAllGridItems();
}

export function renderGallery({ appendOnly = false, startIndex = 0, reconcile = false } = {}) {
    const span = traceSpan("gallery.renderGallery", {
        append_only: appendOnly,
        reconcile: reconcile,
        start_index: startIndex,
        image_count: images.length,
    });

    try {
        if (galleryScrollObserver) galleryScrollObserver.disconnect();

        if (!appendOnly && startIndex === 0) {
            applySavedCustomOrder();
        }

        if (images.length === 0) {
            if (!allLoaded && isBrowsableCollection(currentCollection)) {
                renderGallerySkeleton();
                return;
            }
            dom.contentArea.innerHTML = `
                <div class="empty-state" style="height: 100%; display: flex; align-items: center; justify-content: center; flex-direction: column; color: var(--text-dim);">
                    <div class="empty-state-icon" style="margin-bottom: 16px;">
                        <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                    </div>
                    <p>No media found for the selected filters</p>
                </div>
            `;
            return;
        }

        const masonry = dom.contentArea.querySelector('.gallery-masonry');
        if (reconcile && masonry) {
            reconcileGalleryCards(masonry);
            resizeAllGridItems();
            applySearchFilter();
        } else if (appendOnly && masonry) {
            const fragment = document.createDocumentFragment();
            const newCards = [];
            for (let index = startIndex; index < images.length; index++) {
                const card = createGalleryCard(images[index], index);
                newCards.push(card);
                // eslint-disable-next-line no-restricted-syntax -- appending to a detached fragment batches the DOM update
                fragment.appendChild(card);
            }
            masonry.appendChild(fragment);

            resizeAllGridItems(newCards);
            applySearchFilter();
        } else {
            const html = `<div class="gallery-masonry">${images.map(galleryCardHtml).join('')}</div>`;
            dom.contentArea.innerHTML = html;
            applySearchFilter();

            dom.contentArea.querySelectorAll('.gallery-card').forEach(card => {
                const index = Number.parseInt(card.dataset.index, 10);
                card.dataset.renderSignature = imageRenderSignature(images[index]);
                bindGalleryCard(card);
            });

            resizeAllGridItems();
            bindCentralSortEvents();
        }

        if (!allLoaded && isBrowsableCollection(currentCollection)) {
            let sentinel = document.querySelector('#gallery-sentinel');
            if (!sentinel) {
                sentinel = document.createElement('div');
                sentinel.id = 'gallery-sentinel';
                sentinel.className = 'infinite-scroll-sentinel';
                sentinel.innerHTML = '<span class="infinite-scroll-spinner" aria-hidden="true"></span><span>Loading more media…</span>';
                dom.contentArea.appendChild(sentinel);
            } else {
                dom.contentArea.appendChild(sentinel);
            }

            const observer = new IntersectionObserver(entries => {
                if (entries.some(entry => entry.isIntersecting)) {
                    loadNextGalleryPage();
                }
            }, { root: null, rootMargin: '600px 0px', threshold: 0 });
            setGalleryScrollObserver(observer);
            observer.observe(sentinel);
        } else {
            dom.contentArea.querySelector('#gallery-sentinel')?.remove();
        }
    } finally {
        span.end();
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

let galleryPointerDrag = null;

function clearDragOverElements() {
    document.querySelectorAll('.drag-over').forEach(el => el.classList.remove('drag-over'));
}

document.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.pointerType === 'touch') return;
    if (event.target.closest('button, input, a, .image-delete-btn, .gallery-delete')) return;
    const card = event.target.closest('.gallery-card, .image-item');
    if (!card) return;

    const index = Number.parseInt(card.dataset.index, 10);
    const img = card.classList.contains('image-item')
        ? (window.sidebarImages ? window.sidebarImages[index] : null)
        : images[index];

    const imageId = Number(card.dataset.imageId || img?.id);
    if (!imageId) return;

    galleryPointerDrag = {
        pointerId: event.pointerId,
        card,
        imageId,
        fileName: img?.file_name || img?.file || 'Asset',
        thumbUrl: thumbUrl(img || { id: imageId }),
        startX: event.clientX,
        startY: event.clientY,
        dragging: false,
        preview: null,
        dropTarget: null,
        lastMoveDirection: undefined,
        lastReorderTime: 0,
    };
    try {
        card.setPointerCapture?.(event.pointerId);
    } catch {
        // Fallback if capture not available
    }
});

function getGalleryCardPositions() {
    const grid = document.querySelector('.gallery-masonry');
    if (!grid) return new Map();
    const positions = new Map();
    grid.querySelectorAll('.gallery-card[data-image-id]').forEach(card => {
        if (card.dataset.placeholder) return;
        positions.set(card.dataset.imageId, card.getBoundingClientRect());
    });
    return positions;
}

function applyGalleryFlipAnimation(oldPositions) {
    const grid = document.querySelector('.gallery-masonry');
    if (!grid) return;
    const cards = [...grid.querySelectorAll('.gallery-card[data-image-id]')];
    const moves = [];

    cards.forEach(card => {
        const oldPos = oldPositions.get(card.dataset.imageId);
        if (!oldPos) return;
        const newPos = card.getBoundingClientRect();
        const dx = oldPos.left - newPos.left;
        const dy = oldPos.top - newPos.top;
        if (Math.abs(dx) > 0.5 || Math.abs(dy) > 0.5) {
            moves.push({ card, dx, dy });
        }
    });

    if (!moves.length) return;

    moves.forEach(({ card, dx, dy }) => {
        card.style.transition = 'none';
        card.style.transform = `translate(${dx}px, ${dy}px)`;
    });

    grid.offsetHeight;

    requestAnimationFrame(() => {
        moves.forEach(({ card }) => {
            card.style.transition = '';
            card.style.transform = '';
        });
    });
}

function getGalleryCardAtCursor(clientX, clientY, placeholder) {
    const elem = document.elementFromPoint(clientX, clientY);
    if (!elem) return null;
    const card = elem.closest('.gallery-card');
    if (!card || card === placeholder || card.dataset.placeholder) return null;
    if (!card.dataset.imageId) return null;
    const grid = document.querySelector('.gallery-masonry');
    if (!grid || !grid.contains(card)) return null;
    return card;
}

function updateGalleryGridReorder(session, clientX, clientY) {
    if (!session.placeholder) return;
    const now = Date.now();
    if (session.lastReorderTime && now - session.lastReorderTime < 120) return;

    const grid = document.querySelector('.gallery-masonry');
    if (!grid) return;
    const allCards = [...grid.querySelectorAll('.gallery-card')];
    const placeholderIdx = allCards.indexOf(session.placeholder);
    if (placeholderIdx === -1) return;

    const hoverCard = getGalleryCardAtCursor(clientX, clientY, session.placeholder);
    if (!hoverCard) return;

    const hoverIdx = allCards.indexOf(hoverCard);
    if (hoverIdx === -1 || hoverIdx === placeholderIdx) return;

    const hoverRect = hoverCard.getBoundingClientRect();
    const hCenterX = hoverRect.left + hoverRect.width / 2;
    const hCenterY = hoverRect.top + hoverRect.height / 2;

    const goAfter = (clientX > hCenterX) || (Math.abs(clientX - hCenterX) < 30 && clientY > hCenterY);

    if (hoverIdx === placeholderIdx + 1 && !goAfter) return;
    if (hoverIdx === placeholderIdx - 1 && goAfter) return;

    session.lastReorderTime = now;
    const oldPositions = getGalleryCardPositions();

    if (goAfter) {
        hoverCard.parentNode.insertBefore(session.placeholder, hoverCard.nextElementSibling);
    } else {
        hoverCard.parentNode.insertBefore(session.placeholder, hoverCard);
    }

    grid.classList.add('reordering');
    resizeAllGridItems();
    applyGalleryFlipAnimation(oldPositions);
}

document.addEventListener('pointermove', event => {
    const session = galleryPointerDrag;
    if (!session || session.pointerId !== event.pointerId) return;

    const distance = Math.hypot(event.clientX - session.startX, event.clientY - session.startY);
    if (!session.dragging && distance >= 4) {
        session.dragging = true;
        session.card.classList.add('dragging');

        const rect = session.card.getBoundingClientRect();
        const ghost = session.card.cloneNode(true);
        ghost.classList.add('asset-drag-ghost');
        ghost.style.position = 'fixed';
        ghost.style.top = '0';
        ghost.style.left = '0';
        ghost.style.width = `${rect.width || 200}px`;
        ghost.style.height = `${rect.height || 260}px`;
        ghost.style.zIndex = '999999';
        ghost.style.pointerEvents = 'none';

        document.body.append(ghost);
        session.preview = ghost;
        session.cardWidth = rect.width || 200;
        session.cardHeight = rect.height || 260;
        document.body.classList.add('asset-pointer-dragging');
    }

    if (!session.dragging) return;
    event.preventDefault();

    if (session.preview) {
        const x = event.clientX - session.cardWidth / 2;
        const y = event.clientY - session.cardHeight / 2;
        session.preview.style.left = `${x}px`;
        session.preview.style.top = `${y}px`;
        session.preview.style.transform = 'rotate(2deg) scale(1.02)';
    }

    const elemUnder = document.elementFromPoint(event.clientX, event.clientY);
    const overGrid = elemUnder?.closest('.gallery-masonry');

    if (overGrid && session.card.classList.contains('gallery-card')) {
        if (!session.placeholder) {
            session.card.classList.add('dragging-original');
            const placeholder = session.card.cloneNode(false);
            placeholder.classList.add('drag-placeholder');
            placeholder.dataset.placeholder = 'true';
            session.card.parentNode.insertBefore(placeholder, session.card);
            session.placeholder = placeholder;
        }
        updateGalleryGridReorder(session, event.clientX, event.clientY);
    } else {
        const dropTarget = elemUnder?.closest('[data-album-drop-target], [data-album-id]') || null;
        if (dropTarget !== session.dropTarget) {
            clearDragOverElements();
            session.dropTarget = dropTarget;
            dropTarget?.classList.add('drag-over');
        }
    }
}, { passive: false });

document.addEventListener('pointerup', async event => {
    const session = galleryPointerDrag;
    if (!session || session.pointerId !== event.pointerId) return;

    try {
        session.card.releasePointerCapture?.(session.pointerId);
    } catch (_e) {
        // Capture may already be released by the browser.
    }

    const wasDragging = session.dragging;
    const dropTarget = session.dropTarget;
    const placeholder = session.placeholder;

    session.preview?.remove();
    session.card.classList.remove('dragging', 'dragging-original');
    document.body.classList.remove('asset-pointer-dragging');
    clearDragOverElements();

    const grid = document.querySelector('.gallery-masonry');
    grid?.classList.remove('reordering');
    grid?.querySelectorAll('.gallery-card').forEach(card => {
        card.style.transform = '';
        card.style.transition = '';
    });

    if (placeholder) {
        if (grid && !dropTarget) {
            placeholder.parentNode.insertBefore(session.card, placeholder);
            placeholder.remove();

            const cardElements = [...grid.querySelectorAll('.gallery-card[data-image-id]')];
            const newOrderIds = cardElements.map(c => Number(c.dataset.imageId)).filter(Boolean);

            cardElements.forEach((c, idx) => {
                c.dataset.index = String(idx);
            });

            const imgMap = new Map();
            for (const img of images) {
                imgMap.set(Number(img.id), img);
            }
            const reordered = [];
            for (const id of newOrderIds) {
                if (imgMap.has(id)) {
                    reordered.push(imgMap.get(id));
                    imgMap.delete(id);
                }
            }
            for (const img of imgMap.values()) {
                reordered.push(img);
            }
            images.length = 0;
            images.push(...reordered);

            saveGalleryOrder(currentCollection, newOrderIds);
            hasCustomOrder = true;
            setSortKey('custom');
            saveState();

            if (currentCollection.type === 'album' && currentCollection.id != null && newOrderIds.length > 1) {
                fetchJson(`/api/albums/${currentCollection.id}/reorder`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ asset_ids: newOrderIds }),
                }).catch(err => showToast(err.message, true));
            }

            resizeAllGridItems([session.card]);
        } else {
            placeholder.remove();
            resizeAllGridItems();
        }
    }

    galleryPointerDrag = null;

    if (wasDragging) {
        suppressNextClick = true;
        window.setTimeout(() => { suppressNextClick = false; }, 150);

        if (dropTarget) {
            const albumId = Number(dropTarget.dataset.albumDropTarget || dropTarget.dataset.albumId);
            if (albumId && session.imageId) {
                try {
                    const { addAssetsToAlbum } = await import('./api.js');
                    const res = await addAssetsToAlbum(albumId, [session.imageId]);
                    const albumName = dropTarget.querySelector('.folder-item-name')?.textContent || 'album';
                    showToast(res.affected ? `Added 1 asset to "${albumName}"` : `Asset is already in "${albumName}"`);
                } catch (err) {
                    showToast(err.message, true);
                }
            }
        }
    }
});

document.addEventListener('pointercancel', event => {
    const session = galleryPointerDrag;
    if (!session || session.pointerId !== event.pointerId) return;
    try {
        session.card.releasePointerCapture?.(session.pointerId);
    } catch (_e) {
        // Capture may already be released by the browser.
    }
    session.preview?.remove();
    session.placeholder?.remove();
    session.card.classList.remove('dragging', 'dragging-original');
    document.body.classList.remove('asset-pointer-dragging');
    clearDragOverElements();
    const grid = document.querySelector('.gallery-masonry');
    grid?.classList.remove('reordering');
    grid?.querySelectorAll('.gallery-card').forEach(card => {
        card.style.transform = '';
        card.style.transition = '';
    });
    resizeAllGridItems();
    galleryPointerDrag = null;
});

document.addEventListener('dragstart', event => {
    if (event.target.closest('.gallery-card, .image-item, .asset-card')) {
        event.preventDefault();
    }
});
