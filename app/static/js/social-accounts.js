const SOCIAL_GRID_ID = 'social-grid';
const PROVIDERS = ['telegram', 'vk', 'instagram'];

const PROVIDER_META = {
    telegram: {
        title: 'Telegram',
        icon: '✈',
        description: 'Publish to your Telegram channel or chats as your personal account.',
        hintNotConfigured: 'Telegram application credentials (api_id/api_hash) are not configured yet.',
        hintConfigured: 'Authorize in your browser via QR code or phone number.',
    },
    vk: {
        title: 'ВКонтакте',
        icon: 'V',
        svgPath: 'm9.489.004.729-.003h3.564l.73.003.914.01.433.007.418.011.403.014.388.016.374.021.36.025.345.03.333.033c1.74.196 2.933.616 3.833 1.516.9.9 1.32 2.092 1.516 3.833l.034.333.029.346.025.36.02.373.025.588.012.41.013.644.009.915.004.98-.001 3.313-.003.73-.01.914-.007.433-.011.418-.014.403-.016.388-.021.374-.025.36-.03.345-.033.333c-.196 1.74-.616 2.933-1.516 3.833-.9.9-2.092 1.32-3.833 1.516l-.333.034-.346.029-.36.025-.373.02-.588.025-.41.012-.644.013-.915.009-.98.004-3.313-.001-.73-.003-.914-.01-.433-.007-.418-.011-.403-.014-.388-.016-.374-.021-.36-.025-.345-.03-.333-.033c-1.74-.196-2.933-.616-3.833-1.516-.9-.9-1.32-2.092-1.516-3.833l-.034-.333-.029-.346-.025-.36-.02-.373-.025-.588-.012-.41-.013-.644-.009-.915-.004-.98.001-3.313.003-.73.01-.914.007-.433.011-.418.014-.403.016-.388.021-.374.025-.36.03-.345.033-.333c.196-1.74.616-2.933 1.516-3.833.9-.9 2.092-1.32 3.833-1.516l.333-.034.346-.029.36-.025.373-.02.588-.025.41-.012.644-.013.915-.009ZM6.79 7.3H4.05c.13 6.24 3.25 9.99 8.72 9.99h.31v-3.57c2.01.2 3.53 1.67 4.14 3.57h2.84c-.78-2.84-2.83-4.41-4.11-5.01 1.28-.74 3.08-2.54 3.51-4.98h-2.58c-.56 1.98-2.22 3.78-3.8 3.95V7.3H10.5v6.92c-1.6-.4-3.62-2.34-3.71-6.92Z',
        description: 'Publish to a community or profile wall via VK ID authorization.',
        hintNotConfigured: 'VK application (client_id) is not configured yet.',
        hintConfigured: 'Opens VK authorization in your browser.',
    },
    instagram: {
        title: 'Instagram',
        icon: '◈',
        svgPath: 'M7.0301.084c-1.2768.0602-2.1487.264-2.911.5634-.7888.3075-1.4575.72-2.1228 1.3877-.6652.6677-1.075 1.3368-1.3802 2.127-.2954.7638-.4956 1.6365-.552 2.914-.0564 1.2775-.0689 1.6882-.0626 4.947.0062 3.2586.0206 3.6671.0825 4.9473.061 1.2765.264 2.1482.5635 2.9107.308.7889.72 1.4573 1.388 2.1228.6679.6655 1.3365 1.0743 2.1285 1.38.7632.295 1.6361.4961 2.9134.552 1.2773.056 1.6884.069 4.9462.0627 3.2578-.0062 3.668-.0207 4.9478-.0814 1.28-.0607 2.147-.2652 2.9098-.5633.7889-.3086 1.4578-.72 2.1228-1.3881.665-.6682 1.0745-1.3378 1.3795-2.1284.2957-.7632.4966-1.636.552-2.9124.056-1.2809.0692-1.6898.063-4.948-.0063-3.2583-.021-3.6668-.0817-4.9465-.0607-1.2797-.264-2.1487-.5633-2.9117-.3084-.7889-.72-1.4568-1.3876-2.1228C21.2982 1.33 20.628.9208 19.8378.6165 19.074.321 18.2017.1197 16.9244.0645 15.6471.0093 15.236-.005 11.977.0014 8.718.0076 8.31.0215 7.0301.0839m.1402 21.6932c-1.17-.0509-1.8053-.2453-2.2287-.408-.5606-.216-.96-.4771-1.3819-.895-.422-.4178-.6811-.8186-.9-1.378-.1644-.4234-.3624-1.058-.4171-2.228-.0595-1.2645-.072-1.6442-.079-4.848-.007-3.2037.0053-3.583.0607-4.848.05-1.169.2456-1.805.408-2.2282.216-.5613.4762-.96.895-1.3816.4188-.4217.8184-.6814 1.3783-.9003.423-.1651 1.0575-.3614 2.227-.4171 1.2655-.06 1.6447-.072 4.848-.079 3.2033-.007 3.5835.005 4.8495.0608 1.169.0508 1.8053.2445 2.228.408.5608.216.96.4754 1.3816.895.4217.4194.6816.8176.9005 1.3787.1653.4217.3617 1.056.4169 2.2263.0602 1.2655.0739 1.645.0796 4.848.0058 3.203-.0055 3.5834-.061 4.848-.051 1.17-.245 1.8055-.408 2.2294-.216.5604-.4763.96-.8954 1.3814-.419.4215-.8181.6811-1.3783.9-.4224.1649-1.0577.3617-2.2262.4174-1.2656.0595-1.6448.072-4.8493.079-3.2045.007-3.5825-.006-4.848-.0608M16.953 5.5864A1.44 1.44 0 1 0 18.39 4.144a1.44 1.44 0 0 0-1.437 1.4424M5.8385 12.012c.0067 3.4032 2.7706 6.1557 6.173 6.1493 3.4026-.0065 6.157-2.7701 6.1506-6.1733-.0065-3.4032-2.771-6.1565-6.174-6.1498-3.403.0067-6.156 2.771-6.1496 6.1738M8 12.0077a4 4 0 1 1 4.008 3.9921A3.9996 3.9996 0 0 1 8 12.0077',
        description: 'Publishing to Instagram is planned but not available yet.',
        hintNotConfigured: 'Not implemented yet.',
    },
};

const TG_POLL_MS = 3000;
const VK_POLL_MS = 2000;
const VK_POLL_TIMEOUT_MS = 5 * 60 * 1000;
const OPTIONAL_SHOW_KEY = 'social.showOptionalAdapters';

let tgPollTimer = null;
let vkPollTimer = null;
let vkPollStartedAt = 0;

const elements = {};
let socialStatus = null;

window.cmvSocialStatus = () => socialStatus;

function $(id) {
    return document.getElementById(id);
}

function el(tag, className, text) {
    const node = document.createElement(tag);
    if (className) node.className = className;
    if (text !== undefined) node.textContent = text;
    return node;
}

async function requestJson(url, options = {}) {
    const response = await fetch(url, options);
    const data = await response.json().catch(() => ({}));
    if (!response.ok || data.error) {
        const error = new Error(data.error || `${response.status} ${response.statusText}`);
        error.code = data.code;
        error.technicalError = data.technical_error;
        throw error;
    }
    return data;
}

function showToast(message, isError = false) {
    const toast = $('toast');
    if (!toast) return;
    toast.textContent = message;
    toast.classList.toggle('toast-error', isError);
    toast.classList.add('show');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => toast.classList.remove('show'), 3200);
}

async function loadSocialStatus() {
    try {
        socialStatus = await requestJson('/api/social/status');
    } catch (error) {
        socialStatus = null;
    }
    return socialStatus;
}

function providerConnected(name) {
    if (!socialStatus) return false;
    const data = socialStatus.providers?.[name];
    if (!data) return false;
    if (data.connected) return true;
    const live = data.publisher;
    return !!(live && live.connected);
}

function providerConfigured(name) {
    if (!socialStatus) return true;
    const live = socialStatus.providers?.[name]?.publisher;
    if (!live) return true;
    return live.configured !== false;
}

function providerEnabled(name) {
    if (!socialStatus) return true;
    const data = socialStatus.providers?.[name];
    if (!data) return true;
    return data.enabled !== false;
}

function optionalAdaptersShown() {
    try {
        return localStorage.getItem(OPTIONAL_SHOW_KEY) === '1';
    } catch (_) {
        return false;
    }
}

function providerLabel(name) {
    if (!socialStatus) return '';
    const live = socialStatus.providers?.[name]?.publisher;
    if (live && live.connected) {
        if (live.username) return `@${live.username}`;
        if (live.first_name) return live.first_name;
        if (live.phone) return live.phone;
    }
    return '';
}

function renderStatusLine(name) {
    const meta = PROVIDER_META[name];
    if (providerConnected(name)) {
        const label = providerLabel(name);
        const line = el('p', 'social-status-line', label ? `Signed in as ${label}` : 'Connected');
        line.classList.add('connected');
        return line;
    }
    if (!providerConfigured(name)) {
        return el('p', 'social-status-line muted', meta.hintNotConfigured);
    }
    return el('p', 'social-status-line', meta.hintConfigured);
}

function buildActions(name) {
    const actions = el('div', 'social-card-actions');
    const connected = providerConnected(name);

    if (name === 'telegram') {
        const authorize = el('button', 'btn btn-primary', 'Authorize');
        authorize.type = 'button';
        authorize.disabled = !providerConfigured(name) || !providerEnabled(name);
        authorize.addEventListener('click', () => openTelegramDialog());
        actions.append(authorize);
        if (connected) {
            const disconnect = el('button', 'btn btn-secondary', 'Disconnect');
            disconnect.type = 'button';
            disconnect.addEventListener('click', () => disconnectTelegram());
            actions.append(disconnect);
        }
    } else if (name === 'vk') {
        const authorize = el('button', 'btn btn-primary', 'Authorize');
        authorize.type = 'button';
        authorize.disabled = !providerConfigured(name);
        authorize.addEventListener('click', () => startVkAuth());
        actions.append(authorize);
        if (connected) {
            const disconnect = el('button', 'btn btn-secondary', 'Disconnect');
            disconnect.type = 'button';
            disconnect.addEventListener('click', () => disconnectVk());
            actions.append(disconnect);
        }
    } else {
        const soon = el('span', 'social-soon-tag', 'Planned');
        actions.append(soon);
    }
    return actions;
}

function renderCard(name) {
    const meta = PROVIDER_META[name];
    const card = el('div', 'social-card');
    card.dataset.provider = name;

    const iconWrap = el('div', 'social-card-icon');
    if (meta.svgPath) {
        iconWrap.innerHTML = `<svg viewBox="0 0 24 24" role="img" aria-label="${meta.title}" xmlns="http://www.w3.org/2000/svg"><path d="${meta.svgPath}"/></svg>`;
    } else {
        iconWrap.textContent = meta.icon;
    }
    card.append(iconWrap);

    const body = el('div', 'social-card-body');
    const title = el('h3', '', meta.title);
    body.append(title);
    if (name === 'telegram') {
        body.append(el('span', 'social-optional-tag', 'Optional'));
    }
    body.append(el('p', 'social-card-description', meta.description));
    body.append(renderStatusLine(name));
    body.append(buildActions(name));
    card.append(body);
    return card;
}

function visibleProviders() {
    const revealOptional = optionalAdaptersShown();
    return PROVIDERS.filter((name) => providerEnabled(name) || (name === 'telegram' && revealOptional));
}

async function renderSocialGrid() {
    const grid = $(SOCIAL_GRID_ID);
    if (!grid) return;
    await loadSocialStatus();
    grid.replaceChildren(...visibleProviders().map(renderCard));
    if (typeof window.updateRailCounts === 'function') window.updateRailCounts();
}

function stopTelegramPolling() {
    if (tgPollTimer !== null) {
        window.clearInterval(tgPollTimer);
        tgPollTimer = null;
    }
}

function stopVkPolling() {
    if (vkPollTimer !== null) {
        window.clearInterval(vkPollTimer);
        vkPollTimer = null;
    }
}

// ----------------------------------------------------------------------
// Telegram dialog
// ----------------------------------------------------------------------

function resetTelegramDialog() {
    $('social-tg-phone').value = '';
    $('social-tg-code').value = '';
    $('social-tg-password').value = '';
    $('social-tg-error').hidden = true;
    $('social-tg-busy').hidden = true;
    $('social-tg-qr').hidden = true;
    $('social-tg-send-code').hidden = true;
    $('social-tg-submit').hidden = true;
    $('social-tg-code-step').hidden = true;
    $('social-tg-password-step').hidden = true;
    $('social-tg-phone-step').hidden = false;
}

function setTelegramError(message) {
    const error = $('social-tg-error');
    error.textContent = message || '';
    error.hidden = !message;
    $('social-tg-busy').hidden = true;
}

function setTelegramBusy(busy) {
    $('social-tg-busy').hidden = !busy;
}

function applyTelegramState(state, extra = {}) {
    if (state === 'connected') {
        closeTelegramDialog(true);
        return;
    }
    if (state === 'code_requested') {
        $('social-tg-qr').hidden = true;
        $('social-tg-phone-step').hidden = true;
        $('social-tg-send-code').hidden = true;
        $('social-tg-code-step').hidden = false;
        $('social-tg-submit').hidden = false;
        $('social-tg-submit').textContent = 'Confirm';
        $('social-tg-code').focus();
    } else if (state === 'password_required') {
        $('social-tg-qr').hidden = true;
        $('social-tg-phone-step').hidden = true;
        $('social-tg-code-step').hidden = true;
        $('social-tg-send-code').hidden = true;
        $('social-tg-password-step').hidden = false;
        $('social-tg-submit').hidden = false;
        $('social-tg-submit').textContent = 'Sign in';
        $('social-tg-password').focus();
    } else if (state === 'qr_waiting') {
        $('social-tg-code-step').hidden = true;
        $('social-tg-password-step').hidden = true;
        $('social-tg-phone-step').hidden = false;
        $('social-tg-send-code').hidden = false;
        $('social-tg-submit').hidden = true;
        const qr = $('social-tg-qr');
        qr.src = `/api/social/telegram/auth/qr.png?t=${Date.now()}`;
        qr.hidden = false;
        setTelegramBusy(true);
    } else if (state === 'idle') {
        setTelegramBusy(false);
    } else if (state === 'error') {
        setTelegramBusy(false);
        setTelegramError((extra && extra.error) || 'Authorization failed.');
    }
}

async function pollTelegramState() {
    try {
        const state = await requestJson('/api/social/telegram/auth/state');
        if (state.state === 'qr_waiting') {
            const qr = $('social-tg-qr');
            if (qr && !qr.hidden) {
                qr.src = `/api/social/telegram/auth/qr.png?t=${Date.now()}`;
            }
        }
        applyTelegramState(state.state, state);
    } catch (error) {
        if (tgPollTimer !== null) {
            setTelegramError(error.message);
        }
    }
}

function openTelegramDialog() {
    resetTelegramDialog();
    const dialog = $('social-telegram-dialog');
    dialog.showModal();
    startTelegramAuth();
}

async function startTelegramAuth(phone) {
    setTelegramBusy(true);
    setTelegramError('');
    stopTelegramPolling();
    try {
        const body = phone ? { phone } : {};
        const state = await requestJson('/api/social/telegram/auth/start', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(body),
        });
        applyTelegramState(state.state, state);
        if (state.state === 'qr_waiting' || state.state === 'code_requested' || state.state === 'password_required') {
            tgPollTimer = window.setInterval(pollTelegramState, TG_POLL_MS);
        }
    } catch (error) {
        setTelegramError(error.message);
    }
}

async function submitTelegramCodeOrPassword() {
    setTelegramBusy(true);
    setTelegramError('');
    const codeStep = !$('social-tg-code-step').hidden;
    const passwordStep = !$('social-tg-password-step').hidden;
    try {
        let state;
        if (passwordStep) {
            const password = $('social-tg-password').value;
            state = await requestJson('/api/social/telegram/auth/password', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ password }),
            });
        } else if (codeStep) {
            const code = $('social-tg-code').value;
            state = await requestJson('/api/social/telegram/auth/code', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ code }),
            });
        }
        applyTelegramState(state.state, state);
    } catch (error) {
        setTelegramError(error.message);
    }
}

function closeTelegramDialog(refresh = false) {
    stopTelegramPolling();
    const dialog = $('social-telegram-dialog');
    if (dialog.open) dialog.close();
    if (refresh) {
        showToast('Telegram account connected.');
        renderSocialGrid();
    }
}

async function disconnectTelegram() {
    try {
        await requestJson('/api/social/telegram/auth/disconnect', { method: 'POST' });
        showToast('Telegram account disconnected.');
        await renderSocialGrid();
    } catch (error) {
        showToast(error.message, true);
    }
}

// ----------------------------------------------------------------------
// VK auth
// ----------------------------------------------------------------------

async function startVkAuth() {
    stopVkPolling();
    try {
        const result = await requestJson('/api/social/vk/auth/start', { method: 'POST' });
        if (!result.authorize_url) {
            showToast('VK authorization is not available.', true);
            return;
        }
        window.open(result.authorize_url, 'vkauth', 'width=680,height=720');
        vkPollStartedAt = Date.now();
        showToast('Complete the authorization in the opened browser window.');
        vkPollTimer = window.setInterval(pollVkStatus, VK_POLL_MS);
        pollVkStatus();
    } catch (error) {
        showToast(error.message, true);
    }
}

async function pollVkStatus() {
    try {
        const result = await requestJson('/api/social/vk/auth/state');
        if (result.connected) {
            stopVkPolling();
            showToast('VK account connected.');
            await renderSocialGrid();
            return;
        }
        if (Date.now() - vkPollStartedAt > VK_POLL_TIMEOUT_MS) {
            stopVkPolling();
            showToast('VK authorization timed out. Please try again.', true);
        }
    } catch (error) {
        if (Date.now() - vkPollStartedAt > VK_POLL_TIMEOUT_MS) {
            stopVkPolling();
        }
    }
}

async function disconnectVk() {
    try {
        await requestJson('/api/social/vk/auth/disconnect', { method: 'POST' });
        showToast('VK account disconnected.');
        await renderSocialGrid();
    } catch (error) {
        showToast(error.message, true);
    }
}

// ----------------------------------------------------------------------
// Wire-up
// ----------------------------------------------------------------------

function bindEvents() {
    const toggle = $('social-show-optional');
    if (toggle) {
        toggle.checked = optionalAdaptersShown();
        toggle.addEventListener('change', () => {
            try {
                localStorage.setItem(OPTIONAL_SHOW_KEY, toggle.checked ? '1' : '0');
            } catch (_) {
                // ignore storage failures
            }
            renderSocialGrid();
        });
    }
    const dialog = $('social-telegram-dialog');
    if (dialog) {
        $('close-social-telegram').addEventListener('click', () => closeTelegramDialog(false));
        $('social-tg-cancel').addEventListener('click', async () => {
            stopTelegramPolling();
            try {
                await requestJson('/api/social/telegram/auth/cancel', { method: 'POST' });
            } catch (_) {
                // ignore cancel errors
            }
            dialog.close();
        });
        $('social-tg-send-code').addEventListener('click', () => {
            const phone = $('social-tg-phone').value.trim();
            if (!phone) {
                setTelegramError('Enter your phone number first.');
                return;
            }
            startTelegramAuth(phone);
        });
        dialog.addEventListener('close', stopTelegramPolling);
        $('social-telegram-form').addEventListener('submit', (event) => {
            event.preventDefault();
            submitTelegramCodeOrPassword();
        });
    }
}

async function init() {
    if (!$('social-grid')) return;
    bindEvents();
    await renderSocialGrid();
}

document.addEventListener('DOMContentLoaded', () => {
    init().catch((error) => showToast(error.message, true));
});
