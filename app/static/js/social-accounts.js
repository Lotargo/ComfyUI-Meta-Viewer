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
        description: 'Publish to a community or profile wall via VK ID authorization.',
        hintNotConfigured: 'VK application (client_id) is not configured yet.',
        hintConfigured: 'Opens VK authorization in your browser.',
    },
    instagram: {
        title: 'Instagram',
        icon: '◈',
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
    iconWrap.textContent = meta.icon;
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
