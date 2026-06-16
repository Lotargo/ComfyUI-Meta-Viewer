/**
 * Search bar component with fuzzy search
 */

import { images, setActiveIndex, saveState } from '../state.js';

let fuse = null;
let searchResults = [];
let selectedIndex = -1;

export function initSearch() {
    const input = document.getElementById('search-input');
    if (!input) return;

    // Load Fuse.js dynamically
    const script = document.createElement('script');
    script.src = '/static/js/vendor/fuse.min.js';
    script.onload = () => {
        initFuse();
    };
    document.head.appendChild(script);

    input.addEventListener('input', onSearch);
    input.addEventListener('keydown', onKeydown);
    input.addEventListener('focus', onSearch);
    input.addEventListener('blur', () => {
        setTimeout(() => clearResults(), 200);
    });
}

function initFuse() {
    if (typeof Fuse === 'undefined') return;

    fuse = new Fuse(images, {
        keys: [
            { name: 'file_name', weight: 2 },
            { name: 'format', weight: 1 },
            { name: 'prompt_parameters.positive_prompt', weight: 0.8 },
            { name: 'prompt_parameters.negative_prompt', weight: 0.5 },
            { name: 'prompt_parameters.model', weight: 1.5 },
            { name: 'prompt_parameters.sampler', weight: 0.5 }
        ],
        threshold: 0.4,
        includeMatches: true,
        minMatchCharLength: 2
    });
}

function rebuildIndex() {
    if (typeof Fuse === 'undefined') return;
    fuse = new Fuse(images, {
        keys: [
            { name: 'file_name', weight: 2 },
            { name: 'format', weight: 1 },
            { name: 'prompt_parameters.positive_prompt', weight: 0.8 },
            { name: 'prompt_parameters.negative_prompt', weight: 0.5 },
            { name: 'prompt_parameters.model', weight: 1.5 },
            { name: 'prompt_parameters.sampler', weight: 0.5 }
        ],
        threshold: 0.4,
        includeMatches: true,
        minMatchCharLength: 2
    });
}

function onSearch(e) {
    const query = e.target.value.trim();

    if (!query || query.length < 2) {
        clearResults();
        highlightItems([]);
        return;
    }

    if (!fuse) {
        rebuildIndex();
    }

    if (!fuse) return;

    searchResults = fuse.search(query);
    selectedIndex = -1;

    // Highlight matching items in sidebar
    const indices = searchResults.map(r => r.item ? images.indexOf(r.item) : -1).filter(i => i >= 0);
    highlightItems(indices);
}

function highlightItems(indices) {
    const items = document.querySelectorAll('.image-item');
    items.forEach(item => {
        const idx = parseInt(item.dataset.index);
        item.classList.toggle('search-match', indices.includes(idx));
    });
}

function clearResults() {
    searchResults = [];
    selectedIndex = -1;
    highlightItems([]);
}

function onKeydown(e) {
    if (e.key === 'Escape') {
        e.target.value = '';
        clearResults();
        e.target.blur();
        return;
    }

    if (e.key === 'ArrowDown') {
        e.preventDefault();
        selectedIndex = Math.min(selectedIndex + 1, searchResults.length - 1);
        selectResult(selectedIndex);
    }

    if (e.key === 'ArrowUp') {
        e.preventDefault();
        selectedIndex = Math.max(selectedIndex - 1, 0);
        selectResult(selectedIndex);
    }

    if (e.key === 'Enter' && selectedIndex >= 0) {
        selectResult(selectedIndex);
    }
}

function selectResult(index) {
    if (index < 0 || index >= searchResults.length) return;

    const result = searchResults[index];
    const img = result.item;
    const imgIndex = images.indexOf(img);

    if (imgIndex >= 0) {
        setActiveIndex(imgIndex);
        saveState();

        // Scroll into view
        const item = document.querySelector(`.image-item[data-index="${imgIndex}"]`);
        if (item) {
            item.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
            item.classList.add('active');
        }

        // Load meta view
        import('../meta-view.js').then(m => m.renderMeta(img));
    }
}

export function refreshSearchIndex() {
    rebuildIndex();
}
