/**
 * Create Mode — ComfyUI Meta Viewer
 * Clean, human-centric creation studio with dynamic 5-minute ambient background
 * Refactored using Open Design guidelines: zero-slop UX, tactile micro-interactions, robust state handling.
 */

// Configurable Ambient Rotation Interval (5 minutes)
const AMBIENT_ROTATION_INTERVAL_MS = 5 * 60 * 1000;

// Application State
const state = {
    profiles: [],
    activeProfileId: 'realism',
    aspectRatio: '1:1',
    quality: 'standard',
    batchSize: 1,
    improveWithAi: true,
    referenceImageDataUrl: null,
    referenceFileName: '',
    ambientImages: [],
    ambientIndex: 0,
    activeAmbientLayer: 'a',
    currentRunId: null,
    pollInterval: null,
    ambientRotationTimer: null,
    lastGeneratedOutput: null,
    aiAssistantHistory: [],
};

// DOM Element References
const elements = {
    // Prompt & Inputs
    promptInput: document.getElementById('prompt-input'),
    promptBoxContainer: document.getElementById('prompt-box-container'),
    referenceFileInput: document.getElementById('reference-file-input'),
    referencePreviewContainer: document.getElementById('reference-preview-container'),
    referencePreviewImg: document.getElementById('reference-preview-img'),
    referenceFileName: document.getElementById('reference-filename'),
    removeReferenceBtn: document.getElementById('remove-reference-btn'),
    promptClearBtn: document.getElementById('prompt-clear-btn'),
    aiImproveCheckbox: document.getElementById('ai-improve-checkbox'),
    
    // Style & Parameters
    modelCardsContainer: document.getElementById('model-cards-container'),
    aspectRatioSelector: document.getElementById('aspect-ratio-selector'),
    qualitySelector: document.getElementById('quality-selector'),
    batchSelector: document.getElementById('batch-selector'),
    
    // Primary Action & Error
    createButton: document.getElementById('create-button'),
    createProgressFill: document.getElementById('create-progress-fill'),
    createProgressText: document.getElementById('create-progress-text'),
    errorBanner: document.getElementById('generation-error-banner'),
    errorTitle: document.getElementById('error-title'),
    errorMessage: document.getElementById('error-message'),
    errorTechText: document.getElementById('error-tech-text'),
    errorDismissBtn: document.getElementById('error-dismiss-btn'),
    
    // Canvas & Viewport States
    canvasSurface: document.getElementById('canvas-surface'),
    canvasIdleState: document.getElementById('canvas-idle-state'),
    canvasGeneratingState: document.getElementById('canvas-generating-state'),
    canvasGeneratingStatus: document.getElementById('canvas-generating-status'),
    canvasResultState: document.getElementById('canvas-result-state'),
    canvasResultImg: document.getElementById('canvas-result-img'),
    canvasActionBar: document.getElementById('canvas-action-bar'),
    
    // Canvas Actions
    btnActionDownload: document.getElementById('btn-action-download'),
    btnActionLibrary: document.getElementById('btn-action-library'),
    btnActionRemix: document.getElementById('btn-action-remix'),
    btnActionCopyPrompt: document.getElementById('btn-action-copy-prompt'),
    
    // Ambient Background Layers
    ambientLayerA: document.getElementById('ambient-layer-a'),
    ambientLayerB: document.getElementById('ambient-layer-b'),
    
    // AI Assistant Drawer
    aiAssistantDrawer: document.getElementById('ai-assistant-drawer'),
    aiAssistantToggle: document.getElementById('ai-assistant-toggle'),
    assistantCloseBtn: document.getElementById('assistant-close-btn'),
    assistantNewChatBtn: document.getElementById('assistant-new-chat-btn'),
    assistantMessages: document.getElementById('assistant-messages-container'),
    assistantChatForm: document.getElementById('assistant-chat-form'),
    assistantChatInput: document.getElementById('assistant-chat-input'),
};

/**
 * Re-bind DOM element references dynamically on DOM Ready to avoid null elements due to early execution
 */
function rebindDOMElements() {
    elements.promptInput = document.getElementById('prompt-input');
    elements.promptBoxContainer = document.getElementById('prompt-box-container');
    elements.referenceFileInput = document.getElementById('reference-file-input');
    elements.referencePreviewContainer = document.getElementById('reference-preview-container');
    elements.referencePreviewImg = document.getElementById('reference-preview-img');
    elements.referenceFileName = document.getElementById('reference-filename');
    elements.removeReferenceBtn = document.getElementById('remove-reference-btn');
    elements.promptClearBtn = document.getElementById('prompt-clear-btn');
    elements.aiImproveCheckbox = document.getElementById('ai-improve-checkbox');
    
    elements.modelCardsContainer = document.getElementById('model-cards-container');
    elements.aspectRatioSelector = document.getElementById('aspect-ratio-selector');
    elements.qualitySelector = document.getElementById('quality-selector');
    elements.batchSelector = document.getElementById('batch-selector');
    
    elements.createButton = document.getElementById('create-button');
    elements.createProgressFill = document.getElementById('create-progress-fill');
    elements.createProgressText = document.getElementById('create-progress-text');
    elements.errorBanner = document.getElementById('generation-error-banner');
    elements.errorTitle = document.getElementById('error-title');
    elements.errorMessage = document.getElementById('error-message');
    elements.errorTechText = document.getElementById('error-tech-text');
    elements.errorDismissBtn = document.getElementById('error-dismiss-btn');
    
    elements.canvasSurface = document.getElementById('canvas-surface');
    elements.canvasIdleState = document.getElementById('canvas-idle-state');
    elements.canvasGeneratingState = document.getElementById('canvas-generating-state');
    elements.canvasGeneratingStatus = document.getElementById('canvas-generating-status');
    elements.canvasResultState = document.getElementById('canvas-result-state');
    elements.canvasResultImg = document.getElementById('canvas-result-img');
    elements.canvasActionBar = document.getElementById('canvas-action-bar');
    
    elements.btnActionDownload = document.getElementById('btn-action-download');
    elements.btnActionLibrary = document.getElementById('btn-action-library');
    elements.btnActionRemix = document.getElementById('btn-action-remix');
    elements.btnActionCopyPrompt = document.getElementById('btn-action-copy-prompt');
    
    elements.ambientLayerA = document.getElementById('ambient-layer-a');
    elements.ambientLayerB = document.getElementById('ambient-layer-b');
    
    elements.aiAssistantDrawer = document.getElementById('ai-assistant-drawer');
    elements.aiAssistantToggle = document.getElementById('ai-assistant-toggle');
    elements.assistantCloseBtn = document.getElementById('assistant-close-btn');
    elements.assistantNewChatBtn = document.getElementById('assistant-new-chat-btn');
    elements.assistantMessages = document.getElementById('assistant-messages-container');
    elements.assistantChatForm = document.getElementById('assistant-chat-form');
    elements.assistantChatInput = document.getElementById('assistant-chat-input');
}

/**
 * Friendly metadata mapping for profiles (clean, human-readable labels with inline SVGs)
 */
const PROFILE_FRIENDLY_INFO = {
    realism: {
        name: 'Фото',
        tagline: 'Реалистичные снимки',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 19a2 2 0 0 1-2 2H3a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h4l2-3h6l2 3h4a2 2 0 0 1 2 2z"></path><circle cx="12" cy="13" r="4"></circle></svg>`
    },
    anime: {
        name: 'Аниме',
        tagline: 'Аниме и иллюстрация',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20.84 4.61a5.5 5.5 0 0 0-7.78 0L12 5.67l-1.06-1.06a5.5 5.5 0 0 0-7.78 7.78l1.06 1.06L12 21.23l7.78-7.78 1.06-1.06a5.5 5.5 0 0 0 0-7.78z"></path></svg>`
    },
    universal: {
        name: 'Арт',
        tagline: 'Живопись и рисунки',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22c5.523 0 10-4.477 10-10S17.523 2 12 2 2 6.477 2 12s4.477 10 10 10z"></path><path d="M12 6a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"></path><path d="M6 12a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"></path><path d="M18 12a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"></path><path d="M12 18a1.5 1.5 0 1 1 0-3 1.5 1.5 0 0 1 0 3z"></path></svg>`
    },
    flux: {
        name: 'Универсал',
        tagline: 'Универсальные стили',
        icon: `<svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3v1m0 16v1m9-9h-1M4 12H3m15.364-6.364l-.707.707M6.343 17.657l-.707.707m0-12.728l.707.707m11.314 11.314l.707.707M12 8a4 4 0 1 0 0 8 4 4 0 0 0 0-8z"></path></svg>`
    },
};

/**
 * Bootstrap Create Mode Data
 */
async function initSimpleMode() {
    // Rebind DOM Element References to guarantee they are parsed correctly
    rebindDOMElements();

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

        // Dynamic update of ComfyUI connection status badge
        const badge = document.getElementById('comfy-status-badge');
        if (badge) {
            badge.classList.remove('status-unknown', 'status-connected', 'status-disconnected');
            if (data.comfyui_status && data.comfyui_status.online) {
                badge.classList.add('status-connected');
            } else {
                badge.classList.add('status-disconnected');
            }
        }

        // Set initial ambient background & start 5-minute rotation
        if (state.ambientImages.length > 0) {
            rotateAmbientImage();
            startAmbientRotationTimer();
        }

        // Render Style Selection Pills
        renderStylePills();
    } catch (err) {
        console.error('Failed to initialize Create Mode:', err);
        showError('Ошибка инициализации', 'Не удалось загрузить профили создания с сервера.');
    }
}

/**
 * Ambient Background Management with Preloading & 5-Minute Rotation
 */
function setAmbientImage(url) {
    if (!url) return;
    
    // Preload image before fading in to avoid blank frames
    const preloader = new Image();
    preloader.onload = () => {
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
    };
    preloader.src = url;
}

function rotateAmbientImage() {
    if (!state.ambientImages || state.ambientImages.length === 0) return;
    state.ambientIndex = (state.ambientIndex + 1) % state.ambientImages.length;
    const randomArt = state.ambientImages[state.ambientIndex];
    if (randomArt) {
        setAmbientImage(randomArt.preview_url || randomArt.thumbnail_url);
    }
}

function startAmbientRotationTimer() {
    if (state.ambientRotationTimer) {
        clearInterval(state.ambientRotationTimer);
    }
    state.ambientRotationTimer = setInterval(() => {
        rotateAmbientImage();
    }, AMBIENT_ROTATION_INTERVAL_MS);
}

/**
 * Render Clean Style Selection Pills
 */
function renderStylePills() {
    if (!elements.modelCardsContainer) return;
    elements.modelCardsContainer.innerHTML = '';

    state.profiles.forEach(profile => {
        const friendly = PROFILE_FRIENDLY_INFO[profile.id] || {
            name: profile.name,
            icon: '✨'
        };

        const pill = document.createElement('button');
        pill.type = 'button';
        pill.className = `style-pill-btn ${profile.id === state.activeProfileId ? 'active' : ''}`;
        pill.setAttribute('role', 'radio');
        pill.setAttribute('aria-checked', profile.id === state.activeProfileId ? 'true' : 'false');
        pill.dataset.profileId = profile.id;
        pill.title = profile.tagline || profile.description || friendly.name;

        pill.innerHTML = `
            <span class="style-pill-icon">${friendly.icon}</span>
            <span class="style-pill-name">${escapeHtml(friendly.name)}</span>
            <span class="style-pill-desc">${escapeHtml(friendly.tagline || profile.tagline || profile.description || '')}</span>
        `;

        pill.addEventListener('click', () => {
            selectProfile(profile.id);
        });

        elements.modelCardsContainer.appendChild(pill);
    });
}

function selectProfile(profileId) {
    state.activeProfileId = profileId;
    document.querySelectorAll('.style-pill-btn').forEach(btn => {
        const isActive = btn.dataset.profileId === profileId;
        btn.classList.toggle('active', isActive);
        btn.setAttribute('aria-checked', isActive ? 'true' : 'false');
    });
}

/**
 * Canvas Stage State Manager
 * States: 'idle' | 'generating' | 'result'
 */
function setCanvasState(mode, statusText = '') {
    if (!elements.canvasSurface) return;

    if (mode === 'idle') {
        elements.canvasIdleState.hidden = false;
        elements.canvasIdleState.classList.add('active');
        elements.canvasGeneratingState.hidden = true;
        elements.canvasGeneratingState.classList.remove('active');
        elements.canvasResultState.hidden = true;
        elements.canvasResultState.classList.remove('active');
        elements.canvasSurface.classList.remove('has-result');
    } else if (mode === 'generating') {
        elements.canvasIdleState.hidden = true;
        elements.canvasIdleState.classList.remove('active');
        elements.canvasGeneratingState.hidden = false;
        elements.canvasGeneratingState.classList.add('active');
        elements.canvasResultState.hidden = true;
        elements.canvasResultState.classList.remove('active');
        elements.canvasSurface.classList.remove('has-result');
        if (elements.canvasGeneratingStatus) {
            elements.canvasGeneratingStatus.textContent = statusText || 'Создаём изображение…';
        }
    } else if (mode === 'result') {
        elements.canvasIdleState.hidden = true;
        elements.canvasIdleState.classList.remove('active');
        elements.canvasGeneratingState.hidden = true;
        elements.canvasGeneratingState.classList.remove('active');
        elements.canvasResultState.hidden = false;
        elements.canvasResultState.classList.add('active');
        elements.canvasSurface.classList.add('has-result');
    }
}

/**
 * Generation Execution & Polling
 */
async function handleCreate() {
    if (state.currentRunId) return; // already generating

    const promptText = elements.promptInput ? elements.promptInput.value.trim() : '';
    if (!promptText && !state.referenceImageDataUrl) {
        elements.promptInput.focus();
        showError('Пустой запрос', 'Опишите изображение, которое хотите создать.');
        return;
    }

    dismissError();
    setButtonGeneratingState(true, 0, 'Запуск…');
    setCanvasState('generating', 'Подготовка генерации…');

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
            throw new Error(data.error || data.suggestion || 'Запрос на генерацию отклонён');
        }

        state.currentRunId = data.run_id;
        startPollingRun(data.run_id);
    } catch (err) {
        console.error('Generation failed:', err);
        setButtonGeneratingState(false);
        setCanvasState('idle');
        showError('Ошибка генерации', err.message);
    }
}

function startPollingRun(runId) {
    if (state.pollInterval) clearInterval(state.pollInterval);

    let progress = 10;
    const stages = [
        'Создаём композицию…',
        'Отрисовка деталей…',
        'Проработка света и текстур…',
        'Финальная обработка…'
    ];
    let stageIdx = 0;

    state.pollInterval = setInterval(async () => {
        try {
            const res = await fetch(`/api/simple/runs/${runId}`);
            if (!res.ok) return;
            const data = await res.json();

            if (data.status === 'running') {
                progress = Math.min(progress + 7, 92);
                stageIdx = Math.floor((progress / 100) * stages.length);
                const currentStage = stages[Math.min(stageIdx, stages.length - 1)];
                
                setButtonGeneratingState(true, progress, `${progress}%`);
                if (elements.canvasGeneratingStatus) {
                    elements.canvasGeneratingStatus.textContent = currentStage;
                }
            } else if (data.status === 'completed' || data.is_complete) {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.currentRunId = null;
                setButtonGeneratingState(false);
                handleGenerationSuccess(data.outputs || []);
            } else if (data.status === 'failed' || data.status === 'cancelled') {
                clearInterval(state.pollInterval);
                state.pollInterval = null;
                state.currentRunId = null;
                setButtonGeneratingState(false);
                setCanvasState('idle');
                showError('Ошибка создания', data.run?.error || 'Процесс был прерван в ComfyUI.');
            }
        } catch (e) {
            console.warn('Poll error:', e);
        }
    }, 800);
}

function setButtonGeneratingState(isGenerating, percent = 0, text = 'Создание…') {
    if (!elements.createButton) return;
    if (isGenerating) {
        elements.createButton.classList.add('running');
        elements.createProgressFill.style.width = `${percent}%`;
        elements.createProgressText.textContent = text;
    } else {
        elements.createButton.classList.remove('running');
        elements.createProgressFill.style.width = '0%';
        elements.createProgressText.textContent = 'Создание…';
    }
}

function handleGenerationSuccess(outputs) {
    if (!outputs || outputs.length === 0) {
        setCanvasState('idle');
        return;
    }

    const firstArt = outputs[0];
    state.lastGeneratedOutput = firstArt;

    // Display image on the dedicated Canvas
    if (elements.canvasResultImg) {
        elements.canvasResultImg.src = firstArt.preview_url || firstArt.thumbnail_url;
    }
    setCanvasState('result');

    // Instantly transition ambient background to this new artwork!
    const artUrl = firstArt.preview_url || firstArt.thumbnail_url;
    setAmbientImage(artUrl);
    // Reset the 5-minute timer so it stays for full 5 minutes before next rotation
    startAmbientRotationTimer();
}

/**
 * Setup Event Listeners
 */
function setupEventListeners() {
    // Create Button Trigger
    if (elements.createButton) {
        elements.createButton.addEventListener('click', handleCreate);
    }

    // Keyboard Shortcut: Ctrl + Enter to create
    window.addEventListener('keydown', (e) => {
        if ((e.ctrlKey || e.metaKey) && e.key === 'Enter') {
            e.preventDefault();
            handleCreate();
        }
    });

    // Prompt Textarea input handling & auto-height
    if (elements.promptInput) {
        elements.promptInput.addEventListener('input', () => {
            const hasText = elements.promptInput.value.trim().length > 0;
            if (elements.promptClearBtn) {
                elements.promptClearBtn.hidden = !hasText;
            }
            // Auto resize
            elements.promptInput.style.height = 'auto';
            elements.promptInput.style.height = `${Math.max(84, elements.promptInput.scrollHeight)}px`;
        });
    }

    // Clear prompt button
    if (elements.promptClearBtn) {
        elements.promptClearBtn.addEventListener('click', () => {
            if (elements.promptInput) {
                elements.promptInput.value = '';
                elements.promptInput.dispatchEvent(new Event('input'));
                elements.promptInput.focus();
            }
        });
    }

    // AI Improve Checkbox Toggle
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
        elements.aspectRatioSelector.querySelectorAll('.aspect-card').forEach(btn => {
            btn.addEventListener('click', () => {
                const ratio = btn.dataset.ratio;
                state.aspectRatio = ratio;
                elements.aspectRatioSelector.querySelectorAll('.aspect-card').forEach(b => {
                    const isActive = b.dataset.ratio === ratio;
                    b.classList.toggle('active', isActive);
                    b.setAttribute('aria-checked', isActive ? 'true' : 'false');
                });
            });
        });
    }

    // Reference Image File Upload
    if (elements.referenceFileInput) {
        elements.referenceFileInput.addEventListener('change', (e) => {
            const file = e.target.files?.[0];
            if (file) handleReferenceFile(file);
        });
    }

    // Reference Image Drag & Drop on prompt container
    if (elements.promptBoxContainer) {
        elements.promptBoxContainer.addEventListener('dragover', (e) => {
            e.preventDefault();
            elements.promptBoxContainer.style.borderColor = 'var(--accent, #14b8a6)';
        });
        elements.promptBoxContainer.addEventListener('dragleave', () => {
            elements.promptBoxContainer.style.borderColor = '';
        });
        elements.promptBoxContainer.addEventListener('drop', (e) => {
            e.preventDefault();
            elements.promptBoxContainer.style.borderColor = '';
            const file = e.dataTransfer?.files?.[0];
            if (file && file.type.startsWith('image/')) {
                handleReferenceFile(file);
            }
        });
    }

    // Remove Reference Image Button
    if (elements.removeReferenceBtn) {
        elements.removeReferenceBtn.addEventListener('click', () => {
            state.referenceImageDataUrl = null;
            state.referenceFileName = '';
            if (elements.referencePreviewContainer) elements.referencePreviewContainer.hidden = true;
            if (elements.referenceFileInput) elements.referenceFileInput.value = '';
        });
    }

    // Canvas Action: Download
    if (elements.btnActionDownload) {
        elements.btnActionDownload.addEventListener('click', () => {
            if (!state.lastGeneratedOutput) return;
            const url = state.lastGeneratedOutput.preview_url || state.lastGeneratedOutput.thumbnail_url;
            const a = document.createElement('a');
            a.href = url;
            a.download = state.lastGeneratedOutput.filename || `artwork-${Date.now()}.png`;
            document.body.appendChild(a);
            a.click();
            document.body.removeChild(a);
        });
    }

    // Canvas Action: Copy Prompt
    if (elements.btnActionCopyPrompt) {
        elements.btnActionCopyPrompt.addEventListener('click', async () => {
            const text = elements.promptInput ? elements.promptInput.value.trim() : '';
            if (text) {
                try {
                    await navigator.clipboard.writeText(text);
                    const originalTitle = elements.btnActionCopyPrompt.title;
                    elements.btnActionCopyPrompt.title = 'Скопировано!';
                    setTimeout(() => {
                        elements.btnActionCopyPrompt.title = originalTitle;
                    }, 2000);
                } catch (_) {}
            }
        });
    }

    // Canvas Action: Remix / Iterate
    if (elements.btnActionRemix) {
        elements.btnActionRemix.addEventListener('click', () => {
            if (elements.promptInput) {
                elements.promptInput.focus();
                elements.promptInput.select();
            }
        });
    }

    // Error Dismiss
    if (elements.errorDismissBtn) {
        elements.errorDismissBtn.addEventListener('click', dismissError);
    }

    // AI Assistant Drawer Toggle
    if (elements.aiAssistantToggle && elements.aiAssistantDrawer) {
        elements.aiAssistantToggle.addEventListener('click', () => {
            elements.aiAssistantDrawer.hidden = !elements.aiAssistantDrawer.hidden;
            if (!elements.aiAssistantDrawer.hidden && elements.assistantChatInput) {
                elements.assistantChatInput.focus();
            }
        });
    }

    if (elements.assistantCloseBtn && elements.aiAssistantDrawer) {
        elements.assistantCloseBtn.addEventListener('click', () => {
            elements.aiAssistantDrawer.hidden = true;
        });
    }

    // Quick suggestions in AI Assistant
    document.querySelectorAll('.quick-suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const promptText = chip.dataset.prompt;
            if (promptText && elements.promptInput) {
                elements.promptInput.value = promptText;
                elements.promptInput.dispatchEvent(new Event('input'));
                if (elements.aiAssistantDrawer) elements.aiAssistantDrawer.hidden = true;
            }
        });
    });

    // AI Assistant Chat Form
    if (elements.assistantChatForm) {
        elements.assistantChatForm.addEventListener('submit', handleAssistantChat);
    }
}

/**
 * Reference File Handling
 */
function handleReferenceFile(file) {
    if (!file || !file.type.startsWith('image/')) return;
    const reader = new FileReader();
    reader.onload = (e) => {
        state.referenceImageDataUrl = e.target.result;
        state.referenceFileName = file.name;
        if (elements.referencePreviewImg) {
            elements.referencePreviewImg.onload = () => {
                if (elements.referencePreviewContainer && state.referenceImageDataUrl) {
                    elements.referencePreviewContainer.hidden = false;
                }
            };
            elements.referencePreviewImg.onerror = () => {
                state.referenceImageDataUrl = null;
                state.referenceFileName = '';
                if (elements.referencePreviewContainer) {
                    elements.referencePreviewContainer.hidden = true;
                }
            };
            elements.referencePreviewImg.src = state.referenceImageDataUrl;
        }
        if (elements.referenceFileName) {
            elements.referenceFileName.textContent = file.name;
        }
    };
    reader.readAsDataURL(file);
}

/**
 * AI Assistant Chat Handler
 */
async function handleAssistantChat(e) {
    if (e) e.preventDefault();
    if (!elements.assistantChatInput) return;
    const text = elements.assistantChatInput.value.trim();
    if (!text) return;

    elements.assistantChatInput.value = '';
    appendAssistantMessage('user', text);

    const loadingId = appendAssistantMessage('assistant', 'Думаю…');

    try {
        const res = await fetch('/api/simple/assistant/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                message: text,
                current_prompt: elements.promptInput?.value || '',
                profile_id: state.activeProfileId,
                history: state.aiAssistantHistory,
            }),
        });

        const data = await res.json();
        const msgEl = document.getElementById(loadingId);
        if (data.reply) {
            if (msgEl) msgEl.textContent = data.reply;
            state.aiAssistantHistory.push({ role: 'user', content: text });
            state.aiAssistantHistory.push({ role: 'assistant', content: data.reply });

            if (data.suggested_prompt) {
                const applyBtn = document.createElement('button');
                applyBtn.className = 'btn btn-primary btn-sm';
                applyBtn.style.marginTop = '8px';
                applyBtn.textContent = 'Применить этот промпт';
                applyBtn.addEventListener('click', () => {
                    if (elements.promptInput) {
                        elements.promptInput.value = data.suggested_prompt;
                        elements.promptInput.dispatchEvent(new Event('input'));
                        if (elements.aiAssistantDrawer) elements.aiAssistantDrawer.hidden = true;
                    }
                });
                msgEl?.appendChild(applyBtn);
            }
        } else {
            if (msgEl) msgEl.textContent = 'Не удалось получить ответ от ассистента.';
        }
    } catch (err) {
        const msgEl = document.getElementById(loadingId);
        if (msgEl) msgEl.textContent = 'Ошибка связи с ИИ-помощником.';
    }
}

function appendAssistantMessage(role, text) {
    const id = `msg-${Date.now()}-${Math.random().toString(36).substr(2, 4)}`;
    const msg = document.createElement('div');
    msg.id = id;
    msg.className = `assistant-message ${role === 'user' ? 'assistant-message-user' : 'assistant-message-system'}`;
    msg.textContent = text;
    elements.assistantMessages?.appendChild(msg);
    if (elements.assistantMessages) {
        elements.assistantMessages.scrollTop = elements.assistantMessages.scrollHeight;
    }
    return id;
}

/**
 * Error Handling Utilities
 */
function showError(title, message, techDetails = '') {
    if (!elements.errorBanner) return;
    if (elements.errorTitle) elements.errorTitle.textContent = title;
    if (elements.errorMessage) elements.errorMessage.textContent = message;
    if (elements.errorTechText && techDetails) {
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
        .replace(/"/g, '&quot;');
}

// Auto initialize on DOM ready
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', initSimpleMode);
} else {
    initSimpleMode();
}
