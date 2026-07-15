/**
 * Gallery view with masonry layout
 */

import { images, activeIndex, galleryActive, currentFolderId, allLoaded, scrollObserver, totalImages, dom, setScrollObserver, saveState } from './state.js';
import { escapeHtml, thumbUrl, formatImageCountLabel } from './utils.js';
import { skeletonGalleryCard } from './components/skeleton.js';

export function renderGallery() {
    dom.imageCount.textContent = formatImageCountLabel(images.length, totalImages);

    // Show skeleton while loading
    if (images.length === 0) {
        let skeletonHtml = '<div class="gallery-masonry">';
        for (let i = 0; i < 12; i++) {
            skeletonHtml += skeletonGalleryCard();
        }
        skeletonHtml += '</div>';
        dom.contentArea.innerHTML = skeletonHtml;
        return;
    }

    let html = '<div class="gallery-masonry">';
    images.forEach((img, i) => {
        const src = thumbUrl(img);
        const isActive = i === activeIndex ? ' active' : '';
        const hasError = img.error ? '<div class="card-error"><svg viewBox="0 0 24 24" width="24" height="24" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div>' : '';
        const fmt = img.format || '';
        const dims = img.size ? `${img.size[0]}x${img.size[1]}` : '';
        const fileName = img.file_name || img.file || '';

        html += `
            <div class="gallery-card${isActive}" data-index="${i}">
                <img src="${src}" alt="${escapeHtml(fileName)}" loading="lazy">
                <button class="image-delete-btn gallery-delete" data-index="${i}" title="Delete image" aria-label="Delete ${escapeHtml(fileName)}">
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

    // Add click handlers
    dom.contentArea.querySelectorAll('.gallery-card').forEach(card => {
        card.addEventListener('click', () => {
            const idx = parseInt(card.dataset.index);
            import('./lightbox.js').then(m => m.openLightbox(idx, images));
        });
    });

    dom.contentArea.querySelectorAll('.gallery-delete').forEach(button => {
        button.addEventListener('click', e => {
            e.stopPropagation();
            const idx = parseInt(button.dataset.index);
            import('./api.js').then(m => m.deleteImageAt(idx));
        });
    });

    // Infinite scroll
    if (!allLoaded && currentFolderId) {
        const sentinel = document.createElement('div');
        sentinel.id = 'gallery-sentinel';
        sentinel.style.height = '1px';
        dom.contentArea.appendChild(sentinel);

        if (scrollObserver) scrollObserver.disconnect();

        setScrollObserver(new IntersectionObserver(entries => {
            if (entries[0].isIntersecting) {
                import('./api.js').then(m => m.loadMore());
            }
        }, { root: dom.contentArea, threshold: 0.1 }));

        scrollObserver.observe(sentinel);
    }
}

export function renderGallerySkeleton() {
    let html = '<div class="gallery-masonry">';
    for (let i = 0; i < 12; i++) {
        html += skeletonGalleryCard();
    }
    html += '</div>';
    dom.contentArea.innerHTML = html;
}
