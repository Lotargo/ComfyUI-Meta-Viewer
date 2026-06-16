/**
 * Sidebar image item component
 */

import { escapeHtml, thumbUrl } from '../utils.js';

export function createSidebarItem(img, index, isActive) {
    const div = document.createElement('div');
    div.className = 'image-item' + (isActive ? ' active' : '');
    div.dataset.index = index;

    const src = thumbUrl(img);
    const fileName = img.file_name || img.file || '';
    const format = img.format || '';
    const size = img.size ? `${img.size[0]}x${img.size[1]}` : '';

    div.innerHTML = `
        <div class="item-thumb">
            <img src="${src}" alt="" loading="lazy">
        </div>
        <div class="item-info">
            <div class="name">${escapeHtml(fileName)}</div>
            <div class="meta-hint">${format} ${size}</div>
        </div>
        <button class="image-delete-btn sidebar-delete" data-index="${index}" title="Delete image" aria-label="Delete ${escapeHtml(fileName)}">
            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.2" fill="none" stroke-linecap="round" stroke-linejoin="round"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"></path><path d="M10 11v6"></path><path d="M14 11v6"></path><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"></path></svg>
        </button>
    `;

    return div;
}
