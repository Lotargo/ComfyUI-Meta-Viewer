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
            <div class="name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        </div>
        <button class="image-delete-btn sidebar-delete" data-index="${index}" title="Delete image" aria-label="Delete ${escapeHtml(fileName)}">
            <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round">
                <line x1="18" y1="6" x2="6" y2="18"></line>
                <line x1="6" y1="6" x2="18" y2="18"></line>
            </svg>
        </button>
    `;

    return div;
}
