import test from 'node:test';
import assert from 'node:assert/strict';

import {
    normalizePreferences,
    parsePreferences,
} from '../app/static/js/preferences.js';

import {
    getCustomOrderKey,
    loadCustomOrder,
    serverScopeForCollection,
    ensureServerCustomOrder,
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

test('serverScopeForCollection maps descriptors to server scopes', () => {
    assert.equal(serverScopeForCollection({ type: 'folder', id: 5 }), 'folder:5');
    assert.equal(serverScopeForCollection({ type: 'media', id: null }), 'media:all');
    assert.equal(serverScopeForCollection({ type: 'collection', collection: 'all' }), 'media:all');
    assert.equal(serverScopeForCollection({ type: 'collection', collection: 'favorites' }), 'collection:favorites');
    // Albums persist via the album reorder endpoint, never via scopes.
    assert.equal(serverScopeForCollection({ type: 'album', id: 42 }), null);
});

test('ensureServerCustomOrder migrates a local snapshot once, then retires it', async () => {
    localStorage.clear();
    localStorage.setItem(CUSTOM_ORDER_STORAGE_KEY, JSON.stringify({ 'folder:5': [103, 101, 102] }));

    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({ url, method: options?.method || 'GET', body: options?.body });
        if (url.startsWith('/api/custom-order?')) {
            return { ok: true, json: async () => ({ scope: 'folder:5', image_ids: [], positioned: 0, unpositioned: 3 }) };
        }
        return { ok: true, json: async () => ({ ok: true }) };
    };

    const migrated = await ensureServerCustomOrder({ type: 'folder', id: 5 });
    assert.equal(migrated, true);
    const put = calls.find(call => call.method === 'PUT');
    assert.ok(put, 'expected a bulk PUT migration');
    assert.deepEqual(JSON.parse(put.body), { scope: 'folder:5', ordered_ids: [103, 101, 102] });
    // Local snapshot retired after migration.
    assert.equal(loadCustomOrder({ type: 'folder', id: 5 }), null);

    const second = await ensureServerCustomOrder({ type: 'folder', id: 5 });
    assert.equal(second, false);
    assert.equal(calls.filter(call => call.method === 'PUT').length, 1);
});

test('ensureServerCustomOrder defers to existing server data', async () => {
    localStorage.clear();
    localStorage.setItem(CUSTOM_ORDER_STORAGE_KEY, JSON.stringify({ 'folder:7': [201, 202] }));

    const calls = [];
    globalThis.fetch = async url => {
        calls.push(url);
        return { ok: true, json: async () => ({ scope: 'folder:7', image_ids: [202, 201], positioned: 2, unpositioned: 0 }) };
    };

    const migrated = await ensureServerCustomOrder({ type: 'folder', id: 7 });
    assert.equal(migrated, false);
    assert.ok(calls.every(url => !url.startsWith('/api/custom-order') || url.includes('?')), 'no PUT expected');
    // Stale local snapshot retired in favor of the server.
    assert.equal(loadCustomOrder({ type: 'folder', id: 7 }), null);
});
