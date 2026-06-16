# API Reference

> REST API endpoints для Comfy Meta Viewer.

Базовый URL: `http://localhost:7860`

---

## Table of Contents

- [Folders](#folders)
  - [GET /api/folders](#get-apifolders)
  - [DELETE /api/folders/{id}](#delete-apifoldersid)
- [Scanning](#scanning)
  - [POST /api/scan](#post-apiscan)
  - [POST /api/extract](#post-apiextract)
  - [POST /api/upload](#post-apiupload)
- [Images](#images)
  - [GET /api/images](#get-apiimages)
  - [GET /api/images/{id}](#get-apiimagesid)
  - [DELETE /api/images/{id}](#delete-apiimagesid)
- [Thumbnails & Originals](#thumbnails--originals)
  - [GET /api/thumbnail/{id}](#get-apithumbnailid)
  - [GET /api/original/{id}](#get-apioriginalid)
- [Cutout](#cutout)
  - [GET /api/cutout/{id}](#get-apicutoutid)
  - [POST /api/cutout/{id}](#post-apicutoutid)
  - [DELETE /api/cutout/{id}](#delete-apicutoutid)
- [Sessions](#sessions)
  - [GET /api/sessions](#get-apisessions)
  - [POST /api/sessions](#post-apisessions)
  - [GET /api/sessions/{id}](#get-apisessionsid)
  - [PATCH /api/sessions/{id}](#patch-apisessionsid)
  - [DELETE /api/sessions/{id}](#delete-apisessionsid)
- [System](#system)
  - [POST /api/reset](#post-apireset)
  - [GET /api/diagnostics](#get-apidiagnostics)
- [Схемы данных](#схемы-данных)

---

## Folders

### `GET /api/folders`

Возвращает список всех просканированных папок.

**Response:**
```json
[
  {
    "id": 1,
    "path": "/path/to/images",
    "name": "images",
    "image_count": 42,
    "scanned_at": "2025-01-15T10:30:00"
  }
]
```

---

### `DELETE /api/folders/{id}`

Удаляет папку и все связанные изображения (каскадное удаление).

**Response:**
```json
{ "ok": true }
```

---

## Scanning

### `POST /api/scan`

Сканирует папку с изображениями. Инкрементально: проверяет `mtime` файлов, пропускает уже обработанные.

**Request:**
```json
{ "path": "/path/to/folder" }
```

**Response:**
```json
{
  "folder_id": 1,
  "folder_name": "folder",
  "images_count": 42,
  "page": 1,
  "per_page": 50
}
```

**Behavior:**
- Рекурсивно обходит дерево директорий
- Фильтрует по расширениям: `.png`, `.jpg`, `.jpeg`, `.webp`, `.bmp`, `.tiff`
- Проверяет `mtime` для пропуска неизмененных файлов
- Генерирует thumbnails
- Сохраняет метаданные в SQLite

---

### `POST /api/extract`

Извлекает метаданные по списку файлов (для drag-drop отдельных файлов).

**Request:**
```json
{
  "paths": [
    "/path/to/image1.png",
    "/path/to/image2.png"
  ]
}
```

**Response:**
```json
{
  "images": [
    {
      "id": 1,
      "file_name": "image1.png",
      "format": "PNG",
      "width": 1024,
      "height": 768,
      "metadata": { ... }
    }
  ]
}
```

---

### `POST /api/upload`

Загружает файлы через multipart form. Сохраняет `original_data` в БД как BLOB.

**Request:** `multipart/form-data` с полем `files`

**Response:**
```json
{
  "images": [
    {
      "id": 1,
      "file_name": "uploaded.png",
      "format": "PNG",
      "width": 512,
      "height": 512
    }
  ]
}
```

---

## Images

### `GET /api/images`

Пагинированный список изображений.

**Query Parameters:**

| Параметр | Тип | По умолчанию | Описание |
|----------|-----|-------------|----------|
| `folder_id` | int | -- | Фильтр по папке |
| `page` | int | 1 | Номер страницы |
| `per_page` | int | 50 | Изображений на страницу |

**Response:**
```json
{
  "images": [
    {
      "id": 1,
      "file_name": "image.png",
      "rel_path": "subfolder/image.png",
      "format": "PNG",
      "width": 1024,
      "height": 768,
      "file_size": 2048000,
      "error": null
    }
  ],
  "page": 1,
  "per_page": 50,
  "total": 200,
  "has_more": true
}
```

---

### `GET /api/images/{id}`

Полная информация об изображении включая метаданные, workflow и EXIF.

**Response:**
```json
{
  "id": 1,
  "file_name": "image.png",
  "format": "PNG",
  "width": 1024,
  "height": 768,
  "mode": "RGBA",
  "file_size": 2048000,
  "metadata": {
    "prompt": "a beautiful landscape, masterpiece",
    "negative_prompt": "ugly, blurry",
    "settings": {
      "steps": 20,
      "sampler": "euler",
      "cfg": 7.0,
      "seed": 12345,
      "model": "sd_xl_base_1.0",
      "width": 1024,
      "height": 768
    },
    "workflow": {
      "nodes": [...],
      "connections": [...]
    },
    "raw_chunks": {
      "parameters": "Steps: 20, Sampler: euler, ...",
      "tEXt": [...]
    },
    "exif": { ... }
  },
  "thumbnail_url": "/api/thumbnail/1",
  "original_url": "/api/original/1"
}
```

---

### `DELETE /api/images/{id}`

Удаляет изображение из БД и связанные кэши (thumbnail, cutout).

**Response:**
```json
{ "ok": true }
```

---

## Thumbnails & Originals

### `GET /api/thumbnail/{id}`

Возвращает JPEG thumbnail. Генерируется лениво и кэшируется на диске.

**Response:** `image/jpeg`

---

### `GET /api/original/{id}`

Возвращает оригинальное изображение. Для uploaded файлов -- из BLOB в БД, для scanned -- с диска.

**Response:** `image/{format}`

---

## Cutout

### `GET /api/cutout/{id}`

Возвращает cached transparent PNG cutout (если существует).

**Response:**
```json
{
  "exists": true,
  "url": "/api/cutout/1"
}
```
или
```json
{ "exists": false }
```

---

### `POST /api/cutout/{id}`

Генерирует transparent PNG cutout (автоматическое удаление фона). Если уже есть в кэше -- возвращает существующий.

**Response:**
```json
{
  "exists": true,
  "url": "/api/cutout/1",
  "cached": true
}
```

---

### `DELETE /api/cutout/{id}`

Очищает cutout кэш для изображения.

**Response:**
```json
{ "ok": true }
```

---

## Sessions

### `GET /api/sessions`

Возвращает список всех сессий.

**Response:**
```json
[
  {
    "id": 1,
    "name": "My Project",
    "folder_id": 1,
    "created_at": "2025-01-15T10:30:00"
  }
]
```

---

### `POST /api/sessions`

Создаёт новую сессию.

**Request:**
```json
{
  "name": "My Project",
  "folder_id": 1
}
```

**Response:**
```json
{
  "id": 1,
  "name": "My Project",
  "folder_id": 1,
  "created_at": "2025-01-15T10:30:00"
}
```

---

### `GET /api/sessions/{id}`

Возвращает детали сессии.

---

### `PATCH /api/sessions/{id}`

Переименовывает сессию.

**Request:**
```json
{ "name": "New Name" }
```

---

### `DELETE /api/sessions/{id}`

Удаляет сессию.

**Response:**
```json
{ "ok": true }
```

---

## System

### `POST /api/reset`

Полная очистка: база данных + thumbnail cache + cutout cache.

**Response:**
```json
{
  "ok": true,
  "message": "Database and caches cleared"
}
```

---

### `GET /api/diagnostics`

Возвращает статистику системы.

**Response:**
```json
{
  "folders": 3,
  "images": 150,
  "sessions": 2,
  "uploads": 12,
  "thumbnails": 138,
  "cutouts": 5,
  "db_path": ".comfy_meta_uploads/meta.db",
  "cache_path": "cache/"
}
```

---

## Схемы данных

### ImageListItem

```json
{
  "id": "int",
  "file_name": "string",
  "rel_path": "string",
  "format": "string",
  "width": "int | null",
  "height": "int | null",
  "file_size": "int | null",
  "error": "string | null"
}
```

### ImageDetail

```json
{
  "id": "int",
  "file_name": "string",
  "format": "string",
  "width": "int",
  "height": "int",
  "mode": "string",
  "file_size": "int",
  "metadata": {
    "prompt": "string",
    "negative_prompt": "string",
    "settings": "GenerationSettings",
    "workflow": "WorkflowData | null",
    "raw_chunks": "RawChunks",
    "exif": "object | null"
  },
  "thumbnail_url": "string",
  "original_url": "string"
}
```

### GenerationSettings

```json
{
  "steps": "int",
  "sampler": "string",
  "scheduler": "string",
  "cfg": "float",
  "seed": "int",
  "model": "string",
  "width": "int",
  "height": "int",
  "denoise": "float",
  "batch_size": "int",
  "lora": ["string"]
}
```
