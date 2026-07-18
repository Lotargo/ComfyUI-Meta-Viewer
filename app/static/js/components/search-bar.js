/**
 * Search bar component. Search is applied independently to the central folder
 * gallery and the global Images sidebar.
 */

import { images, sidebarImages, searchSettings, saveState, dom } from '../state.js';

export let currentSearchTerms = [];
export let isExactMatch = false;

export function initSearch() {
    if (!dom.searchInput) return;

    dom.searchInput.addEventListener('input', onSearch);
    dom.searchInput.addEventListener('keydown', onKeydown);

    if (dom.searchSettingsBtn && dom.searchSettingsDropdown) {
        const setSettingsVisible = visible => {
            dom.searchSettingsDropdown.style.display = visible ? 'flex' : 'none';
            dom.searchSettingsBtn.setAttribute('aria-expanded', String(visible));
        };

        dom.searchSettingsBtn.addEventListener('click', event => {
            event.stopPropagation();
            const isVisible = dom.searchSettingsDropdown.style.display !== 'none';
            setSettingsVisible(!isVisible);
            if (!isVisible) syncSettingsToUI();
        });

        document.addEventListener('click', event => {
            if (!dom.searchSettingsDropdown.contains(event.target) && !dom.searchSettingsBtn.contains(event.target)) {
                setSettingsVisible(false);
            }
        });

        document.addEventListener('keydown', event => {
            if (event.key !== 'Escape' || dom.searchSettingsDropdown.style.display === 'none') return;
            setSettingsVisible(false);
            dom.searchSettingsBtn.focus();
        });

        const bindCheckbox = (id, key, fieldKey) => {
            const checkbox = document.querySelector('#' + id);
            if (!checkbox) return;
            checkbox.addEventListener('change', event => {
                if (fieldKey) searchSettings.fields[fieldKey] = event.target.checked;
                else searchSettings[key] = event.target.checked;
                saveState();
                applySearchFilter();
            });
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
    const setCheckbox = (id, value) => {
        const checkbox = document.querySelector('#' + id);
        if (checkbox) checkbox.checked = Boolean(value);
    };
    setCheckbox('search-exact-match', searchSettings.exactMatch);
    setCheckbox('search-field-positive', searchSettings.fields.positive_prompt);
    setCheckbox('search-field-negative', searchSettings.fields.negative_prompt);
    setCheckbox('search-field-model', searchSettings.fields.model);
    setCheckbox('search-field-sampler', searchSettings.fields.sampler);
    setCheckbox('search-field-resolution', searchSettings.fields.resolution);
}

function getMatchPredicate(query) {
    currentSearchTerms = [];
    isExactMatch = searchSettings.exactMatch;
    if (!query) return () => true;

    const terms = (query.includes(',') ? query.split(',') : query.split(' '))
        .map(term => term.toLowerCase().trim())
        .filter(Boolean);
    currentSearchTerms = terms;

    return img => {
        if (!img) return false;
        const searchableParts = [img.file_name, img.format];
        const params = img.prompt_parameters || {};
        if (searchSettings.fields.positive_prompt && params.positive_prompt) searchableParts.push(params.positive_prompt);
        if (searchSettings.fields.negative_prompt && params.negative_prompt) searchableParts.push(params.negative_prompt);
        if (searchSettings.fields.model && params.model) searchableParts.push(params.model);
        if (searchSettings.fields.sampler && params.sampler) searchableParts.push(params.sampler);
        if (searchSettings.fields.resolution) {
            if (img.size?.[0] && img.size?.[1]) searchableParts.push(`${img.size[0]}x${img.size[1]}`);
            if (img.width && img.height) searchableParts.push(`${img.width}x${img.height}`);
            if (img.image_width && img.image_height) searchableParts.push(`${img.image_width}x${img.image_height}`);
        }

        const searchString = searchableParts.filter(Boolean).join(' ').toLowerCase();
        return terms.every(term => {
            if (!isExactMatch) return searchString.includes(term);
            const escaped = term.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
            return new RegExp(`(?:^|\\W)${escaped}(?:$|\\W)`).test(searchString);
        });
    };
}

function onSearch(event) {
    const predicate = getMatchPredicate(event.target.value.trim());

    document.querySelectorAll('.gallery-card').forEach(card => {
        const index = Number.parseInt(card.dataset.index, 10);
        card.style.display = images[index] && predicate(images[index]) ? '' : 'none';
    });

    document.querySelectorAll('.image-item').forEach(item => {
        const index = Number.parseInt(item.dataset.index, 10);
        item.style.display = sidebarImages[index] && predicate(sidebarImages[index]) ? '' : 'none';
    });
}

function onKeydown(event) {
    if (event.key !== 'Escape') return;
    event.target.value = '';
    onSearch({ target: event.target });
    event.target.blur();
}

export function applySearchFilter() {
    if (dom.searchInput) onSearch({ target: dom.searchInput });
}

export function refreshSearchIndex() {
    // Search operates directly on the current paginated collections.
}
