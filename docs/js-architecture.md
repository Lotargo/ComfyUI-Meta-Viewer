# JavaScript Architecture

> Frontend module architecture for ComfyUI Meta Viewer.

The frontend is a framework-free single-page application built with Vanilla JavaScript and ES modules. It keeps the runtime simple, offline-friendly, and easy to inspect.

---

## Table of Contents

- [Overview](#overview)
- [Module Map](#module-map)
- [State Management](#state-management)
- [API Client](#api-client)
- [Event System](#event-system)
- [Feature Modules](#feature-modules)
- [Components](#components)
- [Vendor Libraries](#vendor-libraries)
- [Extension Guidelines](#extension-guidelines)

---

## Overview

The browser UI is split into small modules with clear responsibilities:

- `app.js` wires the application together.
- `state.js` stores shared UI state.
- `api.js` wraps backend calls.
- Feature modules own larger interaction areas such as the sidebar, workflow graph, keyboard shortcuts, and cutout panel.
- Component modules own reusable UI fragments such as search and skeleton loading.

No React/Vue/Svelte runtime is required.

---

## Module Map

```
app/static/js/
├── app.js                 # Entry point
├── state.js               # Shared UI state
├── preferences.js         # Versioned preference schema and validation
├── api.js                 # REST API client
├── events.js              # DOM event wiring
├── gallery.js             # Masonry/gallery rendering
├── lightbox.js            # Fullscreen image viewer
├── meta-view.js           # Summary/Workflow/Raw metadata panels
├── sessions.js            # Local session-oriented UI state helpers
├── utils.js               # Generic helpers
├── components/
│   ├── search-bar.js      # Fuse.js search UI
│   ├── image-context-menu.js # Shared Viewer/Library image actions
│   ├── sidebar-item.js    # Sidebar image item rendering
│   └── skeleton.js        # Loading placeholders
├── features/
│   ├── sidebar.js         # Resizable sidebar and folder/image list
│   ├── workflow-graph.js  # SVG workflow graph
│   ├── keyboard.js        # Shortcuts and Help Center
│   └── cutout.js          # Cutout panel and preview
└── vendor/
    └── fuse.min.js        # Local Fuse.js bundle
```

---

## State Management

**File:** `app/static/js/state.js`

The app uses a small shared state module instead of an external state management library. It contains both ephemeral runtime values and stable UI preference values, but only the latter are serialized.

```javascript
{
    images: [],           // Current image list/page
    activeIndex: -1,      // Selected image index
    viewMode: 'gallery',  // 'upload' | 'list' | 'gallery'
    currentFolderId: null,// Stable selected folder ID
    folders: [],          // Indexed folders
    currentPage: 0,       // Ephemeral pagination state
    allLoaded: true,      // Infinite-scroll flag
    isLoading: false      // Request/loading flag
}
```

`preferences.js` defines schema version 2 and normalizes every saved field. `localStorage` contains only stable preferences: selected folder ID, view/sidebar modes, sidebar dimensions, sorting, search options, metadata tab, and lightbox metadata-panel visibility. Collections, indexes, open dialogs/lightbox state, zoom/pan, search text, pagination, caches, and DOM classes are always rebuilt from runtime data. Old search preferences from `sessionStorage` are migrated once.

During boot, preferences are applied while the boot layer still hides intermediate DOM. The backend folder list then confirms the selected folder ID; a missing ID falls back to an existing folder and is immediately corrected in storage.

---

## API Client

**File:** `app/static/js/api.js`

`api.js` centralizes backend calls and keeps route usage out of UI modules.

Typical functions:

```javascript
scanFolder(path)            // POST /api/scan
loadFromPaths(paths)        // POST /api/extract
loadFromFiles(files)        // POST /api/upload
loadMore()                  // GET  /api/images?page=N
loadFolderImages(id)        // GET  /api/images?folder_id=N
deleteImageAt(id)           // DELETE /api/images/{id}
getFolders()                // GET  /api/folders
deleteFolderFromServer(id)  // DELETE /api/folders/{id}
getCutout(id)               // GET  /api/cutout/{id}
createCutout(id)            // POST /api/cutout/{id}
deleteCutout(id)            // DELETE /api/cutout/{id}
getThumbnail(id)            // GET  /api/thumbnail/{id}
```

Recommended pattern:

```javascript
export async function scanFolder(path) {
    try {
        const res = await fetch('/api/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ path }),
        });
        if (!res.ok) return null;
        return await res.json();
    } catch (error) {
        console.error('Scan failed:', error);
        return null;
    }
}
```

---

## Event System

**File:** `app/static/js/events.js`

`events.js` binds high-level DOM interactions and delegates feature-specific work to modules.

Common event sources:

| Event | Source | Purpose |
|-------|--------|---------|
| `drop` | `window` | Drag-and-drop files/folders |
| `dragover` | `window` | Prevent browser default behavior |
| `paste` | `document` | Path/input paste behavior |
| `click` | UI controls | Buttons, tabs, image items |
| `keydown` | `document` | Keyboard shortcuts |

---

## Feature Modules

### `features/sidebar.js`

Owns the sidebar layout and folder/image list interactions.

Responsibilities:

- Resize handle.
- Folder list rendering.
- Image list rendering.
- Infinite scroll sentinel.
- Image selection and deletion actions.

### `features/workflow-graph.js`

Renders ComfyUI workflow data as an SVG graph.

Responsibilities:

- Create SVG nodes and edges.
- Color nodes by category.
- Support pan/zoom interactions.
- Expose selected node details.

### `features/keyboard.js`

Owns keyboard shortcuts and the Help Center.

Typical shortcuts:

```javascript
// ArrowLeft / ArrowRight: image navigation
// Enter: open lightbox
// Escape: close active panel
// Delete: delete selected image
// Ctrl+F: search
// G: toggle gallery/list
// ?: help center
// 1-3: metadata tabs
// D: metadata panel
// S: sidebar
```

### `features/cutout.js`

Owns the cutout panel.

Responsibilities:

- Request cutout generation.
- Preview generated transparent PNGs.
- Download cutouts.
- Delete cached cutouts.

---

## Components

### `components/search-bar.js`

Client-side fuzzy search powered by Fuse.js.

Typical searchable fields:

```javascript
{
    keys: [
        { name: 'file_name', weight: 0.4 },
        { name: 'format', weight: 0.2 },
        { name: 'metadata.prompt', weight: 0.3 },
        { name: 'metadata.settings.model', weight: 0.05 },
        { name: 'metadata.settings.sampler', weight: 0.05 }
    ],
    threshold: 0.3,
    includeScore: true
}
```

### `components/sidebar-item.js`

Renders image entries for the sidebar.

```html
<div class="sidebar-item">
    <img class="sidebar-item__thumb" src="/api/thumbnail/{id}">
    <div class="sidebar-item__info">
        <span class="sidebar-item__name">{file_name}</span>
        <span class="sidebar-item__meta">{format} {width}x{height}</span>
    </div>
    <button class="sidebar-item__delete">✕</button>
</div>
```

### `components/skeleton.js`

Provides loading placeholders for sidebar items, gallery cards, and metadata panels.

---

## Vendor Libraries

### Fuse.js

**File:** `app/static/js/vendor/fuse.min.js`

Fuse.js is stored locally so the app can run without CDN/network access.

Purpose: fuzzy search over image filenames and extracted metadata.

---

## Extension Guidelines

When adding a new frontend feature:

1. Put feature-level behavior in `app/static/js/features/`.
2. Put reusable UI fragments in `app/static/js/components/`.
3. Add backend calls to `api.js` instead of calling `fetch()` directly from many modules.
4. Store cross-module UI state in `state.js`.
5. Keep DOM event binding local and easy to remove/reinitialize.
6. Add matching CSS under `app/static/css/features/` or `app/static/css/components/`.
