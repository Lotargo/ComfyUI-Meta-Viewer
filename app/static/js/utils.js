import { showToast } from './state.js';

export function escapeHtml(s) {
    if (s === null || s === undefined) return '<null>';
    const str = typeof s === 'object' ? JSON.stringify(s, null, 2) : String(s);
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function formatValue(v) {
    if (v === null || v === undefined) return '<null>';
    if (typeof v === 'object') return escapeHtml(JSON.stringify(v, null, 2));
    return escapeHtml(String(v));
}

export function getStringValue(v) {
    if (v === null || v === undefined) return '';
    if (typeof v === 'object') return JSON.stringify(v, null, 2);
    return String(v);
}

export function thumbUrl(img) {
    return img.id ? `/api/thumbnail/${img.id}` : (img.thumbnail || '');
}

export function originalUrl(img) {
    return img.id ? `/api/original/${img.id}` : (img.thumbnail || '');
}

export function showLoading(msg) {
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `<div class="empty-state anim-fade-in"><div class="icon">&#8987;</div><div>${escapeHtml(msg)}</div></div>`;
}

export function showError(msg) {
    const contentArea = document.getElementById('content-area');
    contentArea.innerHTML = `<div class="empty-state anim-shake"><div class="icon">&#9888;</div><div>${escapeHtml(msg)}</div></div>`;
}

export async function copyText(text) {
    await navigator.clipboard.writeText(text);
    showToast('Copied!');
}
