# Features

> Полное описание всех возможностей Comfy Meta Viewer.

---

## Table of Contents

- [Metadata Extraction](#metadata-extraction)
- [ComfyUI Workflow Visualization](#comfyui-workflow-visualization)
- [Folder Scanning](#folder-scanning)
- [SQLite Persistence](#sqlite-persistence)
- [Gallery View](#gallery-view)
- [Lightbox](#lightbox)
- [Fuzzy Search](#fuzzy-search)
- [Object Cutout](#object-cutout)
- [Keyboard Shortcuts](#keyboard-shortcuts)
- [Skeleton Loading](#skeleton-loading)
- [Resizable Sidebar](#resizable-sidebar)
- [Session Management](#session-management)
- [Drag-and-Drop Upload](#drag-and-drop-upload)
- [Thumbnails](#thumbnails)
- [Diagnostics](#diagnostics)
- [Hard Reset](#hard-reset)
- [Paste Path](#paste-path)
- [Responsive Design](#responsive-design)

---

## Metadata Extraction

**Файл:** `app/extractor.py` (540 строк)

Автоматическое извлечение метаданных из изображений, сгенерированных ComfyUI.

### Поддерживаемые форматы

| Формат | Источник метаданных | Поддержка |
|--------|-------------------|-----------|
| PNG | tEXt, iTXt chunks | Полная |
| JPEG | EXIF + комментарии | Полная |
| WEBP | EXIF | Базовая |
| BMP | -- | Только размеры |
| TIFF | EXIF | Базовая |

### Извлекаемые данные

| Категория | Поля |
|-----------|------|
| **Prompt** | Положительный промпт, негативный промпт |
| **Settings** | Steps, Sampler, Scheduler, CFG, Seed, Denoise, Batch Size |
| **Model** | Имя основной модели, VAE |
| **LoRA** | Список используемых LoRA + weights |
| **Resolution** | Width, Height |
| **Workflow** | Полная структура нод ComfyUI |
| **EXIF** | Camera, lens, ISO, shutter, aperture |
| **Raw** | Оригинальные текстовые чанки |

### Парсинг workflow

Извлекает JSON workflow из PNG chunks в двух форматах:
- **API format** (prompt JSON): `{node_id: {class_type, inputs}}`
- **UI format** (с координатами нод): `{last_node_id, nodes[], links[]}`

---

## ComfyUI Workflow Visualization

**Файл:** `app/static/js/features/workflow-graph.js` (289 строк)

SVG-визуализация графа генерации ComfyUI.

### Возможности

- Интерактивный SVG-граф нод
- Цветовая кодировка по категориям:
  - **Models** -- фиолетовый
  - **Prompts** -- зеленый
  - **Sampler** -- оранжевый
  - **Image Settings** -- синий
  - **Post Processing** -- розовый
  - **LoRA** -- желтый
  - **Other** -- серый
- Cubic bezier соединения между нодами
- Pan/zoom для навигации
- Выбор ноды для просмотра деталей
- Подсветка при наведении

### Управление

| Действие | Описание |
|----------|----------|
| Click на ноду | Выбор, показ деталей |
| Drag | Pan графа |
| Scroll | Zoom in/out |

---

## Folder Scanning

**Файл:** `app/main.py` (POST /api/scan)

In-place сканирование папок без копирования файлов.

### Особенности

- Рекурсивный обход директорий
- Фильтрация по расширениям: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
- Инкрементальное сканирование через `mtime`
- Автоматическая генерация thumbnails
- Сохранение метаданных в SQLite

### Алгоритм

```
1. Принять путь к папке
2. Найти или создать запись в folders
3. Рекурсивно обойти дерево
4. Для каждого файла:
   a. Проверить расширение
   b. Сравнить mtime с сохраненным
   c. Если новый/измененный:
      - Извлечь метаданные
      - Сгенерировать thumbnail
      - Вставить в БД
5. Вернуть folder_id + count
```

---

## SQLite Persistence

**Файл:** `app/database.py` (451 строк)

Хранение всех данных в SQLite с WAL mode.

### Таблицы

| Таблица | Описание | Ключевые поля |
|---------|----------|---------------|
| `folders` | Папки с изображениями | id, path, name, scanned_at |
| `images` | Изображения + метаданные | id, folder_id FK, rel_path, metadata_json, original_data BLOB |
| `sessions` | Пользовательские сессии | id, name, folder_id FK |

### Особенности

- WAL mode для лучшей производительности
- Foreign keys с CASCADE delete
- Индексы для быстрого поиска
- `original_data` BLOB для uploaded файлов
- `metadata_json` TEXT для хранения полных метаданных

---

## Gallery View

**Файл:** `app/static/js/gallery.js`

Masonry layout для просмотра изображений.

### Возможности

- Masonry (waterfall) раскладка
- Lazy loading через `IntersectionObserver`
- Skeleton placeholders при загрузке
- Infinite scroll
- Переключение list/gallery views

---

## Lightbox

**Файл:** `app/static/js/lightbox.js`

Fullscreen просмотр изображений.

### Управление

| Горячая клавиша | Действие |
|----------------|----------|
| `←` / `→` | Навигация между изображениями |
| `+` / `-` | Zoom in / out |
| `R` | Поворот на 90° |
| `F` | Toggle fullscreen |
| `Esc` | Закрыть |
| Mouse wheel | Zoom |
| Drag | Панорамирование (при zoom) |
| Swipe (touch) | Навигация на мобильных |

### Возможности

- Zoom: 0.1x -- 10x
- Поворот: 90° шаги
- Touch swipe навигация
- Метаданные panel toggle
- Download
- Copy all metadata

---

## Fuzzy Search

**Файл:** `app/static/js/components/search-bar.js`

Нечёткий поиск через Fuse.js.

### Поиск по полям

| Поле | Вес |
|------|-----|
| `file_name` | Высокий |
| `format` | Средний |
| `metadata.prompt` | Высокий |
| `metadata.settings.model` | Средний |
| `metadata.settings.sampler` | Средний |

### Горячая клавиша

`Ctrl+F` -- открыть поиск

---

## Object Cutout

**Файл:** `app/cutout.py` (103 строки) + `app/static/js/features/cutout.js` (149 строк)

Автоматическое удаление фона и экспорт transparent PNG.

### Алгоритм

```
1. Проверить alpha-канал:
   - Если < 10% transparent → fallback к background estimation

2. Background estimation:
   - Взять полоски 10px по краям (top, bottom, left, right)
   - Средний цвет = background color

3. Создать mask:
   - Евклидово расстояние от background
   - Threshold: расстояние > порога → foreground

4. Морфологические фильтры:
   - Закрытие (closing) для заполнения дыр
   - Медианный фильтр для шума

5. Gaussian blur для сглаживания краёв

6. Применить mask → transparent PNG
```

### Кэширование

- Cutout PNG кэшируются в `cache/cutouts/`
- При повторном запросе -- мгновенная отдача
- Очистка через `DELETE /api/cutout/{id}`

### Просмотр

- Checkerboard background для preview
- Download transparent PNG
- Regenerate (пересоздать)

---

## Keyboard Shortcuts

**Файл:** `app/static/js/features/keyboard.js` (324 строки)

14 горячих клавиш + Help Center.

### Shortcuts

| Клавиша | Действие |
|---------|----------|
| `←` / `→` | Предыдущее/следующее изображение |
| `↑` / `↓` | Scroll в sidebar |
| `Enter` | Открыть lightbox |
| `Escape` | Закрыть lightbox / панель |
| `Delete` | Удалить изображение |
| `Ctrl+F` | Поиск |
| `G` | Toggle gallery/list view |
| `Ctrl+Shift+R` | Hard reset |
| `?` | Help Center |
| `1-3` | Switch meta tabs (Summary/Workflow/Raw) |
| `D` | Toggle meta panel |
| `S` | Toggle sidebar |

### Help Center

4 вкладки:
1. **Shortcuts** -- все горячие клавиши
2. **Workflow** -- как работает ComfyUI workflow graph
3. **Storage** -- где хранятся данные
4. **Diagnostics** -- статистика системы

---

## Skeleton Loading

**Файл:** `app/static/js/components/skeleton.js`

Placeholder-ы при загрузке данных.

### Типы

- Sidebar items: прямоугольники с анимацией shimmer
- Gallery cards: квадраты с анимацией
- Meta view: строки текста

---

## Resizable Sidebar

**Файл:** `app/static/js/features/sidebar.js` (211 строк)

Sidebar с возможностью изменения ширины.

### Параметры

| Параметр | Значение |
|----------|----------|
| Min width | 280px |
| Max width | 500px |
| Default | 320px |
| Handle width | 4px |

### Содержимое

- Image list с thumbnails
- Folder browser (все просканированные папки)
- Infinite scroll sentinel
- Format/dimensions badges
- Delete button

---

## Session Management

**Файл:** `app/static/jssessions.js`

Группировка изображений по сессиям.

### Возможности

- Создание сессий с привязкой к папке
- Переименование
- Удаление
- Sync с backend API
- Сохранение в sessionStorage

---

## Drag-and-Drop Upload

**Файл:** `app/static/js/events.js`

Загрузка файлов через drag-and-drop.

### Поддерживаемые способы

| Способ | Описание |
|--------|----------|
| Drag & Drop | Перетаскивание файлов на окно |
| File Input | Кнопка "Choose Files" |
| Folder Input | Кнопка "Choose Folder" |
| Paste Path | Вставка пути из буфера обмена |

### Поведение

- Множественная загрузка
- Прогресс-индикация
- Автоматическое извлечение метаданных
- Сохранение original_data в БД

---

## Thumbnails

**Файл:** `app/extractor.py` + `app/main.py`

Lazy generation + disk cache.

### Формат

- JPEG quality: 85
- Max dimension: 300px
- Путь: `cache/thumbnails/{id}.jpg`

### Поведение

- Генерируются при первом запросе
- Кэшируются на диске
- При удалении изображения -- удаляется thumbnail

---

## Diagnostics

**Файл:** Help Center → Diagnostics tab

### Статистика

| Метрика | Описание |
|---------|----------|
| Folders | Количество просканированных папок |
| Images | Всего изображений в БД |
| Sessions | Количество сессий |
| Uploads | Загруженных файлов |
| Thumbnails | Сгенерированных thumbnails |
| Cutouts | Сгенерированных cutouts |

---

## Hard Reset

**Файл:** `app/main.py` (POST /api/reset)

Полная очистка всех данных.

### Что очищается

1. SQLite database (все таблицы)
2. Thumbnail cache (`cache/thumbnails/`)
3. Cutout cache (`cache/cutouts/`)
4. Upload folder (`.comfy_meta_uploads/`)

### Горячая клавиша

`Ctrl+Shift+R`

---

## Paste Path

**Файл:** `app/static/js/events.js`

Вставка пути к папке из буфера обмена.

### Поведение

- Ctrl+V → проверка содержит ли текст путь
- Если путь к папке → сканирование
- Если путь к файлам → извлечение метаданных

---

## Responsive Design

**Файл:** `app/static/css/utils/responsive.css`

Адаптивный дизайн для всех размеров экрана.

### Breakpoints

| Breakpoint | Описание |
|------------|----------|
| < 768px | Mobile:collapsed sidebar, stacked layout |
| 768-1024px | Tablet: resizable sidebar |
| > 1024px | Desktop: full layout |

### Адаптация

- Sidebar: collapsed на mobile, toggle кнопкой
- Gallery: fewer columns на маленьких экранах
- Lightbox: touch swipe на mobile
- Meta panel: bottom sheet на mobile
