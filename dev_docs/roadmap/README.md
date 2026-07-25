# Development Roadmap

Эта директория содержит архитектурные технические задания и подробную карту их интеграции в ComfyUI Meta Viewer.

Проект перешёл из фазы добавления отдельных возможностей в фазу сложной продуктовой интеграции. Поэтому верхнеуровневого списка из нескольких галочек больше недостаточно: наличие backend-класса, API route или страницы ещё не означает, что пользовательский сценарий завершён и проверен.

## Основные документы

- [Detailed execution roadmap](EXECUTION_PLAN.md) — текущая последовательность разработки, зависимости, gates и детализированные чеклисты.
- [Workflow template and resource baseline](WORKFLOW_TEMPLATE_BASELINE.md) — проверенный снимок built-in templates, bindings и канонической resource taxonomy.
- Документы `00–10` — архитектурные требования и критерии готовности отдельных подсистем.

## Как теперь отмечается выполнение

- `[x]` означает, что весь связанный документ реализован, интегрирован и проверен по его критериям готовности.
- `[ ]` означает, что остаётся реализация, интеграция, практическая проверка или подтверждение на целевых окружениях.
- Статус `implemented` в пояснении означает, что существенная часть кода уже существует, но верхнеуровневая задача пока не закрыта.
- Детальный прогресс отмечается в [EXECUTION_PLAN.md](EXECUTION_PLAN.md), а не новой преждевременной галочкой в этом файле.

## Текущий критический путь

1. Workflow template contracts и resource taxonomy.
2. Базовые templates для разных способов загрузки моделей.
3. Импорт, регистрация и управление пользовательскими workflows.
4. Model compatibility, preflight и понятная диагностика ComfyUI errors.
5. Интеграция Generate, Translate, Adapt, Reconstruct и Remix с editor drafts.
6. Практические prompt и end-to-end проверки.
7. Опциональный AI rating.
8. Release verification.
9. Desktop packaging.

## Общие принципы

- Приложение остаётся локальным и однопользовательским.
- Windows, Linux и macOS считаются равноправными целевыми платформами.
- Физические файлы не перемещаются ради альбомов, избранного и другой виртуальной организации.
- Облачные хранилища подключаются как обычные локальные директории, которыми управляет установленный desktop-клиент.
- ComfyUI интегрируется через стандартные структуры установки, локальный процесс и его API.
- Meta Viewer не пытается заменить ComfyUI Manager и не обещает запуск любого неизвестного model file.
- Prompt scenario и workflow template являются разными сущностями.
- AI-операции создают редактируемый draft и не запускают генерацию автоматически.
- Основной editor остаётся простым; технические параметры раскрываются только при применимости или конкретной ошибке.
- AI rating является отдельной опциональной функцией и не блокирует основной сценарий.
- Для спорных или быстро меняющихся решений исполнитель сверяется с актуальными источниками и реальными API, а не полагается только на память модели.

## Рабочий протокол для исполнителя

Эти правила действуют по умолчанию на протяжении работы над roadmap и не требуют повторного подтверждения пользователя:

- Исполнитель самостоятельно определяет логические границы коммитов и создаёт коммиты после завершения связного, проверенного среза. Незавершённые или не прошедшие обязательные проверки изменения не коммитятся как завершённый результат.
- Исполнитель самостоятельно решает, когда для текущего gate нужен реальный запуск ComfyUI. Задачи runtime integration, workflow compatibility и end-to-end generation не отмечаются выполненными только по unit-тестам или анализу кода, если roadmap требует практической проверки.
- Для реальных AI-проверок исполнитель самостоятельно выбирает подходящий уже настроенный LLM profile. Если существующие profiles не обеспечивают воспроизводимый или изолированный сценарий, исполнитель может создать отдельный test profile, не изменяя и не раскрывая сохранённые credentials без необходимости.
- Browser automation используется только для простых, быстрых и узко ограниченных smoke checks, где результат можно однозначно подтвердить: страница открывается, ожидаемый control присутствует, короткое действие даёт ожидаемое состояние, отсутствует явная runtime error.
- Browser automation не используется как замена полноценному визуальному QA, длительному исследованию интерфейса или исчерпывающей проверке всех пользовательских сценариев. Исполнитель не тратит значительный объём работы на browser-проверку, если доступные средства не позволяют надёжно увидеть и оценить весь результат.
- Когда нужен детальный UI review — композиция, responsive behavior на нескольких размерах, визуальные дефекты, сложные interaction flows или субъективная оценка удобства — исполнитель подготавливает конкретный checklist и просит пользователя провести проверку. Полученные наблюдения фиксируются как evidence для соответствующего roadmap gate.
- Невыполненная ручная UI-проверка явно остаётся pending и не маскируется успешными unit/API/browser smoke tests.

## Status dashboard

### Core

- [ ] [00. Cross-platform foundation](core/00_CROSS_PLATFORM_FOUNDATION.md)  
  **Implemented; verification pending.** Нужна подтверждённая матрица Windows, Linux и macOS, включая Unicode paths, picker fallback и platform actions.

- [x] [01. Database and index reset](core/01_DATABASE_AND_INDEX_RESET.md)  
  **Completed.** Физический reset, Factory Reset, отдельная конфигурация источников и повторная индексация реализованы.

- [ ] [02. Source monitoring and cloud directories](core/02_SOURCE_MONITORING_AND_CLOUD_DIRECTORIES.md)  
  **Implemented; stress verification pending.** Нужны реальные массовые sync/reconnect проверки, временно недоступные диски и длительная работа watcher/reconcile.

### Library

- [x] [03. Media library, albums and favorites](library/03_MEDIA_LIBRARY_ALBUMS_AND_FAVORITES.md)  
  **Completed.** Отдельная Library, albums, favorites, tags, notes, ratings, bulk actions и различимые виды удаления реализованы.

- [ ] [04. Unified media assets and video](library/04_UNIFIED_MEDIA_ASSETS_AND_VIDEO.md)  
  **Implemented; media matrix pending.** Нужны проверки FFmpeg/no-FFmpeg, разных video containers, poster failures и сохранения virtual relations.

### AI

- [ ] [05. AI provider layer](ai/05_AI_PROVIDER_LAYER.md)  
  **Implemented; integration and environment verification pending.** Профили, Keyring/env credentials, CLI adapters и normalized errors существуют, но нужны реальные provider/OS checks и полное использование в editor operations.

- [ ] [06. Prompt skills research](ai/06_PROMPT_SKILLS_RESEARCH.md)  
  **Partially verified.** Базовые Flux-like, SDXL и Pony profiles существуют, но остаются operation benchmarks, multimodal tests, независимые SDXL/Pony проверки и checkpoint capability profiles.

- [ ] [06A. Prompt profile and agent execution architecture](ai/06A_PROMPT_PROFILE_AND_AGENT_EXECUTION_ARCHITECTURE.md)  
  **Implemented; product integration pending.** Compiler, contracts, persistence и adapters существуют, но должны быть замкнуты на editor drafts и проверены одинаковым PromptTask через direct и agent-host execution.

- [ ] [07. Translation, remix and AI ranking](ai/07_TRANSLATION_REMIX_AND_AI_RANKING.md)  
  **Active integration phase.** Remix и backend foundations существуют; Generate, Translate, Adapt, editable SceneSpec, Reconstruct и опциональный AI rating должны стать законченными пользовательскими потоками.

### ComfyUI

- [ ] [08. Runtime integration and process control](comfyui/08_RUNTIME_INTEGRATION_AND_PROCESS_CONTROL.md)  
  **Implemented; runtime matrix pending.** Нужны реальные проверки Windows Portable, venv installations, managed/external modes, crash, port conflict и process cleanup.

- [ ] [09. Workflow templates and editor](comfyui/09_WORKFLOW_TEMPLATES_AND_EDITOR.md)  
  **Current primary workstream.** Редактор, loader contracts, resource filtering, API workflow registration, mapping wizard, registry statuses и management table реализованы; остаются UI workflow conversion, remap/duplicate/export operations и field-level error diagnostics.

### Desktop

- [ ] [10. Desktop packaging and installers](desktop/10_DESKTOP_PACKAGING_AND_INSTALLERS.md)  
  **Deferred.** Начинается только после завершения основной интеграции и release verification.

## Ближайший рабочий срез

Подробные пункты находятся в разделах `Current execution slice`, `Phase 2`, `Phase 3`, `Phase 4` и `Phase 6` файла [EXECUTION_PLAN.md](EXECUTION_PLAN.md).

Основной фокус:

- [x] Инвентаризировать существующие workflow templates.
- [x] Утвердить resource taxonomy.
- [x] Разделить checkpoint-contained, separate-components и GGUF templates.
- [x] Фильтровать resources по semantic slots.
- [x] Регистрировать imported API workflows и сохранять автоматически найденные mappings.
- [x] Разрешать неоднозначные bindings через mapping wizard с manifest preview.
- [x] Добавить workflow management modal/table и revalidation statuses.
- [ ] Связывать ComfyUI errors с конкретными editor fields.
- [ ] После стабилизации contracts подключить AI operations к drafts.

AI rating, полностью автоматический model importer и desktop packaging в текущий рабочий срез не входят.
