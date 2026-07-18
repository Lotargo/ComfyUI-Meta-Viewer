import {
    currentCollection,
    dom,
    ratingFilter,
    saveState,
    setRatingFilter,
    showToast,
} from '../state.js';
import {
    invalidateApiCache,
    loadCollectionImages,
    loadSidebarImages,
} from '../api.js';

function filterLabel(rating) {
    if (rating === null) return 'Rating';
    if (rating === 0) return 'Unrated';
    return `${rating} ★`;
}

function closeRatingFilter({ restoreFocus = false } = {}) {
    if (!dom.ratingFilterMenu || !dom.ratingFilterBtn) return;
    dom.ratingFilterMenu.style.display = 'none';
    dom.ratingFilterBtn.setAttribute('aria-expanded', 'false');
    if (restoreFocus) dom.ratingFilterBtn.focus();
}

function syncRatingFilter() {
    if (!dom.ratingFilterBtn || !dom.ratingFilterMenu) return;
    const label = filterLabel(ratingFilter);
    if (dom.ratingFilterLabel) dom.ratingFilterLabel.textContent = label;
    dom.ratingFilterBtn.classList.toggle('active', ratingFilter !== null);
    dom.ratingFilterBtn.title = ratingFilter === null
        ? 'Filter by rating'
        : `Rating filter: ${label}`;
    dom.ratingFilterBtn.setAttribute('aria-label', dom.ratingFilterBtn.title);
    dom.ratingFilterMenu.querySelectorAll('[data-viewer-rating]').forEach(button => {
        const value = button.dataset.viewerRating;
        const optionRating = value === 'all' ? null : Number(value);
        const active = optionRating === ratingFilter;
        button.classList.toggle('active', active);
        button.setAttribute('aria-checked', String(active));
        const indicator = button.querySelector('.indicator');
        if (indicator) indicator.textContent = active ? '•' : '';
    });
}

async function reloadFilteredImages() {
    invalidateApiCache();
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
}

async function selectRatingFilter(nextRating) {
    setRatingFilter(nextRating);
    saveState();
    syncRatingFilter();
    closeRatingFilter();
    dom.ratingFilterBtn.disabled = true;
    try {
        await reloadFilteredImages();
    } finally {
        dom.ratingFilterBtn.disabled = false;
    }
}

export function initRatingFilter() {
    if (!dom.ratingFilterBtn || !dom.ratingFilterMenu) return;
    syncRatingFilter();

    dom.ratingFilterBtn.addEventListener('click', event => {
        event.stopPropagation();
        const willOpen = dom.ratingFilterMenu.style.display === 'none';
        document.querySelectorAll(
            '#sort-dropdown-menu, #sidebar-sort-dropdown-menu, #folders-sort-dropdown-menu, #viewer-albums-sort-dropdown-menu',
        ).forEach(menu => { menu.style.display = 'none'; });
        document.querySelector('#sort-btn')?.setAttribute('aria-expanded', 'false');
        if (dom.searchSettingsDropdown) dom.searchSettingsDropdown.style.display = 'none';
        dom.searchSettingsBtn?.setAttribute('aria-expanded', 'false');
        dom.ratingFilterMenu.style.display = willOpen ? 'flex' : 'none';
        dom.ratingFilterBtn.setAttribute('aria-expanded', String(willOpen));
    });

    dom.ratingFilterMenu.addEventListener('click', event => {
        event.stopPropagation();
        const option = event.target.closest('[data-viewer-rating]');
        if (!option) return;
        const value = option.dataset.viewerRating;
        const nextRating = value === 'all' ? null : Number(value);
        selectRatingFilter(nextRating).catch(error => showToast(error.message));
    });

    document.addEventListener('click', () => closeRatingFilter());
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape' && dom.ratingFilterMenu.style.display !== 'none') {
            closeRatingFilter({ restoreFocus: true });
        }
    });
}
