/**
 * Shared custom sort order module for ComfyUI Meta Viewer.
 * Keeps consistent ordering across Gallery, Sidebar, and Library views.
 */

export const CUSTOM_ORDER_STORAGE_KEY = 'cmv_custom_order';
const LEGACY_GALLERY_ORDER_KEY = 'cmv_gallery_order';
const LEGACY_LIBRARY_ORDER_KEY = 'cmv_library_order';

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

export function saveAllCustomOrders(orders) {
    try {
        localStorage.setItem(CUSTOM_ORDER_STORAGE_KEY, JSON.stringify(orders));
        // Keep legacy keys in sync for backward compatibility
        localStorage.setItem(LEGACY_GALLERY_ORDER_KEY, JSON.stringify(orders));
        localStorage.setItem(LEGACY_LIBRARY_ORDER_KEY, JSON.stringify(orders));
    } catch (_error) {
        // storage quota exceeded or storage unavailable
    }
}

export function loadCustomOrder(collection) {
    const orders = loadAllCustomOrders();
    const key = getCustomOrderKey(collection);
    return orders[key] || null;
}

export function saveCustomOrder(collection, orderIds) {
    const orders = loadAllCustomOrders();
    const key = getCustomOrderKey(collection);
    orders[key] = [...orderIds].map(Number).filter(id => Number.isInteger(id) && id > 0);
    saveAllCustomOrders(orders);
}

/**
 * Reorders an array of items in place according to the saved custom order.
 * - Any newly generated or scanned items not in `saved` are placed at the TOP.
 * - Paginated older items are placed at the BOTTOM.
 * - Items in `saved` follow their exact saved order.
 */
export function applyCustomOrder(items, collection, { idField = 'id' } = {}) {
    if (!Array.isArray(items) || items.length < 2) {
        return { active: false, count: items ? items.length : 0 };
    }
    const saved = loadCustomOrder(collection);
    if (!saved || saved.length < 2) {
        return { active: false, count: items.length };
    }

    const itemMap = new Map();
    for (const item of items) {
        const id = Number(item?.[idField]);
        if (id) itemMap.set(id, item);
    }

    const savedSet = new Set(saved.map(Number));
    const newItemsAtTop = [];
    const newItemsAtBottom = [];

    const firstSavedIdx = items.findIndex(item => savedSet.has(Number(item?.[idField])));
    items.forEach((item, idx) => {
        const id = Number(item?.[idField]);
        if (!savedSet.has(id)) {
            if (firstSavedIdx === -1 || idx < firstSavedIdx) {
                newItemsAtTop.push(item);
            } else {
                newItemsAtBottom.push(item);
            }
        }
    });

    const reordered = [];
    for (const id of saved) {
        const numId = Number(id);
        if (itemMap.has(numId)) {
            reordered.push(itemMap.get(numId));
            itemMap.delete(numId);
        }
    }

    items.length = 0;
    items.push(...newItemsAtTop, ...reordered, ...newItemsAtBottom);

    return { active: true, count: items.length };
}
