# Development Roadmap

Эта директория содержит не последовательные фазы разработки, а самостоятельные технические задания по развитию ComfyUI Meta Viewer.

Документы намеренно не описывают каждый класс, функцию и промежуточный коммит. Большинство задач можно выполнить за один или несколько целевых заходов. Конкретный способ реализации выбирается во время работы с учётом текущего состояния проекта и актуальной документации используемых технологий.

## Общие принципы

- Приложение остаётся локальным и однопользовательским.
- Windows, Linux и macOS считаются равноправными целевыми платформами.
- Физические файлы не перемещаются ради альбомов, избранного и другой виртуальной организации.
- Облачные хранилища подключаются как обычные локальные директории, которыми управляет установленный desktop-клиент.
- ComfyUI интегрируется через стандартные структуры установки, локальный процесс и его API.
- Сложные механизмы восстановления, облачная авторизация и поддержка любых нестандартных окружений не являются обязательными.
- Для спорных или быстро меняющихся решений исполнитель должен сверяться с актуальными источниками, а не полагаться только на память модели.

## Индекс

### Core

- [x] [00. Cross-platform foundation](core/00_CROSS_PLATFORM_FOUNDATION.md)
- [x] [01. Database and index reset](core/01_DATABASE_AND_INDEX_RESET.md)
- [ ] [02. Source monitoring and cloud directories](core/02_SOURCE_MONITORING_AND_CLOUD_DIRECTORIES.md)

### Library

- [ ] [03. Media library, albums and favorites](library/03_MEDIA_LIBRARY_ALBUMS_AND_FAVORITES.md)
- [ ] [04. Unified media assets and video](library/04_UNIFIED_MEDIA_ASSETS_AND_VIDEO.md)

### AI

- [ ] [05. AI provider layer](ai/05_AI_PROVIDER_LAYER.md)
- [ ] [06. Prompt skills research](ai/06_PROMPT_SKILLS_RESEARCH.md)
- [ ] [07. Translation, remix and AI ranking](ai/07_TRANSLATION_REMIX_AND_AI_RANKING.md)

### ComfyUI

- [ ] [08. Runtime integration and process control](comfyui/08_RUNTIME_INTEGRATION_AND_PROCESS_CONTROL.md)
- [ ] [09. Workflow templates and editor](comfyui/09_WORKFLOW_TEMPLATES_AND_EDITOR.md)

### Desktop

- [ ] [10. Desktop packaging and installers](desktop/10_DESKTOP_PACKAGING_AND_INSTALLERS.md)

## Как отмечать выполнение

Чекбокс в этом файле отмечается только после завершения всего связанного документа. Внутренние документы не обязаны содержать собственные чеклисты: критерии готовности в конце каждого задания используются для проверки результата.
