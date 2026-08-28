/* Create page continuity: preserve active work across navigation and enrich long-running task UI. */

const CREATE_PATH = '/create';
const RUN_KEY = 'cmv_simple_active_run';
const RUN_PROGRESS_KEY = 'cmv_simple_active_run_progress';
const PROMPT_KEY = 'cmv_simple_prompt_draft';
const POLL_MS = 1000;

if (typeof window !== 'undefined' && window.location.pathname === CREATE_PATH) {
    const nativeFetch = window.fetch.bind(window);
    let activeRunId = null;
    let runPoll = null;
    let restoredOutput = null;
    let latestDownloadItems = [];
    let downloadObserver = null;

    const sessionGet = key => {
        try { return sessionStorage.getItem(key); } catch { return null; }
    };
    const sessionSet = (key, value) => {
        try { sessionStorage.setItem(key, String(value)); } catch {}
    };
    const sessionRemove = key => {
        try { sessionStorage.removeItem(key); } catch {}
    };

    function requestUrl(input) {
        if (typeof input === 'string') return input;
        if (input instanceof URL) return input.href;
        return input?.url || '';
    }

    function requestMethod(input, init) {
        return String(init?.method || input?.method || 'GET').toUpperCase();
    }

    function normalizePath(url) {
        try { return new URL(url, window.location.origin).pathname; }
        catch { return String(url || '').split('?')[0]; }
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

    function percentFor(item) {
        if (item?.status === 'completed') return 100;
        if (!Number(item?.file_size_bytes || 0)) return null;
        return Math.max(0, Math.min(100, Math.round(Number(item?.progress || 0))));
    }

    function injectStyles() {
        if (document.getElementById('cmv-continuity-styles')) return;
        const style = document.createElement('style');
        style.id = 'cmv-continuity-styles';
        style.textContent = `
            .model-download-copy{position:relative}
            .cmv-download-percent{display:inline-flex;align-items:center;justify-content:center;min-width:38px;height:20px;padding:0 7px;border-radius:999px;background:color-mix(in srgb,var(--accent,#ed6f9b) 11%,transparent);color:var(--accent,#ed6f9b);font-size:9px;font-weight:800;font-variant-numeric:tabular-nums}
            .cmv-download-cancel{border-color:color-mix(in srgb,#d87575 38%,var(--border-subtle,rgba(255,255,255,.09)))!important;color:#d98a8a!important}
            .cmv-download-cancel:hover{background:rgba(216,117,117,.08)!important;color:#efaaaa!important}
            .cmv-download-cancel:disabled{opacity:.5;cursor:wait}
        `;
        document.head.appendChild(style);
    }

    function enhanceDownloadRows() {
        const wrap = document.getElementById('model-downloads');
        if (!wrap || !latestDownloadItems.length) return;
        const rows = [...wrap.querySelectorAll('.model-download-row')];
        rows.forEach((row, index) => {
            const item = latestDownloadItems[index];
            if (!item) return;
            const actions = row.querySelector('.model-download-actions');
            if (!actions) return;

            const percent = percentFor(item);
            let badge = actions.querySelector('.cmv-download-percent');
            if (percent !== null) {
                if (!badge) {
                    badge = document.createElement('span');
                    badge.className = 'cmv-download-percent';
                    actions.prepend(badge);
                }
                const text = `${percent}%`;
                if (badge.textContent !== text) badge.textContent = text;
            } else if (badge) {
                badge.remove();
            }

            const canCancel = ['queued', 'downloading', 'paused'].includes(item.status) && Number(item.id) > 0;
            let cancel = actions.querySelector('.cmv-download-cancel');
            if (canCancel && !cancel) {
                cancel = document.createElement('button');
                cancel.type = 'button';
                cancel.className = 'download-mini-btn cmv-download-cancel';
                cancel.dataset.cmvDownloadCancel = String(item.id);
                cancel.textContent = 'Отмена';
                actions.appendChild(cancel);
            } else if (!canCancel && cancel) {
                cancel.remove();
            }
        });
    }

    function scheduleDownloadEnhancement(items) {
        latestDownloadItems = latestDownloads(items);
        requestAnimationFrame(() => requestAnimationFrame(enhanceDownloadRows));
    }

    function clearActiveRun() {
        activeRunId = null;
        clearInterval(runPoll);
        runPoll = null;
        sessionRemove(RUN_KEY);
        sessionRemove(RUN_PROGRESS_KEY);
    }

    function setCreateProgress(percent, label) {
        const button = document.getElementById('create');
        const fill = document.getElementById('progress-fill');
        const text = document.getElementById('progress-text');
        const generating = document.getElementById('generating-text');
        const layout = document.getElementById('studio-layout');
        const generatingView = document.getElementById('generating');
        const resultView = document.getElementById('result');
        if (!button || !fill || !text || !layout) return;
        const safePercent = Math.max(5, Math.min(92, Number(percent) || 8));
        button.classList.add('running');
        button.disabled = true;
        fill.style.width = `${safePercent}%`;
        text.textContent = `${safePercent}%`;
        layout.dataset.view = 'generating';
        if (generatingView) generatingView.hidden = false;
        if (resultView) resultView.hidden = true;
        if (generating) generating.textContent = label || 'Создаём изображение…';
    }

    function showRestoredResult(outputs) {
        const output = outputs?.[0];
        if (!output) return false;
        restoredOutput = output;
        const image = document.getElementById('result-img');
        const layout = document.getElementById('studio-layout');
        const generatingView = document.getElementById('generating');
        const resultView = document.getElementById('result');
        const createButton = document.getElementById('create');
        const progressFill = document.getElementById('progress-fill');
        const progressText = document.getElementById('progress-text');
        if (image) image.src = output.preview_url || output.thumbnail_url || '';
        if (layout) layout.dataset.view = 'result';
        if (generatingView) generatingView.hidden = true;
        if (resultView) resultView.hidden = false;
        if (createButton) {
            createButton.classList.remove('running');
            createButton.disabled = false;
        }
        if (progressFill) progressFill.style.width = '0%';
        if (progressText) progressText.textContent = 'Запуск…';
        return true;
    }

    function showRunFailure(message) {
        const title = document.getElementById('error-title');
        const text = document.getElementById('error-text');
        const banner = document.getElementById('error');
        const layout = document.getElementById('studio-layout');
        const generatingView = document.getElementById('generating');
        const resultView = document.getElementById('result');
        const createButton = document.getElementById('create');
        if (title) title.textContent = 'Генерация остановилась';
        if (text) text.textContent = message || 'Процесс завершился без результата.';
        if (banner) banner.hidden = false;
        if (layout) layout.dataset.view = 'idle';
        if (generatingView) generatingView.hidden = true;
        if (resultView) resultView.hidden = true;
        if (createButton) {
            createButton.classList.remove('running');
            createButton.disabled = false;
        }
    }

    async function readRun(runId) {
        const response = await nativeFetch(`/api/simple/runs/${encodeURIComponent(runId)}`, { cache: 'no-store' });
        if (!response.ok) throw new Error(`${response.status}`);
        return response.json();
    }

    function handleRunSnapshot(data, runId) {
        if (!data || runId !== activeRunId) return true;
        if (['queued', 'running'].includes(data.status)) {
            let progress = Math.max(8, Number(sessionGet(RUN_PROGRESS_KEY)) || 8);
            progress = Math.min(92, progress + 4);
            sessionSet(RUN_PROGRESS_KEY, progress);
            setCreateProgress(progress, 'Создаём изображение…');
            return false;
        }
        if (data.status === 'completed') {
            clearActiveRun();
            showRestoredResult(data.outputs || []);
            return true;
        }
        if (data.is_complete) {
            clearActiveRun();
            showRunFailure(data.error || 'Процесс завершился без результата.');
            return true;
        }
        return false;
    }

    async function pollRestoredRun() {
        if (!activeRunId) return;
        const runId = activeRunId;
        try {
            const data = await readRun(runId);
            if (handleRunSnapshot(data, runId)) return;
        } catch {
            clearActiveRun();
            showRunFailure('Не удалось восстановить состояние предыдущей генерации.');
            return;
        }
        clearInterval(runPoll);
        runPoll = setInterval(async () => {
            if (!activeRunId) return;
            const currentId = activeRunId;
            try {
                const data = await readRun(currentId);
                if (handleRunSnapshot(data, currentId)) clearInterval(runPoll);
            } catch {
                clearActiveRun();
                showRunFailure('Связь с выполнявшейся генерацией потеряна.');
            }
        }, POLL_MS);
    }

    function restoreEditorState() {
        injectStyles();
        const prompt = document.getElementById('prompt');
        const savedPrompt = sessionGet(PROMPT_KEY);
        if (prompt && savedPrompt !== null && !prompt.value) {
            prompt.value = savedPrompt;
            prompt.dispatchEvent(new Event('input', { bubbles: true }));
        }
        const savedRun = sessionGet(RUN_KEY);
        if (savedRun) {
            activeRunId = savedRun;
            setCreateProgress(Number(sessionGet(RUN_PROGRESS_KEY)) || 8, 'Возвращаемся к генерации…');
            pollRestoredRun();
        }
        const downloads = document.getElementById('model-downloads');
        if (downloads && !downloadObserver) {
            downloadObserver = new MutationObserver(() => enhanceDownloadRows());
            downloadObserver.observe(downloads, { childList: true, subtree: true });
        }
    }

    window.fetch = async function cmvContinuityFetch(input, init) {
        const url = requestUrl(input);
        const method = requestMethod(input, init);
        const response = await nativeFetch(input, init);
        const path = normalizePath(url);

        if (method === 'POST' && path === '/api/simple/generate' && response.ok) {
            restoredOutput = null;
            response.clone().json().then(data => {
                if (!data?.run_id) return;
                activeRunId = String(data.run_id);
                sessionSet(RUN_KEY, activeRunId);
                sessionSet(RUN_PROGRESS_KEY, 8);
                const prompt = document.getElementById('prompt');
                if (prompt) sessionSet(PROMPT_KEY, prompt.value);
            }).catch(() => {});
        }

        if (method === 'GET' && path === '/api/simple/downloads' && response.ok) {
            response.clone().json().then(data => scheduleDownloadEnhancement(data?.items || [])).catch(() => {});
        }

        if (method === 'GET' && path.startsWith('/api/simple/runs/') && response.ok) {
            response.clone().json().then(data => {
                if (data?.status === 'completed' || data?.is_complete) clearActiveRun();
            }).catch(() => {});
        }
        return response;
    };

    document.addEventListener('input', event => {
        if (event.target?.id === 'prompt') sessionSet(PROMPT_KEY, event.target.value);
    }, true);

    document.addEventListener('click', async event => {
        const cancel = event.target.closest?.('[data-cmv-download-cancel]');
        if (cancel) {
            event.preventDefault();
            const id = Number(cancel.dataset.cmvDownloadCancel);
            if (!id || cancel.disabled) return;
            cancel.disabled = true;
            cancel.textContent = 'Отмена…';
            try {
                await nativeFetch(`/api/simple/downloads/${id}/cancel`, { method: 'POST' });
                document.getElementById('model-recheck')?.click();
            } finally {
                cancel.disabled = false;
                cancel.textContent = 'Отмена';
            }
            return;
        }

        if (restoredOutput && event.target.closest?.('#result-download')) {
            event.preventDefault();
            event.stopImmediatePropagation();
            const url = restoredOutput.preview_url || restoredOutput.thumbnail_url;
            if (!url) return;
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = restoredOutput.filename || `creation-${Date.now()}.png`;
            anchor.click();
        }
    }, true);

    document.addEventListener('keydown', event => {
        if (!activeRunId) return;
        if ((event.ctrlKey || event.metaKey) && event.key === 'Enter') {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', () => setTimeout(restoreEditorState, 0), { once: true });
    } else {
        setTimeout(restoreEditorState, 0);
    }
}
