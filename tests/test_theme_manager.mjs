import test from 'node:test';
import assert from 'node:assert/strict';

import {
    getStoredTheme,
    resolveEffectiveTheme,
    applyTheme,
    updateThemeUI,
} from '../app/static/js/theme-manager.js';

// Setup mock localStorage & DOM for Node.js test environment
const storageMap = new Map();
globalThis.localStorage = {
    getItem: key => (storageMap.has(key) ? storageMap.get(key) : null),
    setItem: (key, val) => storageMap.set(key, String(val)),
    removeItem: key => storageMap.delete(key),
    clear: () => storageMap.clear(),
};

globalThis.document = {
    documentElement: {
        setAttribute: (key, val) => {
            document.documentElement[key] = val;
        },
        getAttribute: key => document.documentElement[key] || null,
    },
    querySelectorAll: () => [],
    addEventListener: () => {},
};

globalThis.window = {
    matchMedia: query => ({
        matches: query.includes('dark'),
        addEventListener: () => {},
    }),
    dispatchEvent: () => {},
};

globalThis.CustomEvent = class CustomEvent {
    constructor(name, detail) {
        this.name = name;
        this.detail = detail;
    }
};

test('getStoredTheme defaults to dark', () => {
    localStorage.clear();
    assert.equal(getStoredTheme(), 'dark');
});

test('getStoredTheme retrieves valid stored themes', () => {
    localStorage.setItem('cmv_theme', 'light');
    assert.equal(getStoredTheme(), 'light');

    localStorage.setItem('cmv_theme', 'strawberry');
    assert.equal(getStoredTheme(), 'strawberry');

    localStorage.setItem('cmv_theme', 'system');
    assert.equal(getStoredTheme(), 'system');
});

test('getStoredTheme falls back on corrupted or unknown theme names', () => {
    localStorage.setItem('cmv_theme', 'invalid-theme-123');
    assert.equal(getStoredTheme(), 'dark');
});

test('resolveEffectiveTheme returns the direct theme or resolves system', () => {
    assert.equal(resolveEffectiveTheme('light'), 'light');
    assert.equal(resolveEffectiveTheme('strawberry'), 'strawberry');
    assert.equal(resolveEffectiveTheme('dark'), 'dark');
    assert.equal(resolveEffectiveTheme('system'), 'dark'); // based on mock matchMedia
});

test('applyTheme sets data-theme attribute on documentElement and saves to localStorage', () => {
    applyTheme('strawberry');
    assert.equal(document.documentElement.getAttribute('data-theme'), 'strawberry');
    assert.equal(localStorage.getItem('cmv_theme'), 'strawberry');

    applyTheme('light');
    assert.equal(document.documentElement.getAttribute('data-theme'), 'light');
    assert.equal(localStorage.getItem('cmv_theme'), 'light');
});
