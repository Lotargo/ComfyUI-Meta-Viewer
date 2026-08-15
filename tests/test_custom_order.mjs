import test from 'node:test';
import assert from 'node:assert/strict';

import {
    normalizePreferences,
    parsePreferences,
} from '../app/static/js/preferences.js';

import {
    getCustomOrderKey,
    loadCustomOrder,
    saveCustomOrder,
    applyCustomOrder,
    CUSTOM_ORDER_STORAGE_KEY,
} from '../app/static/js/custom-order.js';

// Setup mock localStorage for Node.js test environment
const storageMap = new Map();
globalThis.localStorage = {
    getItem: key => (storageMap.has(key) ? storageMap.get(key) : null),
    setItem: (key, val) => storageMap.set(key, String(val)),
    removeItem: key => storageMap.delete(key),
    clear: () => storageMap.clear(),
};

test('custom sortKey persists in preferences', () => {
    const prefs = normalizePreferences({
        version: 2,
        sorting: {
            gallery: { key: 'custom', direction: 'desc' },
        },
    });
    assert.equal(prefs.sorting.gallery.key, 'custom');
});

test('custom sort key roundtrips through JSON serialization', () => {
    const raw = JSON.stringify({
        version: 2,
        sorting: {
            gallery: { key: 'custom', direction: 'desc' },
        },
    });
    const parsed = parsePreferences(raw);
    assert.equal(parsed.sorting.gallery.key, 'custom');
});

test('getCustomOrderKey normalizes folder, album, and media collections identically', () => {
    assert.equal(getCustomOrderKey({ type: 'folder', id: 1 }), 'folder:1');
    assert.equal(getCustomOrderKey({ type: 'album', id: 42 }), 'album:42');
    assert.equal(getCustomOrderKey({ type: 'media', id: null }), 'media:all');
    assert.equal(getCustomOrderKey({ type: 'collection', collection: 'all' }), 'media:all');
    assert.equal(getCustomOrderKey({ type: 'collection', collection: 'favorites' }), 'collection:favorites');
    assert.equal(getCustomOrderKey('all'), 'media:all');
    assert.equal(getCustomOrderKey('favorites'), 'collection:favorites');
});

test('saveCustomOrder and loadCustomOrder synchronize across collection descriptors', () => {
    localStorage.clear();
    const folderCollection = { type: 'folder', id: 5 };
    saveCustomOrder(folderCollection, [103, 101, 102]);

    assert.deepEqual(loadCustomOrder(folderCollection), [103, 101, 102]);
    assert.deepEqual(loadCustomOrder({ type: 'folder', id: 5 }), [103, 101, 102]);

    // Check media / all synchronization
    saveCustomOrder({ type: 'media', id: null }, [500, 400, 300]);
    assert.deepEqual(loadCustomOrder('all'), [500, 400, 300]);
    assert.deepEqual(loadCustomOrder({ type: 'collection', collection: 'all' }), [500, 400, 300]);
});

test('applyCustomOrder reorders items and prepends new incoming items to the top', () => {
    localStorage.clear();
    const collection = { type: 'folder', id: 1 };
    saveCustomOrder(collection, [20, 10, 30]);

    // Suppose newly generated image 40 arrives from server at the front: [40, 10, 20, 30]
    const items = [{ id: 40 }, { id: 10 }, { id: 20 }, { id: 30 }];
    const result = applyCustomOrder(items, collection);

    assert.equal(result.active, true);
    // 40 should be at the top, followed by the custom ordered [20, 10, 30]
    assert.deepEqual(items.map(i => i.id), [40, 20, 10, 30]);
});
