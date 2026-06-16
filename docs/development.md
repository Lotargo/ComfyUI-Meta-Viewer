# Development

> Руководство для разработчиков Comfy Meta Viewer.

---

## Table of Contents

- [Предварительные требования](#предварительные-требования)
- [Установка](#установка)
- [Структура проекта](#структура-проекта)
- [Запуск](#запуск)
- [Добавление нового API endpoint](#добавление-нового-api-endpoint)
- [Добавление нового JS модуля](#добавление-нового-js-модуля)
- [Добавление нового CSS компонента](#добавление-нового-css-компонента)
- [Код-стайл](#код-стайл)
- [Тестирование](#тестирование)

---

## Предварительные требования

| Зависимость | Версия | Описание |
|------------|--------|----------|
| Python | 3.10+ | Язык |
| Poetry | 1.7+ | Менеджер зависимостей |
| Браузер | -- | Chrome/Firefox/Edge |

---

## Установка

```bash
# Клонировать репозиторий
git clone https://github.com/your-repo/comfy-meta-viewer.git
cd comfy-meta-viewer

# Установить зависимости
poetry install --no-root

# Запустить
poetry run python -m app.main
```

---

## Структура проекта

```
comfy-meta-viewer/
├── app/                          # Python backend
│   ├── __init__.py
│   ├── main.py                   # Flask routes (18 endpoints)
│   ├── database.py               # SQLite operations
│   ├── extractor.py              # Metadata parsing
│   ├── cutout.py                 # Background removal
│   ├── schemas.py                # Pydantic models
│   ├── static/                   # Frontend
│   │   ├── css/
│   │   │   ├── base/             # Variables, reset, typography
│   │   │   ├── layout/           # Shell, sidebar, content
│   │   │   ├── components/       # UI components
│   │   │   ├── features/         # Feature-specific styles
│   │   │   └── utils/            # Responsive
│   │   └── js/
│   │       ├── app.js            # Entry point
│   │       ├── state.js          # Global state
│   │       ├── api.js            # HTTP client
│   │       ├── events.js         # DOM events
│   │       ├── components/       # Reusable components
│   │       ├── features/         # Feature modules
│   │       └── vendor/           # Third-party
│   └── templates/
│       └── index.html
├── cache/                        # Generated files
├── dev_docs/                     # Internal docs
├── docs/                         # Public docs
└── pyproject.toml
```

---

## Запуск

```bash
# Development
poetry run python -m app.main

# С custom портом
COMFY_META_PORT=8080 poetry run python -m app.main

# Без открытия браузера
poetry run python -m app.main --no-browser
```

Сервер запускается на `http://localhost:7860`.

---

## Добавление нового API endpoint

### 1. Создать route в `main.py`

```python
@app.route("/api/my-endpoint", methods=["POST"])
def my_endpoint():
    data = request.get_json()
    # Logic here
    return jsonify({"result": "ok"})
```

### 2. Добавить Pydantic модель в `schemas.py` (опционально)

```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str
```

### 3. Добавить API клиент в `api.js`

```javascript
export async function myEndpoint(data) {
    const res = await fetch("/api/my-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    return res.json();
}
```

### 4. Добавить документацию в `docs/api.md`

---

## Добавление нового JS модуля

### 1. Создать файл в `features/` или `components/`

```javascript
// features/my-feature.js
import { state } from "../state.js";

export function initMyFeature() {
    // Setup
}

export function destroyMyFeature() {
    // Cleanup
}
```

### 2. Импортировать в `app.js`

```javascript
import { initMyFeature } from "./features/my-feature.js";

// В init():
initMyFeature();
```

### 3. Добавить TypeScript declarations в `types.d.ts` (если нужно)

```typescript
declare module "./features/my-feature.js" {
    export function initMyFeature(): void;
    export function destroyMyFeature(): void;
}
```

---

## Добавление нового CSS компонента

### 1. Создать файл в соответствующей папке

- UI компоненты → `components/`
- Feature-специфичные → `features/`
- Layout → `layout/`
- Базовые → `base/`

### 2. Использовать CSS custom properties

```css
/* components/my-component.css */
.my-component {
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}
```

### 3. Подключить в `index.html`

```html
<link rel="stylesheet" href="/static/css/components/my-component.css">
```

---

## Код-стайл

### Python

- PEP 8
- Type hints для всех функций
- Pydantic для валидации
- Docstrings для публичных функций
- Длинна строки: 100 символов

### JavaScript

- ES modules (import/export)
- Без фреймворков (vanilla JS)
- camelCase для переменных/функций
- PascalCase для классов
- Длинна строки: 100 символов

### CSS

- BEM-like именование (block__element--modifier)
- CSS custom properties для всего
- Модульная структура (один файл = одна область)
- Минимум !important

---

## Тестирование

### Текущий статус

**Тесты отсутствуют.** Проект не имеет unit/integration тестов.

### Рекомендации

1. **Backend**: pytest + flask testing client
2. **Frontend**: Vitest или Jest для JS модулей
3. **E2E**: Playwright или Cypress

### Ручное тестирование

1. Запустить сервер
2. Открыть `http://localhost:7860`
3. Проверить все features:
   - Сканирование папки
   - Drag-drop upload
   - Просмотр метаданных
   - Workflow graph
   - Cutout
   - Search
   - Keyboard shortcuts
   - Responsive
