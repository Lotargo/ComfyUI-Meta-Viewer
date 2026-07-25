const bootstrapScript = document.querySelector('script[data-ai-settings-main]');
const mainModuleUrl = bootstrapScript?.dataset.aiSettingsMain;
const originalFetch = window.fetch;
const pendingRequests = new Set();

function trackRequest(request) {
    const tracked = request
        .then(response => response.clone().arrayBuffer().catch(() => undefined))
        .catch(() => undefined)
        .finally(() => pendingRequests.delete(tracked));
    pendingRequests.add(tracked);
    return request;
}

function waitForNetworkIdle({ quietMs = 80, timeoutMs = 4000 } = {}) {
    return new Promise(resolve => {
        const startedAt = performance.now();
        let idleSince = null;

        const check = () => {
            const now = performance.now();
            if (pendingRequests.size === 0) {
                idleSince ??= now;
                if (now - idleSince >= quietMs) {
                    resolve();
                    return;
                }
            } else {
                idleSince = null;
            }

            if (now - startedAt >= timeoutMs) {
                resolve();
                return;
            }
            window.setTimeout(check, 25);
        };

        check();
    });
}

function waitForDomQuiet(root, { quietMs = 80, timeoutMs = 1200 } = {}) {
    return new Promise(resolve => {
        let quietTimer;
        const timeoutTimer = window.setTimeout(finish, timeoutMs);
        const observer = new MutationObserver(scheduleFinish);

        function finish() {
            window.clearTimeout(quietTimer);
            window.clearTimeout(timeoutTimer);
            observer.disconnect();
            resolve();
        }

        function scheduleFinish() {
            window.clearTimeout(quietTimer);
            quietTimer = window.setTimeout(finish, quietMs);
        }

        observer.observe(root, {
            childList: true,
            subtree: true,
            attributes: true,
            characterData: true,
        });
        scheduleFinish();
    });
}

function waitForTwoFrames() {
    return new Promise(resolve => {
        requestAnimationFrame(() => requestAnimationFrame(resolve));
    });
}

async function bootstrap() {
    window.fetch = (...args) => trackRequest(originalFetch.apply(window, args));

    try {
        if (!mainModuleUrl) throw new Error('AI settings module URL is missing.');
        await import(mainModuleUrl);
        await waitForNetworkIdle();
        await Promise.allSettled([
            document.fonts?.ready ?? Promise.resolve(),
            waitForDomQuiet(document.body),
        ]);
    } catch (error) {
        console.error('Failed to initialize AI settings.', error);
    } finally {
        window.fetch = originalFetch;
        await waitForTwoFrames();
        document.body.classList.remove('ui-booting');
    }
}

void bootstrap();
