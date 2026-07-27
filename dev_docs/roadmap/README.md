# Development Roadmap

Эта директория хранит архитектурные документы, подтверждённый технический baseline и рабочий путь к первому публичному релизу ComfyUI Meta Viewer.

Roadmap должен сохранять память о выполненной работе, но не превращать каждую будущую идею и редкую проверку в обязательный blocker релиза.

## С чего продолжать

Открыть [v1 Execution Plan](EXECUTION_PLAN.md) и переходить к **созданию release tag `v1.0.0`**.

Текущая последовательность:

1. CI на Windows, Linux и macOS.
2. Clean install и запуск приложения.
3. Короткий Viewer/Library smoke.
4. Один end-to-end ComfyUI run на текущем `main`.
5. Обновление публичного README и release tag.

Новые templates, расширение AI rating и desktop packaging до этого не являются текущим рабочим срезом.

## Рабочие документы

- [v1 Execution Plan](EXECUTION_PLAN.md) — выполненные крупные блоки, текущие release gates и следующий рабочий шаг.
- [Workflow template and resource baseline](WORKFLOW_TEMPLATE_BASELINE.md) — проверенный снимок built-in templates, manifest v2, bindings, taxonomy и runtime evidence.
- Документы `00–10` — архитектурные требования отдельных подсистем и идеи дальнейшего развития.

## Значение статусов

- **Completed** — основная реализация закончена и подтверждена кодом, тестами или runtime evidence.
- **Release verification** — подсистема реализована; перед v1 нужен только короткий пользовательский smoke, а не новая фаза разработки.
- **Post-v1** — полезное расширение или полная compatibility matrix, которая не блокирует первый релиз.

## Текущий статус проекта

### 00. Cross-platform foundation

**Status: Release verification.**

Path abstractions, platform actions и fallback behavior реализованы. Перед v1 достаточно подтвердить CI на трёх runner OS и clean install на основной release-платформе. Полная ручная матрица Unicode, UNC и всех platform actions остаётся post-v1, если CI не выявит конкретную ошибку.

### 01. Database and index reset

**Status: Completed.**

Factory Reset, отдельный reset индекса, повторная индексация и сохранность исходных files реализованы. Перед релизом остаётся короткий smoke, что reset/reindex не удаляет media.

### 02. Source monitoring and cloud directories

**Status: Release verification.**

Watcher и periodic reconciliation foundation реализованы. Для v1 нужен обычный source-directory smoke. Длительные reconnect, temporarily unavailable drives и массовая cloud-sync матрица перенесены после релиза.

### 03. Media library, albums and favorites

**Status: Completed.**

Library, albums, favorites, ratings, tags, notes, bulk selection и раздельные виды удаления реализованы. Перед тегом проверяется только persistence одной базовой операции после restart.

### 04. Unified media assets and video

**Status: Release verification.**

Images и videos используют общую asset model, browsing и technical metadata. Перед v1 проверяется по одному реальному image/video asset и понятное поведение при отсутствии FFmpeg. Полная container matrix не блокирует релиз.

### 05. AI provider layer

**Status: Completed for v1 scope.**

Сохранённые OpenAI-compatible и CLI profiles, Keyring/env credentials, normalized errors и capability-based adapters реализованы. Полная parity всех transports не нужна для выпуска основной Viewer/ComfyUI functionality.

### 06. Prompt skills research

**Status: Completed baseline; further research is Post-v1.**

Flux-like, SDXL и Pony family profiles и основные scenario manifests существуют. Дополнительные operation benchmarks, repeat-run statistics и checkpoint-specific capability profiles развиваются после релиза.

### 06A. Prompt profile and agent execution architecture

**Status: Completed.**

PromptTask, SceneSpec, PromptResult, compiler contracts, persistence и execution adapters реализованы и подключены к editor drafts. Reconstruct и Adapt имеют реальный runtime evidence.

### 07. Translation, remix and AI ranking

**Status: Core operations completed; rating automation is Post-v1.**

Generate, Translate, Adapt, Reconstruct и Remix создают persisted editable drafts и не запускают generation автоматически. Source/result, revisions и lineage сохраняются.

Manual AI rating foundation также реализована: отдельные technical states, nullable artistic rank, ручной запуск, override/delete и Library filters. Global/per-run opt-in и расширенная provider-policy matrix не блокируют v1.

### 08. Runtime integration and process control

**Status: Release verification.**

Runtime setup, inventory, preflight, queue/run state, cancellation foundation, result import и normalized errors реализованы. Перед v1 нужен один повторный end-to-end run на текущем `main`. Полная матрица Portable/venv/external/port conflict/crash остаётся post-v1.

### 09. Workflow templates and editor

**Status: Completed.**

Реализованы:

- manifest v2 и semantic resource slots;
- checkpoint-contained, separate-components, GGUF, reference, two-stage и video templates;
- resource compatibility filtering и preflight;
- API/UI workflow import;
- mapping wizard и registry statuses;
- management table, revalidation, remap, duplicate, export и delete;
- field-level ComfyUI error diagnostics;
- draft/run persistence и imported-result provenance.

Технический состав и runtime evidence подробно зафиксированы в [WORKFLOW_TEMPLATE_BASELINE.md](WORKFLOW_TEMPLATE_BASELINE.md).

### 10. Desktop packaging and installers

**Status: Post-v1.**

Desktop shell, bundled runtime, installers, signing и auto-update начинаются после стабилизации и публикации Python/local-web версии. Они не должны использоваться как условие первого релиза.

## Уже подтверждённые end-to-end сценарии

В ходе разработки получен реальный runtime evidence для:

- `core-image` с отдельным negative conditioning и импортом результата;
- Reconstruct: image → persisted SceneSpec → prompt render без повторного vision call;
- Remix через Windows Portable ComfyUI с ручным Run и сохранённым lineage;
- Pony/SDXL GGUF quality generation в 832×1216;
- Flux-family GGUF generation;
- workflow import/remap/duplicate/export lifecycle.

Эти доказательства не следует обнулять. Перед v1 выполняется один короткий regression run на текущем commit, а не повтор всей исторической матрицы.

## Границы первого релиза

В v1 входят:

- локальный запуск приложения;
- индексирование пользовательских директорий;
- Viewer и metadata extraction;
- image/video Library и виртуальная организация;
- подключение ComfyUI;
- manifest-driven editor и базовые built-in workflows;
- один подтверждённый основной generation path;
- AI prompt drafts как дополнительная функция;
- честная документация известных ограничений.

## После v1

Без блокировки первого релиза продолжаются:

- дополнительные inpaint, ControlNet, pose, upscale, refiner и video workflows;
- полная поддержка редких custom loaders и multiple independent pipelines;
- автоматический model importer/registration wizard;
- полные cross-platform и ComfyUI installation matrices;
- длительные watcher/cloud/reconnect stress tests;
- расширенные prompt benchmarks и transport parity;
- global/per-run AI rating automation;
- desktop packaging и auto-update.

## Рабочий протокол

- Коммитить логически завершённые и проверенные срезы напрямую в `main`.
- Не возвращать завершённую подсистему в общий статус «не готово» из-за post-v1 edge cases.
- Реальный ComfyUI run требуется для end-to-end gate, но не для каждого unit-level изменения.
- Browser automation используется для коротких однозначных smoke checks и не заменяет полноценный визуальный review.
- Новый release blocker добавляется только при наличии конкретного воспроизводимого дефекта.

## Архитектурные документы

### Core

- [00. Cross-platform foundation](core/00_CROSS_PLATFORM_FOUNDATION.md)
- [01. Database and index reset](core/01_DATABASE_AND_INDEX_RESET.md)
- [02. Source monitoring and cloud directories](core/02_SOURCE_MONITORING_AND_CLOUD_DIRECTORIES.md)

### Library

- [03. Media library, albums and favorites](library/03_MEDIA_LIBRARY_ALBUMS_AND_FAVORITES.md)
- [04. Unified media assets and video](library/04_UNIFIED_MEDIA_ASSETS_AND_VIDEO.md)

### AI

- [05. AI provider layer](ai/05_AI_PROVIDER_LAYER.md)
- [06. Prompt skills research](ai/06_PROMPT_SKILLS_RESEARCH.md)
- [06A. Prompt profile and agent execution architecture](ai/06A_PROMPT_PROFILE_AND_AGENT_EXECUTION_ARCHITECTURE.md)
- [07. Translation, remix and AI ranking](ai/07_TRANSLATION_REMIX_AND_AI_RANKING.md)

### ComfyUI and desktop

- [08. Runtime integration and process control](comfyui/08_RUNTIME_INTEGRATION_AND_PROCESS_CONTROL.md)
- [09. Workflow templates and editor](comfyui/09_WORKFLOW_TEMPLATES_AND_EDITOR.md)
- [10. Desktop packaging and installers](desktop/10_DESKTOP_PACKAGING_AND_INSTALLERS.md)
