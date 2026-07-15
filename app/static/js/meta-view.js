/**
 * Meta view - renders metadata details in content area
 * Now with tabs: Summary / Workflow / Raw
 */

import { images, activeIndex, detailCache, galleryActive, dom, saveState } from './state.js';
import { escapeHtml, formatValue, getStringValue, thumbUrl, copyText } from './utils.js';
import { skeletonMetaView } from './components/skeleton.js';
import { renderWorkflowGraph, initWorkflowGraphEvents } from './features/workflow-graph.js';

let currentTab = 'summary';

export function renderMeta(img) {
    if (!img) {
        dom.contentArea.innerHTML = `
            <div class="empty-state">
                <div class="empty-state-icon">
                    <svg viewBox="0 0 24 24" width="48" height="48" stroke="currentColor" stroke-width="1.5" fill="none" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
                </div>
                <p>No image selected</p>
            </div>
        `;
        return;
    }

    if (img.error) {
        dom.contentArea.innerHTML = `
            <div class="meta-view">
                <div class="card">
                    <div class="card-header">
                        <span class="icon">
                            <svg viewBox="0 0 24 24" width="20" height="20" stroke="var(--red)" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
                        </span>
                        <h3>Error reading ${escapeHtml(img.file_name || img.file)}</h3>
                    </div>
                    <div class="card-body">
                        <pre class="raw-pre">${escapeHtml(img.error)}</pre>
                    </div>
                </div>
            </div>
        `;
        return;
    }

    if (galleryActive) return;

    // Show skeleton while loading detail
    if (img.id && !detailCache[img.id]) {
        dom.contentArea.innerHTML = skeletonMetaView();
        // Load detail in background
        loadDetail(img).then(() => {
            if (images[activeIndex] === img) {
                renderMeta(img);
            }
        });
        return;
    }

    const detail = (img.id && detailCache[img.id]) || img;
    const fileName = detail.file_name || detail.file || '';

    let html = '<div class="meta-view">';

    // Header
    html += `
        <div class="meta-view-header">
            <img src="${thumbUrl(detail)}" alt="" class="meta-thumb">
            <div class="meta-info">
                <h2>${escapeHtml(fileName)}</h2>
                <div class="meta-details">
                    ${detail.format ? `<span class="badge badge-format">${escapeHtml(detail.format)}</span>` : ''}
                    ${detail.size ? `<span class="text-dim">${detail.size[0]} x ${detail.size[1]}</span>` : ''}
                    ${detail.mode ? `<span class="text-dim">${escapeHtml(detail.mode)}</span>` : ''}
                </div>
            </div>
            <button class="btn btn-sm btn-primary" id="copy-all-meta-btn">Copy All</button>
        </div>
    `;

    // Tabs
    const hasWorkflow = detail.workflow && detail.workflow.workflow_nodes;
    const hasRaw = detail.raw_parameters || detail.raw_chunks;

    html += `
        <div class="content-tabs">
            <button class="content-tab ${currentTab === 'summary' ? 'active' : ''}" data-tab="summary">Summary</button>
            ${hasWorkflow ? `<button class="content-tab ${currentTab === 'workflow' ? 'active' : ''}" data-tab="workflow">Workflow</button>` : ''}
            ${hasRaw ? `<button class="content-tab ${currentTab === 'raw' ? 'active' : ''}" data-tab="raw">Raw</button>` : ''}
        </div>
    `;

    // Tab panels
    html += `<div class="tab-panel ${currentTab === 'summary' ? 'active' : ''}" id="panel-summary">`;
    html += renderSummaryTab(detail);
    html += '</div>';

    if (hasWorkflow) {
        html += `<div class="tab-panel ${currentTab === 'workflow' ? 'active' : ''}" id="panel-workflow">`;
        html += renderWorkflowTab(detail.workflow);
        html += '</div>';
    }

    if (hasRaw) {
        html += `<div class="tab-panel ${currentTab === 'raw' ? 'active' : ''}" id="panel-raw">`;
        html += renderRawTab(detail);
        html += '</div>';
    }

    html += '</div>';
    dom.contentArea.innerHTML = html;

    // Event listeners
    attachEventListeners();
}

function renderSummaryTab(detail) {
    let html = '';
    const pp = detail.prompt_parameters;

    if (pp) {
        html += renderCategory('Generation Settings', '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><circle cx="12" cy="12" r="3"></circle><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 1 1-2.83 2.83l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-4 0v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 1 1-2.83-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1 0-4h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 1 1 2.83-2.83l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 4 0v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 1 1 2.83 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 0 4h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>', 'settings', [
            ...Object.entries(pp).filter(([k]) => !['generation_settings', 'extra_settings', 'workflow_nodes'].includes(k))
                .map(([k, v]) => ({ key: k, value: v })),
            ...(pp.generation_settings ? Object.entries(pp.generation_settings).map(([k, v]) => ({ key: k, value: v })) : []),
        ]);
    }

    if (pp && pp.positive_prompt) {
        html += renderCategory('Positive Prompt', '<svg viewBox="0 0 24 24" width="14" height="14" stroke="var(--green)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><polyline points="20 6 9 17 4 12"></polyline></svg>', 'prompt_pos', [{ key: 'Prompt', value: pp.positive_prompt }], true);
    }

    if (pp && pp.negative_prompt) {
        html += renderCategory('Negative Prompt', '<svg viewBox="0 0 24 24" width="14" height="14" stroke="var(--red)" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>', 'prompt_neg', [{ key: 'Negative Prompt', value: pp.negative_prompt }], true);
    }

    if (pp && pp.extra_settings && Object.keys(pp.extra_settings).length > 0) {
        html += renderCategory('Extra Settings', '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>', 'extra',
            Object.entries(pp.extra_settings).map(([k, v]) => ({ key: k, value: v })));
    }

    if (detail.exif && Object.keys(detail.exif).length > 0) {
        html += renderCategory('EXIF Data', '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>', 'exif',
            Object.entries(detail.exif).map(([k, v]) => ({ key: k, value: v })));
    }

    return html;
}

function renderWorkflowTab(workflow) {
    let html = '';

    // Render SVG graph
    html += renderWorkflowGraph(workflow);

    // Also render node details below
    const catIcons = {
        'Models': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>',
        'Prompts': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="M12 20h9"></path><path d="M16.5 3.5a2.12 2.12 0 0 1 3 3L7 19l-4 1 1-4Z"></path></svg>',
        'Sampler': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="4" y1="21" x2="4" y2="14"></line><line x1="4" y1="10" x2="4" y2="3"></line><line x1="12" y1="21" x2="12" y2="12"></line><line x1="12" y1="8" x2="12" y2="3"></line><line x1="20" y1="21" x2="20" y2="16"></line><line x1="20" y1="12" x2="20" y2="3"></line><line x1="1" y1="14" x2="7" y2="14"></line><line x1="9" y1="8" x2="15" y2="8"></line><line x1="17" y1="16" x2="23" y2="16"></line></svg>',
        'Image Settings': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
        'Post Processing': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><line x1="16.5" y1="9.4" x2="7.5" y2="4.21"></line><polygon points="12 22.08 12 12 3 6.92 3 17.08 12 22.08"></polygon><polygon points="12 22.08 21 17.08 21 6.92 12 12 12 22.08"></polygon><polygon points="12 12 3 6.92 12 1.83 21 6.92 12 12"></polygon></svg>',
        'LoRA': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><path d="m21 2-2 2m-7.61 7.61a5.5 5.5 0 1 1-7.778 7.778 5.5 5.5 0 0 1 7.777-7.777zm0 0L15.5 7.5m0 0 1.5 1.5M15.5 7.5 14 6"></path></svg>',
        'Other': '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>'
    };
    const catBadge = {
        'Models': 'badge-models', 'Prompts': 'badge-prompts', 'Sampler': 'badge-sampler',
        'Image Settings': 'badge-image-settings', 'Post Processing': 'badge-post-processing', 'LoRA': 'badge-lora', 'Other': 'badge-other'
    };

    if (workflow.workflow_nodes) {
        for (const [catName, nodes] of Object.entries(workflow.workflow_nodes)) {
            html += renderNodeCategory(catName, catIcons[catName] || '<svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>', nodes, catBadge[catName] || 'badge-other');
        }
    }

    return html;
}

function renderRawTab(detail) {
    let html = '';

    if (detail.raw_parameters) {
        html += `
            <div class="raw-block">
                <h4>Raw Parameters</h4>
                <pre class="raw-pre">${escapeHtml(detail.raw_parameters)}</pre>
            </div>
        `;
    }

    if (detail.raw_chunks && Object.keys(detail.raw_chunks).length > 0) {
        html += `
            <div class="raw-block">
                <h4>Raw Chunks</h4>
                <pre class="raw-pre">${escapeHtml(JSON.stringify(detail.raw_chunks, null, 2))}</pre>
            </div>
        `;
    }

    return html;
}

function renderCategory(title, icon, id, rows, isLong) {
    let html = `
        <div class="card">
            <div class="card-header" data-category="${id}">
                <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" class="arrow" id="arrow-${id}"><polyline points="6 9 12 15 18 9"></polyline></svg>
                <span class="icon">${icon}</span>
                <h3>${title}</h3>
                <div class="actions">
                    <button class="btn btn-sm btn-ghost copy-all" data-category="${id}" ${isLong ? 'data-value-only="true"' : ''}>Copy</button>
                </div>
            </div>
            <div class="card-body" id="body-${id}">
    `;

    rows.forEach(r => {
        const valStr = getStringValue(r.value);
        const escapedVal = escapeHtml(valStr).replace(/"/g, '&quot;');
        html += `
            <div class="card-row">
                <div class="key">${escapeHtml(r.key)}</div>
                <div class="value">${formatValue(r.value)}</div>
                <button class="copy-btn" data-copy-value="${escapedVal}"><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
            </div>
        `;
    });

    html += '</div></div>';
    return html;
}

function renderNodeCategory(title, icon, nodes, badgeClass) {
    let html = `
        <div class="card">
            <div class="card-header" data-category="node-${title}">
                <svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2.5" fill="none" stroke-linecap="round" stroke-linejoin="round" class="arrow" id="arrow-node-${title}"><polyline points="6 9 12 15 18 9"></polyline></svg>
                <span class="icon">${icon}</span>
                <h3>${escapeHtml(title)}</h3>
            </div>
            <div class="card-body" id="body-node-${title}">
    `;

    nodes.forEach(node => {
        const fullText = `${node.class_type} #${node.node_id}\n` +
            Object.entries(node.inputs || {}).map(([k, v]) => `  ${k}: ${getStringValue(v)}`).join('\n');
        const escapedFullText = escapeHtml(fullText).replace(/"/g, '&quot;');

        html += `
            <div class="node-card">
                <div class="node-header">
                    <span class="badge ${badgeClass}">${escapeHtml(node.class_type)}</span>
                    <span class="node-title">${escapeHtml(node.title || node.class_type)}</span>
                    <span class="node-id">#${escapeHtml(node.node_id)}</span>
                    <button class="btn btn-sm btn-ghost copy-btn" data-copy-value="${escapedFullText}"><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 4px; vertical-align: middle;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg>Copy</button>
                </div>
                <div class="node-inputs">
        `;

        for (const [k, v] of Object.entries(node.inputs || {})) {
            const valStr = getStringValue(v);
            const escapedVal = escapeHtml(valStr).replace(/"/g, '&quot;');
            html += `
                <div class="card-row">
                    <div class="key">${escapeHtml(k)}</div>
                    <div class="value">${formatValue(v)}</div>
                    <button class="copy-btn" data-copy-value="${escapedVal}"><svg viewBox="0 0 24 24" width="12" height="12" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round" style="vertical-align: middle;"><rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path></svg></button>
                </div>
            `;
        }

        html += '</div></div>';
    });

    html += '</div></div>';
    return html;
}

function toggleCategory(id) {
    const body = document.getElementById('body-' + id);
    const arrow = document.getElementById('arrow-' + id);
    if (!body) return;
    body.classList.toggle('collapsed');
    if (arrow) arrow.classList.toggle('collapsed');
}

function copyCategory(id, valueOnly = false) {
    const body = document.getElementById('body-' + id);
    if (!body) return;
    const rows = body.querySelectorAll('.card-row');
    let text = '';
    rows.forEach((r, i) => {
        const key = r.querySelector('.key')?.textContent || '';
        const val = r.querySelector('.value')?.textContent || '';
        if (valueOnly) {
            text += val + (i < rows.length - 1 ? '\n' : '');
        } else {
            text += `${key}: ${val}\n`;
        }
    });
    copyText(text.trim());
}

function copyAllMeta() {
    const img = activeIndex >= 0 && images[activeIndex];
    const detail = (img && img.id && detailCache[img.id]) || img;
    if (detail) copyText(JSON.stringify(detail, null, 2));
}

async function loadDetail(img) {
    if (!img.id) return;
    try {
        const resp = await fetch(`/api/images/${img.id}`);
        if (resp.ok) {
            detailCache[img.id] = await resp.json();
        }
    } catch (e) { /* ignore */ }
}

function attachEventListeners() {
    // Tab switching
    dom.contentArea.querySelectorAll('.content-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            currentTab = tab.dataset.tab;
            dom.contentArea.querySelectorAll('.content-tab').forEach(t => t.classList.remove('active'));
            dom.contentArea.querySelectorAll('.tab-panel').forEach(p => p.classList.remove('active'));
            tab.classList.add('active');
            document.getElementById('panel-' + currentTab)?.classList.add('active');
        });
    });

    // Category collapse
    dom.contentArea.querySelectorAll('.card-header[data-category]').forEach(el => {
        el.addEventListener('click', () => {
            const id = el.dataset.category;
            if (id) toggleCategory(id);
        });
    });

    // Copy all category
    dom.contentArea.querySelectorAll('.copy-all').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = el.dataset.category;
            const valueOnly = el.dataset.valueOnly === 'true';
            if (id) copyCategory(id, valueOnly);
        });
    });

    // Copy single value
    dom.contentArea.querySelectorAll('.copy-btn').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const val = el.dataset.copyValue || el.closest('.card-row')?.querySelector('.value')?.textContent || '';
            copyText(val);
        });
    });

    // Copy all meta
    dom.contentArea.querySelector('#copy-all-meta-btn')?.addEventListener('click', copyAllMeta);

    // Workflow graph events
    initWorkflowGraphEvents();
}
