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
    ref: null,
    refUrl: null,
    ambient: [],
    layer: 0,
    timer: null,
    run: null,
    poll: null,
    last: null,
    history: [],
    downloads: [],
    downloadPoll: null,
    modelMenuOpen: false,
    runtimeConfig: null,
    runtimeStatus: null,
};

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

function restore() {
    try {
        state.modelId = localStorage.getItem('cmv_simple_model') || document.body.dataset.defaultModelId || '';
        state.ratio = localStorage.getItem('cmv_simple_ratio') || '1:1';
        state.quality = localStorage.getItem('cmv_simple_quality') || 'standard';
        state.batch = Math.max(1, Math.min(4, Number(localStorage.getItem('cmv_simple_batch')) || 1));
        const ai = localStorage.getItem('cmv_simple_ai_improve');
        if (ai !== null) state.improve = ai === 'true';
    } catch {}
}

function esc(value) {
    const div = document.createElement('div');
    div.textContent = String(value ?? '');
    return div.innerHTML;
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
    if (!state.models.some(item => item.id === state.modelId)) {
        state.modelId = state.models[0]?.id || '';
    }
    renderCatalog();
    wire();
    syncModel();
    syncRatio();
    syncQuality();
    syncBatch();
    resizePrompt();
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
    if ($('model-selected-name')) $('model-selected-name').textContent = current?.name || 'Модель';
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
    $('model-vram').textContent = current.vram_rec_gb ? `Рекомендуется ${current.vram_rec_gb} GB VRAM` : '';
    state.health = null;
    paintHealth({ status: 'checking', message: 'Проверяем локальные компоненты' });
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
        ready: ['is-ready', 'Готова'],
        not_installed: ['is-missing', 'Нужна установка'],
        workflow_pending: ['is-pending', 'Workflow готовится'],
        unknown: ['is-checking', 'Не проверено'],
        checking: ['is-checking', 'Проверяем'],
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
    const active = state.downloads.some(item => ['queued', 'downloading'].includes(item.status));
    install.hidden = !(health?.status === 'not_installed' && health?.installable !== false);
    install.disabled = active;
    install.querySelector('span').textContent = active ? 'Загрузка…' : 'Скачать недостающее';
    panel.hidden = !rows.length && !state.downloads.length && ['ready', 'checking'].includes(health?.status);
}

async function loadHealth() {
    const id = state.modelId;
    if (!id) return;
    try {
        const data = await json(`/api/simple/models/${encodeURIComponent(id)}/status`);
        if (state.modelId === id) paintHealth(data.health || {});
    } catch {
        if (state.modelId === id) {
            paintHealth({ status: 'unknown', message: 'Не удалось проверить локальные компоненты' });
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
        queued: 'В очереди',
        downloading: item.file_size_bytes ? `${Math.round(item.progress || 0)}%` : 'Загрузка…',
        paused: 'Пауза',
        completed: 'Готово',
        failed: 'Ошибка',
        cancelled: 'Отменено',
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
        const indeterminate = item.status === 'downloading' && !item.file_size_bytes;
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
                    ${canPause ? `<button class="download-mini-btn" type="button" data-download-action="pause" data-download-id="${item.id}">Пауза</button>` : ''}
                    ${canResume ? `<button class="download-mini-btn" type="button" data-download-action="resume" data-download-id="${item.id}">${item.status === 'failed' ? 'Повторить' : 'Продолжить'}</button>` : ''}
                </div>
            </div>
            <div class="model-download-track${indeterminate ? ' is-indeterminate' : ''}"><div class="model-download-fill" style="width:${Math.max(0, Math.min(100, Number(item.progress || 0)))}%"></div></div>
            ${item.error ? `<p class="model-download-error">${esc(item.error)}</p>` : ''}
        </div>`;
    }).join('');
    paintHealth(state.health || { status: 'checking', message: 'Проверяем локальные компоненты' });
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
    button.querySelector('span').textContent = 'Подготовка…';
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
            error('Не все компоненты удалось поставить', data.unavailable.join('\n'));
        }
    } catch (err) {
        if (err.data?.open_settings) openRuntimeSettings();
        error('Не удалось начать загрузку', err.message);
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
        error('Не удалось изменить загрузку', err.message);
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
                setTimeout(loadHealth, 450);
            }
        }
    }, 850);
}

async function loadAmbient() {
    try {
        const data = await json('/api/simple/ambient?limit=36');
        state.ambient = Array.isArray(data.items) ? data.items : [];
        if (state.ambient.length) {
            ambientPick();
            if (state.ambient.length > 1) state.timer = setInterval(ambientPick, ROTATE);
        }
    } catch {}
}

function ambientPick() {
    setAmbient(state.ambient[Math.floor(Math.random() * state.ambient.length)]);
}

function setAmbient(item) {
    const primary = typeof item === 'string' ? item : item?.preview_url;
    const fallback = typeof item === 'object' ? item?.thumbnail_url : null;
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
    if (!next || !previous) return;
    next.style.backgroundImage = `url("${String(url).replaceAll('"', '%22')}")`;
    next.classList.add('active');
    previous.classList.remove('active');
    state.layer = state.layer ? 0 : 1;
}

async function loadAi() {
    try {
        const data = await json('/api/simple/ai-status');
        const available = Boolean(data.available && data.has_text);
        $('ai-toggle').disabled = !available;
        $('ai-toggle-wrap').classList.toggle('is-unavailable', !available);
        $('ai-toggle').checked = available && state.improve;
    } catch {
        $('ai-toggle').disabled = true;
        $('ai-toggle-wrap').classList.add('is-unavailable');
    }
}

function syncRatio() {
    const allowed = new Set((model()?.aspect_ratios || []).map(item => item.ratio));
    if (allowed.size && !allowed.has(state.ratio)) state.ratio = model().aspect_ratios[0].ratio;
    document.querySelectorAll('[data-ratio]').forEach(button => {
        const enabled = !allowed.size || allowed.has(button.dataset.ratio);
        button.disabled = !enabled;
        button.classList.toggle('active', enabled && button.dataset.ratio === state.ratio);
    });
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
    $('reference-input').onchange = event => {
        if (event.target.files?.[0]) reference(event.target.files[0]);
    };
    $('reference-remove').onclick = clearReference;
    dropZone();
    $('create').onclick = create;
    $('error-close').onclick = hideError;
    $('result-download').onclick = downloadResult;
    $('result-edit').onclick = () => { canvas('idle'); $('prompt').focus(); };
    $('model-install').onclick = installModel;
    $('model-recheck').onclick = async () => { await loadHealth(); await loadDownloads(); };
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
        }
    });
    assistantWelcome();
}

function resizePrompt() {
    const textarea = $('prompt');
    if (!textarea) return;
    textarea.style.height = 'auto';
    textarea.style.height = `${Math.max(112, Math.min(textarea.scrollHeight, 240))}px`;
    textarea.style.overflowY = textarea.scrollHeight > 240 ? 'auto' : 'hidden';
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
    if (!file.type.startsWith('image/')) return error('Не получилось добавить изображение', 'Выберите файл изображения.');
    if (file.size > MAX_REF) return error('Изображение слишком большое', 'Для референса выберите файл меньше 20 МБ.');
    const reader = new FileReader();
    reader.onload = () => {
        clearReference(false);
        state.ref = String(reader.result);
        state.refUrl = URL.createObjectURL(file);
        $('reference-name').textContent = file.name;
        $('reference-img').src = state.refUrl;
        $('reference-preview').hidden = false;
    };
    reader.onerror = () => error('Не удалось прочитать изображение', 'Попробуйте другой файл.');
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
    if (state.health?.status === 'not_installed') return 'Сначала установите отсутствующие компоненты выбранной модели.';
    if (state.health?.status === 'workflow_pending') return 'Workflow этой модели ещё калибруется.';
    return '';
}

async function create() {
    if (state.run) return;
    const why = blocking();
    if (why) return error('Модель пока не готова', why);
    const prompt = $('prompt').value.trim();
    if (!prompt && !state.ref) return error('Нечего создавать', 'Напишите идею или добавьте изображение-ориентир.');
    hideError();
    canvas('generating');
    createButton(true, 5, 'Запуск…');
    try {
        const data = await json('/api/simple/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                profile_id: state.modelId,
                prompt,
                improve_with_ai: state.improve,
                aspect_ratio: state.ratio,
                quality: state.quality,
                batch_size: state.batch,
                reference_image: state.ref,
            }),
        });
        state.run = data.run_id;
        pollRun();
    } catch (err) {
        createButton(false);
        canvas('idle');
        if (err.data?.missing_resources) {
            paintHealth({
                status: 'not_installed',
                message: 'Не хватает компонентов',
                missing_resources: err.data.missing_resources,
                installable: true,
            });
        }
        error('Не удалось начать генерацию', err.message);
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
                createButton(true, percent, `${percent}%`);
                $('generating-text').textContent = 'Создаём изображение…';
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
                error('Генерация остановилась', 'Процесс завершился без результата.');
            }
        } catch {}
    }, 1000);
}

function stopRunPolling() {
    clearInterval(state.poll);
    state.poll = null;
    state.run = null;
}

function showResult(outputs) {
    const output = outputs[0];
    if (!output) return error('Результат не найден', 'Генерация завершилась без доступного изображения.');
    state.last = output;
    $('result-img').src = output.preview_url || output.thumbnail_url;
    canvas('result');
    setAmbient(output.preview_url || output.thumbnail_url);
}

function canvas(view) {
    $('studio-layout').dataset.view = view;
    $('generating').hidden = view !== 'generating';
    $('result').hidden = view !== 'result';
}

function createButton(running, percent = 0, text = 'Создание…') {
    const button = $('create');
    button.classList.toggle('running', running);
    button.disabled = running;
    $('progress-fill').style.width = `${running ? percent : 0}%`;
    $('progress-text').textContent = running ? text : 'Запуск…';
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
    if (!status) return 'Статус ComfyUI пока неизвестен.';
    if (['ready', 'external'].includes(status.status)) return `ComfyUI доступен на ${status.host || '127.0.0.1'}:${status.port || 8188}.`;
    if (status.status === 'busy') return 'ComfyUI подключён и сейчас занят генерацией.';
    if (status.last_error) return status.last_error;
    return `Текущий статус: ${status.status || 'неизвестно'}.`;
}

function paintRuntimeDot() {
    const dot = $('runtime-settings-dot');
    dot.className = 'runtime-settings-dot';
    if (state.runtimeStatus && ['ready', 'external', 'busy'].includes(state.runtimeStatus.status)) dot.classList.add('is-ready');
    else if (state.runtimeConfig?.install_path) dot.classList.add('is-configured');
}

async function loadRuntimeSummary() {
    const [configResult, statusResult] = await Promise.allSettled([
        json('/api/comfyui/config'),
        json('/api/comfyui/status'),
    ]);
    if (configResult.status === 'fulfilled') state.runtimeConfig = configResult.value;
    if (statusResult.status === 'fulfilled') state.runtimeStatus = statusResult.value;
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
        runtimeDetection('', 'Путь ещё не выбран', runtimeStatusText(state.runtimeStatus));
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
    button.textContent = 'Открываем…';
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
        runtimeDetection('error', 'Не удалось открыть выбор папки', err.message);
    } finally {
        button.disabled = false;
        button.textContent = 'Обзор…';
    }
}

function paintDetectionResult(detection) {
    if (!detection) return runtimeDetection('error', 'Путь не проверен', 'Не удалось получить результат проверки.');
    if (detection.is_valid) {
        runtimeDetection('good', 'ComfyUI найден', detection.comfy_dir || detection.root_path || 'Путь распознан.');
    } else if (detection.comfy_dir) {
        runtimeDetection('warning', 'Папка ComfyUI найдена', `${detection.comfy_dir}. ${detection.error || 'Python не определён; скачивание моделей всё равно доступно.'}`);
    } else {
        runtimeDetection('error', 'ComfyUI не найден', detection.error || 'В этой папке не найден main.py.');
    }
}

async function detectRuntimePath() {
    const path = $('runtime-install-path').value.trim();
    if (!path) return runtimeDetection('', 'Путь не выбран', runtimeStatusText(state.runtimeStatus));
    runtimeDetection('', 'Проверяем путь…', path);
    try {
        const data = await json('/api/comfyui/detect', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path, custom_python: $('runtime-python').value.trim() || null }),
        });
        paintDetectionResult(data);
        return data;
    } catch (err) {
        runtimeDetection('error', 'Ошибка проверки', err.message);
        return null;
    }
}

async function testRuntime() {
    const button = $('runtime-test');
    button.disabled = true;
    button.textContent = 'Проверяем…';
    try {
        await detectRuntimePath();
        const status = await json('/api/comfyui/status');
        state.runtimeStatus = status;
        if (['ready', 'external', 'busy'].includes(status.status)) {
            runtimeDetection('good', 'ComfyUI доступен', runtimeStatusText(status));
        } else {
            runtimeDetection('warning', 'Путь сохранится, но сервер не отвечает', runtimeStatusText(status));
        }
        paintRuntimeDot();
    } catch (err) {
        runtimeDetection('warning', 'ComfyUI сейчас недоступен', err.message);
    } finally {
        button.disabled = false;
        button.textContent = 'Проверить';
    }
}

async function saveRuntimeSettings(event) {
    event.preventDefault();
    const saveButton = $('runtime-save');
    saveButton.disabled = true;
    saveButton.textContent = 'Сохраняем…';
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
        runtimeDetection('error', 'Не удалось сохранить настройки', err.message);
    } finally {
        saveButton.disabled = false;
        saveButton.textContent = 'Сохранить';
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
    $('assistant-messages').innerHTML = '<div class="assistant-message assistant-message-system"><strong>Помогу уточнить запрос</strong><p>Можно разобрать композицию, свет, настроение или формулировку.</p></div>';
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
    const pending = addMsg('assistant', 'Думаю…');
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
        state.history.push({ role: 'user', content: text }, { role: 'assistant', content: data.reply });
    } catch (err) {
        pending.textContent = err.message;
    } finally {
        $('assistant-send').disabled = false;
    }
}

document.readyState === 'loading'
    ? document.addEventListener('DOMContentLoaded', init)
    : init();
