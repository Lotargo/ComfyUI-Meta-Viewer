# Development

> Developer guide for ComfyUI Meta Viewer.

This guide covers local setup, project structure, extension points, and manual testing.

---

## Table of Contents

- [Requirements](#requirements)
- [Setup](#setup)
- [Project Structure](#project-structure)
- [Running Locally](#running-locally)
- [Adding an API Endpoint](#adding-an-api-endpoint)
- [Adding a JavaScript Module](#adding-a-javascript-module)
- [Adding a CSS Component](#adding-a-css-component)
- [Code Style](#code-style)
- [Testing](#testing)

---

## Requirements

| Dependency | Version | Purpose |
|------------|---------|---------|
| Python | 3.10+ | Backend runtime |
| Poetry | 1.7+ | Dependency management |
| Browser | Current Chrome/Firefox/Edge | Local UI |

---

## Setup

```bash
# Clone the repository
git clone https://github.com/Lotargo/ComfyUI-Meta-Viewer.git
cd ComfyUI-Meta-Viewer

# Install dependencies
poetry install --no-root

# Run the application
poetry run python -m app.main
```

---

## Project Structure

```
ComfyUI-Meta-Viewer/
├── app/                          # Python backend + frontend static assets
│   ├── __init__.py
│   ├── main.py                   # Flask routes and startup wiring
│   ├── database.py               # SQLite operations
│   ├── extractor.py              # Metadata parsing
│   ├── cutout.py                 # Background removal
│   ├── schemas.py                # Pydantic models
│   ├── static/
│   │   ├── css/                  # Modular CSS
│   │   └── js/                   # ES modules
│   └── templates/
│       └── index.html            # SPA entry template
├── cache/                        # Generated thumbnails and cutouts
├── dev_docs/                     # Internal development notes
├── docs/                         # Public documentation
├── pyproject.toml                # Poetry project configuration
├── start.bat                     # Windows launcher
└── start.sh                      # Linux/macOS launcher
```

---

## Running Locally

```bash
# Default development launch
poetry run python -m app.main

# Custom port
COMFY_META_PORT=8080 poetry run python -m app.main

# Do not auto-open the browser
poetry run python -m app.main --no-browser

# Exercise physical index recreation without starting Flask
poetry run python -m app.main --reset-index
```

Default URL: `http://localhost:7860`.

---

## Adding an API Endpoint

### 1. Add a route in `app/main.py`

```python
@app.route("/api/my-endpoint", methods=["POST"])
def my_endpoint():
    data = request.get_json(silent=True) or {}
    return jsonify({"result": "ok", "input": data})
```

### 2. Add a Pydantic model in `app/schemas.py` when useful

```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str
```

### 3. Add a client wrapper in `app/static/js/api.js`

```javascript
export async function myEndpoint(data) {
    const res = await fetch("/api/my-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) return null;
    return res.json();
}
```

### 4. Document the endpoint

Update `docs/api.md` with request/response examples.

---

## Adding a JavaScript Module

### 1. Create a feature or component module

```javascript
// app/static/js/features/my-feature.js
import { state } from "../state.js";

export function initMyFeature() {
    // Setup
}

export function destroyMyFeature() {
    // Cleanup
}
```

### 2. Import it from `app.js`

```javascript
import { initMyFeature } from "./features/my-feature.js";

// During app initialization:
initMyFeature();
```

### 3. Add types only if the project introduces TypeScript tooling

The current frontend is plain ES modules. If TypeScript declarations are added later, keep them close to the module they describe or document the convention in this file.

---

## Adding a CSS Component

### 1. Create a file in the relevant folder

- UI components → `app/static/css/components/`
- Feature-specific styles → `app/static/css/features/`
- Layout styles → `app/static/css/layout/`
- Base styles → `app/static/css/base/`

### 2. Use CSS custom properties

```css
/* app/static/css/components/my-component.css */
.my-component {
    background: var(--color-bg);
    border: 1px solid var(--color-border);
    border-radius: var(--radius-md);
    padding: var(--spacing-md);
}
```

### 3. Include the stylesheet

Add the file to `app/templates/index.html` or to the appropriate CSS import path used by the current layout.

---

## Code Style

### Python

- Use type hints for public functions and core helpers.
- Use Pydantic models for request/response validation where helpful.
- Keep route handlers small and move reusable logic into modules.
- Prefer clear error responses with useful HTTP status codes.
- Target a readable line length of roughly 100 characters.

### JavaScript

- Use ES modules (`import` / `export`).
- Keep the frontend framework-free unless the project direction changes.
- Use `camelCase` for variables/functions and `PascalCase` for classes.
- Keep DOM querying and event binding localized to feature modules.

### CSS

- Use modular files grouped by responsibility.
- Prefer CSS custom properties for repeated values.
- Keep selectors predictable and BEM-like when possible.
- Avoid `!important` unless there is a strong reason.

---

## Testing

### Automated Checks

```bash
python -m unittest discover -s tests -v
npm run test:preferences
npm run lint
```

The Python suite covers Flask/database/image-processing behavior. The Node test suite uses the built-in test runner for the versioned preference schema and state-persistence boundary. ESLint checks all frontend modules.

GitHub Actions runs the same checks on Windows, Ubuntu, and macOS. The path suite also
verifies stable service directories, native directory scanning, Unicode and spaces,
Windows/POSIX upload filenames, and that scanning does not write into a source folder.

### Manual Test Checklist

1. Start the server.
2. Open `http://localhost:7860`.
3. Verify the main flows:
   - Folder scan.
   - Drag-and-drop upload.
   - Metadata summary rendering.
   - Workflow graph rendering.
   - Thumbnail loading.
   - Original image loading.
   - Cutout generation/deletion.
   - Fuzzy search.
   - Keyboard shortcuts.
   - Reset flow.
   - Responsive layout.
