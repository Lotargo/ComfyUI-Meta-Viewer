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
                <div class="empty-state-icon">&#128444;</div>
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
                        <span class="icon">&#9888;</span>
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
        html += renderCategory('Generation Settings', '&#9881;', 'settings', [
            ...Object.entries(pp).filter(([k]) => !['generation_settings', 'extra_settings', 'workflow_nodes'].includes(k))
                .map(([k, v]) => ({ key: k, value: v })),
            ...(pp.generation_settings ? Object.entries(pp.generation_settings).map(([k, v]) => ({ key: k, value: v })) : []),
        ]);
    }

    if (pp && pp.positive_prompt) {
        html += renderCategory('Positive Prompt', '&#10003;', 'prompt_pos', [{ key: 'Prompt', value: pp.positive_prompt }], true);
    }

    if (pp && pp.negative_prompt) {
        html += renderCategory('Negative Prompt', '&#10007;', 'prompt_neg', [{ key: 'Negative Prompt', value: pp.negative_prompt }], true);
    }

    if (pp && pp.extra_settings && Object.keys(pp.extra_settings).length > 0) {
        html += renderCategory('Extra Settings', '&#9733;', 'extra',
            Object.entries(pp.extra_settings).map(([k, v]) => ({ key: k, value: v })));
    }

    if (detail.exif && Object.keys(detail.exif).length > 0) {
        html += renderCategory('EXIF Data', '&#128196;', 'exif',
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
        'Models': '&#128190;', 'Prompts': '&#128221;', 'Sampler': '&#127922;',
        'Image Settings': '&#128444;', 'Post Processing': '&#128230;', 'LoRA': '&#128273;', 'Other': '&#128269;'
    };
    const catBadge = {
        'Models': 'badge-models', 'Prompts': 'badge-prompts', 'Sampler': 'badge-sampler',
        'Image Settings': 'badge-image-settings', 'Post Processing': 'badge-post-processing', 'LoRA': 'badge-lora', 'Other': 'badge-other'
    };

    if (workflow.workflow_nodes) {
        for (const [catName, nodes] of Object.entries(workflow.workflow_nodes)) {
            html += renderNodeCategory(catName, catIcons[catName] || '&#128269;', nodes, catBadge[catName] || 'badge-other');
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
                <span class="arrow" id="arrow-${id}">&#9660;</span>
                <span class="icon">${icon}</span>
                <h3>${title}</h3>
                <span class="counter">${rows.length}</span>
                <div class="actions">
                    <button class="btn btn-sm btn-ghost copy-all" data-category="${id}">Copy</button>
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
                <button class="copy-btn" data-copy-value="${escapedVal}">&#128203;</button>
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
                <span class="arrow" id="arrow-node-${title}">&#9660;</span>
                <span class="icon">${icon}</span>
                <h3>${escapeHtml(title)}</h3>
                <span class="counter">${nodes.length}</span>
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
                    <button class="btn btn-sm btn-ghost copy-btn" data-copy-value="${escapedFullText}">&#128203; Copy</button>
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
                    <button class="copy-btn" data-copy-value="${escapedVal}">&#128203;</button>
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

function copyCategory(id) {
    const body = document.getElementById('body-' + id);
    if (!body) return;
    const rows = body.querySelectorAll('.card-row');
    let text = '';
    rows.forEach(r => {
        const key = r.querySelector('.key')?.textContent || '';
        const val = r.querySelector('.value')?.textContent || '';
        text += `${key}: ${val}\n`;
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
            if (id) copyCategory(id);
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
