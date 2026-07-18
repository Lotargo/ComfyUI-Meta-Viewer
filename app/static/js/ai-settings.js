const elements = {
    secretStatus: document.getElementById('secret-store-status'),
    feedback: document.getElementById('page-feedback'),
    profilesGrid: document.getElementById('profiles-grid'),
    profilesEmpty: document.getElementById('profiles-empty'),
    cliGrid: document.getElementById('cli-grid'),
    defaultText: document.getElementById('default-text-profile'),
    defaultMultimodal: document.getElementById('default-multimodal-profile'),
    dialog: document.getElementById('profile-dialog'),
    form: document.getElementById('profile-form'),
    formError: document.getElementById('profile-form-error'),
    id: document.getElementById('profile-id'),
    kind: document.getElementById('profile-kind'),
    cliType: document.getElementById('profile-cli-type'),
    executable: document.getElementById('profile-executable'),
    name: document.getElementById('profile-name'),
    baseUrl: document.getElementById('profile-base-url'),
    keySource: document.getElementById('profile-key-source'),
    apiKey: document.getElementById('profile-api-key'),
    apiKeyEnv: document.getElementById('profile-api-key-env'),
    model: document.getElementById('profile-model'),
    modelOptions: document.getElementById('profile-model-options'),
    timeout: document.getElementById('profile-timeout'),
    multimodal: document.getElementById('profile-multimodal'),
    extraBody: document.getElementById('profile-extra-body'),
    openaiFields: document.getElementById('openai-fields'),
    apiKeyField: document.getElementById('api-key-field'),
    apiKeyHelp: document.getElementById('api-key-help'),
    apiKeyEnvField: document.getElementById('api-key-env-field'),
    extraBodyField: document.getElementById('extra-body-field'),
    dialogTitle: document.getElementById('profile-dialog-title'),
    dialogKicker: document.getElementById('profile-dialog-kicker'),
    saveProfile: document.getElementById('save-profile'),
};

let profiles = [];
let defaults = { text_profile_id: null, multimodal_profile_id: null };
let secretStore = { available: false };
let integrations = [];
const activeTests = new Map();

function createElement(tag, className, text) {
    const element = document.createElement(tag);
    if (className) element.className = className;
    if (text !== undefined) element.textContent = text;
    return element;
}

async function requestJson(url, options) {
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

function setFeedback(message, type = '') {
    elements.feedback.hidden = !message;
    elements.feedback.textContent = message || '';
    elements.feedback.className = `page-feedback${type ? ` ${type}` : ''}`;
}

function renderSecretStore() {
    elements.secretStatus.classList.toggle('available', secretStore.available);
    elements.secretStatus.classList.toggle('unavailable', !secretStore.available);
    const title = elements.secretStatus.querySelector('strong');
    const detail = elements.secretStatus.querySelector('div span');
    title.textContent = secretStore.available
        ? 'System credential storage available'
        : 'System credential storage unavailable';
    detail.textContent = secretStore.message || 'Use an environment variable for API credentials.';
    const systemOption = elements.keySource.querySelector('option[value="system"]');
    systemOption.disabled = !secretStore.available;
}

function appendBadge(container, text, className = '') {
    container.append(createElement('span', `profile-badge${className ? ` ${className}` : ''}`, text));
}

function actionButton(label, action, className = 'btn btn-secondary') {
    const button = createElement('button', className, label);
    button.type = 'button';
    button.addEventListener('click', action);
    return button;
}

function profileKindLabel(profile) {
    if (profile.kind === 'openai_compatible') return 'OpenAI-compatible';
    return integrations.find(item => item.type === profile.cli_type)?.label
        || profile.cli_type
        || 'Local CLI';
}

function renderProfiles() {
    elements.profilesGrid.replaceChildren();
    elements.profilesEmpty.hidden = profiles.length > 0;
    profiles.forEach(profile => {
        const card = createElement('article', 'profile-card');
        card.dataset.profileId = profile.id;
        const top = createElement('div', 'card-topline');
        const heading = createElement('div');
        heading.append(createElement('h3', '', profile.name));
        heading.append(createElement('p', 'model-id', profile.model));
        top.append(heading);
        top.append(createElement('span', 'profile-badge', profileKindLabel(profile)));
        card.append(top);

        const badges = createElement('div', 'badge-row');
        appendBadge(badges, `${profile.timeout_seconds}s timeout`);
        if (profile.multimodal) appendBadge(badges, 'Multimodal', 'vision');
        if (!profile.has_credentials) appendBadge(badges, 'Credentials unavailable', 'missing');
        if (defaults.text_profile_id === profile.id) appendBadge(badges, 'Default text');
        if (defaults.multimodal_profile_id === profile.id) appendBadge(badges, 'Default vision');
        card.append(badges);

        if (profile.credential_error) {
            card.append(createElement('p', 'card-test-result error', profile.credential_error));
        }
        const result = createElement('p', 'card-test-result');
        result.hidden = true;
        card.append(result);

        const actions = createElement('div', 'card-actions');
        const testText = actionButton('Test text', () => runProfileTest(profile, false, testText, result));
        actions.append(testText);
        if (profile.multimodal) {
            const testVision = actionButton('Test image', () => runProfileTest(profile, true, testVision, result));
            actions.append(testVision);
        }
        actions.append(actionButton('Edit', () => openProfileDialog(profile)));
        actions.append(actionButton('Delete', () => deleteProfile(profile), 'btn btn-danger'));
        card.append(actions);
        elements.profilesGrid.append(card);
    });
    renderDefaultSelectors();
}

function renderDefaultSelectors() {
    const fill = (select, predicate, selected) => {
        select.replaceChildren(new Option('Not selected', ''));
        profiles.filter(predicate).forEach(profile => {
            select.append(new Option(`${profile.name} — ${profile.model}`, profile.id));
        });
        select.value = selected || '';
    };
    fill(elements.defaultText, () => true, defaults.text_profile_id);
    fill(elements.defaultMultimodal, profile => profile.multimodal, defaults.multimodal_profile_id);
}

async function saveDefaults() {
    try {
        const data = await requestJson('/api/ai/defaults', {
            method: 'PATCH',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text_profile_id: elements.defaultText.value || null,
                multimodal_profile_id: elements.defaultMultimodal.value || null,
            }),
        });
        defaults = data.defaults;
        renderProfiles();
        setFeedback('Default AI profiles updated.', 'success');
    } catch (error) {
        renderDefaultSelectors();
        setFeedback(error.message, 'error');
    }
}

async function runProfileTest(profile, multimodal, button, result) {
    const active = activeTests.get(profile.id);
    if (active) {
        active.abort();
        return;
    }
    const controller = new AbortController();
    activeTests.set(profile.id, controller);
    const originalLabel = button.textContent;
    button.textContent = 'Cancel test';
    result.hidden = false;
    result.className = 'card-test-result';
    result.textContent = multimodal ? 'Testing image input…' : 'Testing text input…';
    try {
        const data = await requestJson(`/api/ai/profiles/${profile.id}/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ multimodal }),
            signal: controller.signal,
        });
        result.className = 'card-test-result success';
        result.textContent = `Connected in ${data.latency_ms} ms · ${data.response_preview}`;
    } catch (error) {
        result.className = 'card-test-result error';
        result.textContent = error.name === 'AbortError' ? 'Test cancelled.' : error.message;
        if (error.technicalError) result.title = error.technicalError;
    } finally {
        activeTests.delete(profile.id);
        button.textContent = originalLabel;
    }
}

async function deleteProfile(profile) {
    if (!window.confirm(`Delete the profile “${profile.name}” and its stored API key?`)) return;
    try {
        await requestJson(`/api/ai/profiles/${profile.id}`, { method: 'DELETE' });
        await loadProfiles();
        setFeedback(`Deleted “${profile.name}”.`, 'success');
    } catch (error) {
        setFeedback(error.message, 'error');
    }
}

function authenticationLabel(authentication) {
    const labels = {
        available: 'Authorization available',
        missing: 'Authorization missing',
        error: 'Authorization error',
        unknown: 'Authorization not verified',
        unavailable: 'Not installed',
    };
    return labels[authentication?.status] || 'Status unknown';
}

function renderIntegrations() {
    elements.cliGrid.replaceChildren();
    integrations.forEach(integration => {
        const card = createElement('article', 'cli-card');
        const top = createElement('div', 'cli-topline');
        const heading = createElement('div');
        heading.append(createElement('h3', '', integration.label));
        heading.append(createElement(
            'p',
            'cli-path',
            integration.executable || 'Executable not found in PATH',
        ));
        top.append(heading);
        const statusClass = integration.installed
            ? (integration.authentication?.status || 'unknown')
            : 'missing';
        top.append(createElement(
            'span',
            `cli-status ${statusClass}`,
            integration.installed ? (integration.version || 'Installed') : 'Not installed',
        ));
        card.append(top);
        const message = createElement(
            'p',
            'cli-message',
            integration.authentication?.message || authenticationLabel(integration.authentication),
        );
        card.append(message);

        const badges = createElement('div', 'badge-row');
        appendBadge(badges, authenticationLabel(integration.authentication), statusClass === 'available' ? 'vision' : '');
        if (integration.multimodal) appendBadge(badges, 'Image attachment', 'vision');
        if (integration.experimental) appendBadge(badges, 'Experimental adapter');
        card.append(badges);

        if (integration.installed) {
            const actions = createElement('div', 'card-actions');
            actions.append(actionButton('Create profile', () => prepareCliProfile(integration, message)));
            card.append(actions);
        }
        elements.cliGrid.append(card);
    });
}

async function prepareCliProfile(integration, message) {
    let models = [];
    if (integration.model_discovery) {
        message.textContent = 'Loading models from the CLI…';
        try {
            const data = await requestJson(`/api/ai/cli-integrations/${integration.type}/models`);
            models = data.models || [];
            message.textContent = models.length
                ? `Loaded ${models.length} model IDs. Choose one in the profile form.`
                : (data.message || 'No models were reported. Enter an ID manually.');
        } catch (error) {
            message.textContent = `Model discovery failed: ${error.message}`;
        }
    }
    openProfileDialog(null, integration, models);
}

function updateKeyFields() {
    const source = elements.keySource.value;
    elements.apiKeyField.hidden = source !== 'system';
    elements.apiKeyEnvField.hidden = source !== 'environment';
}

function resetProfileForm() {
    elements.form.reset();
    elements.id.value = '';
    elements.kind.value = 'openai_compatible';
    elements.cliType.value = '';
    elements.executable.value = '';
    elements.timeout.value = '60';
    elements.extraBody.value = '';
    elements.modelOptions.replaceChildren();
    elements.formError.hidden = true;
    elements.formError.textContent = '';
}

function openProfileDialog(profile = null, integration = null, models = []) {
    resetProfileForm();
    const isCli = Boolean(integration || profile?.kind === 'cli');
    const cliType = integration?.type || profile?.cli_type || '';
    elements.kind.value = isCli ? 'cli' : 'openai_compatible';
    elements.cliType.value = cliType;
    elements.executable.value = integration?.executable || profile?.executable || '';
    elements.openaiFields.hidden = isCli;
    elements.extraBodyField.hidden = isCli;
    elements.dialogKicker.textContent = isCli
        ? (integration?.label || profileKindLabel(profile))
        : 'OpenAI-compatible';
    elements.dialogTitle.textContent = profile ? 'Edit provider profile' : 'Add provider profile';
    elements.saveProfile.textContent = profile ? 'Save changes' : 'Save profile';
    const detectedCli = integration || integrations.find(item => item.type === cliType);
    elements.multimodal.disabled = isCli && !(detectedCli?.multimodal ?? profile?.multimodal);

    if (profile) {
        elements.id.value = profile.id;
        elements.name.value = profile.name;
        elements.model.value = profile.model;
        elements.timeout.value = String(profile.timeout_seconds);
        elements.multimodal.checked = profile.multimodal;
        if (!isCli) {
            elements.baseUrl.value = profile.base_url;
            elements.keySource.value = profile.api_key_source;
            elements.apiKeyEnv.value = profile.api_key_env || '';
            elements.extraBody.value = Object.keys(profile.extra_body || {}).length
                ? JSON.stringify(profile.extra_body, null, 2)
                : '';
            elements.apiKey.placeholder = 'Leave blank to keep the stored key';
            elements.apiKeyHelp.textContent = 'Leave blank to preserve the current key.';
        }
    } else if (!isCli) {
        elements.keySource.value = secretStore.available ? 'system' : 'environment';
        elements.apiKey.placeholder = 'Stored securely after save';
        elements.apiKeyHelp.textContent = 'Required for a new system-stored profile.';
    } else {
        elements.name.value = integration.label;
        elements.multimodal.checked = integration.multimodal;
    }
    models.slice(0, 2000).forEach(model => elements.modelOptions.append(new Option(model, model)));
    updateKeyFields();
    elements.dialog.showModal();
    elements.name.focus();
}

function profilePayload() {
    const payload = {
        kind: elements.kind.value,
        name: elements.name.value.trim(),
        model: elements.model.value.trim(),
        timeout_seconds: Number(elements.timeout.value),
        multimodal: elements.multimodal.checked,
    };
    if (payload.kind === 'cli') {
        payload.cli_type = elements.cliType.value;
        payload.executable = elements.executable.value || null;
        return payload;
    }
    payload.base_url = elements.baseUrl.value.trim();
    payload.api_key_source = elements.keySource.value;
    payload.api_key = elements.apiKey.value.trim();
    payload.api_key_env = elements.apiKeyEnv.value.trim() || null;
    const extra = elements.extraBody.value.trim();
    payload.extra_body = extra ? JSON.parse(extra) : {};
    return payload;
}

async function submitProfile(event) {
    event.preventDefault();
    elements.formError.hidden = true;
    elements.saveProfile.disabled = true;
    try {
        const payload = profilePayload();
        const profileId = elements.id.value;
        const url = profileId ? `/api/ai/profiles/${profileId}` : '/api/ai/profiles';
        await requestJson(url, {
            method: profileId ? 'PATCH' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });
        elements.dialog.close();
        await loadProfiles();
        setFeedback(profileId ? 'Provider profile updated.' : 'Provider profile created.', 'success');
    } catch (error) {
        elements.formError.textContent = error instanceof SyntaxError
            ? 'Additional request parameters contain invalid JSON.'
            : error.message;
        elements.formError.hidden = false;
    } finally {
        elements.saveProfile.disabled = false;
    }
}

async function loadProfiles() {
    const data = await requestJson('/api/ai/profiles');
    profiles = data.profiles || [];
    defaults = data.defaults || defaults;
    secretStore = data.secret_store || secretStore;
    renderSecretStore();
    renderProfiles();
}

async function loadIntegrations() {
    elements.cliGrid.replaceChildren(createElement('div', 'empty-panel', 'Scanning PATH and checking CLI status…'));
    const data = await requestJson('/api/ai/cli-integrations');
    integrations = data.integrations || [];
    renderIntegrations();
    renderProfiles();
}

async function refreshAll() {
    setFeedback('Refreshing provider and CLI status…');
    try {
        await Promise.all([loadProfiles(), loadIntegrations()]);
        setFeedback('Provider status refreshed.', 'success');
    } catch (error) {
        setFeedback(error.message, 'error');
    }
}

document.getElementById('add-provider').addEventListener('click', () => openProfileDialog());
document.getElementById('refresh-cli').addEventListener('click', async () => {
    try {
        await loadIntegrations();
        setFeedback('Local CLI scan completed.', 'success');
    } catch (error) {
        setFeedback(error.message, 'error');
    }
});
document.getElementById('refresh-all').addEventListener('click', refreshAll);
document.getElementById('close-profile-dialog').addEventListener('click', () => elements.dialog.close());
document.getElementById('cancel-profile').addEventListener('click', () => elements.dialog.close());
elements.keySource.addEventListener('change', updateKeyFields);
elements.form.addEventListener('submit', submitProfile);
elements.defaultText.addEventListener('change', saveDefaults);
elements.defaultMultimodal.addEventListener('change', saveDefaults);

refreshAll();
