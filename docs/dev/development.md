# Development

> Developer guide for ComfyUI Meta Viewer.

This guide covers local setup, project structure, extension points, API contract rules, and testing.

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
│   ├── main.py                   # Core Flask routes and startup wiring
│   ├── database.py               # SQLite operations
│   ├── library.py                # Albums, favorites, tags, filters
│   ├── extractor.py              # Metadata parsing
│   ├── cutout.py                 # Background removal
│   ├── schemas.py                # Pydantic models
│   ├── source_monitor.py         # Watchers, debounce, reconnect, reconciliation
│   ├── ai/                       # AI prompt compiler, provider adapters, durable jobs
│   │   └── routes.py             # Public AI REST routes
│   ├── comfyui/                  # ComfyUI runtime, Simple Mode, legacy editor
│   │   ├── routes.py             # Public ComfyUI runtime routes
│   │   ├── simple_routes.py      # Public Simple Mode routes
│   │   └── editor_routes.py      # Legacy/internal workflow-editor routes
│   ├── integrations/social/      # Social status/auth/publishing contract
│   ├── static/
│   │   ├── css/                  # Modular CSS
│   │   └── js/                   # ES modules
│   └── templates/                # Jinja2 HTML templates
├── cache/                        # Generated thumbnails, previews, and cutouts
├── dev_docs/                     # Internal specifications and sprint roadmaps
├── docs/                         # Technical documentation
├── site/                         # Public landing page and Scalar API portal
│   └── api/openapi.json          # Machine-readable public OpenAPI 3.1 contract
├── tests/
│   └── test_openapi_contract.py  # Public Flask route/OpenAPI drift gate
├── pyproject.toml                # Poetry project configuration
├── benchmark.bat                 # Windows benchmark launcher
├── benchmark.sh                  # Linux/macOS benchmark launcher
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

CMV treats `site/api/openapi.json` as the public machine-readable API contract. The detailed human reference lives in `docs/core/api.md`. Supported public routes and OpenAPI are checked for drift by `tests/test_openapi_contract.py` on every normal pytest/CI run.

The supported public route modules are:

- `app/main.py` - core media, folders, library, uploads, cutouts, diagnostics, and reset routes;
- `app/ai/routes.py` - AI providers, prompt operations, jobs, resources, and ratings;
- `app/comfyui/routes.py` - ComfyUI runtime lifecycle and configuration;
- `app/comfyui/simple_routes.py` - Simple Mode model setup, generation, and run tracking;
- `app/integrations/social/routes.py` - social capability/authentication/publishing contract.

`app/comfyui/editor_routes.py` belongs to the pre-Simple-Mode workflow editor. Its `/api/editor/*` routes are intentionally legacy/internal and are excluded from the public OpenAPI coverage gate unless that product decision changes explicitly.

### 1. Add the route to the owning public module

Choose the module that owns the capability instead of putting every endpoint into `app/main.py`.

```python
@simple_blueprint.route("/api/simple/my-endpoint", methods=["POST"])
def my_endpoint():
    data = request.get_json(silent=True) or {}
    return jsonify({"result": "ok", "input": data})
```

Keep route handlers small and move reusable behavior into services/modules.

### 2. Add request/response validation when useful

Use Pydantic models for structured payloads or contracts with non-trivial validation.

```python
class MyRequest(BaseModel):
    field: str

class MyResponse(BaseModel):
    result: str
```

### 3. Update the public OpenAPI contract

Every new supported non-legacy `/api/*` method must be added to `site/api/openapi.json` with:

- the exact normalized path (`<int:id>` in Flask becomes `{id}` in OpenAPI);
- the HTTP method;
- a useful `summary`;
- at least one tag;
- a unique `operationId`;
- all path parameters declared with `in: path` and `required: true`;
- request and important response schemas where they materially help API consumers.

The Scalar portal at `site/api/index.html` reads this file directly.

### 4. Update the detailed API reference

Document behavior, edge cases, important response codes, and examples in `docs/core/api.md`.

Keep the distinction clear:

- `site/api/openapi.json` - supported public machine contract;
- `docs/core/api.md` - detailed human reference and implementation notes;
- `/api/editor/*` - legacy/internal unless explicitly promoted back into the public API.

### 5. Add a frontend wrapper when the web UI consumes it

If the browser UI calls the new endpoint, add or update the appropriate wrapper in `app/static/js/api.js` or the owning frontend module.

```javascript
export async function myEndpoint(data) {
    const res = await fetch("/api/simple/my-endpoint", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(data),
    });
    if (!res.ok) return null;
    return res.json();
}
```

An endpoint used only by external/local integrations does not need a frontend wrapper merely to satisfy the API contract.

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

- UI components -> `app/static/css/components/`
- Feature-specific styles -> `app/static/css/features/`
- Layout styles -> `app/static/css/layout/`
- Base styles -> `app/static/css/base/`

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
poetry run python -m pytest tests -q
npm run test:preferences
npm run lint
```

The Python suite covers Flask/database/image-processing behavior and the public API contract. `tests/test_openapi_contract.py` statically reads route decorators from the supported public route modules and compares their normalized method/path pairs with `site/api/openapi.json`. It also checks Scalar navigation metadata, unique operation IDs, exact path-parameter declarations, and malformed component references.

This makes API drift a CI failure: a new supported Flask route cannot silently appear without its OpenAPI entry, and a removed/renamed route cannot remain advertised in the public contract.

The Node test suite uses the built-in test runner for the versioned preference schema and state-persistence boundary. ESLint checks all frontend modules.

GitHub Actions runs the same checks on Windows, Ubuntu, and macOS. The path suite also verifies stable service directories, native directory scanning and watcher events, burst coalescing, reconnect behavior, Unicode and spaces, Windows/POSIX upload filenames, and that scanning does not write into a source folder.

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
4. Open the Scalar API portal and spot-check any endpoint changed in the same patch.
