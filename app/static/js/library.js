const dom = {
    systemCollections: document.getElementById('system-collections'),
    albumList: document.getElementById('album-list'),
    sidebarAlbumTotal: document.getElementById('sidebar-album-total'),
    createAlbum: document.getElementById('create-album'),
    btnLibraryGuide: document.getElementById('btn-library-guide'),
    guideDialog: document.getElementById('library-guide-dialog'),
    closeLibraryGuide: document.getElementById('close-library-guide'),
    collectionTitle: document.getElementById('collection-title'),
    collectionSummary: document.getElementById('collection-summary'),
    search: document.getElementById('library-search'),
    sort: document.getElementById('library-sort'),
    modelFilter: document.getElementById('library-model-filter'),
    orientationFilter: document.getElementById('library-orientation-filter'),
    nodeFilter: document.getElementById('library-node-filter'),
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
    infiniteScrollSentinel: document.getElementById('infinite-scroll-sentinel'),
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
    addFilesButton: document.getElementById('library-add-files-button'),
    addFilesInput: document.getElementById('library-add-files-input'),
    toolbarCopyWorkflow: document.getElementById('toolbar-copy-workflow'),
    toolbarCopyPosPrompt: document.getElementById('toolbar-copy-pos-prompt'),
    toolbarCopyNegPrompt: document.getElementById('toolbar-copy-neg-prompt'),
    shell: document.querySelector('.library-shell'),
    previewPanel: document.getElementById('library-preview-panel'),
    previewPanelImg: document.getElementById('preview-panel-img'),
    previewBackdrop: document.getElementById('preview-backdrop'),
    closePreviewPanel: document.getElementById('close-preview-panel'),
    btnToggleSelect: document.getElementById('btn-toggle-select'),
    btnTogglePreview: document.getElementById('btn-toggle-preview'),
    previewCopyWorkflow: document.getElementById('preview-copy-workflow'),
    previewCopyPosPrompt: document.getElementById('preview-copy-pos-prompt'),
    previewCopyNegPrompt: document.getElementById('preview-copy-neg-prompt'),
    previewCarousel: document.getElementById('preview-carousel'),
    previewResizeHandle: document.getElementById('preview-resize-handle'),
    btnToggleSidebar: document.getElementById('btn-toggle-sidebar'),
    sidebar: document.querySelector('.library-sidebar'),
    toast: document.getElementById('library-toast'),
};

const storageKeys = {
    previewVisible: 'library-preview-visible',
    previewWidth: 'library-preview-width',
    sidebarCollapsed: 'library-sidebar-collapsed',
};

function readStoredBoolean(key, fallback) {
    try {
        const stored = localStorage.getItem(key);
        return stored === null ? fallback : stored === 'true';
    } catch {
        return fallback;
    }
}

function readStoredNumber(key, fallback) {
    try {
        const stored = Number(localStorage.getItem(key));
        return Number.isFinite(stored) && stored > 0 ? stored : fallback;
    } catch {
        return fallback;
    }
}

function writeStoredPreference(key, value) {
    try {
        localStorage.setItem(key, String(value));
    } catch {
        // The UI still works when browser storage is unavailable.
    }
}

const storedSidebarCollapsed = readStoredBoolean(storageKeys.sidebarCollapsed, false);

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
    selectMode: false,
    showPreview: readStoredBoolean(storageKeys.previewVisible, true),
    activeAssetId: null,
    metadataFilters: { node_types: [] },
    infiniteScrollObserver: null,
    assetRequestController: null,
    draggingAssetIds: [],
    pointerDrag: null,
    suppressNextGridClick: false,
    lastGridClick: null,
    previewWidth: readStoredNumber(storageKeys.previewWidth, 450),
    sidebarCollapsed: storedSidebarCollapsed,
    sidebarExplicitlyCollapsed: storedSidebarCollapsed,
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

    dom.sidebarAlbumTotal.textContent = state.albums.length ? String(state.albums.length) : '';
    dom.albumList.innerHTML = state.albums.length ? state.albums.map(album => `
        <article class="sidebar-album-card ${state.collection === 'album' && state.albumId === album.id ? 'active' : ''}"
                 data-album-id="${album.id}" data-album-drop-target="${album.id}" data-album-name="${escapeHtml(album.name)}">
            <button class="sidebar-album-main" type="button" data-album-open="${album.id}" title="Open ${escapeHtml(album.name)}">
                <span class="sidebar-album-cover" ${album.display_cover_image_id ? `style="background-image:url('/api/thumbnail/${album.display_cover_image_id}')"` : ''}>
                    <span class="sidebar-album-placeholder" aria-hidden="true">${album.display_cover_image_id ? '' : '▤'}</span>
                    <span class="sidebar-album-drop-icon" aria-hidden="true">＋</span>
                </span>
                <span class="sidebar-album-copy">
                    <span class="sidebar-album-title-row">
                        <span class="sidebar-album-name">${escapeHtml(album.name)}</span>
                        <span class="sidebar-album-count">${album.asset_count}</span>
                    </span>
                    <span class="sidebar-album-drop-label">Drop images here</span>
                </span>
            </button>
            <span class="sidebar-album-actions">
                <button type="button" data-album-action="rename" title="Rename album" aria-label="Rename ${escapeHtml(album.name)}">✎</button>
                <button type="button" data-album-action="delete" title="Delete album" aria-label="Delete ${escapeHtml(album.name)}">×</button>
            </span>
        </article>`).join('') : `
            <button class="album-empty-state" type="button" data-create-album-shortcut>
                <span class="album-empty-icon">＋</span>
                <span><strong>Create an album</strong><small>Then drag images here</small></span>
            </button>`;

    dom.bulkAlbum.innerHTML = '<option value="">Add to album…</option>' + state.albums.map(album => (
        `<option value="${album.id}">${escapeHtml(album.name)}</option>`
    )).join('');
}

function renderMetadataFilters() {
    const currentNode = dom.nodeFilter.value;
    const nodeTypes = state.metadataFilters.node_types || [];
    dom.nodeFilter.innerHTML = '<option value="">All generation nodes</option>' + nodeTypes.map(nodeType => (
        `<option value="${escapeHtml(nodeType)}">${escapeHtml(nodeType)}</option>`
    )).join('');
    if (nodeTypes.includes(currentNode)) dom.nodeFilter.value = currentNode;
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
        dom.infiniteScrollSentinel.hidden = true;
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
            const isActive = asset.id === state.activeAssetId;
            return `
                <article class="asset-card ${selected ? 'selected' : ''} ${isActive ? 'active' : ''} ${asset.available ? '' : 'unavailable'}"
                         data-asset-id="${asset.id}" tabindex="${isActive ? '0' : '-1'}"
                         aria-selected="${selected ? 'true' : 'false'}"
                         aria-label="${escapeHtml(asset.file_name)}">
                    <div class="asset-thumb-wrap">
                        <img class="asset-thumb" src="${escapeHtml(asset.thumbnail_url)}" alt="" loading="lazy" draggable="false">
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
    updateInfiniteScroll();
    dom.collectionTitle.textContent = state.collectionName;
    dom.collectionSummary.textContent = `${state.total} asset${state.total === 1 ? '' : 's'} · physical files stay in their sources`;
    updateSelectionToolbar();
}

let selectionToolbarTimer = null;

function updateSelectionToolbar() {
    const count = state.selected.size;
    dom.toolbar.hidden = !state.selectMode || count === 0;
    dom.selectionCount.textContent = `${count} selected`;
    dom.selectVisible.checked = state.assets.length > 0 && state.assets.every(asset => state.selected.has(asset.id));
    dom.selectVisible.indeterminate = count > 0 && !dom.selectVisible.checked;
    const isAlbum = state.collection === 'album' && state.albumId !== null;
    dom.removeFromAlbum.hidden = !isAlbum;
    dom.setAlbumCover.hidden = !isAlbum || count !== 1;
    dom.editAsset.disabled = count !== 1;

    if (selectionToolbarTimer) {
        clearTimeout(selectionToolbarTimer);
        selectionToolbarTimer = null;
    }

    if (state.selectMode && count === 1) {
        const assetId = selectedIds()[0];
        selectionToolbarTimer = setTimeout(async () => {
            try {
                const detail = await fetchJson(`/api/images/${assetId}`);
                if (state.selected.size === 1 && selectedIds()[0] === assetId) {
                    const hasWorkflow = !!(detail.workflow_ui_json || detail.workflow);
                    const hasPos = !!detail.prompt_parameters?.positive_prompt;
                    const hasNeg = !!detail.prompt_parameters?.negative_prompt;

                    dom.toolbarCopyWorkflow.hidden = !hasWorkflow;
                    dom.toolbarCopyPosPrompt.hidden = !hasPos;
                    dom.toolbarCopyNegPrompt.hidden = !hasNeg;
                }
            } catch (error) {
                console.error('Failed to load asset details for bulk copy options:', error);
                dom.toolbarCopyWorkflow.hidden = true;
                dom.toolbarCopyPosPrompt.hidden = true;
                dom.toolbarCopyNegPrompt.hidden = true;
            }
        }, 100);
    } else {
        dom.toolbarCopyWorkflow.hidden = true;
        dom.toolbarCopyPosPrompt.hidden = true;
        dom.toolbarCopyNegPrompt.hidden = true;
    }
}

let previewPanelTimer = null;

function updateLayoutColumns() {
    const activeAsset = state.assets.find(item => item.id === state.activeAssetId);
    dom.btnTogglePreview.classList.toggle('active', state.showPreview);
    dom.btnTogglePreview.setAttribute('aria-pressed', String(state.showPreview));
    const previewActionLabel = state.showPreview ? 'Hide image preview' : 'Show image preview';
    dom.btnTogglePreview.title = previewActionLabel;
    dom.btnTogglePreview.setAttribute('aria-label', previewActionLabel);
    if (state.showPreview && activeAsset) {
        dom.previewPanel.style.width = state.previewWidth + 'px';
        dom.previewPanel.style.borderLeftWidth = '1px';
    } else {
        dom.previewPanel.style.width = '0px';
        dom.previewPanel.style.borderLeftWidth = '0px';
    }
}

function updateSidebarUI() {
    dom.shell.classList.toggle('sidebar-collapsed', state.sidebarCollapsed);
    dom.btnToggleSidebar.setAttribute('aria-expanded', String(!state.sidebarCollapsed));
    dom.btnToggleSidebar.title = state.sidebarCollapsed ? 'Show sidebar' : 'Hide sidebar';
    updateLayoutColumns();
}

function setPreviewVisibility(visible) {
    state.showPreview = visible;
    writeStoredPreference(storageKeys.previewVisible, visible);
    updatePreviewPanel();
}

function updatePreviewPanel() {
    if (previewPanelTimer) {
        clearTimeout(previewPanelTimer);
        previewPanelTimer = null;
    }

    const activeAsset = state.assets.find(item => item.id === state.activeAssetId);
    if (state.showPreview && activeAsset) {
        const originalUrl = `/api/original/${activeAsset.id}`;
        
        if (dom.previewPanelImg.getAttribute('data-loaded-id') !== String(activeAsset.id)) {
            dom.previewPanelImg.setAttribute('data-loaded-id', String(activeAsset.id));
            dom.previewPanelImg.src = originalUrl;
            dom.previewBackdrop.style.backgroundImage = `url("${originalUrl}")`;
        }
        
        if (state.selectMode && state.selected.size > 1) {
            const selectedAssets = state.assets.filter(asset => state.selected.has(asset.id));
            dom.previewCarousel.innerHTML = selectedAssets.map(asset => {
                const isActive = asset.id === state.activeAssetId;
                return `
                    <div class="carousel-thumb-wrap ${isActive ? 'active' : ''}" data-carousel-id="${asset.id}">
                        <img class="carousel-thumb" src="${escapeHtml(asset.thumbnail_url)}" alt="" loading="lazy">
                    </div>
                `;
            }).join('');
            dom.previewCarousel.hidden = false;
        } else {
            dom.previewCarousel.hidden = true;
            dom.previewCarousel.innerHTML = '';
        }

        dom.shell.classList.add('show-preview');
        updateLayoutColumns();

        previewPanelTimer = setTimeout(async () => {
            try {
                const detail = await fetchJson(`/api/images/${activeAsset.id}`);
                if (state.activeAssetId === activeAsset.id && state.showPreview) {
                    currentSelectedDetail = detail;
                    const hasWorkflow = !!(detail.workflow_ui_json || detail.workflow);
                    const hasPos = !!detail.prompt_parameters?.positive_prompt;
                    const hasNeg = !!detail.prompt_parameters?.negative_prompt;

                    dom.previewCopyWorkflow.hidden = !hasWorkflow;
                    dom.previewCopyPosPrompt.hidden = !hasPos;
                    dom.previewCopyNegPrompt.hidden = !hasNeg;
                }
            } catch (error) {
                console.error('Failed to load asset details for preview options:', error);
                dom.previewCopyWorkflow.hidden = true;
                dom.previewCopyPosPrompt.hidden = true;
                dom.previewCopyNegPrompt.hidden = true;
            }
        }, 100);
    } else {
        dom.shell.classList.remove('show-preview');
        updateLayoutColumns();
        dom.previewPanelImg.src = '';
        dom.previewPanelImg.removeAttribute('data-loaded-id');
        dom.previewBackdrop.style.backgroundImage = '';
        dom.previewCopyWorkflow.hidden = true;
        dom.previewCopyPosPrompt.hidden = true;
        dom.previewCopyNegPrompt.hidden = true;
        dom.previewCarousel.hidden = true;
        dom.previewCarousel.innerHTML = '';
    }
}

function applyCurrentFilters(params) {
    if (state.albumId !== null) params.set('album_id', String(state.albumId));
    if (dom.search.value.trim()) params.set('q', dom.search.value.trim());
    if (state.ratingFilter !== null) params.set('rating', String(state.ratingFilter));
    if (dom.modelFilter.value) params.set('model_family', dom.modelFilter.value);
    if (dom.orientationFilter.value) params.set('orientation', dom.orientationFilter.value);
    if (dom.nodeFilter.value) params.set('node_type', dom.nodeFilter.value);
    return params;
}

function buildAssetsUrl() {
    const [sortBy, sortDir] = dom.sort.value.split(':');
    const params = applyCurrentFilters(new URLSearchParams({
        collection: state.collection,
        page: String(state.page),
        per_page: String(state.perPage),
        sort_by: sortBy,
        sort_dir: sortDir,
    }));
    return `/api/library/assets?${params}`;
}

async function refreshAssets() {
    if (state.assetRequestController) state.assetRequestController.abort();
    const controller = new AbortController();
    state.assetRequestController = controller;
    state.loading = true;
    try {
        const [sortBy, sortDir] = dom.sort.value.split(':');
        const params = applyCurrentFilters(new URLSearchParams({
            collection: state.collection,
            page: '1',
            per_page: String(state.page * state.perPage),
            sort_by: sortBy,
            sort_dir: sortDir,
        }));

        const data = await fetchJson(`/api/library/assets?${params}`, { signal: controller.signal });
        state.assets = data.assets || [];
        state.total = data.total || 0;
        if (!state.assets.some(asset => asset.id === state.activeAssetId)) {
            state.activeAssetId = state.assets[0]?.id ?? null;
        }
    } catch (error) {
        if (error.name !== 'AbortError') showToast(error.message, true);
    } finally {
        if (state.assetRequestController === controller) {
            state.assetRequestController = null;
            state.loading = false;
            renderAssets();
            updatePreviewPanel();
        }
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

async function loadMetadata({ includeFilters = false } = {}) {
    const data = await fetchJson(`/api/library?include_filters=${includeFilters ? '1' : '0'}`);
    state.systemCollections = data.system_collections || [];
    state.albums = data.albums || [];
    state.summary = data.summary || {};
    if (data.metadata_filters) state.metadataFilters = data.metadata_filters;
    renderCollections();
    renderMetadataFilters();
}

async function loadAssets({ append = false } = {}) {
    if (state.loading && append) return false;
    if (state.assetRequestController) state.assetRequestController.abort();
    const controller = new AbortController();
    state.assetRequestController = controller;
    state.loading = true;
    renderAssets();
    let succeeded = false;
    try {
        const data = await fetchJson(buildAssetsUrl(), { signal: controller.signal });
        state.assets = append ? [...state.assets, ...(data.assets || [])] : (data.assets || []);
        state.total = data.total || 0;
        succeeded = true;
    } catch (error) {
        if (error.name !== 'AbortError') {
            showToast(error.message, true);
            if (!append) state.assets = [];
        }
    } finally {
        if (state.assetRequestController === controller) {
            state.assetRequestController = null;
            state.loading = false;
            if (state.assets.length > 0 && state.activeAssetId === null) {
                state.activeAssetId = state.assets[0].id;
            }
            renderAssets();
            updatePreviewPanel();
        }
    }
    return succeeded;
}

function updateInfiniteScroll() {
    const hasMore = state.collection !== 'albums' && state.assets.length < state.total;
    const shouldShow = state.assets.length > 0 && (hasMore || state.loading);
    dom.infiniteScrollSentinel.hidden = !shouldShow;
    const label = dom.infiniteScrollSentinel.querySelector('span:last-child');
    if (label) label.textContent = state.loading ? 'Loading more assets…' : 'More assets load automatically';

    if (!state.infiniteScrollObserver) return;
    state.infiniteScrollObserver.unobserve(dom.infiniteScrollSentinel);
    if (hasMore && !state.loading) {
        window.requestAnimationFrame(() => {
            if (!dom.infiniteScrollSentinel.hidden) {
                state.infiniteScrollObserver.observe(dom.infiniteScrollSentinel);
            }
        });
    }
}

async function loadNextPage() {
    if (state.loading || state.collection === 'albums' || state.assets.length >= state.total) return;
    const previousPage = state.page;
    state.page += 1;
    const succeeded = await loadAssets({ append: true });
    if (!succeeded) state.page = previousPage;
}

function setupInfiniteScroll() {
    state.infiniteScrollObserver = new IntersectionObserver(entries => {
        if (entries.some(entry => entry.isIntersecting)) {
            loadNextPage().catch(error => showToast(error.message, true));
        }
    }, {
        root: null,
        rootMargin: '600px 0px',
        threshold: 0,
    });
    updateInfiniteScroll();
}

async function selectCollection(collection, name, albumId = null) {
    state.collection = collection;
    state.collectionName = name;
    state.albumId = albumId;
    state.page = 1;
    state.assets = [];
    state.selected.clear();
    state.lastSelectedIndex = null;
    state.activeAssetId = null;
    renderCollections();
    if (collection === 'albums') {
        renderAssets();
        updatePreviewPanel();
    } else {
        await loadAssets();
    }
}

function selectedIds() {
    return [...state.selected];
}

function cancelPendingAssetLoad() {
    if (!state.assetRequestController) return;
    state.assetRequestController.abort();
    state.assetRequestController = null;
    state.loading = false;
}

async function runBulk(action, extra = {}) {
    const ids = selectedIds();
    if (!ids.length) return;
    cancelPendingAssetLoad();
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

function captureLibraryScroll() {
    const containers = [];
    const seen = new Set();
    const addContainer = element => {
        if (!element || seen.has(element)) return;
        seen.add(element);
        containers.push({
            element,
            left: element.scrollLeft,
            top: element.scrollTop,
        });
    };

    let ancestor = dom.grid.parentElement;
    while (ancestor) {
        const overflowY = window.getComputedStyle(ancestor).overflowY;
        if (/(auto|scroll|overlay)/.test(overflowY)) addContainer(ancestor);
        ancestor = ancestor.parentElement;
    }

    addContainer(document.scrollingElement);
    addContainer(document.documentElement);
    addContainer(document.body);

    return containers;
}

function restoreLibraryScroll(scrollState) {
    scrollState.forEach(({ element, left, top }) => {
        element.scrollLeft = left;
        element.scrollTop = top;
    });
}

function preserveVisibleCardPosition(anchor, scrollState) {
    restoreLibraryScroll(scrollState);
    if (!anchor) return;

    const currentCard = dom.grid.querySelector(`[data-asset-id="${anchor.assetId}"]`);
    if (!currentCard) return;

    const offsetChange = currentCard.getBoundingClientRect().top - anchor.top;
    if (Math.abs(offsetChange) <= 0.5) return;

    const activeScroller = scrollState.find(({ top }) => top > 0)
        || scrollState.find(({ element }) => element === document.scrollingElement)
        || scrollState[0];
    if (activeScroller) {
        activeScroller.element.scrollTop += offsetChange;
        activeScroller.top = activeScroller.element.scrollTop;
    }
}

function clearGridSelection({ exitSelectMode = false } = {}) {
    const scrollState = captureLibraryScroll();
    const visibleCard = [...dom.grid.querySelectorAll('[data-asset-id]')].find(card => {
        const rect = card.getBoundingClientRect();
        return rect.bottom > 0 && rect.top < window.innerHeight;
    });
    const anchor = visibleCard ? {
        assetId: visibleCard.dataset.assetId,
        top: visibleCard.getBoundingClientRect().top,
    } : null;

    const focusedElement = document.activeElement;
    if (focusedElement?.closest?.('#selection-toolbar, .asset-select')) {
        focusedElement.blur();
    }

    state.selected.clear();
    state.lastSelectedIndex = null;
    if (exitSelectMode) {
        state.selectMode = false;
        dom.btnToggleSelect.classList.remove('active');
        dom.shell.classList.remove('select-mode-on');
    }

    dom.grid.querySelectorAll('.asset-card.selected').forEach(card => {
        card.classList.remove('selected');
        card.setAttribute('aria-selected', 'false');
        const checkbox = card.querySelector('.asset-select');
        if (checkbox) checkbox.checked = false;
    });
    updateSelectionToolbar();
    updatePreviewPanel();

    restoreLibraryScroll(scrollState);
    window.requestAnimationFrame(() => {
        preserveVisibleCardPosition(anchor, scrollState);
        window.requestAnimationFrame(() => preserveVisibleCardPosition(anchor, scrollState));
    });
}

function activateAssetSelection(assetId, index) {
    state.selectMode = true;
    state.selected.add(assetId);
    state.lastSelectedIndex = index;
    state.activeAssetId = assetId;
    dom.btnToggleSelect.classList.add('active');
    dom.shell.classList.add('select-mode-on');
    renderAssets();
    updatePreviewPanel();
    focusActiveCard();
}

function focusActiveCard({ smooth = false } = {}) {
    window.requestAnimationFrame(() => {
        const card = dom.grid.querySelector(`[data-asset-id="${state.activeAssetId}"]`);
        if (!card) return;
        card.focus({ preventScroll: true });
        card.scrollIntoView({
            block: 'nearest',
            inline: 'nearest',
            behavior: smooth ? 'smooth' : 'auto',
        });
    });
}

function assetNoLongerMatches(asset) {
    if (state.collection === 'favorites' && !asset.favorite) return true;
    if (state.collection === 'not_rated' && (asset.rating || 0) > 0) return true;
    return state.ratingFilter !== null && (asset.rating || 0) !== state.ratingFilter;
}

async function patchAsset(assetId, payload, successMessage = '') {
    const index = state.assets.findIndex(asset => asset.id === assetId);
    if (index < 0) return;
    cancelPendingAssetLoad();
    const data = await fetchJson(`/api/library/assets/${assetId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
    });

    if (assetNoLongerMatches(data.asset)) {
        state.assets.splice(index, 1);
        state.total = Math.max(0, state.total - 1);
        state.selected.delete(assetId);
        state.activeAssetId = state.assets[Math.min(index, state.assets.length - 1)]?.id ?? null;
    } else {
        state.assets[index] = data.asset;
    }

    await loadMetadata();
    renderAssets();
    updatePreviewPanel();
    focusActiveCard();
    if (successMessage) showToast(successMessage);
}

async function toggleFavorite(assetId) {
    const asset = state.assets.find(item => item.id === assetId);
    if (!asset) return;
    await patchAsset(
        assetId,
        { favorite: !asset.favorite },
        asset.favorite ? 'Removed from favorites' : 'Added to favorites',
    );
}

async function setAssetRating(assetId, rating) {
    await patchAsset(assetId, { rating }, `Rated ${rating} star${rating === 1 ? '' : 's'}`);
}

dom.systemCollections.addEventListener('click', event => {
    const button = event.target.closest('[data-collection]');
    if (!button) return;
    const collection = state.systemCollections.find(item => item.id === button.dataset.collection);
    if (collection) selectCollection(collection.id, collection.name);
});

dom.albumList.addEventListener('click', async event => {
    if (event.target.closest('[data-create-album-shortcut]')) {
        dom.createAlbum.click();
        return;
    }
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

function clearAlbumDropTargets() {
    dom.albumList.querySelectorAll('.drag-over').forEach(item => item.classList.remove('drag-over'));
}

async function addAssetsToAlbumFromGrid(albumId, assetIds) {
    try {
        const data = await fetchJson(`/api/albums/${albumId}/assets`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ asset_ids: assetIds }),
        });
        await loadMetadata();
        const album = state.albums.find(item => item.id === albumId);
        showToast(data.affected
            ? `${data.affected} asset${data.affected === 1 ? '' : 's'} added to ${album?.name || 'album'}`
            : `Selected assets are already in ${album?.name || 'this album'}`);
    } catch (error) {
        showToast(error.message, true);
    }
}

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
    if (state.suppressNextGridClick) {
        event.preventDefault();
        event.stopPropagation();
        state.suppressNextGridClick = false;
        return;
    }
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
            await toggleFavorite(assetId);
        } catch (error) {
            showToast(error.message, true);
        }
        return;
    }

    if (!event.target.closest('button, input, a')) {
        const clickTime = performance.now();
        const isDoubleClick = (
            state.lastGridClick?.assetId === assetId
            && clickTime - state.lastGridClick.time <= 400
        );
        state.lastGridClick = isDoubleClick ? null : { assetId, time: clickTime };
        if (isDoubleClick) {
            event.preventDefault();
            activateAssetSelection(assetId, index);
            return;
        }
    } else {
        state.lastGridClick = null;
    }

    if (state.selectMode) {
        toggleSelection(assetId, index, event.shiftKey);
        state.activeAssetId = assetId;
        renderAssets();
        updatePreviewPanel();
    } else {
        state.activeAssetId = assetId;
        renderAssets();
        updatePreviewPanel();
    }
});

function createAssetDragPreview(asset, count) {
    const preview = document.createElement('div');
    preview.className = 'asset-drag-preview';

    const image = document.createElement('img');
    image.src = asset.thumbnail_url;
    image.alt = '';
    image.draggable = false;

    const copy = document.createElement('span');
    copy.className = 'asset-drag-preview-copy';
    const title = document.createElement('strong');
    title.textContent = count === 1 ? asset.file_name : `${count} selected images`;
    const hint = document.createElement('span');
    hint.textContent = 'Drop onto an album';
    copy.append(title, hint);
    preview.append(image, copy);
    document.body.append(preview);
    return preview;
}

function albumTargetAtPoint(clientX, clientY) {
    return document.elementFromPoint(clientX, clientY)?.closest?.('[data-album-drop-target]') || null;
}

function updatePointerDropTarget(session, clientX, clientY) {
    const target = albumTargetAtPoint(clientX, clientY);
    if (target === session.dropTarget) return;
    clearAlbumDropTargets();
    session.dropTarget = target;
    target?.classList.add('drag-over');
}

function beginPointerAssetDrag(session, event) {
    const asset = state.assets.find(item => item.id === session.assetId);
    if (!asset) return false;

    const dragSelectedGroup = state.selectMode && state.selected.has(session.assetId);
    state.draggingAssetIds = dragSelectedGroup ? selectedIds() : [session.assetId];
    session.dragging = true;
    session.preview = createAssetDragPreview(asset, state.draggingAssetIds.length);
    const draggingIds = new Set(state.draggingAssetIds);
    dom.grid.querySelectorAll('[data-asset-id]').forEach(card => {
        const cardId = Number(card.dataset.assetId);
        card.classList.toggle('dragging', draggingIds.has(cardId));
    });
    dom.shell.classList.add('asset-drag-active');
    document.body.classList.add('asset-pointer-dragging');
    updatePointerDropTarget(session, event.clientX, event.clientY);
    return true;
}

function moveAssetDragPreview(session, clientX, clientY) {
    if (!session.preview) return;
    session.preview.style.transform = `translate3d(${clientX + 14}px, ${clientY + 14}px, 0)`;
}

function cleanupPointerAssetDrag(session) {
    try {
        session.card.releasePointerCapture?.(session.pointerId);
    } catch {
        // Capture may already be released by the browser.
    }
    session.preview?.remove();
    clearAlbumDropTargets();
    dom.shell.classList.remove('asset-drag-active');
    document.body.classList.remove('asset-pointer-dragging');
    state.draggingAssetIds = [];
    state.pointerDrag = null;
    renderAssets();
    updatePreviewPanel();
}

dom.grid.addEventListener('pointerdown', event => {
    if (event.button !== 0 || event.pointerType === 'touch') return;
    if (state.pointerDrag) return;
    if (event.target.closest('button, input, a')) return;
    const card = event.target.closest('[data-asset-id]');
    if (!card || state.collection === 'albums') return;
    const assetId = Number(card.dataset.assetId);
    if (!state.assets.some(asset => asset.id === assetId)) return;

    state.pointerDrag = {
        pointerId: event.pointerId,
        assetId,
        card,
        startX: event.clientX,
        startY: event.clientY,
        dragging: false,
        preview: null,
        dropTarget: null,
    };
    card.setPointerCapture?.(event.pointerId);
});

document.addEventListener('pointermove', event => {
    const session = state.pointerDrag;
    if (!session || session.pointerId !== event.pointerId) return;
    const distance = Math.hypot(event.clientX - session.startX, event.clientY - session.startY);
    if (!session.dragging && distance >= 6 && !beginPointerAssetDrag(session, event)) return;
    if (!session.dragging) return;
    event.preventDefault();
    moveAssetDragPreview(session, event.clientX, event.clientY);
    updatePointerDropTarget(session, event.clientX, event.clientY);
}, { passive: false });

async function finishPointerAssetDrag(event, cancelled = false) {
    const session = state.pointerDrag;
    if (!session || session.pointerId !== event.pointerId) return;
    const wasDragging = session.dragging;
    if (!wasDragging) {
        try {
            session.card.releasePointerCapture?.(session.pointerId);
        } catch {
            // Capture may already be released by the browser.
        }
        state.pointerDrag = null;
        return;
    }
    const finalDropTarget = cancelled
        ? null
        : albumTargetAtPoint(event.clientX, event.clientY);
    const albumId = finalDropTarget
        ? Number(finalDropTarget.dataset.albumDropTarget)
        : null;
    const assetIds = [...state.draggingAssetIds];

    if (wasDragging) {
        state.suppressNextGridClick = true;
        window.setTimeout(() => { state.suppressNextGridClick = false; }, 100);
    }
    cleanupPointerAssetDrag(session);
    if (wasDragging && albumId && assetIds.length) {
        await addAssetsToAlbumFromGrid(albumId, assetIds);
    }
}

document.addEventListener('pointerup', event => {
    finishPointerAssetDrag(event).catch(error => showToast(error.message, true));
});

document.addEventListener('pointercancel', event => {
    finishPointerAssetDrag(event, true).catch(error => showToast(error.message, true));
});

dom.grid.addEventListener('dragstart', event => event.preventDefault());

dom.selectVisible.addEventListener('change', () => {
    if (dom.selectVisible.checked) {
        state.assets.forEach(asset => state.selected.add(asset.id));
    } else {
        state.assets.forEach(asset => state.selected.delete(asset.id));
    }
    renderAssets();
    updatePreviewPanel();
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
    updatePreviewPanel();
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

let currentSelectedDetail = null;

dom.toolbarCopyWorkflow.addEventListener('click', async () => {
    const wf = currentSelectedDetail?.workflow_ui_json || currentSelectedDetail?.workflow;
    if (!wf) return;
    try {
        await navigator.clipboard.writeText(JSON.stringify(wf, null, 2));
        showToast('Workflow copied to clipboard');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.toolbarCopyPosPrompt.addEventListener('click', async () => {
    if (!currentSelectedDetail || !currentSelectedDetail.prompt_parameters?.positive_prompt) return;
    try {
        await navigator.clipboard.writeText(currentSelectedDetail.prompt_parameters.positive_prompt);
        showToast('Positive prompt copied to clipboard');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.toolbarCopyNegPrompt.addEventListener('click', async () => {
    if (!currentSelectedDetail || !currentSelectedDetail.prompt_parameters?.negative_prompt) return;
    try {
        await navigator.clipboard.writeText(currentSelectedDetail.prompt_parameters.negative_prompt);
        showToast('Negative prompt copied to clipboard');
    } catch (error) {
        showToast(error.message, true);
    }
});

dom.addFilesButton.addEventListener('click', () => dom.addFilesInput.click());

dom.addFilesInput.addEventListener('change', async () => {
    if (!dom.addFilesInput.files.length) return;
    const files = dom.addFilesInput.files;
    const SUPPORTED_EXTENSIONS = ['.png', '.jpg', '.jpeg', '.webp', '.bmp', '.tiff'];
    const validFiles = Array.from(files).filter(file => {
        const ext = file.name.slice(file.name.lastIndexOf('.')).toLowerCase();
        return SUPPORTED_EXTENSIONS.includes(ext);
    });

    if (validFiles.length === 0) {
        showToast('No supported images found', true);
        return;
    }

    const formData = new FormData();
    for (const file of validFiles) formData.append('files', file);

    showToast(`Adding ${validFiles.length} file(s)...`);
    try {
        const data = await fetchJson('/api/upload', {
            method: 'POST',
            body: formData
        });
        if (data.images?.length) {
            showToast(`${data.images.length} file(s) added successfully`);
            await loadMetadata({ includeFilters: true });
            await loadAssets();
        } else {
            showToast('No images were added', true);
        }
    } catch (error) {
        showToast(error.message, true);
    } finally {
        dom.addFilesInput.value = '';
    }
});

function resetAssetQuery() {
    state.page = 1;
    state.assets = [];
    state.selected.clear();
    state.lastSelectedIndex = null;
    state.activeAssetId = null;
    loadAssets().catch(error => showToast(error.message, true));
}

let searchTimer;
dom.search.addEventListener('input', () => {
    window.clearTimeout(searchTimer);
    searchTimer = window.setTimeout(resetAssetQuery, 250);
});

dom.sort.addEventListener('change', resetAssetQuery);
dom.modelFilter.addEventListener('change', resetAssetQuery);
dom.orientationFilter.addEventListener('change', resetAssetQuery);
dom.nodeFilter.addEventListener('change', resetAssetQuery);

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

    resetAssetQuery();
});

function gridColumnCount() {
    const columns = window.getComputedStyle(dom.grid).gridTemplateColumns;
    if (!columns || columns === 'none') return 1;
    return Math.max(1, columns.split(/\s+/).filter(Boolean).length);
}

async function moveActiveAsset(key) {
    if (!state.assets.length || state.collection === 'albums') return;
    let index = state.assets.findIndex(asset => asset.id === state.activeAssetId);
    if (index < 0) index = 0;
    const columns = gridColumnCount();
    const delta = {
        ArrowLeft: -1,
        ArrowRight: 1,
        ArrowUp: -columns,
        ArrowDown: columns,
    }[key];
    let targetIndex = index + delta;

    if (targetIndex >= state.assets.length && state.assets.length < state.total) {
        await loadNextPage();
    }
    targetIndex = Math.max(0, Math.min(targetIndex, state.assets.length - 1));
    state.activeAssetId = state.assets[targetIndex].id;
    renderAssets();
    updatePreviewPanel();
    focusActiveCard({ smooth: true });
}

document.addEventListener('keydown', async event => {
    const activeElement = document.activeElement;
    const editing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(activeElement?.tagName) || activeElement?.isContentEditable;
    const dialogOpen = dom.editor.open || dom.albumDialog.open || dom.guideDialog.open;
    const externalInteractive = !!activeElement?.closest?.('button, a, [role="button"]') && !activeElement.closest('.asset-card');
    if (event.key === 'Escape') {
        let handled = true;
        if (dom.guideDialog.open) {
            dom.guideDialog.close();
        } else if (dom.editor.open) {
            dom.editor.close();
        } else if (dom.albumDialog.open) {
            dom.albumDialog.close();
        } else if (state.selectMode) {
            clearGridSelection({ exitSelectMode: true });
        } else if (state.selected.size > 0) {
            clearGridSelection();
        } else {
            handled = false;
        }
        if (handled) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    } else if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === 'a' && !editing && !dialogOpen) {
        event.preventDefault();
        state.assets.forEach(asset => state.selected.add(asset.id));
        renderAssets();
        updatePreviewPanel();
    } else if (!editing && !dialogOpen && !externalInteractive && !event.ctrlKey && !event.metaKey && !event.altKey && event.key.startsWith('Arrow')) {
        event.preventDefault();
        await moveActiveAsset(event.key);
    } else if (!editing && !dialogOpen && !externalInteractive && !event.ctrlKey && !event.metaKey && !event.altKey && (event.key === ' ' || event.code === 'Space')) {
        event.preventDefault();
        if (event.repeat || !state.activeAssetId) return;
        if (!state.selectMode) {
            state.selectMode = true;
            dom.btnToggleSelect.classList.add('active');
            dom.shell.classList.add('select-mode-on');
        }
        const index = state.assets.findIndex(asset => asset.id === state.activeAssetId);
        if (index >= 0) {
            toggleSelection(state.activeAssetId, index, event.shiftKey);
            updatePreviewPanel();
            focusActiveCard();
        }
    } else if (!editing && !dialogOpen && !externalInteractive && !event.ctrlKey && !event.metaKey && !event.altKey && event.key.toLowerCase() === 'f') {
        event.preventDefault();
        if (event.repeat || !state.activeAssetId) return;
        try {
            await toggleFavorite(state.activeAssetId);
        } catch (error) {
            showToast(error.message, true);
        }
    } else if (!editing && !dialogOpen && !externalInteractive && !event.ctrlKey && !event.metaKey && !event.altKey && /^[1-5]$/.test(event.key)) {
        event.preventDefault();
        if (event.repeat || !state.activeAssetId) return;
        try {
            await setAssetRating(state.activeAssetId, Number(event.key));
        } catch (error) {
            showToast(error.message, true);
        }
    }
}, { capture: true });

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
        setupDialogBackdropClose(dom.guideDialog);

        dom.btnLibraryGuide.addEventListener('click', () => {
            dom.guideDialog.showModal();
            dom.btnLibraryGuide.setAttribute('aria-expanded', 'true');
        });
        dom.closeLibraryGuide.addEventListener('click', () => dom.guideDialog.close());

        dom.editor.addEventListener('close', () => {
            setTimeout(() => document.activeElement?.blur(), 0);
        });
        dom.albumDialog.addEventListener('close', () => {
            setTimeout(() => document.activeElement?.blur(), 0);
        });
        dom.guideDialog.addEventListener('close', () => {
            dom.btnLibraryGuide.setAttribute('aria-expanded', 'false');
            dom.btnLibraryGuide.focus({ preventScroll: true });
        });
        dom.closePreviewPanel.addEventListener('click', () => {
            setPreviewVisibility(false);
        });

        dom.btnToggleSelect.addEventListener('click', () => {
            state.selectMode = !state.selectMode;
            dom.btnToggleSelect.classList.toggle('active', state.selectMode);
            dom.shell.classList.toggle('select-mode-on', state.selectMode);
            if (!state.selectMode) {
                state.selected.clear();
            } else {
                if (state.activeAssetId) {
                    state.selected.add(state.activeAssetId);
                }
            }
            renderAssets();
            updatePreviewPanel();
        });

        dom.btnTogglePreview.addEventListener('click', () => {
            setPreviewVisibility(!state.showPreview);
        });

        dom.previewCarousel.addEventListener('click', event => {
            const wrap = event.target.closest('[data-carousel-id]');
            if (!wrap) return;
            const assetId = Number(wrap.dataset.carouselId);
            state.activeAssetId = assetId;
            renderAssets();
            updatePreviewPanel();
        });

        dom.previewCopyWorkflow.addEventListener('click', async () => {
            const wf = currentSelectedDetail?.workflow_ui_json || currentSelectedDetail?.workflow;
            if (!wf) return;
            try {
                await navigator.clipboard.writeText(JSON.stringify(wf, null, 2));
                showToast('Workflow copied to clipboard');
            } catch (error) {
                showToast(error.message, true);
            }
        });

        dom.previewCopyPosPrompt.addEventListener('click', async () => {
            if (!currentSelectedDetail || !currentSelectedDetail.prompt_parameters?.positive_prompt) return;
            try {
                await navigator.clipboard.writeText(currentSelectedDetail.prompt_parameters.positive_prompt);
                showToast('Positive prompt copied to clipboard');
            } catch (error) {
                showToast(error.message, true);
            }
        });

        dom.previewCopyNegPrompt.addEventListener('click', async () => {
            if (!currentSelectedDetail || !currentSelectedDetail.prompt_parameters?.negative_prompt) return;
            try {
                await navigator.clipboard.writeText(currentSelectedDetail.prompt_parameters.negative_prompt);
                showToast('Negative prompt copied to clipboard');
            } catch (error) {
                showToast(error.message, true);
            }
        });

        // Resize handle logic
        let isResizing = false;
        let startX = 0;
        let startWidth = 0;

        dom.previewResizeHandle.addEventListener('mousedown', e => {
            isResizing = true;
            startX = e.clientX;
            startWidth = state.previewWidth;
            dom.previewResizeHandle.classList.add('resizing');
            document.body.style.cursor = 'col-resize';
            document.body.style.userSelect = 'none';

            document.addEventListener('mousemove', handleResize);
            document.addEventListener('mouseup', stopResize);
        });

        function handleResize(e) {
            if (!isResizing) return;
            const dx = e.clientX - startX;
            let newWidth = startWidth - dx;

            // 1. If sidebar is open, check if resizing the preview panel leaves less than 450px for the grid.
            // If so, automatically collapse the sidebar! (But don't touch sidebarExplicitlyCollapsed)
            if (!state.sidebarCollapsed && newWidth > window.innerWidth - 250 - 450) {
                state.sidebarCollapsed = true;
                updateSidebarUI();
            }

            // 2. If sidebar is automatically collapsed (not explicitly collapsed by user),
            // check if shrinking the preview panel allows the sidebar to fit back with at least 450px grid width.
            // If so, automatically restore/expand the sidebar!
            if (state.sidebarCollapsed && !state.sidebarExplicitlyCollapsed && newWidth <= window.innerWidth - 250 - 450) {
                state.sidebarCollapsed = false;
                updateSidebarUI();
            }

            const currentSidebarWidth = state.sidebarCollapsed ? 0 : 250;
            const maxAllowed = window.innerWidth - currentSidebarWidth - 450;
            newWidth = Math.max(300, Math.min(maxAllowed, newWidth));

            state.previewWidth = newWidth;
            writeStoredPreference(storageKeys.previewWidth, newWidth);
            updateLayoutColumns();
        }

        function stopResize() {
            if (!isResizing) return;
            isResizing = false;
            dom.previewResizeHandle.classList.remove('resizing');
            document.body.style.cursor = '';
            document.body.style.userSelect = '';

            document.removeEventListener('mousemove', handleResize);
            document.removeEventListener('mouseup', stopResize);
        }

        // Sidebar Toggle click handler
        dom.btnToggleSidebar.addEventListener('click', () => {
            state.sidebarCollapsed = !state.sidebarCollapsed;
            state.sidebarExplicitlyCollapsed = state.sidebarCollapsed;
            writeStoredPreference(storageKeys.sidebarCollapsed, state.sidebarCollapsed);

            // If we are opening the sidebar and preview is visible,
            // we must make sure the middle pane has at least 450px of space.
            // If not, we push (reduce) the preview panel width!
            if (!state.sidebarCollapsed && state.showPreview) {
                const activeAsset = state.assets.find(item => item.id === state.activeAssetId);
                if (activeAsset) {
                    const requiredGallerySpace = 450;
                    const maxAllowedPreviewWidth = window.innerWidth - 250 - requiredGallerySpace;
                    if (state.previewWidth > maxAllowedPreviewWidth) {
                        state.previewWidth = Math.max(300, maxAllowedPreviewWidth);
                        writeStoredPreference(storageKeys.previewWidth, state.previewWidth);
                    }
                }
            }

            updateSidebarUI();
        });

        // Initialize sidebar and columns layout
        updateSidebarUI();
        setupInfiniteScroll();

        await loadMetadata({ includeFilters: true });
        await loadAssets();
    } catch (error) {
        dom.feedback.textContent = `Library could not be loaded: ${error.message}`;
        showToast(error.message, true);
    }
}

initialize();
