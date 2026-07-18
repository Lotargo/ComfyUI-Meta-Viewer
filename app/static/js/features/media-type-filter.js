import {
    dom,
    currentCollection,
    mediaTypeFilter,
    saveState,
    setMediaTypeFilter,
    showToast,
} from '../state.js';
import {
    invalidateApiCache,
    loadCollectionImages,
    loadSidebarImages,
} from '../api.js';

function filterLabel() {
    if (mediaTypeFilter.images && mediaTypeFilter.videos) return 'All';
    return mediaTypeFilter.images ? 'Images' : 'Videos';
}

function closeMediaTypeFilter({ restoreFocus = false } = {}) {
    if (!dom.mediaTypeFilterMenu || !dom.mediaTypeFilterBtn) return;
    dom.mediaTypeFilterMenu.style.display = 'none';
    dom.mediaTypeFilterBtn.setAttribute('aria-expanded', 'false');
    if (restoreFocus) dom.mediaTypeFilterBtn.focus();
}

function syncMediaTypeFilter() {
    if (dom.mediaFilterImages) dom.mediaFilterImages.checked = mediaTypeFilter.images;
    if (dom.mediaFilterVideos) dom.mediaFilterVideos.checked = mediaTypeFilter.videos;
    if (dom.mediaTypeFilterLabel) dom.mediaTypeFilterLabel.textContent = filterLabel();
    if (dom.mediaTypeFilterBtn) {
        const filtered = !(mediaTypeFilter.images && mediaTypeFilter.videos);
        dom.mediaTypeFilterBtn.classList.toggle('active', filtered);
        dom.mediaTypeFilterBtn.title = `Media: ${filterLabel()}`;
        dom.mediaTypeFilterBtn.setAttribute('aria-label', dom.mediaTypeFilterBtn.title);
    }
}

async function applyMediaTypeFilter(nextFilter) {
    if (!nextFilter.images && !nextFilter.videos) {
        showToast('Keep at least one media type visible');
        syncMediaTypeFilter();
        return;
    }

    setMediaTypeFilter(nextFilter);
    saveState();
    syncMediaTypeFilter();
    invalidateApiCache();
    dom.mediaTypeFilterBtn.disabled = true;
    try {
        const loads = [loadSidebarImages({ force: true, render: false })];
        if (currentCollection.id) {
            loads.push(loadCollectionImages(
                { ...currentCollection },
                { force: true, render: false },
            ));
        }
        await Promise.all(loads);
        const [{ renderSidebar }, { renderCurrentContent }] = await Promise.all([
            import('./sidebar.js'),
            import('../events.js'),
        ]);
        renderSidebar();
        await renderCurrentContent();
        if (dom.lightbox?.classList.contains('open')) {
            const { syncLightboxAfterCollectionChange } = await import('../lightbox.js');
            syncLightboxAfterCollectionChange();
        }
    } finally {
        dom.mediaTypeFilterBtn.disabled = false;
    }
}

export function initMediaTypeFilter() {
    if (!dom.mediaTypeFilterBtn || !dom.mediaTypeFilterMenu) return;
    syncMediaTypeFilter();

    dom.mediaTypeFilterBtn.addEventListener('click', event => {
        event.stopPropagation();
        const willOpen = dom.mediaTypeFilterMenu.style.display === 'none';
        document.querySelectorAll(
            '#sort-dropdown-menu, #sidebar-sort-dropdown-menu, #folders-sort-dropdown-menu, #viewer-albums-sort-dropdown-menu, #viewer-rating-filter-menu',
        ).forEach(menu => { menu.style.display = 'none'; });
        dom.mediaTypeFilterMenu.style.display = willOpen ? 'flex' : 'none';
        dom.mediaTypeFilterBtn.setAttribute('aria-expanded', String(willOpen));
    });

    dom.mediaTypeFilterMenu.addEventListener('click', event => event.stopPropagation());
    dom.mediaTypeFilterMenu.addEventListener('change', () => {
        applyMediaTypeFilter({
            images: Boolean(dom.mediaFilterImages?.checked),
            videos: Boolean(dom.mediaFilterVideos?.checked),
        }).catch(error => showToast(error.message));
    });

    document.addEventListener('click', () => closeMediaTypeFilter());
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && dom.mediaTypeFilterMenu.style.display !== 'none') {
            closeMediaTypeFilter({ restoreFocus: true });
        }
    });
}
