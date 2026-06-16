/**
 * Sidebar image item component
 */

import { escapeHtml, thumbUrl } from '../utils.js';

export function createSidebarItem(img, index, isActive, isGrid) {
    const div = document.createElement('div');
    div.className = 'image-item' + (isActive ? ' active' : '');
    div.dataset.index = index;

    const src = thumbUrl(img);
    const fileName = img.file_name || img.file || '';

    if (isGrid) {
        div.innerHTML = `
            <img src="${src}" alt="" loading="lazy">
            <div class="name" title="${escapeHtml(fileName)}">${escapeHtml(fileName)}</div>
        `;
    } else {
        const format = img.format || '';
        const size = img.size ? `${img.size[0]}x${img.size[1]}` : '';
        div.innerHTML = `
            <img src="${src}" alt="" loading="lazy">
            <div class="item-info">
                <div class="name">${escapeHtml(fileName)}</div>
                <div class="meta-hint">${format} ${size}</div>
            </div>
        `;
    }

    return div;
}

export function createSessionHeader(session) {
    const hdr = document.createElement('div');
    hdr.className = 'session-header';
    hdr.innerHTML = `
        <span class="session-name">${escapeHtml(session.name)}</span>
        <span class="session-count">${session.images.length}</span>
        <button class="btn btn-sm btn-ghost session-remove" data-session-id="${session.id}">&times;</button>
    `;
    return hdr;
}
