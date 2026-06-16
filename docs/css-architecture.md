# CSS Architecture

> Архитектура CSS стилей Comfy Meta Viewer.

---

## Table of Contents

- [Обзор](#обзор)
- [Структура](#структура)
- [Custom Properties](#custom-properties)
- [Base](#base)
- [Layout](#layout)
- [Components](#components)
- [Features](#features)
- [Utils](#utils)
- [Именование](#именование)

---

## Обзор

CSS построен на **Custom Properties** (CSS Variables) с модульной структурой. Нет препроцессоров (SASS/LESS) -- чистый CSS.

### Принципы

1. **Custom Properties** для всего (цвета, spacing, typography)
2. **Один файл = одна область** ответственности
3. **Минимум !important**
4. **Mobile-first** responsive design

---

## Структура

```
app/static/css/
├── base/                        # Базовые стили
│   ├── variables.css            # CSS custom properties
│   ├── reset.css                # Normalize/reset
│   ├── typography.css           # Шрифты, текст
│   └── animations.css           # Кейфреймы
├── layout/                      # Структура страницы
│   ├── app-shell.css            # Главный контейнер
│   ├── sidebar.css              # Sidebar
│   └── content.css              # Основной контент
├── components/                  # UI компоненты
│   ├── buttons.css              # Кнопки
│   ├── cards.css                # Карточки
│   ├── inputs.css               # Инпуты
│   ├── badges.css               # Бейджи
│   ├── skeleton.css             # Skeleton loading
│   ├── toast.css                # Уведомления
│   ├── modal.css                # Модальные окна
│   ├── shortcuts.css            # Keyboard shortcuts
│   └── search.css               # Search bar
├── features/                    # Feature-специфичные стили
│   ├── meta-panel.css           # Metadata panel
│   ├── workflow-graph.css       # Workflow SVG graph
│   ├── gallery.css              # Masonry gallery
│   ├── lightbox.css             # Fullscreen lightbox
│   └── cutout.css               # Cutout panel
└── utils/
    └── responsive.css           # Media queries
```

---

## Custom Properties

### Цвета (`variables.css`)

```css
:root {
    /* Background */
    --color-bg-primary: #1a1a2e;
    --color-bg-secondary: #16213e;
    --color-bg-tertiary: #0f3460;

    /* Text */
    --color-text-primary: #e6e6e6;
    --color-text-secondary: #a0a0a0;
    --color-text-muted: #666;

    /* Accent */
    --color-accent: #4a90d9;
    --color-accent-hover: #5aa0e9;

    /* Borders */
    --color-border: #333;
    --color-border-light: #444;

    /* Status */
    --color-success: #27ae60;
    --color-warning: #f39c12;
    --color-error: #e74c3c;

    /* Category colors (workflow graph) */
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

### Borders & Radius

```css
:root {
    --border-width: 1px;
    --radius-sm: 4px;
    --radius-md: 8px;
    --radius-lg: 12px;
    --radius-full: 9999px;
}
```

### Shadows

```css
:root {
    --shadow-sm: 0 1px 2px rgba(0, 0, 0, 0.3);
    --shadow-md: 0 4px 8px rgba(0, 0, 0, 0.3);
    --shadow-lg: 0 8px 16px rgba(0, 0, 0, 0.4);
    --shadow-xl: 0 16px 32px rgba(0, 0, 0, 0.5);
}
```

### Z-Index

```css
:root {
    --z-sidebar: 100;
    --z-header: 200;
    --z-dropdown: 300;
    --z-modal: 400;
    --z-lightbox: 500;
    --z-toast: 600;
}
```

---

## Base

### `reset.css`

Базовый reset стилей:

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

Типографика:

```css
h1 { font-size: var(--font-size-2xl); font-weight: var(--font-weight-bold); }
h2 { font-size: var(--font-size-xl); font-weight: var(--font-weight-bold); }
h3 { font-size: var(--font-size-lg); font-weight: var(--font-weight-medium); }

code, pre {
    font-family: 'Fira Code', monospace;
    font-size: var(--font-size-sm);
}

a {
    color: var(--color-accent);
    text-decoration: none;
}

a:hover {
    color: var(--color-accent-hover);
}
```

### `animations.css`

Кейфреймы:

```css
@keyframes shimmer {
    0% { background-position: -200px 0; }
    100% { background-position: calc(200px + 100%) 0; }
}

@keyframes fadeIn {
    from { opacity: 0; }
    to { opacity: 1; }
}

@keyframes slideUp {
    from { transform: translateY(10px); opacity: 0; }
    to { transform: translateY(0); opacity: 1; }
}

@keyframes spin {
    from { transform: rotate(0deg); }
    to { transform: rotate(360deg); }
}
```

---

## Layout

### `app-shell.css`

Главный контейнер:

```css
.app-shell {
    display: grid;
    grid-template-columns: var(--sidebar-width, 320px) 1fr;
    height: 100vh;
    overflow: hidden;
}
```

### `sidebar.css`

Sidebar:

```css
.sidebar {
    width: var(--sidebar-width, 320px);
    background: var(--color-bg-secondary);
    border-right: var(--border-width) solid var(--color-border);
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.sidebar__resize-handle {
    width: 4px;
    cursor: col-resize;
    background: transparent;
    transition: background 0.2s;
}

.sidebar__resize-handle:hover {
    background: var(--color-accent);
}
```

### `content.css`

Основной контент:

```css
.content {
    display: flex;
    flex-direction: column;
    overflow: hidden;
}

.content__header {
    display: flex;
    align-items: center;
    padding: var(--spacing-md);
    border-bottom: var(--border-width) solid var(--color-border);
}

.content__body {
    flex: 1;
    overflow-y: auto;
    padding: var(--spacing-md);
}
```

---

## Components

### `buttons.css`

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

.btn:hover {
    background: var(--color-bg-tertiary);
    border-color: var(--color-accent);
}

.btn--primary {
    background: var(--color-accent);
    border-color: var(--color-accent);
    color: white;
}

.btn--danger {
    background: var(--color-error);
    border-color: var(--color-error);
    color: white;
}
```

### `cards.css`

```css
.card {
    background: var(--color-bg-secondary);
    border: var(--border-width) solid var(--color-border);
    border-radius: var(--radius-md);
    overflow: hidden;
    transition: all 0.2s;
}

.card:hover {
    border-color: var(--color-accent);
    box-shadow: var(--shadow-md);
}

.card__image {
    width: 100%;
    aspect-ratio: 1;
    object-fit: cover;
}

.card__body {
    padding: var(--spacing-md);
}
```

### `badges.css`

```css
.badge {
    display: inline-flex;
    align-items: center;
    padding: 2px var(--spacing-sm);
    border-radius: var(--radius-full);
    font-size: var(--font-size-xs);
    font-weight: var(--font-weight-medium);
}

.badge--format {
    background: var(--color-accent);
    color: white;
}

.badge--dimensions {
    background: var(--color-bg-tertiary);
    color: var(--color-text-secondary);
}
```

### `skeleton.css`

```css
.skeleton {
    background: linear-gradient(
        90deg,
        var(--color-bg-secondary) 25%,
        var(--color-bg-tertiary) 50%,
        var(--color-bg-secondary) 75%
    );
    background-size: 200px 100%;
    animation: shimmer 1.5s infinite;
    border-radius: var(--radius-md);
}
```

---

## Features

### `meta-panel.css`

```css
.meta-panel {
    width: 380px;
    background: var(--color-bg-secondary);
    border-left: var(--border-width) solid var(--color-border);
    display: flex;
    flex-direction: column;
}

.meta-panel__tabs {
    display: flex;
    border-bottom: var(--border-width) solid var(--color-border);
}

.meta-panel__tab {
    flex: 1;
    padding: var(--spacing-sm) var(--spacing-md);
    background: transparent;
    border: none;
    color: var(--color-text-secondary);
    cursor: pointer;
    transition: all 0.2s;
}

.meta-panel__tab--active {
    color: var(--color-accent);
    border-bottom: 2px solid var(--color-accent);
}
```

### `gallery.css`

```css
.gallery {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
    gap: var(--spacing-md);
}

.gallery__item {
    break-inside: avoid;
    cursor: pointer;
}

.gallery__image {
    width: 100%;
    border-radius: var(--radius-md);
    transition: transform 0.2s;
}

.gallery__image:hover {
    transform: scale(1.02);
}
```

### `lightbox.css`

```css
.lightbox {
    position: fixed;
    inset: 0;
    z-index: var(--z-lightbox);
    background: rgba(0, 0, 0, 0.95);
    display: flex;
    align-items: center;
    justify-content: center;
}

.lightbox__image {
    max-width: 90vw;
    max-height: 90vh;
    object-fit: contain;
    transition: transform 0.2s;
}

.lightbox__controls {
    position: absolute;
    bottom: var(--spacing-lg);
    left: 50%;
    transform: translateX(-50%);
    display: flex;
    gap: var(--spacing-sm);
}
```

---

## Utils

### `responsive.css`

```css
/* Mobile */
@media (max-width: 767px) {
    .app-shell {
        grid-template-columns: 1fr;
    }

    .sidebar {
        position: fixed;
        left: -100%;
        z-index: var(--z-sidebar);
        transition: left 0.3s;
    }

    .sidebar--open {
        left: 0;
    }

    .meta-panel {
        position: fixed;
        bottom: 0;
        left: 0;
        right: 0;
        width: 100%;
        max-height: 60vh;
    }
}

/* Tablet */
@media (min-width: 768px) and (max-width: 1023px) {
    .app-shell {
        grid-template-columns: 280px 1fr;
    }
}

/* Desktop */
@media (min-width: 1024px) {
    .app-shell {
        grid-template-columns: var(--sidebar-width, 320px) 1fr;
    }
}
```

---

## Именование

### BEM-like паттерн

```css
.block {}                    /* Компонент */
.block__element {}           /* Элемент */
.block--modifier {}          /* Модификатор */

/* Примеры: */
.sidebar {}
.sidebar__header {}
.sidebar__item {}
.sidebar__item--active {}
.sidebar__item--selected {}
```

### State classes

```css
.is-active {}                /* Активное состояние */
.is-loading {}               /* Загрузка */
.is-hidden {}                /* Скрыто */
.is-error {}                 /* Ошибка */
```
