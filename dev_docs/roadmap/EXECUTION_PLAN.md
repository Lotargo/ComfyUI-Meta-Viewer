# v1 Execution Plan

Этот документ показывает три вещи одновременно:

1. что в проекте уже реализовано и не должно планироваться заново;
2. какие проверки действительно остались перед первым публичным релизом;
3. с какого конкретного шага продолжать работу.

Подробные документы `00–10` остаются архитектурными требованиями, а [WORKFLOW_TEMPLATE_BASELINE.md](WORKFLOW_TEMPLATE_BASELINE.md) фиксирует технический baseline workflow templates и resource taxonomy. Этот файл — рабочая последовательность до v1, а не исчерпывающий список всех будущих улучшений.

## Правила статусов

- `[x]` — результат реализован и подтверждён кодом, тестами или сохранённым runtime evidence.
- `[ ]` — конкретная работа, которая ещё нужна для выпуска v1.
- Пункты раздела `После v1` не блокируют релиз и намеренно не оформлены как обязательные чекбоксы.
- Уже реализованная подсистема не возвращается в состояние «не готово» только из-за отсутствия полной матрицы редких окружений.

## Текущая позиция

Основная продуктовая интеграция уже выполнена. Workflow editor, template contracts, import/registry, resource compatibility, preflight, AI drafts и базовая Library существуют и связаны между собой.

Оставшаяся работа перед v1 — это прежде всего:

1. подтвердить исправленный CI;
2. выполнить короткий smoke в чистом окружении;
3. повторить один стабильный end-to-end run через ComfyUI на текущем `main`;
4. обновить публичную документацию и выпустить тег.

## Начать отсюда

**Текущий первый шаг: Создать release tag (v1.0.0) для первого публичного релиза.**

До завершения release gates не следует возвращаться к расширению AI rating, добавлению новых template families, универсальному model importer или desktop packaging, если только не найден дефект, реально мешающий установке или основному сценарию.

---

# Выполненные крупные блоки

Эти пункты сохраняются в плане, чтобы не потерять историю прогресса и не выполнять уже сделанную работу повторно.

## A. Core, index и Library

- [x] Локальная однопользовательская архитектура без обязательного облачного backend.
- [x] Индексация подключённых директорий без перемещения исходных файлов.
- [x] Factory Reset и отдельный reset индекса без удаления пользовательских media files.
- [x] Source watcher и periodic reconciliation foundation.
- [x] Media Library с albums, favorites, ratings, tags, notes и bulk selection.
- [x] Разделение удаления из индекса, виртуальной организации и physical Trash.
- [x] Единая модель image/video assets, previews и technical metadata.
- [x] Импорт результатов генерации обратно в Library с provenance.

## B. Workflow templates и editor

- [x] Manifest schema v2 с identity, capabilities, resource slots, editable fields и bindings.
- [x] Каноническая resource taxonomy и compatibility aliases.
- [x] Отдельные templates для checkpoint-contained, Flux separate-components и GGUF generation.
- [x] Built-in reference/img2img, two-stage и video templates.
- [x] Template-aware resource filtering и сохранение несовместимого выбора без молчаливого удаления.
- [x] Runtime inventory и dependency preview.
- [x] Preflight перед каждым run: runtime, nodes, resources, slots и known parameter ranges.
- [x] Нормализация ComfyUI errors с node/input mapping и подсветкой editor fields.
- [x] Workflow draft и run persistence с восстановлением после reload/restart.

## C. Import и управление workflows

- [x] Импорт ComfyUI API workflow JSON.
- [x] Преобразование поддерживаемого UI workflow JSON в API graph.
- [x] Автоматическое обнаружение loaders, prompt encoders, sampler, dimensions и outputs.
- [x] Mapping wizard для неоднозначных bindings и неизвестных custom loaders.
- [x] Registry statuses: ready, warning, invalid и partially mapped/expert.
- [x] Workflow management table с поиском, filtering и revalidation.
- [x] Повторный remap зарегистрированного user workflow.
- [x] Duplicate, export и delete для user templates.
- [x] Built-in templates защищены от удаления и перекрытия user template с тем же ID.

## D. AI prompt layer

- [x] Строгие contracts PromptTask, SceneSpec, PromptResult и InstructionBundle.
- [x] Family profiles для Flux-like, SDXL и Pony.
- [x] Сохранённые OpenAI-compatible и CLI profiles без раскрытия credentials.
- [x] Generate создаёт редактируемый editor draft без автоматического запуска ComfyUI.
- [x] Translate хранит source и translated result раздельно.
- [x] Adapt сохраняет target family, revisions и проверенные checkpoint triggers.
- [x] Reconstruct разделён на persisted editable SceneSpec и отдельный render без повторного vision call.
- [x] Remix позволяет выбрать persisted source prompt и compatible workflow, сохраняя lineage.
- [x] Negative prompt сохраняется отдельным conditioning и проходит в metadata результата.

## E. Runtime evidence, уже полученный в разработке

- [x] Реальный `core-image` run подтвердил отдельный negative conditioning и импорт результата.
- [x] Reconstruct подтверждён реальным multimodal OpenCode profile: image → SceneSpec → render без второго image call.
- [x] Remix подтверждён реальным Windows Portable ComfyUI run с ручным запуском и `derived_from_asset_id`.
- [x] Pony/SDXL GGUF generation подтверждён quality run в 832×1216 с импортом и provenance.
- [x] Flux-family GGUF generation подтверждён отдельным Krea-based run с импортом результата.
- [x] Workflow template management, duplicate/export и import round-trip покрыты реализацией и regression tests.

## F. Опциональный AI rating

- [x] AI rating отделён от user stars и technical generation statuses.
- [x] Отсутствие профиля или provider refusal не мешает сохранению asset.
- [x] Ручной запуск rating для Library asset через сохранённый multimodal profile.
- [x] Nullable artistic rank для not-rated, rejected, unreadable и generation-error states.
- [x] Manual override и удаление rating.
- [x] Отдельные Library filters по AI rank и rating status.

AI rating уже имеет рабочую foundation, но его дальнейшее расширение не является условием выпуска v1.

---

# Release gates

## Gate 1. CI и чистая установка — CURRENT

Цель: подтвердить, что проект устанавливается из репозитория без локальных случайных зависимостей.

### 1.1 GitHub Actions

- [x] Найдена причина падения всех трёх jobs: `pyproject.toml` перестал соответствовать `poetry.lock` после добавления обязательного `rich`.
- [x] `pyproject.toml` снова синхронизирован с существующим lock-файлом.
- [x] Для terminal smoke tools добавлен stdlib fallback; настоящий Rich используется, когда установлен.
- [x] Подтвердить свежий успешный `poetry install --no-root` и прохождение всего тестового набора (`pytest`, `unittest`, `test:preferences`, `test:metadata`, `lint`).
- [x] Проверены оставшиеся test steps (347 Python tests, 10 JS tests, ESLint clean).

**Exit criteria:** все обязательные CI jobs зелёные либо конкретная недоступная проверка честно помечена как non-blocking с объяснением.

### 1.2 Clean environment smoke

- [x] Создать чистое Python-окружение на основной release-платформе (Windows).
- [x] Выполнить установку по README (`poetry install --no-root`).
- [x] Запустить импорт/приложение без обязательного установленного Rich (stdlib fallback работает).
- [x] Открыть главную страницу без import/runtime error (HTTP 200 OK на `/`).

**Exit criteria:** новый пользователь может выполнить документированную установку без знаний о внутренней истории проекта.

---

## Gate 2. Core application smoke

Цель: проверить не каждую комбинацию ОС, а основной пользовательский путь v1.

- [x] Добавить или выбрать source directory с реальными ComfyUI outputs.
- [x] Дождаться индексации и увидеть media в Viewer/Library.
- [x] Открыть одно изображение и проверить prompt, model и основные generation parameters.
- [x] Открыть одно видео и проверить preview/technical metadata; отсутствие FFmpeg должно давать понятное ограничение, а не падение приложения.
- [x] Добавить asset в album или favorites.
- [x] Перезапустить приложение и подтвердить сохранение виртуального состояния.
- [x] Выполнить reset/reindex smoke и подтвердить, что исходные files не удалены.

**Exit criteria:** просмотр, индекс, базовая Library и persistence работают в одном чистом пользовательском сценарии.

---

## Gate 3. ComfyUI end-to-end smoke на текущем main

Старые runtime evidence остаются действительными как доказательство архитектуры, но перед тегом нужен один короткий повторный run после последних изменений и merge conflict.

Рекомендуемый стабильный сценарий: `core-image` с обычным checkpoint-contained model. Если текущее локальное окружение лучше подготовлено для `core-reference`, допускается использовать его и явно записать выбор.

- [x] Подключить одну реально поддерживаемую установку ComfyUI.
- [x] Проверить runtime online и загрузку inventory.
- [x] Открыть выбранный built-in template.
- [x] Выбрать model resources и получить `ready` preview/preflight.
- [x] Запустить generation отдельным ручным действием.
- [x] Дождаться terminal success без зависшего run state.
- [x] Подтвердить импорт output в Library.
- [x] Проверить template, draft, run, prompt и model provenance.
- [x] Для reference/remix сценария дополнительно проверить lineage к source asset.
- [x] Проверить одну понятную diagnostic path, например missing resource или invalid parameter, без расширения полноценной failure matrix.

**Exit criteria:** один основной путь generation завершён на текущем commit, а ошибка одного известного типа объясняется пользователю без raw-only сообщения.

---

## Gate 4. Public documentation и release

- [x] Сверить feature list корневого README с реально доступным UI.
- [x] Обновить Quick Start по результатам clean environment smoke.
- [x] Указать поддерживаемый диапазон Python и проверенную release-платформу.
- [x] Добавить краткий раздел Known limitations.
- [x] Явно указать, что не все custom nodes, model families и imported workflows гарантированно совместимы.
- [x] Указать статус desktop installers: после v1, запуск пока через Python/local web app.
- [x] Проверить ссылки на roadmap и technical docs.
- [ ] Создать release tag после закрытия Gate 1–3.

**Exit criteria:** публичные обещания совпадают с подтверждённым поведением, а пользователь понимает установку и ограничения.

---

# Что не блокирует v1

Следующие направления остаются ценными, но выполняются после первого релиза или при появлении конкретного пользовательского запроса:

- полная матрица Windows, Linux и macOS с Unicode, UNC и разными filesystem behaviors;
- длительные watcher, reconnect и cloud-sync stress tests;
- проверка каждого способа установки ComfyUI и каждого port/crash scenario;
- новые inpaint, ControlNet, pose, upscale, refiner и video template variants;
- универсальное распознавание любого неизвестного workflow и multiple independent pipelines;
- автоматический model registration/import wizard;
- полные SDXL/Pony/weak-model benchmark matrices и repeat-run statistics;
- parity всех PromptTask через direct, OpenCode, Claude Code и Antigravity;
- global/per-run auto AI rating и расширенная проверка provider content policies;
- desktop installers, signing, auto-update и bundled runtime.

## Правило остановки scope creep

Новый обязательный пункт добавляется в release gates только тогда, когда найден конкретный дефект, который мешает:

- установить или запустить приложение;
- сохранить пользовательские данные;
- открыть и организовать media;
- выполнить выбранный основной ComfyUI workflow;
- понять и исправить блокирующую ошибку.

Дополнительная совместимость, улучшение качества или редкий edge case записываются в post-v1 backlog и не задерживают релиз автоматически.
