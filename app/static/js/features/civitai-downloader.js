/* Civitai model downloader — Create editor. */
(() => {
    const $ = (id) => document.getElementById(id);

    const dialog = $("civitai-downloader-dialog");
    if (!dialog) return;

    const openBtn = $("civitai-downloader-open");
    const closeBtn = $("civitai-dialog-close");
    const headerStatusText = $("civitai-downloader-status-text");
    const headerStatusDetail = $("civitai-downloader-status-detail");
    const headerBadge = $("civitai-downloader-badge");

    const form = $("civitai-search-form");
    const queryEl = $("civitai-query");
    const typeEl = $("civitai-type");
    const sortEl = $("civitai-sort");
    const nsfwEl = $("civitai-nsfw");

    const tabBrowse = $("civitai-tab-browse");
    const tabDownloads = $("civitai-tab-downloads");
    const panelBrowse = $("civitai-panel-browse");
    const panelDownloads = $("civitai-panel-downloads");
    const downloadCountEl = $("civitai-download-count");

    const resultCountEl = $("civitai-result-count");
    const resultStatusEl = $("civitai-result-status");
    const resultsEl = $("civitai-results");
    const emptyEl = $("civitai-empty");
    const prevPageBtn = $("civitai-prev-page");
    const nextPageBtn = $("civitai-next-page");
    const pageInfoEl = $("civitai-page-info");

    const downloadsEl = $("civitai-downloads");

    let filters = { model_types: [], folders: [], folder_for_type: {} };
    let searchState = { query: "", types: "", sort: "Most Downloaded", nsfw: true, page: 1, pages: 1, cursor: "", next_cursor: "", using_cursor: false, cursor_stack: [], loading: false };
    let detailsCache = new Map();
    let downloads = [];
    let lastKnownCompleted = new Set();
    let pollTimer = null;
    let downloadInFlight = new Set();

    /* ------------------------------------------------------------------ utils */

    function escapeHtml(value) {
        return String(value == null ? "" : value)
            .replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;").replace(/'/g, "&#39;");
    }

    function formatBytes(value) {
        const bytes = Number(value) || 0;
        if (bytes <= 0) return "—";
        const units = ["B", "KB", "MB", "GB", "TB"];
        let size = bytes;
        let unit = 0;
        while (size >= 1024 && unit < units.length - 1) { size /= 1024; unit += 1; }
        return `${size >= 100 ? Math.round(size) : size.toFixed(1)} ${units[unit]}`;
    }

    function formatCount(value) {
        const n = Number(value) || 0;
        if (n >= 1_000_000) return `${(n / 1_000_000).toFixed(1)}M`;
        if (n >= 1_000) return `${(n / 1_000).toFixed(1)}k`;
        return String(n);
    }

    async function requestJson(url, options = {}) {
        const response = await fetch(url, {
            headers: { "Content-Type": "application/json", ...(options.headers || {}) },
            ...options,
        });
        let data = null;
        try { data = await response.json(); } catch (_) { /* no body */ }
        if (!response.ok) {
            const message = (data && (data.error || data.message)) || `Request failed (${response.status})`;
            throw new Error(message);
        }
        return data;
    }

    function showToast(message, type = 'success') {
        const container = $("toast-container");
        if (!container) return;
        const toast = document.createElement("div");
        toast.className = `editor-toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);
        window.setTimeout(() => toast.remove(), 4200);
    }

    function dispatchModelsUpdated() {
        window.dispatchEvent(new CustomEvent("civitai:models-updated"));
    }

    /* ---------------------------------------------------------------- filtering */

    function currentPayload() {
        const payload = {
            query: searchState.query,
            types: searchState.types,
            sort: searchState.sort,
            nsfw: searchState.nsfw,
            page: searchState.page,
            limit: 20,
        };
        if (searchState.using_cursor && searchState.cursor) {
            payload.cursor = searchState.cursor;
        }
        return payload;
    }

    async function runSearch() {
        if (searchState.loading) return;
        searchState.loading = true;
        resultStatusEl.textContent = "Searching Civitai…";
        try {
            const data = await requestJson("/api/editor/models/civitai/search", {
                method: "POST",
                body: JSON.stringify(currentPayload()),
            });
            searchState.using_cursor = Boolean(data.using_cursor);
            searchState.next_cursor = data.next_cursor || "";
            if (!searchState.using_cursor) {
                searchState.page = Number(data.current_page) || 1;
                searchState.pages = Number(data.total_pages) || 1;
            }
            renderResults(data.items || [], data.total_items || 0);
        } catch (error) {
            resultStatusEl.textContent = "";
            renderError(error.message);
        } finally {
            searchState.loading = false;
            updatePagination();
        }
    }

    function renderResults(items, total) {
        emptyEl.hidden = items.length > 0;
        resultCountEl.textContent = total > 0 ? `${total.toLocaleString()} models` : "";
        resultStatusEl.textContent = "";
        resultsEl.innerHTML = items.map((item) => renderCard(item)).join("");
        updatePagination();
        attachCardListeners();
    }

    function renderError(message) {
        emptyEl.hidden = false;
        emptyEl.innerHTML = `<p>${escapeHtml(message)}</p><small>Check your connection and retry.</small>`;
        resultCountEl.textContent = "";
        resultsEl.innerHTML = "";
        prevPageBtn.disabled = true;
        nextPageBtn.disabled = true;
        pageInfoEl.textContent = "";
    }

    function updatePagination() {
        if (searchState.using_cursor) {
            prevPageBtn.disabled = searchState.cursor_stack.length === 0 || searchState.loading;
            nextPageBtn.disabled = !searchState.next_cursor || searchState.loading;
            pageInfoEl.textContent = searchState.cursor_stack.length + 1 > 0
                ? `Page ${searchState.cursor_stack.length + 1}`
                : "";
        } else {
            prevPageBtn.disabled = searchState.page <= 1 || searchState.loading;
            nextPageBtn.disabled = searchState.page >= searchState.pages || searchState.loading;
            pageInfoEl.textContent = searchState.pages > 0 ? `Page ${searchState.page} of ${searchState.pages}` : "";
        }
    }

    /* ------------------------------------------------------------------- cards */

    function thumbnailFor(item) {
        const image = (item.images || []).find((img) => img && img.url && !img.nsfw) || (item.images || [])[0];
        if (!image) return null;
        const ratio = image.width && image.height ? image.width / image.height : 4 / 3;
        return {
            src: image.proxy_url || image.url || "",
            ratio: `${Math.max(ratio, 4 / 3)}`,
        };
    }

    function folderForType(modelType) {
        const mapped = filters.folder_for_type && filters.folder_for_type[modelType];
        return mapped || (filters.folders && filters.folders[0]) || "checkpoints";
    }

    function folderOptions(selected) {
        return (filters.folders || [])
            .map((folder) => `<option value="${escapeHtml(folder)}"${folder === selected ? " selected" : ""}>${escapeHtml(folder)}</option>`)
            .join("");
    }

    function renderCard(item) {
        const thumb = thumbnailFor(item);
        const stats = item.stats || {};
        const defaultFolder = folderForType(item.type);
        const primaryLabel = item.version_name || "Version";
        const thumbHtml = thumb && thumb.src
            ? `<img class="civitai-card-thumb" src="${escapeHtml(thumb.src)}" alt="" loading="lazy" style="aspect-ratio: ${thumb.ratio}">`
            : `<div class="civitai-card-thumb" aria-hidden="true" style="aspect-ratio: 4/3"></div>`;
        return `
            <article class="civitai-card" data-model-id="${item.id}" data-model-name="${escapeHtml(item.name)}" data-model-type="${escapeHtml(item.type)}">
                ${thumbHtml}
                <div class="civitai-card-body">
                    <h4 class="civitai-card-title">${escapeHtml(item.name)}</h4>
                    <p class="civitai-card-meta">
                        ${escapeHtml(item.type || "model")}
                        ${item.creator ? ` · ${escapeHtml(item.creator)}` : ""}
                        ${stats.rating ? ` · ⭐ ${stats.rating}` : ""}
                        ${stats.download_count ? ` · ${formatCount(stats.download_count)} downloads` : ""}
                    </p>
                    <div class="civitai-card-actions">
                        <select class="civitai-folder-select" aria-label="Target folder">
                            ${folderOptions(defaultFolder)}
                        </select>
                        <select class="civitai-version-select" aria-label="Version">
                            <option value="${item.version_id}" data-name="${escapeHtml(primaryLabel)}"
                                data-filename="${escapeHtml(item.file_name)}" data-size="${item.file_size_bytes}" data-type="">
                                ${escapeHtml(primaryLabel)} · ${formatBytes(item.file_size_bytes)}
                            </option>
                        </select>
                        <button class="civitai-versions-toggle btn btn-ghost btn-sm" type="button" title="Load more versions">Versions</button>
                        <button class="civitai-download-btn btn btn-sm btn-primary" type="button">Download</button>
                    </div>
                </div>
            </article>`;
    }

    function attachCardListeners() {
        resultsEl.querySelectorAll(".civitai-card").forEach((card) => {
            const modelId = Number(card.dataset.modelId);
            const toggle = card.querySelector(".civitai-versions-toggle");
            toggle.addEventListener("click", () => loadVersions(card, modelId));
            const downloadBtn = card.querySelector(".civitai-download-btn");
            downloadBtn.addEventListener("click", () => startDownload(card, modelId));
        });
    }

    async function loadVersions(card, modelId) {
        const select = card.querySelector(".civitai-version-select");
        if (select.dataset.loading) return;
        select.dataset.loading = "1";
        const toggle = card.querySelector(".civitai-versions-toggle");
        toggle.disabled = true;
        toggle.textContent = "Loading…";
        try {
            if (!detailsCache.has(modelId)) {
                detailsCache.set(modelId, await requestJson(`/api/editor/models/civitai/details/${modelId}`));
            }
            const details = detailsCache.get(modelId);
            const options = [];
            for (const version of details.versions || []) {
                const file = (version.files || []).find((f) => f.primary) || (version.files || [])[0];
                if (!file) continue;
                options.push(`<option value="${version.id}" data-name="${escapeHtml(version.name)}"
                    data-filename="${escapeHtml(file.name)}" data-size="${file.size_bytes}" data-type="${escapeHtml(file.type)}">
                    ${escapeHtml(version.name)}${version.base_model ? ` · ${escapeHtml(version.base_model)}` : ""} · ${formatBytes(file.size_bytes)}
                </option>`);
            }
            if (options.length) {
                select.innerHTML = options.join("");
            } else {
                showToast("No downloadable files for this model.", "error");
            }
            toggle.textContent = "Versions";
        } catch (error) {
            toggle.textContent = "Versions";
            showToast(error.message, "error");
        } finally {
            toggle.disabled = false;
            delete select.dataset.loading;
        }
    }

    async function startDownload(card, modelId) {
        const folder = card.querySelector(".civitai-folder-select").value;
        const versionOption = card.querySelector(".civitai-version-select").selectedOptions[0];
        if (!versionOption) {
            showToast("No file selected for download.", "error");
            return;
        }
        const key = `${modelId}:${versionOption.value}`;
        if (downloadInFlight.has(key)) return;
        downloadInFlight.add(key);
        const button = card.querySelector(".civitai-download-btn");
        const original = button.textContent;
        button.disabled = true;
        button.textContent = "Queueing…";
        try {
            const row = await requestJson("/api/editor/models/civitai/download", {
                method: "POST",
                body: JSON.stringify({
                    model_id: modelId,
                    model_name: card.dataset.modelName || "",
                    version_id: Number(versionOption.value),
                    version_name: versionOption.dataset.name || "",
                    folder,
                    filename: versionOption.dataset.filename || "",
                    file_type: versionOption.dataset.type || "",
                    file_size_bytes: Number(versionOption.dataset.size) || 0,
                }),
            });
            showToast("Download queued.");
            updateHeaderStatus();
            await refreshDownloads();
        } catch (error) {
            showToast(error.message, "error");
        } finally {
            downloadInFlight.delete(key);
            button.disabled = false;
            button.textContent = original;
        }
    }

    /* ---------------------------------------------------------------- downloads */

    function activeDownloadCount() {
        return downloads.filter((d) => d.status === "queued" || d.status === "downloading").length;
    }

    function terminalDownloadCount() {
        return downloads.filter((d) => d.status === "completed").length;
    }

    async function refreshDownloads() {
        let data;
        try {
            data = await requestJson("/api/editor/models/civitai/downloads");
        } catch (_) {
            return;
        }
        downloads = data.items || [];
        renderDownloads();
        updateHeaderStatus();
        updatePolling();
        notifyNewCompleted();
    }

    function renderDownloads() {
        const count = activeDownloadCount();
        downloadCountEl.textContent = count > 0 ? String(count) : "";
        downloadCountEl.hidden = count === 0;

        if (!downloads.length) {
            downloadsEl.innerHTML = `<div class="civitai-empty"><p>No downloads yet.</p><small>Queued downloads will show up here with live progress.</small></div>`;
            return;
        }
        downloadsEl.innerHTML = downloads.map(renderDownloadItem).join("");
        attachDownloadListeners();
    }

    function renderDownloadItem(row) {
        const status = row.status;
        const progress = status === "completed" ? 100 : Math.max(0, Number(row.progress) || 0);
        const cancelled = status === "cancelled";
        const failed = status === "failed";
        const isActive = status === "queued" || status === "downloading";
        const showControls = isActive || failed || status === "completed";
        const folderBadge = `<span class="civitai-badge status-${escapeHtml(status)}">${escapeHtml(status)}</span>`;
        const fileName = row.filename || "file";
        const fileDisplay = `${escapeHtml(row.civitai_model_name || fileName)}${row.version_name ? ` — ${escapeHtml(row.version_name)}` : ""}`;
        const sizeText = row.file_size_bytes
            ? `${formatBytes(row.downloaded_bytes)} / ${formatBytes(row.file_size_bytes)}`
            : formatBytes(row.downloaded_bytes);
        return `
            <div class="civitai-download-item" data-download-id="${row.id}">
                <div class="civitai-download-head">
                    <div>
                        <h4 class="civitai-download-name">${fileDisplay}</h4>
                        <p class="civitai-download-sub">${escapeHtml(row.folder)} / ${escapeHtml(fileName)} · ${sizeText}</p>
                    </div>
                    <div class="civitai-download-actions">
                        ${folderBadge}
                        ${showControls ? `<button class="btn btn-ghost btn-sm civitai-download-action" type="button" data-action="${isActive ? "cancel" : "delete"}">${isActive ? "Cancel" : "Remove"}</button>` : ""}
                    </div>
                </div>
                ${isActive ? `
                    <div class="civitai-download-track">
                        <div class="civitai-download-bar"><div class="civitai-download-bar-fill" style="width:${progress}%"></div></div>
                        <span class="civitai-download-percent">${progress.toFixed(0)}%</span>
                    </div>` : ""}
                ${failed && row.error ? `<p class="civitai-download-error">${escapeHtml(row.error)}</p>` : ""}
            </div>`;
    }

    function attachDownloadListeners() {
        downloadsEl.querySelectorAll(".civitai-download-action").forEach((button) => {
            button.addEventListener("click", async () => {
                const item = button.closest(".civitai-download-item");
                const id = Number(item.dataset.downloadId);
                const action = button.dataset.action;
                button.disabled = true;
                try {
                    if (action === "cancel") {
                        await requestJson(`/api/editor/models/civitai/downloads/${id}/cancel`, { method: "POST" });
                        showToast("Download cancelled.");
                    } else {
                        await requestJson(`/api/editor/models/civitai/downloads/${id}`, { method: "DELETE" });
                        showToast("Download removed.");
                    }
                    await refreshDownloads();
                } catch (error) {
                    showToast(error.message, "error");
                    button.disabled = false;
                }
            });
        });
    }

    function notifyNewCompleted() {
        for (const row of downloads) {
            if (row.status === "completed" && !lastKnownCompleted.has(row.id)) {
                lastKnownCompleted.add(row.id);
                showToast(`${row.civitai_model_name || row.filename} downloaded.`);
                dispatchModelsUpdated();
            }
        }
    }

    function updatePolling() {
        const active = activeDownloadCount() > 0;
        if (active && !pollTimer) {
            pollTimer = setInterval(refreshDownloads, 2000);
        } else if (!active && pollTimer) {
            clearInterval(pollTimer);
            pollTimer = null;
        }
    }

    /* ---------------------------------------------------------------- header status */

    function updateHeaderStatus() {
        const active = activeDownloadCount();
        if (active > 0) {
            headerStatusDetail.textContent = `${active} active download${active > 1 ? "s" : ""}`;
            headerBadge.hidden = false;
            headerBadge.textContent = String(active);
        } else {
            const completed = terminalDownloadCount();
            headerStatusDetail.textContent = completed > 0 ? `${completed} completed` : "Civitai downloads";
            headerBadge.hidden = true;
            headerBadge.textContent = "";
        }
    }

    /* ------------------------------------------------------------------ dialog open */

    async function openDialog() {
        dialog.showModal();
        openBtn.setAttribute("aria-expanded", "true");
        switchPanel("downloads");
        try {
            const data = await requestJson("/api/editor/models/civitai/filters");
            filters = data;
            typeEl.innerHTML = `<option value="">All types</option>` + (data.model_types || [])
                .map((t) => `<option value="${escapeHtml(t)}">${escapeHtml(t)}</option>`)
                .join("");
            await refreshDownloads();
        } catch (error) {
            showToast(error.message, "error");
        }
    }

    function closeDialog() {
        dialog.close();
        openBtn.setAttribute("aria-expanded", "false");
    }

    function switchPanel(name) {
        const browse = name === "browse";
        tabBrowse.classList.toggle("active", browse);
        tabDownloads.classList.toggle("active", !browse);
        tabBrowse.setAttribute("aria-selected", String(browse));
        tabDownloads.setAttribute("aria-selected", String(!browse));
        panelBrowse.hidden = !browse;
        panelDownloads.hidden = browse;
        if (browse && !searchState.query) {
            queryEl.focus();
        }
    }

    /* ------------------------------------------------------------------------ wiring */

    openBtn.addEventListener("click", openDialog);
    closeBtn.addEventListener("click", closeDialog);
    dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDialog();
    });
    dialog.addEventListener("click", (event) => {
        if (event.target === dialog) closeDialog();
    });

    tabBrowse.addEventListener("click", () => switchPanel("browse"));
    tabDownloads.addEventListener("click", () => switchPanel("downloads"));

    form.addEventListener("submit", (event) => {
        event.preventDefault();
        searchState.query = queryEl.value.trim();
        searchState.types = typeEl.value;
        searchState.sort = sortEl.value || "Most Downloaded";
        searchState.nsfw = nsfwEl.checked;
        searchState.page = 1;
        searchState.cursor = "";
        searchState.next_cursor = "";
        searchState.cursor_stack = [];
        switchPanel("browse");
        runSearch();
    });

    prevPageBtn.addEventListener("click", () => {
        if (searchState.using_cursor) {
            if (searchState.cursor_stack.length === 0) return;
            searchState.cursor = searchState.cursor_stack.pop();
            runSearch();
        } else if (searchState.page > 1) {
            searchState.page -= 1;
            runSearch();
        }
    });
    nextPageBtn.addEventListener("click", () => {
        if (searchState.using_cursor) {
            if (!searchState.next_cursor) return;
            searchState.cursor_stack.push(searchState.cursor);
            searchState.cursor = searchState.next_cursor;
            runSearch();
        } else if (searchState.page < searchState.pages) {
            searchState.page += 1;
            runSearch();
        }
    });

    window.addEventListener("civitai:models-updated", () => {
        if (document.visibilityState === "visible") refreshDownloads();
    });

    document.addEventListener("visibilitychange", () => {
        if (!document.hidden) refreshDownloads();
    });

    /* Poll once on load to sync the header badge after page reload. */
    refreshDownloads();
})();
