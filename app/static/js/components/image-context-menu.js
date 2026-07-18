const MENU_MARGIN = 8;

const icons = {
    open: '<path d="M14 3h7v7"></path><path d="M10 14 21 3"></path><path d="M21 14v5a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5"></path>',
    folder: '<path d="M3 7a2 2 0 0 1 2-2h5l2 2h7a2 2 0 0 1 2 2v8a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2Z"></path><path d="M8 13h8M13 10l3 3-3 3"></path>',
    image: '<rect x="3" y="3" width="18" height="18" rx="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><path d="m21 15-5-5L5 21"></path>',
    path: '<rect x="8" y="8" width="11" height="11" rx="2"></rect><path d="M16 8V5a2 2 0 0 0-2-2H5a2 2 0 0 0-2 2v9a2 2 0 0 0 2 2h3"></path>',
    download: '<path d="M12 3v12"></path><path d="m7 10 5 5 5-5"></path><path d="M5 21h14"></path>',
    positive: '<path d="M5 4h14v13H8l-3 3Z"></path><path d="M12 8v5M9.5 10.5h5"></path>',
    negative: '<path d="M5 4h14v13H8l-3 3Z"></path><path d="M9.5 10.5h5"></path>',
    workflow: '<circle cx="6" cy="6" r="2"></circle><circle cx="18" cy="6" r="2"></circle><circle cx="12" cy="18" r="2"></circle><path d="m7.7 7.1 3.2 8.1M16.3 7.1l-3.2 8.1M8 6h8"></path>',
    favorite: '<path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.6l-1-1a5.5 5.5 0 0 0-7.8 7.8l1 1L12 21l7.8-7.6 1-1a5.5 5.5 0 0 0 0-7.8Z"></path>',
    album: '<rect x="3" y="5" width="18" height="15" rx="2"></rect><path d="M3 9h18M8 13h8M8 17h5"></path>',
    edit: '<path d="M12 20h9"></path><path d="M16.5 3.5a2.1 2.1 0 0 1 3 3L8 18l-4 1 1-4Z"></path>',
    cutout: '<path d="M4 8V5a1 1 0 0 1 1-1h3M16 4h3a1 1 0 0 1 1 1v3M20 16v3a1 1 0 0 1-1 1h-3M8 20H5a1 1 0 0 1-1-1v-3"></path><path d="M9 9h6v6H9Z"></path>',
    remove: '<path d="M3 6h18M8 6V4h8v2M19 6l-1 14H6L5 6M10 11v5M14 11v5"></path>',
    loading: '<path d="M20 12a8 8 0 1 1-2.3-5.7"></path>',
};

let activeMenu = null;
const pendingImageDetails = new Map();

async function fetchJson(url, options) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error) {
        throw new Error(data.error || `${response.status} ${response.statusText}`);
    }
    return data;
}

function loadImageDetail(imageId) {
    if (!pendingImageDetails.has(imageId)) {
        const request = fetchJson(`/api/images/${imageId}`);
        pendingImageDetails.set(imageId, request);
        request.then(
            () => pendingImageDetails.delete(imageId),
            () => pendingImageDetails.delete(imageId),
        );
    }
    return pendingImageDetails.get(imageId);
}

async function copyText(text, successMessage, notify) {
    if (!navigator.clipboard?.writeText) {
        throw new Error('Copying text is not supported by this browser');
    }
    await navigator.clipboard.writeText(text);
    notify(successMessage);
}

function downloadImage(sourceUrl, fileName, notify) {
    const link = document.createElement('a');
    link.href = sourceUrl;
    link.download = fileName || 'image';
    document.body.appendChild(link);
    link.click();
    link.remove();
    notify('Image download started');
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

function actionButton(action, onActivate) {
    const button = document.createElement('button');
    button.className = 'image-context-menu__item';
    if (action.tone === 'danger') button.classList.add('image-context-menu__item--danger');
    button.type = 'button';
    button.setAttribute('role', 'menuitem');
    button.disabled = action.enabled === false;
    if (button.disabled && action.disabledReason) button.title = action.disabledReason;

    const icon = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    icon.setAttribute('viewBox', '0 0 24 24');
    icon.setAttribute('aria-hidden', 'true');
    icon.innerHTML = icons[action.icon] || icons.image;
    if (action.icon === 'loading') icon.classList.add('image-context-menu__loading-icon');

    const label = document.createElement('span');
    label.textContent = action.label;
    button.append(icon, label);
    button.addEventListener('click', () => onActivate(action));
    return button;
}

function enabledItems(menu) {
    return [...menu.children]
        .map(child => child.matches('.image-context-menu__submenu-wrap')
            ? child.querySelector(':scope > .image-context-menu__item')
            : child)
        .filter(child => child?.matches?.('.image-context-menu__item:not(:disabled)'));
}

function positionSubmenu(submenu) {
    submenu.classList.remove('image-context-menu--opens-left');
    submenu.style.top = '-6px';
    let rect = submenu.getBoundingClientRect();
    if (rect.right > window.innerWidth - MENU_MARGIN) {
        submenu.classList.add('image-context-menu--opens-left');
        rect = submenu.getBoundingClientRect();
    }
    if (rect.bottom > window.innerHeight - MENU_MARGIN) {
        submenu.style.top = `${-6 - (rect.bottom - window.innerHeight + MENU_MARGIN)}px`;
        rect = submenu.getBoundingClientRect();
    }
    if (rect.top < MENU_MARGIN) {
        submenu.style.top = `${Number.parseFloat(submenu.style.top) + MENU_MARGIN - rect.top}px`;
    }
}

function actionEntry(action, runAction, submenuControls) {
    if (!action.children?.length) return actionButton(action, runAction);

    const wrapper = document.createElement('div');
    wrapper.className = 'image-context-menu__submenu-wrap';
    const submenu = document.createElement('div');
    submenu.className = 'image-context-menu image-context-menu--submenu';
    submenu.setAttribute('role', 'menu');
    submenu.setAttribute('aria-label', action.label);
    submenu.hidden = true;

    const parentButton = actionButton(action, () => {
        openSubmenu({ focusFirst: true });
    });
    parentButton.classList.add('image-context-menu__item--submenu');
    parentButton.setAttribute('aria-haspopup', 'menu');
    parentButton.setAttribute('aria-expanded', 'false');
    const chevron = document.createElement('span');
    chevron.className = 'image-context-menu__chevron';
    chevron.textContent = '›';
    chevron.setAttribute('aria-hidden', 'true');
    parentButton.appendChild(chevron);

    action.children.forEach(child => submenu.appendChild(actionButton(child, runAction)));

    const closeSubmenu = ({ restoreFocus = false } = {}) => {
        submenu.hidden = true;
        parentButton.setAttribute('aria-expanded', 'false');
        if (restoreFocus) parentButton.focus({ preventScroll: true });
    };
    const openSubmenu = ({ focusFirst = false } = {}) => {
        submenuControls.forEach(control => {
            if (control.close !== closeSubmenu) control.close();
        });
        submenu.hidden = false;
        parentButton.setAttribute('aria-expanded', 'true');
        positionSubmenu(submenu);
        if (focusFirst) enabledItems(submenu)[0]?.focus({ preventScroll: true });
    };
    submenuControls.push({ button: parentButton, submenu, open: openSubmenu, close: closeSubmenu });

    wrapper.addEventListener('pointerenter', () => {
        if (!parentButton.disabled) openSubmenu();
    });
    wrapper.addEventListener('pointerleave', () => {
        if (!submenu.contains(document.activeElement)) closeSubmenu();
    });
    parentButton.addEventListener('keydown', event => {
        if (event.key !== 'ArrowRight') return;
        event.preventDefault();
        event.stopPropagation();
        openSubmenu({ focusFirst: true });
    });
    submenu.addEventListener('keydown', event => {
        if (event.key !== 'ArrowLeft') return;
        event.preventDefault();
        event.stopPropagation();
        closeSubmenu({ restoreFocus: true });
    });

    wrapper.append(parentButton, submenu);
    return wrapper;
}

function appendSection(container, actions, runAction, submenuControls) {
    const visibleActions = actions.filter(action => action && action.visible !== false);
    if (!visibleActions.length) return;
    if (container.childElementCount) {
        const separator = document.createElement('div');
        separator.className = 'image-context-menu__separator';
        separator.setAttribute('role', 'separator');
        container.appendChild(separator);
    }
    visibleActions.forEach(action => {
        container.appendChild(actionEntry(action, runAction, submenuControls));
    });
}

function imageMetadataActions(detail, notify) {
    const promptParameters = detail?.prompt_parameters || {};
    const workflow = detail?.workflow_ui_json || detail?.workflow;
    return [
        {
            label: 'Copy positive prompt',
            icon: 'positive',
            visible: Boolean(promptParameters.positive_prompt),
            run: () => copyText(
                String(promptParameters.positive_prompt),
                'Positive prompt copied to clipboard',
                notify,
            ),
        },
        {
            label: 'Copy negative prompt',
            icon: 'negative',
            visible: Boolean(promptParameters.negative_prompt),
            run: () => copyText(
                String(promptParameters.negative_prompt),
                'Negative prompt copied to clipboard',
                notify,
            ),
        },
        {
            label: 'Copy workflow',
            icon: 'workflow',
            visible: Boolean(workflow),
            run: () => copyText(
                JSON.stringify(workflow, null, 2),
                'Workflow copied to clipboard',
                notify,
            ),
        },
    ];
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
    detail = null,
    extraSections = [],
    anchor = event.currentTarget || event.target,
    notify = () => {},
}) {
    event.preventDefault();
    event.stopPropagation();
    closeImageContextMenu();

    const localFileDisabledReason = 'This image has no available local file';
    const coreSections = [
        [
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
            {
                label: 'Download image',
                icon: 'download',
                enabled: Boolean(sourceUrl && canAccessOriginal),
                disabledReason: 'The original image is unavailable',
                run: () => downloadImage(sourceUrl, fileName, notify),
            },
        ],
        [
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
                    const data = await fetchJson(`/api/images/${imageId}/file-location`);
                    await copyText(data.path, 'File path copied to clipboard', notify);
                },
            },
        ],
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
    const submenuControls = [];
    const target = anchor;
    const runAction = action => {
        if (action.enabled === false) return;
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

    coreSections.forEach(section => appendSection(menu, section, runAction, submenuControls));

    const metadataAnchor = document.createComment('metadata-actions');
    menu.appendChild(metadataAnchor);
    let metadataNodes = [];
    const renderMetadata = metadataDetail => {
        metadataNodes.forEach(node => node.remove());
        metadataNodes = [];
        const actions = imageMetadataActions(metadataDetail, notify)
            .filter(action => action.visible !== false);
        if (!actions.length) return;
        const separator = document.createElement('div');
        separator.className = 'image-context-menu__separator';
        separator.setAttribute('role', 'separator');
        metadataNodes.push(separator, ...actions.map(action => (
            actionEntry(action, runAction, submenuControls)
        )));
        metadataNodes.forEach(node => menu.insertBefore(node, metadataAnchor));
    };

    if (detail) {
        renderMetadata(detail);
    } else if (imageId) {
        const loadingAction = actionEntry({
            label: 'Loading metadata…',
            icon: 'loading',
            enabled: false,
        }, runAction, submenuControls);
        const loadingSeparator = document.createElement('div');
        loadingSeparator.className = 'image-context-menu__separator';
        loadingSeparator.setAttribute('role', 'separator');
        metadataNodes = [loadingSeparator, loadingAction];
        metadataNodes.forEach(node => menu.insertBefore(node, metadataAnchor));
    }

    extraSections.forEach(section => appendSection(menu, section, runAction, submenuControls));

    document.body.appendChild(menu);
    activeMenu = { controller, menu, target };
    positionMenu(menu, menuCoordinates(event, target));

    const firstItem = enabledItems(menu)[0];
    firstItem?.focus({ preventScroll: true });

    if (!detail && imageId) {
        loadImageDetail(imageId).then(loadedDetail => {
            if (activeMenu?.menu !== menu) return;
            renderMetadata(loadedDetail);
            positionMenu(menu, menuCoordinates(event, target));
        }).catch(() => {
            if (activeMenu?.menu !== menu) return;
            renderMetadata(null);
            positionMenu(menu, menuCoordinates(event, target));
        });
    }

    menu.addEventListener('keydown', keyEvent => {
        const currentMenu = keyEvent.target.closest('[role="menu"]') || menu;
        const items = enabledItems(currentMenu);
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
            const submenuControl = submenuControls.find(control => control.submenu === currentMenu);
            if (submenuControl) submenuControl.close({ restoreFocus: true });
            else closeImageContextMenu({ restoreFocus: true });
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
