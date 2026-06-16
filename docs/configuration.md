# Configuration

> Настройка и конфигурация Comfy Meta Viewer.

---

## Table of Contents

- [Переменные окружения](#переменные-окружения)
- [Порты и адреса](#порты-и-адреса)
- [Пути хранения](#пути-хранения)
- [Расширения файлов](#расширения-файлов)
- [Параметры SQLite](#параметры-sqlite)
- [Параметры thumbnail](#параметры-thumbnail)
- [Параметры cutout](#параметры-cutout)
- [CLI флаги](#cli-флаги)

---

## Переменные окружения

| Переменная | Значение по умолчанию | Описание |
|------------|----------------------|----------|
| `COMFY_META_PORT` | `7860` | Порт HTTP сервера |
| `COMFY_META_UPLOAD` | `.comfy_meta_uploads` | Директория для uploads и БД |

### Примеры использования

```bash
# Windows
set COMFY_META_PORT=8080
set COMFY_META_UPLOAD=D:\my_data
start.bat

# Linux/macOS
COMFY_META_PORT=8080 COMFY_META_UPLOAD=/data/comfy-meta ./start.sh
```

---

## Порты и адреса

| Ресурс | URL |
|--------|-----|
| Web UI | `http://localhost:7860` |
| API Base | `http://localhost:7860/api/` |
| Static files | `http://localhost:7860/static/` |

Для изменения порта используйте переменную `COMFY_META_PORT`.

---

## Пути хранения

### Структура

```
comfy-meta-viewer/
├── .comfy_meta_uploads/
│   ├── meta.db                    # SQLite database
│   └── {uuid}_{filename}          # Uploaded original files
├── cache/
│   ├── thumbnails/
│   │   ├── 1.jpg                  # JPEG thumbnails
│   │   ├── 2.jpg
│   │   └── ...
│   └── cutouts/
│       ├── 1.png                  # Transparent PNG cutouts
│       ├── 2.png
│       └── ...
└── .venv/                         # Python virtualenv
```

### Описание

| Директория | Содержимое | Очищается при reset |
|------------|-----------|-------------------|
| `.comfy_meta_uploads/` | SQLite DB + uploaded files | Да |
| `cache/thumbnails/` | JPEG thumbnails | Да |
| `cache/cutouts/` | Transparent PNG cutouts | Да |

---

## Расширения файлов

### Поддерживаемые

| Расширение | Полное извлечение | Базовое |
|------------|-------------------|---------|
| `.png` | tEXt, iTXt chunks | -- |
| `.jpg` | EXIF + комментарии | -- |
| `.jpeg` | EXIF + комментарии | -- |
| `.webp` | -- | EXIF |
| `.bmp` | -- | Размеры |
| `.tiff` | -- | EXIF |

### Фильтрация

При сканировании фильтруются только файлы с указанными расширениями (без учёта регистра).

---

## Параметры SQLite

### Режим

- **WAL mode** (Write-Ahead Logging) для параллельного чтения
- **Foreign keys** включены
- **CASCADE delete** для images → folders

### Индексы

```sql
idx_images_folder        -- Быстрый поиск по folder_id
idx_images_folder_mtime  -- Инкрементальное сканирование
```

### BLOB хранение

Uploaded файлы сохраняются как `original_data BLOB` в таблице `images`. Это позволяет:
- Не хранить копии на диске
- Автоматически удалять при DELETE
- Отдавать через `/api/original/{id}`

---

## Параметры thumbnail

| Параметр | Значение |
|----------|----------|
| Формат | JPEG |
| Quality | 85 |
| Max dimension | 300px |
| Путь | `cache/thumbnails/{id}.jpg` |
| Генерация | Lazy (при первом запросе) |

---

## Параметры cutout

| Параметр | Значение |
|----------|----------|
| Формат | PNG (RGBA) |
| Путь | `cache/cutouts/{id}.png` |
| Генерация | По запросу POST /api/cutout/{id} |
| Кэширование | Да (persistent) |
| Алгоритм | Alpha channel + background estimation |

---

## CLI флаги

```
usage: python -m app.main [-h] [--no-browser]

Comfy Meta Viewer

options:
  -h, --help       show this help message and exit
  --no-browser     Don't auto-open browser
```

### Примеры

```bash
# Обычный запуск
poetry run python -m app.main

# Без автоматического открытия браузера
poetry run python -m app.main --no-browser

# Через start.bat (Windows)
start.bat
```
