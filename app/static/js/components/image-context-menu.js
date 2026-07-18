const MENU_MARGIN = 8;

const icons = {
    open: '<path d="M14 3h7v7"></path><path d="M10 14 21 3"></path><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"></path>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path><path d="M8 13h8M13 10l3 3-3 3"></path>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="m21 15-5-5L5 21"></path>',
    path: '<rect x="8" y="8" width="11" height="11" rx="2"></rect><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"></path>',
};

let activeMenu = null;

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error) {
        throw new Error(data.error || `${response.status} ${response.statusText}`);
    }
    return data;
}

async function decodeBlob(blob) {
    if (typeof window.createImageBitmap === 'function') {
        return window.createImageBitmap(blob);
    }

    const objectUrl = URL.createObjectURL(blob);
    const image = new Image();
    try {
        await new Promise((resolve, reject) => {
            image.addEventListener('load', resolve, { once: true });
            image.addEventListener('error', reject, { once: true });
            image.src = objectUrl;
        });
        return image;
    } catch (error) {
        URL.revokeObjectURL(objectUrl);
        throw error;
    }
}

async function imageBlobAsPng(blob) {
    if (blob.type.toLowerCase() === 'image/png') return blob;

    const decoded = await decodeBlob(blob);
    try {
        const width = decoded.width || decoded.naturalWidth;
        const height = decoded.height || decoded.naturalHeight;
        if (!width || !height) throw new Error('The image could not be decoded for copying');

        const canvas = document.createElement('canvas');
        canvas.width = width;
        canvas.height = height;
        const context = canvas.getContext('2d');
        if (!context) throw new Error('Image clipboard conversion is unavailable');
        context.drawImage(decoded, 0, 0);

        return new Promise((resolve, reject) => {
            canvas.toBlob(result => {
                if (result) resolve(result);
                else reject(new Error('The image could not be converted for copying'));
            }, 'image/png');
        });
    } finally {
        if (typeof decoded.close === 'function') decoded.close();
        if (decoded instanceof HTMLImageElement && decoded.src.startsWith('blob:')) {
            URL.revokeObjectURL(decoded.src);
        }
    }
}

async function fetchImageAsPng(sourceUrl) {
    const response = await fetch(sourceUrl, { cache: 'no-cache' });
    if (!response.ok) {
        const data = await response.json().catch(() => ({}));
        throw new Error(data.error || 'The original image is unavailable');
    }
    return imageBlobAsPng(await response.blob());
}

async function copyImage(sourceUrl) {
    if (!navigator.clipboard?.write || typeof window.ClipboardItem !== 'function') {
        throw new Error('Copying images is not supported by this browser');
    }
    const pngPromise = fetchImageAsPng(sourceUrl);
    const item = new window.ClipboardItem({ 'image/png': pngPromise });
    await navigator.clipboard.write([item]);
}

function actionButton(action, runAction) {
    const button = document.createElement('button');
    button.className = 'image-context-menu__item';
    button.type = 'button';
    button.setAttribute('role', 'menuitem');
    button.disabled = !action.enabled;
    if (!action.enabled && action.disabledReason) button.title = action.disabledReason;

    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = icons[action.icon];

    const label = document.createElement('span');
    label.textContent = action.label;
    button.append(icon, label);
    button.addEventListener('click', () => runAction(action));
    return button;
}

function menuCoordinates(event, target) {
    if (event.clientX || event.clientY) {
        return { x: event.clientX, y: event.clientY };
    }
    const rect = target?.getBoundingClientRect?.();
    return rect
        ? { x: rect.left + Math.min(28, rect.width / 2), y: rect.top + Math.min(28, rect.height / 2) }
        : { x: MENU_MARGIN, y: MENU_MARGIN };
}

function positionMenu(menu, coordinates) {
    const rect = menu.getBoundingClientRect();
    const left = Math.max(
        MENU_MARGIN,
        Math.min(coordinates.x, window.innerWidth - rect.width - MENU_MARGIN),
    );
    const top = Math.max(
        MENU_MARGIN,
        Math.min(coordinates.y, window.innerHeight - rect.height - MENU_MARGIN),
    );
    menu.style.left = `${left}px`;
    menu.style.top = `${top}px`;
}

export function closeImageContextMenu({ restoreFocus = false } = {}) {
    if (!activeMenu) return;
    const { controller, menu, target } = activeMenu;
    activeMenu = null;
    controller.abort();
    menu.remove();
    if (restoreFocus && target?.isConnected && typeof target.focus === 'function') {
        target.focus({ preventScroll: true });
    }
}

export function showImageContextMenu(event, {
    imageId,
    fileName,
    sourceUrl,
    canAccessOriginal = true,
    hasLocalFile = false,
    anchor = event.currentTarget || event.target,
    notify = () => {},
}) {
    event.preventDefault();
    event.stopPropagation();
    closeImageContextMenu();

    const localFileDisabledReason = 'This image has no available local file';
    const actions = [
        {
            label: 'Open original',
            icon: 'open',
            enabled: Boolean(sourceUrl && canAccessOriginal),
            disabledReason: 'The original image is unavailable',
            run: () => window.open(sourceUrl, '_blank', 'noopener,noreferrer'),
        },
        {
            label: 'Show in folder',
            icon: 'folder',
            enabled: Boolean(imageId && hasLocalFile),
            disabledReason: localFileDisabledReason,
            run: async () => {
                await fetchJson(`/api/images/${imageId}/reveal`, { method: 'POST' });
                notify('Opened in file manager');
            },
        },
        { separator: true },
        {
            label: 'Copy image',
            icon: 'image',
            enabled: Boolean(sourceUrl && canAccessOriginal),
            disabledReason: 'The original image is unavailable',
            run: async () => {
                await copyImage(sourceUrl);
                notify('Image copied to clipboard');
            },
        },
        {
            label: 'Copy file path',
            icon: 'path',
            enabled: Boolean(imageId && hasLocalFile),
            disabledReason: localFileDisabledReason,
            run: async () => {
                if (!navigator.clipboard?.writeText) {
                    throw new Error('Copying text is not supported by this browser');
                }
                const data = await fetchJson(`/api/images/${imageId}/file-location`);
                await navigator.clipboard.writeText(data.path);
                notify('File path copied to clipboard');
            },
        },
    ];

    const menu = document.createElement('div');
    menu.className = 'image-context-menu';
    menu.setAttribute('role', 'menu');
    menu.setAttribute('aria-label', `Actions for ${fileName || 'image'}`);

    const title = document.createElement('div');
    title.className = 'image-context-menu__title';
    title.textContent = fileName || 'Image actions';
    title.title = fileName || '';
    menu.appendChild(title);

    const controller = new AbortController();
    const target = anchor;
    const runAction = action => {
        if (!action.enabled) return;
        closeImageContextMenu();
        try {
            const result = action.run();
            if (result && typeof result.catch === 'function') {
                result.catch(error => notify(error.message || 'Image action failed', true));
            }
        } catch (error) {
            notify(error.message || 'Image action failed', true);
        }
    };

    actions.forEach(action => {
        if (action.separator) {
            const separator = document.createElement('div');
            separator.className = 'image-context-menu__separator';
            separator.setAttribute('role', 'separator');
            menu.appendChild(separator);
        } else {
            menu.appendChild(actionButton(action, runAction));
        }
    });

    document.body.appendChild(menu);
    activeMenu = { controller, menu, target };
    positionMenu(menu, menuCoordinates(event, target));

    const enabledItems = () => [...menu.querySelectorAll('.image-context-menu__item:not(:disabled)')];
    const firstItem = enabledItems()[0];
    firstItem?.focus({ preventScroll: true });

    menu.addEventListener('keydown', keyEvent => {
        const items = enabledItems();
        const currentIndex = items.indexOf(document.activeElement);
        let nextIndex = null;
        if (keyEvent.key === 'ArrowDown') nextIndex = (currentIndex + 1) % items.length;
        if (keyEvent.key === 'ArrowUp') nextIndex = (currentIndex - 1 + items.length) % items.length;
        if (keyEvent.key === 'Home') nextIndex = 0;
        if (keyEvent.key === 'End') nextIndex = items.length - 1;
        if (nextIndex !== null && items.length) {
            keyEvent.preventDefault();
            keyEvent.stopPropagation();
            items[nextIndex].focus();
        } else if (keyEvent.key === 'Escape') {
            keyEvent.preventDefault();
            keyEvent.stopPropagation();
            closeImageContextMenu({ restoreFocus: true });
        } else if (keyEvent.key === 'Tab') {
            closeImageContextMenu();
        }
    }, { signal: controller.signal });

    document.addEventListener('pointerdown', pointerEvent => {
        if (!menu.contains(pointerEvent.target)) closeImageContextMenu();
    }, { capture: true, signal: controller.signal });
    window.addEventListener('resize', () => closeImageContextMenu(), { signal: controller.signal });
    window.addEventListener('scroll', () => closeImageContextMenu(), { capture: true, signal: controller.signal });
    window.addEventListener('blur', () => closeImageContextMenu(), { signal: controller.signal });
}
