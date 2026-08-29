# Documentation Index

> Central technical documentation for ComfyUI Meta Viewer (CMV).

This directory contains the public technical and architectural documentation of the project.
- **Public Landing & Interactive API**: [`site/`](../site/) (deployed to GitHub Pages; interactive API explorer at [`site/api/`](../site/api/index.html))
- **Technical Documentation**: [`docs/`](./) (system architecture, API reference, AI subsystem, developer guides)
- **Internal Roadmaps & Specifications**: [`dev_docs/`](../dev_docs/) (strategic sprint plans and milestone specifications)

---

## Public Portal & API

| Resource | Location | Description |
|----------|----------|-------------|
| [Landing Page](../site/index.html) | `site/index.html` | Project overview, showcase gallery, feature highlights, and quick install |
| [Interactive API Reference (Scalar)](../site/api/index.html) | `site/api/index.html` | Public OpenAPI 3.1 contract for all supported non-legacy `/api/*` routes, rendered by Scalar with live request examples and code snippets |

`site/api/openapi.json` is the machine-readable public API contract. `docs/core/api.md` is the detailed human reference with behavioral notes and examples. The pre-Simple-Mode `/api/editor/*` workflow-editor surface is retained as legacy/internal implementation material and is intentionally excluded from the public OpenAPI contract and its CI coverage gate.

---

## Core Documentation

| Document | Description |
|----------|-------------|
| [Architecture](core/architecture.md) | System overview, data flow, SQLite storage model, and extension points |
| [API Reference](core/api.md) | Detailed REST reference; supported public routes stay synchronized with `site/api/openapi.json`, with legacy editor notes kept separately |
| [Features](core/features.md) | User-facing capabilities, keyboard shortcuts, and UI interactions |
| [Configuration](core/configuration.md) | Environment variables, local directories, file support, and CLI flags |
| [Installation](core/installation.md) | Installation options, requirements, and startup scripts |

---

## Development & Engineering

| Document | Description |
|----------|-------------|
| [Development Guide](dev/development.md) | Local setup, project structure, contribution workflow, API contract rules, and testing checklist |
| [JavaScript Architecture](dev/js-architecture.md) | Frontend ES module structure, state management, API client, and feature modules |
| [CSS Architecture](dev/css-architecture.md) | Styling design system, custom CSS properties, naming conventions, and layout tokens |

---

## AI Subsystem & Prompt Architecture

| Document | Description |
|----------|-------------|
| [AI Prompt Architecture](ai/prompt-architecture.md) | High-level overview: canonical instruction layers, deterministic compilation, and durable jobs |
| [Prompt Architecture Spec](ai/prompt-architecture-spec.md) | Master reference specification: profiles, operations, scenarios, modifiers, and contracts |
| [Intent Benchmark](ai/intent-benchmark.md) | Raw-intent prompt generation benchmarks and model-judge evaluation suite |
| [OpenCode Smoke Testing](ai/opencode-smoke-testing.md) | Managed CLI agent execution, test scenarios, profiles, and reporting |
| [AI Smoke Testing](ai/smoke-testing.md) | Provider verification, test suites, and diagnostic execution |

---

## Product & UX Design

| Document | Description |
|----------|-------------|
| [Simple Mode Redesign](design/simple-mode-redesign.md) | Target UX, verified profile model, AI-assisted generation flow, and migration rules |

---

## Roadmaps & Internal Planning

Active strategic plans and technical roadmaps are maintained in [`dev_docs/roadmap/`](../dev_docs/roadmap/README.md):

| Area | Roadmap Reference | Status |
|------|-------------------|--------|
| **Core & Foundation** | [`dev_docs/roadmap/core/`](../dev_docs/roadmap/core/) | Cross-platform, Database reset, Source monitoring |
| **Simple Mode** | [`dev_docs/roadmap/simple/`](../dev_docs/roadmap/simple/03_SIMPLE_MODE_MODEL_CALIBRATION.md) | Prompt generator, calibration of 8 base models |
| **Advanced Mode** | [`dev_docs/roadmap/advanced/`](../dev_docs/roadmap/advanced/04_ADVANCED_MODE_AND_COMFYUI_INTEGRATION.md) | Embedded ComfyUI, Txt2Img, Img2Img, Studio |
| **Social & Export** | [`dev_docs/roadmap/oauth/`](../dev_docs/roadmap/oauth/06_SOCIAL_EXPORT_PLAN.md) | Social OAuth, Telegram/VK/Instagram export |
| **Desktop Packaging** | [`dev_docs/roadmap/desktop/`](../dev_docs/roadmap/desktop/07_DESKTOP_PACKAGING_AND_INSTALLERS.md) | Standalone cross-platform desktop installers |

---

## Quick Links

| Goal | Start Here |
|------|------------|
| Install and run the app | [Installation](core/installation.md) &bull; [Development > Setup](dev/development.md#setup) |
| Understand system design | [Architecture](core/architecture.md) |
| Explore REST endpoints | [API Reference](core/api.md) &bull; [Scalar API (Interactive)](../site/api/index.html) |
| Review keyboard shortcuts | [Features > Keyboard Shortcuts](core/features.md#keyboard-shortcuts) |
| Configure storage or port | [Configuration](core/configuration.md#environment-variables) |
| Add a backend endpoint | [Development > Adding an API Endpoint](dev/development.md#adding-an-api-endpoint) |
| Add a frontend module | [JavaScript Architecture > Extension Guidelines](dev/js-architecture.md#extension-guidelines) |
| Add or customize styles | [CSS Architecture > Extension Guidelines](dev/css-architecture.md#extension-guidelines) |
| Inspect AI prompt pipeline | [AI Prompt Architecture](ai/prompt-architecture.md) |
| Review Simple Mode spec | [Simple Mode Redesign](design/simple-mode-redesign.md) |
