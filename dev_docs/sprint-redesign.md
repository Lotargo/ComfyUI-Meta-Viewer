# Спринт: Полный редизайн UI

**Статус:** В процессе
**Начало:** 2026-06-16
**Цель:** Модульный редизайн фронтенда с улучшением UX

---

## Задачи

### Этап 1: Базовая структура CSS
- [ ] Создать `css/base/variables.css` (расширенные токены: отступы, тени, transition)
- [ ] Создать `css/base/reset.css`
- [ ] Создать `css/base/typography.css` (шрифты, размеры, line-height)
- [ ] Создать `css/layout/app-shell.css` (header + main layout)
- [ ] Создать `css/layout/sidebar.css` (resizable sidebar)
- [ ] Создать `css/layout/content.css` (content area + tabs)
- [ ] Обновить `index.html` — новая структура header/sidebar/content

### Этап 2: UI компоненты
- [ ] Создать `css/components/buttons.css` (primary, secondary, ghost, icon)
- [ ] Создать `css/components/cards.css` (meta cards, node cards)
- [ ] Создать `css/components/inputs.css` (search, file input)
- [ ] Создать `css/components/badges.css` (category badges, status)
- [ ] Создать `css/components/skeleton.css` (loading placeholders)
- [ ] Создать `css/components/toast.css`
- [ ] Создать `js/components/skeleton.js` (генератор skeleton HTML)

### Этап 3: Sidebar redesign
- [ ] CSS: resizable sidebar с drag handle
- [ ] CSS: улучшенные image items (hover preview, better active state)
- [ ] JS: `js/components/sidebar-item.js` (отдельный компонент)
- [ ] JS: sidebar resize logic (mousedown/mousemove)
- [ ] CSS: session headers (улучшенный дизайн)

### Этап 4: Content tabs + skeleton loading
- [ ] CSS: tab bar компонент (Summary / Workflow / Raw)
- [ ] JS: tab switching logic в `meta-view.js`
- [ ] CSS: skeleton loading для изображений и мета
- [ ] JS: skeleton вставка при загрузке
- [ ] Плавное появление контента (fade-in)

### Этап 5: Search (Fuse.js)
- [ ] Установить Fuse.js (CDN или локально)
- [ ] JS: `js/components/search-bar.js` (input + results)
- [ ] JS: `js/api/client.js` (fetch wrapper с search endpoint)
- [ ] CSS: search results dropdown
- [ ] Подсветка совпадений в sidebar
- [ ] Keyboard shortcut: Ctrl+F → focus search

### Этап 6: Workflow SVG граф
- [ ] JS: `js/features/workflow-graph.js` (SVG генерация)
- [ ] CSS: `css/features/workflow-graph.css` (node styles, connections)
- [ ] Расчёт позиций нод (simple tree layout)
- [ ] SVG линии между нодами (links)
- [ ] Zoom/pan мышью
- [ ] Click на ноду → expand details

### Этап 7: Keyboard shortcuts
- [ ] JS: `js/features/keyboard.js` (event listener)
- [ ] Shortcuts: ←/→ навигация, Esc закрыть, / поиск, 1/2/3 tabs
- [ ] CSS: shortcuts overlay (? для показа)
- [ ] JS: shortcuts overlay component

### Этап 8: Responsive
- [ ] CSS: `css/utils/responsive.css` (media queries)
- [ ] Mobile: collapsible sidebar (hamburger)
- [ ] Tablet: stacking layout
- [ ] Lightbox: full-width на узких экранах

### Этап 9: Gallery masonry
- [ ] Установить masonry layout (CSS grid или minimal lib)
- [ ] CSS: `css/features/gallery.css` (masonry grid)
- [ ] Hover preview卡片
- [ ] Lazy loading для thumbnails

### Этап 10: Lightbox improvements
- [ ] Toggleable metadata panel (кнопка show/hide)
- [ ] Улучшенная навигация (swipe на тач-устройствах)
- [ ] Zoom in/out
- [ ] Download button

---

## Зависимости

| Пакет | Статус | Где используется |
|-------|--------|------------------|
| Fuse.js | [ ] Добавить | Search по метаданным |
| Masonry | [ ] Решить: CSS grid или lib | Gallery view |

---

## Файловая структура (целевая)

```
app/static/
├── css/
│   ├── base/
│   │   ├── variables.css
│   │   ├── reset.css
│   │   └── typography.css
│   ├── layout/
│   │   ├── app-shell.css
│   │   ├── sidebar.css
│   │   └── content.css
│   ├── components/
│   │   ├── buttons.css
│   │   ├── cards.css
│   │   ├── inputs.css
│   │   ├── badges.css
│   │   ├── skeleton.css
│   │   └── toast.css
│   ├── features/
│   │   ├── gallery.css
│   │   ├── lightbox.css
│   │   ├── meta-panel.css
│   │   ├── workflow-graph.css
│   │   └── sessions.css
│   └── utils/
│       ├── animations.css
│       ├── responsive.css
│       └── scrollbar.css
├── js/
│   ├── core/
│   │   ├── app.js
│   │   └── state.js
│   ├── api/
│   │   └── client.js
│   ├── components/
│   │   ├── search-bar.js
│   │   ├── sidebar-item.js
│   │   ├── category-card.js
│   │   ├── node-card.js
│   │   ├── skeleton.js
│   │   └── toast.js
│   ├── features/
│   │   ├── sidebar.js
│   │   ├── gallery.js
│   │   ├── lightbox.js
│   │   ├── meta-view.js
│   │   ├── workflow-graph.js
│   │   ├── sessions.js
│   │   └── keyboard.js
│   └── utils/
│       ├── dom.js
│       ├── format.js
│       └── clipboard.js
└── js/vendor/          # Внешние библиотеки
    └── fuse.min.js
```

---

## Примечания

- Сохраняем vanilla JS без фреймворков
- CSS без препроцессора (чистый CSS с custom properties)
- Все новые CSS файлы подключать в index.html
- Старые CSS файлы удалить после миграции
