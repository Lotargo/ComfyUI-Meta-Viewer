const elements = {
    secretStatus: document.getElementById('secret-store-status'),
    secretTitle: document.getElementById('secret-store-title'),
    secretDetail: document.getElementById('secret-store-detail'),
    toast: document.getElementById('toast'),
    profilesGrid: document.getElementById('profiles-grid'),
    profilesEmpty: document.getElementById('profiles-empty'),
    cliGrid: document.getElementById('cli-grid'),
    cliSection: document.getElementById('cli-section'),
    defaultPanel: document.getElementById('default-profile-panel'),
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
    standardModelField: document.getElementById('standard-model-field'),
    model: document.getElementById('profile-model'),
    modelCombobox: document.getElementById('profile-model-combobox'),
    modelOptions: document.getElementById('profile-model-options'),
    modelToggle: document.getElementById('profile-model-toggle'),
    opencodeModelFields: document.getElementById('opencode-model-fields'),
    modelProvider: document.getElementById('profile-model-provider'),
    modelProviderCombobox: document.getElementById('profile-model-provider-combobox'),
    modelProviderOptions: document.getElementById('profile-model-provider-options'),
    modelProviderToggle: document.getElementById('profile-model-provider-toggle'),
    modelName: document.getElementById('profile-model-name'),
    modelNameCombobox: document.getElementById('profile-model-name-combobox'),
    modelNameOptions: document.getElementById('profile-model-name-options'),
    modelNameToggle: document.getElementById('profile-model-name-toggle'),
    modelCatalogHint: document.getElementById('model-catalog-hint'),
    catalogDialog: document.getElementById('model-catalog-dialog'),
    catalogForm: document.getElementById('model-catalog-form'),
    catalogProviders: document.getElementById('model-catalog-providers'),
    catalogStatus: document.getElementById('model-catalog-status'),
    catalogError: document.getElementById('model-catalog-error'),
    catalogProviderId: document.getElementById('model-catalog-provider-id'),
    catalogDiscover: document.getElementById('discover-model-catalog'),
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
let cliCatalog = [];
const CONNECTED_CLI_STORAGE_KEY = 'cmv_ai_connected_cli_types_v1';
const MODEL_CATALOG_STORAGE_KEY = 'cmv_ai_model_catalog_v1';
const cliProbes = new Map();
const cliPending = new Set();
const activeTests = new Map();
let modelChoices = [];
let activeModelOptionIndex = -1;
let modelProviderLoadingToken = 0;
const discoveredCatalogModels = new Map();
let catalogDraft = new Map();

function readConnectedCliTypes() {
    try {
        const stored = JSON.parse(localStorage.getItem(CONNECTED_CLI_STORAGE_KEY) || '[]');
        return new Set(Array.isArray(stored) ? stored.filter(type => typeof type === 'string') : []);
    } catch {
        return new Set();
    }
}

const connectedCliTypes = readConnectedCliTypes();

function writeConnectedCliTypes() {
    try {
        localStorage.setItem(CONNECTED_CLI_STORAGE_KEY, JSON.stringify([...connectedCliTypes]));
    } catch {
        // CLI probing still works when browser storage is unavailable.
    }
}

function readModelCatalogSettings() {
    try {
        const stored = JSON.parse(localStorage.getItem(MODEL_CATALOG_STORAGE_KEY) || '{}');
        const providers = stored?.opencode?.providers;
        const result = Object.create(null);
        if (!providers || typeof providers !== 'object' || Array.isArray(providers)) return result;
        Object.entries(providers)
            .filter(([provider, models]) => (
                typeof provider === 'string'
                && provider
                && Array.isArray(models)
            ))
            .forEach(([provider, models]) => {
                result[provider] = [
                    ...new Set(models.filter(model => typeof model === 'string' && model)),
                ];
            });
        return result;
    } catch {
        return Object.create(null);
    }
}

let visibleOpenCodeCatalog = readModelCatalogSettings();

function writeModelCatalogSettings() {
    try {
        localStorage.setItem(MODEL_CATALOG_STORAGE_KEY, JSON.stringify({
            opencode: { providers: visibleOpenCodeCatalog },
        }));
    } catch {
        // Manual provider and model entry remains available without browser storage.
    }
}

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

function showToast(message, isError = false) {
    if (!elements.toast) return;
    elements.toast.textContent = message;
    elements.toast.classList.toggle('toast-error', isError);
    elements.toast.classList.add('show');
    window.clearTimeout(showToast.timer);
    showToast.timer = window.setTimeout(() => elements.toast.classList.remove('show'), 3200);
}

function renderSecretStore() {
    elements.secretStatus.classList.toggle('available', secretStore.available);
    elements.secretStatus.classList.toggle('unavailable', !secretStore.available);
    elements.secretTitle.textContent = secretStore.available
        ? 'System credential store available'
        : 'System credential store unavailable';
    const detail = secretStore.available
        ? ''
        : (secretStore.message || 'Use an environment variable for API credentials.');
    elements.secretDetail.textContent = detail;
    elements.secretDetail.hidden = !detail;
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

function trashIcon() {
    const svg = document.createElementNS('http://www.w3.org/2000/svg', 'svg');
    svg.setAttribute('viewBox', '0 0 24 24');
    svg.setAttribute('fill', 'none');
    svg.setAttribute('stroke', 'currentColor');
    svg.setAttribute('stroke-width', '2');
    svg.setAttribute('stroke-linecap', 'round');
    svg.setAttribute('stroke-linejoin', 'round');
    svg.innerHTML = '<path d="M3 6h18"/><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6"/><path d="M8 6V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"/>';
    return svg;
}

function profileKindLabel(profile) {
    if (profile.kind === 'openai_compatible') return 'OpenAI-compatible';
    return cliCatalog.find(item => item.type === profile.cli_type)?.label
        || profile.cli_type
        || 'Local CLI';
}

function renderProfiles() {
    elements.profilesGrid.replaceChildren();
    elements.profilesEmpty.hidden = profiles.length > 0;
    elements.defaultPanel.hidden = profiles.length === 0;
    profiles.forEach(profile => {
        const card = createElement('article', 'profile-card');
        card.dataset.profileId = profile.id;
        const top = createElement('div', 'card-topline');
        const heading = createElement('div');
        heading.append(createElement('h3', '', profile.name));
        heading.append(createElement('p', 'model-id', profile.model));
        if (profile.kind === 'openai_compatible' && profile.base_url) {
            heading.append(createElement('p', 'model-id', profile.base_url));
        }
        top.append(heading);
        top.append(createElement('span', 'profile-badge', profileKindLabel(profile)));
        card.append(top);

        const deleteButton = createElement('button', 'card-delete');
        deleteButton.type = 'button';
        deleteButton.title = `Delete “${profile.name}”`;
        deleteButton.setAttribute('aria-label', `Delete profile ${profile.name}`);
        deleteButton.append(trashIcon());
        deleteButton.addEventListener('click', () => deleteProfile(profile));
        card.append(deleteButton);

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
        showToast('Default AI profiles updated.');
    } catch (error) {
        renderDefaultSelectors();
        showToast(error.message, true);
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
    const timeoutSeconds = Math.max(5, Number(profile.timeout_seconds) || 60);
    let elapsedSeconds = 0;
    let clientTimedOut = false;
    button.textContent = 'Cancel test';
    result.hidden = false;
    result.className = 'card-test-result';
    const progressLabel = multimodal ? 'Testing image input' : 'Testing text input';
    result.textContent = `${progressLabel}… 0s / ${timeoutSeconds}s`;
    const progressTimer = window.setInterval(() => {
        elapsedSeconds += 1;
        result.textContent = `${progressLabel}… ${elapsedSeconds}s / ${timeoutSeconds}s`;
    }, 1000);
    const deadlineTimer = window.setTimeout(() => {
        clientTimedOut = true;
        controller.abort();
    }, (timeoutSeconds + 3) * 1000);
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
        if (clientTimedOut) {
            result.textContent = `Test timed out after ${timeoutSeconds} seconds.`;
        } else {
            result.textContent = error.name === 'AbortError' ? 'Test cancelled.' : error.message;
        }
        if (error.technicalError) result.title = error.technicalError;
    } finally {
        window.clearInterval(progressTimer);
        window.clearTimeout(deadlineTimer);
        activeTests.delete(profile.id);
        button.textContent = originalLabel;
    }
}

async function deleteProfile(profile) {
    if (!window.confirm(`Delete the profile “${profile.name}” and its stored API key?`)) return;
    try {
        await requestJson(`/api/ai/profiles/${profile.id}`, { method: 'DELETE' });
        await loadProfiles();
        showToast(`Deleted “${profile.name}”.`);
    } catch (error) {
        showToast(error.message, true);
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

function currentOs() {
    const ua = navigator.userAgent;
    if (/windows/i.test(ua)) return 'windows';
    if (/mac os|macintosh/i.test(ua)) return 'macos';
    return 'linux';
}

function copyCommand(command, button) {
    const done = () => {
        button.textContent = 'Copied';
        window.setTimeout(() => { button.textContent = 'Copy'; }, 1600);
    };
    if (navigator.clipboard?.writeText) {
        navigator.clipboard.writeText(command).then(done, () => showToast('Copy failed', true));
    } else {
        const helper = createElement('textarea');
        helper.value = command;
        document.body.append(helper);
        helper.select();
        try {
            document.execCommand('copy');
            done();
        } catch {
            showToast('Copy failed', true);
        }
        helper.remove();
    }
}

function buildInstallBlock(install) {
    const block = createElement('div', 'cli-install');
    block.append(createElement('p', 'cli-install-title', 'Install the CLI with a terminal command:'));
    const osKeys = ['windows', 'macos', 'linux'];
    const detected = currentOs();
    osKeys
        .sort((a, b) => (a === detected ? -1 : b === detected ? 1 : 0))
        .forEach(osKey => {
            const entry = install[osKey];
            if (!entry) return;
            const row = createElement('div', `cli-install-os${osKey === detected ? ' current' : ''}`);
            row.append(createElement('span', 'cli-install-label', entry.label));
            if (entry.command) {
                row.append(createElement('code', '', entry.command));
                const copy = actionButton('Copy', () => copyCommand(entry.command, copy), 'cli-copy');
                row.append(copy);
            } else if (entry.url) {
                const link = createElement('a', '', 'Download from the official site');
                link.href = entry.url;
                link.target = '_blank';
                link.rel = 'noopener noreferrer';
                row.append(link);
            }
            block.append(row);
        });
    const note = createElement('p', 'cli-install-note');
    note.append('If the command is not on PATH afterwards, run ');
    note.append(createElement('code', '', install.path_setup_command));
    note.append(`. ${install.note} `);
    const docs = createElement('a', '', 'CLI installation docs');
    docs.href = install.docs_url;
    docs.target = '_blank';
    docs.rel = 'noopener noreferrer';
    note.append(docs);
    block.append(note);
    return block;
}

function cliStatusBadge(integration) {
    const status = integration.authentication?.status || 'unknown';
    if (status === 'available') return { className: 'available', text: integration.version || 'Installed' };
    if (status === 'error') return { className: 'error', text: integration.version || 'Installed' };
    if (status === 'missing') return { className: 'warning', text: integration.version || 'Installed' };
    return { className: 'neutral', text: integration.version || 'Installed' };
}

function renderCliCard(entry) {
    const integration = cliProbes.get(entry.type);
    const pending = cliPending.has(entry.type);
    const card = createElement('article', `cli-card${integration || pending ? '' : ' unchecked'}`);
    card.dataset.cliType = entry.type;

    const top = createElement('div', 'cli-topline');
    const heading = createElement('div');
    heading.append(createElement('h3', '', entry.label));
    const subtitle = integration
        ? (integration.executable || 'Executable not found in PATH')
        : 'Not checked yet';
    heading.append(createElement('p', 'cli-path', subtitle));
    top.append(heading);

    let badge;
    if (pending) {
        badge = { className: 'neutral', text: 'Checking…' };
    } else if (!integration) {
        badge = { className: 'neutral', text: 'Not checked' };
    } else if (integration.installed) {
        badge = cliStatusBadge(integration);
    } else if (integration.ide?.installed) {
        badge = { className: 'warning', text: 'CLI not installed' };
    } else {
        badge = { className: 'neutral', text: 'Not installed' };
    }
    top.append(createElement('span', `cli-status ${badge.className}`, badge.text));
    card.append(top);

    const message = createElement('p', 'cli-message');
    card.append(message);

    if (!integration && !pending) {
        message.textContent = 'Press Connect to probe this tool. Nothing runs until then.';
        const actions = createElement('div', 'card-actions');
        actions.append(actionButton('Connect', () => connectCli(entry.type), 'btn btn-primary'));
        card.append(actions);
        return card;
    }
    if (pending) {
        message.textContent = 'Probing PATH and checking status…';
        return card;
    }

    message.textContent = integration.authentication?.message
        || authenticationLabel(integration.authentication);

    const badges = createElement('div', 'badge-row');
    if (integration.installed) {
        appendBadge(badges, authenticationLabel(integration.authentication),
            integration.authentication?.status === 'available' ? 'vision' : '');
        if (integration.multimodal) appendBadge(badges, 'Image attachment', 'vision');
        if (integration.experimental) appendBadge(badges, 'Experimental adapter');
    }
    card.append(badges);

    if (!integration.installed && integration.install) {
        card.append(buildInstallBlock(integration.install));
    }

    const actions = createElement('div', 'card-actions');
    if (integration.installed) {
        actions.append(actionButton('Create profile', () => prepareCliProfile(integration, message)));
    }
    actions.append(actionButton('Re-check', () => connectCli(entry.type)));
    card.append(actions);
    return card;
}

function renderIntegrations() {
    elements.cliGrid.replaceChildren();
    cliCatalog.forEach(entry => elements.cliGrid.append(renderCliCard(entry)));
}

async function connectCli(cliType) {
    if (cliPending.has(cliType)) return;
    cliPending.add(cliType);
    renderIntegrations();
    try {
        const data = await requestJson(`/api/ai/cli-integrations/${cliType}`);
        cliProbes.set(cliType, data.integration);
        connectedCliTypes.add(cliType);
        writeConnectedCliTypes();
    } catch (error) {
        showToast(error.message, true);
    } finally {
        cliPending.delete(cliType);
        renderIntegrations();
    }
}

async function prepareCliProfile(integration, message) {
    if (integration.type === 'opencode') {
        message.textContent = 'Choose a visible provider, then load only its model list.';
        openProfileDialog(null, integration);
        return;
    }
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

function modelChoiceParts(model) {
    const separator = model.indexOf('/');
    if (separator <= 0 || separator === model.length - 1) {
        return { provider: 'Other models', name: model };
    }
    return {
        provider: model.slice(0, separator),
        name: model.slice(separator + 1),
    };
}

function closeModelOptions() {
    elements.modelOptions.hidden = true;
    elements.model.setAttribute('aria-expanded', 'false');
    elements.modelToggle.setAttribute('aria-expanded', 'false');
    elements.model.removeAttribute('aria-activedescendant');
    activeModelOptionIndex = -1;
}

function visibleModelOptions() {
    return [...elements.modelOptions.querySelectorAll('.model-option')];
}

function setActiveModelOption(index) {
    const options = visibleModelOptions();
    if (!options.length) return;
    options.forEach(option => option.classList.remove('active'));
    activeModelOptionIndex = (index + options.length) % options.length;
    const active = options[activeModelOptionIndex];
    active.classList.add('active');
    elements.model.setAttribute('aria-activedescendant', active.id);
    active.scrollIntoView({ block: 'nearest' });
}

function renderModelOptions(query = '') {
    if (!modelChoices.length) {
        closeModelOptions();
        return;
    }
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const matches = modelChoices.filter(model => (
        !normalizedQuery || model.toLocaleLowerCase().includes(normalizedQuery)
    ));
    elements.modelOptions.replaceChildren();
    activeModelOptionIndex = -1;

    if (!matches.length) {
        elements.modelOptions.append(createElement(
            'p',
            'model-options-empty',
            'No matching models. You can still enter an exact ID manually.',
        ));
    } else {
        const groups = new Map();
        matches.forEach(model => {
            const parts = modelChoiceParts(model);
            if (!groups.has(parts.provider)) groups.set(parts.provider, []);
            groups.get(parts.provider).push({ id: model, name: parts.name });
        });
        let optionIndex = 0;
        groups.forEach((models, provider) => {
            const group = createElement('div', 'model-option-group');
            group.setAttribute('role', 'group');
            group.setAttribute('aria-label', provider);
            group.append(createElement('div', 'model-option-provider', provider));
            models.forEach(model => {
                const option = createElement('div', 'model-option');
                option.id = `profile-model-option-${optionIndex}`;
                option.dataset.value = model.id;
                option.setAttribute('role', 'option');
                option.setAttribute('aria-selected', String(elements.model.value === model.id));
                option.append(createElement('span', 'model-option-name', model.name));
                if (model.name !== model.id) {
                    option.append(createElement('span', 'model-option-id', model.id));
                }
                group.append(option);
                optionIndex += 1;
            });
            elements.modelOptions.append(group);
        });
    }
    elements.modelOptions.hidden = false;
    elements.model.setAttribute('aria-expanded', 'true');
    elements.modelToggle.setAttribute('aria-expanded', 'true');
}

function selectModelOption(option) {
    elements.model.value = option.dataset.value;
    closeModelOptions();
    elements.model.focus();
}

function setModelChoices(models) {
    modelChoices = [...new Set(
        models
            .filter(model => typeof model === 'string' && model.trim())
            .map(model => model.trim()),
    )].slice(0, 2000);
    closeModelOptions();
    elements.modelToggle.hidden = modelChoices.length === 0;
}

function createPicker(prefix, combobox, input, toggle, options) {
    return {
        prefix,
        combobox,
        input,
        toggle,
        options,
        choices: [],
        activeIndex: -1,
        onCommit: null,
    };
}

const providerPicker = createPicker(
    'profile-provider',
    elements.modelProviderCombobox,
    elements.modelProvider,
    elements.modelProviderToggle,
    elements.modelProviderOptions,
);
const modelNamePicker = createPicker(
    'profile-model-name',
    elements.modelNameCombobox,
    elements.modelName,
    elements.modelNameToggle,
    elements.modelNameOptions,
);

function closePicker(picker) {
    picker.options.hidden = true;
    picker.input.setAttribute('aria-expanded', 'false');
    picker.toggle.setAttribute('aria-expanded', 'false');
    picker.input.removeAttribute('aria-activedescendant');
    picker.activeIndex = -1;
}

function pickerOptionElements(picker) {
    return [...picker.options.querySelectorAll('.model-option')];
}

function setPickerActiveOption(picker, index) {
    const options = pickerOptionElements(picker);
    if (!options.length) return;
    options.forEach(option => option.classList.remove('active'));
    picker.activeIndex = (index + options.length) % options.length;
    const active = options[picker.activeIndex];
    active.classList.add('active');
    picker.input.setAttribute('aria-activedescendant', active.id);
    active.scrollIntoView({ block: 'nearest' });
}

function renderPickerOptions(picker, query = '') {
    if (!picker.choices.length) {
        closePicker(picker);
        return;
    }
    const normalizedQuery = query.trim().toLocaleLowerCase();
    const matches = picker.choices.filter(choice => (
        !normalizedQuery
        || choice.value.toLocaleLowerCase().includes(normalizedQuery)
        || choice.label.toLocaleLowerCase().includes(normalizedQuery)
    ));
    picker.options.replaceChildren();
    picker.activeIndex = -1;
    if (!matches.length) {
        picker.options.append(createElement(
            'p',
            'model-options-empty',
            'No matching entries. You can still enter an exact ID manually.',
        ));
    } else {
        matches.forEach((choice, index) => {
            const option = createElement('div', 'model-option');
            option.id = `${picker.prefix}-option-${index}`;
            option.dataset.value = choice.value;
            option.setAttribute('role', 'option');
            option.setAttribute('aria-selected', String(picker.input.value === choice.value));
            option.append(createElement('span', 'model-option-name', choice.label));
            if (choice.detail && choice.detail !== choice.label) {
                option.append(createElement('span', 'model-option-id', choice.detail));
            }
            picker.options.append(option);
        });
    }
    picker.options.hidden = false;
    picker.input.setAttribute('aria-expanded', 'true');
    picker.toggle.setAttribute('aria-expanded', 'true');
}

function selectPickerOption(picker, option) {
    picker.input.value = option.dataset.value;
    closePicker(picker);
    picker.input.focus();
    if (picker.onCommit) picker.onCommit(picker.input.value);
}

function setPickerChoices(picker, choices) {
    const seen = new Set();
    picker.choices = choices.filter(choice => {
        if (!choice?.value || seen.has(choice.value)) return false;
        seen.add(choice.value);
        return true;
    });
    closePicker(picker);
    picker.options.replaceChildren();
    picker.toggle.hidden = picker.choices.length === 0;
}

function bindPicker(picker) {
    picker.input.addEventListener('focus', () => renderPickerOptions(picker));
    picker.input.addEventListener('input', () => renderPickerOptions(picker, picker.input.value));
    picker.input.addEventListener('keydown', event => {
        if (event.key === 'ArrowDown') {
            event.preventDefault();
            if (picker.options.hidden) renderPickerOptions(picker);
            setPickerActiveOption(picker, picker.activeIndex + 1);
        } else if (event.key === 'ArrowUp') {
            event.preventDefault();
            if (picker.options.hidden) renderPickerOptions(picker);
            setPickerActiveOption(picker, picker.activeIndex - 1);
        } else if (event.key === 'Enter' && !picker.options.hidden) {
            const option = pickerOptionElements(picker)[picker.activeIndex];
            if (option) {
                event.preventDefault();
                selectPickerOption(picker, option);
            } else if (picker.onCommit && picker.input.value.trim()) {
                event.preventDefault();
                closePicker(picker);
                picker.onCommit(picker.input.value.trim());
            }
        } else if (event.key === 'Escape' || event.key === 'Tab') {
            closePicker(picker);
        }
    });
    picker.toggle.addEventListener('click', () => {
        if (!picker.options.hidden) {
            closePicker(picker);
            return;
        }
        picker.input.focus();
        renderPickerOptions(picker);
    });
    picker.options.addEventListener('pointerdown', event => event.preventDefault());
    picker.options.addEventListener('click', event => {
        const option = event.target.closest('.model-option');
        if (option) selectPickerOption(picker, option);
    });
}

function splitOpenCodeModel(model) {
    const separator = model.indexOf('/');
    if (separator <= 0 || separator === model.length - 1) {
        return { provider: '', model };
    }
    return {
        provider: model.slice(0, separator),
        model: model.slice(separator + 1),
    };
}

function visibleProviderChoices(currentProvider = '') {
    const providers = Object.keys(visibleOpenCodeCatalog);
    if (currentProvider && !providers.includes(currentProvider)) providers.push(currentProvider);
    return providers.sort((left, right) => left.localeCompare(right)).map(provider => ({
        value: provider,
        label: provider,
    }));
}

function setOpenCodeModelChoices(provider, models) {
    const prefix = `${provider}/`;
    setPickerChoices(modelNamePicker, models.map(model => {
        const fullId = model.startsWith(prefix) ? model : `${prefix}${model}`;
        return {
            value: fullId.slice(prefix.length),
            label: fullId.slice(prefix.length),
            detail: fullId,
        };
    }));
}

async function loadOpenCodeProviderModels(provider, { preserveModel = false } = {}) {
    const providerId = provider.trim();
    if (!providerId) {
        setPickerChoices(modelNamePicker, []);
        return;
    }
    const currentToken = ++modelProviderLoadingToken;
    const selectedModels = visibleOpenCodeCatalog[providerId];
    if (!preserveModel) elements.modelName.value = '';
    if (selectedModels?.length) {
        setOpenCodeModelChoices(providerId, selectedModels);
        elements.modelCatalogHint.textContent = (
            `${selectedModels.length} selected model${selectedModels.length === 1 ? '' : 's'} shown. `
            + 'No catalog request was needed.'
        );
        return;
    }
    if (discoveredCatalogModels.has(providerId)) {
        const models = discoveredCatalogModels.get(providerId);
        setOpenCodeModelChoices(providerId, models);
        elements.modelCatalogHint.textContent = `${models.length} models available for ${providerId}.`;
        return;
    }
    elements.modelCatalogHint.textContent = `Loading models for ${providerId}…`;
    setPickerChoices(modelNamePicker, []);
    try {
        const query = new URLSearchParams({ provider: providerId });
        const data = await requestJson(`/api/ai/cli-integrations/opencode/models?${query}`);
        if (currentToken !== modelProviderLoadingToken) return;
        const models = data.models || [];
        discoveredCatalogModels.set(providerId, models);
        setOpenCodeModelChoices(providerId, models);
        elements.modelCatalogHint.textContent = (
            `${models.length} models loaded for ${providerId}; other providers were not requested.`
        );
    } catch (error) {
        if (currentToken !== modelProviderLoadingToken) return;
        elements.modelCatalogHint.textContent = `Could not load ${providerId}: ${error.message}`;
    }
}

function chooseOpenCodeProvider(provider, options) {
    const providerId = provider.trim();
    if (providerId === elements.modelProvider.dataset.committedProvider) return;
    elements.modelProvider.dataset.committedProvider = providerId;
    elements.modelProvider.value = providerId;
    closePicker(providerPicker);
    loadOpenCodeProviderModels(providerId, options);
}

function configureOpenCodeModelFields(savedModel = '') {
    const saved = splitOpenCodeModel(savedModel);
    const providerIds = Object.keys(visibleOpenCodeCatalog);
    const provider = saved.provider || (providerIds.length === 1 ? providerIds[0] : '');
    elements.modelProvider.value = provider;
    elements.modelProvider.dataset.committedProvider = provider;
    elements.modelName.value = saved.model;
    setPickerChoices(providerPicker, visibleProviderChoices(provider));
    if (!providerIds.length && !provider) {
        elements.modelCatalogHint.textContent = (
            'No providers are visible yet. Add one in Display settings or enter its ID manually.'
        );
        setPickerChoices(modelNamePicker, []);
    } else if (provider) {
        loadOpenCodeProviderModels(provider, { preserveModel: Boolean(saved.model) });
    } else {
        elements.modelCatalogHint.textContent = `${providerIds.length} providers are available.`;
        setPickerChoices(modelNamePicker, []);
    }
}

function catalogModelsByProvider(models) {
    const groups = new Map();
    models.forEach(model => {
        if (typeof model !== 'string') return;
        const parts = splitOpenCodeModel(model);
        if (!parts.provider) return;
        if (!groups.has(parts.provider)) groups.set(parts.provider, []);
        groups.get(parts.provider).push(model);
    });
    return groups;
}

function ensureCatalogDraftProvider(provider, enabled = false) {
    if (!catalogDraft.has(provider)) {
        catalogDraft.set(provider, {
            enabled,
            mode: 'all',
            models: new Set(),
        });
    }
    return catalogDraft.get(provider);
}

function resetCatalogDraft() {
    catalogDraft = new Map();
    Object.entries(visibleOpenCodeCatalog).forEach(([provider, models]) => {
        catalogDraft.set(provider, {
            enabled: true,
            mode: models.length ? 'selected' : 'all',
            models: new Set(models),
        });
    });
    discoveredCatalogModels.forEach((_models, provider) => {
        ensureCatalogDraftProvider(provider);
    });
}

function catalogRadio(provider, index, value, checked, label) {
    const wrapper = createElement('label', 'catalog-radio');
    const input = document.createElement('input');
    input.type = 'radio';
    input.name = `catalog-mode-${index}`;
    input.value = value;
    input.dataset.role = 'catalog-mode';
    input.dataset.provider = provider;
    input.checked = checked;
    wrapper.append(input, createElement('span', '', label));
    return wrapper;
}

function renderCatalogSettings() {
    elements.catalogProviders.replaceChildren();
    const providers = [...catalogDraft.keys()].sort((left, right) => left.localeCompare(right));
    if (!providers.length) {
        elements.catalogProviders.append(createElement(
            'p',
            'catalog-empty',
            'Add a provider ID to avoid loading the complete catalog, or discover all providers once.',
        ));
        return;
    }
    providers.forEach((provider, index) => {
        const state = catalogDraft.get(provider);
        const knownModels = [...new Set([
            ...(discoveredCatalogModels.get(provider) || []),
            ...state.models,
        ])];
        const card = createElement('section', `catalog-provider${state.enabled ? ' enabled' : ''}`);
        card.dataset.provider = provider;
        const header = createElement('div', 'catalog-provider-header');
        const providerLabel = createElement('label', 'catalog-provider-check');
        const checkbox = document.createElement('input');
        checkbox.type = 'checkbox';
        checkbox.checked = state.enabled;
        checkbox.dataset.role = 'catalog-provider';
        checkbox.dataset.provider = provider;
        providerLabel.append(checkbox, createElement('strong', '', provider));
        header.append(providerLabel);
        header.append(createElement(
            'span',
            'catalog-model-count',
            knownModels.length ? `${knownModels.length} known` : 'Not loaded',
        ));
        card.append(header);

        if (state.enabled) {
            const controls = createElement('div', 'catalog-provider-controls');
            const modes = createElement('div', 'catalog-mode-row');
            modes.append(
                catalogRadio(provider, index, 'all', state.mode === 'all', 'Show all models'),
                catalogRadio(provider, index, 'selected', state.mode === 'selected', 'Only selected models'),
            );
            controls.append(modes);

            if (state.mode === 'selected' && knownModels.length) {
                const search = document.createElement('input');
                search.className = 'catalog-model-search';
                search.type = 'search';
                search.placeholder = `Filter ${provider} models`;
                search.dataset.role = 'catalog-search';
                search.dataset.provider = provider;
                controls.append(search);
                const list = createElement('div', 'catalog-model-list');
                knownModels.forEach(model => {
                    const parts = splitOpenCodeModel(model);
                    const option = createElement('label', 'catalog-model-option');
                    option.dataset.search = model.toLocaleLowerCase();
                    const modelCheckbox = document.createElement('input');
                    modelCheckbox.type = 'checkbox';
                    modelCheckbox.checked = state.models.has(model);
                    modelCheckbox.dataset.role = 'catalog-model';
                    modelCheckbox.dataset.provider = provider;
                    modelCheckbox.value = model;
                    option.append(modelCheckbox, createElement('span', '', parts.model));
                    list.append(option);
                });
                controls.append(list);
            } else if (state.mode === 'selected') {
                controls.append(createElement(
                    'p', 'catalog-provider-note', 'Load this provider to choose individual models.',
                ));
            } else {
                controls.append(createElement(
                    'p',
                    'catalog-provider-note',
                    'The model list will be requested only for this provider when it is selected.',
                ));
            }
            const load = createElement(
                'button',
                'btn btn-secondary catalog-load-provider',
                knownModels.length ? 'Refresh provider models' : 'Load provider models',
            );
            load.type = 'button';
            load.dataset.action = 'load-provider';
            load.dataset.provider = provider;
            controls.append(load);
            card.append(controls);
        }
        elements.catalogProviders.append(card);
    });
}

function openCatalogSettings() {
    resetCatalogDraft();
    elements.catalogError.hidden = true;
    elements.catalogError.textContent = '';
    elements.catalogProviderId.value = '';
    elements.catalogStatus.textContent = (
        'The complete catalog is requested only when you press Discover all providers.'
    );
    renderCatalogSettings();
    elements.catalogDialog.showModal();
}

async function loadCatalogProvider(provider) {
    elements.catalogStatus.textContent = `Loading only ${provider} models…`;
    try {
        const query = new URLSearchParams({ provider });
        const data = await requestJson(`/api/ai/cli-integrations/opencode/models?${query}`);
        discoveredCatalogModels.set(provider, data.models || []);
        ensureCatalogDraftProvider(provider, true);
        elements.catalogStatus.textContent = (
            `${data.models?.length || 0} models loaded for ${provider}; other providers were not requested.`
        );
        renderCatalogSettings();
    } catch (error) {
        elements.catalogStatus.textContent = `Could not load ${provider}: ${error.message}`;
    }
}

async function discoverCatalogProviders() {
    elements.catalogDiscover.disabled = true;
    elements.catalogStatus.textContent = 'Discovering the complete OpenCode catalog…';
    try {
        const data = await requestJson('/api/ai/cli-integrations/opencode/models');
        const groups = catalogModelsByProvider(data.models || []);
        groups.forEach((models, provider) => {
            discoveredCatalogModels.set(provider, models);
            ensureCatalogDraftProvider(provider);
        });
        elements.catalogStatus.textContent = (
            `${groups.size} providers discovered. Select only the ones you want to display.`
        );
        renderCatalogSettings();
    } catch (error) {
        elements.catalogStatus.textContent = `Catalog discovery failed: ${error.message}`;
    } finally {
        elements.catalogDiscover.disabled = false;
    }
}

function addCatalogProvider() {
    const provider = elements.catalogProviderId.value.trim();
    if (!provider || provider.length > 100 || /[\s/]/.test(provider)) {
        elements.catalogError.textContent = 'Enter a provider ID without spaces or slashes.';
        elements.catalogError.hidden = false;
        return;
    }
    ensureCatalogDraftProvider(provider, true).enabled = true;
    elements.catalogProviderId.value = '';
    elements.catalogError.hidden = true;
    renderCatalogSettings();
}

function saveCatalogSettings(event) {
    event.preventDefault();
    const next = Object.create(null);
    for (const [provider, state] of catalogDraft) {
        if (!state.enabled) continue;
        if (state.mode === 'selected' && !state.models.size) {
            elements.catalogError.textContent = (
                `Select at least one ${provider} model, or choose Show all models.`
            );
            elements.catalogError.hidden = false;
            return;
        }
        next[provider] = state.mode === 'selected' ? [...state.models] : [];
    }
    if (!Object.keys(next).length) {
        elements.catalogError.textContent = 'Select at least one provider to display.';
        elements.catalogError.hidden = false;
        return;
    }
    visibleOpenCodeCatalog = next;
    writeModelCatalogSettings();
    setPickerChoices(providerPicker, visibleProviderChoices(elements.modelProvider.value));
    elements.catalogDialog.close();
    const currentProvider = elements.modelProvider.value.trim();
    if (currentProvider) {
        loadOpenCodeProviderModels(currentProvider, {
            preserveModel: Boolean(elements.modelName.value),
        });
    } else {
        elements.modelCatalogHint.textContent = `${Object.keys(next).length} providers are visible.`;
    }
}

function resetProfileForm() {
    elements.form.reset();
    elements.id.value = '';
    elements.kind.value = 'openai_compatible';
    elements.cliType.value = '';
    elements.executable.value = '';
    elements.timeout.value = '60';
    elements.extraBody.value = '';
    elements.modelProvider.value = '';
    elements.modelProvider.dataset.committedProvider = '';
    elements.modelName.value = '';
    setModelChoices([]);
    setPickerChoices(providerPicker, []);
    setPickerChoices(modelNamePicker, []);
    elements.modelOptions.replaceChildren();
    elements.formError.hidden = true;
    elements.formError.textContent = '';
}

function openProfileDialog(profile = null, integration = null, models = []) {
    resetProfileForm();
    const isCli = Boolean(integration || profile?.kind === 'cli');
    const cliType = integration?.type || profile?.cli_type || '';
    const isOpenCode = isCli && cliType === 'opencode';
    elements.kind.value = isCli ? 'cli' : 'openai_compatible';
    elements.cliType.value = cliType;
    elements.executable.value = integration?.executable || profile?.executable || '';
    elements.openaiFields.hidden = isCli;
    elements.extraBodyField.hidden = isCli;
    elements.standardModelField.hidden = isOpenCode;
    elements.opencodeModelFields.hidden = !isOpenCode;
    elements.model.required = !isOpenCode;
    elements.modelProvider.required = isOpenCode;
    elements.modelName.required = isOpenCode;
    elements.dialogKicker.textContent = isCli
        ? (integration?.label || profileKindLabel(profile))
        : 'OpenAI-compatible';
    elements.dialogTitle.textContent = profile ? 'Edit provider profile' : 'Add provider profile';
    elements.saveProfile.textContent = profile ? 'Save changes' : 'Save profile';
    const detectedCli = integration || cliCatalog.find(item => item.type === cliType);
    elements.multimodal.disabled = isCli && !(detectedCli?.multimodal ?? profile?.multimodal);

    if (profile) {
        elements.id.value = profile.id;
        elements.name.value = profile.name;
        if (!isOpenCode) elements.model.value = profile.model;
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
    if (isOpenCode) {
        configureOpenCodeModelFields(profile?.model || '');
    } else {
        setModelChoices(models);
    }
    updateKeyFields();
    elements.dialog.showModal();
    elements.name.focus();
}

function profilePayload() {
    let model = elements.model.value.trim();
    if (elements.kind.value === 'cli' && elements.cliType.value === 'opencode') {
        const provider = elements.modelProvider.value.trim();
        const modelName = elements.modelName.value.trim();
        model = modelName.startsWith(`${provider}/`)
            ? modelName
            : `${provider}/${modelName}`;
    }
    const payload = {
        kind: elements.kind.value,
        name: elements.name.value.trim(),
        model,
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
        showToast(profileId ? 'Provider profile updated.' : 'Provider profile created.');
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

async function loadCliCatalog() {
    let reconnectTypes = [];
    try {
        const data = await requestJson('/api/ai/cli-integrations?probe=0');
        cliCatalog = data.integrations || [];
        const availableTypes = new Set(cliCatalog.map(entry => entry.type));
        let storedTypesChanged = false;
        connectedCliTypes.forEach(type => {
            if (!availableTypes.has(type)) {
                connectedCliTypes.delete(type);
                storedTypesChanged = true;
            }
        });
        if (storedTypesChanged) writeConnectedCliTypes();
        reconnectTypes = [...connectedCliTypes];
    } catch (error) {
        showToast(error.message, true);
    }
    renderIntegrations();
    await Promise.all(reconnectTypes.map(connectCli));
}

async function refreshProfiles() {
    try {
        await loadProfiles();
        showToast('Provider status refreshed.');
    } catch (error) {
        showToast(error.message, true);
    }
}

document.getElementById('add-provider').addEventListener('click', () => openProfileDialog());
document.getElementById('empty-add-provider').addEventListener('click', () => openProfileDialog());
document.getElementById('empty-goto-cli').addEventListener('click', () => {
    elements.cliSection.scrollIntoView({ behavior: 'smooth', block: 'start' });
});
document.getElementById('refresh-all').addEventListener('click', refreshProfiles);
document.getElementById('close-profile-dialog').addEventListener('click', () => elements.dialog.close());
document.getElementById('cancel-profile').addEventListener('click', () => elements.dialog.close());
elements.keySource.addEventListener('change', updateKeyFields);
elements.model.addEventListener('focus', () => renderModelOptions());
elements.model.addEventListener('input', () => renderModelOptions(elements.model.value));
elements.model.addEventListener('keydown', event => {
    if (event.key === 'ArrowDown') {
        event.preventDefault();
        if (elements.modelOptions.hidden) renderModelOptions();
        setActiveModelOption(activeModelOptionIndex + 1);
    } else if (event.key === 'ArrowUp') {
        event.preventDefault();
        if (elements.modelOptions.hidden) renderModelOptions();
        setActiveModelOption(activeModelOptionIndex - 1);
    } else if (event.key === 'Enter' && !elements.modelOptions.hidden) {
        const option = visibleModelOptions()[activeModelOptionIndex];
        if (option) {
            event.preventDefault();
            selectModelOption(option);
        }
    } else if (event.key === 'Escape' || event.key === 'Tab') {
        closeModelOptions();
    }
});
elements.modelToggle.addEventListener('click', () => {
    if (!elements.modelOptions.hidden) {
        closeModelOptions();
        return;
    }
    elements.model.focus();
    renderModelOptions();
});
elements.modelOptions.addEventListener('pointerdown', event => event.preventDefault());
elements.modelOptions.addEventListener('click', event => {
    const option = event.target.closest('.model-option');
    if (option) selectModelOption(option);
});
providerPicker.onCommit = provider => chooseOpenCodeProvider(provider);
bindPicker(providerPicker);
bindPicker(modelNamePicker);
elements.modelProvider.addEventListener('keydown', event => {
    if (event.key === 'Enter' && elements.modelProviderOptions.hidden) {
        event.preventDefault();
        chooseOpenCodeProvider(elements.modelProvider.value);
    }
});
elements.modelProvider.addEventListener('change', () => {
    chooseOpenCodeProvider(elements.modelProvider.value);
});
document.getElementById('open-model-catalog').addEventListener('click', openCatalogSettings);
document.getElementById('close-model-catalog').addEventListener('click', () => {
    elements.catalogDialog.close();
});
document.getElementById('cancel-model-catalog').addEventListener('click', () => {
    elements.catalogDialog.close();
});
document.getElementById('add-model-catalog-provider').addEventListener('click', addCatalogProvider);
elements.catalogProviderId.addEventListener('keydown', event => {
    if (event.key === 'Enter') {
        event.preventDefault();
        addCatalogProvider();
    }
});
elements.catalogDiscover.addEventListener('click', discoverCatalogProviders);
elements.catalogProviders.addEventListener('change', event => {
    const target = event.target;
    const provider = target.dataset.provider;
    if (!provider) return;
    const state = ensureCatalogDraftProvider(provider);
    if (target.dataset.role === 'catalog-provider') {
        state.enabled = target.checked;
        renderCatalogSettings();
    } else if (target.dataset.role === 'catalog-mode') {
        state.mode = target.value;
        renderCatalogSettings();
    } else if (target.dataset.role === 'catalog-model') {
        if (target.checked) state.models.add(target.value);
        else state.models.delete(target.value);
    }
});
elements.catalogProviders.addEventListener('input', event => {
    if (event.target.dataset.role !== 'catalog-search') return;
    const query = event.target.value.trim().toLocaleLowerCase();
    const card = event.target.closest('.catalog-provider');
    card.querySelectorAll('.catalog-model-option').forEach(option => {
        option.hidden = Boolean(query) && !option.dataset.search.includes(query);
    });
});
elements.catalogProviders.addEventListener('click', event => {
    const button = event.target.closest('[data-action="load-provider"]');
    if (button) loadCatalogProvider(button.dataset.provider);
});
elements.catalogForm.addEventListener('submit', saveCatalogSettings);
document.addEventListener('pointerdown', event => {
    if (!elements.modelCombobox.contains(event.target)) closeModelOptions();
    if (!providerPicker.combobox.contains(event.target)) closePicker(providerPicker);
    if (!modelNamePicker.combobox.contains(event.target)) closePicker(modelNamePicker);
});
elements.dialog.addEventListener('close', () => {
    closeModelOptions();
    closePicker(providerPicker);
    closePicker(modelNamePicker);
});
elements.form.addEventListener('submit', submitProfile);
elements.defaultText.addEventListener('change', saveDefaults);
elements.defaultMultimodal.addEventListener('change', saveDefaults);

refreshProfiles();
loadCliCatalog().then(() => renderProfiles());
