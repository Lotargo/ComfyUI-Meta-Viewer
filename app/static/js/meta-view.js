import { images, activeIndex, detailCache, galleryActive, dom, saveState } from './state.js';
import { escapeHtml, formatValue, getStringValue, thumbUrl, copyText } from './utils.js';

export function renderMeta(img) {
    if (!img) {
        dom.contentArea.innerHTML = '<div class="empty-state anim-fade-in"><div class="icon">&#128444;</div></div>';
        return;
    }
    if (img.error) {
        dom.contentArea.innerHTML = `<div class="meta-view anim-shake"><div class="category"><div class="category-header"><h3>Error reading ${escapeHtml(img.file_name || img.file)}</h3></div><div class="raw-block"><pre>${escapeHtml(img.error)}</pre></div></div></div>`;
        return;
    }
    if (galleryActive) return;

    const detail = (img.id && detailCache[img.id]) || img;
    const fileName = detail.file_name || detail.file || '';

    let html = '<div class="meta-view anim-slide-up">';
    html += `<div class="meta-view-header">
        <img src="${thumbUrl(detail)}" alt="">
        <div class="info">
            <h2>${escapeHtml(fileName)}</h2>
            <div class="details">${escapeHtml(detail.format || '')} | ${detail.size ? detail.size[0]+' x '+detail.size[1] : ''} | ${escapeHtml(detail.mode || '')}</div>
        </div>
        <button class="btn btn-sm" id="copy-all-meta-btn">Copy All</button>
    </div>`;

    const pp = detail.prompt_parameters;
    if (pp) {
        html += renderCategory('Generation Settings', '&#9881;', 'settings', [
            ...Object.entries(pp).filter(([k]) => !['generation_settings','extra_settings','workflow_nodes'].includes(k))
                .map(([k, v]) => ({key: k, value: v})),
            ...(pp.generation_settings ? Object.entries(pp.generation_settings).map(([k, v]) => ({key: k, value: v})) : []),
        ]);
    }

    if (pp && pp.positive_prompt) {
        html += renderCategory('Positive Prompt', '&#10003;', 'prompt_pos', [{key: 'Prompt', value: pp.positive_prompt}], true);
    }
    if (pp && pp.negative_prompt) {
        html += renderCategory('Negative Prompt', '&#10007;', 'prompt_neg', [{key: 'Negative Prompt', value: pp.negative_prompt}], true);
    }

    const wf = detail.workflow;
    if (wf && wf.workflow_nodes) {
        const catIcons = {
            'Models': '&#128190;', 'Prompts': '&#128221;', 'Sampler': '&#127922;',
            'Image Settings': '&#128444;', 'Post Processing': '&#128230;', 'LoRA': '&#128273;', 'Other': '&#128269;'
        };
        const catBadge = {
            'Models': 'Models', 'Prompts': 'Prompts', 'Sampler': 'Sampler',
            'Image Settings': 'ImageSettings', 'Post Processing': 'PostProcessing', 'LoRA': 'LoRA', 'Other': 'Other'
        };
        for (const [catName, nodes] of Object.entries(wf.workflow_nodes)) {
            const rows = [];
            nodes.forEach(node => rows.push({isNode: true, node, category: catBadge[catName] || 'Other'}));
            html += renderNodeCategory(catName, catIcons[catName] || '&#128269;', rows);
        }
    }

    if (pp && pp.extra_settings && Object.keys(pp.extra_settings).length > 0) {
        html += renderCategory('Extra Settings', '&#9733;', 'extra',
            Object.entries(pp.extra_settings).map(([k, v]) => ({key: k, value: v})));
    }

    if (detail.exif && Object.keys(detail.exif).length > 0) {
        html += renderCategory('EXIF Data', '&#128196;', 'exif',
            Object.entries(detail.exif).map(([k, v]) => ({key: k, value: v})));
    }

    if (detail.raw_chunks && Object.keys(detail.raw_chunks).length > 0) {
        html += renderCategory('Raw Chunks', '&#128193;', 'raw',
            Object.entries(detail.raw_chunks).map(([k, v]) => ({key: k, value: v})));
    }

    if (detail.raw_parameters) {
        html += renderCategory('Raw Parameters', '&#128196;', 'raw_params',
            [{key: 'parameters', value: detail.raw_parameters}], true);
    }

    html += '</div>';
    dom.contentArea.innerHTML = html;

    dom.contentArea.querySelector('#copy-all-meta-btn')?.addEventListener('click', copyAllMeta);
    dom.contentArea.querySelectorAll('.category-header').forEach(el => {
        el.addEventListener('click', () => {
            const id = el.closest('.category').querySelector('.category-body')?.id?.replace('body-', '');
            if (id) toggleCategory(id);
        });
    });
    dom.contentArea.querySelectorAll('.copy-all').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const id = el.closest('.category').querySelector('.category-body')?.id?.replace('body-', '');
            if (id) copyCategory(id);
        });
    });
    dom.contentArea.querySelectorAll('.copy-btn').forEach(el => {
        el.addEventListener('click', (e) => {
            e.stopPropagation();
            const val = el.dataset.copyValue || el.closest('.meta-row')?.querySelector('.value')?.textContent || '';
            copyText(val);
        });
    });
}

function renderCategory(title, icon, id, rows, isLong) {
    let html = `<div class="category">
        <div class="category-header">
            <span class="arrow" id="arrow-${id}">&#9660;</span>
            <span class="cat-icon">${icon}</span>
            <h3>${title}</h3>
            <span class="count">${rows.length}</span>
            <button class="btn btn-sm copy-all">Copy</button>
        </div>
        <div class="category-body" id="body-${id}">`;
    rows.forEach(r => {
        const valStr = getStringValue(r.value);
        const escapedVal = escapeHtml(valStr).replace(/"/g, '&quot;');
        html += `<div class="meta-row">
            <div class="key">${escapeHtml(r.key)}</div>
            <div class="value">${formatValue(r.value)}</div>
            <button class="btn btn-sm copy-btn" data-copy-value="${escapedVal}">&#128203;</button>
        </div>`;
    });
    html += '</div></div>';
    return html;
}

function renderNodeCategory(title, icon, rows) {
    let html = `<div class="category">
        <div class="category-header">
            <span class="arrow" id="arrow-node-${title}">&#9660;</span>
            <span class="cat-icon">${icon}</span>
            <h3>${escapeHtml(title)}</h3>
            <span class="count">${rows.length}</span>
        </div>
        <div class="category-body" id="body-node-${title}">`;
    rows.forEach(r => {
        const n = r.node;
        const fullText = `${n.class_type} #${n.node_id}\n` +
            Object.entries(n.inputs || {}).map(([k,v]) => `  ${k}: ${getStringValue(v)}`).join('\n');
        const escapedFullText = escapeHtml(fullText).replace(/"/g, '&quot;');
        html += `<div class="node-block">
            <div class="node-header">
                <span class="node-badge ${r.category}">${escapeHtml(n.class_type)}</span>
                <span class="node-title">${escapeHtml(n.title || n.class_type)}</span>
                <span class="node-id">#${escapeHtml(n.node_id)}</span>
                <button class="btn btn-sm copy-btn" style="margin-left:8px" data-copy-value="${escapedFullText}">&#128203; Copy</button>
            </div>
            <div class="node-inputs">`;
        for (const [k, v] of Object.entries(n.inputs || {})) {
            const valStr = getStringValue(v);
            const escapedVal = escapeHtml(valStr).replace(/"/g, '&quot;');
            html += `<div class="meta-row">
                <div class="key">${escapeHtml(k)}</div>
                <div class="value">${formatValue(v)}</div>
                <button class="btn btn-sm copy-btn" data-copy-value="${escapedVal}">&#128203;</button>
            </div>`;
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
    const rows = body.querySelectorAll('.meta-row');
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