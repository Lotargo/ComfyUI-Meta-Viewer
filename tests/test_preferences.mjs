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
            selectedFolderId: 42,
            viewMode: 'list',
            sidebarTab: 'folders',
        },
        layout: {
            sidebarWidth: 900,
            sidebarCollapsed: true,
            foldersViewMode: 'tile',
            lightboxMetaOpen: false,
            metadataTab: 'raw',
        },
        sorting: {
            gallery: { key: 'name', direction: 'asc' },
            images: { key: 'invalid', direction: 'asc' },
            folders: { key: 'image_count', direction: 'invalid' },
        },
        searchSettings: {
            exactMatch: true,
            fields: { model: false },
        },
    });

    assert.equal(preferences.navigation.selectedFolderId, 42);
    assert.equal(preferences.navigation.viewMode, 'list');
    assert.equal(preferences.navigation.sidebarTab, 'folders');
    assert.equal(preferences.layout.sidebarWidth, 500);
    assert.equal(preferences.layout.sidebarCollapsed, true);
    assert.equal(preferences.layout.foldersViewMode, 'tile');
    assert.equal(preferences.layout.lightboxMetaOpen, false);
    assert.equal(preferences.layout.metadataTab, 'raw');
    assert.deepEqual(preferences.sorting.gallery, { key: 'name', direction: 'asc' });
    assert.deepEqual(preferences.sorting.images, { key: 'date', direction: 'asc' });
    assert.deepEqual(preferences.sorting.folders, { key: 'image_count', direction: 'desc' });
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
    state.setSortKey('name');
    state.setSortDir('asc');
    state.setLightboxMetaOpen(false);
    state.setMetadataTab('workflow');
    state.setImages([{ id: 1 }]);
    state.setCurrentPage(9);
    state.saveState();

    assert.ok(localStorage.getItem(PREFERENCES_STORAGE_KEY));

    state.resetRuntimeState();
    state.loadState();

    assert.equal(state.currentFolderId, 77);
    assert.equal(state.viewMode, 'list');
    assert.equal(state.galleryActive, false);
    assert.equal(state.activeSidebarTab, 'folders');
    assert.equal(state.sidebarWidth, 444);
    assert.equal(state.sidebarCollapsed, true);
    assert.equal(state.foldersViewMode, 'tile');
    assert.equal(state.sortKey, 'name');
    assert.equal(state.sortDir, 'asc');
    assert.equal(state.lightboxMetaOpen, false);
    assert.equal(state.metadataTab, 'workflow');
    assert.deepEqual(state.images, []);
    assert.equal(state.currentPage, 0);
});
