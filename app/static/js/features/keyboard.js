/**
 * Keyboard shortcuts handler
 */

import { images, activeIndex, detailCache, dom } from '../state.js';
import { toggleSidebar } from './sidebar.js';
import { copyText } from '../utils.js';

const shortcuts = {
    'arrowleft': { description: 'Previous image', action: prevImage },
    'arrowright': { description: 'Next image', action: nextImage },
    'escape': { description: 'Close lightbox', action: closeLightbox },
    'b': { description: 'Toggle sidebar', action: toggleSidebar },
    '/': { description: 'Focus search', action: focusSearch, preventDefault: true },
    '?': { description: 'Show shortcuts', action: toggleShortcuts },
    'c': { description: 'Copy metadata', action: copyMetadata },
    '1': { description: 'Summary tab', action: () => switchTab('summary') },
    '2': { description: 'Workflow tab', action: () => switchTab('workflow') },
    '3': { description: 'Raw tab', action: () => switchTab('raw') },
    'f': { description: 'Toggle fullscreen', action: toggleFullscreen },
    '+': { description: 'Zoom in', action: zoomIn },
    '-': { description: 'Zoom out', action: zoomOut },
    '0': { description: 'Reset zoom', action: resetZoom },
    'm': { description: 'Toggle metadata panel', action: toggleMetaPanel }
};

export function initKeyboardShortcuts() {
    document.addEventListener('keydown', handleKeydown);
}

function handleKeydown(e) {
    if (e.target.tagName === 'INPUT' || e.target.tagName === 'TEXTAREA') {
        if (e.key === 'Escape') {
            e.target.blur();
        }
        return;
    }

    if (e.ctrlKey && e.key === 'f') {
        e.preventDefault();
        focusSearch();
        return;
    }

    if (e.ctrlKey && e.key === 'c') {
        return;
    }

    const key = e.key.toLowerCase();
    const shortcut = shortcuts[key];

    if (shortcut) {
        if (shortcut.preventDefault) {
            e.preventDefault();
        }
        shortcut.action();
    }
}

function prevImage() {
    if (activeIndex > 0) {
        import('./sidebar.js').then(m => m.selectImage(activeIndex - 1));
    }
}

function nextImage() {
    if (activeIndex < images.length - 1) {
        import('./sidebar.js').then(m => m.selectImage(activeIndex + 1));
    }
}

function closeLightbox() {
    dom.lightbox.classList.remove('open');
}

function focusSearch() {
    document.getElementById('search-input')?.focus();
}

function toggleShortcuts() {
    document.getElementById('shortcuts-overlay')?.classList.toggle('open');
}

function copyMetadata() {
    const img = images[activeIndex];
    if (!img) return;

    const detail = (img.id && detailCache[img.id]) || img;
    if (detail) {
        copyText(JSON.stringify(detail, null, 2));
    }
}

function switchTab(tabName) {
    const tab = document.querySelector(`.content-tab[data-tab="${tabName}"]`);
    if (tab) {
        tab.click();
    }
}

function toggleFullscreen() {
    if (!document.fullscreenElement) {
        document.documentElement.requestFullscreen();
    } else {
        document.exitFullscreen();
    }
}

function zoomIn() {
    import('../lightbox.js').then(m => m.zoomIn());
}

function zoomOut() {
    import('../lightbox.js').then(m => m.zoomOut());
}

function resetZoom() {
    import('../lightbox.js').then(m => m.resetZoom());
}

function toggleMetaPanel() {
    import('../lightbox.js').then(m => m.toggleMetaPanel());
}

export function getShortcutsList() {
    return Object.entries(shortcuts).map(([key, { description }]) => ({
        key,
        description
    }));
}
