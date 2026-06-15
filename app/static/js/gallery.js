import { images, activeIndex, galleryActive, currentFolderId, allLoaded, scrollObserver, totalImages, dom, setScrollObserver, saveState } from './state.js';
import { escapeHtml, thumbUrl } from './utils.js';

export function renderGallery() {
    dom.imageCount.textContent = totalImages ? `(${images.length}/${totalImages})` : '';
    let html = '<div class="gallery-grid anim-fade-in">';
    images.forEach((img, i) => {
        const src = thumbUrl(img);
        const isActive = i === activeIndex ? ' active' : '';
        const hasError = img.error ? '<div class="card-error">&#9888;</div>' : '';
        const fmt = img.format || '';
        const dims = img.size ? `${img.size[0]}x${img.size[1]}` : '';
        const fileName = img.file_name || img.file || '';
        html += `<div class="gallery-card${isActive}" data-index="${i}">
            <img src="${src}" alt="${escapeHtml(fileName)}" loading="lazy">
            ${hasError}
            <div class="card-info">
                <div class="card-name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
                <div class="card-meta">${fmt} ${dims}</div>
            </div>
        </div>`;
    });
    html += '</div>';
    dom.contentArea.innerHTML = html;

    dom.contentArea.querySelectorAll('.gallery-card').forEach(card => {
        card.addEventListener('click', () => {
            const idx = parseInt(card.dataset.index);
            import('./lightbox.js').then(m => m.openLightbox(idx));
        });
    });

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
        }, {root: dom.contentArea, threshold: 0.1}));
        scrollObserver.observe(sentinel);
    }
}
