import test from 'node:test';
import assert from 'node:assert/strict';

import {
    PREFERENCES_VERSION,
    PREFERENCES_STORAGE_KEY,
    createDefaultPreferences,
    normalizePreferences,
    parsePreferences,
} from '../app/static/js/preferences.js';

class MemoryStorage {
    constructor() {
        this.values = new Map();
    }

    getItem(key) {
        return this.values.has(key) ? this.values.get(key) : null;
    }

    setItem(key, value) {
        this.values.set(key, String(value));
    }

    removeItem(key) {
        this.values.delete(key);
    }

    clear() {
        this.values.clear();
    }
}

test('invalid or corrupted preferences fall back to independent defaults', () => {
    const corrupted = parsePreferences('{not-json');
    const defaults = createDefaultPreferences();
    assert.deepEqual(corrupted, defaults);

    corrupted.searchSettings.fields.model = false;
    assert.equal(createDefaultPreferences().searchSettings.fields.model, true);
});

test('current preferences are validated field by field', () => {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION,
        navigation: {
            selectedCollection: { type: 'album', id: 42 },
            viewMode: 'list',
            sidebarTab: 'albums',
        },
        layout: {
            sidebarWidth: 900,
            sidebarCollapsed: true,
            foldersViewMode: 'tile',
            albumsViewMode: 'tile',
            lightboxMetaOpen: false,
            metadataTab: 'raw',
        },
        sorting: {
            gallery: { key: 'name', direction: 'asc' },
            images: { key: 'invalid', direction: 'asc' },
            folders: { key: 'image_count', direction: 'invalid' },
            albums: { key: 'asset_count', direction: 'desc' },
        },
        filters: {
            rating: 4,
            mediaTypes: { images: false, videos: true },
        },
        searchSettings: {
            exactMatch: true,
            fields: { model: false },
        },
    });

    assert.deepEqual(preferences.navigation.selectedCollection, { type: 'album', id: 42 });
    assert.equal(preferences.navigation.selectedFolderId, null);
    assert.equal(preferences.navigation.viewMode, 'list');
    assert.equal(preferences.navigation.sidebarTab, 'albums');
    assert.equal(preferences.layout.sidebarWidth, 500);
    assert.equal(preferences.layout.sidebarCollapsed, true);
    assert.equal(preferences.layout.foldersViewMode, 'tile');
    assert.equal(preferences.layout.albumsViewMode, 'tile');
    assert.equal(preferences.layout.lightboxMetaOpen, false);
    assert.equal(preferences.layout.metadataTab, 'raw');
    assert.deepEqual(preferences.sorting.gallery, { key: 'name', direction: 'asc' });
    assert.deepEqual(preferences.sorting.images, { key: 'date', direction: 'asc' });
    assert.deepEqual(preferences.sorting.folders, { key: 'image_count', direction: 'desc' });
    assert.deepEqual(preferences.sorting.albums, { key: 'asset_count', direction: 'desc' });
    assert.equal(preferences.filters.rating, 4);
    assert.deepEqual(preferences.filters.mediaTypes, { images: false, videos: true });
    assert.equal(preferences.searchSettings.exactMatch, true);
    assert.equal(preferences.searchSettings.fields.model, false);
    assert.equal(preferences.searchSettings.fields.positive_prompt, true);
});

test('legacy search preferences migrate without restoring unsafe runtime state', () => {
    const preferences = normalizePreferences({
        currentFolderId: 999,
        images: [{ id: 1 }],
        lightboxIndex: 17,
        searchSettings: {
            exactMatch: true,
            fields: { sampler: false },
        },
    });

    assert.equal(preferences.navigation.selectedFolderId, null);
    assert.equal(preferences.navigation.viewMode, 'gallery');
    assert.equal(preferences.searchSettings.exactMatch, true);
    assert.equal(preferences.searchSettings.fields.sampler, false);
});

test('unknown future schemas are ignored safely', () => {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION + 1,
        navigation: { selectedFolderId: 50, viewMode: 'upload' },
        layout: { sidebarCollapsed: true },
        searchSettings: { exactMatch: true },
    });

    assert.deepEqual(preferences, createDefaultPreferences());
});

test('invalid rating filters fall back to all ratings', () => {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION,
        filters: { rating: 9 },
    });
    assert.equal(preferences.filters.rating, null);
});

test('media type filters always keep a visible type', () => {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION,
        filters: { mediaTypes: { images: false, videos: false } },
    });
    assert.deepEqual(preferences.filters.mediaTypes, { images: true, videos: true });
});

test('the global media collection is a persistent navigation target', () => {
    const preferences = normalizePreferences({
        version: PREFERENCES_VERSION,
        navigation: {
            selectedCollection: { type: 'media', id: 99 },
            sidebarTab: 'images',
        },
    });
    assert.deepEqual(preferences.navigation.selectedCollection, { type: 'media', id: null });
    assert.equal(preferences.navigation.selectedFolderId, null);
});

test('state persistence restores stable preferences but not runtime collections', async () => {
    globalThis.document = { getElementById: () => null };
    globalThis.localStorage = new MemoryStorage();
    globalThis.sessionStorage = new MemoryStorage();
    const state = await import(`../app/static/js/state.js?state-test=${Date.now()}`);

    state.setCurrentFolderId(77);
    state.setViewModeValue('list');
    state.setGalleryActive(false);
    state.setActiveSidebarTab('folders');
    state.setSidebarWidth(444);
    state.setSidebarCollapsed(true);
    state.setFoldersViewMode('tile');
    state.setAlbumsViewMode('tile');
    state.setSortKey('name');
    state.setSortDir('asc');
    state.setRatingFilter(3);
    state.setMediaTypeFilter({ images: false, videos: true });
    state.setLightboxMetaOpen(false);
    state.setMetadataTab('workflow');
    state.setImages([{ id: 1 }]);
    state.setCurrentPage(9);
    state.saveState();

    assert.ok(localStorage.getItem(PREFERENCES_STORAGE_KEY));

    state.resetRuntimeState();
    state.loadState();

    assert.equal(state.currentFolderId, 77);
    assert.deepEqual(state.currentCollection, { type: 'folder', id: 77, name: '' });
    assert.equal(state.viewMode, 'list');
    assert.equal(state.galleryActive, false);
    assert.equal(state.activeSidebarTab, 'folders');
    assert.equal(state.sidebarWidth, 444);
    assert.equal(state.sidebarCollapsed, true);
    assert.equal(state.foldersViewMode, 'tile');
    assert.equal(state.albumsViewMode, 'tile');
    assert.equal(state.sortKey, 'name');
    assert.equal(state.sortDir, 'asc');
    assert.equal(state.ratingFilter, 3);
    assert.deepEqual(state.mediaTypeFilter, { images: false, videos: true });
    assert.equal(state.lightboxMetaOpen, false);
    assert.equal(state.metadataTab, 'workflow');
    assert.deepEqual(state.images, []);
    assert.equal(state.currentPage, 0);

    state.setCurrentCollection({ type: 'album', id: 91, name: 'Runtime-only name' });
    state.setActiveSidebarTab('albums');
    state.setAlbums([{ id: 91, name: 'Persistent array reference' }]);
    state.setAlbums(state.albums);
    assert.equal(state.albums.length, 1);
    state.saveState();
    state.resetRuntimeState();
    state.loadState();
    assert.deepEqual(state.currentCollection, { type: 'album', id: 91, name: '' });
    assert.equal(state.currentFolderId, null);
    assert.equal(state.activeSidebarTab, 'albums');

    localStorage.setItem('cmv_preferences', 'legacy');
    localStorage.setItem('cmv_ai_connected_cli_types_v1', '["opencode"]');
    localStorage.setItem('cmv_ai_model_catalog_v1', '{}');
    sessionStorage.setItem('cmv_state', 'legacy');
    state.clearStoredPreferences();
    assert.equal(localStorage.getItem(PREFERENCES_STORAGE_KEY), null);
    assert.equal(localStorage.getItem('cmv_preferences'), null);
    assert.equal(localStorage.getItem('cmv_ai_connected_cli_types_v1'), null);
    assert.equal(localStorage.getItem('cmv_ai_model_catalog_v1'), null);
    assert.equal(sessionStorage.getItem('cmv_state'), null);
});
