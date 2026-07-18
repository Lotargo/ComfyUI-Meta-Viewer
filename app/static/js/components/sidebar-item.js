/**
 * Sidebar image item component
 */

import { escapeHtml, imageRenderSignature, thumbUrl } from '../utils.js';

export function createSidebarItem(img, index, isActive) {
    const div = document.createElement('div');
    div.className = 'image-item' + (isActive ? ' active' : '');
    div.dataset.index = index;
    div.dataset.imageId = img.id ?? '';
    div.dataset.renderSignature = imageRenderSignature(img);

    const src = thumbUrl(img);
    const fileName = img.file_name || img.file || '';
    const isVideo = img.media_type === 'video';
    const removeLabel = img.has_local_file === false ? 'Delete uploaded asset' : 'Remove from index';
    const mediaBadge = isVideo
        ? `<span class="media-type-badge" aria-label="Video">
            <svg viewBox="0 0 16 16" width="9" height="9" fill="currentColor" aria-hidden="true"><path d="M5 3.5v9l7-4.5z"></path></svg>Video
        </span>`
        : '';

    div.innerHTML = `
        <div class="item-thumb">
            <img src="${src}" alt="" loading="lazy" draggable="false">
            ${mediaBadge}
        </div>
        <div class="item-info">
            <div class="name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        </div>
        <button class="image-delete-btn sidebar-delete" data-index="${index}" title="${removeLabel}" aria-label="${removeLabel}: ${escapeHtml(fileName)}">
            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;

    return div;
}
