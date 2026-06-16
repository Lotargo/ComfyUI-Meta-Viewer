# Documentation

> Documentation index for ComfyUI Meta Viewer.

This folder contains the public documentation for the project: architecture, API behavior, feature overview, configuration, and development guides.

---

## Core Documentation

| Document | Description |
|----------|-------------|
| [Architecture](architecture.md) | System overview, data flow, storage model, and extension points |
| [API Reference](api.md) | Current REST API routes with request/response examples |
| [Features](features.md) | User-facing features and implementation notes |
| [Configuration](configuration.md) | Environment variables, local paths, file support, and CLI flags |

---

## Development Documentation

| Document | Description |
|----------|-------------|
| [Development](development.md) | Local setup, project structure, contribution workflow, and testing checklist |
| [JavaScript Architecture](js-architecture.md) | Frontend ES module structure, state, API client, and feature modules |
| [CSS Architecture](css-architecture.md) | Styling structure, custom properties, naming rules, and extension guidelines |

---

## Internal Development Notes

The `dev_docs/` folder contains planning notes and sprint documents. These files are kept as historical development context and may not always match the current public documentation.

| Document | Status |
|----------|--------|
| [Refactor Plan](../dev_docs/plan.md) | Archived planning note |
| [UI Redesign Sprint](../dev_docs/sprint-redesign.md) | Completed sprint note |
| [Object Cutout Sprint](../dev_docs/sprint-object-cutout.md) | Historical sprint note |

---

## Quick Links

| Goal | Start Here |
|------|------------|
| Install and run the app | [Development > Setup](development.md#setup) |
| Understand the system design | [Architecture](architecture.md) |
| Use or integrate with the REST API | [API Reference](api.md) |
| Review user-facing capabilities | [Features](features.md) |
| Change the port or storage path | [Configuration > Environment Variables](configuration.md#environment-variables) |
| Add a new backend endpoint | [Development > Adding an API Endpoint](development.md#adding-an-api-endpoint) |
| Add a frontend module | [JavaScript Architecture > Extension Guidelines](js-architecture.md#extension-guidelines) |
| Add or organize styles | [CSS Architecture > Extension Guidelines](css-architecture.md#extension-guidelines) |

---

## Notes

- The root [`README.md`](../README.md) is the project landing page.
- Files in this folder are intended to stay aligned with the current codebase.
- Files in `dev_docs/` are allowed to be more historical or exploratory.
