export const PREFERENCES_VERSION = 2;
export const PREFERENCES_STORAGE_KEY = 'cmv_preferences_v2';
export const LEGACY_PREFERENCES_STORAGE_KEY = 'cmv_preferences';

const VIEW_MODES = new Set(['gallery', 'list', 'upload']);
const SIDEBAR_TABS = new Set(['folders', 'albums', 'images']);
const COLLECTION_TYPES = new Set(['folder', 'album']);
const FOLDER_VIEW_MODES = new Set(['list', 'tile']);
const META_TABS = new Set(['summary', 'workflow', 'raw']);
const SORT_DIRECTIONS = new Set(['asc', 'desc']);
const IMAGE_SORT_KEYS = new Set(['name', 'date', 'size', 'type']);
const FOLDER_SORT_KEYS = new Set(['name', 'scanned_at', 'image_count']);
const ALBUM_SORT_KEYS = new Set(['name', 'updated_at', 'asset_count']);

function isRecord(value) {
    return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

function enumValue(value, allowed, fallback) {
    return allowed.has(value) ? value : fallback;
}

function booleanValue(value, fallback) {
    return typeof value === 'boolean' ? value : fallback;
}

function selectedFolderId(value) {
    return Number.isInteger(value) && value > 0 ? value : null;
}

function selectedCollection(value, legacyFolderId = null) {
    const legacyId = selectedFolderId(legacyFolderId);
    if (!isRecord(value)) return { type: 'folder', id: legacyId };
    const type = enumValue(value.type, COLLECTION_TYPES, 'folder');
    return { type, id: selectedFolderId(value.id) };
}

function sidebarWidth(value) {
    if (!Number.isFinite(value)) return 360;
    return Math.min(500, Math.max(280, Math.round(value)));
}

function ratingFilter(value) {
    return Number.isInteger(value) && value >= 0 && value <= 5 ? value : null;
}

export function createDefaultPreferences() {
    return {
        version: PREFERENCES_VERSION,
        navigation: {
            selectedCollection: { type: 'folder', id: null },
            selectedFolderId: null,
            viewMode: 'gallery',
            sidebarTab: 'images',
        },
        layout: {
            sidebarWidth: 360,
            sidebarCollapsed: false,
            foldersViewMode: 'list',
            albumsViewMode: 'list',
            lightboxMetaOpen: true,
            metadataTab: 'summary',
        },
        sorting: {
            gallery: { key: 'date', direction: 'desc' },
            images: { key: 'date', direction: 'desc' },
            folders: { key: 'scanned_at', direction: 'desc' },
            albums: { key: 'name', direction: 'asc' },
        },
        filters: {
            rating: null,
        },
        searchSettings: {
            exactMatch: false,
            fields: {
                positive_prompt: true,
                negative_prompt: true,
                model: true,
                sampler: true,
                resolution: true,
            },
        },
    };
}

export function normalizePreferences(value) {
    const defaults = createDefaultPreferences();
    const source = isRecord(value) ? value : {};
    const isCurrentVersion = source.version === PREFERENCES_VERSION;
    const isLegacyVersion = source.version === undefined;
    const current = isCurrentVersion ? source : {};
    const navigation = isRecord(current.navigation) ? current.navigation : {};
    const layout = isRecord(current.layout) ? current.layout : {};
    const sorting = isRecord(current.sorting) ? current.sorting : {};
    const gallerySort = isRecord(sorting.gallery) ? sorting.gallery : {};
    const imagesSort = isRecord(sorting.images) ? sorting.images : {};
    const foldersSort = isRecord(sorting.folders) ? sorting.folders : {};
    const albumsSort = isRecord(sorting.albums) ? sorting.albums : {};
    const filters = isRecord(current.filters) ? current.filters : {};
    const search = isCurrentVersion || isLegacyVersion
        ? (isRecord(source.searchSettings) ? source.searchSettings : {})
        : {};
    const searchFields = isRecord(search.fields) ? search.fields : {};

    const collection = selectedCollection(navigation.selectedCollection, navigation.selectedFolderId);
    return {
        version: PREFERENCES_VERSION,
        navigation: {
            selectedCollection: collection,
            selectedFolderId: collection.type === 'folder' ? collection.id : null,
            viewMode: enumValue(navigation.viewMode, VIEW_MODES, defaults.navigation.viewMode),
            sidebarTab: enumValue(navigation.sidebarTab, SIDEBAR_TABS, defaults.navigation.sidebarTab),
        },
        layout: {
            sidebarWidth: sidebarWidth(layout.sidebarWidth),
            sidebarCollapsed: booleanValue(layout.sidebarCollapsed, defaults.layout.sidebarCollapsed),
            foldersViewMode: enumValue(layout.foldersViewMode, FOLDER_VIEW_MODES, defaults.layout.foldersViewMode),
            albumsViewMode: enumValue(layout.albumsViewMode, FOLDER_VIEW_MODES, defaults.layout.albumsViewMode),
            lightboxMetaOpen: booleanValue(layout.lightboxMetaOpen, defaults.layout.lightboxMetaOpen),
            metadataTab: enumValue(layout.metadataTab, META_TABS, defaults.layout.metadataTab),
        },
        sorting: {
            gallery: {
                key: enumValue(gallerySort.key, IMAGE_SORT_KEYS, defaults.sorting.gallery.key),
                direction: enumValue(gallerySort.direction, SORT_DIRECTIONS, defaults.sorting.gallery.direction),
            },
            images: {
                key: enumValue(imagesSort.key, IMAGE_SORT_KEYS, defaults.sorting.images.key),
                direction: enumValue(imagesSort.direction, SORT_DIRECTIONS, defaults.sorting.images.direction),
            },
            folders: {
                key: enumValue(foldersSort.key, FOLDER_SORT_KEYS, defaults.sorting.folders.key),
                direction: enumValue(foldersSort.direction, SORT_DIRECTIONS, defaults.sorting.folders.direction),
            },
            albums: {
                key: enumValue(albumsSort.key, ALBUM_SORT_KEYS, defaults.sorting.albums.key),
                direction: enumValue(albumsSort.direction, SORT_DIRECTIONS, defaults.sorting.albums.direction),
            },
        },
        filters: {
            rating: ratingFilter(filters.rating),
        },
        searchSettings: {
            exactMatch: booleanValue(search.exactMatch, defaults.searchSettings.exactMatch),
            fields: {
                positive_prompt: booleanValue(searchFields.positive_prompt, defaults.searchSettings.fields.positive_prompt),
                negative_prompt: booleanValue(searchFields.negative_prompt, defaults.searchSettings.fields.negative_prompt),
                model: booleanValue(searchFields.model, defaults.searchSettings.fields.model),
                sampler: booleanValue(searchFields.sampler, defaults.searchSettings.fields.sampler),
                resolution: booleanValue(searchFields.resolution, defaults.searchSettings.fields.resolution),
            },
        },
    };
}

export function parsePreferences(serialized) {
    if (typeof serialized !== 'string' || !serialized) return createDefaultPreferences();
    try {
        return normalizePreferences(JSON.parse(serialized));
    } catch (_error) {
        return createDefaultPreferences();
    }
}
