const byId = (id) => document.getElementById(id);

const elements = {
    categoryTabs: byId('template-category-tabs'),
    templateSelect: byId('template-select'),
    templateName: byId('template-name'),
    templateMeta: byId('template-meta'),
    templateDescription: byId('template-description'),
    sourceBanner: byId('source-draft-banner'),
    fields: byId('editor-fields'),
    advancedFields: byId('advanced-fields'),
    advancedCount: byId('advanced-count'),
    advancedOpen: byId('advanced-settings-open'),
    advancedDialog: byId('advanced-settings-dialog'),
    resourceSection: byId('resource-section'),
    resourceSlots: byId('resource-slots'),
    resourceCount: byId('resource-count'),
    advancedResourceSection: byId('advanced-resource-section'),
    advancedResourceSlots: byId('advanced-resource-slots'),
    draftStatus: byId('draft-status'),
    validationSummary: byId('validation-summary'),
    previewButton: byId('preview-workflow'),
    generateButton: byId('generate-workflow'),
    generateLabel: byId('generate-label'),
    generateHelp: byId('generate-help'),
    generateFromPreview: byId('generate-from-preview'),
    previewDialog: byId('workflow-preview-dialog'),
    dependencyReport: byId('dependency-report'),
    workflowJson: byId('workflow-json-preview'),
    runRibbon: byId('run-ribbon'),
    runStateIcon: byId('run-state-icon'),
    runStateTitle: byId('run-state-title'),
    runStateDetail: byId('run-state-detail'),
    runProgress: byId('run-progress-bar'),
    cancelRun: byId('cancel-run'),
    queueSummary: byId('queue-summary'),
    resultGrid: byId('result-grid'),
    resultsEmpty: byId('results-empty'),
    resultsRefresh: byId('results-refresh'),
    offlineBanner: byId('runtime-offline-banner'),
    runtimeOpen: byId('runtime-open'),
    runtimeConnect: byId('runtime-connect-cta'),
    runtimeLayer: byId('runtime-drawer-layer'),
    runtimeDrawer: byId('runtime-drawer'),
    runtimeClose: byId('runtime-close'),
    runtimeBackdrop: byId('runtime-drawer-backdrop'),
    runtimeHeaderStatus: byId('runtime-status-text'),
    runtimeHeaderDetail: byId('runtime-status-detail'),
    runtimeHeaderDot: byId('runtime-header-dot'),
    runtimePill: byId('runtime-status-pill'),
    runtimeDrawerStatus: byId('runtime-drawer-status'),
    runtimeDrawerDetail: byId('runtime-drawer-detail'),
    importOpen: byId('import-template-open'),
    importDialog: byId('template-import-dialog'),
    importForm: byId('template-import-form'),
    importFile: byId('template-import-file'),
    importName: byId('template-import-name'),
    importSubmit: byId('template-import-submit'),
    sourceInspect: byId('analyze-source-workflow'),
    sourceDialog: byId('source-workflow-dialog'),
    sourceSummary: byId('source-workflow-summary'),
    sourceReport: byId('source-workflow-report'),
    sourceJson: byId('source-workflow-json'),
    toastContainer: byId('toast-container'),
};

const runtimeElements = {
    mode: byId('stat-mode'),
    status: byId('stat-status'),
    pid: byId('stat-pid'),
    queue: byId('stat-queue'),
    endpoint: byId('stat-endpoint'),
    start: byId('btn-start'),
    stop: byId('btn-stop'),
    restart: byId('btn-restart'),
    interrupt: byId('btn-interrupt'),
    save: byId('btn-save-config'),
    detect: byId('btn-detect-path'),
    launcher: byId('btn-gen-script'),
    refresh: byId('refresh-status'),
    installPath: byId('install-path'),
    host: byId('host-input'),
    port: byId('port-input'),
    extraArgs: byId('extra-args-input'),
    customPython: byId('custom-python-input'),
    detectionCard: byId('detection-result-card'),
    detectionBadge: byId('detection-badge'),
    detectionSummary: byId('detection-summary'),
    detectionDetails: byId('detection-details'),
    stats: byId('system-stats-panel'),
    logs: byId('logs-console'),
    autoScroll: byId('autoscroll-logs'),
    clearLogs: byId('btn-clear-logs'),
    refreshLogs: byId('btn-refresh-logs'),
};

const state = {
    templates: [],
    inventory: { online: false, models: {}, node_types: [] },
    selected: null,
    draft: null,
    values: {},
    resources: {},
    runs: [],
    currentRun: null,
    previewReady: false,
    saveTimer: null,
    pollTimer: null,
    statusTimer: null,
    loadingTemplate: false,
};

const ADVANCED_FIELD_IDS = new Set([
    'negative_prompt', 'width', 'height', 'batch_size', 'seed', 'steps', 'cfg',
    'sampler', 'scheduler', 'filename_prefix', 'denoise', 'frames', 'fps',
    'base_steps', 'refiner_steps', 'refiner_denoise', 'format', 'codec',
]);

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const contentType = response.headers.get('content-type') || '';
    const data = contentType.includes('application/json') ? await response.json() : {};
    if (!response.ok) {
        const error = new Error(data.error || `Request failed (${response.status})`);
        error.code = data.code;
        error.data = data;
        throw error;
    }
    return data;
}

function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `editor-toast ${type}`;
    toast.textContent = message;
    elements.toastContainer.appendChild(toast);
    window.setTimeout(() => toast.remove(), 4500);
}

function iconSvg(kind) {
    const icons = {
        model: '<svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="1.8" fill="none"><path d="M12 3 4 7v10l8 4 8-4V7z"/><path d="m4 7 8 4 8-4M12 11v10"/></svg>',
        adapter: '<svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="1.8" fill="none"><path d="M8 3v5m8-5v5M6 8h12v5a6 6 0 0 1-12 0zM12 19v2"/></svg>',
        open: '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 3h7v7M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>',
        download: '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/></svg>',
    };
    return icons[kind] || icons.model;
}

function currentManifest() {
    return state.selected?.manifest || null;
}

function setDraftStatus(label, mode = '') {
    elements.draftStatus.textContent = label;
    elements.draftStatus.className = `draft-state ${mode}`.trim();
}

function markDirty() {
    state.previewReady = false;
    elements.generateFromPreview.disabled = true;
    updateValidation(null);
    setDraftStatus('Unsaved changes');
    window.clearTimeout(state.saveTimer);
    state.saveTimer = window.setTimeout(() => {
        saveDraft().catch(() => {});
    }, 450);
}

function defaultResourceSelections(template) {
    const output = {};
    for (const [slotId, slot] of Object.entries(template.manifest.resource_slots || {})) {
        const options = template.resource_options?.[slotId] || [];
        if (slot.multiple) {
            output[slotId] = [];
        } else if (slot.required && options.length === 1) {
            output[slotId] = options[0].name;
        }
    }
    return output;
}

async function bootstrap() {
    try {
        const payload = await requestJson('/api/editor/bootstrap');
        state.templates = payload.templates || [];
        state.inventory = payload.inventory || state.inventory;
        if (!state.templates.length) throw new Error('No workflow templates are available.');

        const draftId = new URLSearchParams(window.location.search).get('draft_id');
        if (draftId) {
            const draftPayload = await requestJson(`/api/editor/drafts/${encodeURIComponent(draftId)}`);
            const registered = state.templates.find((item) => item.manifest.id === draftPayload.draft.template_id);
            if (registered) {
                state.draft = draftPayload.draft;
                state.values = { ...registered.defaults, ...draftPayload.draft.values };
                state.resources = { ...draftPayload.draft.resource_selections };
                selectTemplate(registered, { preserveDraft: true });
            } else {
                throw new Error(`Template ${draftPayload.draft.template_id} is no longer installed.`);
            }
        } else {
            const first = state.templates.find((item) => item.manifest.id === 'core-image') || state.templates[0];
            selectTemplate(first);
        }
        updateRuntimePresence(state.inventory.online);
        await loadRuns();
    } catch (error) {
        elements.fields.innerHTML = `<div class="resource-card-empty">${escapeHtml(error.message)}</div>`;
        showToast(error.message, 'error');
    }
}

function selectTemplate(template, { preserveDraft = false } = {}) {
    state.loadingTemplate = true;
    state.selected = template;
    if (!preserveDraft) {
        state.draft = null;
        state.values = { ...template.defaults };
        state.resources = defaultResourceSelections(template);
        history.replaceState({}, '', '/editor');
    }
    state.previewReady = false;
    renderTemplateNavigation();
    renderFields();
    renderResources();
    renderSourceBanner();
    updateValidation(null);
    setDraftStatus(state.draft ? `Draft #${state.draft.id}` : 'New draft');
    state.loadingTemplate = false;
}

function renderTemplateNavigation() {
    const manifest = currentManifest();
    const categories = [...new Set(state.templates.map((item) => item.manifest.category))];
    elements.categoryTabs.querySelectorAll('[data-category]').forEach((tab) => {
        const active = tab.dataset.category === manifest.category;
        tab.classList.toggle('active', active);
        tab.setAttribute('aria-selected', active ? 'true' : 'false');
        tab.hidden = !categories.includes(tab.dataset.category);
    });
    const sameCategory = state.templates.filter((item) => item.manifest.category === manifest.category);
    elements.templateSelect.innerHTML = sameCategory
        .map((item) => `<option value="${escapeHtml(item.manifest.id)}"${item.manifest.id === manifest.id ? ' selected' : ''}>${escapeHtml(item.manifest.name)}</option>`)
        .join('');
    elements.templateName.textContent = manifest.name;
    elements.templateMeta.textContent = `${manifest.media_type} · v${manifest.version} · ${state.selected.source}`;
    elements.templateDescription.textContent = manifest.description;
    updateGenerateAvailability();
}

function renderFields() {
    const fields = currentManifest().fields || [];
    const regular = fields.filter((field) => !field.advanced && !ADVANCED_FIELD_IDS.has(field.id));
    const advanced = fields.filter((field) => field.advanced || ADVANCED_FIELD_IDS.has(field.id));
    elements.fields.innerHTML = renderFieldSections(regular, 1);
    elements.advancedFields.innerHTML = renderFieldSections(advanced, 0, true);
    bindFieldEvents(elements.fields);
    bindFieldEvents(elements.advancedFields);
    updateAdvancedCount(advanced.length);
}

function renderFieldSections(fields, indexStart = 1, compact = false) {
    const sections = new Map();
    for (const field of fields) {
        if (!sections.has(field.section)) sections.set(field.section, []);
        sections.get(field.section).push(field);
    }
    return [...sections.entries()].map(([section, items], index) => `
        <section class="control-section">
            ${compact
        ? `<div class="advanced-section-heading"><h3>${escapeHtml(section)}</h3></div>`
        : `<div class="control-section-heading"><div><span class="control-section-index">${index === 0 ? 'Start here' : String(index + indexStart).padStart(2, '0')}</span><h2>${escapeHtml(friendlySectionName(section))}</h2></div></div>`}
            <div class="control-grid">${items.map(renderField).join('')}</div>
        </section>
    `).join('');
}

function friendlySectionName(section) {
    const names = {
        Prompt: 'Describe your idea',
        Reference: 'Add a reference image',
    };
    return names[section] || section;
}

function friendlyFieldLabel(field) {
    const labels = {
        positive_prompt: currentManifest()?.media_type === 'video' ? 'What should happen in the video?' : 'What should the image look like?',
        negative_prompt: 'What should be avoided?',
        checkpoint: 'Model',
    };
    return labels[field.id] || field.label;
}

function friendlyResourceName(name) {
    const baseName = String(name || '').split(/[\\/]/).pop() || String(name || '');
    return baseName
        .replace(/\.(safetensors|ckpt|pt|pth|bin)$/i, '')
        .replace(/[_-]+/g, ' ')
        .replace(/\s+/g, ' ')
        .trim();
}

function renderField(field) {
    const value = state.values[field.id] ?? '';
    const classNames = ['editor-field', `field-${field.kind}`];
    if (field.id === 'positive_prompt') classNames.push('field-positive');
    if (field.id === 'negative_prompt') classNames.push('field-negative');
    let control;
    const attributes = [
        `data-field-id="${escapeHtml(field.id)}"`,
        field.minimum !== null && field.minimum !== undefined ? `min="${field.minimum}"` : '',
        field.maximum !== null && field.maximum !== undefined ? `max="${field.maximum}"` : '',
        field.step !== null && field.step !== undefined ? `step="${field.step}"` : '',
        field.required ? 'required' : '',
    ].filter(Boolean).join(' ');

    if (field.kind === 'textarea') {
        const placeholder = field.id === 'positive_prompt' ? 'For example: a quiet cabin beside a frozen lake at sunrise…' : '';
        control = `<textarea id="field-${escapeHtml(field.id)}" placeholder="${escapeHtml(placeholder)}" ${attributes}>${escapeHtml(value)}</textarea>`;
    } else if (field.kind === 'select') {
        control = `<select id="field-${escapeHtml(field.id)}" ${attributes}>${field.options.map((option) => `<option value="${escapeHtml(option.value)}"${String(value) === option.value ? ' selected' : ''}>${escapeHtml(option.label)}</option>`).join('')}</select>`;
    } else if (field.kind === 'seed') {
        control = `<div class="seed-control"><input id="field-${escapeHtml(field.id)}" type="number" value="${escapeHtml(value)}" ${attributes}><button class="seed-randomize" type="button" data-randomize="${escapeHtml(field.id)}" title="Random seed" aria-label="Use random seed">↻</button></div>`;
    } else if (field.kind === 'image') {
        const hasValue = Boolean(value);
        control = `<div class="reference-upload${hasValue ? ' has-value' : ''}" data-reference-upload="${escapeHtml(field.id)}"><div class="reference-upload-copy"><strong>${hasValue ? 'Reference ready' : 'No reference image'}</strong><span>${escapeHtml(value || 'Upload to the connected ComfyUI input folder')}</span></div><label class="reference-upload-button">${hasValue ? 'Replace' : 'Upload'}<input type="file" accept="image/*" data-image-field="${escapeHtml(field.id)}" hidden></label></div>`;
    } else {
        const type = field.kind === 'number' ? 'number' : 'text';
        control = `<input id="field-${escapeHtml(field.id)}" type="${type}" value="${escapeHtml(value)}" ${attributes}>`;
    }
    const help = field.id === 'positive_prompt'
        ? 'Use natural language. Mention the subject, mood, lighting or style you want.'
        : field.description;
    return `<label class="${classNames.join(' ')}"><span class="field-label">${escapeHtml(friendlyFieldLabel(field))}${field.required ? ' *' : ''}</span>${control}${help ? `<small class="field-help">${escapeHtml(help)}</small>` : ''}</label>`;
}

function bindFieldEvents(container) {
    container.querySelectorAll('[data-field-id]').forEach((input) => {
        input.addEventListener('input', () => {
            const field = currentManifest().fields.find((item) => item.id === input.dataset.fieldId);
            state.values[input.dataset.fieldId] = field?.kind === 'number' || field?.kind === 'seed'
                ? (input.value === '' ? null : Number(input.value))
                : input.value;
            markDirty();
        });
    });
    container.querySelectorAll('[data-randomize]').forEach((button) => {
        button.addEventListener('click', () => {
            const id = button.dataset.randomize;
            state.values[id] = -1;
            const input = byId(`field-${id}`);
            if (input) input.value = '-1';
            markDirty();
        });
    });
    container.querySelectorAll('[data-image-field]').forEach((input) => {
        input.addEventListener('change', () => uploadReference(input));
    });
}

async function uploadReference(input) {
    const file = input.files?.[0];
    if (!file) return;
    const fieldId = input.dataset.imageField;
    const upload = input.closest('[data-reference-upload]');
    upload.classList.add('is-loading');
    const form = new FormData();
    form.append('file', file);
    try {
        const payload = await requestJson('/api/editor/inputs', { method: 'POST', body: form });
        state.values[fieldId] = payload.value;
        renderFields();
        markDirty();
        showToast('Reference image uploaded to ComfyUI.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        upload.classList.remove('is-loading');
    }
}

function renderResources() {
    const slots = Object.entries(currentManifest().resource_slots || {});
    const requiredSlots = slots.filter(([, slot]) => slot.required);
    const optionalSlots = slots.filter(([, slot]) => !slot.required);
    elements.resourceSection.hidden = requiredSlots.length === 0;
    elements.resourceCount.textContent = requiredSlots.length > 1 ? `${requiredSlots.length} required files` : 'Required';
    elements.resourceSlots.innerHTML = requiredSlots.map(([slotId, slot]) => renderResourceSlot(slotId, slot)).join('');
    elements.advancedResourceSection.hidden = optionalSlots.length === 0;
    elements.advancedResourceSlots.innerHTML = optionalSlots.map(([slotId, slot]) => renderResourceSlot(slotId, slot)).join('');
    bindResourceEvents(elements.resourceSlots);
    bindResourceEvents(elements.advancedResourceSlots);
    const advancedFields = (currentManifest().fields || []).filter((field) => field.advanced || ADVANCED_FIELD_IDS.has(field.id));
    updateAdvancedCount(advancedFields.length, optionalSlots.length);
    updateGenerateAvailability();
}

function updateAdvancedCount(fieldCount, resourceCount = null) {
    const optionalResources = resourceCount ?? Object.values(currentManifest()?.resource_slots || {}).filter((slot) => !slot.required).length;
    const total = fieldCount + optionalResources;
    elements.advancedCount.textContent = String(total);
}

function renderResourceSlot(slotId, slot) {
    const options = state.selected.resource_options?.[slotId] || [];
    const kind = slot.multiple ? 'adapter' : 'model';
    const label = slotId.includes('checkpoint') && !slotId.includes('refiner') ? 'Model' : slot.label;
    const description = slot.required
        ? (slot.description || 'This local model powers the generation.')
        : (slot.description || 'Optional style add-on.');
    const head = `<div class="resource-card-head"><div><span class="resource-kind-icon">${iconSvg(kind)}</span><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(description)}</small></div></div></div>`;
    if (!options.length) {
        return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<div class="resource-card-empty">No compatible model was found. Open the ComfyUI connection panel to check this installation.</div></div>`;
    }
    if (slot.multiple) {
        const selections = Array.isArray(state.resources[slotId]) ? state.resources[slotId] : [];
        return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<div class="lora-add-row"><select data-lora-option="${escapeHtml(slotId)}"><option value="">Choose an add-on…</option>${options.map((option) => `<option value="${escapeHtml(option.name)}">${escapeHtml(friendlyResourceName(option.name))}</option>`).join('')}</select><button class="btn btn-secondary btn-sm" type="button" data-lora-add="${escapeHtml(slotId)}">Add</button></div><div class="lora-list">${selections.map((selection, index) => renderLora(slotId, selection, index)).join('')}</div></div>`;
    }
    const selected = typeof state.resources[slotId] === 'string'
        ? state.resources[slotId]
        : state.resources[slotId]?.name || '';
    return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<select data-resource-slot="${escapeHtml(slotId)}"><option value="">${slot.required ? 'Choose a model…' : 'None'}</option>${options.map((option) => `<option value="${escapeHtml(option.name)}"${selected === option.name ? ' selected' : ''}>${escapeHtml(friendlyResourceName(option.name))}</option>`).join('')}</select></div>`;
}

function renderLora(slotId, selection, index) {
    const normalized = typeof selection === 'string'
        ? { name: selection, strength_model: 1, strength_clip: 1 }
        : selection;
    return `<div class="lora-card"><span class="lora-card-name" title="${escapeHtml(normalized.name)}">${escapeHtml(friendlyResourceName(normalized.name))}</span><input type="number" min="-5" max="5" step="0.05" value="${escapeHtml(normalized.strength_model ?? 1)}" data-lora-strength="${escapeHtml(slotId)}" data-lora-index="${index}" title="Style strength"><button class="lora-remove" type="button" data-lora-remove="${escapeHtml(slotId)}" data-lora-index="${index}" aria-label="Remove add-on">×</button></div>`;
}

function bindResourceEvents(container) {
    container.querySelectorAll('[data-resource-slot]').forEach((select) => {
        select.addEventListener('change', () => {
            state.resources[select.dataset.resourceSlot] = select.value;
            markDirty();
        });
    });
    container.querySelectorAll('[data-lora-add]').forEach((button) => {
        button.addEventListener('click', () => {
            const slotId = button.dataset.loraAdd;
            const select = container.querySelector(`[data-lora-option="${CSS.escape(slotId)}"]`);
            if (!select.value) return;
            const selections = Array.isArray(state.resources[slotId]) ? [...state.resources[slotId]] : [];
            if (selections.some((item) => (typeof item === 'string' ? item : item.name) === select.value)) {
                showToast('That adapter is already in the chain.', 'info');
                return;
            }
            selections.push({ name: select.value, strength_model: 1, strength_clip: 1 });
            state.resources[slotId] = selections;
            renderResources();
            markDirty();
        });
    });
    container.querySelectorAll('[data-lora-remove]').forEach((button) => {
        button.addEventListener('click', () => {
            const selections = [...(state.resources[button.dataset.loraRemove] || [])];
            selections.splice(Number(button.dataset.loraIndex), 1);
            state.resources[button.dataset.loraRemove] = selections;
            renderResources();
            markDirty();
        });
    });
    container.querySelectorAll('[data-lora-strength]').forEach((input) => {
        input.addEventListener('change', () => {
            const selections = [...(state.resources[input.dataset.loraStrength] || [])];
            const index = Number(input.dataset.loraIndex);
            selections[index] = { ...selections[index], strength_model: Number(input.value), strength_clip: Number(input.value) };
            state.resources[input.dataset.loraStrength] = selections;
            markDirty();
        });
    });
}

async function ensureDraft() {
    if (state.draft) return state.draft;
    const payload = await requestJson('/api/editor/drafts', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
            template_id: currentManifest().id,
            values: state.values,
            resource_selections: state.resources,
        }),
    });
    state.draft = payload.draft;
    history.replaceState({}, '', `/editor?draft_id=${state.draft.id}`);
    renderSourceBanner();
    return state.draft;
}

async function saveDraft() {
    if (state.loadingTemplate) return;
    setDraftStatus('Saving…', 'saving');
    try {
        const draft = await ensureDraft();
        const payload = await requestJson(`/api/editor/drafts/${draft.id}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ values: state.values, resource_selections: state.resources }),
        });
        state.draft = payload.draft;
        setDraftStatus(`Saved · #${state.draft.id}`, 'saved');
    } catch (error) {
        setDraftStatus('Save failed', 'error');
        showToast(error.message, 'error');
        throw error;
    }
}

function renderSourceBanner() {
    elements.sourceBanner.hidden = !state.draft?.source_asset_id;
}

async function previewWorkflow({ openDialog = true } = {}) {
    elements.previewButton.disabled = true;
    try {
        await saveDraft();
        const payload = await requestJson(`/api/editor/drafts/${state.draft.id}/preview`, { method: 'POST' });
        state.inventory = payload.inventory || state.inventory;
        state.previewReady = Boolean(payload.dependencies.ready);
        updateValidation(payload.dependencies);
        elements.dependencyReport.innerHTML = dependencyCards(payload.dependencies);
        elements.workflowJson.textContent = JSON.stringify(payload.workflow, null, 2);
        if (openDialog) elements.previewDialog.showModal();
        return payload;
    } catch (error) {
        state.previewReady = false;
        updateValidation(error.data?.dependencies || null, error.message);
        showToast(error.message, 'error');
        return null;
    } finally {
        elements.previewButton.disabled = false;
    }
}

function updateValidation(report, explicitError = '') {
    let mode = 'neutral';
    const missing = requiredConfigurationIssues();
    let text = state.inventory.online
        ? (missing.length ? missing[0] : 'Ready to create')
        : 'Connect ComfyUI to create';
    if (report?.ready) {
        mode = 'ready';
        text = 'Ready to create';
    } else if (report) {
        mode = 'error';
        const total = (report.missing_nodes?.length || 0) + (report.missing_resources?.length || 0);
        text = total ? 'Some required ComfyUI files are missing' : (report.runtime_error || 'ComfyUI could not validate this creation');
    } else if (explicitError) {
        mode = 'error';
        text = explicitError;
    } else if (state.inventory.online && !missing.length) {
        mode = 'ready';
    }
    elements.validationSummary.innerHTML = `<span class="validation-dot ${mode}"></span><span>${escapeHtml(text)}</span>`;
    elements.generateFromPreview.disabled = !state.previewReady;
    updateGenerateAvailability();
}

function requiredConfigurationIssues() {
    if (!currentManifest()) return ['Choose what you want to create'];
    for (const field of currentManifest().fields || []) {
        if (field.required && (state.values[field.id] === '' || state.values[field.id] === null || state.values[field.id] === undefined)) {
            return [`Complete “${friendlyFieldLabel(field)}”`];
        }
    }
    for (const [slotId, slot] of Object.entries(currentManifest().resource_slots || {})) {
        const value = state.resources[slotId];
        if (slot.required && (!value || (Array.isArray(value) && !value.length))) {
            return [`Choose ${slot.label.toLowerCase()} to continue`];
        }
    }
    return [];
}

function updateGenerateAvailability() {
    if (!elements.generateButton) return;
    const media = currentManifest()?.media_type === 'video' ? 'video' : 'image';
    const running = state.currentRun && ['queued', 'running'].includes(state.currentRun.status);
    elements.generateLabel.textContent = state.inventory.online ? `Create ${media}` : 'Connect ComfyUI';
    elements.generateHelp.textContent = state.inventory.online
        ? `Your ${media} will be saved to Library automatically.`
        : 'Connect your local ComfyUI once, then create from this page.';
    elements.generateButton.disabled = !state.selected || Boolean(running);
}

function dependencyCards(report) {
    const runtimeClass = report.runtime_online ? 'ready' : 'error';
    const runtimeText = report.runtime_online ? 'ComfyUI API answered the preflight check.' : (report.runtime_error || 'ComfyUI API is offline.');
    const nodes = report.missing_nodes || [];
    const resources = report.missing_resources || [];
    const compatibility = report.compatibility_issues || [];
    return `
        <article class="dependency-card ${runtimeClass}"><strong>Runtime</strong><p>${escapeHtml(runtimeText)}</p></article>
        <article class="dependency-card ${nodes.length ? 'error' : 'ready'}"><strong>Node types</strong>${nodes.length ? `<ul>${nodes.map((node) => `<li>${escapeHtml(node)}</li>`).join('')}</ul>` : '<p>All required node types are installed.</p>'}</article>
        <article class="dependency-card ${resources.length ? 'error' : 'ready'}"><strong>Model resources</strong>${resources.length ? `<ul>${resources.map((item) => `<li>${escapeHtml(item.label)} — ${escapeHtml(item.reason)}</li>`).join('')}</ul>` : '<p>Every required resource is resolved explicitly.</p>'}</article>
        <article class="dependency-card ${compatibility.some((item) => item.status === 'incompatible') ? 'error' : compatibility.length ? 'warning' : 'ready'}"><strong>Compatibility</strong>${compatibility.length ? `<ul>${compatibility.map((item) => `<li>${escapeHtml(item.resource_name)} — ${escapeHtml(item.reason)}</li>`).join('')}</ul>` : '<p>No compatibility conflicts detected.</p>'}</article>
    `;
}

async function generateWorkflow() {
    if (!state.inventory.online) {
        openRuntimeDrawer();
        showToast('Connect or start ComfyUI first.', 'info');
        return;
    }
    const missing = requiredConfigurationIssues();
    if (missing.length) {
        updateValidation(null, missing[0]);
        showToast(missing[0], 'info');
        const firstMissing = elements.fields.querySelector(':invalid') || elements.resourceSlots.querySelector('select');
        firstMissing?.focus();
        return;
    }
    if (!state.previewReady) {
        const preview = await previewWorkflow({ openDialog: false });
        if (!preview?.dependencies.ready) return;
    }
    elements.generateButton.disabled = true;
    elements.generateFromPreview.disabled = true;
    try {
        const payload = await requestJson(`/api/editor/drafts/${state.draft.id}/run`, { method: 'POST' });
        state.currentRun = payload.run;
        if (elements.previewDialog.open) elements.previewDialog.close();
        renderRunRibbon(state.currentRun);
        await loadRuns();
        startRunPolling();
        showToast('Workflow queued in ComfyUI.', 'success');
    } catch (error) {
        if (error.data?.dependencies) updateValidation(error.data.dependencies);
        showToast(error.message, 'error');
        elements.generateFromPreview.disabled = !state.previewReady;
        updateGenerateAvailability();
    }
}

function startRunPolling() {
    window.clearTimeout(state.pollTimer);
    if (!state.currentRun || ['completed', 'failed', 'cancelled'].includes(state.currentRun.status)) return;
    state.pollTimer = window.setTimeout(pollCurrentRun, 1500);
}

async function pollCurrentRun() {
    try {
        const payload = await requestJson(`/api/editor/runs/${state.currentRun.id}`);
        state.currentRun = payload.run;
        renderRunRibbon(state.currentRun);
        if (['completed', 'failed', 'cancelled'].includes(state.currentRun.status)) {
            await loadRuns();
            if (state.currentRun.status === 'completed') showToast('Generation imported into the local library.', 'success');
            if (state.currentRun.status === 'failed') showToast('ComfyUI reported a failed workflow.', 'error');
            return;
        }
    } catch (error) {
        showToast(`Could not refresh run: ${error.message}`, 'error');
    }
    startRunPolling();
}

function renderRunRibbon(run) {
    if (!run) {
        elements.runRibbon.hidden = true;
        return;
    }
    elements.runRibbon.hidden = false;
    elements.runStateIcon.className = `run-state-icon ${run.status}`;
    const labels = { queued: 'Queued', running: 'Generating', completed: 'Completed', failed: 'Failed', cancelled: 'Cancelled' };
    elements.runStateTitle.textContent = labels[run.status] || run.status;
    elements.runStateDetail.textContent = run.current_node
        ? `Executing node ${run.current_node}`
        : run.queue_position !== null && run.queue_position !== undefined
            ? `Queue position ${run.queue_position + 1}`
            : `Prompt ${run.prompt_id}`;
    const progress = run.status === 'completed' ? 100 : Math.max(4, Math.min(99, Number(run.progress || 0) * 100));
    elements.runProgress.style.width = `${progress}%`;
    elements.cancelRun.hidden = ['completed', 'failed', 'cancelled'].includes(run.status);
    elements.queueSummary.innerHTML = `<span></span> ${['queued', 'running'].includes(run.status) ? labels[run.status] : 'Queue idle'}`;
    if (['completed', 'failed', 'cancelled'].includes(run.status)) {
        elements.generateFromPreview.disabled = !state.previewReady;
    }
    updateGenerateAvailability();
}

async function cancelCurrentRun() {
    if (!state.currentRun) return;
    elements.cancelRun.disabled = true;
    try {
        const payload = await requestJson(`/api/editor/runs/${state.currentRun.id}/cancel`, { method: 'POST' });
        state.currentRun = payload.run;
        renderRunRibbon(state.currentRun);
        await loadRuns();
        showToast('Run cancelled.', 'info');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.cancelRun.disabled = false;
    }
}

async function loadRuns() {
    try {
        const payload = await requestJson('/api/editor/runs?limit=40');
        state.runs = payload.runs || [];
        const active = state.runs.find((run) => ['queued', 'running'].includes(run.status));
        if (active && !state.currentRun) {
            state.currentRun = active;
            renderRunRibbon(active);
            startRunPolling();
        }
        renderResults();
    } catch (error) {
        console.error('Failed to load workflow runs', error);
    }
}

function renderResults() {
    const cards = [];
    for (const run of state.runs) {
        for (const assetId of run.output_asset_ids || []) cards.push(resultCard(run, assetId));
    }
    const nonOutputRuns = state.runs.filter((run) => !(run.output_asset_ids || []).length && ['failed', 'cancelled'].includes(run.status));
    cards.push(...nonOutputRuns.slice(0, 4).map(runHistoryCard));
    elements.resultGrid.innerHTML = cards.join('');
    elements.resultsEmpty.hidden = cards.length > 0;
    elements.resultGrid.querySelectorAll('img, video').forEach((media) => {
        media.addEventListener('error', () => {
            media.closest('.result-card')?.remove();
            elements.resultsEmpty.hidden = Boolean(elements.resultGrid.children.length);
        }, { once: true });
    });
}

function resultCard(run, assetId) {
    const isVideo = (run.output_refs || []).some((ref) => {
        const mediaKey = String(ref.media_key || '').toLowerCase();
        const filename = String(ref.filename || '').toLowerCase();
        return mediaKey.includes('video') || /\.(mp4|webm|mov|m4v|mkv|avi)$/.test(filename);
    });
    const media = isVideo
        ? `<video src="/api/original/${assetId}" preload="metadata" controls></video>`
        : `<img src="/api/preview/${assetId}" alt="Generated result ${assetId}" loading="lazy">`;
    return `<article class="result-card"><div class="result-media">${media}</div><div class="result-card-meta"><div><strong>Creation #${run.id}</strong><span>Saved in Library</span></div><div class="result-card-actions"><a href="/library" title="Open in Library">${iconSvg('open')}</a><a href="/api/original/${assetId}" download title="Download original">${iconSvg('download')}</a></div></div></article>`;
}

function runHistoryCard(run) {
    const message = run.error?.message || run.error?.exception_message || `Run ${run.status}`;
    return `<article class="run-history-card ${escapeHtml(run.status)}"><span class="validation-dot ${run.status === 'failed' ? 'error' : 'neutral'}"></span><div><strong>Generation #${run.id} ${escapeHtml(run.status)}</strong><p>${escapeHtml(message)}</p></div></article>`;
}

function updateRuntimePresence(online) {
    state.inventory.online = Boolean(online);
    elements.offlineBanner.hidden = Boolean(online);
    updateValidation(null);
}

function openRuntimeDrawer() {
    elements.runtimeLayer.hidden = false;
    elements.runtimeOpen.setAttribute('aria-expanded', 'true');
    document.body.classList.add('drawer-open');
    window.requestAnimationFrame(() => elements.runtimeDrawer.focus?.());
}

function closeRuntimeDrawer() {
    elements.runtimeLayer.hidden = true;
    elements.runtimeOpen.setAttribute('aria-expanded', 'false');
    document.body.classList.remove('drawer-open');
}

function runtimeConfigPayload() {
    return {
        install_path: runtimeElements.installPath.value.trim(),
        host: runtimeElements.host.value.trim() || '127.0.0.1',
        port: Number(runtimeElements.port.value) || 8188,
        extra_args: runtimeElements.extraArgs.value.trim(),
        custom_python: runtimeElements.customPython.value.trim(),
    };
}

async function loadRuntimeConfig() {
    try {
        const config = await requestJson('/api/comfyui/config');
        runtimeElements.installPath.value = config.install_path || '';
        runtimeElements.host.value = config.host || '127.0.0.1';
        runtimeElements.port.value = config.port || 8188;
        runtimeElements.extraArgs.value = config.extra_args || '';
        runtimeElements.customPython.value = config.custom_python || '';
        if (config.install_path) detectRuntime(config.install_path, config.custom_python, false);
    } catch (error) {
        console.error('Could not load ComfyUI configuration', error);
    }
}

async function saveRuntimeConfig() {
    try {
        await requestJson('/api/comfyui/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(runtimeConfigPayload()),
        });
        showToast('ComfyUI connection saved.', 'success');
        await detectRuntime();
        await updateRuntimeStatus(true);
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function detectRuntime(path = '', customPython = '', notify = true) {
    const config = runtimeConfigPayload();
    if (path) config.install_path = path;
    if (customPython) config.custom_python = customPython;
    if (!config.install_path) {
        if (notify) showToast('Enter a ComfyUI installation path.', 'error');
        return;
    }
    runtimeElements.detect.disabled = true;
    try {
        const data = await requestJson('/api/comfyui/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path: config.install_path, custom_python: config.custom_python }),
        });
        runtimeElements.detectionCard.hidden = false;
        runtimeElements.detectionBadge.className = `badge ${data.is_valid ? 'badge-success' : 'badge-error'}`;
        runtimeElements.detectionBadge.textContent = data.is_valid ? (data.is_portable ? 'Portable Windows' : 'Standard') : 'Invalid';
        runtimeElements.detectionSummary.textContent = data.is_valid ? 'Valid ComfyUI installation detected' : (data.error || 'Structure not recognized');
        runtimeElements.detectionDetails.textContent = data.is_valid
            ? [`Comfy directory: ${data.comfy_dir}`, `Entry point: ${data.main_py}`, `Python: ${data.interpreter}`].join('\n')
            : `Path: ${data.root_path || config.install_path}\nError: ${data.error || 'Unknown'}`;
    } catch (error) {
        if (notify) showToast(error.message, 'error');
    } finally {
        runtimeElements.detect.disabled = false;
    }
}

async function updateRuntimeStatus(refreshEditor = false) {
    try {
        const data = await requestJson('/api/comfyui/status');
        renderRuntimeStatus(data);
        const wentOnline = !state.inventory.online && Boolean(data.online);
        updateRuntimePresence(data.online);
        if ((wentOnline || refreshEditor) && data.online) await refreshTemplates();
        if (data.mode === 'managed') fetchRuntimeLogs();
        return data;
    } catch (error) {
        renderRuntimeStatus({ status: 'stopped', online: false, last_error: error.message });
        updateRuntimePresence(false);
        return null;
    }
}

function renderRuntimeStatus(data) {
    const status = String(data.status || (data.online ? 'ready' : 'stopped')).toLowerCase();
    const title = status.charAt(0).toUpperCase() + status.slice(1);
    const detail = data.mode === 'managed'
        ? (data.pid ? `Managed process · PID ${data.pid}` : 'Managed process')
        : data.mode === 'external'
            ? 'External ComfyUI API connected'
            : (data.last_error || 'No process running');
    elements.runtimeHeaderStatus.textContent = data.online ? 'ComfyUI connected' : title;
    elements.runtimeHeaderDetail.textContent = data.online ? detail : 'Open runtime setup';
    elements.runtimeDrawerStatus.textContent = title;
    elements.runtimeDrawerDetail.textContent = detail;
    elements.runtimeHeaderDot.className = `runtime-state-dot status-${status}`;
    elements.runtimePill.className = `runtime-status-card status-${status}`;
    runtimeElements.mode.textContent = String(data.mode || 'none').toUpperCase();
    runtimeElements.status.textContent = status.toUpperCase();
    runtimeElements.pid.textContent = data.pid || '—';
    runtimeElements.endpoint.textContent = `${data.host || runtimeElements.host.value || '127.0.0.1'}:${data.port || runtimeElements.port.value || 8188}`;
    const remaining = Number(data.queue_info?.total_remaining || 0);
    runtimeElements.queue.textContent = data.online ? (remaining ? `${remaining} queued` : 'Idle') : 'Offline';
    runtimeElements.start.disabled = data.mode === 'managed' && ['ready', 'busy', 'starting'].includes(status);
    runtimeElements.stop.disabled = data.mode !== 'managed';
    runtimeElements.restart.disabled = !data.installation?.is_valid;
    runtimeElements.interrupt.disabled = !data.online;
    renderSystemStats(data.system_stats);
}

function renderSystemStats(stats) {
    if (!stats) {
        runtimeElements.stats.innerHTML = '<p class="no-stats-msg">System statistics appear when ComfyUI is online.</p>';
        return;
    }
    const system = stats.system || {};
    const devices = stats.devices || [];
    runtimeElements.stats.innerHTML = `<div class="system-stat-grid"><div><span>Platform</span><strong>${escapeHtml(system.os || 'Unknown')}</strong></div><div><span>Python</span><strong>${escapeHtml(system.python_version || 'Unknown')}</strong></div>${devices.map((device) => `<div><span>${escapeHtml(device.name || 'Device')}</span><strong>${device.vram_free ? `${(device.vram_free / 1073741824).toFixed(1)} GB free` : 'Ready'}</strong></div>`).join('')}</div>`;
}

async function fetchRuntimeLogs() {
    try {
        const data = await requestJson('/api/comfyui/logs?lines=300');
        if (data.logs?.length) {
            runtimeElements.logs.innerHTML = `<code>${escapeHtml(data.logs.join('\n'))}</code>`;
            if (runtimeElements.autoScroll.checked) runtimeElements.logs.parentElement.scrollTop = runtimeElements.logs.parentElement.scrollHeight;
        }
    } catch (error) {
        console.error('Could not fetch ComfyUI logs', error);
    }
}

async function runtimeAction(action, body = null) {
    const button = runtimeElements[action];
    if (button) button.disabled = true;
    try {
        const options = { method: 'POST' };
        if (body) {
            options.headers = { 'Content-Type': 'application/json' };
            options.body = JSON.stringify(body);
        }
        const data = await requestJson(`/api/comfyui/${action}`, options);
        showToast(action === 'interrupt' ? 'Interrupt sent to ComfyUI.' : `ComfyUI ${action} request accepted.`, 'success');
        await updateRuntimeStatus(true);
        return data;
    } catch (error) {
        showToast(error.message, 'error');
        return null;
    } finally {
        if (button) button.disabled = false;
    }
}

async function generateLauncher() {
    try {
        const data = await requestJson('/api/comfyui/launcher', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(runtimeConfigPayload()),
        });
        showToast(`Launcher saved to ${data.script_path}`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function refreshTemplates() {
    const selectedId = currentManifest()?.id;
    try {
        const payload = await requestJson('/api/editor/templates');
        state.templates = payload.templates || state.templates;
        state.inventory = payload.inventory || state.inventory;
        const selected = state.templates.find((item) => item.manifest.id === selectedId);
        if (selected) {
            state.selected = selected;
            renderResources();
        }
        updateRuntimePresence(state.inventory.online);
    } catch (error) {
        console.error('Could not refresh editor inventory', error);
    }
}

async function importTemplate(event) {
    event.preventDefault();
    const file = elements.importFile.files?.[0];
    if (!file) return;
    elements.importSubmit.disabled = true;
    const form = new FormData();
    form.append('file', file);
    try {
        const template = await requestJson('/api/editor/templates/import', { method: 'POST', body: form });
        const existing = state.templates.findIndex((item) => item.manifest.id === template.manifest.id);
        if (existing >= 0) state.templates[existing] = template;
        else state.templates.push(template);
        selectTemplate(template);
        elements.importDialog.close();
        showToast(`Imported ${template.manifest.name}.`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.importSubmit.disabled = false;
    }
}

async function inspectSourceWorkflow() {
    if (!state.draft?.source_asset_id) return;
    elements.sourceSummary.textContent = 'Inspecting embedded graph dependencies…';
    elements.sourceReport.innerHTML = '';
    elements.sourceJson.textContent = '';
    elements.sourceDialog.showModal();
    try {
        const payload = await requestJson(`/api/editor/assets/${state.draft.source_asset_id}/workflow`);
        elements.sourceSummary.textContent = payload.workflow
            ? `${payload.format?.toUpperCase()} workflow · ${payload.node_types.length} node types`
            : payload.message;
        elements.sourceReport.innerHTML = `<article class="dependency-card ${payload.runtime_online ? 'ready' : 'warning'}"><strong>Runtime comparison</strong><p>${payload.runtime_online ? 'Compared with the connected ComfyUI installation.' : 'Runtime offline; every embedded node is shown as unresolved.'}</p></article><article class="dependency-card ${payload.missing_nodes.length ? 'error' : 'ready'}"><strong>Missing node types</strong>${payload.missing_nodes.length ? `<ul>${payload.missing_nodes.map((node) => `<li>${escapeHtml(node)}</li>`).join('')}</ul>` : '<p>No missing node types.</p>'}</article>`;
        elements.sourceJson.textContent = payload.workflow ? JSON.stringify(payload.workflow, null, 2) : 'No embedded workflow.';
    } catch (error) {
        elements.sourceSummary.textContent = error.message;
        showToast(error.message, 'error');
    }
}

function bindEvents() {
    elements.categoryTabs.addEventListener('click', (event) => {
        const button = event.target.closest('[data-category]');
        if (!button || button.dataset.category === currentManifest()?.category) return;
        const template = state.templates.find((item) => item.manifest.category === button.dataset.category);
        if (template) selectTemplate(template);
    });
    elements.templateSelect.addEventListener('change', () => {
        const template = state.templates.find((item) => item.manifest.id === elements.templateSelect.value);
        if (template) selectTemplate(template);
    });
    elements.previewButton.addEventListener('click', () => previewWorkflow());
    elements.advancedOpen.addEventListener('click', () => elements.advancedDialog.showModal());
    elements.generateButton.addEventListener('click', generateWorkflow);
    elements.generateFromPreview.addEventListener('click', generateWorkflow);
    elements.cancelRun.addEventListener('click', cancelCurrentRun);
    elements.resultsRefresh.addEventListener('click', loadRuns);
    elements.runtimeOpen.addEventListener('click', openRuntimeDrawer);
    elements.runtimeConnect.addEventListener('click', openRuntimeDrawer);
    elements.runtimeClose.addEventListener('click', closeRuntimeDrawer);
    elements.runtimeBackdrop.addEventListener('click', closeRuntimeDrawer);
    elements.importOpen.addEventListener('click', () => elements.importDialog.showModal());
    elements.importFile.addEventListener('change', () => {
        const file = elements.importFile.files?.[0];
        elements.importName.textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : 'No file selected';
        elements.importSubmit.disabled = !file;
    });
    elements.importForm.addEventListener('submit', importTemplate);
    elements.sourceInspect.addEventListener('click', inspectSourceWorkflow);
    runtimeElements.save.addEventListener('click', saveRuntimeConfig);
    runtimeElements.detect.addEventListener('click', () => detectRuntime());
    runtimeElements.refresh.addEventListener('click', () => updateRuntimeStatus(true));
    runtimeElements.start.addEventListener('click', () => runtimeAction('start', runtimeConfigPayload()));
    runtimeElements.stop.addEventListener('click', () => runtimeAction('stop'));
    runtimeElements.restart.addEventListener('click', () => runtimeAction('restart', runtimeConfigPayload()));
    runtimeElements.interrupt.addEventListener('click', () => runtimeAction('interrupt'));
    runtimeElements.launcher.addEventListener('click', generateLauncher);
    runtimeElements.clearLogs.addEventListener('click', () => { runtimeElements.logs.innerHTML = '<code>[CMV] Console logs cleared.</code>'; });
    runtimeElements.refreshLogs.addEventListener('click', fetchRuntimeLogs);
    document.addEventListener('keydown', (event) => {
        if (event.key === 'Escape' && !elements.runtimeLayer.hidden) closeRuntimeDrawer();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') loadRuns();
    });
    window.addEventListener('focus', loadRuns);
    window.addEventListener('beforeunload', () => {
        window.clearTimeout(state.pollTimer);
        window.clearInterval(state.statusTimer);
    });
}

async function initialize() {
    bindEvents();
    await loadRuntimeConfig();
    await bootstrap();
    await updateRuntimeStatus();
    state.statusTimer = window.setInterval(() => updateRuntimeStatus(false), 4000);
}

initialize();
