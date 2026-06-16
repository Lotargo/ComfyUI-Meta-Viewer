import { images, activeIndex, galleryActive, currentFolderId, allLoaded, detailCache, scrollObserver, sessions, totalImages, dom, setActiveIndex, setScrollObserver, saveState } from './state.js';
import { escapeHtml, thumbUrl } from './utils.js';

export function renderSidebar() {
    if (galleryActive) return;
    dom.imageList.innerHTML = '';
    dom.imageCount.textContent = totalImages ? `(${images.length}/${totalImages})` : '';

    if (sessions.length > 0) {
        for (const session of sessions) {
            if (sessions.length > 1) {
                const hdr = document.createElement('div');
                hdr.className = 'session-header anim-slide-in-left';
                hdr.innerHTML = `<span class="session-name">${escapeHtml(session.name)}</span><span class="session-count">${session.images.length}</span><button class="btn btn-sm session-remove" data-session-id="${session.id}">&times;</button>`;
                hdr.querySelector('.session-remove').addEventListener('click', (e) => {
                    e.stopPropagation();
                    import('./sessions.js').then(m => m.removeSession(session.id));
                });
                dom.imageList.appendChild(hdr);
            }
            session.images.forEach(img => {
                const i = images.indexOf(img);
                if (i < 0) return;
                const div = document.createElement('div');
                div.className = 'image-item' + (i === activeIndex ? ' active' : '');
                const src = thumbUrl(img);
                const fileName = img.file_name || img.file || '';
                div.innerHTML = `<img src="${src}" alt="" loading="lazy">` +
                    `<div style="flex:1;min-width:0">` +
                        `<div class="name">${escapeHtml(fileName)}</div>` +
                        `<div class="meta-hint">${img.format || ''} ${img.size ? img.size[0]+'x'+img.size[1] : ''}</div>` +
                    `</div>`;
                div.onclick = () => selectImage(i);
                dom.imageList.appendChild(div);
            });
        }
    } else {
        images.forEach((img, i) => {
            const div = document.createElement('div');
            div.className = 'image-item' + (i === activeIndex ? ' active' : '');
            const src = thumbUrl(img);
            const fileName = img.file_name || img.file || '';
            div.innerHTML = `<img src="${src}" alt="" loading="lazy">` +
                `<div style="flex:1;min-width:0">` +
                    `<div class="name">${escapeHtml(fileName)}</div>` +
                    `<div class="meta-hint">${img.format || ''} ${img.size ? img.size[0]+'x'+img.size[1] : ''}</div>` +
                `</div>`;
            div.onclick = () => selectImage(i);
            dom.imageList.appendChild(div);
        });
    }

    appendSentinel();
}

export function appendSentinel() {
    if (scrollObserver) scrollObserver.disconnect();
    const existing = document.getElementById('scroll-sentinel');
    if (existing) existing.remove();
    if (allLoaded) return;
    const sentinel = document.createElement('div');
    sentinel.id = 'scroll-sentinel';
    sentinel.style.height = '1px';
    dom.imageList.appendChild(sentinel);
    setScrollObserver(new IntersectionObserver(entries => {
        if (entries[0].isIntersecting) {
            import('./api.js').then(m => m.loadMore());
        }
    }, {root: dom.imageList, threshold: 0.1}));
    scrollObserver.observe(sentinel);
}

export async function selectImage(idx) {
    setActiveIndex(idx);
    saveState();
    renderSidebar();
    const img = images[idx];
    if (!img) {
        const { renderMeta } = await import('./meta-view.js');
        return renderMeta(null);
    }
    if (galleryActive) {
        dom.imageList.querySelectorAll('.image-item').forEach((el, i) => {
            el.classList.toggle('active', i === idx);
        });
        import('./lightbox.js').then(m => m.openLightbox(idx));
        return;
    }
    const { renderMeta } = await import('./meta-view.js');
    renderMeta(img);
    if (img.id && !detailCache[img.id]) {
        try {
            const resp = await fetch(`/api/images/${img.id}`);
            if (resp.ok) detailCache[img.id] = await resp.json();
        } catch(e) { /* ignore */ }
    }
}
