# Development Roadmap

Эта директория хранит направление развития ComfyUI Meta Viewer, а не бесконечный список условий для «идеального» релиза.

Главная цель сейчас — выпустить рабочую и понятную версию v1. Дополнительные шаблоны, редкие окружения и глубокие стресс-проверки не должны блокировать публикацию уже полезного приложения.

## Рабочие документы

- [Короткий план релиза v1](EXECUTION_PLAN.md) — единственный текущий список обязательных задач.
- [Workflow template and resource baseline](WORKFLOW_TEMPLATE_BASELINE.md) — проверенный снимок built-in templates, bindings и канонической resource taxonomy.
- Документы `00–10` — архитектурные требования и идеи дальнейшего развития. Они не являются обязательным чеклистом перед первым релизом.

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

## Рабочий протокол

- Логические и проверенные срезы коммитятся самостоятельно; незавершённая работа не отмечается как готовая.
- Runtime integration и end-to-end generation подтверждаются реальным запуском ComfyUI, когда это требуется сценарием.
- Browser automation используется для коротких и однозначных smoke checks, но не подменяет полноценный визуальный QA.
- Детальная ручная UI-проверка остаётся pending, пока пользователь её не подтвердил.

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
