(function () {
    'use strict';

    const prefetchedUrls = new Set();

    function prefetchUrl(url) {
        if (!url || prefetchedUrls.has(url)) return;
        prefetchedUrls.add(url);

        const link = document.createElement('link');
        link.rel = 'prefetch';
        link.href = url;
        link.as = 'document';
        document.head.appendChild(link);
    }

    function initPrefetching() {
        const switcherLinks = document.querySelectorAll('.app-switcher-link');
        
        switcherLinks.forEach(link => {
            const href = link.getAttribute('href');
            if (!href || href === window.location.pathname) return;

            link.addEventListener('pointerenter', () => prefetchUrl(href), { passive: true });
            link.addEventListener('touchstart', () => prefetchUrl(href), { passive: true });
        });

        const prefetchTargets = ['/library', '/create', '/editor', '/settings/ai', '/'];
        
        const runIdlePrefetch = window.requestIdleCallback || function (cb) { setTimeout(cb, 1200); };
        runIdlePrefetch(() => {
            prefetchTargets.forEach(target => {
                if (target !== window.location.pathname) {
                    prefetchUrl(target);
                }
            });
        });
    }

    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initPrefetching);
    } else {
        initPrefetching();
    }
})();
