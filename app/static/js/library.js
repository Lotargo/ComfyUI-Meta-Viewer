const dom = {
    systemCollections: document.getElementById('system-collections'),
    albumList: document.getElementById('album-list'),
    createAlbum: document.getElementById('create-album'),
    collectionTitle: document.getElementById('collection-title'),
    collectionSummary: document.getElementById('collection-summary'),
    search: document.getElementById('library-search'),
    sort: document.getElementById('library-sort'),
    toolbar: document.getElementById('selection-toolbar'),
    selectionCount: document.getElementById('selection-count'),
    selectVisible: document.getElementById('select-visible'),
    bulkAlbum: document.getElementById('bulk-album'),
    bulkRating: document.getElementById('bulk-rating'),
    removeFromAlbum: document.getElementById('remove-from-album'),
    setAlbumCover: document.getElementById('set-album-cover'),
    editAsset: document.getElementById('edit-asset'),
    removeFromIndex: document.getElementById('remove-from-index'),
    clearSelection: document.getElementById('clear-selection'),
    feedback: document.getElementById('library-feedback'),
    grid: document.getElementById('asset-grid'),
    loadMore: document.getElementById('load-more'),
    editor: document.getElementById('asset-editor'),
    editorForm: document.getElementById('asset-editor-form'),
    editorTitle: document.getElementById('editor-title'),
    editorRating: document.getElementById('editor-rating'),
    editorTags: document.getElementById('editor-tags'),
    editorNote: document.getElementById('editor-note'),
    editorFilename: document.getElementById('editor-filename'),
    ratingFilterButtons: document.getElementById('rating-filter-buttons'),
    albumDialog: document.getElementById('album-dialog'),
    albumDialogForm: document.getElementById('album-dialog-form'),
    albumDialogTitle: document.getElementById('album-dialog-title'),
    albumDialogName: document.getElementById('album-dialog-name'),
    toast: document.getElementById('library-toast'),
};

const state = {
    systemCollections: [],
    albums: [],
    summary: {},
    collection: 'all',
    albumId: null,
    collectionName: 'All assets',
    assets: [],
    total: 0,
    page: 1,
    perPage: 80,
    selected: new Set(),
    lastSelectedIndex: null,
    loading: false,
    ratingFilter: null,
};

const collectionIcons = {
    all: '▦',
    favorites: '♥',
    albums: '▤',
    without_metadata: '◇',
    recently_added: '◷',
    unavailable: '!',
    images: '▧',
    videos: '▶',
    not_rated: '☆',
};

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error) {
        throw new Error(data.error || `${response.status} ${response.statusText}`);
    }
    return data;
}

function showToast(message, isError = false) {
    dom.toast.textContent = message;
    dom.toast.classList.toggle('error', isError);
    dom.toast.classList.add('visible');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => dom.toast.classList.remove('visible'), 2800);
}

function collectionCount(id) {
    const counts = {
        all: state.summary.assets,
        favorites: state.summary.favorites,
        unavailable: state.summary.unavailable,
        not_rated: state.summary.not_rated,
    };
    return counts[id];
}

function renderCollections() {
    dom.systemCollections.innerHTML = state.systemCollections.map(collection => {
        const count = collectionCount(collection.id);
        return `
            <button class="collection-button ${state.collection === collection.id ? 'active' : ''}"
                    type="button" data-collection="${escapeHtml(collection.id)}">
                <span class="collection-icon">${collectionIcons[collection.id] || '•'}</span>
                <span class="collection-name">${escapeHtml(collection.name)}</span>
                ${Number.isInteger(count) ? `<span class="collection-count">${count}</span>` : ''}
            </button>`;
    }).join('');

    dom.albumList.innerHTML = state.albums.length ? state.albums.map(album => `
        <div class="collection-button ${state.collection === 'album' && state.albumId === album.id ? 'active' : ''}"
             role="button" tabindex="0" data-album-id="${album.id}" data-album-name="${escapeHtml(album.name)}">
            <span class="collection-icon collection-cover" ${album.display_cover_image_id ? `style="background-image:url('/api/thumbnail/${album.display_cover_image_id}')"` : ''}>${album.display_cover_image_id ? '' : '▤'}</span>
            <span class="collection-name">${escapeHtml(album.name)}</span>
            <span class="collection-count">${album.asset_count}</span>
            <span class="album-actions">
                <button type="button" data-album-action="rename" title="Rename album" aria-label="Rename ${escapeHtml(album.name)}">✎</button>
                <button type="button" data-album-action="delete" title="Delete album" aria-label="Delete ${escapeHtml(album.name)}">×</button>
            </span>
        </div>`).join('') : '<p class="library-subtitle" style="padding: 8px 10px">No albums yet.</p>';

    dom.bulkAlbum.innerHTML = '<option value="">Add to album…</option>' + state.albums.map(album => (
        `<option value="${album.id}">${escapeHtml(album.name)}</option>`
    )).join('');
}

function formatBytes(value) {
    const bytes = Number(value) || 0;
    if (bytes < 1024) return `${bytes} B`;
    if (bytes < 1024 ** 2) return `${(bytes / 1024).toFixed(1)} KB`;
    return `${(bytes / 1024 ** 2).toFixed(1)} MB`;
}

function renderAssets() {
    if (state.collection === 'albums') {
        if (!state.albums.length) {
            dom.grid.innerHTML = '';
            dom.feedback.hidden = false;
            dom.feedback.textContent = 'No albums yet. Click "+" in the sidebar to create one.';
        } else {
            dom.feedback.hidden = true;
            dom.grid.innerHTML = state.albums.map(album => {
                const coverUrl = album.display_cover_image_id ? `/api/thumbnail/${album.display_cover_image_id}` : '';
                return `
                    <article class="album-card" data-grid-album-id="${album.id}" tabindex="0" aria-label="${escapeHtml(album.name)}">
                        <div class="album-thumb-wrap">
                            ${coverUrl ? `<img class="album-thumb" src="${escapeHtml(coverUrl)}" alt="" loading="lazy">` : `<div class="album-thumb-placeholder">▤</div>`}
                            <div class="album-actions-overlay">
                                <button type="button" class="btn btn-sm btn-ghost rename-album-btn" data-album-action="rename" title="Rename album" aria-label="Rename ${escapeHtml(album.name)}">✎ Rename</button>
                                <button type="button" class="btn btn-sm btn-danger delete-album-btn" data-album-action="delete" title="Delete album" aria-label="Delete ${escapeHtml(album.name)}">× Delete</button>
                            </div>
                        </div>
                        <div class="album-info">
                            <div class="album-name" title="${escapeHtml(album.name)}">${escapeHtml(album.name)}</div>
                            <div class="album-meta">${album.asset_count} asset${album.asset_count === 1 ? '' : 's'}</div>
                        </div>
                    </article>`;
            }).join('');
        }
        dom.loadMore.hidden = true;
        dom.collectionTitle.textContent = state.collectionName;
        dom.collectionSummary.textContent = `${state.albums.length} album${state.albums.length === 1 ? '' : 's'}`;
        updateSelectionToolbar();
        return;
    }

    if (!state.assets.length) {
        dom.grid.innerHTML = '';
        dom.feedback.hidden = false;
        dom.feedback.textContent = state.loading ? 'Loading library…' : 'No assets match this collection.';
    } else {
        dom.feedback.hidden = true;
        dom.grid.innerHTML = state.assets.map(asset => {
            const selected = state.selected.has(asset.id);
            const rating = '★'.repeat(asset.rating || 0);
            const tags = (asset.tags || []).slice(0, 3).map(tag => `<span class="asset-tag">${escapeHtml(tag)}</span>`).join('');
            const dimensions = asset.width && asset.height ? `${asset.width}×${asset.height}` : (asset.format || 'asset');
            return `
                <article class="asset-card ${selected ? 'selected' : ''} ${asset.available ? '' : 'unavailable'}"
                         data-asset-id="${asset.id}" tabindex="0" aria-label="${escapeHtml(asset.file_name)}">
                    <div class="asset-thumb-wrap">
                        <img class="asset-thumb" src="${escapeHtml(asset.thumbnail_url)}" alt="" loading="lazy">
                        <input class="asset-select" type="checkbox" ${selected ? 'checked' : ''}
                               aria-label="Select ${escapeHtml(asset.file_name)}">
                        <button class="asset-favorite ${asset.favorite ? 'active' : ''}" type="button"
                                title="${asset.favorite ? 'Remove from favorites' : 'Add to favorites'}"
                                aria-label="${asset.favorite ? 'Remove from favorites' : 'Add to favorites'}">♥</button>
                        ${asset.available ? '' : '<span class="asset-availability">Unavailable source</span>'}
                    </div>
                    <div class="asset-info">
                        <div class="asset-name" title="${escapeHtml(asset.file_name)}">${escapeHtml(asset.file_name)}</div>
                        <div class="asset-source" title="${escapeHtml(asset.source_path)}">${escapeHtml(asset.source_name)}</div>
                        ${tags ? `<div class="asset-tags">${tags}</div>` : ''}
                        <div class="asset-card-footer">
                            <span class="asset-rating">${rating || 'Not rated'}</span>
                            <span class="asset-meta">${escapeHtml(dimensions)} · ${formatBytes(asset.file_size)}</span>
                        </div>
                    </div>
                </article>`;
        }).join('');
    }
    dom.loadMore.hidden = state.assets.length >= state.total || state.loading;
    dom.collectionTitle.textContent = state.collectionName;
    dom.collectionSummary.textContent = `${state.total} asset${state.total === 1 ? '' : 's'} · physical files stay in their sources`;
    updateSelectionToolbar();
}

function updateSelectionToolbar() {
    const count = state.selected.size;
    dom.toolbar.hidden = count === 0;
    dom.selectionCount.textContent = `${count} selected`;
    dom.selectVisible.checked = state.assets.length > 0 && state.assets.every(asset => state.selected.has(asset.id));
    dom.selectVisible.indeterminate = count > 0 && !dom.selectVisible.checked;
    const isAlbum = state.collection === 'album' && state.albumId !== null;
    dom.removeFromAlbum.hidden = !isAlbum;
    dom.setAlbumCover.hidden = !isAlbum || count !== 1;
    dom.editAsset.disabled = count !== 1;
}

function buildAssetsUrl() {
    const [sortBy, sortDir] = dom.sort.value.split(':');
    const params = new URLSearchParams({
        collection: state.collection,
        page: String(state.page),
        per_page: String(state.perPage),
        sort_by: sortBy,
        sort_dir: sortDir,
    });
    if (state.albumId !== null) params.set('album_id', String(state.albumId));
    if (dom.search.value.trim()) params.set('q', dom.search.value.trim());
    if (state.ratingFilter !== null) params.set('rating', String(state.ratingFilter));
    return `/api/library/assets?${params}`;
}

async function refreshAssets() {
    if (state.loading) return;
    state.loading = true;
    try {
        const [sortBy, sortDir] = dom.sort.value.split(':');
        const params = new URLSearchParams({
            collection: state.collection,
            page: '1',
            per_page: String(state.page * state.perPage),
            sort_by: sortBy,
            sort_dir: sortDir,
        });
        if (state.albumId !== null) params.set('album_id', String(state.albumId));
        if (dom.search.value.trim()) params.set('q', dom.search.value.trim());
        if (state.ratingFilter !== null) params.set('rating', String(state.ratingFilter));

        const data = await fetchJson(`/api/library/assets?${params}`);
        state.assets = data.assets || [];
        state.total = data.total || 0;
    } catch (error) {
        showToast(error.message, true);
    } finally {
        state.loading = false;
        renderAssets();
    }
}

function makeDraggable(dialogEl, handleEl) {
    let isDragging = false;
    let startX = 0, startY = 0;
    let initialX = 0, initialY = 0;

    handleEl.addEventListener('mousedown', dragStart);
    handleEl.addEventListener('touchstart', dragStart, { passive: true });

    function dragStart(e) {
        if (e.target.closest('button, input, select, textarea')) return;
        isDragging = true;
        const clientX = e.type === 'touchstart' ? e.touches[0].clientX : e.clientX;
        const clientY = e.type === 'touchstart' ? e.touches[0].clientY : e.clientY;
        const rect = dialogEl.getBoundingClientRect();
        if (!dialogEl.style.left) {
            dialogEl.style.left = `${rect.left + rect.width / 2}px`;
            dialogEl.style.top = `${rect.top + rect.height / 2}px`;
        }
        startX = clientX;
        startY = clientY;
        initialX = parseFloat(dialogEl.style.left);
        initialY = parseFloat(dialogEl.style.top);
        document.addEventListener('mousemove', dragMove);
        document.addEventListener('mouseup', dragEnd);
        document.addEventListener('touchmove', dragMove, { passive: false });
        document.addEventListener('touchend', dragEnd);
    }

    function dragMove(e) {
        if (!isDragging) return;
        if (e.cancelable) e.preventDefault();
        const clientX = e.type === 'touchmove' ? e.touches[0].clientX : e.clientX;
        const clientY = e.type === 'touchmove' ? e.touches[0].clientY : e.clientY;
        const dx = clientX - startX;
        const dy = clientY - startY;
        dialogEl.style.left = `${initialX + dx}px`;
        dialogEl.style.top = `${initialY + dy}px`;
    }

    function dragEnd() {
        isDragging = false;
        document.removeEventListener('mousemove', dragMove);
        document.removeEventListener('mouseup', dragEnd);
        document.removeEventListener('touchmove', dragMove);
        document.removeEventListener('touchend', dragEnd);
    }
}

async function loadMetadata() {
    const data = await fetchJson('/api/library');
    state.systemCollections = data.system_collections || [];
    state.albums = data.albums || [];
    state.summary = data.summary || {};
    renderCollections();
}

async function loadAssets({ append = false } = {}) {
    if (state.loading) return;
    state.loading = true;
    renderAssets();
    try {
        const data = await fetchJson(buildAssetsUrl());
        state.assets = append ? [...state.assets, ...(data.assets || [])] : (data.assets || []);
        state.total = data.total || 0;
    } catch (error) {
        showToast(error.message, true);
        if (!append) state.assets = [];
    } finally {
        state.loading = false;
        renderAssets();
    }
}

async function selectCollection(collection, name, albumId = null) {
    state.collection = collection;
    state.collectionName = name;
    state.albumId = albumId;
    state.page = 1;
    state.assets = [];
    state.selected.clear();
    state.lastSelectedIndex = null;
    renderCollections();
    if (collection === 'albums') {
        renderAssets();
    } else {
        await loadAssets();
    }
}

function selectedIds() {
    return [...state.selected];
}

async function runBulk(action, extra = {}) {
    const ids = selectedIds();
    if (!ids.length) return;
    const result = await fetchJson('/api/library/assets/bulk', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ asset_ids: ids, action, ...extra }),
    });
    showToast(`${result.affected} asset${result.affected === 1 ? '' : 's'} updated`);
    state.selected.clear();
    await Promise.all([loadMetadata(), refreshAssets()]);
}

function toggleSelection(assetId, index, extend = false) {
    if (extend && state.lastSelectedIndex !== null) {
        const start = Math.min(index, state.lastSelectedIndex);
        const end = Math.max(index, state.lastSelectedIndex);
        state.assets.slice(start, end + 1).forEach(asset => state.selected.add(asset.id));
    } else if (state.selected.has(assetId)) {
        state.selected.delete(assetId);
    } else {
        state.selected.add(assetId);
    }
    state.lastSelectedIndex = index;
    renderAssets();
}

dom.systemCollections.addEventListener('click', event => {
    const button = event.target.closest('[data-collection]');
    if (!button) return;
    const collection = state.systemCollections.find(item => item.id === button.dataset.collection);
    if (collection) selectCollection(collection.id, collection.name);
});

dom.albumList.addEventListener('click', async event => {
    const button = event.target.closest('[data-album-id]');
    if (!button) return;
    const albumId = Number(button.dataset.albumId);
    const album = state.albums.find(item => item.id === albumId);
    const action = event.target.closest('[data-album-action]')?.dataset.albumAction;
    try {
        if (action === 'rename') {
            event.stopPropagation();
            dom.albumDialog.dataset.action = 'rename';
            dom.albumDialog.dataset.albumId = String(albumId);
            dom.albumDialogTitle.textContent = 'Rename album';
            dom.albumDialogName.value = album?.name || '';
            dom.albumDialog.style.left = '';
            dom.albumDialog.style.top = '';
            dom.albumDialog.showModal();
        } else if (action === 'delete') {
            event.stopPropagation();
            if (!window.confirm(`Delete album "${album?.name}"? Only the virtual album will be deleted. Indexed assets and physical files will remain untouched.`)) return;
            await fetchJson(`/api/albums/${albumId}`, { method: 'DELETE' });
            if (state.albumId === albumId) {
                await selectCollection('all', 'All assets');
            }
            await loadMetadata();
            showToast('Album deleted; files were not changed');
        } else if (album) {
            await selectCollection('album', album.name, album.id);
        }
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.createAlbum.addEventListener('click', () => {
    dom.albumDialog.dataset.action = 'create';
    dom.albumDialog.dataset.albumId = '';
    dom.albumDialogTitle.textContent = 'Create album';
    dom.albumDialogName.value = '';
    dom.albumDialog.style.left = '';
    dom.albumDialog.style.top = '';
    dom.albumDialog.showModal();
});

dom.grid.addEventListener('click', async event => {
    // Check if album card clicked (in albums grid view)
    const albumCard = event.target.closest('[data-grid-album-id]');
    if (albumCard) {
        const albumId = Number(albumCard.dataset.gridAlbumId);
        const album = state.albums.find(item => item.id === albumId);
        const action = event.target.closest('[data-album-action]')?.dataset.albumAction;
        try {
            if (action === 'rename') {
                event.stopPropagation();
                dom.albumDialog.dataset.action = 'rename';
                dom.albumDialog.dataset.albumId = String(albumId);
                dom.albumDialogTitle.textContent = 'Rename album';
                dom.albumDialogName.value = album?.name || '';
                dom.albumDialog.style.left = '';
                dom.albumDialog.style.top = '';
                dom.albumDialog.showModal();
            } else if (action === 'delete') {
                event.stopPropagation();
                if (!window.confirm(`Delete album "${album?.name}"? Only the virtual album will be deleted. Indexed assets and physical files will remain untouched.`)) return;
                await fetchJson(`/api/albums/${albumId}`, { method: 'DELETE' });
                await loadMetadata();
                renderAssets();
                showToast('Album deleted; files were not changed');
            } else if (album) {
                await selectCollection('album', album.name, album.id);
            }
        } catch (error) {
            showToast(error.message, true);
        }
        return;
    }

    const card = event.target.closest('[data-asset-id]');
    if (!card) return;
    const assetId = Number(card.dataset.assetId);
    const index = state.assets.findIndex(asset => asset.id === assetId);
    const asset = state.assets[index];
    if (!asset) return;
    if (event.target.closest('.asset-favorite')) {
        event.stopPropagation();
        try {
            const data = await fetchJson(`/api/library/assets/${assetId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ favorite: !asset.favorite }),
            });
            if (state.collection === 'favorites' && !data.asset.favorite) {
                state.assets.splice(index, 1);
                state.total = Math.max(0, state.total - 1);
            } else {
                state.assets[index] = data.asset;
            }
            await loadMetadata();
            renderAssets();
        } catch (error) {
            showToast(error.message, true);
        }
        return;
    }
    toggleSelection(assetId, index, event.shiftKey);
});

dom.grid.addEventListener('dblclick', event => {
    const card = event.target.closest('[data-asset-id]');
    if (!card || event.target.closest('button, input')) return;
    const asset = state.assets.find(item => item.id === Number(card.dataset.assetId));
    if (asset) window.open(asset.original_url, '_blank', 'noopener');
});

dom.selectVisible.addEventListener('change', () => {
    if (dom.selectVisible.checked) {
        state.assets.forEach(asset => state.selected.add(asset.id));
    } else {
        state.assets.forEach(asset => state.selected.delete(asset.id));
    }
    renderAssets();
});

dom.toolbar.addEventListener('click', event => {
    const action = event.target.closest('[data-bulk]')?.dataset.bulk;
    if (action) runBulk(action).catch(error => showToast(error.message, true));
});

dom.bulkAlbum.addEventListener('change', async () => {
    const albumId = Number(dom.bulkAlbum.value);
    if (!albumId) return;
    try {
        await runBulk('add_to_album', { album_id: albumId });
    } catch (error) {
        showToast(error.message, true);
    } finally {
        dom.bulkAlbum.value = '';
    }
});

dom.bulkRating.addEventListener('change', async () => {
    if (dom.bulkRating.value === '') return;
    try {
        await runBulk('set_rating', { rating: Number(dom.bulkRating.value) });
    } catch (error) {
        showToast(error.message, true);
    } finally {
        dom.bulkRating.value = '';
    }
});

dom.removeFromAlbum.addEventListener('click', async () => {
    if (!window.confirm('Remove the selected assets from this album? The index and physical files will not be changed.')) return;
    try {
        await runBulk('remove_from_album', { album_id: state.albumId });
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.setAlbumCover.addEventListener('click', async () => {
    const assetId = selectedIds()[0];
    if (!assetId || !state.albumId) return;
    try {
        await fetchJson(`/api/albums/${state.albumId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ cover_image_id: assetId }),
        });
        await loadMetadata();
        showToast('Album cover updated');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.removeFromIndex.addEventListener('click', async () => {
    const count = state.selected.size;
    const message = `Remove ${count} selected asset${count === 1 ? '' : 's'} from the index? Album links, favorites, tags, notes, and cached previews will be removed. Physical files will remain on disk and may be indexed again during source reconciliation.`;
    if (!window.confirm(message)) return;
    try {
        await runBulk('remove_from_index');
        showToast('Removed from index; physical files were not deleted');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.clearSelection.addEventListener('click', () => {
    state.selected.clear();
    renderAssets();
});

dom.editAsset.addEventListener('click', () => {
    const asset = state.assets.find(item => state.selected.has(item.id));
    if (!asset) return;
    dom.editor.dataset.assetId = String(asset.id);
    dom.editorTitle.textContent = asset.file_name;
    dom.editorFilename.value = asset.file_name;
    dom.editorRating.value = String(asset.rating || 0);
    dom.editorTags.value = (asset.tags || []).join(', ');
    dom.editorNote.value = asset.note || '';
    dom.editor.style.left = '';
    dom.editor.style.top = '';
    dom.editor.showModal();
});

dom.editorForm.addEventListener('submit', async event => {
    if (event.submitter?.id !== 'save-asset') return;
    event.preventDefault();
    const assetId = Number(dom.editor.dataset.assetId);
    try {
        const data = await fetchJson(`/api/library/assets/${assetId}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                file_name: dom.editorFilename.value.trim(),
                rating: Number(dom.editorRating.value),
                tags: dom.editorTags.value.split(',').map(tag => tag.trim()).filter(Boolean),
                note: dom.editorNote.value,
            }),
        });
        const index = state.assets.findIndex(asset => asset.id === assetId);
        if (index >= 0) state.assets[index] = data.asset;
        dom.editor.close();
        renderAssets();
        await loadMetadata();
        showToast('Asset details saved');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.loadMore.addEventListener('click', async () => {
    state.page += 1;
    await loadAssets({ append: true });
});

let searchTimer;
dom.search.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(() => {
        state.page = 1;
        state.assets = [];
        state.selected.clear();
        loadAssets();
    }, 250);
});

dom.sort.addEventListener('change', () => {
    state.page = 1;
    state.assets = [];
    state.selected.clear();
    loadAssets();
});

dom.albumDialogForm.addEventListener('submit', async event => {
    if (event.submitter?.id !== 'save-album-btn') return;
    event.preventDefault();
    const action = dom.albumDialog.dataset.action;
    const albumId = dom.albumDialog.dataset.albumId;
    const name = dom.albumDialogName.value.trim();
    if (!name) return;

    try {
        if (action === 'create') {
            const data = await fetchJson('/api/albums', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            await loadMetadata();
            await selectCollection('album', data.album.name, data.album.id);
            showToast('Album created');
        } else if (action === 'rename') {
            await fetchJson(`/api/albums/${albumId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ name }),
            });
            if (state.albumId === Number(albumId)) {
                state.collectionName = name;
            }
            await loadMetadata();
            renderAssets();
            showToast('Album renamed');
        }
        dom.albumDialog.close();
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.ratingFilterButtons.addEventListener('click', event => {
    const button = event.target.closest('.rating-filter-btn');
    if (!button) return;
    const rating = parseInt(button.dataset.rating, 10);

    if (state.ratingFilter === rating) {
        state.ratingFilter = null;
    } else {
        state.ratingFilter = rating;
    }

    dom.ratingFilterButtons.querySelectorAll('.rating-filter-btn').forEach(btn => {
        const btnRating = parseInt(btn.dataset.rating, 10);
        btn.classList.toggle('active', state.ratingFilter === btnRating);
    });

    state.page = 1;
    state.assets = [];
    state.selected.clear();
    loadAssets();
});

document.addEventListener('keydown', event => {
    const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(document.activeElement?.tagName);
    if (event.key === 'Escape') {
        if (dom.editor.open) {
            dom.editor.close();
            event.preventDefault();
        } else if (dom.albumDialog.open) {
            dom.albumDialog.close();
            event.preventDefault();
        } else {
            state.selected.clear();
            renderAssets();
        }
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && !editing) {
        event.preventDefault();
        state.assets.forEach(asset => state.selected.add(asset.id));
        renderAssets();
    }
});

function setupDialogBackdropClose(dialogEl) {
    dialogEl.addEventListener('click', event => {
        const rect = dialogEl.getBoundingClientRect();
        const isInDialog = (
            rect.top <= event.clientY &&
            event.clientY <= rect.top + rect.height &&
            rect.left <= event.clientX &&
            event.clientX <= rect.left + rect.width
        );
        if (!isInDialog) {
            dialogEl.close();
        }
    });
}

async function initialize() {
    try {
        makeDraggable(dom.editor, dom.editor.querySelector('.editor-heading'));
        makeDraggable(dom.albumDialog, dom.albumDialog.querySelector('.editor-heading'));
        setupDialogBackdropClose(dom.editor);
        setupDialogBackdropClose(dom.albumDialog);

        dom.editor.addEventListener('close', () => {
            setTimeout(() => document.activeElement?.blur(), 0);
        });
        dom.albumDialog.addEventListener('close', () => {
            setTimeout(() => document.activeElement?.blur(), 0);
        });

        await loadMetadata();
        await loadAssets();
    } catch (error) {
        dom.feedback.textContent = `Library could not be loaded: ${error.message}`;
        showToast(error.message, true);
    }
}

initialize();
