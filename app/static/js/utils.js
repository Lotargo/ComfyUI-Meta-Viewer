import { showToast, cacheBuster, dom } from './state.js';
import {
    getMetadataStringValue as metadataStringValue,
    getStringValue as stringValue,
} from './metadata-format.js';

export function escapeHtml(s) {
    if (s === null || s === undefined) return '<null>';
    const str = typeof s === 'object' ? JSON.stringify(s, null, 2) : String(s);
    return str.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

export function highlightText(text, terms = [], isExactMatch = false) {
    if (!terms || terms.length === 0) return escapeHtml(text);
    
    let html = escapeHtml(text);
    
    // Sort terms by length descending so longer terms are highlighted first
    const sortedTerms = [...terms].sort((a, b) => b.length - a.length);

    sortedTerms.forEach(term => {
        if (!term) return;
        const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
        const pattern = isExactMatch 
            ? `(?:^|\\b)(${escapedTerm})(?:\\b|$)`
            : `(${escapedTerm})`;
        
        // Use a regex to find matches, ignoring case. 
        // We use a placeholder so we don't double-highlight.
        const regex = new RegExp(pattern, 'gi');
        // This simple replace might replace inside existing <mark> tags if we're not careful.
        // A safer way for multiple terms is to split and map, but for simple use case, we do it carefully.
        html = html.replace(regex, '<mark class="search-highlight">$1</mark>');
    });

    // Fix any nested <mark> tags if they occurred
    html = html.replace(/<mark[^>]*><mark[^>]*>/g, '<mark class="search-highlight">');
    html = html.replace(/<\/mark><\/mark>/g, '</mark>');

    return html;
}

export function formatValue(v, terms = [], isExactMatch = false) {
    if (v === null || v === undefined) return '<null>';
    return highlightText(stringValue(v), terms, isExactMatch);
}

export function getStringValue(v) {
    return stringValue(v);
}

export function formatMetadataValue(key, value, terms = [], isExactMatch = false) {
    if (value === null || value === undefined) return '<null>';
    return highlightText(metadataStringValue(key, value), terms, isExactMatch);
}

export function getMetadataStringValue(key, value) {
    return metadataStringValue(key, value);
}

export function formatMediaCountLabel(loaded, total) {
    const safeLoaded = Math.max(0, loaded || 0);
    const safeTotal = Math.max(0, total || 0);
    if (!safeLoaded && !safeTotal) return '';
    if (!safeTotal || safeLoaded === safeTotal) {
        return `${safeLoaded} item${safeLoaded === 1 ? '' : 's'}`;
    }
    return `${safeLoaded} / ${safeTotal} loaded`;
}

export function thumbUrl(img) {
    return img.id ? `/api/thumbnail/${img.id}?t=${cacheBuster}` : (img.thumbnail || '');
}

export function imageRenderSignature(img) {
    return JSON.stringify([
        img.id ?? null,
        img.media_type || 'image',
        img.file_name || img.file || '',
        img.format || '',
        Array.isArray(img.size) ? img.size : null,
        img.mode || '',
        img.error || '',
        img.rating || 0,
        img.preview_status || '',
    ]);
}

export function originalUrl(img) {
    return img.id ? `/api/original/${img.id}?t=${cacheBuster}` : (img.thumbnail || '');
}

export function previewUrl(img) {
    return img.id ? `/api/preview/${img.id}?t=${cacheBuster}` : (img.thumbnail || '');
}

export function showLoading(msg) {
    dom.contentArea.innerHTML = `<div class="empty-state anim-fade-in"><div class="icon"><svg viewBox="0 0 24 24" width="48" height="48" stroke="var(--accent)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" class="anim-spin"><line x1="12" y1="2" x2="12" y2="6"></line><line x1="12" y1="18" x2="12" y2="22"></line><line x1="4.93" y1="4.93" x2="7.76" y2="7.76"></line><line x1="16.24" y1="16.24" x2="19.07" y2="19.07"></line><line x1="2" y1="12" x2="6" y2="12"></line><line x1="18" y1="12" x2="22" y2="12"></line><line x1="4.93" y1="19.07" x2="7.76" y2="16.24"></line><line x1="16.24" y1="7.76" x2="19.07" y2="4.93"></line></svg></div><div>${escapeHtml(msg)}</div></div>`;
}

export function showError(msg) {
    dom.contentArea.innerHTML = `<div class="empty-state anim-shake"><div class="icon"><svg viewBox="0 0 24 24" width="48" height="48" stroke="var(--red)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg></div><div>${escapeHtml(msg)}</div></div>`;
}

export async function copyText(text) {
    await navigator.clipboard.writeText(text);
    showToast('Copied!');
}

export function customAlert(title, message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <div class="modal-title">🔔 ${escapeHtml(title)}</div>
                <div class="modal-message">${escapeHtml(message)}</div>
                <div class="modal-actions">
                    <button class="btn btn-primary modal-ok-btn">OK</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.offsetHeight;
        overlay.classList.add('open');
        
        const close = () => {
            overlay.classList.remove('open');
            setTimeout(() => { overlay.remove(); resolve(); }, 250);
        };
        overlay.querySelector('.modal-ok-btn').addEventListener('click', close);
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(); });
    });
}

export function customConfirm(title, message) {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <div class="modal-title">❓ ${escapeHtml(title)}</div>
                <div class="modal-message">${escapeHtml(message)}</div>
                <div class="modal-actions">
                    <button class="btn btn-secondary modal-cancel-btn">Cancel</button>
                    <button class="btn btn-primary modal-ok-btn">Confirm</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        overlay.offsetHeight;
        overlay.classList.add('open');
        
        const close = (res) => {
            overlay.classList.remove('open');
            setTimeout(() => { overlay.remove(); resolve(res); }, 250);
        };
        overlay.querySelector('.modal-ok-btn').addEventListener('click', () => close(true));
        overlay.querySelector('.modal-cancel-btn').addEventListener('click', () => close(false));
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(false); });
    });
}

export function customPrompt(title, message, defaultValue = '') {
    return new Promise((resolve) => {
        const overlay = document.createElement('div');
        overlay.className = 'modal-overlay';
        overlay.innerHTML = `
            <div class="modal-content">
                <div class="modal-title">✏️ ${escapeHtml(title)}</div>
                <div class="modal-message">${escapeHtml(message)}</div>
                <input type="text" class="modal-input" value="${escapeHtml(defaultValue)}">
                <div class="modal-actions">
                    <button class="btn btn-secondary modal-cancel-btn">Cancel</button>
                    <button class="btn btn-primary modal-ok-btn">OK</button>
                </div>
            </div>
        `;
        document.body.appendChild(overlay);
        
        const input = overlay.querySelector('.modal-input');
        input.focus();
        input.select();
        overlay.offsetHeight;
        overlay.classList.add('open');
        
        const close = (res) => {
            overlay.classList.remove('open');
            setTimeout(() => { overlay.remove(); resolve(res); }, 250);
        };
        overlay.querySelector('.modal-ok-btn').addEventListener('click', () => close(input.value));
        overlay.querySelector('.modal-cancel-btn').addEventListener('click', () => close(null));
        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') close(input.value);
            if (e.key === 'Escape') close(null);
        });
        overlay.addEventListener('click', (e) => { if (e.target === overlay) close(null); });
    });
}
