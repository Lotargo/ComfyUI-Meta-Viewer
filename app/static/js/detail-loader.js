import { detailCache } from './state.js';

const pendingDetails = new Map();

export async function ensureImageDetail(img) {
    if (!img?.id || detailCache[img.id]) return img;
    if (pendingDetails.has(img.id)) {
        await pendingDetails.get(img.id);
        return img;
    }

    const request = fetch(`/api/assets/${img.id}`)
        .then(async response => {
            if (!response.ok) throw new Error(`Failed to load asset detail: ${response.status}`);
            detailCache[img.id] = await response.json();
        })
        .finally(() => pendingDetails.delete(img.id));
    pendingDetails.set(img.id, request);
    await request;
    return img;
}

export async function renderImageMeta(img) {
    if (img) {
        try {
            await ensureImageDetail(img);
        } catch (error) {
            console.error(error);
        }
    }
    const { renderMeta } = await import('./meta-view.js');
    renderMeta(img || null);
}
