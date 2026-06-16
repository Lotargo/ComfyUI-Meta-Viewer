import { images, lightboxIndex, showToast } from '../state.js';

let currentCutout = null;
let isBusy = false;

function getEls() {
    return {
        panel: document.getElementById('cutout-panel'),
        preview: document.getElementById('cutout-preview'),
        status: document.getElementById('cutout-status'),
        download: document.getElementById('cutout-download'),
        regenerate: document.getElementById('cutout-regenerate'),
        clear: document.getElementById('cutout-clear'),
        close: document.getElementById('cutout-close'),
    };
}

function getActiveImage() {
    return images[lightboxIndex] || null;
}

function cutoutFileName(img) {
    const fileName = img?.file_name || img?.file || 'cutout.png';
    const base = fileName.replace(/\.[^.]+$/, '');
    return `${base}_cutout.png`;
}

function setPanelOpen(open) {
    const { panel } = getEls();
    panel?.classList.toggle('open', open);
}

function setStatus(message) {
    const { status } = getEls();
    if (status) status.textContent = message;
}

function setActionsEnabled({ hasCutout = false, canRequest = Boolean(getActiveImage()?.id) } = {}) {
    const { download, regenerate, clear } = getEls();
    if (download) download.disabled = !hasCutout;
    if (regenerate) regenerate.disabled = !canRequest || isBusy;
    if (clear) clear.disabled = !hasCutout || isBusy;
}

function renderEmpty(message = 'No cutout yet') {
    const { preview } = getEls();
    if (!preview) return;
    preview.replaceChildren();
    const empty = document.createElement('div');
    empty.className = 'cutout-empty';
    empty.textContent = message;
    preview.appendChild(empty);
    currentCutout = null;
    setActionsEnabled();
}

function renderLoading() {
    const { preview } = getEls();
    if (!preview) return;
    preview.innerHTML = `
        <div class="cutout-loading">
            <div class="cutout-spinner"></div>
            <span>Creating transparent PNG...</span>
        </div>
    `;
    setActionsEnabled({ canRequest: true });
}

function renderCutout(url) {
    const { preview } = getEls();
    if (!preview) return;
    const cacheBustUrl = `${url}?t=${Date.now()}`;
    preview.replaceChildren();
    const img = document.createElement('img');
    img.src = cacheBustUrl;
    img.alt = 'Object cutout preview';
    preview.appendChild(img);
    currentCutout = { url, cacheBustUrl, image: getActiveImage() };
    setActionsEnabled({ hasCutout: true, canRequest: true });
}

async function createCutout({ regenerate = false } = {}) {
    const img = getActiveImage();
    if (!img?.id || isBusy) {
        if (!img?.id) {
            setStatus('Cutout is available for images saved in the local database.');
            renderEmpty('No database image selected');
        }
        return;
    }

    isBusy = true;
    setPanelOpen(true);
    setStatus(regenerate ? 'Clearing cached cutout...' : 'Generating cutout...');
    renderLoading();

    try {
        if (regenerate) {
            await fetch(`/api/cutout/${img.id}`, { method: 'DELETE' });
        }

        const resp = await fetch(`/api/cutout/${img.id}`, { method: 'POST' });
        const data = await resp.json();
        if (!resp.ok || data.error) {
            throw new Error(data.error || 'Cutout failed');
        }

        renderCutout(data.cutout_url);
        setStatus(data.cached ? 'Loaded cached transparent PNG.' : 'Transparent PNG ready.');
    } catch (e) {
        renderEmpty('Cutout failed');
        setStatus(e.message || 'Cutout failed');
    } finally {
        isBusy = false;
        setActionsEnabled({ hasCutout: Boolean(currentCutout), canRequest: Boolean(getActiveImage()?.id) });
    }
}

async function clearCutoutCache() {
    const img = getActiveImage();
    if (!img?.id || isBusy) return;

    isBusy = true;
    setStatus('Clearing cached cutout...');
    setActionsEnabled({ hasCutout: Boolean(currentCutout), canRequest: true });

    try {
        const resp = await fetch(`/api/cutout/${img.id}`, { method: 'DELETE' });
        const data = await resp.json();
        if (!resp.ok || data.error) {
            throw new Error(data.error || 'Could not clear cutout cache');
        }
        renderEmpty('No cutout yet');
        setStatus(data.deleted ? 'Cached cutout cleared.' : 'No cached cutout to clear.');
    } catch (e) {
        setStatus(e.message || 'Could not clear cutout cache');
    } finally {
        isBusy = false;
        setActionsEnabled({ hasCutout: Boolean(currentCutout), canRequest: Boolean(getActiveImage()?.id) });
    }
}

export function openCutoutPanel() {
    const img = getActiveImage();
    setPanelOpen(true);
    if (!img) {
        renderEmpty('No image selected');
        setStatus('Open an image first.');
        return;
    }
    createCutout();
}

export function closeCutoutPanel() {
    setPanelOpen(false);
}

export function resetCutoutPanel() {
    currentCutout = null;
    isBusy = false;
    renderEmpty();
    setStatus('Select an object to create a transparent PNG.');
}

export function downloadCutout() {
    if (!currentCutout?.url) return;
    const a = document.createElement('a');
    a.href = currentCutout.url;
    a.download = cutoutFileName(currentCutout.image);
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    showToast('Cutout download started');
}

export function initCutoutEvents() {
    document.getElementById('lb-cutout')?.addEventListener('click', openCutoutPanel);
    document.getElementById('cutout-close')?.addEventListener('click', closeCutoutPanel);
    document.getElementById('cutout-download')?.addEventListener('click', downloadCutout);
    document.getElementById('cutout-clear')?.addEventListener('click', clearCutoutCache);
    document.getElementById('cutout-regenerate')?.addEventListener('click', () => {
        createCutout({ regenerate: true });
    });
}
