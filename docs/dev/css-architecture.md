# CSS Architecture

> Styling architecture for ComfyUI Meta Viewer.

The CSS layer is built with plain CSS, custom properties, and modular files. There is no Sass/Less build step, which keeps the project simple and easy to run locally.

---

## Table of Contents

- [Overview](#overview)
- [Directory Structure](#directory-structure)
- [Custom Properties](#custom-properties)
- [Base Styles](#base-styles)
- [Layout Styles](#layout-styles)
- [Components](#components)
- [Feature Styles](#feature-styles)
- [Responsive Utilities](#responsive-utilities)
- [Naming Guidelines](#naming-guidelines)
- [Extension Guidelines](#extension-guidelines)

---

## Overview

Design principles:

1. **Custom properties for shared values**: colors, spacing, typography, shadows, and z-index layers.
2. **One file = one responsibility** where practical.
3. **Readable selectors** with BEM-like naming.
4. **No preprocessing requirement**: the app should run with static CSS files.
5. **Minimal `!important`** and predictable cascade order.

---

## Directory Structure

```
app/static/css/
├── base/                        # Foundational styles
│   ├── variables.css            # CSS custom properties
│   ├── reset.css                # Normalize/reset
│   ├── typography.css           # Text styles
│   └── animations.css           # Keyframes
├── layout/                      # Page layout
│   ├── app-shell.css            # Main app container
│   ├── sidebar.css              # Sidebar layout
│   └── content.css              # Main content area
├── components/                  # Reusable UI components
│   ├── buttons.css              # Buttons
│   ├── cards.css                # Cards
│   ├── inputs.css               # Inputs
│   ├── badges.css               # Badges
│   ├── skeleton.css             # Loading skeletons
│   ├── toast.css                # Notifications
│   ├── modal.css                # Modals
│   ├── shortcuts.css            # Keyboard shortcut display
│   └── search.css               # Search bar
├── features/                    # Feature-specific styles
│   ├── meta-panel.css           # Metadata panel
│   ├── workflow-graph.css       # Workflow SVG graph
│   ├── gallery.css              # Masonry gallery
│   ├── lightbox.css             # Fullscreen lightbox
│   └── cutout.css               # Cutout panel
└── utils/
    └── responsive.css           # Media queries and responsive helpers
```

---

## Custom Properties

Shared values should live in `base/variables.css`.

### Colors

```css
:root {
    --color-bg-primary: #1a1a2e;
    --color-bg-secondary: #16213e;
    --color-bg-tertiary: #0f3460;

    --color-text-primary: #e6e6e6;
    --color-text-secondary: #a0a0a0;
    --color-text-muted: #666;

    --color-accent: #4a90d9;
    --color-accent-hover: #5aa0e9;

    --color-border: #333;
    --color-border-light: #444;

    --color-success: #27ae60;
    --color-warning: #f39c12;
    --color-error: #e74c3c;
}
```

### Workflow Category Colors

```css
:root {
    --color-model: #9b59b6;
    --color-prompt: #27ae60;
    --color-sampler: #e67e22;
    --color-image-settings: #3498db;
    --color-post-processing: #e91e63;
    --color-lora: #f1c40f;
    --color-other: #95a5a6;
}
```

### Spacing

```css
:root {
    --spacing-xs: 4px;
    --spacing-sm: 8px;
    --spacing-md: 16px;
    --spacing-lg: 24px;
    --spacing-xl: 32px;
    --spacing-2xl: 48px;
}
```

### Typography

```css
:root {
    --font-family: 'Inter', -apple-system, BlinkMacSystemFont, sans-serif;
    --font-size-xs: 10px;
    --font-size-sm: 12px;
    --font-size-md: 14px;
    --font-size-lg: 16px;
    --font-size-xl: 20px;
    --font-size-2xl: 24px;
    --font-weight-normal: 400;
    --font-weight-medium: 500;
    --font-weight-bold: 600;
}
```

### Borders, Radius, Shadows, and Layers

```css
:root {
    --border-width: 1px;
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-full: 9999px;

    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.4);
    --shadow-xl: 0 16px 32px rgba(0, 0, 0, 0.5);

    --z-sidebar: 100;
    --z-header: 200;
    --z-dropdown: 300;
    --z-modal: 400;
    --z-lightbox: 500;
    --z-toast: 600;
}
```

---

## Base Styles

Base styles define browser resets, default typography, and shared animations.

### `reset.css`

```css
*, *::before, *::after {
    box-sizing: border-box;
    margin: 0;
    padding: 0;
}

body {
    font-family: var(--font-family);
    font-size: var(--font-size-md);
    color: var(--color-text-primary);
    background: var(--color-bg-primary);
    line-height: 1.5;
}
```

### `typography.css`

```css
h1 { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); }
h2 { font-size: var(--font-size-xl); font-weight: var(--font-weight-bold); }
h3 { font-size: var(--font-size-lg); font-weight: var(--font-weight-medium); }

code, pre {
    font-family: 'Fira Code', monospace;
    font-size: var(--font-size-sm);
}
```

### `animations.css`

Common animations include shimmer loading, fade in/out, slide transitions, and spinner rotation.

---

## Layout Styles

Layout files define the app shell and major panes.

### `app-shell.css`

```css
.app-shell {
    display: grid;
    grid-template-columns: var(--sidebar-width, 320px) 1fr;
    height: 100vh;
    overflow: hidden;
}
```

### `sidebar.css`

```css
.sidebar {
    width: var(--sidebar-width, 320px);
    background: var(--color-bg-secondary);
    border-right: var(--border-width) solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}
```

### `content.css`

```css
.content {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.content__body {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-md);
}
```

---

## Components

Component files should define reusable UI pieces that can appear in multiple features.

Examples:

| File | Purpose |
|------|---------|
| `buttons.css` | Primary, secondary, danger, and icon buttons |
| `cards.css` | Image/gallery cards |
| `inputs.css` | Inputs, path boxes, form controls |
| `badges.css` | Format/dimension/status labels |
| `skeleton.css` | Loading placeholders |
| `toast.css` | Notifications |
| `modal.css` | Modal surfaces |
| `shortcuts.css` | Shortcut key display |
| `search.css` | Search bar |

Example component:

```css
.btn {
    display: inline-flex;
    align-items: center;
    gap: var(--spacing-sm);
    padding: var(--spacing-sm) var(--spacing-md);
    border: var(--border-width) solid var(--color-border);
    border-radius: var(--radius-md);
    background: var(--color-bg-secondary);
    color: var(--color-text-primary);
    cursor: pointer;
    transition: all 0.2s;
}
```

---

## Feature Styles

Feature files style larger UI surfaces that map to application behavior.

| File | Purpose |
|------|---------|
| `meta-panel.css` | Summary/Workflow/Raw metadata panel |
| `workflow-graph.css` | SVG node graph and node details |
| `gallery.css` | Gallery/grid browsing |
| `lightbox.css` | Fullscreen image viewer |
| `cutout.css` | Cutout preview and actions |

Feature CSS can compose component classes but should avoid redefining generic button/card/input rules.

---

## Responsive Utilities

`utils/responsive.css` contains media queries and responsive adjustments.

Recommended behavior:

- Preserve desktop-first productivity layout.
- Collapse or hide secondary panels on narrow screens.
- Keep the lightbox usable on touch devices.
- Avoid fixed-width assumptions outside major panes.

---

## Naming Guidelines

Use predictable, BEM-like naming:

```css
.block {}
.block__element {}
.block--modifier {}
```

Examples:

```css
.sidebar {}
.sidebar__item {}
.sidebar__item--active {}

.meta-panel {}
.meta-panel__tab {}
.meta-panel__tab--active {}

.workflow-node {}
.workflow-node--model {}
```

Guidelines:

- Use nouns for blocks: `sidebar`, `lightbox`, `meta-panel`.
- Use elements for internal parts: `__header`, `__body`, `__button`.
- Use modifiers for state/variant: `--active`, `--disabled`, `--danger`.
- Avoid overly deep selectors when a class would be clearer.

---

## Extension Guidelines

When adding styles:

1. Put shared values in `base/variables.css`.
2. Put reusable UI rules in `components/`.
3. Put feature-specific rules in `features/`.
4. Keep layout rules in `layout/`.
5. Add responsive adjustments in `utils/responsive.css` when possible.
6. Reuse existing custom properties instead of hardcoding repeated values.
7. Prefer adding a new class over chaining fragile descendant selectors.
