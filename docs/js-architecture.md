# JavaScript Architecture

> Архитектура frontend JavaScript модулей Comfy Meta Viewer.

---

## Table of Contents

- [Обзор](#обзор)
- [Модули](#модули)
- [State Management](#state-management)
- [API Client](#api-client)
- [Event System](#event-system)
- [Feature Modules](#feature-modules)
- [Components](#components)
- [Vendor Libraries](#vendor-libraries)

---

## Обзор

Frontend построен на **Vanilla JavaScript** с использованием ES modules. Нет фреймворков (React, Vue, Svelte) -- чистый JS + DOM API.

### Модульная система

```
app.js (entry point)
├── state.js        (reactive store)
├── api.js          (HTTP client)
├── events.js       (DOM event handlers)
├── gallery.js      (masonry layout)
├── lightbox.js     (fullscreen viewer)
├── meta-view.js    (metadata display)
├── sessions.js     (session management)
├── utils.js        (helpers)
├── components/
│   ├── search-bar.js
│   ├── sidebar-item.js
│   └── skeleton.js
├── features/
│   ├── sidebar.js
│   ├── workflow-graph.js
│   ├── keyboard.js
│   └── cutout.js
└── vendor/
    └── fuse.min.js
```

---

## Модули

### `app.js` -- Entry Point

**Строка:** 1

Точка входа. Инициализирует все модули, восстанавливает состояние.

```javascript
// Инициализация:
// 1. state.js: restore from sessionStorage
// 2. events.js: bind all event listeners
// 3. gallery.js: init masonry
// 4. lightbox.js: init fullscreen
// 5. meta-view.js: init tabs
// 6. features/sidebar.js: init sidebar
// 7. features/keyboard.js: init shortcuts
// 8. features/cutout.js: init cutout panel
// 9. sessions.js: init session management
// 10. Load initial data
```

---

### `state.js` -- Global State

**Файл:** `app/static/js/state.js`

Реактивное хранилище состояния приложения.

```javascript
// Состояние:
{
    images: [],           // Текущий список изображений
    activeIndex: -1,      // Индекс выбранного изображения
    sessions: [],         // Все сессии
    currentSession: null, // Текущая сессия
    viewMode: 'list',     // 'list' | 'gallery'
    folderId: null,       // ID текущей папки
    folders: [],          // Все папки
    page: 1,              // Текущая страница
    perPage: 50,          // На страницу
    hasMore: true,        // Есть ещё данные
    isLoading: false      // Флаг загрузки
}
```

#### API

```javascript
import { state } from "./state.js";

// Получить значение
state.images      // []
state.activeIndex // -1

// Установить значение
state.images = newData;
state.activeIndex = 0;

// Сохранить в sessionStorage
saveState();

// Восстановить из sessionStorage
restoreState();
```

#### Сохранение

- `sessionStorage` для UI state (activeIndex, viewMode)
- Backend API для persistent data (folders, images, sessions)

---

### `api.js` -- HTTP Client

**Файл:** `app/static/js/api.js`

Все HTTP запросы к backend.

```javascript
// Основные функции:
scanFolder(path)            // POST /api/scan
loadFromPaths(paths)        // POST /api/extract
loadFromFiles(files)        // POST /api/upload
loadMore()                  // GET  /api/images?page=N
deleteImageAt(id)           // DELETE /api/images/{id}
loadFolderImages(id)        // GET  /api/images?folder_id=N
getFolders()                // GET  /api/folders
deleteFolderFromServer(id)  // DELETE /api/folders/{id}
getCutout(id)               // GET  /api/cutout/{id}
createCutout(id)            // POST /api/cutout/{id}
deleteCutout(id)            // DELETE /api/cutout/{id}
getThumbnail(id)            // GET  /api/thumbnail/{id}
```

#### Обработка ошибок

Все функции обрабатывают ошибки и возвращают `null` при ошибке:

```javascript
export async function scanFolder(path) {
    try {
        const res = await fetch("/api/scan", { ... });
        if (!res.ok) return null;
        return await res.json();
    } catch (e) {
        console.error("Scan failed:", e);
        return null;
    }
}
```

---

### `events.js` -- Event System

**Файл:** `app/static/js/events.js`

Обработка DOM событий.

#### Обработчики

| Событие | Элемент | Описание |
|---------|---------|----------|
| `drop` | window | Drag & drop файлов |
| `dragover` | window | Предотвращение default |
| `paste` | document | Ctrl+V (path paste) |
| `click` | various | Кнопки, tabs, items |
| `keydown` | document | Keyboard shortcuts |

#### Drag & Drop

```javascript
window.addEventListener("drop", async (e) => {
    e.preventDefault();
    const items = e.dataTransfer.items;

    // Проверка: files или folders
    const files = [];
    for (const item of items) {
        if (item.kind === "file") {
            const entry = item.webkitGetAsEntry();
            if (entry.isFile) files.push(entry);
            else if (entry.isDirectory) {
                // Рекурсивный обход
                const dirFiles = await readDirectory(entry);
                files.push(...dirFiles);
            }
        }
    }

    // Загрузка
    await loadFromFiles(files);
});
```

---

## Feature Modules

### `features/sidebar.js`

**Строк:** 211

Resizable sidebar с image list.

```javascript
// Функции:
initSidebar()              // Инициализация
setupResize()              // Drag-to-resize handle
renderImageList(images)    // Отрисовка списка
renderFolderList(folders)  // Отрисовка папок
loadMoreImages()           // Infinite scroll
```

#### Resize

```javascript
// Min: 280px, Max: 500px, Default: 320px
const MIN_WIDTH = 280;
const MAX_WIDTH = 500;

handle.addEventListener("mousedown", (e) => {
    const startX = e.clientX;
    const startWidth = sidebar.offsetWidth;

    const onMove = (e) => {
        const newWidth = startWidth + (e.clientX - startX);
        sidebar.style.width = Math.min(MAX_WIDTH, Math.max(MIN_WIDTH, newWidth)) + "px";
    };

    const onUp = () => {
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
    };

    document.addEventListener("mousemove", onMove);
    document.addEventListener("mouseup", onUp);
});
```

---

### `features/workflow-graph.js`

**Строк:** 289

SVG визуализация ComfyUI workflow.

```javascript
// Функции:
renderWorkflowGraph(workflow)  // Главная функция
createNode(node)               // Создание SVG node
createConnection(from, to)    // Создание SVG connection
colorForCategory(type)        // Цвет по категории
```

#### Категории нод

| Категория | Цвет | Типы нод |
|-----------|------|----------|
| Models | `#9b59b6` | CheckpointLoader, UNETLoader, etc. |
| Prompts | `#27ae60` | CLIPTextEncode, etc. |
| Sampler | `#e67e22` | KSampler, SamplerCustom, etc. |
| Image Settings | `#3498db` | EmptyLatentImage, ImageScale, etc. |
| Post Processing | `#e91e63` | ImageBlend, etc. |
| LoRA | `#f1c40f` | LoraLoader, etc. |
| Other | `#95a5a6` | Остальные |

---

### `features/keyboard.js`

**Строк:** 324

Keyboard shortcuts + Help Center.

```javascript
// Горячие клавиши:
// ArrowLeft/Right: навигация
// ArrowUp/Down: scroll sidebar
// Enter: открыть lightbox
// Escape: закрыть
// Delete: удалить
// Ctrl+F: поиск
// G: toggle gallery/list
// Ctrl+Shift+R: hard reset
// ?: help center
// 1-3: switch meta tabs
// D: toggle meta panel
// S: toggle sidebar
```

#### Help Center

```javascript
// 4 вкладки:
// 1. Shortcuts - все горячие клавиши
// 2. Workflow - как работает workflow graph
// 3. Storage - где хранятся данные
// 4. Diagnostics - статистика системы
```

---

### `features/cutout.js`

**Строк:** 149

Cutout panel: create, preview, download.

```javascript
// Функции:
initCutoutPanel()           // Инициализация
createCutout(imageId)       // Запрос cutout
downloadCutout(imageId)     // Скачать PNG
showPreview(url)            // Показать preview
```

---

## Components

### `components/search-bar.js`

Fuzzy search через Fuse.js.

```javascript
// Конфигурация Fuse.js:
{
    keys: [
        { name: "file_name", weight: 0.4 },
        { name: "format", weight: 0.2 },
        { name: "metadata.prompt", weight: 0.3 },
        { name: "metadata.settings.model", weight: 0.05 },
        { name: "metadata.settings.sampler", weight: 0.05 }
    ],
    threshold: 0.3,
    includeScore: true
}
```

---

### `components/sidebar-item.js`

Компонент sidebar item.

```javascript
// Шаблон:
<div class="sidebar-item">
    <img class="sidebar-item__thumb" src="/api/thumbnail/{id}">
    <div class="sidebar-item__info">
        <span class="sidebar-item__name">{file_name}</span>
        <span class="sidebar-item__meta">{format} {width}x{height}</span>
    </div>
    <button class="sidebar-item__delete">✕</button>
</div>
```

---

### `components/skeleton.js`

Skeleton loading компоненты.

```javascript
// Типы:
createSidebarSkeleton(count)   // Sidebar items skeleton
createGallerySkeleton(count)   // Gallery cards skeleton
createMetaSkeleton()           // Meta view skeleton
```

---

## Vendor Libraries

### Fuse.js v7.0.0

**Файл:** `app/static/js/vendor/fuse.min.js`

Локальная копия для offline использования.

**Назначение:** Fuzzy search по метаданным изображений.

**Версия:** 7.0.0 (последняя стабильная)
