/**
 * Simple Mode — ComfyUI Meta Viewer
 * Clean, aesthetic, distraction-free creation workflow.
 */

// Application State
const state = {
    profiles: [],
    activeProfileId: 'realism',
    aspectRatio: '1:1',
    quality: 'standard',
    batchSize: 1,
    improveWithAi: true,
    referenceImageDataUrl: null,
    ambientImages: [],
    activeAmbientLayer: 'a',
    currentRunId: null,
    pollInterval: null,
    aiAssistantHistory: [],
    popoverCarouselTimer: null,
    popoverCarouselIndex: 0,
};

// DOM Element References
const elements = {
    promptInput: document.getElementById('prompt-input'),
    referenceFileInput: document.getElementById('reference-file-input'),
    referencePreviewContainer: document.getElementById('reference-preview-container'),
    referencePreviewImg: document.getElementById('reference-preview-img'),
    removeReferenceBtn: document.getElementById('remove-reference-btn'),
    promptClearBtn: document.getElementById('prompt-clear-btn'),
    aiImproveCheckbox: document.getElementById('ai-improve-checkbox'),
    modelCardsContainer: document.getElementById('model-cards-container'),
    modelProvenanceNote: document.getElementById('model-provenance-note'),
    aspectRatioSelector: document.getElementById('aspect-ratio-selector'),
    qualitySelector: document.getElementById('quality-selector'),
    batchSelector: document.getElementById('batch-selector'),
    createButton: document.getElementById('create-button'),
    createProgressFill: document.getElementById('create-progress-fill'),
    createProgressText: document.getElementById('create-progress-text'),
    errorBanner: document.getElementById('generation-error-banner'),
    errorTitle: document.getElementById('error-title'),
    errorMessage: document.getElementById('error-message'),
    errorTechText: document.getElementById('error-tech-text'),
    errorDismissBtn: document.getElementById('error-dismiss-btn'),
    resultsStage: document.getElementById('results-stage'),
    resultsGallery: document.getElementById('results-gallery'),
    ambientLayerA: document.getElementById('ambient-layer-a'),
    ambientLayerB: document.getElementById('ambient-layer-b'),
    modelDetailPopover: document.getElementById('model-detail-popover'),
    popoverCloseBtn: document.getElementById('popover-close-btn'),
    aiAssistantDrawer: document.getElementById('ai-assistant-drawer'),
    aiAssistantToggle: document.getElementById('ai-assistant-toggle'),
    assistantCloseBtn: document.getElementById('assistant-close-btn'),
    assistantNewChatBtn: document.getElementById('assistant-new-chat-btn'),
    assistantMessages: document.getElementById('assistant-messages-container'),
    assistantChatForm: document.getElementById('assistant-chat-form'),
    assistantChatInput: document.getElementById('assistant-chat-input'),
};

/**
 * Bootstrap Simple Mode Data
 */
async function initSimpleMode() {
    // Load persisted preferences
    try {
        const savedAiImprove = localStorage.getItem('cmv_simple_ai_improve');
        if (savedAiImprove !== null) {
            state.improveWithAi = savedAiImprove === 'true';
            if (elements.aiImproveCheckbox) {
                elements.aiImproveCheckbox.checked = state.improveWithAi;
            }
        }
    } catch (_) {}

    setupEventListeners();

    try {
        const res = await fetch('/api/simple/bootstrap');
        if (!res.ok) throw new Error(`Bootstrap failed: ${res.statusText}`);
        const data = await res.json();

        state.profiles = data.profiles || [];
        state.ambientImages = data.ambient_candidates || [];

        // Set initial ambient background
        if (state.ambientImages.length > 0) {
            const randomArt = state.ambientImages[Math.floor(Math.random() * state.ambientImages.length)];
            setAmbientImage(randomArt.preview_url || randomArt.thumbnail_url);
        }

        // Render Model Cards
        renderModelCards();
        updateActiveProfileMeta();
    } catch (err) {
        console.error('Failed to initialize Simple Mode:', err);
        showError('Initialization Error', 'Could not load generation profiles from server.');
    }
}

/**
 * Ambient Artwork Background Crossfade Coordinator
 */
function setAmbientImage(url) {
    if (!url) return;
    if (state.activeAmbientLayer === 'a') {
        elements.ambientLayerB.style.backgroundImage = `url('${url}')`;
        elements.ambientLayerB.classList.add('active');
        elements.ambientLayerA.classList.remove('active');
        state.activeAmbientLayer = 'b';
    } else {
        elements.ambientLayerA.style.backgroundImage = `url('${url}')`;
        elements.ambientLayerA.classList.add('active');
        elements.ambientLayerB.classList.remove('active');
        state.activeAmbientLayer = 'a';
    }
}

/**
 * Render Model Cards
 */
function renderModelCards() {
    if (!elements.modelCardsContainer) return;
    elements.modelCardsContainer.innerHTML = '';

    state.profiles.forEach(profile => {
        const card = document.createElement('div');
        card.className = `model-card ${profile.id === state.activeProfileId ? 'active' : ''}`;
        card.setAttribute('role', 'radio');
        card.setAttribute('aria-checked', profile.id === state.activeProfileId ? 'true' : 'false');
        card.dataset.profileId = profile.id;

        card.innerHTML = `
            <div class="model-card-top">
                <span class="model-card-name">${escapeHtml(profile.name)}</span>
                <button class="model-info-trigger" type="button" title="View ${escapeHtml(profile.name)} details" aria-label="Model info">ℹ</button>
            </div>
            <div class="model-card-tagline">${escapeHtml(profile.tagline || profile.description)}</div>
            <div class="model-card-footer">
                <span class="model-card-family">${escapeHtml(profile.prompt_family.toUpperCase())}</span>
                <span class="model-card-vram">${profile.vram_min_gb}G+ VRAM</span>
            </div>
        `;

        // Select Card Click
        card.addEventListener('click', (e) => {
            if (e.target.closest('.model-info-trigger')) return;
            selectProfile(profile.id);
        });

        // Detail Popover Button
        const infoBtn = card.querySelector('.model-info-trigger');
        if (infoBtn) {
            infoBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                openModelDetailPopover(profile);
            });
        }

        elements.modelCardsContainer.appendChild(card);
    });
}

function selectProfile(profileId) {
    state.activeProfileId = profileId;
    document.querySelectorAll('.model-card').forEach(c => {
        const isActive = c.dataset.profileId === profileId;
        c.classList.toggle('active', isActive);
        c.setAttribute('aria-checked', isActive ? 'true' : 'false');
    });
    updateActiveProfileMeta();
}

function updateActiveProfileMeta() {
    const active = state.profiles.find(p => p.id === state.activeProfileId);
    if (active && elements.modelProvenanceNote) {
        elements.modelProvenanceNote.textContent = active.technical_model || active.name;
    }
}

/**
 * Open Model Detail Popover
 */
function openModelDetailPopover(profile) {
    const popover = elements.modelDetailPopover;
    if (!popover) return;

    document.getElementById('popover-model-name').textContent = profile.name;
    document.getElementById('popover-model-tagline').textContent = profile.tagline || profile.description;
    document.getElementById('popover-vram-min').textContent = `${profile.vram_min_gb} GB`;
    document.getElementById('popover-vram-rec').textContent = `${profile.vram_rec_gb} GB`;
    document.getElementById('popover-prompt-family').textContent = profile.prompt_family.toUpperCase();
    document.getElementById('popover-technical-model').textContent = profile.technical_model;

    // Render Strengths
    const strengthsList = document.getElementById('popover-strengths-list');
    strengthsList.innerHTML = (profile.strengths || []).map(s => `<li>${escapeHtml(s)}</li>`).join('');

    // Render Weaknesses
    const weaknessesList = document.getElementById('popover-weaknesses-list');
    weaknessesList.innerHTML = (profile.weaknesses || []).map(w => `<li>${escapeHtml(w)}</li>`).join('');

    // Render Carousel
    const carousel = document.getElementById('popover-example-carousel');
    carousel.innerHTML = '';
    state.popoverCarouselIndex = 0;

    if (profile.examples && profile.examples.length > 0) {
        profile.examples.forEach((ex, idx) => {
            const img = document.createElement('img');
            img.className = `popover-example-img ${idx === 0 ? 'active' : ''}`;
            img.src = ex.image_url;
            img.alt = ex.title;
            carousel.appendChild(img);
        });
        document.getElementById('popover-example-caption').textContent = profile.examples[0].prompt || profile.examples[0].title;
        startPopoverCarousel(profile.examples);
    } else {
        carousel.innerHTML = '<div style="display:flex;align-items:center;justify-content:center;height:100%;color:#64748b;">No examples available</div>';
        document.getElementById('popover-example-caption').textContent = '';
    }

    popover.hidden = false;
}

function startPopoverCarousel(examples) {
    if (state.popoverCarouselTimer) clearInterval(state.popoverCarouselTimer);
    if (!examples || examples.length <= 1) return;

    state.popoverCarouselTimer = setInterval(() => {
        state.popoverCarouselIndex = (state.popoverCarouselIndex + 1) % examples.length;
        const imgs = document.querySelectorAll('.popover-example-img');
        imgs.forEach((img, idx) => {
            img.classList.toggle('active', idx === state.popoverCarouselIndex);
        });
        const currentEx = examples[state.popoverCarouselIndex];
        if (currentEx) {
            document.getElementById('popover-example-caption').textContent = currentEx.prompt || currentEx.title;
        }
    }, 4000);
}

function closeModelDetailPopover() {
    if (elements.modelDetailPopover) elements.modelDetailPopover.hidden = true;
    if (state.popoverCarouselTimer) {
        clearInterval(state.popoverCarouselTimer);
        state.popoverCarouselTimer = null;
    }
}

/**
 * Generation Execution & Progress
 */
async function handleCreate() {
    if (state.currentRunId) return; // already generating

    const promptText = elements.promptInput ? elements.promptInput.value.trim() : '';
    if (!promptText && !state.referenceImageDataUrl) {
        elements.promptInput.focus();
        showError('Empty Prompt', 'Please describe the image you want to create.');
        return;
    }

    dismissError();
    setGeneratingState(true, 0, 'Starting generation…');

    try {
        const payload = {
            profile_id: state.activeProfileId,
            prompt: promptText,
            improve_with_ai: state.improveWithAi,
            aspect_ratio: state.aspectRatio,
            quality: state.quality,
            batch_size: state.batchSize,
            reference_image: state.referenceImageDataUrl,
        };

        const res = await fetch('/api/simple/generate', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload),
        });

        const data = await res.json();
        if (!res.ok) {
            throw new Error(data.error || data.suggestion || 'Generation request rejected');
        }

        state.currentRunId = data.run_id;
        startPollingRun(data.run_id);
    } catch (err) {
        console.error('Generation failed:', err);
        setGeneratingState(false);
        showError('Generation Failed', err.message);
    }
}

function startPollingRun(runId) {
    if (state.pollInterval) clearInterval(state.pollInterval);

    let progress = 10;
    state.pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/simple/runs/${runId}`);
            if (!res.ok) return;
            const data = await res.json();

            if (data.status === 'running') {
                progress = Math.min(progress + 8, 92);
                setGeneratingState(true, progress, `Creating · ${progress}%`);
            } else if (data.status === 'completed' || data.is_complete) {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.currentRunId = null;
                setGeneratingState(false);
                handleGenerationSuccess(data.outputs || []);
            } else if (data.status === 'failed' || data.status === 'cancelled') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.currentRunId = null;
                setGeneratingState(false);
                showError('Generation Failed', data.run?.error || 'Execution was interrupted in ComfyUI.');
            }
        } catch (e) {
            console.warn('Poll error:', e);
        }
    }, 800);
}

function setGeneratingState(isGenerating, percent = 0, text = 'Creating…') {
    if (!elements.createButton) return;
    if (isGenerating) {
        elements.createButton.classList.add('is-generating');
        elements.createProgressFill.style.width = `${percent}%`;
        elements.createProgressText.textContent = text;
    } else {
        elements.createButton.classList.remove('is-generating');
        elements.createProgressFill.style.width = '0%';
        elements.createProgressText.textContent = 'Create';
    }
}

function handleGenerationSuccess(outputs) {
    if (!outputs || outputs.length === 0) return;

    if (elements.resultsStage) elements.resultsStage.hidden = false;
    if (elements.resultsGallery) {
        elements.resultsGallery.innerHTML = outputs.map(out => `
            <div class="result-item">
                <a href="/library" title="View in library">
                    <img src="${escapeHtml(out.preview_url || out.thumbnail_url)}" alt="Generated image" loading="lazy">
                </a>
            </div>
        `).join('');
    }

    // Seamlessly crossfade ambient background to the newly generated artwork!
    const firstArt = outputs[0];
    if (firstArt) {
        setAmbientImage(firstArt.preview_url || firstArt.thumbnail_url);
    }
}

/**
 * AI Assistant Slide-over Drawer
 */
async function sendAssistantMessage() {
    const input = elements.assistantChatInput;
    if (!input) return;
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    appendAssistantMessage('user', text);
    state.aiAssistantHistory.push({ role: 'user', content: text });

    const typingBubble = appendAssistantMessage('bot', 'Thinking…');

    try {
        const res = await fetch('/api/simple/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                profile_id: state.activeProfileId,
                history: state.aiAssistantHistory,
            }),
        });
        const data = await res.json();
        if (!res.ok) throw new Error(data.error || 'AI Assistant unavailable');

        typingBubble.remove();
        appendAssistantMessage('bot', data.reply, true);
        state.aiAssistantHistory.push({ role: 'assistant', content: data.reply });
    } catch (err) {
        typingBubble.remove();
        appendAssistantMessage('bot', `⚠️ ${err.message}`);
    }
}

function appendAssistantMessage(role, content, showApplyBtn = false) {
    const container = elements.assistantMessages;
    if (!container) return null;

    const div = document.createElement('div');
    div.className = `assistant-message ${role === 'user' ? 'user-msg' : 'bot-msg'}`;
    div.innerHTML = `<p style="margin:0;white-space:pre-wrap;">${escapeHtml(content)}</p>`;

    if (showApplyBtn && role === 'bot') {
        const applyBtn = document.createElement('button');
        applyBtn.className = 'assistant-apply-prompt-btn';
        applyBtn.type = 'button';
        applyBtn.innerHTML = `✦ Use this prompt`;
        applyBtn.addEventListener('click', () => {
            if (elements.promptInput) {
                // Extract clean prompt if inside quotes or code block
                let promptText = content;
                const match = content.match(/```(?:prompt)?\s*([\s\S]*?)```/) || content.match(/"([^"]+)"/);
                if (match) promptText = match[1].trim();
                elements.promptInput.value = promptText;
                elements.promptInput.focus();
                elements.aiAssistantDrawer.hidden = true;
            }
        });
        div.appendChild(applyBtn);
    }

    container.appendChild(div);
    container.scrollTop = container.scrollHeight;
    return div;
}

/**
 * Event Listeners Setup
 */
function setupEventListeners() {
    // Reference Image Upload Handler
    if (elements.referenceFileInput) {
        elements.referenceFileInput.addEventListener('change', (e) => {
            const file = e.target.files[0];
            if (!file) return;
            const reader = new FileReader();
            reader.onload = (evt) => {
                state.referenceImageDataUrl = evt.target.result;
                if (elements.referencePreviewImg) elements.referencePreviewImg.src = state.referenceImageDataUrl;
                if (elements.referencePreviewContainer) elements.referencePreviewContainer.hidden = false;
            };
            reader.readAsDataURL(file);
        });
    }

    // Remove Reference Button
    if (elements.removeReferenceBtn) {
        elements.removeReferenceBtn.addEventListener('click', () => {
            state.referenceImageDataUrl = null;
            if (elements.referenceFileInput) elements.referenceFileInput.value = '';
            if (elements.referencePreviewContainer) elements.referencePreviewContainer.hidden = true;
        });
    }

    // Improve with AI Checkbox
    if (elements.aiImproveCheckbox) {
        elements.aiImproveCheckbox.addEventListener('change', (e) => {
            state.improveWithAi = e.target.checked;
            try {
                localStorage.setItem('cmv_simple_ai_improve', String(state.improveWithAi));
            } catch (_) {}
        });
    }

    // Aspect Ratio Buttons
    if (elements.aspectRatioSelector) {
        elements.aspectRatioSelector.addEventListener('click', (e) => {
            const btn = e.target.closest('.aspect-btn');
            if (!btn) return;
            state.aspectRatio = btn.dataset.ratio;
            elements.aspectRatioSelector.querySelectorAll('.aspect-btn').forEach(b => {
                const isActive = b === btn;
                b.classList.toggle('active', isActive);
                b.setAttribute('aria-checked', isActive ? 'true' : 'false');
            });
        });
    }

    // Quality Preset Buttons
    if (elements.qualitySelector) {
        elements.qualitySelector.addEventListener('click', (e) => {
            const btn = e.target.closest('.segmented-btn');
            if (!btn) return;
            state.quality = btn.dataset.quality;
            elements.qualitySelector.querySelectorAll('.segmented-btn').forEach(b => {
                const isActive = b === btn;
                b.classList.toggle('active', isActive);
                b.setAttribute('aria-checked', isActive ? 'true' : 'false');
            });
        });
    }

    // Batch Count Buttons
    if (elements.batchSelector) {
        elements.batchSelector.addEventListener('click', (e) => {
            const btn = e.target.closest('.segmented-btn');
            if (!btn) return;
            state.batchSize = parseInt(btn.dataset.batch, 10) || 1;
            elements.batchSelector.querySelectorAll('.segmented-btn').forEach(b => {
                const isActive = b === btn;
                b.classList.toggle('active', isActive);
                b.setAttribute('aria-checked', isActive ? 'true' : 'false');
            });
        });
    }

    // Create Button Trigger
    if (elements.createButton) {
        elements.createButton.addEventListener('click', handleCreate);
    }

    // Dismiss Error
    if (elements.errorDismissBtn) {
        elements.errorDismissBtn.addEventListener('click', dismissError);
    }

    // Popover Close
    if (elements.popoverCloseBtn) {
        elements.popoverCloseBtn.addEventListener('click', closeModelDetailPopover);
    }

    // AI Assistant Open / Close
    if (elements.aiAssistantToggle) {
        elements.aiAssistantToggle.addEventListener('click', () => {
            if (elements.aiAssistantDrawer) {
                elements.aiAssistantDrawer.hidden = !elements.aiAssistantDrawer.hidden;
                if (!elements.aiAssistantDrawer.hidden && elements.assistantChatInput) {
                    elements.assistantChatInput.focus();
                }
            }
        });
    }

    if (elements.assistantCloseBtn) {
        elements.assistantCloseBtn.addEventListener('click', () => {
            if (elements.aiAssistantDrawer) elements.aiAssistantDrawer.hidden = true;
        });
    }

    if (elements.assistantNewChatBtn) {
        elements.assistantNewChatBtn.addEventListener('click', () => {
            state.aiAssistantHistory = [];
            if (elements.assistantMessages) {
                elements.assistantMessages.innerHTML = `
                    <div class="assistant-message system-welcome">
                        <p>Conversation restarted. How can I help refine your prompt?</p>
                    </div>
                `;
            }
        });
    }

    if (elements.assistantChatForm) {
        elements.assistantChatForm.addEventListener('submit', (e) => {
            e.preventDefault();
            sendAssistantMessage();
        });
    }

    // Quick suggestion chips in AI Assistant
    if (elements.aiAssistantDrawer) {
        elements.aiAssistantDrawer.addEventListener('click', (e) => {
            const chip = e.target.closest('.quick-suggestion-chip');
            if (chip && chip.dataset.prompt) {
                if (elements.assistantChatInput) elements.assistantChatInput.value = chip.dataset.prompt;
                sendAssistantMessage();
            }
        });
    }

    // Global ESC to close popovers/drawers
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            closeModelDetailPopover();
            if (elements.aiAssistantDrawer && !elements.aiAssistantDrawer.hidden) {
                elements.aiAssistantDrawer.hidden = true;
            }
        }
    });
}

function showError(title, message, techDetails = null) {
    if (!elements.errorBanner) return;
    elements.errorTitle.textContent = title;
    elements.errorMessage.textContent = message;
    if (techDetails && elements.errorTechText) {
        elements.errorTechText.textContent = techDetails;
        elements.errorTechText.parentElement.hidden = false;
    }
    elements.errorBanner.hidden = false;
}

function dismissError() {
    if (elements.errorBanner) elements.errorBanner.hidden = true;
}

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

// Initialize on DOM Ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSimpleMode);
} else {
    initSimpleMode();
}
