import test from 'node:test';
import assert from 'node:assert/strict';

import {
    normalizePreferences,
    parsePreferences,
} from '../app/static/js/preferences.js';

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
