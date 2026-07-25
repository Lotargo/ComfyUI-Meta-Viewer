const MEDIA_SELECTOR = '.gallery-card .img-wrapper > img, .image-item .item-thumb > img';
const INITIAL_GALLERY_LIMIT = 8;
const INITIAL_SIDEBAR_LIMIT = 6;

const readiness = new WeakMap();
const settleCallbacks = new WeakMap();

const stylesheetReady = new Promise(resolve => {
    const existing = document.querySelector('link[data-viewer-media-loading]');
    if (existing) {
        if (existing.sheet) resolve();
        else {
            existing.addEventListener('load', resolve, { once: true });
            existing.addEventListener('error', resolve, { once: true });
        }
        return;
    }

    const link = document.createElement('link');
    link.rel = 'stylesheet';
    link.href = '/static/css/features/viewer-media-loading.css';
    link.dataset.viewerMediaLoading = '';
    link.addEventListener('load', resolve, { once: true });
    link.addEventListener('error', resolve, { once: true });
    document.head.append(link);
});

function timeout(delay) {
    return new Promise(resolve => window.setTimeout(resolve, delay));
}

function isManagedImage(target) {
    return target instanceof HTMLImageElement && target.matches(MEDIA_SELECTOR);
}

function registerImage(image) {
    if (readiness.has(image)) return readiness.get(image);

    image.decoding = 'async';

    let resolveReady;
    const promise = new Promise(resolve => {
        resolveReady = resolve;
    });

    readiness.set(image, promise);
    settleCallbacks.set(image, async failed => {
        if (image.dataset.mediaSettled === 'true') return;
        image.dataset.mediaSettled = 'true';

        if (!failed && typeof image.decode === 'function') {
            try {
                await Promise.race([image.decode(), timeout(750)]);
            } catch {
                // A completed image can still be safely revealed when decode() rejects.
            }
        }

        image.classList.toggle('media-loaded', !failed);
        image.classList.toggle('media-load-error', failed);
        resolveReady();
    });

    if (image.complete) {
        queueMicrotask(() => {
            settleCallbacks.get(image)?.(image.naturalWidth === 0);
        });
    }

    return promise;
}

function scanManagedImages(root = document) {
    const images = [];
    if (root instanceof Element && root.matches(MEDIA_SELECTOR)) images.push(root);
    if (root.querySelectorAll) images.push(...root.querySelectorAll(MEDIA_SELECTOR));
    images.forEach(registerImage);
}

function setInitialLoadingPriorities() {
    document.querySelectorAll('.gallery-card .img-wrapper > img').forEach((image, index) => {
        const eager = index < INITIAL_GALLERY_LIMIT;
        image.loading = eager ? 'eager' : 'lazy';
        if ('fetchPriority' in image) image.fetchPriority = index < 4 ? 'high' : 'auto';
    });

    document.querySelectorAll('.image-item .item-thumb > img').forEach((image, index) => {
        const eager = index < INITIAL_SIDEBAR_LIMIT;
        image.loading = eager ? 'eager' : 'lazy';
        if ('fetchPriority' in image) image.fetchPriority = index < 2 ? 'high' : 'auto';
    });
}

function initialImages() {
    return [
        ...document.querySelectorAll('.gallery-card .img-wrapper > img'),
    ].slice(0, INITIAL_GALLERY_LIMIT).concat([
        ...document.querySelectorAll('.image-item .item-thumb > img'),
    ].slice(0, INITIAL_SIDEBAR_LIMIT));
}

document.addEventListener('load', event => {
    const image = event.target;
    if (!isManagedImage(image)) return;

    // Gallery cards currently include an inline onload handler that changes aspect-ratio
    // and dispatches a synthetic resize. Stopping propagation here prevents repeated
    // full-grid recalculation while preserving the reserved size from indexed metadata.
    event.stopImmediatePropagation();
    registerImage(image);
    settleCallbacks.get(image)?.(false);
}, true);

document.addEventListener('error', event => {
    const image = event.target;
    if (!isManagedImage(image)) return;

    event.stopImmediatePropagation();
    if (image.dataset.mediaType === 'video') image.hidden = true;
    registerImage(image);
    settleCallbacks.get(image)?.(true);
}, true);

const observer = new MutationObserver(mutations => {
    mutations.forEach(mutation => {
        mutation.addedNodes.forEach(node => {
            if (node instanceof Element) scanManagedImages(node);
        });
    });
    setInitialLoadingPriorities();
});

observer.observe(document.documentElement, { childList: true, subtree: true });
scanManagedImages();

export async function waitForInitialMediaReady({ timeoutMs = 1500 } = {}) {
    await stylesheetReady;
    scanManagedImages();
    setInitialLoadingPriorities();

    const targets = initialImages();
    if (!targets.length) return;

    await Promise.race([
        Promise.all(targets.map(registerImage)),
        timeout(timeoutMs),
    ]);
}
