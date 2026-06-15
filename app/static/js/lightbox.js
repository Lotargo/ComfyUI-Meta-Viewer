import { images, lightboxIndex, totalImages, galleryActive, detailCache, dom, setLightboxIndex, setActiveIndex, saveState } from './state.js';
import { escapeHtml, originalUrl, thumbUrl } from './utils.js';

export async function openLightbox(idx) {
    if (idx < 0 || idx >= images.length) return;
    setLightboxIndex(idx);
    const img = images[idx];
    if (img && img.id && !detailCache[img.id]) {
        try {
            const resp = await fetch(`/api/images/${img.id}`);
            if (resp.ok) detailCache[img.id] = await resp.json();
        } catch(e) { /* ignore */ }
    }
    dom.lightbox.classList.add('open');
    document.body.style.overflow = 'hidden';
    updateLightbox();
}

export function closeLightbox() {
    dom.lightbox.classList.remove('open');
    document.body.style.overflow = '';
    setLightboxIndex(-1);
}

function getDetailForLightbox() {
    const img = images[lightboxIndex];
    if (!img) return null;
    if (img.id && detailCache[img.id]) return detailCache[img.id];
    return img;
}

export function updateLightbox() {
    const img = getDetailForLightbox();
    if (!img) { closeLightbox(); return; }

    setActiveIndex(lightboxIndex);
    saveState();
    if (galleryActive) {
        import('./gallery.js').then(m => m.renderGallery());
    } else {
        import('./sidebar.js').then(m => m.renderSidebar());
    }

    const fileName = img.file_name || img.file || '';
    dom.lbTitle.textContent = fileName;
    dom.lbCounter.textContent = `${lightboxIndex + 1} / ${totalImages || images.length}`;
    dom.lbImg.src = originalUrl(img);

    let html = '';

    if (img.prompt_parameters) {
        const pp = img.prompt_parameters;
        if (pp.positive_prompt) {
            html += `<div class="lb-meta-section">
                <div class="lb-prompt-label">&#10003; Positive Prompt</div>
                <div class="lb-prompt-box">${escapeHtml(pp.positive_prompt)}</div>
            </div>`;
        }
        if (pp.negative_prompt) {
            html += `<div class="lb-meta-section">
                <div class="lb-prompt-label">&#10007; Negative Prompt</div>
                <div class="lb-prompt-box">${escapeHtml(pp.negative_prompt)}</div>
            </div>`;
        }

        const settings = {};
        Object.entries(pp).forEach(([k, v]) => {
            if (!['generation_settings','extra_settings','workflow_nodes','positive_prompt','negative_prompt'].includes(k)) {
                settings[k] = v;
            }
        });
        if (pp.generation_settings) Object.assign(settings, pp.generation_settings);

        if (Object.keys(settings).length) {
            html += '<div class="lb-meta-section"><h4>&#9881; Settings</h4>';
            Object.entries(settings).forEach(([k, v]) => {
                html += `<div class="lb-meta-row"><span class="lb-key">${escapeHtml(k)}</span><span class="lb-val">${escapeHtml(String(v))}</span></div>`;
            });
            html += '</div>';
        }
    }

    if (img.workflow && img.workflow.workflow_nodes) {
        const order = ['Models','Prompts','Sampler','Image Settings','Post Processing','LoRA','Other'];
        order.forEach(catName => {
            const nodes = img.workflow.workflow_nodes[catName];
            if (!nodes || !nodes.length) return;
            html += `<div class="lb-meta-section"><h4>${escapeHtml(catName)} (${nodes.length})</h4>`;
            nodes.forEach(n => {
                html += `<div style="margin-bottom:6px"><span class="lb-key" style="color:var(--accent);font-weight:600">${escapeHtml(n.class_type)}</span> <span style="font-size:10px;color:var(--text-dim)">#${n.node_id}</span></div>`;
                Object.entries(n.inputs || {}).forEach(([k, v]) => {
                    html += `<div class="lb-meta-row"><span class="lb-key">${escapeHtml(k)}</span><span class="lb-val">${escapeHtml(String(v))}</span></div>`;
                });
            });
            html += '</div>';
        });
    }

    if (img.exif && Object.keys(img.exif).length) {
        html += '<div class="lb-meta-section"><h4>&#128196; EXIF</h4>';
        Object.entries(img.exif).forEach(([k, v]) => {
            html += `<div class="lb-meta-row"><span class="lb-key">${escapeHtml(k)}</span><span class="lb-val">${escapeHtml(String(v))}</span></div>`;
        });
        html += '</div>';
    }

    dom.lbMeta.innerHTML = html || '<div style="color:var(--text-dim);font-size:13px;padding:20px;text-align:center">No metadata</div>';
}

export function lbNav(dir) {
    const next = lightboxIndex + dir;
    if (next >= 0 && next < images.length) {
        openLightbox(next);
    }
}

export function initLightboxEvents() {
    document.getElementById('lb-close').addEventListener('click', closeLightbox);
    document.getElementById('lb-prev').addEventListener('click', () => lbNav(-1));
    document.getElementById('lb-next').addEventListener('click', () => lbNav(1));

    document.getElementById('lb-copy').addEventListener('click', () => {
        const img = getDetailForLightbox();
        if (img) {
            import('./utils.js').then(m => m.copyText(JSON.stringify(img, null, 2)));
        }
    });

    dom.lightbox.addEventListener('click', e => {
        if (e.target === dom.lightbox || e.target.classList.contains('lightbox-body')) {
            closeLightbox();
        }
    });

    document.addEventListener('keydown', e => {
        if (!dom.lightbox.classList.contains('open')) return;
        if (e.key === 'Escape') closeLightbox();
        if (e.key === 'ArrowLeft') lbNav(-1);
        if (e.key === 'ArrowRight') lbNav(1);
    });
}
