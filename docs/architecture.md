# Architecture

> Comfy Meta Viewer -- архитектура и структура проекта.

## Обзор

```
┌─────────────────────────────────────────────────────────────────┐
│                        Browser (SPA)                            │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Sidebar  │  │ Gallery  │  │ Lightbox │  │  Meta Panel   │  │
│  │          │  │          │  │          │  │ Summary/WF/Raw│  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  Search  │  │ Cutout   │  │ Workflow │  │ Keyboard/Help │  │
│  │  (Fuse)  │  │  Panel   │  │  Graph   │  │   Center      │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │ REST API (JSON)
┌───────────────────────────┴─────────────────────────────────────┐
│                     Flask Backend (Python)                       │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌───────────────┐  │
│  │  main.py │  │database.py│ │extractor │  │   cutout.py   │  │
│  │  Routes  │  │  SQLite  │  │ Metadata │  │ BG Removal    │  │
│  └──────────┘  └──────────┘  └──────────┘  └───────────────┘  │
└───────────────────────────┬─────────────────────────────────────┘
                            │
                ┌───────────┴───────────┐
                │   SQLite Database     │
                │  ┌───────┐ ┌───────┐  │
                │  │folders│ │images │  │
                │  └───────┘ └───────┘  │
                │  ┌────────────────┐   │
                │  │    sessions    │   │
                │  └────────────────┘   │
                └───────────────────────┘
```

## Стек технологий

| Слой | Технология | Версия | Назначение |
|------|-----------|--------|------------|
| Backend | Python | 3.10+ | Язык серверной логики |
| HTTP Framework | Flask | 3.1 | REST API, раздача static |
| ORM/БД | SQLite3 | встроенный | Хранилище метаданных |
| Валидация | Pydantic | 2.0 | Request/Response модели |
| Изображения | Pillow | 11.0 | Извлечение мета, thumbnails, cutout |
| Frontend | Vanilla JS | ES Modules | Без фреймворков |
| CSS | Custom Properties | -- | Модульная архитектура |
| Поиск | Fuse.js | 7.0 | Fuzzy search |
| Зависимости | Poetry | -- | Управление пакетами |

## Структура каталогов

```
comfy-meta-viewer/
├── app/                          # Python backend + Frontend static
│   ├── main.py                   # Flask app, 18 API routes
│   ├── database.py               # SQLite CRUD (3 tables)
│   ├── extractor.py              # Metadata parsing (PNG/JPG/WEBP)
│   ├── cutout.py                 # Background removal (heuristic)
│   ├── schemas.py                # Pydantic models (14 штук)
│   ├── static/
│   │   ├── css/                  # Модульный CSS
│   │   │   ├── base/             # Variables, reset, typography
│   │   │   ├── layout/           # App shell, sidebar, content
│   │   │   ├── components/       # Buttons, cards, inputs, etc.
│   │   │   ├── features/         # Meta panel, workflow, gallery
│   │   │   └── utils/            # Responsive breakpoints
│   │   └── js/                   # Модульный JavaScript
│   │       ├── app.js            # Entry point
│   │       ├── state.js          # Reactive store
│   │       ├── api.js            # HTTP client
│   │       ├── events.js         # DOM event handlers
│   │       ├── gallery.js        # Masonry layout
│   │       ├── lightbox.js       # Fullscreen viewer
│   │       ├── meta-view.js      # Metadata tabs
│   │       ├── sessions.js       # Session management
│   │       ├── utils.js          # Helpers
│   │       ├── components/       # Reusable UI components
│   │       ├── features/         # Feature modules
│   │       └── vendor/           # Third-party (Fuse.js)
│   └── templates/
│       └── index.html            # SPA entry
├── cache/
│   ├── thumbnails/               # JPEG thumbnails (*.jpg)
│   └── cutouts/                  # Transparent PNGs (*.png)
├── .comfy_meta_uploads/
│   └── meta.db                   # SQLite database
├── dev_docs/                     # Internal dev docs & sprints
├── docs/                         # Public documentation
├── pyproject.toml                # Poetry config
├── start.bat                     # Windows launcher
└── start.sh                      # Linux/macOS launcher
```

## Data Flow

### 1. Сканирование папки

```
User drops folder
       │
       ▼
  POST /api/scan {"path": "..."}
       │
       ▼
  database.py: find_or_create_folder()
       │
       ▼
  extractor.py: scan_directory()
       │
       ├──► Walk tree, filter *.png/*.jpg/*.webp
       │
       ├──► For each image:
       │      extractor.parse_metadata(path)
       │        ├──► PNG: read tEXt/iTXt chunks
       │        ├──► JPG: read EXIF
       │        └──► Parse ComfyUI workflow JSON
       │
       ├──► database.py: insert_images(rows)
       │
       └──► Return {folder_id, images_count, page}
```

### 2. Загрузка изображений (drag-drop)

```
User drops files
       │
       ▼
  POST /api/upload (multipart/form-data)
       │
       ▼
  main.py: save to .comfy_meta_uploads/{uuid}_{name}
       │
       ├──► extractor.parse_metadata(saved_path)
       ├──► database.py: insert with original_data BLOB
       └──► Return {images: [...]}
```

### 3. Просмотр метаданных

```
User clicks image
       │
       ▼
  GET /api/images/{id}
       │
       ▼
  database.py: get_image(id)
       │
       ├──► Deserialize metadata_json
       ├──► Parse workflow if present
       └──► Return full ImageDetail
```

## Database Schema

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY,
    path TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    scanned_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE images (
    id INTEGER PRIMARY KEY,
    folder_id INTEGER NOT NULL,
    rel_path TEXT NOT NULL,
    file_name TEXT NOT NULL,
    file_size INTEGER,
    file_mtime REAL,
    format TEXT,
    width INTEGER,
    height INTEGER,
    mode TEXT,
    error TEXT,
    metadata_json TEXT,
    thumbnail_b64 TEXT,
    original_data BLOB,
    FOREIGN KEY (folder_id) REFERENCES folders(id)
        ON DELETE CASCADE
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    folder_id INTEGER,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (folder_id) REFERENCES folders(id)
        ON DELETE SET NULL
);

CREATE INDEX idx_images_folder ON images(folder_id);
CREATE INDEX idx_images_folder_mtime ON images(folder_id, file_mtime);
```

## Модули Frontend

### State Management (`state.js`)

```
state.js
  ├── images[]           -- массив текущих изображений
  ├── activeIndex        -- индекс выбранного изображения
  ├── sessions[]         -- список сессий
  ├── currentSession     -- текущая сессия
  ├── viewMode           -- 'list' | 'gallery'
  ├── folderId           -- ID текущей папки
  ├── folders[]          -- список папок
  ├── page / perPage     -- пагинация
  ├── hasMore            -- флаг для infinite scroll
  └── isLoading          -- флаг загрузки
```

Все состояния сохраняются в `sessionStorage` для восстановления при обновлении страницы.

### API Client (`api.js`)

```
api.js
  ├── scanFolder(path)           -- POST /api/scan
  ├── loadFromPaths(paths)       -- POST /api/extract
  ├── loadFromFiles(files)       -- POST /api/upload
  ├── loadMore()                 -- GET  /api/images?page=N
  ├── deleteImageAt(id)          -- DELETE /api/images/{id}
  ├── loadFolderImages(id)       -- GET  /api/images?folder_id=N
  ├── getFolders()               -- GET  /api/folders
  ├── deleteFolderFromServer(id) -- DELETE /api/folders/{id}
  ├── getCutout(id)              -- GET  /api/cutout/{id}
  ├── createCutout(id)           -- POST /api/cutout/{id}
  ├── deleteCutout(id)           -- DELETE /api/cutout/{id}
  └── getThumbnail(id)           -- GET  /api/thumbnail/{id}
```

### Feature Modules

| Модуль | Файл | Описание |
|--------|------|----------|
| Sidebar | `features/sidebar.js` | Resizable sidebar, image list, folder browser |
| Workflow Graph | `features/workflow-graph.js` | SVG визуализация ComfyUI нод |
| Keyboard | `features/keyboard.js` | 14 shortcuts + Help Center |
| Cutout | `features/cutout.js` | Panel для удаления фона |
| Gallery | `gallery.js` | Masonry layout + lazy loading |
| Lightbox | `lightbox.js` | Fullscreen viewer + zoom/rotate |
| Meta View | `meta-view.js` | 3 tabs: Summary, Workflow, Raw |
| Search | `components/search-bar.js` | Fuse.js fuzzy search |

## Безопасность

- Нет аутентификации (локальный инструмент)
- Оригинальные файлы хранятся как BLOB в SQLite для uploaded файлов
- При сканировании файлы не копируются (in-place)
- Thumbnail и cutout кэш хранятся на диске

## Расширяемость

- **Новые форматы**: добавить обработчик в `extractor.py`
- **Новые endpoints**: добавить route в `main.py` + Pydantic модель в `schemas.py`
- **Новые features**: создать модуль в `features/` + CSS в `features/`
- **Новые компоненты**: добавить в `components/` + CSS в `components/`
