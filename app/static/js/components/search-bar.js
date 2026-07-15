/**
 * Search bar component
 */

import { images, sidebarImages } from '../state.js';

export function initSearch() {
    const input = document.getElementById('search-input');
    if (!input) return;

    input.addEventListener('input', onSearch);
    input.addEventListener('keydown', onKeydown);
}

function getMatchPredicate(query) {
    if (!query) return () => true;
    
    // Split query by commas for tags, or spaces if no commas
    let terms = [];
    if (query.includes(',')) {
        terms = query.toLowerCase().split(',').map(t => t.trim()).filter(Boolean);
    } else {
        terms = query.toLowerCase().split(' ').map(t => t.trim()).filter(Boolean);
    }

    return (img) => {
        if (!img) return false;
        const searchString = [
            img.file_name,
            img.format,
            img.prompt_parameters?.positive_prompt,
            img.prompt_parameters?.negative_prompt,
            img.prompt_parameters?.model,
            img.prompt_parameters?.sampler
        ].filter(Boolean).join(' ').toLowerCase();

        // All terms must be found in the search string (AND logic)
        return terms.every(term => searchString.includes(term));
    };
}

function onSearch(e) {
    const query = e.target.value.trim();
    const predicate = getMatchPredicate(query);

    // Filter gallery cards
    document.querySelectorAll('.gallery-card').forEach(card => {
        const idx = parseInt(card.dataset.index);
        const img = images[idx];
        if (img && predicate(img)) {
            card.style.display = '';
        } else {
            card.style.display = 'none';
        }
    });

    // Filter sidebar items
    document.querySelectorAll('.image-item').forEach(item => {
        const idx = parseInt(item.dataset.index);
        const img = sidebarImages[idx];
        if (img && predicate(img)) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

function onKeydown(e) {
    if (e.key === 'Escape') {
        e.target.value = '';
        onSearch({ target: e.target });
        e.target.blur();
    }
}

export function applySearchFilter() {
    const input = document.getElementById('search-input');
    if (input) {
        onSearch({ target: input });
    }
}

export function refreshSearchIndex() {
    // No longer needed with DOM filtering
}
