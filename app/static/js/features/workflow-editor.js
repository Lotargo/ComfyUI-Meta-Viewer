import {
    closeLightbox,
    initLightboxEvents,
    nextLightbox,
    openLightbox,
    prevLightbox,
} from '../lightbox.js';

const byId = (id) => document.getElementById(id);

const elements = {
    categoryTabs: byId('template-category-tabs'),
    templateSelect: byId('template-select'),
    templateName: byId('template-name'),
    templateMeta: byId('template-meta'),
    templateDescription: byId('template-description'),
    sourceBanner: byId('source-draft-banner'),
    fields: byId('editor-fields'),
    contextFields: byId('context-fields'),
    advancedFields: byId('advanced-fields'),
    advancedCount: byId('advanced-count'),
    advancedOpen: byId('advanced-settings-open'),
    advancedDialog: byId('advanced-settings-dialog'),
    resourceSection: byId('resource-section'),
    workflowBackdrop: byId('workflow-backdrop'),
    resourceSlots: byId('resource-slots'),
    resourceCount: byId('resource-count'),
    additionalSettings: byId('additional-settings'),
    additionalModelCount: byId('additional-model-count'),
    additionalSettingsBackdrop: byId('additional-settings-backdrop'),
    advancedResourceSection: byId('advanced-resource-section'),
    advancedResourceSlots: byId('advanced-resource-slots'),
    advancedSettingsBackdrop: byId('advanced-settings-backdrop'),
    draftStatus: byId('draft-status'),
    validationSummary: byId('validation-summary'),
    previewButton: byId('preview-workflow'),
    previewButtonLabel: byId('preview-workflow-label'),
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
    runDiagnostic: byId('run-diagnostic'),
    runDiagnosticTitle: byId('run-diagnostic-title'),
    runDiagnosticMessage: byId('run-diagnostic-message'),
    runDiagnosticAction: byId('run-diagnostic-action'),
    runDiagnosticRaw: byId('run-diagnostic-raw'),
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
    importTitle: byId('template-import-title'),
    importLead: byId('template-import-lead'),
    importDropZone: byId('template-import-drop-zone'),
    importFile: byId('template-import-file'),
    importName: byId('template-import-name'),
    importAnalysis: byId('template-import-analysis'),
    importFields: byId('template-import-fields'),
    importDisplayName: byId('template-import-display-name'),
    importId: byId('template-import-id'),
    importDescription: byId('template-import-description'),
    importMapping: byId('template-import-mapping'),
    importMappingControls: byId('template-mapping-controls'),
    importMappingList: byId('template-mapping-list'),
    importMappingApply: byId('template-mapping-apply'),
    importManifestPreview: byId('template-manifest-preview'),
    importSubmit: byId('template-import-submit'),
    workflowManageOpen: byId('manage-workflows-open'),
    workflowManageDialog: byId('workflow-management-dialog'),
    workflowManageBody: byId('workflow-management-body'),
    workflowManageEmpty: byId('workflow-management-empty'),
    workflowManageSearch: byId('workflow-management-search'),
    workflowManageSource: byId('workflow-management-source'),
    workflowManageStatus: byId('workflow-management-status'),
    workflowRevalidateAll: byId('workflow-revalidate-all'),
    workflowMetadataDialog: byId('workflow-metadata-dialog'),
    workflowMetadataForm: byId('workflow-metadata-form'),
    workflowMetadataName: byId('workflow-metadata-name'),
    workflowMetadataDescription: byId('workflow-metadata-description'),
    sourceInspect: byId('analyze-source-workflow'),
    sourceDialog: byId('source-workflow-dialog'),
    sourceSummary: byId('source-workflow-summary'),
    sourceReport: byId('source-workflow-report'),
    sourceJson: byId('source-workflow-json'),
    aiPromptOpen: byId('ai-prompt-open'),
    aiPromptSummary: byId('ai-prompt-summary'),
    aiPromptDialog: byId('ai-prompt-dialog'),
    aiPromptForm: byId('ai-prompt-form'),
    aiPromptInput: byId('ai-prompt-input'),
    aiPromptFamily: byId('ai-prompt-family'),
    aiPromptScenario: byId('ai-prompt-scenario'),
    aiPromptProfile: byId('ai-prompt-profile'),
    aiPromptProfileNote: byId('ai-profile-note'),
    aiPromptSubmit: byId('ai-prompt-submit'),
    translatePromptOpen: byId('translate-prompt-open'),
    translatePromptDialog: byId('translate-prompt-dialog'),
    translatePromptForm: byId('translate-prompt-form'),
    translatePromptPositive: byId('translate-prompt-positive'),
    translatePromptNegative: byId('translate-prompt-negative'),
    translateSourceLanguage: byId('translate-source-language'),
    translateTargetLanguage: byId('translate-target-language'),
    translatePromptFamily: byId('translate-prompt-family'),
    translatePromptScenario: byId('translate-prompt-scenario'),
    translatePromptProfile: byId('translate-prompt-profile'),
    translateProfileNote: byId('translate-profile-note'),
    translatePromptSubmit: byId('translate-prompt-submit'),
    adaptPromptOpen: byId('adapt-prompt-open'),
    adaptPromptDialog: byId('adapt-prompt-dialog'),
    adaptPromptForm: byId('adapt-prompt-form'),
    adaptPromptPositive: byId('adapt-prompt-positive'),
    adaptPromptNegative: byId('adapt-prompt-negative'),
    adaptPromptFamily: byId('adapt-prompt-family'),
    adaptPromptScenario: byId('adapt-prompt-scenario'),
    adaptCheckpointProfile: byId('adapt-checkpoint-profile'),
    adaptPromptProfile: byId('adapt-prompt-profile'),
    adaptProfileNote: byId('adapt-profile-note'),
    adaptPromptSubmit: byId('adapt-prompt-submit'),
    reconstructPromptOpen: byId('reconstruct-prompt-open'),
    reconstructPromptDialog: byId('reconstruct-prompt-dialog'),
    reconstructPromptForm: byId('reconstruct-prompt-form'),
    reconstructPromptFamily: byId('reconstruct-prompt-family'),
    reconstructPromptScenario: byId('reconstruct-prompt-scenario'),
    reconstructVisionProfile: byId('reconstruct-vision-profile'),
    reconstructVisionNote: byId('reconstruct-vision-note'),
    reconstructAnalyze: byId('reconstruct-analyze'),
    reconstructSceneSpec: byId('reconstruct-scene-spec'),
    reconstructRenderProfile: byId('reconstruct-render-profile'),
    reconstructRenderNote: byId('reconstruct-render-note'),
    reconstructSourcePreview: byId('reconstruct-source-preview'),
    reconstructSourceLabel: byId('reconstruct-source-label'),
    reconstructPromptSubmit: byId('reconstruct-prompt-submit'),
    promptProvenanceDialog: byId('prompt-provenance-dialog'),
    promptProvenanceKicker: byId('prompt-provenance-kicker'),
    promptProvenanceTitle: byId('prompt-provenance-title'),
    promptProvenanceSummary: byId('prompt-provenance-summary'),
    promptResultLabel: byId('prompt-result-label'),
    promptSourcePositive: byId('prompt-source-positive'),
    promptSourceNegative: byId('prompt-source-negative'),
    promptTranslatedPositive: byId('prompt-translated-positive'),
    promptTranslatedNegative: byId('prompt-translated-negative'),
    toastContainer: byId('toast-container'),
    resetEditor: byId('reset-editor'),
    saveNote: byId('save-note'),
    editorSidebarToggle: byId('editor-sidebar-toggle'),
    collapseControls: byId('collapse-controls'),
    resultsSearch: byId('results-search'),
    batchPrompt: byId('batch-prompt'),
    sizeSummary: byId('size-summary'),
    aspectQuickControl: byId('aspect-quick-control'),
    aspectMore: byId('aspect-more'),
    aspectPopover: byId('aspect-popover'),
    aspectPopoverClose: byId('aspect-popover-close'),
    aspectCustomToggle: byId('aspect-custom-toggle'),
    customResolution: byId('custom-resolution'),
    customWidth: byId('custom-width'),
    customHeight: byId('custom-height'),
    customWidthRange: byId('custom-width-range'),
    customHeightRange: byId('custom-height-range'),
    customAspectRatio: byId('custom-aspect-ratio'),
    aspectRatioLock: byId('aspect-ratio-lock'),
    batchQuickControl: byId('batch-quick-control'),
    lightbox: byId('lightbox'),
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
    customResolutionOpen: false,
    aspectRatioLocked: true,
    lockedAspectRatio: 1,
    samplingMode: 'recommended',
    advancedFieldMemory: {},
    importPlan: null,
    importMapping: null,
    remappingWorkflowId: null,
    workflows: [],
    editingWorkflowId: null,
    aiCapabilities: [],
    aiProfiles: [],
    aiDefaultProfileId: null,
    aiDefaultMultimodalProfileId: null,
    aiPromptContext: null,
    aiPromptTranslation: null,
    aiPromptAdaptation: null,
    aiSceneSpec: null,
    aiSceneSpecJobId: null,
};

const ADVANCED_FIELD_IDS = new Set([
    'negative_prompt', 'width', 'height', 'batch_size', 'seed', 'steps', 'cfg',
    'sampler', 'scheduler', 'filename_prefix', 'denoise', 'frames', 'fps',
    'base_steps', 'refiner_steps', 'refiner_denoise', 'format', 'codec',
]);

const CREATE_WORKSPACE_STORAGE_KEY = 'cmv_create_workspace_v1';
const CREATE_WORKSPACE_VERSION = 1;
const IMPORT_DIALOG_LEAD = 'Current ComfyUI UI workflows and standard API workflows are mapped automatically. Template JSON bundles and ZIP archives keep their declared mappings.';

function readCreateWorkspace() {
    try {
        const parsed = JSON.parse(localStorage.getItem(CREATE_WORKSPACE_STORAGE_KEY) || 'null');
        if (
            parsed?.version !== CREATE_WORKSPACE_VERSION
            || !parsed.templates
            || typeof parsed.templates !== 'object'
            || Array.isArray(parsed.templates)
        ) {
            return { version: CREATE_WORKSPACE_VERSION, active_template_id: null, templates: {} };
        }
        return parsed;
    } catch {
        return { version: CREATE_WORKSPACE_VERSION, active_template_id: null, templates: {} };
    }
}

const createWorkspace = readCreateWorkspace();

function storedTemplateWorkspace(templateId) {
    const saved = createWorkspace.templates?.[templateId];
    return saved && typeof saved === 'object' ? saved : null;
}

function persistCreateWorkspace() {
    const manifest = currentManifest();
    if (!manifest || state.loadingTemplate) return;
    createWorkspace.active_template_id = manifest.id;
    createWorkspace.templates[manifest.id] = {
        template_version: manifest.version,
        draft: state.draft ? { ...state.draft } : null,
        ai_prompt_context: state.aiPromptContext ? { ...state.aiPromptContext } : null,
        ai_prompt_translation: state.aiPromptTranslation
            ? structuredClone(state.aiPromptTranslation)
            : null,
        ai_prompt_adaptation: state.aiPromptAdaptation
            ? structuredClone(state.aiPromptAdaptation)
            : null,
        ai_scene_spec: state.aiSceneSpec ? structuredClone(state.aiSceneSpec) : null,
        ai_scene_spec_job_id: state.aiSceneSpecJobId,
        values: { ...state.values },
        resources: { ...state.resources },
        ui: {
            sampling_mode: state.samplingMode,
            custom_resolution_open: state.customResolutionOpen,
            aspect_ratio_locked: state.aspectRatioLocked,
            locked_aspect_ratio: state.lockedAspectRatio,
            advanced_field_memory: { ...state.advancedFieldMemory },
        },
        updated_at: new Date().toISOString(),
    };
    try {
        localStorage.setItem(CREATE_WORKSPACE_STORAGE_KEY, JSON.stringify(createWorkspace));
    } catch {
        // Server-side drafts remain the fallback when local storage is unavailable.
    }
}

function restoreTemplateWorkspace(template, saved) {
    const manifest = template.manifest;
    const fieldIds = new Set((manifest.fields || []).map((field) => field.id));
    const slotIds = new Set(Object.keys(manifest.resource_slots || {}));
    const savedValues = Object.fromEntries(
        Object.entries(saved?.values || {}).filter(([fieldId]) => fieldIds.has(fieldId)),
    );
    const savedResources = Object.fromEntries(
        Object.entries(saved?.resources || {}).filter(([slotId]) => slotIds.has(slotId)),
    );
    state.draft = saved?.draft?.template_id === manifest.id ? { ...saved.draft } : null;
    state.aiPromptContext = state.draft && saved?.ai_prompt_context
        ? { ...saved.ai_prompt_context }
        : null;
    state.aiPromptTranslation = state.draft && saved?.ai_prompt_translation
        ? structuredClone(saved.ai_prompt_translation)
        : null;
    state.aiPromptAdaptation = state.draft && saved?.ai_prompt_adaptation
        ? structuredClone(saved.ai_prompt_adaptation)
        : null;
    state.aiSceneSpec = saved?.ai_scene_spec ? structuredClone(saved.ai_scene_spec) : null;
    state.aiSceneSpecJobId = Number(saved?.ai_scene_spec_job_id) || null;
    state.values = { ...template.defaults, ...savedValues };
    state.resources = {
        ...defaultResourceSelections(template),
        ...savedResources,
    };
    state.samplingMode = saved?.ui?.sampling_mode === 'custom' ? 'custom' : 'recommended';
    state.customResolutionOpen = Boolean(saved?.ui?.custom_resolution_open);
    state.aspectRatioLocked = saved?.ui?.aspect_ratio_locked !== false;
    state.lockedAspectRatio = Number(saved?.ui?.locked_aspect_ratio) > 0
        ? Number(saved.ui.locked_aspect_ratio)
        : 1;
    state.advancedFieldMemory = {
        ...(saved?.ui?.advanced_field_memory || {}),
        negative_prompt: saved?.ui?.advanced_field_memory?.negative_prompt
            || state.values.negative_prompt
            || template.defaults.negative_prompt
            || '',
        seed: Number(saved?.ui?.advanced_field_memory?.seed) >= 0
            ? Number(saved.ui.advanced_field_memory.seed)
            : (Number(state.values.seed) >= 0 ? Number(state.values.seed) : 0),
    };
}

function syncDraftUrl() {
    const url = state.draft?.id
        ? `/editor?draft_id=${encodeURIComponent(state.draft.id)}`
        : '/editor';
    history.replaceState({}, '', url);
}

function escapeHtml(value) {
    return String(value ?? '')
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function helpIcon(text) {
    const label = escapeHtml(text);
    return `<span class="help-icon" role="img" tabindex="0" aria-label="${label}" data-tooltip="${label}"><svg viewBox="0 0 24 24" aria-hidden="true"><circle cx="12" cy="12" r="9.5"/><path d="M9.25 9.1a2.9 2.9 0 1 1 5.55 1.2c-.45 1.25-1.65 1.6-2.35 2.35-.35.38-.45.78-.45 1.35"/><path d="M12 17.25h.01"/></svg></span>`;
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

const DECORATIVE_BACKDROP_BATCH_SIZE = 24;
let backdropAlignmentFrame = null;
let backdropResizeObserver = null;
let backdropMutationObserver = null;

function availableBackdropAssets(payload) {
    return (payload?.assets || []).filter((asset) => (
        asset.available
        && asset.thumbnail_url
        && Number(asset.width) > Number(asset.height)
    ));
}

function decorativeBackdropWindows() {
    return [
        { container: elements.resourceSection, image: elements.workflowBackdrop },
        {
            container: elements.additionalSettings?.querySelector(':scope > summary'),
            image: elements.additionalSettingsBackdrop,
        },
        { container: elements.advancedOpen, image: elements.advancedSettingsBackdrop },
    ].filter(({ container, image }) => container && image);
}

function alignDecorativeBackdrops() {
    backdropAlignmentFrame = null;
    const windows = decorativeBackdropWindows().map((entry) => ({
        ...entry,
        rect: entry.container.getBoundingClientRect(),
    })).filter(({ rect }) => rect.width > 0 && rect.height > 0);
    if (!windows.length) return;

    const planeTop = Math.min(...windows.map(({ rect }) => rect.top));
    const planeBottom = Math.max(...windows.map(({ rect }) => rect.bottom));
    const planeHeight = Math.max(1, planeBottom - planeTop);
    windows.forEach(({ image, rect }) => {
        image.style.setProperty('--mosaic-plane-height', `${planeHeight}px`);
        image.style.setProperty('--mosaic-window-offset', `${rect.top - planeTop}px`);
    });
}

function scheduleDecorativeBackdropAlignment() {
    if (backdropAlignmentFrame !== null) return;
    backdropAlignmentFrame = window.requestAnimationFrame(alignDecorativeBackdrops);
}

function observeDecorativeBackdropWindows() {
    const windows = decorativeBackdropWindows();
    if (!windows.length) return;
    if ('ResizeObserver' in window) {
        backdropResizeObserver = new ResizeObserver(scheduleDecorativeBackdropAlignment);
        windows.forEach(({ container }) => backdropResizeObserver.observe(container));
    }
    const controlsScroll = document.querySelector('.controls-scroll');
    if (controlsScroll && 'MutationObserver' in window) {
        backdropMutationObserver = new MutationObserver(scheduleDecorativeBackdropAlignment);
        backdropMutationObserver.observe(controlsScroll, {
            attributes: true,
            attributeFilter: ['class', 'hidden', 'open'],
            childList: true,
            subtree: true,
        });
    }
    window.addEventListener('resize', scheduleDecorativeBackdropAlignment, { passive: true });
    scheduleDecorativeBackdropAlignment();
}

function applyDecorativeBackdrop(target, asset) {
    target.addEventListener('load', () => {
        target.classList.add('is-ready');
        scheduleDecorativeBackdropAlignment();
    }, { once: true });
    target.addEventListener('error', () => {
        target.classList.remove('is-ready');
        target.removeAttribute('src');
    }, { once: true });
    target.src = asset.thumbnail_url;
}

async function loadDecorativeBackdrops() {
    const targets = [
        elements.workflowBackdrop,
        elements.additionalSettingsBackdrop,
        elements.advancedSettingsBackdrop,
    ].filter(Boolean);
    if (!targets.length) return;
    try {
        const buildUrl = (page) => {
            const params = new URLSearchParams({
                collection: 'images',
                orientation: 'landscape',
                page: String(page),
                per_page: String(DECORATIVE_BACKDROP_BATCH_SIZE),
                sort_by: 'date',
                sort_dir: 'desc',
            });
            return `/api/library/assets?${params}`;
        };

        const firstBatch = await requestJson(buildUrl(1));
        const total = Math.max(0, Number(firstBatch.total) || 0);
        if (!total) return;

        const pageCount = Math.max(1, Math.ceil(total / DECORATIVE_BACKDROP_BATCH_SIZE));
        const randomPage = Math.floor(Math.random() * pageCount) + 1;
        const randomBatch = randomPage === 1 ? firstBatch : await requestJson(buildUrl(randomPage));
        const candidates = [...new Map([
            ...availableBackdropAssets(randomBatch),
            ...availableBackdropAssets(firstBatch),
        ].map((asset) => [asset.id, asset])).values()];
        if (!candidates.length) return;

        const sharedAsset = candidates[Math.floor(Math.random() * candidates.length)];
        targets.forEach((target) => applyDecorativeBackdrop(target, sharedAsset));
        scheduleDecorativeBackdropAlignment();
    } catch {
        // The library artwork is decorative; keep the built-in fallback when unavailable.
    }
}

function iconSvg(kind) {
    const icons = {
        model: '<svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="1.8" fill="none"><path d="M12 3 4 7v10l8 4 8-4V7z"/><path d="m4 7 8 4 8-4M12 11v10"/></svg>',
        adapter: '<svg viewBox="0 0 24 24" width="15" height="15" stroke="currentColor" stroke-width="1.8" fill="none"><path d="M8 3v5m8-5v5M6 8h12v5a6 6 0 0 1-12 0zM12 19v2"/></svg>',
        open: '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M14 3h7v7M10 14 21 3M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"/></svg>',
        download: '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M12 3v12m-5-5 5 5 5-5M5 21h14"/></svg>',
        view: '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none"><path d="M8 3H3v5M16 3h5v5M8 21H3v-5M16 21h5v-5"/></svg>',
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
    clearRuntimeDiagnostic();
    state.previewReady = false;
    elements.generateFromPreview.disabled = true;
    updateValidation(null);
    setDraftStatus('Unsaved changes');
    updateWorkspaceSummary();
    persistCreateWorkspace();
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

        const urlParams = new URLSearchParams(window.location.search);
        const draftId = urlParams.get('draft_id');
        const requestedTemplateId = urlParams.get('template_id');
        if (draftId) {
            const draftPayload = await requestJson(`/api/editor/drafts/${encodeURIComponent(draftId)}`);
            const registered = state.templates.find((item) => item.manifest.id === draftPayload.draft.template_id);
            if (registered) {
                state.draft = draftPayload.draft;
                state.aiPromptContext = draftPayload.ai_prompt_context || null;
                state.aiPromptTranslation = draftPayload.ai_prompt_translation || null;
                state.aiPromptAdaptation = draftPayload.ai_prompt_adaptation || null;
                state.aiSceneSpec = draftPayload.ai_scene_spec || null;
                state.aiSceneSpecJobId = draftPayload.ai_scene_spec_job_id || null;
                state.values = { ...registered.defaults, ...draftPayload.draft.values };
                state.resources = { ...draftPayload.draft.resource_selections };
                selectTemplate(registered, { preserveDraft: true });
            } else {
                throw new Error(`Template ${draftPayload.draft.template_id} is no longer installed.`);
            }
        } else {
            const first = state.templates.find(
                (item) => item.manifest.id === requestedTemplateId,
            ) || state.templates.find(
                (item) => item.manifest.id === createWorkspace.active_template_id,
            ) || state.templates.find((item) => item.manifest.id === 'core-image') || state.templates[0];
            selectTemplate(first);
        }
        updateRuntimePresence(state.inventory.online);
        await loadRuns();
    } catch (error) {
        elements.fields.removeAttribute('aria-busy');
        elements.fields.innerHTML = `<div class="resource-card-empty">${escapeHtml(error.message)}</div>`;
        showToast(error.message, 'error');
    }
}

function selectTemplate(template, { preserveDraft = false } = {}) {
    clearRuntimeDiagnostic();
    if (state.selected && state.selected.manifest.id !== template.manifest.id) {
        persistCreateWorkspace();
    }
    window.clearTimeout(state.saveTimer);
    state.loadingTemplate = true;
    state.selected = template;
    if (!preserveDraft) {
        const saved = storedTemplateWorkspace(template.manifest.id);
        if (saved) {
            restoreTemplateWorkspace(template, saved);
        } else {
            state.draft = null;
            state.aiPromptContext = null;
            state.aiPromptTranslation = null;
            state.aiPromptAdaptation = null;
            state.aiSceneSpec = null;
            state.aiSceneSpecJobId = null;
            state.values = { ...template.defaults };
            state.resources = defaultResourceSelections(template);
            state.samplingMode = 'recommended';
            state.customResolutionOpen = false;
            state.aspectRatioLocked = true;
            state.advancedFieldMemory = {};
        }
    }
    if (Number(state.values.width) > 0 && Number(state.values.height) > 0) {
        state.lockedAspectRatio = Number(state.values.width) / Number(state.values.height);
    }
    state.samplingMode = state.samplingMode === 'custom' ? 'custom' : 'recommended';
    state.advancedFieldMemory = {
        ...state.advancedFieldMemory,
        negative_prompt: state.advancedFieldMemory.negative_prompt
            || state.values.negative_prompt
            || template.defaults.negative_prompt
            || '',
        seed: Number(state.advancedFieldMemory.seed) >= 0
            ? Number(state.advancedFieldMemory.seed)
            : (Number(state.values.seed) >= 0 ? Number(state.values.seed) : 0),
    };
    state.previewReady = false;
    renderTemplateNavigation();
    renderFields();
    renderResources();
    syncQuickControls();
    renderSourceBanner();
    updateValidation(null);
    setDraftStatus(state.draft ? `Draft #${state.draft.id}` : 'New draft');
    state.loadingTemplate = false;
    syncDraftUrl();
    persistCreateWorkspace();
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
    elements.templateSelect.innerHTML = state.templates
        .map((item) => `<option value="${escapeHtml(item.manifest.id)}"${item.manifest.id === manifest.id ? ' selected' : ''}>${escapeHtml(friendlyTemplateName(item.manifest))}</option>`)
        .join('');
    elements.templateName.textContent = friendlyTemplateName(manifest);
    elements.templateMeta.textContent = `${manifest.media_type} · v${manifest.version} · ${state.selected.source}`;
    elements.templateDescription.textContent = friendlyTemplateDescription(manifest);
    byId('controls-title').textContent = manifest.media_type === 'video' ? 'Video' : manifest.category === 'reference' ? 'Remix' : 'Image';
    updateGenerateAvailability();
}

function friendlyTemplateName(manifest) {
    const names = {
        'core-image': 'Basic image',
        'core-reference': 'Image remix',
        'core-video': 'Video generation',
        'core-two-stage': 'Two-stage refinement',
    };
    return names[manifest.id] || manifest.name;
}

function friendlyTemplateDescription(manifest) {
    const descriptions = {
        'core-image': 'A general-purpose text-to-image workflow built with standard ComfyUI nodes.',
        'core-reference': 'Reimagine a source image with adjustable transformation strength.',
        'core-video': 'Generate video locally with the selected ComfyUI models.',
        'core-two-stage': 'Base generation followed by a separate refinement pass for added detail.',
    };
    return descriptions[manifest.id] || manifest.description;
}

function renderFields() {
    const fields = (currentManifest().fields || []).filter((field) => !field.hidden);
    const regular = fields.filter((field) => !field.advanced && !ADVANCED_FIELD_IDS.has(field.id));
    const advanced = fields.filter((field) => field.advanced || ADVANCED_FIELD_IDS.has(field.id));
    const promptFields = regular.filter((field) => field.id === 'positive_prompt');
    const contextFields = regular.filter((field) => field.id !== 'positive_prompt');
    elements.fields.innerHTML = promptFields.map(renderField).join('');
    elements.fields.removeAttribute('aria-busy');
    elements.contextFields.innerHTML = contextFields.length ? renderFieldSections(contextFields, 1) : '';
    elements.advancedFields.innerHTML = renderAdvancedConfiguration(advanced);
    bindFieldEvents(elements.fields);
    bindFieldEvents(elements.contextFields);
    bindFieldEvents(elements.advancedFields);
    bindAdvancedConfigurationEvents(elements.advancedFields);
    updateAdvancedCount(advanced.length);
    syncQuickControls();
    updateWorkspaceSummary();
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

function samplingPresetLabel(sampler, scheduler) {
    const suffix = scheduler.value === 'normal' ? '' : ` ${scheduler.label}`;
    return `${sampler.label}${suffix}`;
}

function availableSamplingPresets(samplerField, schedulerField) {
    if (!samplerField || !schedulerField) return [];
    const samplers = new Map((samplerField.options || []).map((option) => [option.value, option]));
    const schedulers = new Map((schedulerField.options || []).map((option) => [option.value, option]));
    const preferredPairs = [
        ['dpmpp_2m', 'karras'],
        ['dpmpp_2m_sde', 'karras'],
        ['dpmpp_2m', 'normal'],
        ['dpmpp_2m_sde', 'normal'],
        ['euler', 'normal'],
        ['euler_ancestral', 'normal'],
        ['euler', 'karras'],
    ];
    const currentPair = [String(state.values.sampler || ''), String(state.values.scheduler || '')];
    const pairs = [currentPair, ...preferredPairs];
    for (const sampler of samplers.keys()) {
        pairs.push([sampler, schedulers.has('karras') ? 'karras' : schedulers.keys().next().value]);
    }

    const seen = new Set();
    return pairs.flatMap(([samplerId, schedulerId]) => {
        const sampler = samplers.get(samplerId);
        const scheduler = schedulers.get(schedulerId);
        const value = `${samplerId}::${schedulerId}`;
        if (!sampler || !scheduler || seen.has(value)) return [];
        seen.add(value);
        return [{
            value,
            sampler: samplerId,
            scheduler: schedulerId,
            label: samplingPresetLabel(sampler, scheduler),
        }];
    });
}

function renderAdvancedRange(field) {
    const value = state.values[field.id] ?? field.default ?? field.minimum ?? 0;
    const attributes = [
        `min="${escapeHtml(field.minimum ?? 0)}"`,
        `max="${escapeHtml(field.maximum ?? 100)}"`,
        `step="${escapeHtml(field.step ?? 1)}"`,
        `value="${escapeHtml(value)}"`,
        `data-field-id="${escapeHtml(field.id)}"`,
    ].join(' ');
    return `
        <div class="advanced-range-control">
            <span class="advanced-control-label">${escapeHtml(friendlyFieldLabel(field))}${helpIcon('Number of processing iterations. More steps can improve detail but increase generation time.')}</span>
            <div class="advanced-range-row">
                <input class="advanced-range" type="range" aria-label="${escapeHtml(friendlyFieldLabel(field))}" ${attributes}>
                <input class="advanced-range-value" type="number" inputmode="numeric" aria-label="${escapeHtml(friendlyFieldLabel(field))}, exact value" ${attributes}>
            </div>
        </div>
    `;
}

function renderAdvancedToggle(field, title, help) {
    const enabled = field.id === 'seed'
        ? Number(state.values[field.id]) >= 0
        : Boolean(String(state.values[field.id] || '').trim());
    return `
        <div class="advanced-toggle-control${enabled ? ' is-enabled' : ''}">
            <label class="advanced-switch-row">
                <span class="advanced-control-label">${escapeHtml(title)}${helpIcon(help)}</span>
                <input type="checkbox" data-advanced-toggle="${escapeHtml(field.id)}"${enabled ? ' checked' : ''}>
                <span class="advanced-switch" aria-hidden="true"></span>
            </label>
            ${enabled ? `<div class="advanced-toggle-detail">${renderField(field)}</div>` : ''}
        </div>
    `;
}

function renderAdvancedConfiguration(fields) {
    const byFieldId = new Map(fields.map((field) => [field.id, field]));
    const samplerField = byFieldId.get('sampler');
    const schedulerField = byFieldId.get('scheduler');
    const stepsField = byFieldId.get('steps');
    const negativeField = byFieldId.get('negative_prompt');
    const seedField = byFieldId.get('seed');
    const presets = availableSamplingPresets(samplerField, schedulerField);
    const currentPreset = `${state.values.sampler || ''}::${state.values.scheduler || ''}`;
    const selectedPreset = presets.some((preset) => preset.value === currentPreset)
        ? currentPreset
        : presets[0]?.value;
    const customMode = state.samplingMode === 'custom';
    const mirroredFields = new Set([
        'width', 'height', 'batch_size', 'sampler', 'scheduler', 'steps', 'negative_prompt', 'seed',
    ]);
    const extraFields = fields.filter((field) => !mirroredFields.has(field.id));

    return `
        <div class="advanced-config-card">
            ${samplerField && schedulerField ? `
                <div class="advanced-sampling-control">
                    <span class="advanced-control-label">Sampling method${helpIcon('Choose a recommended sampler and scheduler pair, or configure both values manually.')}</span>
                    <div class="advanced-mode-switch" role="group" aria-label="Sampler configuration mode">
                        <button type="button" data-sampling-mode="recommended"${customMode ? '' : ' class="active"'}>Recommended</button>
                        <button type="button" data-sampling-mode="custom"${customMode ? ' class="active"' : ''}>Custom</button>
                    </div>
                    <div class="advanced-recommended-sampling"${customMode ? ' hidden' : ''}>
                        <select data-sampling-preset aria-label="Recommended sampling method">
                            ${presets.map((preset) => `<option value="${escapeHtml(preset.value)}"${preset.value === selectedPreset ? ' selected' : ''}>${escapeHtml(preset.label)}</option>`).join('')}
                        </select>
                    </div>
                    <div class="advanced-custom-sampling"${customMode ? '' : ' hidden'}>
                        <label><span>Sampler</span>${renderFieldControl(samplerField)}</label>
                        <label><span>Scheduler</span>${renderFieldControl(schedulerField)}</label>
                    </div>
                </div>
            ` : ''}
            ${stepsField ? renderAdvancedRange(stepsField) : ''}
            ${negativeField ? renderAdvancedToggle(negativeField, 'Negative prompt', 'Describe elements and defects that should not appear in the result.') : ''}
            ${seedField ? renderAdvancedToggle(seedField, 'Fixed seed', 'Keep a specific seed so the generation can be reproduced.') : ''}
            ${extraFields.length ? `
                <details class="advanced-extra-fields">
                    <summary>Additional parameters<svg viewBox="0 0 24 24" aria-hidden="true"><path d="m8 10 4 4 4-4"/></svg></summary>
                    <div class="advanced-extra-grid">${extraFields.map(renderField).join('')}</div>
                </details>
            ` : ''}
        </div>
    `;
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
        positive_prompt: currentManifest()?.media_type === 'video' ? 'What should happen in the video?' : 'Describe the image',
        negative_prompt: 'Negative prompt',
        reference_image: 'Source image',
        width: 'Width',
        height: 'Height',
        batch_size: 'Number of images',
        seed: 'Fixed seed',
        steps: 'Sampling steps',
        cfg: 'Prompt strength (CFG)',
        sampler: 'Sampler',
        scheduler: 'Scheduler',
        filename_prefix: 'Filename prefix',
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

function renderFieldControl(field) {
    const value = state.values[field.id] ?? '';
    let control;
    const attributes = [
        `data-field-id="${escapeHtml(field.id)}"`,
        field.minimum !== null && field.minimum !== undefined ? `min="${field.minimum}"` : '',
        field.maximum !== null && field.maximum !== undefined ? `max="${field.maximum}"` : '',
        field.step !== null && field.step !== undefined ? `step="${field.step}"` : '',
        field.required ? 'required' : '',
    ].filter(Boolean).join(' ');

    if (field.kind === 'textarea') {
        const placeholder = field.id === 'positive_prompt' ? 'A cinematic scene with detailed lighting and rich textures…' : 'low quality, blurry, artifacts…';
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
    return control;
}

function renderField(field) {
    const classNames = ['editor-field', `field-${field.kind}`];
    if (field.id === 'positive_prompt') classNames.push('field-positive');
    if (field.id === 'negative_prompt') classNames.push('field-negative');
    const control = renderFieldControl(field);
    const help = field.id === 'positive_prompt' ? '' : field.description;
    return `<label class="${classNames.join(' ')}"><span class="field-label">${escapeHtml(friendlyFieldLabel(field))}${field.required ? ' *' : ''}</span>${control}${help ? `<small class="field-help">${escapeHtml(help)}</small>` : ''}</label>`;
}

function bindFieldEvents(container) {
    container.querySelectorAll('[data-field-id]').forEach((input) => {
        input.addEventListener('input', () => {
            const field = currentManifest().fields.find((item) => item.id === input.dataset.fieldId);
            state.values[input.dataset.fieldId] = field?.kind === 'number' || field?.kind === 'seed'
                ? (input.value === '' ? null : Number(input.value))
                : input.value;
            container.querySelectorAll(`[data-field-id="${CSS.escape(input.dataset.fieldId)}"]`).forEach((peer) => {
                if (peer !== input) peer.value = input.value;
            });
            if (input.dataset.fieldId === 'negative_prompt' && String(input.value).trim()) {
                state.advancedFieldMemory.negative_prompt = input.value;
            }
            if (input.dataset.fieldId === 'seed' && Number(input.value) >= 0) {
                state.advancedFieldMemory.seed = Number(input.value);
            }
            syncQuickControls();
            markDirty();
        });
    });
    container.querySelectorAll('[data-randomize]').forEach((button) => {
        button.addEventListener('click', () => {
            const id = button.dataset.randomize;
            const fixedSeedControl = id === 'seed' && button.closest('.advanced-toggle-detail');
            state.values[id] = fixedSeedControl
                ? Math.floor(Math.random() * 2147483647)
                : -1;
            if (fixedSeedControl) state.advancedFieldMemory.seed = state.values[id];
            const input = byId(`field-${id}`);
            if (input) input.value = String(state.values[id]);
            markDirty();
        });
    });
    container.querySelectorAll('[data-image-field]').forEach((input) => {
        input.addEventListener('change', () => uploadReference(input));
    });
}

function bindAdvancedConfigurationEvents(container) {
    container.querySelectorAll('[data-sampling-mode]').forEach((button) => {
        button.addEventListener('click', () => {
            const nextMode = button.dataset.samplingMode;
            if (state.samplingMode === nextMode) return;
            state.samplingMode = nextMode;
            renderFields();
        });
    });
    container.querySelector('[data-sampling-preset]')?.addEventListener('change', (event) => {
        const [sampler, scheduler] = event.target.value.split('::');
        if (!sampler || !scheduler) return;
        state.values.sampler = sampler;
        state.values.scheduler = scheduler;
        renderFields();
        markDirty();
    });
    container.querySelectorAll('[data-advanced-toggle]').forEach((toggle) => {
        toggle.addEventListener('change', () => {
            const id = toggle.dataset.advancedToggle;
            if (id === 'negative_prompt') {
                if (toggle.checked) {
                    const field = currentManifest().fields.find((item) => item.id === id);
                    state.values[id] = state.advancedFieldMemory[id] || field?.default || '';
                } else {
                    if (String(state.values[id] || '').trim()) state.advancedFieldMemory[id] = state.values[id];
                    state.values[id] = '';
                }
            }
            if (id === 'seed') {
                if (toggle.checked) {
                    state.values[id] = Number(state.advancedFieldMemory[id]) >= 0
                        ? Number(state.advancedFieldMemory[id])
                        : 0;
                } else {
                    if (Number(state.values[id]) >= 0) state.advancedFieldMemory[id] = Number(state.values[id]);
                    state.values[id] = -1;
                }
            }
            renderFields();
            markDirty();
        });
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
    const selectedOptionalCount = optionalSlots.reduce((total, [slotId]) => {
        const selection = state.resources[slotId];
        if (Array.isArray(selection)) return total + selection.length;
        return total + (typeof selection === 'string' ? Number(Boolean(selection)) : Number(Boolean(selection?.name)));
    }, 0);
    elements.resourceSection.hidden = requiredSlots.length === 0;
    elements.resourceCount.textContent = requiredSlots.length > 1 ? `${requiredSlots.length} models` : 'Required';
    elements.additionalModelCount.textContent = String(selectedOptionalCount);
    elements.additionalSettings.classList.toggle('has-selection', selectedOptionalCount > 0);
    elements.resourceSlots.innerHTML = requiredSlots.map(([slotId, slot]) => renderResourceSlot(slotId, slot)).join('');
    elements.advancedResourceSection.hidden = optionalSlots.length === 0;
    elements.advancedResourceSlots.innerHTML = optionalSlots.map(([slotId, slot]) => renderResourceSlot(slotId, slot)).join('');
    bindResourceEvents(elements.resourceSlots);
    bindResourceEvents(elements.advancedResourceSlots);
    const advancedFields = (currentManifest().fields || []).filter((field) => (
        !field.hidden && (field.advanced || ADVANCED_FIELD_IDS.has(field.id))
    ));
    updateAdvancedCount(advancedFields.length, optionalSlots.length);
    updateGenerateAvailability();
}

function updateAdvancedCount(fieldCount, resourceCount = null) {
    const optionalResources = resourceCount ?? Object.values(currentManifest()?.resource_slots || {}).filter((slot) => !slot.required).length;
    const total = fieldCount + optionalResources;
    elements.advancedCount.textContent = String(total);
}

function updateWorkspaceSummary() {
    const prompt = String(state.values.positive_prompt || '').trim();
    if (elements.batchPrompt) elements.batchPrompt.textContent = prompt || 'New results will appear here after generation';
    const width = state.values.width;
    const height = state.values.height;
    const size = width && height ? `${width} × ${height}` : currentManifest()?.media_type === 'video' ? 'Video' : 'Workflow size';
    if (elements.sizeSummary) elements.sizeSummary.textContent = size;
}

function dimensionLimits(id) {
    const field = currentManifest()?.fields?.find((item) => item.id === id);
    return {
        min: Number(field?.minimum ?? 64),
        max: Number(field?.maximum ?? 8192),
        step: Number(field?.step ?? 8),
    };
}

function normalizeDimension(id, rawValue) {
    const limits = dimensionLimits(id);
    const numeric = Number(rawValue);
    const fallback = Number(state.values[id] ?? limits.min);
    const value = Number.isFinite(numeric) ? numeric : fallback;
    const snapped = limits.min + Math.round((value - limits.min) / limits.step) * limits.step;
    return Math.min(limits.max, Math.max(limits.min, snapped));
}

function greatestCommonDivisor(left, right) {
    let a = Math.abs(Math.round(left));
    let b = Math.abs(Math.round(right));
    while (b) [a, b] = [b, a % b];
    return a || 1;
}

function formatAspectRatio(ratio, width, height) {
    const common = [
        [1 / 2, '1:2'], [9 / 16, '9:16'], [2 / 3, '2:3'], [3 / 4, '3:4'], [4 / 5, '4:5'],
        [1, '1:1'], [5 / 4, '5:4'], [4 / 3, '4:3'], [3 / 2, '3:2'], [16 / 9, '16:9'], [2, '2:1'],
    ];
    const known = common.find(([value]) => Math.abs(ratio - value) / value < 0.015);
    if (known) return known[1];
    const divisor = greatestCommonDivisor(width, height);
    return `${Math.round(width / divisor)}:${Math.round(height / divisor)}`;
}

function currentAspectRatio() {
    const selectedPreset = document.querySelector(
        '[data-aspect-grid] [data-width].active, [data-aspect-popover] [data-width].active',
    );
    const presetWidth = Number(selectedPreset?.dataset.width);
    const presetHeight = Number(selectedPreset?.dataset.height);
    if (presetWidth > 0 && presetHeight > 0) return presetWidth / presetHeight;

    const width = Number(state.values.width);
    const height = Number(state.values.height);
    return width > 0 && height > 0 ? width / height : 1;
}

function captureLockedAspectRatio() {
    if (!state.aspectRatioLocked) return;
    state.lockedAspectRatio = currentAspectRatio();
}

function updateCustomResolutionControls() {
    const width = Number(state.values.width);
    const height = Number(state.values.height);
    if (!elements.customResolution || !Number.isFinite(width) || !Number.isFinite(height)) return;
    elements.customResolution.hidden = !state.customResolutionOpen;
    elements.aspectCustomToggle?.setAttribute('aria-expanded', state.customResolutionOpen ? 'true' : 'false');

    const controls = [
        [elements.customWidth, 'width', width],
        [elements.customWidthRange, 'width', width],
        [elements.customHeight, 'height', height],
        [elements.customHeightRange, 'height', height],
    ];
    controls.forEach(([control, id, value]) => {
        if (!control) return;
        const limits = dimensionLimits(id);
        control.min = String(limits.min);
        control.max = String(limits.max);
        control.step = String(limits.step);
        control.value = String(value);
    });

    elements.aspectRatioLock?.classList.toggle('active', state.aspectRatioLocked);
    elements.aspectRatioLock?.setAttribute('aria-pressed', state.aspectRatioLocked ? 'true' : 'false');
    elements.aspectRatioLock?.setAttribute(
        'aria-label',
        state.aspectRatioLocked ? 'Unlock aspect ratio' : 'Lock aspect ratio',
    );
    const displayedRatio = state.aspectRatioLocked ? state.lockedAspectRatio : width / height;
    if (elements.customAspectRatio) {
        elements.customAspectRatio.value = formatAspectRatio(displayedRatio, width, height);
    }
}

function updateDimensionValues(width, height, { dirty = true } = {}) {
    state.values.width = normalizeDimension('width', width);
    state.values.height = normalizeDimension('height', height);
    const advancedWidth = byId('field-width');
    const advancedHeight = byId('field-height');
    if (advancedWidth) advancedWidth.value = String(state.values.width);
    if (advancedHeight) advancedHeight.value = String(state.values.height);
    syncQuickControls();
    if (dirty) markDirty();
}

function applyCustomDimension(id, rawValue) {
    const ratio = Number(state.lockedAspectRatio) > 0
        ? Number(state.lockedAspectRatio)
        : Number(state.values.width) / Number(state.values.height);
    let width = Number(state.values.width);
    let height = Number(state.values.height);
    if (id === 'width') {
        width = normalizeDimension('width', rawValue);
        if (state.aspectRatioLocked) height = normalizeDimension('height', width / ratio);
    } else {
        height = normalizeDimension('height', rawValue);
        if (state.aspectRatioLocked) width = normalizeDimension('width', height * ratio);
    }
    updateDimensionValues(width, height);
}

function syncQuickControls() {
    if (!currentManifest()) return;
    const fieldIds = new Set((currentManifest().fields || [])
        .filter((field) => !field.hidden)
        .map((field) => field.id));
    const hasSize = fieldIds.has('width') && fieldIds.has('height');
    const hasBatch = fieldIds.has('batch_size');
    const quickMode = document.querySelector('[data-quick-mode]')?.closest('.quick-control');
    if (quickMode) quickMode.hidden = !fieldIds.has('steps');
    if (elements.aspectQuickControl) elements.aspectQuickControl.hidden = !hasSize;
    if (elements.batchQuickControl) elements.batchQuickControl.hidden = !hasBatch;
    let quickAspectMatch = false;
    document.querySelectorAll('[data-aspect-grid] [data-width]').forEach((button) => {
        const active = Number(button.dataset.width) === Number(state.values.width)
            && Number(button.dataset.height) === Number(state.values.height);
        button.classList.toggle('active', active);
        quickAspectMatch ||= active;
    });
    document.querySelectorAll('[data-aspect-popover] [data-width]').forEach((button) => {
        const active = Number(button.dataset.width) === Number(state.values.width)
            && Number(button.dataset.height) === Number(state.values.height);
        button.classList.toggle('active', active);
    });
    elements.aspectMore?.classList.toggle('active', hasSize && !quickAspectMatch);
    if (!hasSize) {
        closeAspectPopover();
        state.customResolutionOpen = false;
    }
    updateCustomResolutionControls();
    document.querySelectorAll('[data-batch-grid] [data-batch]').forEach((button) => {
        button.classList.toggle('active', Number(button.dataset.batch) === Number(state.values.batch_size));
    });
    const defaultSteps = Number(state.selected?.defaults?.steps ?? 28);
    document.querySelectorAll('[data-quick-mode] [data-mode]').forEach((button) => {
        const quality = Number(state.values.steps) > defaultSteps;
        button.classList.toggle('active', button.dataset.mode === (quality ? 'quality' : 'standard'));
    });
    updateWorkspaceSummary();
}

function applyAspectSize(button) {
    if (!button || !currentManifest()) return;
    const width = normalizeDimension('width', button.dataset.width);
    const height = normalizeDimension('height', button.dataset.height);
    state.lockedAspectRatio = width / height;
    updateDimensionValues(width, height);
}

function positionAspectPopover() {
    if (!elements.aspectPopover || elements.aspectPopover.hidden || !elements.aspectMore) return;
    const anchor = elements.aspectMore.getBoundingClientRect();
    const popover = elements.aspectPopover;
    const gutter = 10;
    const edge = 12;
    const width = Math.min(304, window.innerWidth - edge * 2);
    popover.style.width = `${width}px`;
    const measured = popover.getBoundingClientRect();
    const preferredLeft = anchor.right + gutter;
    const left = preferredLeft + width <= window.innerWidth - edge
        ? preferredLeft
        : Math.max(edge, anchor.left - width - gutter);
    const top = Math.min(
        Math.max(edge, anchor.top - 52),
        Math.max(edge, window.innerHeight - measured.height - edge),
    );
    popover.style.left = `${Math.round(left)}px`;
    popover.style.top = `${Math.round(top)}px`;
}

function openAspectPopover() {
    if (!elements.aspectPopover || !elements.aspectMore) return;
    elements.aspectPopover.hidden = false;
    elements.aspectMore.setAttribute('aria-expanded', 'true');
    window.requestAnimationFrame(positionAspectPopover);
}

function closeAspectPopover() {
    if (!elements.aspectPopover || !elements.aspectMore || elements.aspectPopover.hidden) return;
    elements.aspectPopover.hidden = true;
    elements.aspectMore.setAttribute('aria-expanded', 'false');
}

function toggleCustomResolution() {
    state.customResolutionOpen = !state.customResolutionOpen;
    if (state.customResolutionOpen) captureLockedAspectRatio();
    updateCustomResolutionControls();
}

function resetEditor() {
    if (!state.selected) return;
    state.values = { ...state.selected.defaults };
    state.resources = defaultResourceSelections(state.selected);
    if (Number(state.values.width) > 0 && Number(state.values.height) > 0) {
        state.lockedAspectRatio = Number(state.values.width) / Number(state.values.height);
    }
    state.samplingMode = 'recommended';
    state.advancedFieldMemory = {
        negative_prompt: state.values.negative_prompt || '',
        seed: Number(state.values.seed) >= 0 ? Number(state.values.seed) : 0,
    };
    renderFields();
    renderResources();
    markDirty();
    showToast('Settings restored to the workflow defaults.', 'info');
}

function accordionPanel(details) {
    return details.id === 'additional-settings'
        ? details.querySelector(':scope > .advanced-resource-section')
        : details.querySelector(':scope > .advanced-settings-scroll');
}

function positionAccordionFlyout(details) {
    if (!details) return;
    const panel = accordionPanel(details);
    if (!panel) return;
    panel.style.removeProperty('left');
    panel.style.removeProperty('width');
    panel.style.removeProperty('top');
    panel.style.removeProperty('bottom');
    panel.style.removeProperty('max-height');
}

function bindAccordionFlyouts() {
    const accordions = [...document.querySelectorAll('.editor-controls > .controls-scroll .sidebar-accordion')];
    const flyouts = accordions.filter((details) => details.id !== 'advanced-settings-dialog');
    const reposition = () => flyouts.filter((details) => details.open).forEach(positionAccordionFlyout);
    flyouts.forEach((details) => {
        details.addEventListener('toggle', () => {
            if (!details.open) return;
            flyouts.forEach((other) => {
                if (other !== details) other.open = false;
            });
            window.requestAnimationFrame(() => positionAccordionFlyout(details));
        });
    });
    document.addEventListener('pointerdown', (event) => {
        flyouts.forEach((details) => {
            if (details.open && !details.contains(event.target)) details.open = false;
        });
    });
    window.addEventListener('resize', reposition);
    document.querySelector('.controls-scroll')?.addEventListener('scroll', reposition, { passive: true });
    reposition();
}

function resourceCompatibilityStatus(option) {
    return option?.compatibility_status || 'supported';
}

function resourceOptionLabel(option) {
    const labels = {
        limited: 'Limited',
        experimental: 'Experimental',
    };
    const suffix = labels[resourceCompatibilityStatus(option)];
    return `${friendlyResourceName(option.name)}${suffix ? ` · ${suffix}` : ''}`;
}

function renderSelectableResourceOptions(options, selected = '') {
    const selectable = options.filter((option) => resourceCompatibilityStatus(option) !== 'incompatible');
    const persistedIncompatible = options.find((option) => (
        option.name === selected && resourceCompatibilityStatus(option) === 'incompatible'
    ));
    return [
        ...selectable.map((option) => `<option value="${escapeHtml(option.name)}"${selected === option.name ? ' selected' : ''}>${escapeHtml(resourceOptionLabel(option))}</option>`),
        persistedIncompatible
            ? `<option value="${escapeHtml(persistedIncompatible.name)}" selected disabled>${escapeHtml(friendlyResourceName(persistedIncompatible.name))} · Incompatible</option>`
            : '',
    ].join('');
}

function renderResourceCompatibility(option) {
    const status = resourceCompatibilityStatus(option);
    if (!option || status === 'supported' || !option.compatibility_reason) return '';
    const label = status === 'incompatible' ? 'Incompatible' : status === 'limited' ? 'Limited support' : 'Needs verification';
    return `<div class="resource-compatibility ${escapeHtml(status)}"><strong>${label}</strong><span>${escapeHtml(option.compatibility_reason)}</span></div>`;
}

function renderIncompatibleResources(options) {
    const incompatible = options.filter((option) => resourceCompatibilityStatus(option) === 'incompatible');
    if (!incompatible.length) return '';
    return `<details class="resource-incompatible-list"><summary>${incompatible.length} incompatible ${incompatible.length === 1 ? 'model' : 'models'} hidden</summary><ul>${incompatible.map((option) => `<li><strong>${escapeHtml(friendlyResourceName(option.name))}</strong><span>${escapeHtml(option.compatibility_reason || 'This model is not compatible with the active workflow.')}</span></li>`).join('')}</ul></details>`;
}

function renderResourceSlot(slotId, slot) {
    const options = state.selected.resource_options?.[slotId] || [];
    const kind = slot.multiple ? 'adapter' : 'model';
    const label = slotId.includes('checkpoint') && !slotId.includes('refiner') ? 'Model' : slot.label;
    const description = slot.required
        ? (slot.description || 'Local model used for generation.')
        : (slot.description || 'Optional style adapter.');
    const head = `<div class="resource-card-head"><div><span class="resource-kind-icon">${iconSvg(kind)}</span><div><strong>${escapeHtml(label)}</strong><small>${escapeHtml(description)}</small></div></div></div>`;
    if (!options.length) {
        return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<div class="resource-card-empty">No models match this resource type. Check the connection and your ComfyUI folder.</div></div>`;
    }
    if (slot.multiple) {
        const selections = Array.isArray(state.resources[slotId]) ? state.resources[slotId] : [];
        return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<div class="lora-add-row"><select data-lora-option="${escapeHtml(slotId)}"><option value="">Select LoRA…</option>${renderSelectableResourceOptions(options)}</select><button class="btn btn-secondary btn-sm" type="button" data-lora-add="${escapeHtml(slotId)}">Add</button></div>${renderIncompatibleResources(options)}<div class="lora-list">${selections.map((selection, index) => renderLora(slotId, selection, index, options.find((option) => option.name === (typeof selection === 'string' ? selection : selection.name)))).join('')}</div></div>`;
    }
    const selected = typeof state.resources[slotId] === 'string'
        ? state.resources[slotId]
        : state.resources[slotId]?.name || '';
    const selectedOption = options.find((option) => option.name === selected);
    return `<div class="resource-card" data-slot="${escapeHtml(slotId)}">${head}<select data-resource-slot="${escapeHtml(slotId)}"><option value="">${slot.required ? 'Select model…' : 'None'}</option>${renderSelectableResourceOptions(options, selected)}</select>${renderResourceCompatibility(selectedOption)}${renderIncompatibleResources(options)}</div>`;
}

function renderLora(slotId, selection, index, option = null) {
    const normalized = typeof selection === 'string'
        ? { name: selection, strength_model: 1, strength_clip: 1 }
        : selection;
    return `<div class="lora-card"><span class="lora-card-name" title="${escapeHtml(normalized.name)}">${escapeHtml(friendlyResourceName(normalized.name))}</span><input type="number" min="-5" max="5" step="0.05" value="${escapeHtml(normalized.strength_model ?? 1)}" data-lora-strength="${escapeHtml(slotId)}" data-lora-index="${index}" title="Style strength"><button class="lora-remove" type="button" data-lora-remove="${escapeHtml(slotId)}" data-lora-index="${index}" aria-label="Remove add-on">×</button>${renderResourceCompatibility(option)}</div>`;
}

function bindResourceEvents(container) {
    container.querySelectorAll('[data-resource-slot]').forEach((select) => {
        select.addEventListener('change', () => {
            state.resources[select.dataset.resourceSlot] = select.value;
            renderResources();
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
    state.aiPromptContext = payload.ai_prompt_context || null;
    state.aiPromptTranslation = payload.ai_prompt_translation || null;
    state.aiPromptAdaptation = payload.ai_prompt_adaptation || null;
    state.aiSceneSpec = payload.ai_scene_spec || null;
    state.aiSceneSpecJobId = payload.ai_scene_spec_job_id || null;
    syncDraftUrl();
    persistCreateWorkspace();
    renderSourceBanner();
    return state.draft;
}

async function saveDraft({ recoverMissing = true } = {}) {
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
        state.aiPromptContext = payload.ai_prompt_context || state.aiPromptContext;
        state.aiPromptTranslation = payload.ai_prompt_translation || state.aiPromptTranslation;
        state.aiPromptAdaptation = payload.ai_prompt_adaptation || state.aiPromptAdaptation;
        state.aiSceneSpec = payload.ai_scene_spec || state.aiSceneSpec;
        state.aiSceneSpecJobId = payload.ai_scene_spec_job_id || state.aiSceneSpecJobId;
        persistCreateWorkspace();
        setDraftStatus(`Saved · #${state.draft.id}`, 'saved');
    } catch (error) {
        if (recoverMissing && error.code === 'workflow_draft_not_found') {
            state.draft = null;
            state.aiPromptContext = null;
            state.aiPromptTranslation = null;
            state.aiPromptAdaptation = null;
            state.aiSceneSpec = null;
            state.aiSceneSpecJobId = null;
            syncDraftUrl();
            persistCreateWorkspace();
            return saveDraft({ recoverMissing: false });
        }
        setDraftStatus('Save failed', 'error');
        showToast(error.message, 'error');
        throw error;
    }
}

function renderSourceBanner() {
    const fromAsset = Boolean(state.draft?.source_asset_id);
    const fromAI = Boolean(state.draft?.ai_prompt_draft_id);
    elements.sourceBanner.hidden = !fromAsset && !fromAI;
    if (!fromAsset && !fromAI) return;
    const title = elements.sourceBanner.querySelector('strong');
    const detail = elements.sourceBanner.querySelector('span');
    const operation = state.aiPromptContext?.operation;
    const reconstructed = operation === 'reconstruct' && Boolean(state.aiSceneSpec);
    if (fromAsset) {
        title.textContent = reconstructed ? 'AI reconstructed prompt' : 'Remix draft';
        detail.textContent = reconstructed
            ? 'The prompt was rendered from an editable SceneSpec, separately from embedded metadata.'
            : 'The prompt and source were imported from the library.';
        elements.sourceInspect.hidden = false;
        elements.sourceInspect.textContent = reconstructed ? 'SceneSpec' : 'Source';
    } else {
        title.textContent = operation === 'translate'
            ? 'Translated prompt'
            : (operation === 'adapt' ? 'Adapted prompt' : 'AI prompt draft');
        detail.textContent = operation === 'translate'
            ? 'Source and translated prompts are stored separately. ComfyUI has not been started.'
            : (operation === 'adapt'
                ? 'Source and family-adapted prompts are stored separately. ComfyUI has not been started.'
                : 'The generated prompt is editable. ComfyUI has not been started.');
        elements.sourceInspect.hidden = !(
            (operation === 'translate' && state.aiPromptTranslation)
            || (operation === 'adapt' && state.aiPromptAdaptation)
        );
        elements.sourceInspect.textContent = 'Compare';
    }
}

function openPromptProvenance() {
    const translation = state.aiPromptTranslation;
    const adaptation = state.aiPromptAdaptation;
    if (!translation && !adaptation) return;
    const provenance = translation || adaptation;
    const result = translation ? translation.translated : adaptation.adapted;
    if (translation) {
        const sourceLabel = translation.source_language || 'auto-detected';
        elements.promptProvenanceKicker.textContent = 'Saved translation';
        elements.promptProvenanceTitle.textContent = 'Source and translated prompt';
        elements.promptProvenanceSummary.textContent = `${sourceLabel} → ${translation.target_language}`;
        elements.promptResultLabel.textContent = 'Translation';
    } else {
        const checkpoint = adaptation.checkpoint_profile
            ? ` · ${adaptation.checkpoint_profile}`
            : '';
        elements.promptProvenanceKicker.textContent = 'Saved family adaptation';
        elements.promptProvenanceTitle.textContent = 'Source and adapted prompt';
        elements.promptProvenanceSummary.textContent = `Target: ${adaptation.target_family.toUpperCase()}${checkpoint}`;
        elements.promptResultLabel.textContent = 'Adaptation';
    }
    elements.promptSourcePositive.textContent = provenance.source.positive_prompt;
    elements.promptSourceNegative.textContent = provenance.source.negative_prompt || '—';
    elements.promptTranslatedPositive.textContent = result.positive_prompt;
    elements.promptTranslatedNegative.textContent = result.negative_prompt || '—';
    elements.promptProvenanceDialog.showModal();
}

function inspectDraftSource() {
    if (state.aiPromptContext?.operation === 'reconstruct' && state.aiSceneSpec) {
        openReconstructPromptDialog();
        return;
    }
    if (state.draft?.source_asset_id) {
        inspectSourceWorkflow();
        return;
    }
    openPromptProvenance();
}

function suggestedPromptFamily() {
    const ecosystems = currentManifest()?.supported_ecosystems || [];
    if (ecosystems.some((item) => String(item).startsWith('flux'))) return 'flux';
    if (ecosystems.some((item) => ['sdxl', 'illustrious'].includes(item))) return 'sdxl';
    if (ecosystems.includes('pony')) return 'pony';
    return 'sdxl';
}

function supportedPromptProfile(profile) {
    return profile.kind === 'openai_compatible'
        || (profile.kind === 'cli' && profile.cli_type === 'opencode');
}

async function loadPromptAssistantData() {
    const [capabilities, profiles] = await Promise.all([
        requestJson('/api/ai/prompt-capabilities'),
        requestJson('/api/ai/profiles'),
    ]);
    state.aiCapabilities = capabilities.families || [];
    state.aiProfiles = (profiles.profiles || []).filter((profile) => (
        profile.has_credentials !== false && supportedPromptProfile(profile)
    ));
    state.aiDefaultProfileId = profiles.defaults?.text_profile_id || null;
    state.aiDefaultMultimodalProfileId = profiles.defaults?.multimodal_profile_id || null;
}

function populatePromptFamilies(select) {
    select.innerHTML = state.aiCapabilities.map((family) => (
        `<option value="${escapeHtml(family.id)}">${escapeHtml(family.id.toUpperCase())}</option>`
    )).join('');
    const suggested = suggestedPromptFamily();
    if (state.aiCapabilities.some((family) => family.id === suggested)) select.value = suggested;
}

function populatePromptProfiles(select, note) {
    select.innerHTML = state.aiProfiles.length
        ? state.aiProfiles.map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(profile.model)}</option>`).join('')
        : '<option value="">No ready text profiles</option>';
    if (state.aiProfiles.some((profile) => profile.id === state.aiDefaultProfileId)) {
        select.value = state.aiDefaultProfileId;
    }
    note.innerHTML = state.aiProfiles.length
        ? 'The selected profile returns the same normalized prompt contract.'
        : 'Add a usable text profile in <a href="/settings/ai">AI settings</a> first.';
}

function populateVisionProfiles(select, note) {
    const profiles = state.aiProfiles.filter((profile) => (
        profile.multimodal === true && (
            profile.kind === 'openai_compatible'
            || (profile.kind === 'cli' && profile.cli_type === 'opencode')
        )
    ));
    select.innerHTML = profiles.length
        ? profiles.map((profile) => `<option value="${escapeHtml(profile.id)}">${escapeHtml(profile.name)} · ${escapeHtml(profile.model)}</option>`).join('')
        : '<option value="">No ready multimodal profiles</option>';
    if (profiles.some((profile) => profile.id === state.aiDefaultMultimodalProfileId)) {
        select.value = state.aiDefaultMultimodalProfileId;
    }
    note.innerHTML = profiles.length
        ? 'The image is sent only during Analyze image.'
        : 'Add an OpenAI-compatible or OpenCode multimodal profile in <a href="/settings/ai">AI settings</a> first.';
}

function compatibleScenarios(familyId) {
    const family = state.aiCapabilities.find((item) => item.id === familyId);
    return (family?.scenarios || []).filter((item) => (
        ['supported', 'limited', 'experimental'].includes(item.status)
    ));
}

function renderScenarioOptions(select, familyId) {
    const available = compatibleScenarios(familyId);
    select.innerHTML = available.map((item) => {
        const label = item.id.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase());
        const suffix = item.status === 'supported' ? '' : ` · ${item.status}`;
        return `<option value="${escapeHtml(item.id)}">${escapeHtml(label + suffix)}</option>`;
    }).join('');
    return available;
}

function renderAIScenarios() {
    const available = renderScenarioOptions(elements.aiPromptScenario, elements.aiPromptFamily.value);
    elements.aiPromptSubmit.disabled = !available.length || !elements.aiPromptProfile.value;
}

function renderTranslationScenarios() {
    const available = renderScenarioOptions(
        elements.translatePromptScenario,
        elements.translatePromptFamily.value,
    );
    elements.translatePromptSubmit.disabled = (
        !available.length || !elements.translatePromptProfile.value
    );
}

function renderAdaptationScenarios() {
    const available = renderScenarioOptions(
        elements.adaptPromptScenario,
        elements.adaptPromptFamily.value,
    );
    elements.adaptPromptSubmit.disabled = (
        !available.length || !elements.adaptPromptProfile.value
    );
}

function renderReconstructionScenarios() {
    const available = renderScenarioOptions(
        elements.reconstructPromptScenario,
        elements.reconstructPromptFamily.value,
    );
    elements.reconstructAnalyze.disabled = (
        !state.draft?.source_asset_id || !elements.reconstructVisionProfile.value
    );
    elements.reconstructPromptSubmit.disabled = (
        !available.length || !elements.reconstructRenderProfile.value
        || !state.aiSceneSpecJobId || !elements.reconstructSceneSpec.value.trim()
    );
}

async function openAIPromptDialog() {
    elements.aiPromptOpen.disabled = true;
    try {
        await loadPromptAssistantData();
        populatePromptFamilies(elements.aiPromptFamily);
        populatePromptProfiles(elements.aiPromptProfile, elements.aiPromptProfileNote);
        elements.aiPromptInput.value = String(state.values.positive_prompt || '');
        renderAIScenarios();
        elements.aiPromptDialog.showModal();
        elements.aiPromptInput.focus();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.aiPromptOpen.disabled = false;
    }
}

function activateAIPromptDraft(created, statusLabel, toastMessage) {
    state.draft = created.draft;
    state.aiPromptContext = created.ai_prompt_context || null;
    state.aiPromptTranslation = created.ai_prompt_translation || null;
    state.aiPromptAdaptation = created.ai_prompt_adaptation || null;
    state.aiSceneSpec = created.ai_scene_spec || null;
    state.aiSceneSpecJobId = created.ai_scene_spec_job_id || null;
    state.values = { ...state.values, ...created.draft.values };
    state.advancedFieldMemory.negative_prompt = state.values.negative_prompt || '';
    renderFields();
    renderSourceBanner();
    setDraftStatus(`${statusLabel} · #${state.draft.id}`, 'saved');
    syncDraftUrl();
    persistCreateWorkspace();
    showToast(toastMessage, 'success');
}

async function createAIPromptDraft(event) {
    event.preventDefault();
    const userInput = elements.aiPromptInput.value.trim();
    if (!userInput || !elements.aiPromptProfile.value || !elements.aiPromptScenario.value) return;
    elements.aiPromptSubmit.disabled = true;
    elements.aiPromptSubmit.textContent = 'Creating…';
    try {
        const generated = await requestJson('/api/ai/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: elements.aiPromptProfile.value,
                user_input: userInput,
                task: {
                    family: elements.aiPromptFamily.value,
                    scenario: elements.aiPromptScenario.value,
                },
            }),
        });
        const created = await requestJson('/api/editor/drafts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_id: currentManifest().id,
                values: state.values,
                resource_selections: state.resources,
                ai_prompt_draft_id: generated.prompt_draft.id,
            }),
        });
        activateAIPromptDraft(
            created,
            'AI draft',
            'AI prompt draft created. Review it before generation.',
        );
        elements.aiPromptDialog.close();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.aiPromptSubmit.textContent = 'Create draft';
        renderAIScenarios();
    }
}

async function openTranslatePromptDialog() {
    elements.translatePromptOpen.disabled = true;
    try {
        await loadPromptAssistantData();
        populatePromptFamilies(elements.translatePromptFamily);
        populatePromptProfiles(elements.translatePromptProfile, elements.translateProfileNote);
        elements.translatePromptPositive.value = String(state.values.positive_prompt || '');
        elements.translatePromptNegative.value = String(
            state.values.negative_prompt || state.advancedFieldMemory.negative_prompt || '',
        );
        renderTranslationScenarios();
        elements.translatePromptDialog.showModal();
        elements.translatePromptPositive.focus();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.translatePromptOpen.disabled = false;
    }
}

async function createTranslatedPromptDraft(event) {
    event.preventDefault();
    const positivePrompt = elements.translatePromptPositive.value.trim();
    const targetLanguage = elements.translateTargetLanguage.value.trim();
    if (
        !positivePrompt || !targetLanguage || !elements.translatePromptProfile.value
        || !elements.translatePromptScenario.value
    ) return;
    elements.translatePromptSubmit.disabled = true;
    elements.translatePromptSubmit.textContent = 'Translating…';
    try {
        const translated = await requestJson('/api/ai/translate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: elements.translatePromptProfile.value,
                source_language: elements.translateSourceLanguage.value.trim() || null,
                target_language: targetLanguage,
                source: {
                    positive_prompt: positivePrompt,
                    negative_prompt: elements.translatePromptNegative.value.trim(),
                },
                task: {
                    family: elements.translatePromptFamily.value,
                    scenario: elements.translatePromptScenario.value,
                },
            }),
        });
        const created = await requestJson('/api/editor/drafts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_id: currentManifest().id,
                values: state.values,
                resource_selections: state.resources,
                ai_prompt_draft_id: translated.prompt_draft.id,
            }),
        });
        activateAIPromptDraft(
            created,
            'Translated draft',
            'Translation saved as a new draft. Review it before generation.',
        );
        elements.translatePromptDialog.close();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.translatePromptSubmit.textContent = 'Translate to draft';
        renderTranslationScenarios();
    }
}

async function openAdaptPromptDialog() {
    elements.adaptPromptOpen.disabled = true;
    try {
        await loadPromptAssistantData();
        populatePromptFamilies(elements.adaptPromptFamily);
        populatePromptProfiles(elements.adaptPromptProfile, elements.adaptProfileNote);
        elements.adaptPromptPositive.value = String(state.values.positive_prompt || '');
        elements.adaptPromptNegative.value = String(
            state.values.negative_prompt || state.advancedFieldMemory.negative_prompt || '',
        );
        elements.adaptCheckpointProfile.value = '';
        renderAdaptationScenarios();
        elements.adaptPromptDialog.showModal();
        elements.adaptPromptPositive.focus();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.adaptPromptOpen.disabled = false;
    }
}

async function createAdaptedPromptDraft(event) {
    event.preventDefault();
    const positivePrompt = elements.adaptPromptPositive.value.trim();
    if (
        !positivePrompt || !elements.adaptPromptProfile.value
        || !elements.adaptPromptScenario.value || !elements.adaptPromptFamily.value
    ) return;
    elements.adaptPromptSubmit.disabled = true;
    elements.adaptPromptSubmit.textContent = 'Adapting…';
    try {
        const adapted = await requestJson('/api/ai/adapt', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: elements.adaptPromptProfile.value,
                target_family: elements.adaptPromptFamily.value,
                checkpoint_profile: elements.adaptCheckpointProfile.value.trim() || null,
                source: {
                    positive_prompt: positivePrompt,
                    negative_prompt: elements.adaptPromptNegative.value.trim(),
                },
                task: {
                    family: elements.adaptPromptFamily.value,
                    scenario: elements.adaptPromptScenario.value,
                },
            }),
        });
        const created = await requestJson('/api/editor/drafts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_id: currentManifest().id,
                values: state.values,
                resource_selections: state.resources,
                ai_prompt_draft_id: adapted.prompt_draft.id,
            }),
        });
        activateAIPromptDraft(
            created,
            'Adapted draft',
            'Family adaptation saved as a new draft. Review it before generation.',
        );
        elements.adaptPromptDialog.close();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.adaptPromptSubmit.textContent = 'Adapt to draft';
        renderAdaptationScenarios();
    }
}

async function openReconstructPromptDialog() {
    if (!state.draft?.source_asset_id && !state.aiSceneSpec) {
        showToast('Open an image from the Viewer with Remix before reconstruction.', 'info');
        return;
    }
    elements.reconstructPromptOpen.disabled = true;
    try {
        await loadPromptAssistantData();
        populatePromptFamilies(elements.reconstructPromptFamily);
        populatePromptProfiles(elements.reconstructRenderProfile, elements.reconstructRenderNote);
        populateVisionProfiles(elements.reconstructVisionProfile, elements.reconstructVisionNote);
        if (state.aiPromptContext?.family) {
            elements.reconstructPromptFamily.value = state.aiPromptContext.family;
        }
        renderReconstructionScenarios();
        if (state.aiPromptContext?.scenario) {
            elements.reconstructPromptScenario.value = state.aiPromptContext.scenario;
        } else if (state.aiSceneSpec?.recommended_scenario) {
            elements.reconstructPromptScenario.value = state.aiSceneSpec.recommended_scenario;
        }
        elements.reconstructSceneSpec.value = state.aiSceneSpec
            ? JSON.stringify(state.aiSceneSpec, null, 2)
            : '';
        const assetId = state.draft?.source_asset_id;
        elements.reconstructSourcePreview.hidden = !assetId;
        if (assetId) elements.reconstructSourcePreview.src = `/api/thumbnail/${assetId}`;
        elements.reconstructSourceLabel.textContent = assetId ? `Library asset #${assetId}` : 'Saved SceneSpec';
        renderReconstructionScenarios();
        elements.reconstructPromptDialog.showModal();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.reconstructPromptOpen.disabled = false;
    }
}

async function analyzeReconstructionScene() {
    const assetId = state.draft?.source_asset_id;
    if (!assetId || !elements.reconstructVisionProfile.value) return;
    elements.reconstructAnalyze.disabled = true;
    elements.reconstructAnalyze.textContent = 'Analyzing…';
    try {
        const analyzed = await requestJson('/api/ai/reconstruct/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: elements.reconstructVisionProfile.value,
                asset_id: assetId,
                task: {
                    family: elements.reconstructPromptFamily.value,
                    scenario: elements.reconstructPromptScenario.value,
                },
            }),
        });
        state.aiSceneSpec = analyzed.scene_spec;
        state.aiSceneSpecJobId = analyzed.job.id;
        elements.reconstructSceneSpec.value = JSON.stringify(analyzed.scene_spec, null, 2);
        if (analyzed.scene_spec.recommended_scenario) {
            const supported = compatibleScenarios(elements.reconstructPromptFamily.value)
                .some((item) => item.id === analyzed.scene_spec.recommended_scenario);
            if (supported) elements.reconstructPromptScenario.value = analyzed.scene_spec.recommended_scenario;
        }
        persistCreateWorkspace();
        showToast('SceneSpec created. Review uncertain details before rendering.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.reconstructAnalyze.textContent = 'Analyze image';
        renderReconstructionScenarios();
    }
}

async function createReconstructedPromptDraft(event) {
    event.preventDefault();
    if (!state.aiSceneSpecJobId || !elements.reconstructRenderProfile.value) return;
    let sceneSpec;
    try {
        sceneSpec = JSON.parse(elements.reconstructSceneSpec.value);
    } catch {
        showToast('SceneSpec must be valid JSON.', 'error');
        return;
    }
    elements.reconstructPromptSubmit.disabled = true;
    elements.reconstructPromptSubmit.textContent = 'Rendering…';
    try {
        await requestJson(`/api/ai/jobs/${state.aiSceneSpecJobId}/scene-spec`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ scene_spec: sceneSpec }),
        });
        const rendered = await requestJson('/api/ai/reconstruct', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: elements.reconstructRenderProfile.value,
                scene_spec_job_id: state.aiSceneSpecJobId,
                asset_id: state.draft?.source_asset_id || null,
                task: {
                    family: elements.reconstructPromptFamily.value,
                    scenario: elements.reconstructPromptScenario.value,
                },
            }),
        });
        const created = await requestJson('/api/editor/drafts', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                template_id: currentManifest().id,
                values: state.values,
                resource_selections: state.resources,
                source_asset_id: state.draft?.source_asset_id || null,
                ai_prompt_draft_id: rendered.prompt_draft.id,
            }),
        });
        activateAIPromptDraft(
            created,
            'Reconstructed draft',
            'SceneSpec rendered to an editable prompt. Review it before generation.',
        );
        elements.reconstructPromptDialog.close();
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.reconstructPromptSubmit.textContent = 'Render to draft';
        renderReconstructionScenarios();
    }
}

async function previewWorkflow({ openDialog = true } = {}) {
    elements.previewButton.disabled = true;
    elements.previewButton.classList.add('is-loading');
    elements.previewButton.setAttribute('aria-busy', 'true');
    elements.previewButtonLabel.textContent = 'Checking dependencies…';
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
        elements.previewButton.classList.remove('is-loading');
        elements.previewButton.removeAttribute('aria-busy');
        elements.previewButtonLabel.textContent = 'Check dependencies and preview graph';
    }
}

function updateValidation(report, explicitError = '') {
    let mode = 'neutral';
    const missing = requiredConfigurationIssues();
    let text = state.inventory.online
        ? (missing.length ? missing[0] : 'Ready to generate')
        : 'Connect ComfyUI to generate';
    if (report?.ready) {
        mode = 'ready';
        text = 'Ready to generate';
    } else if (report) {
        mode = 'error';
        const total = (report.missing_nodes?.length || 0) + (report.missing_resources?.length || 0);
        text = total ? 'Required ComfyUI files are missing' : (report.runtime_error || 'ComfyUI could not validate the workflow');
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
    if (!currentManifest()) return ['Select a generation type'];
    for (const field of currentManifest().fields || []) {
        if (field.required && (state.values[field.id] === '' || state.values[field.id] === null || state.values[field.id] === undefined)) {
            return [`Complete “${friendlyFieldLabel(field)}”`];
        }
    }
    for (const [slotId, slot] of Object.entries(currentManifest().resource_slots || {})) {
        const value = state.resources[slotId];
        if (slot.required && (!value || (Array.isArray(value) && !value.length))) {
            const label = slotId.includes('checkpoint') ? 'model' : slot.label.toLowerCase();
            return [`Select ${label} to continue`];
        }
    }
    return [];
}

function updateGenerateAvailability() {
    if (!elements.generateButton) return;
    const media = currentManifest()?.media_type === 'video' ? 'video' : 'image';
    const running = state.currentRun && ['queued', 'running'].includes(state.currentRun.status);
    elements.generateLabel.textContent = state.inventory.online ? (media === 'video' ? 'Create video' : 'Create') : 'Connect';
    elements.generateHelp.textContent = state.inventory.online
        ? 'The result will be saved to the library automatically.'
        : 'Connect your local ComfyUI installation to start generating.';
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

function clearRuntimeDiagnostic() {
    elements.runDiagnostic.hidden = true;
    document.querySelectorAll('[data-runtime-invalid]').forEach((control) => {
        control.removeAttribute('aria-invalid');
        control.removeAttribute('data-runtime-invalid');
    });
    document.querySelectorAll('.runtime-field-error').forEach((target) => {
        target.classList.remove('runtime-field-error');
    });
    document.querySelectorAll('[data-runtime-error]').forEach((message) => message.remove());
}

function runtimeFieldTarget(fieldId) {
    const selector = `[data-field-id="${CSS.escape(fieldId)}"]`;
    const control = document.querySelector(selector)
        || document.querySelector(`[data-advanced-toggle="${CSS.escape(fieldId)}"]`);
    if (control) {
        return {
            control,
            container: control.closest('.editor-field, .advanced-range-control, .advanced-toggle-control'),
        };
    }
    if (fieldId === 'width' || fieldId === 'height') {
        return {
            control: fieldId === 'width' ? elements.customWidth : elements.customHeight,
            container: elements.aspectQuickControl,
        };
    }
    if (fieldId === 'batch_size') {
        return {
            control: elements.batchQuickControl?.querySelector('button'),
            container: elements.batchQuickControl,
        };
    }
    return { control: null, container: null };
}

function runtimeResourceTarget(slotId) {
    const container = document.querySelector(`.resource-card[data-slot="${CSS.escape(slotId)}"]`);
    return {
        control: container?.querySelector('select, input, button') || null,
        container,
    };
}

function showRuntimeDiagnostic(diagnostic) {
    if (!diagnostic || typeof diagnostic !== 'object') return;
    clearRuntimeDiagnostic();
    const nodeLocation = [
        diagnostic.class_type,
        diagnostic.node_id ? `node ${diagnostic.node_id}` : '',
        diagnostic.input_name ? `input ${diagnostic.input_name}` : '',
    ].filter(Boolean).join(' · ');
    elements.runDiagnosticTitle.textContent = diagnostic.message || 'ComfyUI could not complete the workflow.';
    elements.runDiagnosticMessage.textContent = nodeLocation || 'The workflow stopped during execution.';
    elements.runDiagnosticAction.textContent = diagnostic.suggested_action || 'Review the settings and retry.';
    elements.runDiagnosticRaw.textContent = JSON.stringify(diagnostic.raw || diagnostic, null, 2);
    elements.runDiagnostic.hidden = false;

    let firstTarget = null;
    const decorated = new Set();
    for (const target of diagnostic.editor_targets || []) {
        if (target.advanced && target.kind === 'field') elements.advancedDialog.open = true;
        if (target.advanced && target.kind === 'resource') elements.additionalSettings.open = true;
        const resolved = target.kind === 'resource'
            ? runtimeResourceTarget(target.id)
            : runtimeFieldTarget(target.id);
        if (!resolved.container) continue;
        firstTarget ||= resolved.control || resolved.container;
        resolved.container.classList.add('runtime-field-error');
        if (resolved.control?.matches('input, textarea, select')) {
            resolved.control.setAttribute('aria-invalid', 'true');
            resolved.control.setAttribute('data-runtime-invalid', 'true');
        }
        if (decorated.has(resolved.container)) continue;
        decorated.add(resolved.container);
        const message = document.createElement('small');
        message.className = 'runtime-field-error-message';
        message.dataset.runtimeError = 'true';
        message.textContent = diagnostic.message;
        resolved.container.appendChild(message);
    }
    const focusTarget = firstTarget || elements.runDiagnostic;
    window.requestAnimationFrame(() => {
        focusTarget.scrollIntoView({ behavior: 'smooth', block: 'center' });
        firstTarget?.focus?.({ preventScroll: true });
    });
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
    clearRuntimeDiagnostic();
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
        if (error.data?.diagnostic) showRuntimeDiagnostic(error.data.diagnostic);
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
            if (state.currentRun.status === 'failed') showToast(state.currentRun.error?.message || 'ComfyUI reported a failed workflow.', 'error');
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
    if (run.status === 'failed' && run.error) showRuntimeDiagnostic(run.error);
    else if (run.status !== 'failed') clearRuntimeDiagnostic();
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

function runOutputIsVideo(run) {
    return (run.output_refs || []).some((ref) => {
        const mediaKey = String(ref.media_key || '').toLowerCase();
        const filename = String(ref.filename || '').toLowerCase();
        return mediaKey.includes('video') || /\.(mp4|webm|mov|m4v|mkv|avi)$/.test(filename);
    });
}

function resultLightboxAssets() {
    return state.runs.flatMap((run) => (run.output_asset_ids || []).map((assetId) => ({
        id: Number(assetId),
        media_type: runOutputIsVideo(run) ? 'video' : 'image',
        file_name: `Generation #${run.id}`,
    })));
}

async function openResultLightbox(assetId) {
    const assets = resultLightboxAssets();
    const index = assets.findIndex((asset) => asset.id === Number(assetId));
    if (index < 0) return;
    await openLightbox(index, assets);
}

function resultCard(run, assetId) {
    const isVideo = runOutputIsVideo(run);
    const media = isVideo
        ? `<video src="/api/original/${assetId}" preload="metadata" controls></video>`
        : `<img src="/api/preview/${assetId}" alt="Generated result ${assetId}" loading="lazy" data-open-result="${assetId}">`;
    return `<article class="result-card" data-result-search="generation ${run.id}"><div class="result-media">${media}<div class="result-card-actions"><button type="button" data-open-result="${assetId}" title="View result" aria-label="View generation ${run.id}">${iconSvg('view')}</button><a href="/api/original/${assetId}" download title="Download">${iconSvg('download')}</a><a href="/library" title="Open in library">${iconSvg('open')}</a></div></div><div class="result-card-meta"><strong>Generation #${run.id}</strong><span>In library</span></div></article>`;
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
    elements.runtimeHeaderStatus.textContent = 'ComfyUI';
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

function workflowStatusLabel(status) {
    return String(status || 'warning').replace(/_/g, ' ');
}

function formatValidationDate(value) {
    if (!value) return 'Never';
    const date = new Date(value);
    return Number.isNaN(date.getTime()) ? value : date.toLocaleString();
}

function renderWorkflowRegistry() {
    const query = elements.workflowManageSearch.value.trim().toLocaleLowerCase();
    const source = elements.workflowManageSource.value;
    const status = elements.workflowManageStatus.value;
    const workflows = state.workflows.filter((workflow) => {
        const haystack = `${workflow.name} ${workflow.id} ${workflow.description}`.toLocaleLowerCase();
        return (!query || haystack.includes(query))
            && (!source || workflow.source === source)
            && (!status || workflow.validation.status === status);
    });
    elements.workflowManageBody.innerHTML = workflows.map((workflow) => {
        const validation = workflow.validation || {};
        const valid = validation.status !== 'invalid';
        const editable = workflow.source === 'user' && valid;
        const removable = workflow.source === 'user';
        return `<tr data-workflow-id="${escapeHtml(workflow.id)}"><td><strong>${escapeHtml(workflow.name)}</strong><small>${escapeHtml(workflow.description || workflow.id)}</small></td><td>${escapeHtml(workflow.category)} · ${escapeHtml(workflow.media_type)}</td><td>${escapeHtml((workflow.ecosystems || []).join(', ') || 'Unknown')}</td><td>${escapeHtml(workflow.loader_family)}</td><td>${escapeHtml(workflow.source === 'user' ? 'Imported' : 'Built-in')}</td><td><span class="workflow-status-badge ${escapeHtml(validation.status)}">${escapeHtml(workflowStatusLabel(validation.status))}</span><small title="${escapeHtml(validation.reason)}">${escapeHtml(validation.reason)}</small></td><td>${escapeHtml(formatValidationDate(validation.last_validated_at))}<small>${validation.inventory_fingerprint ? `Inventory ${escapeHtml(validation.inventory_fingerprint.slice(0, 8))}` : 'No inventory fingerprint'}</small></td><td>Schema ${escapeHtml(workflow.manifest_version)}<small>Template ${escapeHtml(workflow.template_version)}</small></td><td><span class="workflow-management-actions"><button class="btn btn-ghost btn-sm" type="button" data-workflow-action="open"${valid ? '' : ' disabled'}>Open</button><button class="btn btn-ghost btn-sm" type="button" data-workflow-action="revalidate"${valid ? '' : ' disabled'}>Check</button>${editable ? '<button class="btn btn-ghost btn-sm" type="button" data-workflow-action="remap">Map</button><button class="btn btn-ghost btn-sm" type="button" data-workflow-action="edit">Edit</button>' : ''}${removable ? '<button class="btn btn-danger btn-sm" type="button" data-workflow-action="delete">Delete</button>' : ''}</span></td></tr>`;
    }).join('');
    elements.workflowManageEmpty.hidden = workflows.length > 0;
}

async function loadWorkflowRegistry({ open = false } = {}) {
    if (open) elements.workflowManageDialog.showModal();
    elements.workflowManageBody.innerHTML = '<tr><td colspan="9">Loading workflow registry…</td></tr>';
    try {
        const payload = await requestJson('/api/editor/workflows');
        state.workflows = payload.workflows || [];
        renderWorkflowRegistry();
    } catch (error) {
        elements.workflowManageBody.innerHTML = `<tr><td colspan="9">${escapeHtml(error.message)}</td></tr>`;
        showToast(error.message, 'error');
    }
}

async function revalidateWorkflow(templateId) {
    const row = elements.workflowManageBody.querySelector(`[data-workflow-id="${CSS.escape(templateId)}"]`);
    row?.classList.add('is-loading');
    try {
        const payload = await requestJson(`/api/editor/workflows/${encodeURIComponent(templateId)}/revalidate`, {
            method: 'POST',
        });
        const workflow = state.workflows.find((item) => item.id === templateId);
        if (workflow) workflow.validation = payload.validation;
        renderWorkflowRegistry();
        showToast(`Validated ${workflow?.name || templateId}.`, payload.validation.status === 'ready' ? 'success' : 'info');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function revalidateAllWorkflows() {
    elements.workflowRevalidateAll.disabled = true;
    try {
        const payload = await requestJson('/api/editor/workflows/revalidate', { method: 'POST' });
        state.workflows = payload.workflows || [];
        state.inventory = payload.inventory || state.inventory;
        renderWorkflowRegistry();
        showToast('Workflow registry revalidated.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.workflowRevalidateAll.disabled = false;
    }
}

function openWorkflowMetadata(templateId) {
    const workflow = state.workflows.find((item) => item.id === templateId);
    if (!workflow || workflow.source !== 'user') return;
    state.editingWorkflowId = templateId;
    elements.workflowMetadataName.value = workflow.name;
    elements.workflowMetadataDescription.value = workflow.description || '';
    elements.workflowMetadataDialog.showModal();
}

function resetImportDialogMode() {
    state.remappingWorkflowId = null;
    state.importPlan = null;
    state.importMapping = null;
    elements.importForm.reset();
    elements.importTitle.textContent = 'Import workflow';
    elements.importLead.textContent = IMPORT_DIALOG_LEAD;
    elements.importDropZone.hidden = false;
    elements.importName.hidden = false;
    elements.importName.textContent = 'No file selected';
    elements.importDisplayName.disabled = false;
    elements.importId.disabled = false;
    elements.importDescription.disabled = false;
    elements.importSubmit.textContent = 'Import';
    elements.importSubmit.disabled = true;
    elements.importAnalysis.hidden = true;
    elements.importFields.hidden = true;
    elements.importMapping.hidden = true;
}

function renderImportPlan(plan, mapping, { remap = false, preserveMetadata = false } = {}) {
    state.importPlan = plan;
    state.importMapping = mapping || defaultImportMapping(plan);
    const manifest = plan.manifest;
    if (!preserveMetadata) {
        elements.importDisplayName.value = manifest.name || '';
        elements.importId.value = manifest.id || '';
        elements.importDescription.value = manifest.description || '';
    }
    elements.importFields.hidden = false;
    elements.importAnalysis.hidden = false;
    const fieldCount = plan.mappings.filter((item) => item.kind === 'field').length;
    const resourceCount = plan.mappings.filter((item) => item.kind === 'resource').length;
    const format = {
        api_workflow: 'ComfyUI API workflow',
        ui_workflow: 'ComfyUI UI workflow',
        registered_workflow: 'Registered workflow',
        template_bundle: 'Template bundle',
    }[plan.source_format] || 'Workflow';
    const warnings = (plan.warnings || []).length
        ? `<ul>${plan.warnings.map((warning) => `<li>${escapeHtml(warning)}</li>`).join('')}</ul>`
        : '';
    const readyMessage = remap
        ? 'The updated mappings are ready to save.'
        : 'The workflow is ready to register.';
    elements.importAnalysis.innerHTML = `<strong>${escapeHtml(format)} · ${escapeHtml(manifest.loader_family)}</strong><span>${fieldCount} editor bindings and ${resourceCount} model bindings detected. ${plan.ready ? readyMessage : 'Manual mapping is required before registration.'}</span>${warnings}`;
    elements.importAnalysis.classList.toggle('error', !plan.ready);
    renderImportMapping(plan);
    elements.importMappingApply.textContent = plan.ready ? 'Mappings applied' : 'Apply mappings';
    elements.importSubmit.disabled = !plan.ready;
}

async function openWorkflowRemap(templateId) {
    const workflow = state.workflows.find((item) => item.id === templateId);
    if (!workflow || workflow.source !== 'user') return;
    resetImportDialogMode();
    state.remappingWorkflowId = templateId;
    elements.importTitle.textContent = `Remap ${workflow.name}`;
    elements.importLead.textContent = 'Review semantic fields, model roles, and the primary output without replacing the saved workflow graph.';
    elements.importDropZone.hidden = true;
    elements.importName.hidden = true;
    elements.importDisplayName.disabled = true;
    elements.importId.disabled = true;
    elements.importDescription.disabled = true;
    elements.importSubmit.textContent = 'Save mappings';
    elements.importAnalysis.hidden = false;
    elements.importAnalysis.innerHTML = '<strong>Loading saved workflow…</strong><span>Reconstructing the current mapping selections.</span>';
    elements.workflowManageDialog.close();
    elements.importDialog.showModal();
    try {
        const payload = await requestJson(`/api/editor/workflows/${encodeURIComponent(templateId)}/mapping`);
        renderImportPlan(payload.plan, payload.mapping, { remap: true });
    } catch (error) {
        elements.importAnalysis.classList.add('error');
        elements.importAnalysis.innerHTML = `<strong>Cannot remap this workflow</strong><span>${escapeHtml(error.message)}</span>`;
        showToast(error.message, 'error');
    }
}

async function saveWorkflowMetadata(event) {
    event.preventDefault();
    if (!state.editingWorkflowId) return;
    try {
        const template = await requestJson(`/api/editor/templates/${encodeURIComponent(state.editingWorkflowId)}`, {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                name: elements.workflowMetadataName.value.trim(),
                description: elements.workflowMetadataDescription.value.trim(),
            }),
        });
        const index = state.templates.findIndex((item) => item.manifest.id === state.editingWorkflowId);
        if (index >= 0) state.templates[index] = template;
        if (currentManifest()?.id === state.editingWorkflowId) selectTemplate(template, { preserveDraft: true });
        elements.workflowMetadataDialog.close();
        await loadWorkflowRegistry();
        showToast('Workflow metadata updated.', 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function deleteManagedWorkflow(templateId) {
    const workflow = state.workflows.find((item) => item.id === templateId);
    if (!workflow || workflow.source !== 'user') return;
    if (!window.confirm(`Delete imported workflow “${workflow.name}”? Models and ComfyUI files will not be changed.`)) return;
    try {
        await requestJson(`/api/editor/templates/${encodeURIComponent(templateId)}`, { method: 'DELETE' });
        const wasSelected = currentManifest()?.id === templateId;
        await refreshTemplates();
        if (wasSelected) {
            const fallback = state.templates.find((item) => item.manifest.id === 'core-image') || state.templates[0];
            if (fallback) selectTemplate(fallback);
        }
        await loadWorkflowRegistry();
        showToast(`Deleted ${workflow.name}. Models and nodes were not changed.`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    }
}

function handleWorkflowManagementAction(event) {
    const button = event.target.closest('[data-workflow-action]');
    const row = button?.closest('[data-workflow-id]');
    if (!button || !row) return;
    const templateId = row.dataset.workflowId;
    if (button.dataset.workflowAction === 'open') {
        const template = state.templates.find((item) => item.manifest.id === templateId);
        if (template) {
            elements.workflowManageDialog.close();
            selectTemplate(template);
        }
    } else if (button.dataset.workflowAction === 'revalidate') {
        revalidateWorkflow(templateId);
    } else if (button.dataset.workflowAction === 'edit') {
        openWorkflowMetadata(templateId);
    } else if (button.dataset.workflowAction === 'remap') {
        openWorkflowRemap(templateId);
    } else if (button.dataset.workflowAction === 'delete') {
        deleteManagedWorkflow(templateId);
    }
}

async function importTemplate(event) {
    event.preventDefault();
    if (state.remappingWorkflowId) {
        await saveWorkflowRemap();
        return;
    }
    const file = elements.importFile.files?.[0];
    if (!file) return;
    elements.importSubmit.disabled = true;
    const form = new FormData();
    form.append('file', file);
    form.append('name', elements.importDisplayName.value.trim());
    form.append('id', elements.importId.value.trim());
    form.append('description', elements.importDescription.value.trim());
    if (state.importMapping) form.append('mapping', JSON.stringify(state.importMapping));
    try {
        const template = await requestJson('/api/editor/templates/import', { method: 'POST', body: form });
        const existing = state.templates.findIndex((item) => item.manifest.id === template.manifest.id);
        if (existing >= 0) state.templates[existing] = template;
        else state.templates.push(template);
        selectTemplate(template);
        elements.importDialog.close();
        elements.importForm.reset();
        state.importPlan = null;
        state.importMapping = null;
        elements.importAnalysis.hidden = true;
        elements.importFields.hidden = true;
        elements.importMapping.hidden = true;
        elements.importName.textContent = 'No file selected';
        showToast(`Imported ${template.manifest.name}.`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
    } finally {
        elements.importSubmit.disabled = !state.importPlan?.ready;
    }
}

async function saveWorkflowRemap() {
    const templateId = state.remappingWorkflowId;
    if (!templateId || !state.importPlan?.ready) return;
    elements.importSubmit.disabled = true;
    try {
        const template = await requestJson(`/api/editor/workflows/${encodeURIComponent(templateId)}/mapping`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mapping: state.importMapping || {} }),
        });
        const index = state.templates.findIndex((item) => item.manifest.id === templateId);
        if (index >= 0) state.templates[index] = template;
        else state.templates.push(template);
        if (currentManifest()?.id === templateId) selectTemplate(template);
        elements.importDialog.close();
        resetImportDialogMode();
        await loadWorkflowRegistry();
        showToast(`Saved mappings for ${template.manifest.name}. Revalidate it before running.`, 'success');
    } catch (error) {
        showToast(error.message, 'error');
        elements.importSubmit.disabled = !state.importPlan?.ready;
    }
}

function defaultImportMapping(plan) {
    const fieldBinding = (fieldId) => {
        const item = plan.mappings.find((mapping) => (
            mapping.kind === 'field' && mapping.semantic_id === fieldId
        ));
        return item ? `${item.node_id}:${item.input}` : '';
    };
    return {
        sampler_node_id: plan.candidates.samplers.length === 1 ? plan.candidates.samplers[0].value : '',
        positive_binding: fieldBinding('positive_prompt'),
        negative_binding: fieldBinding('negative_prompt'),
        output_node_id: plan.candidates.outputs.length === 1 ? plan.candidates.outputs[0].value : '',
        model_roles: {},
        field_options: Object.fromEntries((plan.manifest.fields || []).map((field) => [field.id, {
            advanced: Boolean(field.advanced),
            hidden: Boolean(field.hidden),
        }])),
    };
}

function mappingSelect(label, key, options, selected, { placeholder = 'Automatic', help = '' } = {}) {
    return `<label class="template-mapping-control"><span>${escapeHtml(label)}</span><select data-mapping-key="${escapeHtml(key)}"><option value="">${escapeHtml(placeholder)}</option>${options.map((option) => `<option value="${escapeHtml(option.value)}"${option.value === selected ? ' selected' : ''}>${escapeHtml(option.label)} · ${escapeHtml(option.confidence)}</option>`).join('')}</select>${help ? `<small>${escapeHtml(help)}</small>` : ''}</label>`;
}

function renderImportManifestPreview() {
    if (!state.importPlan) return;
    const manifest = structuredClone(state.importPlan.manifest);
    manifest.id = elements.importId.value.trim() || manifest.id;
    manifest.name = elements.importDisplayName.value.trim() || manifest.name;
    manifest.description = elements.importDescription.value.trim();
    const fieldOptions = state.importMapping?.field_options || {};
    manifest.fields = (manifest.fields || []).map((field) => ({
        ...field,
        ...(fieldOptions[field.id] || {}),
    }));
    elements.importManifestPreview.textContent = JSON.stringify(manifest, null, 2);
}

function renderImportMapping(plan) {
    elements.importMapping.hidden = false;
    const mapping = state.importMapping || defaultImportMapping(plan);
    const promptOptions = plan.candidates.prompt_inputs || [];
    const outputOptions = plan.candidates.outputs || [];
    const samplerOptions = plan.candidates.samplers || [];
    const controls = [];
    if (['api_workflow', 'ui_workflow', 'registered_workflow'].includes(plan.source_format)) {
        controls.push(mappingSelect('Sampler pipeline', 'sampler_node_id', samplerOptions, mapping.sampler_node_id, {
            placeholder: samplerOptions.length > 1 ? 'Choose sampler…' : 'Automatic',
        }));
        controls.push(mappingSelect('Positive prompt', 'positive_binding', promptOptions, mapping.positive_binding));
        controls.push(mappingSelect('Negative prompt', 'negative_binding', [
            { value: '__none__', label: 'No negative prompt', confidence: 'manual' },
            ...promptOptions,
        ], mapping.negative_binding));
        controls.push(mappingSelect('Primary output', 'output_node_id', outputOptions, mapping.output_node_id, {
            placeholder: outputOptions.length > 1 ? 'Choose output…' : 'Automatic',
        }));
        for (const candidate of plan.candidates.model_inputs || []) {
            const roles = [
                ['ignore', 'Ignore'],
                ['checkpoint', 'Checkpoint'],
                ['diffusion_model', 'Diffusion model'],
                ['diffusion_model_gguf', 'Diffusion model (GGUF)'],
                ['text_encoder', 'Text encoder'],
                ['text_encoder_gguf', 'Text encoder (GGUF)'],
                ['vae', 'VAE'],
                ['lora', 'LoRA'],
            ];
            controls.push(`<label class="template-mapping-control"><span>${escapeHtml(candidate.label)}</span><select data-model-role="${escapeHtml(candidate.value)}"><option value="">Choose model role…</option>${roles.map(([value, label]) => `<option value="${value}"${mapping.model_roles?.[candidate.value] === value ? ' selected' : ''}>${escapeHtml(label)}</option>`).join('')}</select><small>Unknown loader input · current value: ${escapeHtml(candidate.current_value || 'empty')}</small></label>`);
        }
    }
    elements.importMappingControls.innerHTML = controls.join('');

    const fieldRows = (plan.manifest.fields || []).map((field) => {
        const bindings = field.bindings.map((binding) => `${binding.node_id}:${binding.input}`).join(', ');
        const confidence = plan.mappings.find((item) => item.kind === 'field' && item.semantic_id === field.id)?.confidence || 'declared';
        const options = mapping.field_options?.[field.id] || field;
        return `<div class="template-mapping-row"><strong>${escapeHtml(field.label)}</strong><code>${escapeHtml(bindings)}</code><span class="mapping-confidence">${escapeHtml(confidence)}</span><span class="mapping-field-options"><label><input type="checkbox" data-field-option="advanced" data-field-id="${escapeHtml(field.id)}"${options.advanced ? ' checked' : ''}> Advanced</label><label><input type="checkbox" data-field-option="hidden" data-field-id="${escapeHtml(field.id)}"${options.hidden ? ' checked' : ''}> Hidden</label></span></div>`;
    });
    const resourceRows = (plan.mappings || []).filter((item) => item.kind === 'resource').map((item) => (
        `<div class="template-mapping-row"><strong>${escapeHtml(item.semantic_id)}</strong><code>${escapeHtml(`${item.node_id}:${item.input}`)}</code><span class="mapping-confidence">${escapeHtml(item.confidence)}</span><span>Model slot</span></div>`
    ));
    elements.importMappingList.innerHTML = [...fieldRows, ...resourceRows].join('')
        || '<p class="template-import-name">Choose the required mappings, then apply them to preview the final manifest.</p>';
    renderImportManifestPreview();
    elements.importMapping.querySelectorAll('select, input[type="checkbox"]').forEach((control) => {
        control.addEventListener('change', () => {
            state.importMapping = readImportMapping();
            elements.importSubmit.disabled = true;
            elements.importMappingApply.textContent = 'Apply mappings';
            renderImportManifestPreview();
        });
    });
}

function readImportMapping() {
    const mapping = structuredClone(state.importMapping || {});
    elements.importMappingControls.querySelectorAll('[data-mapping-key]').forEach((select) => {
        mapping[select.dataset.mappingKey] = select.value;
    });
    mapping.model_roles = {};
    elements.importMappingControls.querySelectorAll('[data-model-role]').forEach((select) => {
        if (select.value) mapping.model_roles[select.dataset.modelRole] = select.value;
    });
    mapping.field_options = {};
    elements.importMappingList.querySelectorAll('[data-field-id]').forEach((input) => {
        const options = mapping.field_options[input.dataset.fieldId] || {};
        options[input.dataset.fieldOption] = input.checked;
        mapping.field_options[input.dataset.fieldId] = options;
    });
    return mapping;
}

async function analyzeTemplateImport(mappingOverrides = null) {
    const registeredId = state.remappingWorkflowId;
    const file = elements.importFile.files?.[0];
    state.importPlan = null;
    elements.importSubmit.disabled = true;
    elements.importFields.hidden = true;
    elements.importAnalysis.classList.remove('error');
    if (!registeredId && !file) {
        elements.importAnalysis.hidden = true;
        elements.importMapping.hidden = true;
        return;
    }

    elements.importAnalysis.hidden = false;
    elements.importAnalysis.innerHTML = '<strong>Analyzing workflow…</strong><span>Detecting semantic fields, model slots, and output nodes.</span>';
    try {
        if (registeredId) {
            const payload = await requestJson(`/api/editor/workflows/${encodeURIComponent(registeredId)}/mapping`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ mapping: mappingOverrides || state.importMapping || {} }),
            });
            renderImportPlan(payload.plan, payload.mapping, { remap: true, preserveMetadata: true });
        } else {
            const form = new FormData();
            form.append('file', file);
            if (mappingOverrides) form.append('mapping', JSON.stringify(mappingOverrides));
            const plan = await requestJson('/api/editor/templates/import/analyze', { method: 'POST', body: form });
            renderImportPlan(plan, mappingOverrides || defaultImportMapping(plan), {
                preserveMetadata: mappingOverrides !== null,
            });
        }
    } catch (error) {
        elements.importAnalysis.classList.add('error');
        elements.importAnalysis.innerHTML = `<strong>${registeredId ? 'Cannot update these mappings' : 'Cannot import this file'}</strong><span>${escapeHtml(error.message)}</span>`;
        elements.importMapping.hidden = true;
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
    bindAccordionFlyouts();
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
    elements.generateButton.addEventListener('click', generateWorkflow);
    elements.generateFromPreview.addEventListener('click', generateWorkflow);
    elements.cancelRun.addEventListener('click', cancelCurrentRun);
    elements.resultsRefresh.addEventListener('click', loadRuns);
    elements.resultGrid.addEventListener('click', (event) => {
        const trigger = event.target.closest('[data-open-result]');
        if (!trigger) return;
        openResultLightbox(trigger.dataset.openResult).catch((error) => {
            showToast(error.message || String(error), 'error');
        });
    });
    elements.runtimeOpen.addEventListener('click', openRuntimeDrawer);
    elements.runtimeConnect.addEventListener('click', openRuntimeDrawer);
    elements.runtimeClose.addEventListener('click', closeRuntimeDrawer);
    elements.runtimeBackdrop.addEventListener('click', closeRuntimeDrawer);
    elements.importOpen.addEventListener('click', () => {
        resetImportDialogMode();
        elements.importDialog.showModal();
    });
    elements.workflowManageOpen.addEventListener('click', () => loadWorkflowRegistry({ open: true }));
    elements.workflowManageSearch.addEventListener('input', renderWorkflowRegistry);
    elements.workflowManageSource.addEventListener('change', renderWorkflowRegistry);
    elements.workflowManageStatus.addEventListener('change', renderWorkflowRegistry);
    elements.workflowManageBody.addEventListener('click', handleWorkflowManagementAction);
    elements.workflowRevalidateAll.addEventListener('click', revalidateAllWorkflows);
    elements.workflowMetadataForm.addEventListener('submit', saveWorkflowMetadata);
    elements.importFile.addEventListener('change', () => {
        const file = elements.importFile.files?.[0];
        elements.importName.textContent = file ? `${file.name} · ${(file.size / 1024).toFixed(1)} KB` : 'No file selected';
        state.importMapping = null;
        analyzeTemplateImport();
    });
    elements.importMappingApply.addEventListener('click', () => analyzeTemplateImport(readImportMapping()));
    [elements.importDisplayName, elements.importId, elements.importDescription].forEach((input) => {
        input.addEventListener('input', renderImportManifestPreview);
    });
    elements.importForm.addEventListener('submit', importTemplate);
    elements.sourceInspect.addEventListener('click', inspectDraftSource);
    elements.aiPromptOpen.addEventListener('click', openAIPromptDialog);
    elements.aiPromptFamily.addEventListener('change', renderAIScenarios);
    elements.aiPromptProfile.addEventListener('change', renderAIScenarios);
    elements.aiPromptForm.addEventListener('submit', createAIPromptDraft);
    elements.translatePromptOpen.addEventListener('click', openTranslatePromptDialog);
    elements.translatePromptFamily.addEventListener('change', renderTranslationScenarios);
    elements.translatePromptProfile.addEventListener('change', renderTranslationScenarios);
    elements.translatePromptForm.addEventListener('submit', createTranslatedPromptDraft);
    elements.adaptPromptOpen.addEventListener('click', openAdaptPromptDialog);
    elements.adaptPromptFamily.addEventListener('change', renderAdaptationScenarios);
    elements.adaptPromptProfile.addEventListener('change', renderAdaptationScenarios);
    elements.adaptPromptForm.addEventListener('submit', createAdaptedPromptDraft);
    elements.reconstructPromptOpen.addEventListener('click', openReconstructPromptDialog);
    elements.reconstructPromptFamily.addEventListener('change', renderReconstructionScenarios);
    elements.reconstructVisionProfile.addEventListener('change', renderReconstructionScenarios);
    elements.reconstructRenderProfile.addEventListener('change', renderReconstructionScenarios);
    elements.reconstructSceneSpec.addEventListener('input', renderReconstructionScenarios);
    elements.reconstructAnalyze.addEventListener('click', analyzeReconstructionScene);
    elements.reconstructPromptForm.addEventListener('submit', createReconstructedPromptDraft);
    elements.resetEditor.addEventListener('click', resetEditor);
    elements.saveNote.addEventListener('click', async () => {
        try {
            await saveDraft();
            showToast('Draft saved.', 'success');
        } catch (error) {
            showToast(error.message, 'error');
        }
    });
    elements.collapseControls.addEventListener('click', () => {
        const collapsed = document.body.classList.toggle('controls-collapsed');
        elements.collapseControls.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        elements.collapseControls.setAttribute('aria-label', collapsed ? 'Expand panel' : 'Collapse panel');
        elements.editorSidebarToggle.setAttribute('aria-expanded', collapsed ? 'false' : 'true');
        elements.editorSidebarToggle.setAttribute('aria-label', collapsed ? 'Expand settings panel' : 'Collapse settings panel');
        elements.editorSidebarToggle.setAttribute('title', collapsed ? 'Expand settings panel' : 'Collapse settings panel');
    });
    elements.editorSidebarToggle.addEventListener('click', () => elements.collapseControls.click());
    document.querySelectorAll('[data-ui-choice]').forEach((group) => group.addEventListener('click', (event) => {
        const button = event.target.closest('button');
        if (!button) return;
        group.querySelectorAll('button').forEach((item) => item.classList.toggle('active', item === button));
    }));
    document.querySelector('[data-aspect-grid]')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-width]');
        if (!button) return;
        applyAspectSize(button);
    });
    elements.aspectMore?.addEventListener('click', () => {
        if (elements.aspectPopover.hidden) openAspectPopover();
        else closeAspectPopover();
    });
    elements.aspectPopoverClose?.addEventListener('click', closeAspectPopover);
    elements.aspectPopover?.addEventListener('click', (event) => {
        const sizeButton = event.target.closest('[data-width]');
        if (sizeButton) {
            applyAspectSize(sizeButton);
            return;
        }
        if (event.target.closest('[data-aspect-custom]')) toggleCustomResolution();
    });
    elements.aspectRatioLock?.addEventListener('click', () => {
        state.aspectRatioLocked = !state.aspectRatioLocked;
        if (state.aspectRatioLocked && Number(state.values.width) > 0 && Number(state.values.height) > 0) {
            state.lockedAspectRatio = Number(state.values.width) / Number(state.values.height);
        }
        updateCustomResolutionControls();
    });
    [
        [elements.customWidthRange, 'width'],
        [elements.customHeightRange, 'height'],
    ].forEach(([input, id]) => {
        input?.addEventListener('pointerdown', captureLockedAspectRatio);
        input?.addEventListener('focus', captureLockedAspectRatio);
        input?.addEventListener('input', () => applyCustomDimension(id, input.value));
    });
    [
        [elements.customWidth, 'width'],
        [elements.customHeight, 'height'],
    ].forEach(([input, id]) => {
        input?.addEventListener('focus', captureLockedAspectRatio);
        input?.addEventListener('change', () => applyCustomDimension(id, input.value));
        input?.addEventListener('keydown', (event) => {
            if (event.key !== 'Enter') return;
            event.preventDefault();
            applyCustomDimension(id, input.value);
            input.blur();
        });
    });
    document.querySelector('[data-batch-grid]')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-batch]');
        if (!button) return;
        state.values.batch_size = Number(button.dataset.batch);
        renderFields();
        markDirty();
    });
    document.querySelector('[data-quick-mode]')?.addEventListener('click', (event) => {
        const button = event.target.closest('[data-mode]');
        if (!button || !currentManifest()?.fields?.some((field) => field.id === 'steps' && !field.hidden)) return;
        const defaultSteps = Number(state.selected?.defaults?.steps ?? 28);
        state.values.steps = button.dataset.mode === 'quality' ? Math.max(defaultSteps + 12, 40) : defaultSteps;
        renderFields();
        markDirty();
    });
    document.addEventListener('pointerdown', (event) => {
        if (elements.aspectPopover?.hidden) return;
        if (elements.aspectPopover.contains(event.target) || elements.aspectMore?.contains(event.target)) return;
        closeAspectPopover();
    });
    window.addEventListener('resize', positionAspectPopover);
    document.querySelector('.controls-scroll')?.addEventListener('scroll', positionAspectPopover, { passive: true });
    elements.resultsSearch.addEventListener('input', () => {
        const query = elements.resultsSearch.value.trim().toLowerCase();
        elements.resultGrid.querySelectorAll('[data-result-search]').forEach((card) => {
            card.hidden = query && !card.dataset.resultSearch.includes(query);
        });
    });
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
        if (elements.lightbox?.classList.contains('open')) {
            if (event.key === 'Escape') closeLightbox();
            else if (event.key === 'ArrowLeft') prevLightbox();
            else if (event.key === 'ArrowRight') nextLightbox();
            else return;
            event.preventDefault();
            return;
        }
        if (event.key === 'Escape' && !elements.aspectPopover?.hidden) {
            closeAspectPopover();
            elements.aspectMore?.focus();
            return;
        }
        if (event.key === 'Escape' && !elements.runtimeLayer.hidden) closeRuntimeDrawer();
    });
    document.addEventListener('visibilitychange', () => {
        if (document.visibilityState === 'visible') loadRuns();
    });
    window.addEventListener('focus', loadRuns);
    window.addEventListener('beforeunload', () => {
        persistCreateWorkspace();
        window.clearTimeout(state.pollTimer);
        window.clearInterval(state.statusTimer);
        if (backdropAlignmentFrame !== null) window.cancelAnimationFrame(backdropAlignmentFrame);
        backdropResizeObserver?.disconnect();
        backdropMutationObserver?.disconnect();
    });
}

async function initialize() {
    bindEvents();
    initLightboxEvents({ enableContextMenu: false });
    observeDecorativeBackdropWindows();
    loadDecorativeBackdrops();
    await loadRuntimeConfig();
    await bootstrap();
    await updateRuntimeStatus();
    state.statusTimer = window.setInterval(() => updateRuntimeStatus(false), 4000);
}

initialize();
