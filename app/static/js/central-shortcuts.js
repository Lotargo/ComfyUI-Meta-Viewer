import { images, activeIndex, detailCache, dom } from './state.js';
import { copyText } from './utils.js';

export function initCentralCollectionShortcuts() {
    document.addEventListener('keydown', event => {
        if (dom.lightbox?.classList.contains('open')) return;
        if (event.target instanceof HTMLInputElement || event.target instanceof HTMLTextAreaElement) return;

        if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
            event.preventDefault();
            event.stopImmediatePropagation();
            const delta = event.key === 'ArrowLeft' ? -1 : 1;
            const nextIndex = activeIndex + delta;
            if (nextIndex >= 0 && nextIndex < images.length) {
                import('./features/sidebar.js').then(module => module.selectImage(nextIndex));
            }
            return;
        }

        if (event.key.toLowerCase() === 'c' && !event.ctrlKey && !event.metaKey && !event.altKey) {
            const img = images[activeIndex];
            if (!img) return;
            event.stopImmediatePropagation();
            const detail = (img.id && detailCache[img.id]) || img;
            copyText(JSON.stringify(detail, null, 2));
        }
    }, true);
}
