const $ = id => document.getElementById(id);
const MAX_REF = 20 * 1024 * 1024;
const ROTATE = 5 * 60 * 1000;

const state = {
    models: [],
    modelId: '',
    health: null,
    ratio: '1:1',
    quality: 'standard',
    batch: 1,
    improve: true,
    alwaysImprove: false,
    canvasWidth: null,
    aiOriginalPrompt: null,
    aiExpandedPrompt: null,
    applyingAiPrompt: false,
    ref: null,
    refUrl: null,
    ambient: [],
    ambientDeck: [],
    ambientHistory: [],
    ambientCurrent: null,
    ambientLoadingMore: false,
    fit: 'cover',
    layer: 0,
    timer: null,
    interval: 300000,
    opacity: 44,
    blur: 10,
    sound: false,
    run: null,
    poll: null,
    generationProgress: 0,
    last: null,
    lastOutputs: [],
    selectedResultIndex: 0,
    history: [],
    downloads: [],
    downloadPoll: null,
    modelMenuOpen: false,
    runtimeConfig: null,
    runtimeStatus: null,
};

function getCachedJson(key, maxAgeMs = 0) {
    try {
        const raw = sessionStorage.getItem(key) || localStorage.getItem(key);
        if (!raw) return null;
        const parsed = JSON.parse(raw);
        if (maxAgeMs > 0 && parsed?._t && (Date.now() - parsed._t > maxAgeMs)) {
            return null;
        }
        return parsed.data !== undefined ? parsed.data : parsed;
    } catch {
        return null;
    }
}

function setCachedJson(key, data, isLocal = false) {
    try {
        const payload = JSON.stringify({ data, _t: Date.now() });
        if (isLocal) {
            localStorage.setItem(key, payload);
        } else {
            sessionStorage.setItem(key, payload);
        }
    } catch {}
}

function initialAmbient() {
    try {
        const embedded = JSON.parse($('simple-ambient-initial')?.textContent || '[]');
        if (Array.isArray(embedded) && embedded.length) return embedded;
    } catch {}
    const cached = getCachedJson('cmv_simple_ambient_items', 30 * 60 * 1000);
    return Array.isArray(cached) ? cached : [];
}

function hydrateAmbient() {
    const last = localStorage.getItem('cmv_simple_ambient_last');
    if (last) {
        state.ambientCurrent = last;
        state.ambientHistory.push(last);
        applyAmbient(last);
    }
    state.ambient = initialAmbient();
    refillAmbientDeck();
    if (!last && state.ambient.length) {
        ambientPick();
    }
    preloadAmbientPool();
}

function catalog() {
    try { return JSON.parse($('simple-model-catalog')?.textContent || '[]'); }
    catch { return []; }
}

function model() {
    return state.models.find(item => item.id === state.modelId) || null;
}

function save(key, value) {
    try { localStorage.setItem(key, String(value)); } catch {}
}

function applyVisualSettings() {
    document.documentElement.style.setProperty('--studio-card-opacity', `${state.opacity ?? 44}%`);
    document.documentElement.style.setProperty('--studio-ambient-blur', `${state.blur ?? 10}px`);
    document.documentElement.style.setProperty(
        '--studio-ambient-size',
        state.fit === 'contain' ? 'contain' : (state.fit === 'original' ? 'auto' : 'cover')
    );
    document.body.setAttribute('data-ambient-fit', state.fit || 'cover');
}

function restartAmbientTimer() {
    if (state.timer) {
        clearInterval(state.timer);
        state.timer = null;
    }
    if (state.interval > 0 && state.ambient.length > 1) {
        state.timer = setInterval(ambientPick, state.interval);
    }
}

function restore() {
    try {
        state.modelId = localStorage.getItem('cmv_simple_model') || document.body.dataset.defaultModelId || '';
        state.ratio = localStorage.getItem('cmv_simple_ratio') || '1:1';
        state.quality = localStorage.getItem('cmv_simple_quality') || 'standard';
        state.batch = Math.max(1, Math.min(4, Number(localStorage.getItem('cmv_simple_batch')) || 1));
        const ai = localStorage.getItem('cmv_simple_ai_improve');
        if (ai !== null) state.improve = ai === 'true';
        state.alwaysImprove = localStorage.getItem('cmv_simple_ai_always') === 'true';
        const savedCanvasWidth = Number(localStorage.getItem('cmv_simple_canvas_width'));
        if (Number.isFinite(savedCanvasWidth)) state.canvasWidth = savedCanvasWidth;

        const rawInterval = localStorage.getItem('cmv_simple_ambient_interval');
        state.interval = rawInterval !== null && !isNaN(Number(rawInterval)) ? Number(rawInterval) : 300000;

        const rawOpacity = localStorage.getItem('cmv_simple_glass_opacity');
        const numOpacity = Number(rawOpacity);
        if (rawOpacity !== null && !isNaN(numOpacity) && numOpacity >= 5 && numOpacity <= 98) {
            state.opacity = numOpacity;
        } else if (rawOpacity === 'ultra') state.opacity = 18;
        else if (rawOpacity === 'high') state.opacity = 30;
        else if (rawOpacity === 'solid') state.opacity = 82;
        else state.opacity = 44;

        const rawBlur = localStorage.getItem('cmv_simple_ambient_blur');
        state.blur = rawBlur !== null && !isNaN(Number(rawBlur)) ? Number(rawBlur) : 10;
        state.fit = localStorage.getItem('cmv_simple_ambient_fit') || 'cover';
        state.sound = localStorage.getItem('cmv_simple_sound_alert') === 'true';
        const savedPrompt = localStorage.getItem('cmv_simple_prompt');
        if (savedPrompt !== null && $('prompt')) $('prompt').value = savedPrompt;
        state.aiOriginalPrompt = localStorage.getItem('cmv_simple_ai_original_prompt');
        state.aiExpandedPrompt = localStorage.getItem('cmv_simple_ai_expanded_prompt');
    } catch {}
}

function restoreLastResult() {
    const cached = getCachedJson('cmv_simple_last_result');
    const outputs = Array.isArray(cached?.outputs)
        ? cached.outputs
        : (cached ? [cached] : []);
    renderResult(outputs, false);
}

function clearLastResult() {
    state.last = null;
    state.lastOutputs = [];
    state.selectedResultIndex = 0;
    try { localStorage.removeItem('cmv_simple_last_result'); } catch {}
}

function openResultFullscreen(startIndex = 0) {
    const outputs = (state.lastOutputs || []).filter(item => item?.preview_url || item?.thumbnail_url);
    if (!outputs.length) return;
    let currentIndex = typeof startIndex === 'number'
        ? Math.max(0, Math.min(outputs.length - 1, startIndex))
        : (state.selectedResultIndex || 0);
    if (currentIndex < 0 || currentIndex >= outputs.length) currentIndex = 0;

    let scale = 1;
    const overlay = document.createElement('div');
    overlay.className = 'result-lightbox';
    overlay.setAttribute('role', 'dialog');
    overlay.setAttribute('aria-modal', 'true');
    overlay.setAttribute('aria-label', 'Full-screen result preview');

    const close = document.createElement('button');
    close.type = 'button';
    close.className = 'result-lightbox-close';
    close.setAttribute('aria-label', 'Close preview');
    close.textContent = '×';

    const preview = document.createElement('img');
    preview.className = 'result-lightbox-image';
    const initialItem = outputs[currentIndex];
    preview.src = initialItem.preview_url || initialItem.thumbnail_url;
    preview.alt = `Generated result ${currentIndex + 1}`;

    const controls = document.createElement('div');
    controls.className = 'result-lightbox-controls';
    const makeNavButton = (label, direction) => {
        const button = document.createElement('button');
        button.type = 'button';
        button.className = `result-lightbox-nav ${direction}`;
        button.setAttribute('aria-label', label);
        button.textContent = direction === 'prev' ? '‹' : '›';
        return button;
    };
    const previous = makeNavButton('Previous result', 'prev');
    const next = makeNavButton('Next result', 'next');
    if (outputs.length > 1) controls.append(previous, next);

    const updatePreview = () => {
        const current = outputs[currentIndex];
        scale = 1;
        preview.src = current.preview_url || current.thumbnail_url;
        preview.alt = `Generated result ${currentIndex + 1}`;
        preview.style.transform = 'scale(1)';
        selectResultIndex(currentIndex);
    };
    const move = direction => {
        currentIndex = (currentIndex + direction + outputs.length) % outputs.length;
        updatePreview();
    };
    previous.addEventListener('click', () => move(-1));
    next.addEventListener('click', () => move(1));
    preview.addEventListener('wheel', event => {
        event.preventDefault();
        scale = Math.max(.5, Math.min(3, scale + (event.deltaY < 0 ? .15 : -.15)));
        preview.style.transform = `scale(${scale})`;
    }, { passive: false });
    preview.addEventListener('dblclick', () => {
        scale = 1;
        preview.style.transform = 'scale(1)';
    });

    overlay.append(close, controls, preview);
    const dismiss = () => {
        overlay.remove();
        document.removeEventListener('keydown', onKeydown);
    };
    const onKeydown = event => {
        if (event.key === 'Escape') dismiss();
        if (event.key === 'ArrowLeft' && outputs.length > 1) move(-1);
        if (event.key === 'ArrowRight' && outputs.length > 1) move(1);
    };
    close.addEventListener('click', dismiss);
    overlay.addEventListener('click', event => {
        if (event.target === overlay) dismiss();
    });
    document.addEventListener('keydown', onKeydown);
    document.body.appendChild(overlay);
    requestAnimationFrame(() => overlay.classList.add('is-open'));
    close.focus();
}

function applyAiPrompt(suggestedPrompt, originalPrompt = $('prompt').value.trim()) {
    const nextPrompt = String(suggestedPrompt || '').trim();
    if (!nextPrompt) return;
    state.aiOriginalPrompt = originalPrompt;
    state.aiExpandedPrompt = nextPrompt;
    save('cmv_simple_ai_original_prompt', originalPrompt);
    save('cmv_simple_ai_expanded_prompt', nextPrompt);
    state.applyingAiPrompt = true;
    $('prompt').value = nextPrompt;
    $('prompt').dispatchEvent(new Event('input'));
    state.applyingAiPrompt = false;
}

function esc(value) {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
}

function translateStaticUi() {
    document.title = 'Create — ComfyUI Meta Viewer';
    const text = {
        '.ai-assistant-trigger span': 'AI assistant',
        '.studio-title': 'What are we creating?',
        '.studio-subtitle': 'Describe your idea or add an image as a reference.',
        '.reference-upload-btn span:last-child': 'Add image',
        '#prompt-clear': 'Clear',
        '.model-select-kicker': 'Selected model',
        '#model-install span': 'Download missing',
        '#model-recheck': 'Check again',
        '.studio-create-btn .create-btn-content span': 'Create',
        '#progress-text': 'Starting…',
        '#generating-text': 'Preparing…',
        '#result-download': 'Download',
        '.canvas-actions-left a': 'Library',
        '#result-edit': 'Edit prompt',
        '#runtime-settings-title': 'Connect to ComfyUI',
        '#runtime-browse': 'Browse…',
        '#runtime-test': 'Test',
        '#runtime-settings-cancel': 'Cancel',
        '#runtime-save': 'Save',
        '.assistant-title-wrap h2': 'Prompt assistant',
        '#assistant-new': 'New conversation',
    };
    Object.entries(text).forEach(([selector, value]) => {
        const node = document.querySelector(selector);
        if (node) node.textContent = value;
    });
    const prompt = $('prompt');
    if (prompt) prompt.placeholder = 'For example: a night café by the sea, warm window light, light fog and wet pavement';
    const labels = document.querySelectorAll('.section-label');
    ['Model', 'Aspect ratio', 'Quality', 'Images'].forEach((value, index) => {
        if (labels[index]) labels[index].textContent = value;
    });
    const hint = document.querySelector('.section-hint');
    if (hint) hint.textContent = 'Eight ready-to-use models. Technical names are hidden behind our labels.';
    const improve = document.querySelector('.ai-improve-pill span');
    if (improve) improve.textContent = 'Add details';
    const aiWrap = $('ai-toggle-wrap');
    if (aiWrap && !$('ai-always-toggle')) {
        const alwaysWrap = document.createElement('label');
        alwaysWrap.id = 'ai-always-wrap';
        alwaysWrap.className = 'ai-improve-toggle';
        alwaysWrap.innerHTML = '<input id="ai-always-toggle" type="checkbox"><span class="ai-improve-pill">↻ <span>Always add details</span></span>';
        alwaysWrap.querySelector('input').checked = state.alwaysImprove;
        const toolbar = aiWrap.parentElement;
        const group = document.createElement('div');
        group.className = 'ai-improve-toggle-group';
        group.append(aiWrap, alwaysWrap);
        toolbar.appendChild(group);
    }
    const qualityLabels = [
        ['Fast', 'Quick option'],
        ['Standard', 'Default mode'],
        ['Detailed', 'More refinement'],
    ];
    document.querySelectorAll('.quality-card').forEach((card, index) => {
        if (qualityLabels[index]) {
            card.querySelector('strong').textContent = qualityLabels[index][0];
            card.querySelector('.quality-meta').textContent = qualityLabels[index][1];
        }
    });
    const runtimeFields = document.querySelectorAll('.simple-settings-field > span');
    ['ComfyUI folder', 'Python', 'Host', 'Port', 'Civitai API token'].forEach((value, index) => {
        if (runtimeFields[index]) runtimeFields[index].childNodes[0].textContent = value;
    });
    const runtimeHelp = document.querySelector('#runtime-settings-dialog .simple-settings-field small');
    if (runtimeHelp) runtimeHelp.textContent = 'Optional';
    const runtimeDetection = document.querySelector('#runtime-detection-title');
    if (runtimeDetection) runtimeDetection.textContent = 'Path not checked yet';
    const themeLabel = document.querySelector('.header-theme-dropdown .header-menu-label');
    if (themeLabel) themeLabel.textContent = 'Theme';
    document.querySelectorAll('.theme-option small').forEach((node, index) => {
        node.textContent = ['Dark', 'Light', 'Pastel', 'Dark berry', 'System'][index] || node.textContent;
    });
    const referenceKicker = document.querySelector('.reference-preview-kicker');
    if (referenceKicker) referenceKicker.textContent = 'Image reference';
    const assistantInput = $('assistant-input');
    if (assistantInput) assistantInput.placeholder = 'Refine the idea, composition or lighting…';
    const runtimeDescription = document.querySelector('#runtime-settings-dialog header p');
    if (runtimeDescription) runtimeDescription.textContent = 'Point to an existing installation. Models from Create will be downloaded into its models folder.';
    const runtimePathHelp = document.querySelector('#runtime-install-path')?.closest('.simple-settings-field')?.querySelector('small');
    if (runtimePathHelp) runtimePathHelp.textContent = 'Choose a folder containing main.py or a portable root containing ComfyUI.';
    const pythonInput = $('runtime-python');
    if (pythonInput) pythonInput.placeholder = 'Path to python.exe, if it is not detected automatically';
    const civitaiInput = $('runtime-civitai-token');
    if (civitaiInput) civitaiInput.placeholder = 'Leave empty to keep the saved token';
    const detectionText = $('runtime-detection-text');
    if (detectionText) detectionText.textContent = 'Choose a folder or enter a path manually.';
}

async function json(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok) {
        throw Object.assign(
            new Error(data.suggestion || data.error || `${response.status} ${response.statusText}`),
            { data, status: response.status },
        );
    }
    return data;
}

function init() {
    state.models = catalog();
    restore();
    translateStaticUi();
    applyVisualSettings();
    if (!state.models.some(item => item.id === state.modelId)) {
        state.modelId = state.models[0]?.id || '';
    }
    hydrateAmbient();
    renderCatalog();
    wire();
    wireCanvasResize();
    syncModel();
    syncRatio();
    syncQuality();
    syncBatch();
    resizePrompt();
    restoreLastResult();
    loadHealth();
    loadDownloads();
    loadAmbient();
    loadAi();
    loadRuntimeSummary();
    refreshCatalog();
}

function renderCatalog() {
    const menu = $('model-select-menu');
    if (!menu) return;
    menu.innerHTML = state.models.map(item => `
        <button type="button" class="model-select-option${item.id === state.modelId ? ' is-active' : ''}"
                data-model-id="${esc(item.id)}" role="option" aria-selected="${item.id === state.modelId}">
            <span class="model-option-copy">
                <strong>${esc(item.name)}</strong>
                <small>${esc(item.technical_name || '')}</small>
            </span>
            <span class="model-option-check">✓</span>
        </button>`).join('');
    const current = model();
    if ($('model-selected-name')) $('model-selected-name').textContent = current?.name || 'Model';
}

function chooseModel(modelId) {
    if (!state.models.some(item => item.id === modelId)) return;
    state.modelId = modelId;
    save('cmv_simple_model', modelId);
    renderCatalog();
    closeModelMenu();
    syncModel();
    loadHealth();
    loadDownloads();
}

function toggleModelMenu(force) {
    const trigger = $('model-select-trigger');
    const menu = $('model-select-menu');
    if (!trigger || !menu) return;
    const next = typeof force === 'boolean' ? force : !state.modelMenuOpen;
    state.modelMenuOpen = next;
    trigger.setAttribute('aria-expanded', String(next));
    menu.hidden = !next;
}

function closeModelMenu() {
    toggleModelMenu(false);
}

function syncModel() {
    const current = model();
    if (!current) return;
    $('model-selected-name').textContent = current.name;
    $('model-technical').textContent = current.technical_name || current.name;
    $('model-description').textContent = current.description || '';
    $('model-vram').textContent = current.vram_rec_gb ? `Recommended ${current.vram_rec_gb} GB VRAM` : '';
    const cachedHealth = getCachedJson('cmv_health_' + current.id, 60 * 1000);
    if (cachedHealth) {
        paintHealth(cachedHealth);
    } else {
        state.health = null;
        paintHealth({ status: 'checking', message: 'Checking local components' });
    }
    syncRatio();
    syncQuality();
}

function paintHealth(health) {
    state.health = health || {};
    const badge = $('model-health');
    const panel = $('model-health-panel');
    const message = $('model-health-message');
    const missing = $('model-missing');
    const install = $('model-install');
    const map = {
        ready: ['is-ready', 'Ready'],
        not_installed: ['is-missing', 'Installation required'],
        workflow_pending: ['is-pending', 'Workflow pending'],
        unknown: ['is-checking', 'Not checked'],
        checking: ['is-checking', 'Checking'],
    };
    const [className, label] = map[health?.status] || map.unknown;
    badge.className = `model-health-badge ${className}`;
    badge.textContent = label;
    const rows = health?.missing_resources || [];
    message.textContent = health?.message || '';
    missing.innerHTML = rows.map(item => `
        <div class="model-missing-row">
            <span>${esc(item.display_name || item.filename)}</span>
            <small>${esc(item.folder || '')}</small>
        </div>`).join('');
    const activeDownloads = state.downloads.some(item => ['queued', 'downloading'].includes(item.status));
    const failedDownloads = state.downloads.some(item => ['failed', 'error'].includes(item.status));
    install.hidden = !(health?.status === 'not_installed' && health?.installable !== false);
    install.disabled = activeDownloads;
    install.querySelector('span').textContent = activeDownloads ? 'Downloading…' : 'Download missing';
    const isMissing = health?.status === 'not_installed' || rows.length > 0;
    panel.hidden = !isMissing && !activeDownloads && !failedDownloads;
}

async function loadHealth(force = false) {
    const id = state.modelId;
    if (!id) return;
    try {
        const url = `/api/simple/models/${encodeURIComponent(id)}/status${force ? '?refresh=1' : ''}`;
        const data = await json(url);
        const health = data.health || {};
        setCachedJson('cmv_health_' + id, health, false);
        if (state.modelId === id) paintHealth(health);
    } catch {
        if (state.modelId === id && !state.health) {
            paintHealth({ status: 'unknown', message: 'Could not check local components' });
        }
    }
}

async function refreshCatalog() {
    try {
        const data = await json('/api/simple/models');
        if (Array.isArray(data.models) && data.models.length) {
            state.models = data.models;
            if (!state.models.some(item => item.id === state.modelId)) {
                state.modelId = data.default_model_id || state.models[0].id;
            }
            renderCatalog();
            syncModel();
            loadHealth();
        }
    } catch {}
}

function latestDownloads(items) {
    const seen = new Set();
    const result = [];
    for (const item of items || []) {
        const key = `${item.folder}/${item.filename}`;
        if (seen.has(key)) continue;
        seen.add(key);
        result.push(item);
    }
    return result;
}

function bytes(value) {
    const amount = Number(value || 0);
    if (!amount) return '';
    const units = ['B', 'KB', 'MB', 'GB'];
    let number = amount;
    let index = 0;
    while (number >= 1024 && index < units.length - 1) {
        number /= 1024;
        index += 1;
    }
    return `${number >= 100 || index === 0 ? number.toFixed(0) : number.toFixed(1)} ${units[index]}`;
}

function downloadStatus(item) {
    const labels = {
        queued: 'Queued',
        downloading: item.file_size_bytes ? `${Math.round(item.progress || 0)}%` : 'Downloading…',
        paused: 'Paused',
        completed: 'Complete',
        failed: 'Failed',
        cancelled: 'Cancelled',
    };
    return labels[item.status] || item.status;
}

function paintDownloads() {
    const wrap = $('model-downloads');
    if (!wrap) return;
    wrap.hidden = !state.downloads.length;
    wrap.innerHTML = state.downloads.map(item => {
        const canPause = ['queued', 'downloading'].includes(item.status) && item.id > 0;
        const canResume = ['paused', 'failed', 'cancelled'].includes(item.status) && item.id > 0;
        const canCancel = ['queued', 'downloading', 'paused'].includes(item.status) && item.id > 0;
        const indeterminate = item.status === 'downloading' && !item.file_size_bytes;
        const percent = item.file_size_bytes ? Math.round(item.progress || 0) : null;
        const size = item.file_size_bytes
            ? `${bytes(item.downloaded_bytes)} / ${bytes(item.file_size_bytes)}`
            : (item.downloaded_bytes ? bytes(item.downloaded_bytes) : item.folder);
        return `<div class="model-download-row">
            <div class="model-download-head">
                <div class="model-download-copy">
                    <strong>${esc(item.display_name || item.filename)}</strong>
                    <small>${esc(downloadStatus(item))}${size ? ` · ${esc(size)}` : ''}</small>
                </div>
                <div class="model-download-actions">
                    ${percent !== null && ['queued', 'downloading', 'paused'].includes(item.status) ? `<span class="cmv-download-percent">${percent}%</span>` : ''}
                    ${canPause ? `<button class="download-mini-btn" type="button" data-download-action="pause" data-download-id="${item.id}">Pause</button>` : ''}
                    ${canResume ? `<button class="download-mini-btn" type="button" data-download-action="resume" data-download-id="${item.id}">${item.status === 'failed' ? 'Retry' : 'Resume'}</button>` : ''}
                    ${canCancel ? `<button class="download-mini-btn cmv-download-cancel" type="button" data-download-action="cancel" data-download-id="${item.id}">Cancel</button>` : ''}
                </div>
            </div>
            <div class="model-download-track${indeterminate ? ' is-indeterminate' : ''}"><div class="model-download-fill" style="width:${Math.max(0, Math.min(100, Number(item.progress || 0)))}%"></div></div>
            ${item.error ? `<p class="model-download-error">${esc(item.error)}</p>` : ''}
        </div>`;
    }).join('');
    paintHealth(state.health || { status: 'checking', message: 'Checking local components' });
}

async function loadDownloads() {
    const id = state.modelId;
    if (!id) return;
    try {
        const data = await json(`/api/simple/downloads?profile_id=${encodeURIComponent(id)}`);
        if (state.modelId !== id) return;
        state.downloads = latestDownloads(data.items || []);
        paintDownloads();
        if (state.downloads.some(item => ['queued', 'downloading'].includes(item.status))) {
            startDownloadPolling();
        }
    } catch {}
}

async function installModel() {
    if (!state.modelId) return;
    const button = $('model-install');
    button.disabled = true;
    button.querySelector('span').textContent = 'Preparing…';
    try {
        const data = await json(`/api/simple/models/${encodeURIComponent(state.modelId)}/install`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: '{}',
        });
        if (Array.isArray(data.downloads) && data.downloads.length) {
            state.downloads = latestDownloads(data.downloads);
            paintDownloads();
            startDownloadPolling();
        } else {
            await loadDownloads();
            await loadHealth();
        }
        if (data.unavailable?.length) {
            error('Some components could not be installed', data.unavailable.join('\n'));
        }
    } catch (err) {
        if (err.data?.open_settings) openRuntimeSettings();
            error('Could not start download', err.message);
    } finally {
        button.disabled = false;
        paintHealth(state.health || {});
    }
}

async function downloadAction(id, action) {
    try {
        await json(`/api/simple/downloads/${id}/${action}`, { method: 'POST' });
        await loadDownloads();
        if (action === 'resume') startDownloadPolling();
    } catch (err) {
            error('Could not update download', err.message);
    }
}

function startDownloadPolling() {
    clearInterval(state.downloadPoll);
    state.downloadPoll = setInterval(async () => {
        await loadDownloads();
        const active = state.downloads.some(item => ['queued', 'downloading'].includes(item.status));
        if (!active) {
            clearInterval(state.downloadPoll);
            state.downloadPoll = null;
            if (state.downloads.length && state.downloads.every(item => item.status === 'completed')) {
                setTimeout(() => {
                    loadHealth(true);
                    loadDownloads();
                }, 450);
            }
        }
    }, 850);
}

function shuffleArray(arr) {
    const copy = [...arr];
    for (let i = copy.length - 1; i > 0; i--) {
        const j = Math.floor(Math.random() * (i + 1));
        [copy[i], copy[j]] = [copy[j], copy[i]];
    }
    return copy;
}

function refillAmbientDeck() {
    if (!state.ambient.length) {
        state.ambientDeck = [];
        return;
    }
    const recentSet = new Set(state.ambientHistory);
    const unseen = state.ambient.filter(item => !recentSet.has(item.id || item));
    const seen = state.ambient.filter(item => recentSet.has(item.id || item));

    const shuffledUnseen = shuffleArray(unseen);
    const shuffledSeen = shuffleArray(seen);
    let newDeck = [...shuffledUnseen, ...shuffledSeen];

    // Avoid immediate repeat with currently shown image
    if (newDeck.length > 1 && (newDeck[0]?.id || newDeck[0]) === state.ambientCurrent) {
        const first = newDeck.shift();
        newDeck.push(first);
    }
    state.ambientDeck = newDeck;
}

async function loadMoreAmbient() {
    if (state.ambientLoadingMore) return;
    state.ambientLoadingMore = true;
    try {
        const data = await json('/api/simple/ambient?limit=72');
        const items = Array.isArray(data.items) ? data.items : [];
        if (items.length) {
            const existingIds = new Set(state.ambient.map(it => it.id || it));
            const newItems = items.filter(it => !existingIds.has(it.id || it));
            if (newItems.length) {
                state.ambient.push(...newItems);
                setCachedJson('cmv_simple_ambient_items', state.ambient.slice(0, 120), true);
                state.ambientDeck.push(...shuffleArray(newItems));
            }
        }
    } catch {}
    finally {
        state.ambientLoadingMore = false;
    }
}

async function loadAmbient() {
    try {
        const data = await json('/api/simple/ambient?limit=72');
        const items = Array.isArray(data.items) ? data.items : [];
        if (items.length) {
            state.ambient = items;
            setCachedJson('cmv_simple_ambient_items', items, true);
            refillAmbientDeck();
            preloadAmbientPool();
            if (!document.querySelector('.ambient-container.has-ambient')) {
                ambientPick();
            }
            restartAmbientTimer();
        }
    } catch {}
}

function ambientPick(resetTimer = true) {
    if (!state.ambient.length) return;
    if (!state.ambientDeck.length) {
        refillAmbientDeck();
    }
    let nextItem = state.ambientDeck.shift();
    if (!nextItem) return;

    // Check if nextItem matches current active image
    const nextKey = nextItem.id || (typeof nextItem === 'string' ? nextItem : nextItem.preview_url);
    if (nextKey === state.ambientCurrent && state.ambientDeck.length > 0) {
        const alt = state.ambientDeck.shift();
        state.ambientDeck.push(nextItem);
        nextItem = alt;
    }

    state.ambientCurrent = nextItem.id || (typeof nextItem === 'string' ? nextItem : nextItem.preview_url);
    state.ambientHistory.push(state.ambientCurrent);
    if (state.ambientHistory.length > 30) {
        state.ambientHistory.shift();
    }

    setAmbient(nextItem);
    preloadAmbientPool();

    if (resetTimer) {
        restartAmbientTimer();
    }

    if (state.ambientDeck.length < 8) {
        loadMoreAmbient();
    }
}

function preloadAmbientPool() {
    const items = state.ambientDeck.slice(0, 4);
    for (const item of items) {
        const src = typeof item === 'string' ? item : item?.original_url || item?.preview_url || item?.thumbnail_url;
        if (src) {
            const img = new Image();
            img.src = src;
        }
    }
}

function setAmbient(item) {
    const primary = typeof item === 'string' ? item : item?.original_url || item?.preview_url;
    const fallback = typeof item === 'object' ? item?.preview_url || item?.thumbnail_url : null;
    if (!primary) return;
    const image = new Image();
    image.onload = () => applyAmbient(primary);
    image.onerror = () => {
        if (fallback && fallback !== primary) {
            const alt = new Image();
            alt.onload = () => applyAmbient(fallback);
            alt.src = fallback;
        }
    };
    image.src = primary;
}

function applyAmbient(url) {
    const next = state.layer ? $('ambient-a') : $('ambient-b');
    const previous = state.layer ? $('ambient-b') : $('ambient-a');
    const nextBg = state.layer ? $('ambient-backdrop-a') : $('ambient-backdrop-b');
    const prevBg = state.layer ? $('ambient-backdrop-b') : $('ambient-backdrop-a');
    const container = document.querySelector('.ambient-container');
    if (!next || !previous) return;
    const formattedUrl = `url("${String(url).replaceAll('"', '%22')}")`;
    next.style.backgroundImage = formattedUrl;
    next.classList.add('active');
    previous.classList.remove('active');
    if (nextBg && prevBg) {
        nextBg.style.backgroundImage = formattedUrl;
        nextBg.classList.add('active');
        prevBg.classList.remove('active');
    }
    if (container) container.classList.add('has-ambient');
    try { localStorage.setItem('cmv_simple_ambient_last', url); } catch {}
    state.layer = state.layer ? 0 : 1;
}

async function loadAi() {
    const cached = getCachedJson('cmv_ai_status', 120 * 1000);
    if (cached) {
        const available = Boolean(cached.available && cached.has_text);
        $('ai-toggle').disabled = !available;
        $('ai-toggle-wrap').classList.toggle('is-unavailable', !available);
        $('ai-toggle').checked = available && state.improve;
    }
    try {
        const data = await json('/api/simple/ai-status');
        setCachedJson('cmv_ai_status', data, false);
        const available = Boolean(data.available && data.has_text);
        $('ai-toggle').disabled = !available;
        $('ai-toggle-wrap').classList.toggle('is-unavailable', !available);
        $('ai-toggle').checked = available && state.improve;
    } catch {
        if (!cached) {
            $('ai-toggle').disabled = true;
            $('ai-toggle-wrap').classList.add('is-unavailable');
        }
    }
}

function syncCanvasAspect() {
    const map = { '1:1': '1 / 1', '3:4': '3 / 4', '4:3': '4 / 3', '9:16': '9 / 16', '16:9': '16 / 9' };
    const aspect = map[state.ratio] || '3 / 4';
    const [width, height] = state.ratio.split(':').map(Number);
    const defaultCanvasWidth = Math.round(Math.min(760, Math.max(360, 520 * (width / height) / (3 / 4))));
    const limits = canvasWidthLimits();
    const canvasColumnWidth = state.canvasWidth
        ? Math.round(Math.max(limits.min, Math.min(limits.max, state.canvasWidth)))
        : defaultCanvasWidth;
    if (state.canvasWidth) state.canvasWidth = canvasColumnWidth;
    const layout = $('studio-layout');
    const card = document.querySelector('.studio-canvas-card');
    const surface = $('canvas');
    if (layout) layout.style.setProperty('--canvas-column-width', `${canvasColumnWidth}px`);
    if (card) card.style.setProperty('--canvas-aspect', aspect);
    if (surface) surface.style.setProperty('--canvas-aspect', aspect);
    syncCanvasRowHeight();
}

function syncCanvasRowHeight() {
    const layout = $('studio-layout');
    const controls = document.querySelector('.studio-controls-card');
    const canvas = document.querySelector('.studio-canvas-card');
    if (!layout || !controls || !['generating', 'result'].includes(layout.dataset.view)) return;
    const controlsH = Math.ceil(controls.getBoundingClientRect().height);
    const canvasH = canvas ? Math.ceil(canvas.getBoundingClientRect().height) : 0;
    const height = Math.max(controlsH, canvasH);
    if (height > 0) layout.style.setProperty('--studio-split-height', `${height}px`);
}

function canvasWidthLimits() {
    const min = 360;
    return { min, max: 1100 };
}

function wireCanvasResize() {
    const card = document.querySelector('.studio-canvas-card');
    const layout = $('studio-layout');
    if (!card || !layout || card.querySelector('.canvas-resize-handle')) return;
    const handle = document.createElement('button');
    handle.type = 'button';
    handle.className = 'canvas-resize-handle';
    handle.setAttribute('aria-label', 'Resize result panel');
    handle.title = 'Drag to resize';
    card.appendChild(handle);

    let startX = 0;
    let startWidth = 0;
    const onMove = event => {
        const limits = canvasWidthLimits();
        const nextWidth = Math.round(Math.max(limits.min, Math.min(limits.max, startWidth + event.clientX - startX)));
        state.canvasWidth = nextWidth;
        layout.style.setProperty('--canvas-column-width', `${nextWidth}px`);
        save('cmv_simple_canvas_width', nextWidth);
    };
    const onUp = () => {
        window.removeEventListener('pointermove', onMove);
        window.removeEventListener('pointerup', onUp);
        window.removeEventListener('pointercancel', onUp);
        handle.classList.remove('is-resizing');
    };
    handle.addEventListener('pointerdown', event => {
        event.preventDefault();
        startX = event.clientX;
        startWidth = card.getBoundingClientRect().width;
        handle.classList.add('is-resizing');
        handle.setPointerCapture?.(event.pointerId);
        window.addEventListener('pointermove', onMove);
        window.addEventListener('pointerup', onUp, { once: true });
        window.addEventListener('pointercancel', onUp, { once: true });
    });
    window.addEventListener('resize', () => {
        if (!state.canvasWidth) return;
        const limits = canvasWidthLimits();
        state.canvasWidth = Math.max(limits.min, Math.min(limits.max, state.canvasWidth));
        layout.style.setProperty('--canvas-column-width', `${state.canvasWidth}px`);
        save('cmv_simple_canvas_width', state.canvasWidth);
    });
}

function syncRatio() {
    const allowed = new Set((model()?.aspect_ratios || []).map(item => item.ratio));
    if (allowed.size && !allowed.has(state.ratio)) state.ratio = model().aspect_ratios[0].ratio;
    document.querySelectorAll('[data-ratio]').forEach(button => {
        const enabled = !allowed.size || allowed.has(button.dataset.ratio);
        button.disabled = !enabled;
        button.classList.toggle('active', enabled && button.dataset.ratio === state.ratio);
    });
    syncCanvasAspect();
}

function syncQuality() {
    const presets = model()?.quality_presets || {};
    if (!presets[state.quality]) {
        state.quality = presets.standard ? 'standard' : Object.keys(presets)[0] || 'standard';
    }
    document.querySelectorAll('[data-quality]').forEach(button => {
        button.disabled = Boolean(Object.keys(presets).length && !presets[button.dataset.quality]);
        button.classList.toggle('active', button.dataset.quality === state.quality);
    });
}

function syncBatch() {
    document.querySelectorAll('[data-batch]').forEach(button => {
        button.classList.toggle('active', Number(button.dataset.batch) === state.batch);
    });
}

function wire() {
    $('model-select-trigger')?.addEventListener('click', () => toggleModelMenu());
    $('model-select-menu')?.addEventListener('click', event => {
        const option = event.target.closest('[data-model-id]');
        if (option) chooseModel(option.dataset.modelId);
    });
    document.addEventListener('click', event => {
        if (!event.target.closest('#model-combobox')) closeModelMenu();
    });
    document.querySelectorAll('[data-ratio]').forEach(button => {
        button.onclick = () => {
            if (button.disabled) return;
            state.ratio = button.dataset.ratio;
            save('cmv_simple_ratio', state.ratio);
            syncRatio();
        };
    });
    document.querySelectorAll('[data-quality]').forEach(button => {
        button.onclick = () => {
            if (button.disabled) return;
            state.quality = button.dataset.quality;
            save('cmv_simple_quality', state.quality);
            syncQuality();
        };
    });
    document.querySelectorAll('[data-batch]').forEach(button => {
        button.onclick = () => {
            state.batch = Number(button.dataset.batch);
            save('cmv_simple_batch', state.batch);
            syncBatch();
        };
    });

    $('prompt').oninput = () => {
        resizePrompt();
        $('prompt-clear').hidden = !$('prompt').value.trim();
        save('cmv_simple_prompt', $('prompt').value);
        if (!state.applyingAiPrompt && state.aiExpandedPrompt && $('prompt').value !== state.aiExpandedPrompt) {
            state.aiOriginalPrompt = null;
            state.aiExpandedPrompt = null;
            try {
                localStorage.removeItem('cmv_simple_ai_original_prompt');
                localStorage.removeItem('cmv_simple_ai_expanded_prompt');
            } catch {}
        }
    };
    $('prompt-clear').onclick = () => {
        $('prompt').value = '';
        $('prompt').dispatchEvent(new Event('input'));
        $('prompt').focus();
    };
    $('ai-toggle').onchange = event => {
        state.improve = event.target.checked;
        save('cmv_simple_ai_improve', state.improve);
    };
    $('ai-always-toggle')?.addEventListener('change', event => {
        state.alwaysImprove = event.target.checked;
        save('cmv_simple_ai_always', state.alwaysImprove);
    });
    $('reference-input').onchange = event => {
        if (event.target.files?.[0]) reference(event.target.files[0]);
    };
    $('reference-remove').onclick = clearReference;
    dropZone();
    $('create').onclick = create;
    $('error-close').onclick = hideError;
    $('result-download').onclick = downloadResult;
    $('result-edit').onclick = () => { clearLastResult(); canvas('idle'); $('prompt').focus(); };
    $('model-recheck').onclick = async () => {
        const btn = $('model-recheck');
        btn.disabled = true;
        btn.textContent = 'Checking…';
        try {
            sessionStorage.removeItem('cmv_health_' + state.modelId);
            await loadHealth(true);
            await loadDownloads();
        } finally {
            btn.disabled = false;
            btn.textContent = 'Check again';
        }
    };
    $('model-downloads').addEventListener('click', event => {
        const button = event.target.closest('[data-download-action]');
        if (button) downloadAction(Number(button.dataset.downloadId), button.dataset.downloadAction);
    });

    $('runtime-settings-open').onclick = openRuntimeSettings;
    $('runtime-settings-close').onclick = closeRuntimeSettings;
    $('runtime-settings-cancel').onclick = closeRuntimeSettings;
    $('runtime-settings-backdrop').onclick = closeRuntimeSettings;
    $('runtime-browse').onclick = browseRuntimePath;
    $('runtime-test').onclick = testRuntime;
    $('runtime-settings-form').onsubmit = saveRuntimeSettings;

    $('ai-open').onclick = openAssistant;
    $('assistant-close').onclick = closeAssistant;
    $('assistant-backdrop').onclick = closeAssistant;
    $('assistant-new').onclick = () => { state.history = []; assistantWelcome(); };
    $('assistant-form').onsubmit = assistantSend;
    $('assistant-input').onkeydown = event => {
        if (event.key === 'Enter' && !event.shiftKey) {
            event.preventDefault();
            $('assistant-form').requestSubmit();
        }
    };
    addEventListener('keydown', event => {
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            create();
        }
        if (event.key === 'Escape') {
            closeModelMenu();
            closeAssistant();
            closeRuntimeSettings();
            closeContextMenu();
        }
    });
    document.addEventListener('contextmenu', openStudioContextMenu);
    document.addEventListener('click', event => {
        if (!event.target.closest('.image-context-menu')) closeContextMenu();
    });
    window.addEventListener('scroll', closeContextMenu, { passive: true });
    assistantWelcome();
}

function resizePrompt() {
    const textarea = $('prompt');
    if (!textarea) return;
    const minH = 84;
    const maxH = 220;
    textarea.style.height = 'auto';
    const targetH = Math.max(minH, Math.min(textarea.scrollHeight, maxH));
    textarea.style.height = `${targetH}px`;
    textarea.style.overflowY = textarea.scrollHeight > maxH ? 'auto' : 'hidden';
}

function dropZone() {
    const zone = $('prompt-box');
    ['dragenter', 'dragover'].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault();
        zone.classList.add('is-dragging-reference');
    }));
    ['dragleave', 'drop'].forEach(name => zone.addEventListener(name, event => {
        event.preventDefault();
        zone.classList.remove('is-dragging-reference');
    }));
    zone.addEventListener('drop', event => {
        const file = [...(event.dataTransfer?.files || [])].find(item => item.type.startsWith('image/'));
        if (file) reference(file);
    });
}

function reference(file) {
    if (!file.type.startsWith('image/')) return error('Could not add image', 'Choose an image file.');
    if (file.size > MAX_REF) return error('Image is too large', 'Choose a reference file smaller than 20 MB.');
    const reader = new FileReader();
    reader.onload = () => {
        clearReference(false);
        state.ref = String(reader.result);
        state.refUrl = URL.createObjectURL(file);
        $('reference-name').textContent = file.name;
        $('reference-img').src = state.refUrl;
        $('reference-preview').hidden = false;
    };
    reader.onerror = () => error('Could not read image', 'Try another file.');
    reader.readAsDataURL(file);
}

function clearReference(clearInput = true) {
    state.ref = null;
    if (state.refUrl) URL.revokeObjectURL(state.refUrl);
    state.refUrl = null;
    $('reference-img').removeAttribute('src');
    $('reference-preview').hidden = true;
    if (clearInput) $('reference-input').value = '';
}

function blocking() {
    if (state.health?.status === 'not_installed') return 'Install the missing components for the selected model first.';
    if (state.health?.status === 'workflow_pending') return 'This model workflow is still being calibrated.';
    return '';
}

async function create() {
    if (state.run) return;
    const why = blocking();
    if (why) return error('Model is not ready yet', why);
    const visiblePrompt = $('prompt').value.trim();
    const promptIsAiExpanded = state.aiExpandedPrompt && visiblePrompt === state.aiExpandedPrompt;
    const improveWithAi = state.improve && (state.alwaysImprove || !promptIsAiExpanded);
    const prompt = state.alwaysImprove && state.aiOriginalPrompt
        ? state.aiOriginalPrompt.trim()
        : visiblePrompt;
    if (!prompt && !state.ref) return error('Nothing to create', 'Describe an idea or add an image reference.');
    hideError();
    canvas('generating');
    state.generationProgress = 5;
    createButton(true, 5, 'Starting…');
    try {
        const data = await json('/api/simple/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: state.modelId,
                prompt,
                improve_with_ai: improveWithAi,
                aspect_ratio: state.ratio,
                quality: state.quality,
                batch_size: state.batch,
                reference_image: state.ref,
            }),
        });
        state.run = data.run_id;
        if (data.ai_improved && data.positive_prompt) {
            applyAiPrompt(data.positive_prompt, state.aiOriginalPrompt || visiblePrompt);
        }
        pollRun();
    } catch (err) {
        createButton(false);
        canvas('idle');
        if (err.data?.missing_resources) {
            paintHealth({
                status: 'not_installed',
                message: 'Missing components',
                missing_resources: err.data.missing_resources,
                installable: true,
            });
        }
        if (err.status === 502 || err.status === 503 || err.data?.code === 'comfyui_rejected' || err.data?.code === 'comfyui_connection_failed') {
            error(
                'ComfyUI is unavailable or rejected the task',
                err.data?.suggestion || 'Make sure ComfyUI is running at http://127.0.0.1:8188. If you use another host or port, configure it with the gear icon in the header.'
            );
        } else {
            error('Could not start generation', err.message);
        }
    }
}

function pollRun() {
    clearInterval(state.poll);
    let percent = 8;
    state.poll = setInterval(async () => {
        try {
            const data = await json(`/api/simple/runs/${state.run}`);
            if (['queued', 'running'].includes(data.status)) {
                percent = Math.min(92, percent + 5);
                state.generationProgress = percent;
                const total = Math.max(1, Number(state.batch) || 1);
                const completed = Math.min(total, Array.isArray(data.outputs) ? data.outputs.length : 0);
                const current = completed > 0
                    ? Math.min(total, completed + 1)
                    : Math.min(total, Math.max(1, Math.ceil((percent / 92) * total)));
                createButton(true, percent, `${percent}% · ${current}/${total}`);
                $('generating-text').textContent = total > 1
                    ? `Creating image ${current} of ${total}…`
                    : 'Creating image…';
                return;
            }
            if (data.status === 'completed') {
                stopRunPolling();
                createButton(false);
                showResult(data.outputs || []);
            } else if (data.is_complete) {
                stopRunPolling();
                createButton(false);
                canvas('idle');
                const rawError = data.run?.error || data.run?.last_error || '';
                let runError = '';
                if (typeof rawError === 'string') {
                    runError = rawError;
                } else if (rawError && typeof rawError === 'object') {
                    const msg = rawError.message || rawError.error || '';
                    const tech = rawError.technical_message || '';
                    const node = rawError.class_type ? ` (node: ${rawError.class_type})` : '';
                    runError = tech && tech !== msg ? `${msg}${node}\n${tech}` : `${msg}${node}`;
                    if (!runError) runError = JSON.stringify(rawError);
                }
                const statusLabel = data.status === 'failed' ? 'Generation failed' : 'Generation stopped';
                const detail = runError
                    || (data.status === 'cancelled' ? 'Generation was cancelled.' : 'The process finished without a result. ComfyUI may not have processed the task; check its logs.');
                error(statusLabel, detail);
            }
        } catch {}
    }, 1000);
}

function stopRunPolling() {
    clearInterval(state.poll);
    state.poll = null;
    state.run = null;
}

function playSuccessChime() {
    try {
        const AudioCtx = window.AudioContext || window.webkitAudioContext;
        if (!AudioCtx) return;
        const ctx = new AudioCtx();
        const now = ctx.currentTime;
        const notes = [659.25, 987.77, 1318.51];
        notes.forEach((freq, i) => {
            const osc = ctx.createOscillator();
            const gain = ctx.createGain();
            osc.type = 'sine';
            osc.frequency.setValueAtTime(freq, now + i * 0.08);
            gain.gain.setValueAtTime(0.12, now + i * 0.08);
            gain.gain.exponentialRampToValueAtTime(0.0001, now + i * 0.08 + 0.6);
            osc.connect(gain);
            gain.connect(ctx.destination);
            osc.start(now + i * 0.08);
            osc.stop(now + i * 0.08 + 0.65);
        });
        setTimeout(() => { try { ctx.close(); } catch {} }, 1200);
    } catch {}
}

function showResult(outputs) {
    renderResult(outputs, true);
}

function renderResult(outputs, persist = false) {
    const validOutputs = (Array.isArray(outputs) ? outputs : []).filter(output => {
        const url = output?.preview_url || output?.thumbnail_url;
        return output && typeof url === 'string' && url;
    });
    const first = validOutputs[0];
    if (!first) {
        if (persist) error('Result not found', 'Generation finished without an available image.');
        return;
    }

    state.lastOutputs = validOutputs;
    state.selectedResultIndex = 0;
    state.last = validOutputs[0];

    updateResultView();

    if (persist) setCachedJson('cmv_simple_last_result', { outputs: validOutputs, ratio: state.ratio }, true);
    canvas('result');
    setAmbient(first.preview_url || first.thumbnail_url);
    if (persist && state.sound) playSuccessChime();
}

function updateResultView() {
    const validOutputs = state.lastOutputs || [];
    const index = Math.max(0, Math.min(validOutputs.length - 1, state.selectedResultIndex || 0));
    state.selectedResultIndex = index;
    const current = validOutputs[index] || state.last;
    if (!current) return;
    state.last = current;

    const artwork = document.querySelector('.canvas-artwork-wrap');
    const url = current.preview_url || current.thumbnail_url;
    if (artwork) {
        artwork.innerHTML = `<img id="result-img" class="canvas-result-img" src="${esc(url)}" alt="Result ${index + 1}" decoding="async">`;
        artwork.onclick = () => openResultFullscreen(state.selectedResultIndex);
    }

    const thumbsContainer = $('result-thumbnails');
    if (thumbsContainer) {
        if (validOutputs.length > 1) {
            thumbsContainer.hidden = false;
            thumbsContainer.innerHTML = validOutputs.map((output, i) => {
                const thumbUrl = output.thumbnail_url || output.preview_url;
                const isActive = i === index;
                return `<button type="button" class="canvas-thumb-btn${isActive ? ' active' : ''}" data-index="${i}" aria-label="Превью ${i + 1}" title="Изображение ${i + 1}"><img src="${esc(thumbUrl)}" alt="Превью ${i + 1}" class="canvas-thumb-img" decoding="async"></button>`;
            }).join('');
            thumbsContainer.querySelectorAll('.canvas-thumb-btn').forEach(btn => {
                btn.onclick = event => {
                    event.stopPropagation();
                    const nextIdx = Number(btn.dataset.index);
                    selectResultIndex(nextIdx);
                };
            });
        } else {
            thumbsContainer.hidden = true;
            thumbsContainer.innerHTML = '';
        }
    }
}

function selectResultIndex(index) {
    if (!state.lastOutputs || !state.lastOutputs[index]) return;
    state.selectedResultIndex = index;
    state.last = state.lastOutputs[index];
    const current = state.last;
    const url = current.preview_url || current.thumbnail_url;

    const img = document.querySelector('.canvas-artwork-wrap .canvas-result-img');
    if (img) {
        img.src = url;
        img.alt = `Result ${index + 1}`;
    }

    const thumbsContainer = $('result-thumbnails');
    if (thumbsContainer) {
        thumbsContainer.querySelectorAll('.canvas-thumb-btn').forEach((btn, i) => {
            btn.classList.toggle('active', i === index);
        });
    }

    setAmbient(url);
}

function canvas(view) {
    const layout = $('studio-layout');
    layout.dataset.view = view;
    $('generating').hidden = view !== 'generating';
    $('result').hidden = view !== 'result';
    resizePrompt();
    if (view === 'generating' || view === 'result') {
        syncCanvasAspect();
        requestAnimationFrame(() => {
            syncCanvasRowHeight();
            requestAnimationFrame(syncCanvasRowHeight);
        });
    } else {
        layout.style.removeProperty('--studio-split-height');
    }
}

function createButton(running, percent = 0, text = 'Creating…') {
    const button = $('create');
    button.classList.toggle('running', running);
    button.disabled = running;
    $('progress-fill').style.width = `${running ? percent : 0}%`;
    $('progress-text').textContent = running ? text : 'Starting…';
}

function error(title, text) {
    $('error-title').textContent = title;
    $('error-text').textContent = text;
    $('error').hidden = false;
}

function hideError() { $('error').hidden = true; }

function downloadResult() {
    const url = state.last?.preview_url || state.last?.thumbnail_url;
    if (!url) return;
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = state.last.filename || `creation-${Date.now()}.png`;
    anchor.click();
}

function runtimeDetection(kind, title, text) {
    const card = $('runtime-detection');
    card.className = `runtime-detection-card${kind ? ` is-${kind}` : ''}`;
    $('runtime-detection-title').textContent = title;
    $('runtime-detection-text').textContent = text;
}

function runtimeStatusText(status) {
    if (!status) return 'ComfyUI status is unknown.';
    if (['ready', 'external'].includes(status.status)) return `ComfyUI is available at ${status.host || '127.0.0.1'}:${status.port || 8188}.`;
    if (status.status === 'busy') return 'ComfyUI is connected and currently generating.';
    if (status.last_error) return status.last_error;
    return `Current status: ${status.status || 'unknown'}.`;
}

function paintRuntimeDot() {
    const dot = $('runtime-settings-dot');
    dot.className = 'runtime-settings-dot';
    if (state.runtimeStatus && ['ready', 'external', 'busy'].includes(state.runtimeStatus.status)) dot.classList.add('is-ready');
    else if (state.runtimeConfig?.install_path) dot.classList.add('is-configured');
}

async function loadRuntimeSummary() {
    const cachedConfig = getCachedJson('cmv_runtime_config', 120 * 1000);
    const cachedStatus = getCachedJson('cmv_runtime_status', 30 * 1000);
    if (cachedConfig) state.runtimeConfig = cachedConfig;
    if (cachedStatus) {
        state.runtimeStatus = cachedStatus;
        paintRuntimeDot();
    }
    const [configResult, statusResult] = await Promise.allSettled([
        json('/api/comfyui/config'),
        json('/api/comfyui/status'),
    ]);
    if (configResult.status === 'fulfilled') {
        state.runtimeConfig = configResult.value;
        setCachedJson('cmv_runtime_config', configResult.value, false);
    }
    if (statusResult.status === 'fulfilled') {
        state.runtimeStatus = statusResult.value;
        setCachedJson('cmv_runtime_status', statusResult.value, false);
    }
    paintRuntimeDot();
}

async function openRuntimeSettings() {
    $('runtime-settings-backdrop').hidden = false;
    $('runtime-settings-dialog').hidden = false;
    document.body.classList.add('simple-modal-open');
    await loadRuntimeSummary();
    const config = state.runtimeConfig || {};
    $('runtime-install-path').value = config.install_path || '';
    $('runtime-python').value = config.custom_python || '';
    $('runtime-host').value = config.host || '127.0.0.1';
    $('runtime-port').value = config.port || 8188;
    $('runtime-civitai-token').value = '';
    if (config.install_path) {
        await detectRuntimePath();
    } else {
        runtimeDetection('', 'No path selected yet', runtimeStatusText(state.runtimeStatus));
    }
}

function closeRuntimeSettings() {
    const dialog = $('runtime-settings-dialog');
    if (!dialog || dialog.hidden) return;
    $('runtime-settings-backdrop').hidden = true;
    dialog.hidden = true;
    document.body.classList.remove('simple-modal-open');
}

async function browseRuntimePath() {
    const button = $('runtime-browse');
    button.disabled = true;
    button.textContent = 'Opening…';
    try {
        const data = await json('/api/simple/pick-comfyui-directory', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ initial_path: $('runtime-install-path').value.trim() }),
        });
        if (!data.cancelled && data.path) {
            $('runtime-install-path').value = data.path;
            paintDetectionResult(data.detection);
        }
    } catch (err) {
        runtimeDetection('error', 'Could not open folder picker', err.message);
    } finally {
        button.disabled = false;
        button.textContent = 'Browse…';
    }
}

function paintDetectionResult(detection) {
    if (!detection) return runtimeDetection('error', 'Path not checked', 'Could not get the check result.');
    if (detection.is_valid) {
        runtimeDetection('good', 'ComfyUI found', detection.comfy_dir || detection.root_path || 'Path recognized.');
    } else if (detection.comfy_dir) {
        runtimeDetection('warning', 'ComfyUI folder found', `${detection.comfy_dir}. ${detection.error || 'Python was not detected; model downloads are still available.'}`);
    } else {
        runtimeDetection('error', 'ComfyUI not found', detection.error || 'main.py was not found in this folder.');
    }
}

async function detectRuntimePath() {
    const path = $('runtime-install-path').value.trim();
    if (!path) return runtimeDetection('', 'No path selected', runtimeStatusText(state.runtimeStatus));
    runtimeDetection('', 'Checking path…', path);
    try {
        const data = await json('/api/comfyui/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, custom_python: $('runtime-python').value.trim() || null }),
        });
        paintDetectionResult(data);
        return data;
    } catch (err) {
        runtimeDetection('error', 'Check failed', err.message);
        return null;
    }
}

async function testRuntime() {
    const button = $('runtime-test');
    button.disabled = true;
    button.textContent = 'Checking…';
    try {
        await detectRuntimePath();
        const status = await json('/api/comfyui/status');
        state.runtimeStatus = status;
        if (['ready', 'external', 'busy'].includes(status.status)) {
            runtimeDetection('good', 'ComfyUI available', runtimeStatusText(status));
        } else {
            runtimeDetection('warning', 'Path will be saved, but the server is not responding', runtimeStatusText(status));
        }
        paintRuntimeDot();
    } catch (err) {
        runtimeDetection('warning', 'ComfyUI is currently unavailable', err.message);
    } finally {
        button.disabled = false;
    button.textContent = 'Test';
    }
}

async function saveRuntimeSettings(event) {
    event.preventDefault();
    const saveButton = $('runtime-save');
    saveButton.disabled = true;
    saveButton.textContent = 'Saving…';
    const payload = {
        install_path: $('runtime-install-path').value.trim(),
        custom_python: $('runtime-python').value.trim(),
        host: $('runtime-host').value.trim() || '127.0.0.1',
        port: Number($('runtime-port').value) || 8188,
    };
    const token = $('runtime-civitai-token').value.trim();
    if (token) payload.civitai_api_token = token;
    try {
        await json('/api/comfyui/config', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        await loadRuntimeSummary();
        closeRuntimeSettings();
        await loadHealth();
        await loadDownloads();
    } catch (err) {
        runtimeDetection('error', 'Could not save settings', err.message);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = 'Save';
    }
}

function openAssistant() {
    $('assistant-backdrop').hidden = false;
    $('assistant').hidden = false;
    $('assistant-input').focus();
}

function closeAssistant() {
    $('assistant-backdrop').hidden = true;
    $('assistant').hidden = true;
}

function assistantWelcome() {
    $('assistant-messages').innerHTML = '<div class="assistant-message assistant-message-system"><strong>Let’s refine your prompt</strong><p>We can work on composition, lighting, mood or wording.</p></div>';
}

function addMsg(role, text) {
    const div = document.createElement('div');
    div.className = `assistant-message assistant-message-${role}`;
    div.textContent = text;
    $('assistant-messages').appendChild(div);
    $('assistant-messages').scrollTop = $('assistant-messages').scrollHeight;
    return div;
}

async function assistantSend(event) {
    event.preventDefault();
    const text = $('assistant-input').value.trim();
    if (!text) return;
    $('assistant-input').value = '';
    addMsg('user', text);
    const pending = addMsg('assistant', 'Thinking…');
    $('assistant-send').disabled = true;
    try {
        const data = await json('/api/simple/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                current_prompt: $('prompt').value,
                profile_id: state.modelId,
                history: state.history,
            }),
        });
        pending.textContent = data.reply;
        const suggestedPrompt = String(data.suggested_prompt || data.reply || '').trim();
        if (suggestedPrompt) applyAiPrompt(suggestedPrompt);
        state.history.push({ role: 'user', content: text }, { role: 'assistant', content: data.reply });
    } catch (err) {
        pending.textContent = err.message;
    } finally {
        $('assistant-send').disabled = false;
    }
}

let activeContextMenu = null;

function closeContextMenu() {
    if (activeContextMenu) {
        activeContextMenu.remove();
        activeContextMenu = null;
    }
}

function createMenuItem({ icon, label, badge, onClick }) {
    const btn = document.createElement('button');
    btn.type = 'button';
    btn.className = 'image-context-menu__item';
    btn.innerHTML = `${icon}<span class="image-context-menu__item-label">${esc(label)}</span>${badge ? `<span class="image-context-menu__badge">${esc(badge)}</span>` : ''}`;
    btn.addEventListener('click', () => {
        closeContextMenu();
        if (onClick) onClick();
    });
    return btn;
}

function createSubmenuItem({ icon, label, badge, items }) {
    const wrap = document.createElement('div');
    wrap.className = 'image-context-menu__submenu-wrap';

    const parentBtn = document.createElement('button');
    parentBtn.type = 'button';
    parentBtn.className = 'image-context-menu__item image-context-menu__item--submenu';
    parentBtn.innerHTML = `${icon}<span class="image-context-menu__item-label">${esc(label)}</span>${badge ? `<span class="image-context-menu__badge">${esc(badge)}</span>` : ''}<span class="image-context-menu__chevron" aria-hidden="true">›</span>`;

    const submenu = document.createElement('div');
    submenu.className = 'image-context-menu image-context-menu--submenu';
    submenu.hidden = true;

    items.forEach(it => {
        const itemBtn = document.createElement('button');
        itemBtn.type = 'button';
        itemBtn.className = 'image-context-menu__item';
        itemBtn.innerHTML = `${it.icon || '<span style="width:16px;display:inline-block;text-align:center;font-weight:700;color:var(--accent,#2dd4bf);flex-shrink:0">' + (it.active ? '✓' : '') + '</span>'}<span class="image-context-menu__item-label">${esc(it.label)}</span>`;
        itemBtn.addEventListener('click', e => {
            e.stopPropagation();
            closeContextMenu();
            if (it.onClick) it.onClick();
        });
        submenu.appendChild(itemBtn);
    });

    const openSub = () => {
        submenu.hidden = false;
        const rect = wrap.getBoundingClientRect();
        if (rect.right + 220 > window.innerWidth) {
            submenu.classList.add('image-context-menu--opens-left');
        } else {
            submenu.classList.remove('image-context-menu--opens-left');
        }
    };
    const closeSub = () => {
        submenu.hidden = true;
    };

    wrap.addEventListener('pointerenter', openSub);
    wrap.addEventListener('pointerleave', closeSub);

    wrap.appendChild(parentBtn);
    wrap.appendChild(submenu);
    return wrap;
}

function createSliderItem({ icon, label, min, max, step, value, format, onInput, onChange }) {
    const wrap = document.createElement('div');
    wrap.className = 'image-context-menu__slider-item';
    wrap.addEventListener('click', e => e.stopPropagation());
    wrap.addEventListener('mousedown', e => e.stopPropagation());
    wrap.addEventListener('contextmenu', e => e.stopPropagation());

    const header = document.createElement('div');
    header.className = 'image-context-menu__slider-header';

    const titleWrap = document.createElement('span');
    titleWrap.className = 'image-context-menu__slider-title';
    titleWrap.innerHTML = `${icon}<span>${esc(label)}</span>`;

    const valBadge = document.createElement('span');
    valBadge.className = 'image-context-menu__slider-val';
    valBadge.textContent = format ? format(value) : value;

    header.appendChild(titleWrap);
    header.appendChild(valBadge);

    const range = document.createElement('input');
    range.type = 'range';
    range.className = 'image-context-menu__range';
    range.min = String(min);
    range.max = String(max);
    range.step = String(step || 1);
    range.value = String(value);

    range.addEventListener('input', () => {
        const num = Number(range.value);
        valBadge.textContent = format ? format(num) : num;
        if (onInput) onInput(num);
    });

    range.addEventListener('change', () => {
        const num = Number(range.value);
        if (onChange) onChange(num);
    });

    wrap.appendChild(header);
    wrap.appendChild(range);
    return wrap;
}

function openStudioContextMenu(event) {
    if (event.target.closest('input, textarea, [contenteditable="true"]')) {
        return;
    }
    event.preventDefault();
    closeContextMenu();

    const menu = document.createElement('div');
    menu.className = 'image-context-menu studio-context-menu';

    const title = document.createElement('div');
    title.className = 'image-context-menu__title';
    title.textContent = 'Studio settings';
    menu.appendChild(title);

    menu.appendChild(createMenuItem({
        icon: '<svg viewBox="0 0 24 24"><path d="M21.5 2v6h-6M21.34 15.57a10 10 0 1 1-.57-8.38l5.67-5.67"/></svg>',
        label: 'Change background',
        onClick: () => ambientPick(),
    }));

    const sep1 = document.createElement('div');
    sep1.className = 'image-context-menu__separator';
    menu.appendChild(sep1);

    menu.appendChild(createSliderItem({
        icon: '<svg viewBox="0 0 24 24"><polygon points="12 2 2 7 12 12 22 7 12 2"/><polyline points="2 17 12 22 22 17"/><polyline points="2 12 12 17 22 12"/></svg>',
        label: 'Card opacity',
        min: 10,
        max: 95,
        step: 1,
        value: state.opacity ?? 44,
        format: v => `${v}%`,
        onInput: v => {
            state.opacity = v;
            applyVisualSettings();
        },
        onChange: v => {
            state.opacity = v;
            save('cmv_simple_glass_opacity', state.opacity);
        },
    }));

    menu.appendChild(createSliderItem({
        icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="4"/><line x1="12" y1="1" x2="12" y2="4"/><line x1="12" y1="20" x2="12" y2="23"/><line x1="1" y1="12" x2="4" y2="12"/><line x1="20" y1="12" x2="23" y2="12"/></svg>',
        label: 'Background blur',
        min: 0,
        max: 40,
        step: 1,
        value: state.blur ?? 10,
        format: v => (v === 0 ? 'No blur' : `${v} px`),
        onInput: v => {
            state.blur = v;
            applyVisualSettings();
        },
        onChange: v => {
            state.blur = v;
            save('cmv_simple_ambient_blur', state.blur);
        },
    }));

    menu.appendChild(createSliderItem({
        icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>',
        label: 'Change interval',
        min: 0,
        max: 600,
        step: 15,
        value: Math.round((state.interval || 0) / 1000),
        format: v => {
            if (v === 0) return 'Disabled';
            if (v < 60) return `${v} sec`;
            const m = Math.floor(v / 60);
            const s = v % 60;
            return s ? `${m} min ${s} sec` : `${m} min`;
        },
        onInput: v => {
            state.interval = v * 1000;
        },
        onChange: v => {
            state.interval = v * 1000;
            save('cmv_simple_ambient_interval', state.interval);
            restartAmbientTimer();
        },
    }));

    const sep2 = document.createElement('div');
    sep2.className = 'image-context-menu__separator';
    menu.appendChild(sep2);

    const fitLabels = {
        cover: 'Cover',
        contain: 'Contain',
        original: '1:1',
    };
    menu.appendChild(createSubmenuItem({
        icon: '<svg viewBox="0 0 24 24"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>',
        label: 'Background fit',
        badge: fitLabels[state.fit] || 'Cover',
        items: [
            {
                label: 'Cover',
                active: state.fit === 'cover',
                onClick: () => {
                    state.fit = 'cover';
                    save('cmv_simple_ambient_fit', state.fit);
                    applyVisualSettings();
                },
            },
            {
                label: 'Contain',
                active: state.fit === 'contain',
                onClick: () => {
                    state.fit = 'contain';
                    save('cmv_simple_ambient_fit', state.fit);
                    applyVisualSettings();
                },
            },
            {
                label: 'Original (1:1)',
                active: state.fit === 'original',
                onClick: () => {
                    state.fit = 'original';
                    save('cmv_simple_ambient_fit', state.fit);
                    applyVisualSettings();
                },
            },
        ],
    }));

    menu.appendChild(createMenuItem({
        icon: '<svg viewBox="0 0 24 24"><path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9M13.73 21a2 2 0 0 1-3.46 0"/></svg>',
        label: 'Completion sound',
        badge: state.sound ? 'On' : 'Off',
        onClick: () => {
            state.sound = !state.sound;
            save('cmv_simple_sound_alert', state.sound);
            if (state.sound) playSuccessChime();
        },
    }));

    menu.appendChild(createMenuItem({
        icon: '<svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.7 1.7 0 0 0 .34 1.88l.06.06-2.83 2.83-.06-.06A1.7 1.7 0 0 0 15 19.4a1.7 1.7 0 0 0-1 .6 1.7 1.7 0 0 0-.4 1.1V21H9.6v-.1A1.7 1.7 0 0 0 8.5 19.4a1.7 1.7 0 0 0-1.88.34l-.06.06-2.83-2.83.06-.06A1.7 1.7 0 0 0 8.5 4.1a1.7 1.7 0 0 0 1-.6 1.7 1.7 0 0 0 .4-1.1V2h4v.4A1.7 1.7 0 0 0 15 4.1a1.7 1.7 0 0 0 1.88-.34l.06-.06 2.83 2.83-.06.06A1.7 1.7 0 0 0 19.4 8.5a1.7 1.7 0 0 0 .6 1 1.7 1.7 0 0 0 1.1.4h.9v4h-.9a1.7 1.7 0 0 0-1.7 1.1Z"/></svg>',
        label: 'ComfyUI settings…',
        onClick: () => openRuntimeSettings(),
    }));

    document.body.appendChild(menu);
    activeContextMenu = menu;

    const menuRect = menu.getBoundingClientRect();
    let x = event.clientX;
    let y = event.clientY;
    if (x + menuRect.width > window.innerWidth - 8) {
        x = Math.max(8, window.innerWidth - menuRect.width - 8);
    }
    if (y + menuRect.height > window.innerHeight - 8) {
        y = Math.max(8, window.innerHeight - menuRect.height - 8);
    }
    menu.style.left = `${x}px`;
    menu.style.top = `${y}px`;
}

document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
