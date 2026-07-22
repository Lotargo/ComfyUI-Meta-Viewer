/**
 * ComfyUI Integration & Process Control Frontend Controller
 */
document.addEventListener('DOMContentLoaded', () => {
    // Elements
    const statusPill = document.getElementById('runtime-status-pill');
    const statusText = document.getElementById('runtime-status-text');
    const statusDetail = document.getElementById('runtime-status-detail');

    const statMode = document.getElementById('stat-mode');
    const statStatus = document.getElementById('stat-status');
    const statPid = document.getElementById('stat-pid');
    const statEndpoint = document.getElementById('stat-endpoint');
    const statQueue = document.getElementById('stat-queue');

    const btnStart = document.getElementById('btn-start');
    const btnStop = document.getElementById('btn-stop');
    const btnRestart = document.getElementById('btn-restart');
    const btnInterrupt = document.getElementById('btn-interrupt');
    const btnGenScript = document.getElementById('btn-gen-script');
    const btnRefreshStatus = document.getElementById('refresh-status');

    const installPathInput = document.getElementById('install-path');
    const hostInput = document.getElementById('host-input');
    const portInput = document.getElementById('port-input');
    const extraArgsInput = document.getElementById('extra-args-input');
    const customPythonInput = document.getElementById('custom-python-input');

    const btnDetectPath = document.getElementById('btn-detect-path');
    const btnSaveConfig = document.getElementById('btn-save-config');

    const detectionCard = document.getElementById('detection-result-card');
    const detectionBadge = document.getElementById('detection-badge');
    const detectionSummary = document.getElementById('detection-summary');
    const detectionDetails = document.getElementById('detection-details');

    const systemStatsPanel = document.getElementById('system-stats-panel');
    const logsConsole = document.getElementById('logs-console');
    const autoScrollLogs = document.getElementById('autoscroll-logs');
    const btnClearLogs = document.getElementById('btn-clear-logs');
    const btnRefreshLogs = document.getElementById('btn-refresh-logs');
    const toastContainer = document.getElementById('toast-container');

    let pollInterval = null;

    // Toast Notification helper
    function showToast(message, type = 'info') {
        const toast = document.createElement('div');
        toast.className = `toast toast-${type}`;
        toast.style.cssText = `
            padding: 0.75rem 1.25rem;
            border-radius: 8px;
            background: ${type === 'error' ? '#2d1517' : type === 'success' ? '#122519' : '#161b22'};
            border: 1px solid ${type === 'error' ? '#f85149' : type === 'success' ? '#3fb950' : '#30363d'};
            color: ${type === 'error' ? '#ff7b72' : type === 'success' ? '#56d364' : '#e6edf3'};
            font-size: 0.875rem;
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            margin-bottom: 0.5rem;
            transition: opacity 0.3s;
        `;
        toast.textContent = message;
        toastContainer.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    }

    // Load initial configuration
    async function loadConfig() {
        try {
            const resp = await fetch('/api/comfyui/config');
            if (resp.ok) {
                const cfg = await resp.json();
                if (cfg.install_path) installPathInput.value = cfg.install_path;
                if (cfg.host) hostInput.value = cfg.host;
                if (cfg.port) portInput.value = cfg.port;
                if (cfg.extra_args) extraArgsInput.value = cfg.extra_args;
                if (cfg.custom_python) customPythonInput.value = cfg.custom_python;

                if (cfg.install_path) {
                    runDetection(cfg.install_path, cfg.custom_python);
                }
            }
        } catch (err) {
            console.error('Failed to load configuration:', err);
        }
    }

    // Run directory structure detection
    async function runDetection(path, customPython = null) {
        if (!path) return;
        try {
            const resp = await fetch('/api/comfyui/detect', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    path: path,
                    custom_python: customPython || customPythonInput.value.trim()
                })
            });
            const data = await resp.json();
            renderDetectionResult(data);
        } catch (err) {
            showToast('Failed to run installation detection', 'error');
        }
    }

    function renderDetectionResult(data) {
        detectionCard.hidden = false;
        if (data.is_valid) {
            detectionBadge.className = 'badge badge-success';
            detectionBadge.textContent = data.is_portable ? 'Portable Windows' : 'Standard Installation';
            detectionSummary.textContent = 'Valid ComfyUI installation detected';
            detectionDetails.textContent = [
                `Comfy Directory: ${data.comfy_dir}`,
                `Main Entry Point: ${data.main_py}`,
                `Python Interpreter: ${data.interpreter}`
            ].join('\n');
        } else {
            detectionBadge.className = 'badge badge-error';
            detectionBadge.textContent = 'Invalid';
            detectionSummary.textContent = data.error || 'Structure not recognized';
            detectionDetails.textContent = `Path: ${data.root_path || installPathInput.value}\nError: ${data.error || 'Unknown'}`;
        }
    }

    // Save configuration
    async function saveConfig() {
        const payload = {
            install_path: installPathInput.value.trim(),
            host: hostInput.value.trim() || '127.0.0.1',
            port: parseInt(portInput.value, 10) || 8188,
            extra_args: extraArgsInput.value.trim(),
            custom_python: customPythonInput.value.trim()
        };

        try {
            const resp = await fetch('/api/comfyui/config', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(payload)
            });
            if (resp.ok) {
                showToast('Configuration saved successfully', 'success');
                runDetection(payload.install_path, payload.custom_python);
            } else {
                showToast('Failed to save configuration', 'error');
            }
        } catch (err) {
            showToast('Network error saving configuration', 'error');
        }
    }

    // Fetch latest status
    async function updateStatus() {
        try {
            const resp = await fetch('/api/comfyui/status');
            if (!resp.ok) return;
            const data = await resp.json();

            // Update Status Pill
            const status = (data.status || 'stopped').toLowerCase();
            statusPill.className = `status-pill status-${status}`;
            statusText.textContent = status.charAt(0).toUpperCase() + status.slice(1);

            if (data.mode === 'managed') {
                statusDetail.textContent = data.pid ? `PID: ${data.pid}` : 'Managed process';
            } else if (data.mode === 'external') {
                statusDetail.textContent = 'External API connected';
            } else {
                statusDetail.textContent = data.last_error ? `Error: ${data.last_error}` : 'No process running';
            }

            // Update Cards
            statMode.textContent = data.mode ? data.mode.toUpperCase() : 'NONE';
            statStatus.textContent = data.status ? data.status.toUpperCase() : 'STOPPED';
            statPid.textContent = data.pid ? data.pid : '—';
            statEndpoint.textContent = `http://${data.host || '127.0.0.1'}:${data.port || 8188}`;

            if (data.queue_info) {
                const total = data.queue_info.total_remaining || 0;
                statQueue.textContent = `${total} ${total === 1 ? 'task' : 'tasks'} (${data.queue_info.is_busy ? 'Busy' : 'Idle'})`;
            } else {
                statQueue.textContent = data.online ? 'Idle' : 'Offline';
            }

            // Update Action Buttons State
            btnStart.disabled = data.mode === 'managed' && (data.status === 'ready' || data.status === 'busy' || data.status === 'starting');
            btnStop.disabled = data.mode !== 'managed';
            btnRestart.disabled = !data.installation || !data.installation.is_valid;
            btnInterrupt.disabled = !data.online;

            // System stats rendering
            renderSystemStats(data.system_stats);

            // Fetch logs if managed
            if (data.mode === 'managed') {
                fetchLogs();
            }
        } catch (err) {
            console.error('Failed to fetch status:', err);
        }
    }

    function renderSystemStats(stats) {
        if (!stats) {
            systemStatsPanel.innerHTML = '<p class="no-stats-msg">System statistics unavailable (ComfyUI API is offline or starting).</p>';
            return;
        }

        const system = stats.system || {};
        const devices = stats.devices || [];

        let html = `
            <div style="display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr)); gap: 1rem;">
                <div><strong>OS Platform:</strong> ${system.os || 'Unknown'} (${system.python_version || 'Python'})</div>
                <div><strong>ComfyUI Version:</strong> ${system.embedded_python ? 'Embedded Python' : 'Standard Python'}</div>
            </div>
        `;

        if (devices.length > 0) {
            html += '<div style="margin-top: 1rem; border-top: 1px solid #21262d; padding-top: 0.75rem;"><strong>Devices:</strong><ul style="margin-top: 0.5rem; padding-left: 1.2rem;">';
            devices.forEach(dev => {
                const name = dev.name || 'GPU Device';
                const vramTotal = dev.vram_total ? (dev.vram_total / (1024 * 1024 * 1024)).toFixed(2) + ' GB' : 'N/A';
                const vramFree = dev.vram_free ? (dev.vram_free / (1024 * 1024 * 1024)).toFixed(2) + ' GB' : 'N/A';
                html += `<li><strong>${name}</strong> — Total VRAM: ${vramTotal}, Free: ${vramFree}</li>`;
            });
            html += '</ul></div>';
        }

        systemStatsPanel.innerHTML = html;
    }

    // Fetch Logs
    async function fetchLogs() {
        try {
            const resp = await fetch('/api/comfyui/logs?lines=300');
            if (resp.ok) {
                const data = await resp.json();
                const logs = data.logs || [];
                if (logs.length > 0) {
                    logsConsole.innerHTML = `<code>${escapeHtml(logs.join('\n'))}</code>`;
                    if (autoScrollLogs.checked) {
                        const container = logsConsole.parentElement;
                        container.scrollTop = container.scrollHeight;
                    }
                }
            }
        } catch (err) {
            console.error('Failed to fetch logs:', err);
        }
    }

    function escapeHtml(text) {
        return text.replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;');
    }

    // Process control actions
    btnStart.addEventListener('click', async () => {
        btnStart.disabled = true;
        showToast('Starting ComfyUI process...', 'info');
        try {
            const resp = await fetch('/api/comfyui/start', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    install_path: installPathInput.value.trim(),
                    host: hostInput.value.trim(),
                    port: parseInt(portInput.value, 10),
                    extra_args: extraArgsInput.value.trim(),
                    custom_python: customPythonInput.value.trim()
                })
            });
            const data = await resp.json();
            if (resp.ok) {
                showToast('ComfyUI process started!', 'success');
                updateStatus();
            } else {
                showToast(`Failed to start: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast('Network error launching ComfyUI', 'error');
        } finally {
            btnStart.disabled = false;
        }
    });

    btnStop.addEventListener('click', async () => {
        btnStop.disabled = true;
        showToast('Stopping ComfyUI process...', 'info');
        try {
            const resp = await fetch('/api/comfyui/stop', { method: 'POST' });
            if (resp.ok) {
                showToast('ComfyUI process stopped', 'success');
                updateStatus();
            } else {
                const data = await resp.json();
                showToast(`Failed to stop: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast('Network error stopping ComfyUI', 'error');
        } finally {
            btnStop.disabled = false;
        }
    });

    btnRestart.addEventListener('click', async () => {
        showToast('Restarting ComfyUI process...', 'info');
        try {
            const resp = await fetch('/api/comfyui/restart', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    install_path: installPathInput.value.trim(),
                    host: hostInput.value.trim(),
                    port: parseInt(portInput.value, 10),
                    extra_args: extraArgsInput.value.trim(),
                    custom_python: customPythonInput.value.trim()
                })
            });
            const data = await resp.json();
            if (resp.ok) {
                showToast('ComfyUI process restarted!', 'success');
                updateStatus();
            } else {
                showToast(`Failed to restart: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast('Network error restarting ComfyUI', 'error');
        }
    });

    btnInterrupt.addEventListener('click', async () => {
        try {
            const resp = await fetch('/api/comfyui/interrupt', { method: 'POST' });
            const data = await resp.json();
            if (resp.ok && data.success) {
                showToast('Interrupt signal sent to ComfyUI API', 'success');
            } else {
                showToast(`Interrupt failed: ${data.error || 'Unknown error'}`, 'error');
            }
        } catch (err) {
            showToast('Network error interrupting execution', 'error');
        }
    });

    btnGenScript.addEventListener('click', async () => {
        try {
            const resp = await fetch('/api/comfyui/launcher', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    install_path: installPathInput.value.trim(),
                    host: hostInput.value.trim(),
                    port: parseInt(portInput.value, 10),
                    extra_args: extraArgsInput.value.trim(),
                    custom_python: customPythonInput.value.trim()
                })
            });
            const data = await resp.json();
            if (resp.ok) {
                showToast(`Launcher script saved to: ${data.script_path}`, 'success');
            } else {
                showToast(`Script generation failed: ${data.error}`, 'error');
            }
        } catch (err) {
            showToast('Network error generating launcher script', 'error');
        }
    });

    btnDetectPath.addEventListener('click', () => {
        const path = installPathInput.value.trim();
        if (!path) {
            showToast('Please enter an installation path', 'error');
            return;
        }
        runDetection(path);
    });

    btnSaveConfig.addEventListener('click', saveConfig);
    btnRefreshStatus.addEventListener('click', updateStatus);

    btnClearLogs.addEventListener('click', () => {
        logsConsole.innerHTML = '<code>[CMV] Console logs cleared.</code>';
    });

    btnRefreshLogs.addEventListener('click', fetchLogs);

    // Initial setup
    loadConfig();
    updateStatus();

    // Start polling status
    pollInterval = setInterval(updateStatus, 3000);
});
