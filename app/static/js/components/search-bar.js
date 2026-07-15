/**
 * Search bar component
 */

import { images, sidebarImages, searchSettings, saveState } from '../state.js';

export let currentSearchTerms = [];
export let isExactMatch = false;

export function initSearch() {
    const input = document.getElementById('search-input');
    if (!input) return;

    input.addEventListener('input', onSearch);
    input.addEventListener('keydown', onKeydown);

    // Settings dropdown toggle
    const btn = document.getElementById('search-settings-btn');
    const dropdown = document.getElementById('search-settings-dropdown');
    
    if (btn && dropdown) {
        btn.addEventListener('click', (e) => {
            e.stopPropagation();
            const isVisible = dropdown.style.display !== 'none';
            dropdown.style.display = isVisible ? 'none' : 'flex';
            if (!isVisible) syncSettingsToUI();
        });

        // Close when clicking outside
        document.addEventListener('click', (e) => {
            if (!dropdown.contains(e.target) && !btn.contains(e.target)) {
                dropdown.style.display = 'none';
            }
        });

        // Bind checkboxes
        const bindCheckbox = (id, key, fieldKey) => {
            const cb = document.getElementById(id);
            if (cb) {
                cb.addEventListener('change', (e) => {
                    if (fieldKey) {
                        searchSettings.fields[fieldKey] = e.target.checked;
                    } else {
                        searchSettings[key] = e.target.checked;
                    }
                    saveState();
                    applySearchFilter();
                });
            }
        };

        bindCheckbox('search-exact-match', 'exactMatch');
        bindCheckbox('search-field-positive', 'fields', 'positive_prompt');
        bindCheckbox('search-field-negative', 'fields', 'negative_prompt');
        bindCheckbox('search-field-model', 'fields', 'model');
        bindCheckbox('search-field-sampler', 'fields', 'sampler');
        bindCheckbox('search-field-resolution', 'fields', 'resolution');
    }
}

function syncSettingsToUI() {
    const setCb = (id, val) => {
        const cb = document.getElementById(id);
        if (cb) cb.checked = !!val;
    };
    setCb('search-exact-match', searchSettings.exactMatch);
    setCb('search-field-positive', searchSettings.fields.positive_prompt);
    setCb('search-field-negative', searchSettings.fields.negative_prompt);
    setCb('search-field-model', searchSettings.fields.model);
    setCb('search-field-sampler', searchSettings.fields.sampler);
    setCb('search-field-resolution', searchSettings.fields.resolution);
}

function getMatchPredicate(query) {
    currentSearchTerms = [];
    isExactMatch = searchSettings.exactMatch;
    
    if (!query) return () => true;
    
    // Split query by commas for tags, or spaces if no commas
    let terms = [];
    if (query.includes(',')) {
        terms = query.toLowerCase().split(',').map(t => t.trim()).filter(Boolean);
    } else {
        terms = query.toLowerCase().split(' ').map(t => t.trim()).filter(Boolean);
    }
    currentSearchTerms = terms;

    return (img) => {
        if (!img) return false;
        
        let searchableParts = [];
        searchableParts.push(img.file_name);
        searchableParts.push(img.format);
        
        if (searchSettings.fields.positive_prompt && img.prompt_parameters?.positive_prompt) {
            searchableParts.push(img.prompt_parameters.positive_prompt);
        }
        if (searchSettings.fields.negative_prompt && img.prompt_parameters?.negative_prompt) {
            searchableParts.push(img.prompt_parameters.negative_prompt);
        }
        if (searchSettings.fields.model && img.prompt_parameters?.model) {
            searchableParts.push(img.prompt_parameters.model);
        }
        if (searchSettings.fields.sampler && img.prompt_parameters?.sampler) {
            searchableParts.push(img.prompt_parameters.sampler);
        }
        if (searchSettings.fields.resolution) {
            if (img.size && img.size[0] && img.size[1]) searchableParts.push(`${img.size[0]}x${img.size[1]}`);
            if (img.width && img.height) searchableParts.push(`${img.width}x${img.height}`);
            if (img.image_width && img.image_height) searchableParts.push(`${img.image_width}x${img.image_height}`);
        }

        const searchString = searchableParts.filter(Boolean).join(' ').toLowerCase();

        // All terms must be found
        return terms.every(term => {
            if (isExactMatch) {
                // Exact match: term must appear as a whole word (using regex boundary)
                // We escape the term for regex to prevent errors.
                const escapedTerm = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
                const regex = new RegExp(`(?:^|\\W)${escapedTerm}(?:$|\\W)`);
                return regex.test(searchString);
            } else {
                return searchString.includes(term);
            }
        });
    };
}

function onSearch(e) {
    const query = e.target.value.trim();
    const predicate = getMatchPredicate(query);

    const isImagesTab = document.getElementById('tab-images')?.classList.contains('active');
    const galleryList = isImagesTab ? sidebarImages : images;

    // Filter gallery cards
    document.querySelectorAll('.gallery-card').forEach(card => {
        const idx = parseInt(card.dataset.index);
        const img = galleryList[idx];
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
    // No longer needed
}
