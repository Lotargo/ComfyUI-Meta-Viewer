/**
 * Server-side custom sort order for ComfyUI Meta Viewer.
 *
 * Drag-and-drop positions live in the `item_positions` table (one scope per
 * view: 'folder:<id>', 'media:all', 'collection:<id>') and are served via
 * sort_by=custom. Albums keep their own album_images.position mechanism.
 *
 * The localStorage snapshot format below exists only to migrate orders that
 * were saved by older client versions (one PUT per scope, then retired).
 */

export const CUSTOM_ORDER_STORAGE_KEY = 'cmv_custom_order';
const LEGACY_GALLERY_ORDER_KEY = 'cmv_gallery_order';
const LEGACY_LIBRARY_ORDER_KEY = 'cmv_library_order';
const MIGRATED_SCOPES_KEY = 'cmv_custom_order_migrated';

/**
 * Normalizes a collection descriptor to a unified storage key.
 * Supports:
 * - { type: 'folder', id: 1 } -> 'folder:1'
 * - { type: 'album', id: 2 } -> 'album:2'
 * - { type: 'media', id: null } -> 'media:all'
 * - { type: 'collection', collection: 'all' } -> 'media:all'
 * - { collection: 'favorites' } -> 'collection:favorites'
 * - string 'all' | 'favorites' -> 'media:all' | 'collection:favorites'
 */
export function getCustomOrderKey(collection) {
    if (!collection) return 'media:all';
    if (typeof collection === 'string') {
        return collection === 'all' ? 'media:all' : `collection:${collection}`;
    }
    if (collection.type === 'album' && collection.id) {
        return `album:${collection.id}`;
    }
    if (collection.type === 'folder' && collection.id) {
        return `folder:${collection.id}`;
    }
    if (collection.type === 'media' || collection.collection === 'all' || (collection.type === 'folder' && collection.id === null)) {
        return 'media:all';
    }
    if (collection.collection) {
        return `collection:${collection.collection}`;
    }
    return `${collection.type || 'media'}:${collection.id ?? 'all'}`;
}

export function loadAllCustomOrders() {
    try {
        const stored = JSON.parse(localStorage.getItem(CUSTOM_ORDER_STORAGE_KEY));
        if (stored && typeof stored === 'object') return stored;
    } catch (_error) {
        // storage unreadable or unavailable
    }
    // Fallback: migrate from legacy keys if available
    try {
        const legacyGallery = JSON.parse(localStorage.getItem(LEGACY_GALLERY_ORDER_KEY)) || {};
        const legacyLibrary = JSON.parse(localStorage.getItem(LEGACY_LIBRARY_ORDER_KEY)) || {};
        return { ...legacyGallery, ...legacyLibrary };
    } catch (_error) {
        return {};
    }
}

export function loadCustomOrder(collection) {
    const orders = loadAllCustomOrders();
    const key = getCustomOrderKey(collection);
    return orders[key] || null;
}

function dropLocalOrder(key) {
    try {
        const orders = loadAllCustomOrders();
        if (!(key in orders)) return;
        delete orders[key];
        const payload = JSON.stringify(orders);
        localStorage.setItem(CUSTOM_ORDER_STORAGE_KEY, payload);
        localStorage.setItem(LEGACY_GALLERY_ORDER_KEY, payload);
        localStorage.setItem(LEGACY_LIBRARY_ORDER_KEY, payload);
    } catch (_error) {
        // storage quota exceeded or storage unavailable
    }
}

/**
 * Maps a collection descriptor to a server item_positions scope.
 * Returns null for albums (they persist via POST /api/albums/{id}/reorder).
 */
export function serverScopeForCollection(collection) {
    const key = getCustomOrderKey(collection);
    if (key.startsWith('album:')) return null;
    if (key === 'collection:all') return 'media:all';
    return key;
}

function loadMigratedScopes() {
    try {
        const stored = JSON.parse(localStorage.getItem(MIGRATED_SCOPES_KEY));
        if (stored && typeof stored === 'object') return stored;
    } catch (_error) {
        // storage unreadable or unavailable
    }
    return {};
}

function markScopeMigrated(scope) {
    try {
        const migrated = loadMigratedScopes();
        migrated[scope] = true;
        localStorage.setItem(MIGRATED_SCOPES_KEY, JSON.stringify(migrated));
    } catch (_error) {
        // storage quota exceeded or storage unavailable
    }
}

async function readJsonSafe(response) {
    try {
        return await response.json();
    } catch (_error) {
        return {};
    }
}

/**
 * One-time migration of a pre-server localStorage order into item_positions.
 * Returns true when the caller should (re)load the list afterwards.
 * Server data always wins over the local snapshot on conflict.
 */
export async function ensureServerCustomOrder(collection) {
    const scope = serverScopeForCollection(collection);
    if (!scope) return false;
    if (loadMigratedScopes()[scope]) return false;

    const key = getCustomOrderKey(collection);
    let local = loadCustomOrder(collection);
    if (scope === 'media:all' && (!local || local.length < 2)) {
        // The Viewer ('media:all') and the Library ('collection:all') used
        // separate keys for the same view in some client versions.
        const twin = loadAllCustomOrders()['collection:all'];
        if (twin && twin.length >= 2) local = twin;
    }

    let serverState = null;
    try {
        const response = await fetch(`/api/custom-order?scope=${encodeURIComponent(scope)}`);
        if (response.ok) serverState = await readJsonSafe(response);
    } catch (_error) {
        return false; // offline or unreachable — retry on the next load
    }
    if (!serverState) return false;

    if ((serverState.positioned || 0) > 0) {
        // Server already owns this scope: retire the local snapshot.
        dropLocalOrder(key);
        if (scope === 'media:all') dropLocalOrder('collection:all');
        markScopeMigrated(scope);
        return false;
    }
    if (!local || local.length < 2) {
        markScopeMigrated(scope);
        return false;
    }
    try {
        const response = await fetch('/api/custom-order', {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scope, ordered_ids: local }),
        });
        if (!response.ok) return false; // retry on the next load
    } catch (_error) {
        return false;
    }
    dropLocalOrder(key);
    if (scope === 'media:all') dropLocalOrder('collection:all');
    markScopeMigrated(scope);
    return true;
}

/**
 * Persists one drag-and-drop: places imageId between the visible neighbors
 * (null = view edge). Throws on failure so the caller can toast + resync.
 */
export async function persistCustomOrderMove(scope, imageId, beforeId, afterId) {
    const response = await fetch('/api/custom-order/move', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            scope,
            image_id: imageId,
            before_id: beforeId ?? null,
            after_id: afterId ?? null,
        }),
    });
    const data = await readJsonSafe(response);
    if (!response.ok || data.error) {
        throw new Error(data.error || `${response.status} ${response.statusText}`);
    }
    return data;
}
