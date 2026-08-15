/**
 * ComfyUI Meta Viewer — Global Theme Manager
 * Supports: 'dark', 'light', 'strawberry', 'system'
 */

const THEME_STORAGE_KEY = 'cmv_theme';
const VALID_THEMES = ['dark', 'light', 'strawberry', 'system'];

export function getStoredTheme() {
    try {
        const stored = localStorage.getItem(THEME_STORAGE_KEY);
        if (stored && VALID_THEMES.includes(stored)) {
            return stored;
        }
    } catch (_e) {
        // Storage unavailable
    }
    return 'dark';
}

export function resolveEffectiveTheme(themeName) {
    if (themeName === 'system') {
        return window.matchMedia && window.matchMedia('(prefers-color-scheme: dark)').matches
            ? 'dark'
            : 'light';
    }
    return themeName || 'dark';
}

export function applyTheme(themeName) {
    const valid = VALID_THEMES.includes(themeName) ? themeName : 'dark';
    const effective = resolveEffectiveTheme(valid);

    document.documentElement.setAttribute('data-theme', effective);

    try {
        localStorage.setItem(THEME_STORAGE_KEY, valid);
    } catch (_e) {
        // Storage unavailable
    }

    updateThemeUI(valid);

    // Dispatch custom event for any canvas/graph/custom components that listen for theme changes
    window.dispatchEvent(new CustomEvent('themechange', {
        detail: { theme: valid, effectiveTheme: effective },
    }));
}

export function updateThemeUI(selectedTheme) {
    const currentTheme = selectedTheme || getStoredTheme();
    
    document.querySelectorAll('[data-theme-value]').forEach(btn => {
        const value = btn.getAttribute('data-theme-value');
        if (value === currentTheme) {
            btn.classList.add('active');
            btn.setAttribute('aria-selected', 'true');
        } else {
            btn.classList.remove('active');
            btn.setAttribute('aria-selected', 'false');
        }
    });

    // Update theme toggle icon if present
    const toggleIcons = document.querySelectorAll('[data-theme-current-icon]');
    toggleIcons.forEach(icon => {
        icon.setAttribute('data-current-theme', currentTheme);
    });
}

export function initThemeManager() {
    const stored = getStoredTheme();
    applyTheme(stored);

    // Listen for OS system theme changes
    if (window.matchMedia) {
        const mediaQuery = window.matchMedia('(prefers-color-scheme: dark)');
        mediaQuery.addEventListener('change', () => {
            if (getStoredTheme() === 'system') {
                applyTheme('system');
            }
        });
    }

    // Sync across browser tabs
    window.addEventListener('storage', event => {
        if (event.key === THEME_STORAGE_KEY && event.newValue) {
            applyTheme(event.newValue);
        }
    });

    // Bind dropdown click handlers
    document.addEventListener('click', event => {
        const option = event.target.closest('[data-theme-value]');
        if (option) {
            const themeValue = option.getAttribute('data-theme-value');
            if (themeValue) {
                applyTheme(themeValue);
                // Close menu if in a dropdown
                const menu = option.closest('[data-header-menu], [data-theme-menu]');
                if (menu) {
                    menu.classList.remove('open');
                    const trigger = menu.querySelector('[data-header-menu-trigger], [data-theme-menu-trigger]');
                    const dropdown = menu.querySelector('.header-dropdown');
                    if (trigger) trigger.setAttribute('aria-expanded', 'false');
                    if (dropdown) dropdown.hidden = true;
                }
            }
            return;
        }

        // Toggle theme dropdown menu
        const trigger = event.target.closest('[data-theme-menu-trigger]');
        if (trigger) {
            event.stopPropagation();
            const menu = trigger.closest('[data-theme-menu]');
            if (!menu) return;
            const dropdown = menu.querySelector('.header-dropdown');
            const isOpen = menu.classList.contains('open');

            // Close all other header menus
            document.querySelectorAll('[data-header-menu], [data-theme-menu]').forEach(m => {
                if (m !== menu) {
                    m.classList.remove('open');
                    const t = m.querySelector('[data-header-menu-trigger], [data-theme-menu-trigger]');
                    const d = m.querySelector('.header-dropdown');
                    if (t) t.setAttribute('aria-expanded', 'false');
                    if (d) d.hidden = true;
                }
            });

            if (isOpen) {
                menu.classList.remove('open');
                trigger.setAttribute('aria-expanded', 'false');
                if (dropdown) dropdown.hidden = true;
            } else {
                menu.classList.add('open');
                trigger.setAttribute('aria-expanded', 'true');
                if (dropdown) dropdown.hidden = false;
            }
            return;
        }

        // Click outside closes theme menu
        if (!event.target.closest('[data-theme-menu]')) {
            document.querySelectorAll('[data-theme-menu].open').forEach(menu => {
                menu.classList.remove('open');
                const trigger = menu.querySelector('[data-theme-menu-trigger]');
                const dropdown = menu.querySelector('.header-dropdown');
                if (trigger) trigger.setAttribute('aria-expanded', 'false');
                if (dropdown) dropdown.hidden = true;
            });
        }
    });

    // Close on Escape key
    document.addEventListener('keydown', event => {
        if (event.key === 'Escape') {
            document.querySelectorAll('[data-theme-menu].open').forEach(menu => {
                menu.classList.remove('open');
                const trigger = menu.querySelector('[data-theme-menu-trigger]');
                const dropdown = menu.querySelector('.header-dropdown');
                if (trigger) {
                    trigger.setAttribute('aria-expanded', 'false');
                    trigger.focus();
                }
                if (dropdown) dropdown.hidden = true;
            });
        }
    });

    updateThemeUI(stored);
}

// Auto-run if loaded as script or defer
if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initThemeManager);
    } else {
        initThemeManager();
    }
}
