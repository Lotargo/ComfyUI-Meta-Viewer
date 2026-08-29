# Changelog

All notable changes to **ComfyUI Meta Viewer** are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added

- Unicode-aware cross-platform path handling and configurable data/cache
  directories via `COMFY_META_DATA_DIR` / `COMFY_META_CACHE_DIR` (`f9d19f2`,
  `app/database.py:1`, `docs/core/configuration.md`).
- Physical index and factory reset that leave source files untouched (`181ee8f`).
- Source monitoring: `watchdog` filesystem watcher plus periodic reconciliation,
  in-place scanning with incremental cache, and support for cloud-synced desktop
  folders without copying (`002e75f`, `app/main.py:1`).
- Virtual media library: albums, favorites, ratings, tags, notes, and bulk
  selection without moving files (`d169376`, `e07f04d`, `a5eec84`).
- Album browsing inside the viewer (`5412d7a`).
- Redesigned source tiles, album cards, headers, and toolbars (`c6b76c5`–`35bf949`).
- Image context-menu actions — rename, remove, rating filters — and move-to-trash
  via `send2trash` (`30c9aa2`–`f52eb1d`).
- Unified media pipeline for images and video with upload for both types
  (`POST /api/upload`, `f4fccd2`, `8c7c43d`).
- Central gallery and Media sidebar filtering by media type; videos are exposed
  in the central gallery (`a467fe5`, `0ae3b4d`, `8c7c43d`).
- FFmpeg/`ffprobe` poster generation and technical stream metadata when binaries
  are on `PATH` (`README.md:37`).
- BYOK provider profiles: OpenAI-compatible, with masked API-key storage in the
  OS keyring or environment variables (`6ea5aed`, `app/ai/profiles.py:1`,
  `keyring 25.x` in `pyproject.toml:17`).
- Automatic discovery of authenticated local CLIs — OpenCode, Claude Code,
  Antigravity (`f013fa4`, `GET /api/ai/cli-integrations`).
- Prompt domain contracts: `PromptTask`, `SceneSpec`, `PromptResult`,
  `InstructionBundle` (`642505f`, `app/ai/prompting/compiler.py:1`).
- Prompt capability registry (`4d646a3`).
- Deterministic prompt compiler with section fingerprinting and output-contract
  precedence (`7b798bf`, `a17639a`, `282c880`, `23b704b`).
- Family profiles for FLUX / SDXL / Pony (`fe8dabb`–`923cef7`).
- Prompt operations: `generate`, `reconstruct`, `adapt`, `translate`
  (`760458a`–`e0ab76e`).
- Scenario manifests: `portrait`, `single_character`, `product_object`,
  `architecture_interior`, `landscape_environment`, `illustration_art`,
  `graphic_design_text` (`4204461`, `215b915`, `8522917`–`c617f94`).
- Prompt modifiers: `safe`, `adult_only` (`173f6a7`, `24ba89f`).
- Canonical prompt registry with `load_skill()` preserved and native skill export
  for OpenCode / Claude Code / Antigravity / Codex (`6b8c501`, `30d258f`).
- Reusable OpenAI-compatible chat transport (`967681e`, `app/ai/execution/direct.py:1`).
- Direct and managed OpenCode executors (`777a1a2`, `2b8f6f1`,
  `app/ai/execution/opencode.py:1`) with a 5-minute managed timeout (`3ce4327`)
  and descendant-process cleanup via `taskkill` / POSIX tree (`395e2f2`,
  `app/ai/managed_process.py:1`).
- Capability-based execution router (`1ef5f12`, `app/ai/execution/router.py:1`).
- SQLite persistence for jobs, scene specs, prompt drafts, results, and errors,
  plus editable draft revisions with a review lifecycle (`c4fc06a`, `2bf32ce`,
  `63fc94a`, `611ebbe`, `9344914`, `app/ai/job_store.py:1`).
- Strict, family-grounded intent judge with deterministic heuristic checks
  (`193d1e3`, `app/ai/judging/models.py:1`,
  `app/ai/execution/intent_judge_policy.py:1`).
- Isolated OpenCode judge executors (`64f5bf9`).
- Self-judged and language-independent prompt benchmarks (`464caca`, `d7bf22d`).
- Scenario coverage for all seven scenarios plus Flux-like / SDXL / Pony
  adaptations (`e508f31`–`64b9862`).
- OpenCode prompt quality benchmark (`b60cecf`).
- Rich smoke runners for OpenCode and real providers (`7eba144`, `2fe2e38`).
- Interactive benchmark launcher `benchmark.bat` / `benchmark.sh` with `list` /
  `run` and a family→operation→scenario menu (`fdf27d1`, `440d9dc`,
  `README.md:153`).
- AI image ranking service with SQLite persistence and evaluation logic
  (`508b255`).
- ComfyUI runtime integration: setup, dependency preflight, queue / cancellation
  / result import / provenance (`a90295b`, `dfd7d8a`, `4567f40`, `app/comfyui/`).
- Workflow Editor endpoints `POST /api/editor/drafts/{id}/preview|run` and
  `POST /api/editor/remix`.
- Manifest v2 resource contracts (`66b475b`).
- Flux loader variants (`4433904`).
- Pony / Krea GGUF verification (`28cd422`, `91f856b`).
- API/UI graph import and registration (`5b82816`, `d4b377f`).
- Import mapping wizard (`da74661`, `1028289`).
- Template registry management, duplication, and export (`390b50b`, `79a9b9c`).
- Field-level runtime diagnostics (`4b7ce30`).
- AI-connected generation / translation / adaptation / reconstruction flows into
  editor drafts (`ac78ac8`–`e0a8a14`).
- Remix with lineage (`90e24f6`).
- Vision analysis via OpenCode (`d32b387`).
- Preservation of negative prompts and checkpoint triggers (`175da44`, `5d2307e`).
- Local model inspection without managed Python (`4406400`).
- Fixed simple-mode model packs (`64a832f`).
- Civitai model downloader with distinct pause/cancel semantics and
  navigation-resilient tasks (`cf257bc`, `16c9575`–`d5ec0b4`).
- Asset rating foundation (`8161eba`).
- Rebuilt Simple Mode v2 Create surface with Image / Reference / Video /
  High-detail templates and dependency checks (`fd692d3`, `ba6131b`, `8a62966`,
  `3f7f6b5`), glassmorphic styling (`bf1997d`), and navigation prefetch
  (`bb8d913`).
- OpenTelemetry Flask instrumentation and OTLP exporter (`6c26e3b`, `c513bb7`,
  `pyproject.toml:20`–`23`).
- Multi-theme system with `ThemeManager` and CSS custom properties (`c1b132f`,
  `b9f13b0`).
- Social provider skeletons and VK OAuth2 with secure token storage (`53c6390`,
  `8532473`, `telethon` / `qrcode` in `pyproject.toml:18`–`19`).
- Vendored Fuse.js 7.0.0 fuzzy search (`94114cd`, `app/static/js/vendor/`).
- Masonry gallery with infinite scroll (`fd85fc8`).
- Paginated and memoized collections (`308b04c`).
- Deterministic default view bootstrap (`759bb50`).
- Decoupled sidebar / central gallery tabs (`9267226`, `4b230d0`).
- Cross-platform GitHub Actions CI workflow with linting (`25441dd`).
- Persisted and validated UI preferences (`0f14eb0`).
- GitHub Pages landing site, showcase assets, and icons (`e53de5a`, `df876ef`,
  `site/assets/`, `docs/icons/`).
- Comprehensive documentation under `docs/core/`, `docs/dev/`, `docs/ai/`,
  `docs/design/` (`e53de5a`, `df876ef`).

### Changed

- Consolidated CSS/JS modules and removed unused styles (`f7ab0f4`).
- Canonicalized the prompt registry while preserving `load_skill()` and moved
  family bases into `app/ai/prompting/content/profiles/` (`6b8c501`).
- Stabilized the AI Settings layout and bootstrap to remove layout shifts and
  button flicker (`78a4b4a`–`31c8bbe`).
- Scoped thumbnail decoding and reveal (`546d235`–`fbf2bc6`).
- Refactored database initialization (`694bfe9`) and simplified `app/comfyui`
  exports (`d468ae5`).
- Relaxed the `app` import for CI stdlib fallback (`0a0b31c`, `58bc7b0`) and
  restored Poetry/pyproject compatibility (`ee7b1af`).
- Improved performance: eliminated an N+1 query in folder processing
  (`4872922`), optimized tag assignment (`bd55331`), used batch album deletion
  via `executemany` (`84504c6`), and persisted custom sort order (`d33f2e7`,
  `ee1d079`).
- Switched licensing from GPL-3.0 to AGPL-3.0-only across `README.md`,
  `pyproject.toml:6`, and `LICENSE` (`3e1b314`).
- Translated and polished core documentation to English, aligned the API
  reference with Flask routes, and reorganized the roadmap under
  `dev_docs/roadmap/` (`875cb57`–`bc2217b`, `b39da02`, `f032ad2`–`e103948`).

### Fixed

- Sidebar collapse after resize (`c7efa9e`).
- Infinite gallery skeletons when empty after a hard reset (`c452118`).
- Empty-folder layout and folder-list refresh on upload (`32d0a7d`).
- Lightbox flicker and gallery pagination while browsing (`04447e7`, `2a416be`).
- Keyboard navigation scoped to the central folder (`e599454`, `481a841`).
- Search filtering applied independently to sidebar and central gallery
  (`9e49dc7`, `63deff9`).
- Live image updates without viewer flicker (`6c931c2`).
- Video gallery preserved after upload (`e6fec65`).
- Video file uploads (`8e22333`).
- LoRA metadata formatting (`cc19946`).
- Civitai toast spam, duplicate listeners, and the `results-empty` stub flash
  (`6811221`, `d267909`, `02dcd81`, `0fa5a9c`).
- Library page scrolling and preview controls (`f17e68c`, `b3070b4`).
- AI Settings layout and scrolling (`268eb3e`).
- Editor dialogs closed without submitting forms (`1fa294c`).
- Cancelled runs excluded from editor history; vertical resize in the lightbox
  (`b8b80cc`).
- Create downloads: cancellation made destructive and tasks preserved across
  navigation (`fd26fc2`, `132d48e`).
- Removed the `masterpiece` fallback from Simple Mode prompts (`18fd921`).

### Security

- Fixed SQL injection in `app/database.py:get_images_page` (`8f818db`),
  `app/library.py:get_assets` (`5b8a153`), and `list_metadata_filters`
  (`c1b2ed7`).
- Fixed command injection via ComfyUI Manager `extra_args` sanitization
  (`c8905ec`).
- Redacted AI transport responses and gateway payloads against secret exposure
  (`0a422ac`).
- Hardened the Windows `taskkill` fallback to `subprocess` calls without a shell
  (`7b93f9e`).

## [1.0.0] - 2026-07-16

Historic first release — MVP of the metadata viewer. Covers work from the
initial commit `8104d79` (`2026-06-16`) through the roadmap merge `8f078d3`.
Functionally and architecturally superseded by `[Unreleased]`; retained for
historical completeness.

### Added

- **Stack** — Python 3.10+ / Flask 3.1 / Pillow 11 / Poetry
  (`pyproject.toml:10`–`14` at tag), `pydantic` validation (`app/schemas.py:1`),
  `watchdog` monitoring, Vanilla JS (ES modules) SPA, CSS Custom Properties,
  `eslint.config.js:1` baseline.
- **Backend** — SQLite in WAL mode (`app/database.py:1`), PNG text-chunk /
  EXIF / ComfyUI workflow JSON extraction (`app/extractor.py:1`,
  `app/cutout.py:1`), thumbnail / preview / cutout caching in `cache/`,
  application data in `.comfy_meta_uploads/`, REST API and background worker
  (`app/main.py:1`, `c8ab68a`), Pydantic request/response models.
- **Frontend** — gallery with masonry layout (`f3f2ef5`), lightbox with cursor
  zoom / drag pan / original view (`4b3eed1`), sidebar with resize and folder
  list (`e01e749`), sorting with persisted state (`65801b7`, `0ea12d1`),
  summary / workflow (color-coded SVG graph) / raw metadata tabs (`ff92b83`).
- **Media operations** — folder scanning and indexing (`39c7446`), hard reset
  clearing database and thumbnail cache (`5385ee8`), image delete and
  selection (`afa24ce`, `49522dd`), diagnostics API and Help Center with
  14 keyboard shortcuts (`82bc3a1`), object cutout pipeline
  (`286797e`, `9a344f3`).
- **Docs & legal** — initial `docs/` (`da349be`), icons `docs/icons/`,
  `README.md` installation and usage, `LICENSE` (initially GPL-3.0), banner
  `docs/assets/readme-banner.png` (`ce10bed`).

### Changed

- Removed session management in favor of stateless restoration (`8c956e8`),
  consolidated styles.

### Fixed

- Early UI polish — modal dialogs, loading/error states (`9920b68`), badge
  visibility (`d34c3da`).

---

## Links

- Repository: <https://github.com/Lotargo/ComfyUI-Meta-Viewer>
- Architecture: `docs/core/architecture.md`
- API Reference: `docs/core/api.md`
- Features: `docs/core/features.md`
- AI Prompt Architecture: `docs/ai/prompt-architecture.md`
- Intent Benchmarks: `docs/ai/intent-benchmark.md`
- OpenCode Smoke Testing: `docs/ai/opencode-smoke-testing.md`
- Roadmap: `ROADMAP.md` and `dev_docs/roadmap/README.md`

[Unreleased]: https://github.com/Lotargo/ComfyUI-Meta-Viewer/compare/v1.0.0...HEAD
[1.0.0]: https://github.com/Lotargo/ComfyUI-Meta-Viewer/releases/tag/v1.0.0