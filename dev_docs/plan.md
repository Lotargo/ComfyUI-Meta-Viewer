# ComfyUI Meta Viewer — Plan рефакторинга

## 1. Текущие проблемы

### 1.1. Копирование файлов при выборе папки
- **Фронт**: `loadFromDirectory()` собирает `FileList` из `<input webkitdirectory>` и отправляет на `/api/upload`
- **Бэк**: `/api/upload` сохраняет файлы во временную папку, читает метаданные, затем удаляет (`tmp.unlink`)
- **Итог**: бесполезное копирование + потеря оригинального пути — пользователь не видит, откуда файл

### 1.2. Нет кэширования / БД
- Каждое открытие папки заново сканирует все файлы
- Нет транзакционности — при сбое в середине сканирования частичный результат уже ушёл на фронт
- Нет инкрементального обновления — повторное сканирование той же папки читает всё с нуля

### 1.3. Нет пагинации / виртуализации
- Весь список изображений загружается и рендерится сразу
- В папке с 10000+ файлов это приведёт к OOM на фронте и зависанию бэка

### 1.4. Фронт — потеря состояния
- При переключении табов браузера (или вызове `index()` повторно) Vue/React-подобного store нет — весь сброс в `let images = []`
- Нет сохранения в `sessionStorage`/`localStorage`

## 2. Предлагаемая архитектура

### 2.1. Бэкенд: SQLite + работа in-place

**Отказ от копирования**: новый эндпоинт `POST /api/scan` принимает путь к папке, работает с файлами в их оригинальном расположении.

```
POST /api/scan  { "path": "/path/to/folder" }
  → сканирует директорию (рекурсивно?)
  → читает метаданные
  → сохраняет в SQLite
  → возвращает список с пагинацией

GET /api/images?folder_id=X&page=1&per_page=50
  → читает из SQLite, возвращает указанную страницу
```

**SQLite схемы**:

```sql
CREATE TABLE folders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    path TEXT UNIQUE NOT NULL,
    name TEXT,
    scanned_at TEXT DEFAULT (datetime('now'))
);

CREATE TABLE images (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    folder_id INTEGER NOT NULL REFERENCES folders(id) ON DELETE CASCADE,
    rel_path TEXT NOT NULL,         -- путь относительно папки
    file_name TEXT NOT NULL,
    file_size INTEGER,
    file_mtime REAL,               -- mtime для инвалидации кэша
    format TEXT,
    width INTEGER,
    height INTEGER,
    mode TEXT,
    error TEXT,
    metadata_json TEXT,            -- весь extract_metadata() результат
    thumbnail_b64 TEXT,            -- base64 thumbnail (или хранить отдельно)
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(folder_id, rel_path)
);

CREATE INDEX idx_images_folder ON images(folder_id);
CREATE INDEX idx_images_folder_mtime ON images(folder_id, file_mtime);
```

**Транзакции**: всё сканирование папки — в одной транзакции.
Если что-то пошло — `ROLLBACK`, и папка не появится в списке.

**Инвалидация кэша**: сравниваем `file_mtime` — если не изменился, пропускаем (SKIP).

### 2.2. Эндпоинты API (новые)

| Метод | Путь | Описание |
|-------|------|----------|
| `GET` | `/api/folders` | Список просканированных папок |
| `POST` | `/api/scan` | Сканировать папку (с проверкой mtime) |
| `GET` | `/api/images?folder_id=&page=&per_page=&sort=` | Пагинированный список |
| `GET` | `/api/images/<id>/detail` | Полная метаинформация по одному файлу |
| `DELETE` | `/api/folders/<id>` | Удалить папку из БД |
| `POST` | `/api/upload` | **оставить** для ручных файлов (drag-drop) — сохранять как "без папки" |

### 2.3. Фронт: виртуализация + мемоизация + сохранение состояния

**Виртуализация**:
- Использовать Intersection Observer или библиотеку (vanilla реализация не более 100-200 строк)
- Рендерить только видимые + буферные элементы
- В gallery-режиме — ленивая подгрузка больших превью

**Сохранение состояния** (`sessionStorage`):
```js
// при изменении сохраняем
sessionStorage.setItem('cmv_state', JSON.stringify({
    folderId,
    page,
    viewMode,
    scrollPosition,
    activeImageIndex
}));

// при загрузке — восстанавливаем
```

**Мемоизация**:
- `renderSidebar()`, `renderMeta()` — кешировать HTML для неизменившихся данных
- Client-side кэш для thumbnail (они уже base64, но можно избежать повторного `innerHTML`)

**План перехода (этапы)**:

1. **Этап 1** — SQLite + работа in-place (core):
   - Установить `pysqlite3` (или использовать встроенный `sqlite3`)
   - Написать `app/database.py` — инициализация БД, CRUD
   - Переделать `scan_directory()` — проверка mtime, batch-вставка
   - Новые эндпоинты `/api/scan`, `/api/images`
   - Убрать копирование из `loadFromDirectory()` на фронте

2. **Этап 2** — Фронт:
   - Пагинация (page/per_page) с бесконечным скроллом
   - Intersection Observer для подгрузки
   - Сохранение состояния в sessionStorage

3. **Этап 3** — Оптимизация:
   - Мемоизация рендера на фронте
   - Виртуальный скролл (только видимые элементы в DOM)
   - Пул тредов для параллельного чтения метаданных (если нужно)
