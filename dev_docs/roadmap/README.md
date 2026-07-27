# Development Roadmap

Эта директория хранит направление развития ComfyUI Meta Viewer, а не бесконечный список условий для «идеального» релиза.

Главная цель сейчас — выпустить рабочую и понятную версию v1. Дополнительные шаблоны, редкие окружения и глубокие стресс-проверки не должны блокировать публикацию уже полезного приложения.

## Рабочий документ

- [Detailed execution roadmap](EXECUTION_PLAN.md) — текущая последовательность разработки, зависимости, gates и детализированные чеклисты.
- [Workflow template and resource baseline](WORKFLOW_TEMPLATE_BASELINE.md) — проверенный снимок built-in templates, bindings и канонической resource taxonomy.
- Документы `00–10` — архитектурные требования и идеи дальнейшего развития. They form the foundation for development.


## Принцип release-first

Задача считается блокирующей релиз только тогда, когда без неё пользователь не может установить приложение, открыть библиотеку, просмотреть метаданные или выполнить основной сценарий с ComfyUI.

Проверки отдельных контейнеров, редких путей, длительных reconnect-сценариев, всех возможных моделей и каждого AI-провайдера выполняются по мере необходимости или после релиза. Они не должны возвращать уже работающую подсистему в состояние «не готово».

## Текущий объём v1

В первый публичный релиз входят:

- локальный просмотр и индексация изображений и видео;
- извлечение и отображение метаданных ComfyUI;
- библиотека с виртуальной организацией файлов;
- запуск приложения на поддерживаемых версиях Python;
- один подтверждённый полный сценарий генерации через ComfyUI;
- понятная инструкция установки и список известных ограничений.

## Рабочий протокол для исполнителя

Эти правила действуют по умолчанию на протяжении работы над roadmap и не требуют повторного подтверждения пользователя:

- Исполнитель самостоятельно определяет логические границы коммитов и создаёт коммиты после завершения связного, проверенного среза. Незавершённые или не прошедшие обязательные проверки изменения не коммитятся как завершённый результат.
- Исполнитель самостоятельно решает, когда для текущего gate нужен реальный запуск ComfyUI. Задачи runtime integration, workflow compatibility и end-to-end generation не отмечаются выполненными только по unit-тестам или анализу кода, если roadmap требует практической проверки.
- Для реальных AI-проверок исполнитель самостоятельно выбирает подходящий уже настроенный LLM profile. Если существующие profiles не обеспечивают воспроизводимый или изолированный сценарий, исполнитель может создать отдельный test profile, не изменяя и не раскрывая сохранённые credentials без необходимости.
- Browser automation используется только для простых, быстрых и узко ограниченных smoke checks, где результат можно однозначно подтвердить: страница открывается, ожидаемый control присутствует, короткое действие даёт ожидаемое состояние, отсутствует явная runtime error.
- Browser automation не используется как замена полноценному визуальному QA, длительному исследованию интерфейса или исчерпывающей проверке всех пользовательских сценариев. Исполнитель не тратит значительный объём работы на browser-проверку, если доступные средства не позволяют надёжно увидеть и оценить весь результат.
- Когда нужен детальный UI review — композиция, responsive behavior на нескольких размерах, визуальные дефекты, сложные interaction flows или субъективная оценка удобства — исполнитель подготавливает конкретный checklist и просит пользователя провести проверку. Полученные наблюдения фиксируются как evidence для соответствующего roadmap gate.
- Невыполненная ручная UI-проверка явно остаётся pending и не маскируется успешными unit/API/browser smoke tests.

## После v1

В последующие версии можно развивать:

- дополнительные workflow templates и loader strategies;
- расширенный импорт пользовательских workflows;
- GGUF и редкие наборы custom nodes;
- полную матрицу окружений Windows, Linux и macOS;
- длительные watcher, cloud-sync и reconnect stress tests;
- дополнительные AI operations, benchmarks и AI rating;
- desktop installers и автоматическое обновление.

Эти пункты остаются важными, но больше не изображают обязательную месячную работу перед первым релизом.

## Status dashboard

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
- [ ] [06A. Prompt profile and agent execution architecture](ai/06A_PROMPT_PROFILE_AND_AGENT_EXECUTION_ARCHITECTURE.md)  
  **Implemented; product integration pending.** Compiler, contracts, persistence и adapters существуют, но должны быть замкнуты на editor drafts и проверены одинаковым PromptTask через direct и agent-host execution.

- [ ] [07. Translation, remix and AI ranking](ai/07_TRANSLATION_REMIX_AND_AI_RANKING.md)
  **Active AI rating phase.** Generate, отдельный Translate, family-aware Adapt, Reconstruct через persisted editable SceneSpec и Remix с выбором source/workflow создают связанные editor drafts без автоматического запуска. Для опционального AI rating реализованы nullable artistic rank, раздельные technical statuses, безопасный выбор сохранённого multimodal profile, ручной запуск/override/delete и Library filters; остаются global/per-run opt-in, интерактивная UI-проверка и реальные provider-policy checks.

### ComfyUI

- [ ] [08. Runtime integration and process control](comfyui/08_RUNTIME_INTEGRATION_AND_PROCESS_CONTROL.md)  
  **Implemented; runtime matrix pending.** Нужны реальные проверки Windows Portable, venv installations, managed/external modes, crash, port conflict и process cleanup.

- [x] [09. Workflow templates and editor](comfyui/09_WORKFLOW_TEMPLATES_AND_EDITOR.md)
  **Completed.** Редактор, loader contracts, resource filtering, API/UI workflow registration, повторный remap, registry statuses, management table, duplicate/export и field-level runtime diagnostics реализованы. Built-in templates защищены от изменения, удаления и перекрытия user template с тем же ID.

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
- [x] Преобразовывать поддерживаемые UI workflow JSON в API graph перед регистрацией.
- [x] Разрешать неоднозначные bindings через mapping wizard с manifest preview.
- [x] Добавить workflow management modal/table и revalidation statuses.
- [x] Повторно открывать mapping wizard для зарегистрированных пользовательских workflows.
- [x] Дублировать и экспортировать зарегистрированные workflows через management table.
- [x] Связывать ComfyUI errors с конкретными editor fields.
- [x] Подключить Generate prompt к editor draft без автоматического запуска generation.
- [x] Подключить Translate как отдельную операцию с сохранением source/result.
- [x] Подключить Adapt как отдельную family-aware операцию с сохранением source/result.
- [x] Подключить Reconstruct через editable persisted SceneSpec и повторный render без vision call.
- [x] Подключить Remix с выбором persisted prompt source и compatible workflow, сохраняя lineage.
- [x] После стабилизации contracts подключить AI operations к drafts.
- [x] Отделить AI rank от technical evaluation statuses и user stars.
- [x] Добавить ручной AI rating для Library asset через сохранённый multimodal profile.
- [x] Добавить override/delete и отдельные Library filters по AI rank/status.
- [ ] Добавить global/per-run opt-in и проверить AI rating на реальных provider policies.
Полностью автоматический model importer и desktop packaging в текущий рабочий срез не входят.

