# Detailed execution roadmap

Этот документ превращает верхнеуровневые технические задания в последовательный план интеграции и проверки продукта.

Существующие документы `00–10` остаются архитектурными заданиями и источником требований. Этот файл отвечает на другие вопросы:

- в каком порядке выполнять оставшуюся работу;
- какие задачи блокируют следующие;
- что уже реализовано только на уровне кода, но ещё не считается завершённым продуктовым сценарием;
- какие проверки обязательны перед возвратом верхнеуровневой галочки;
- какие решения не следует заново пересматривать без новых доказательств.

## Правила статусов

- `[x]` означает, что результат реализован, интегрирован и проверен по указанным критериям.
- `[ ]` означает, что отсутствует реализация, интеграция, практическая проверка или документированное подтверждение.
- Наличие класса, API route, HTML-страницы или одного успешного запуска само по себе не закрывает задачу.
- Верхнеуровневая задача в `README.md` закрывается только после выполнения всех обязательных дочерних пунктов этого плана и критериев исходного технического задания.
- Проверка должна включать не только unit-тесты, но и реальный пользовательский поток в браузере и подключённом ComfyUI там, где это применимо.

## Зафиксированные продуктовые границы

Эти решения считаются принятыми. Возвращаться к их пересмотру следует только при появлении конкретной технической причины или подтверждённого пользовательского сценария.

- [x] Meta Viewer остаётся локальным и однопользовательским приложением.
- [x] Альбомы, избранное и виртуальная организация не перемещают исходные файлы.
- [x] Meta Viewer не пытается заменить ComfyUI Manager.
- [x] Один универсальный workflow не считается корректным способом поддержки всех моделей.
- [x] Prompt scenario и workflow template считаются разными сущностями.
- [x] Prompt scenarios описывают смысл и структуру prompt, а templates описывают технический граф выполнения.
- [x] AI-операции создают редактируемый draft и не запускают генерацию автоматически.
- [x] Неизвестный model file не перемещается автоматически только на основе имени или слабой эвристики.
- [x] Эвристическое определение типа ресурса всегда имеет confidence и допускает ручное подтверждение.
- [x] Обычный редактор остаётся простым; редкие компоненты и параметры раскрываются только при необходимости.
- [x] AI rating является отдельной опциональной функцией и не блокирует основную генерацию.
- [x] Policy rejection, technical failure и художественная оценка хранятся как разные состояния.

## Критический путь

Текущий порядок разработки:

1. Стабилизировать contracts templates и model resources.
2. Покрыть основные технические способы генерации встроенными templates.
3. Завершить импорт, регистрацию и управление пользовательскими workflows.
4. Довести resource compatibility, preflight и диагностику ошибок.
5. Подключить AI operations к drafts редактора.
6. Проверить полные end-to-end сценарии.
7. Добавить опциональный AI ranking.
8. Провести release verification.
9. Только после этого начинать desktop packaging.

---

# Phase 0. Baseline audit and regression safety

Цель: зафиксировать текущее работающее состояние перед глубокой интеграцией редактора.

## 0.1 Текущий функциональный baseline

- [ ] Зафиксировать список доступных страниц и основных пользовательских потоков.
- [x] Зафиксировать текущие built-in workflow templates и их реальные manifests.
- [x] Зафиксировать текущие resource types, которые возвращает inventory ComfyUI.
- [x] Зафиксировать текущие supported node bindings.
- [x] Зафиксировать текущий формат editor draft, run и imported result.
- [ ] Зафиксировать текущий AI draft/job contract.
- [ ] Сохранить минимальные воспроизводимые test fixtures для существующих workflows.

## 0.2 Регрессионная защита

- [ ] Добавить тест загрузки Viewer с изображениями и видео без layout shifts.
- [ ] Добавить browser smoke test Library.
- [ ] Добавить browser smoke test AI settings.
- [ ] Добавить browser smoke test Create/editor.
- [x] Проверить, что reset index не затрагивает исходные файлы.
- [x] Проверить, что удаление виртуального album не затрагивает assets.
- [x] Проверить, что Remix создаёт draft и не запускает generation.

**Gate:** следующие фазы можно начинать без полного закрытия Phase 0, но перед крупным refactor должны существовать fixtures и хотя бы минимальные smoke tests затрагиваемой области.

---

# Phase 1. Foundation verification

Цель: отделить уже написанный код от реально подтверждённой кроссплатформенной и runtime-совместимости.

## 1.1 Cross-platform paths

- [ ] Проверить scan пути с пробелами на Windows.
- [ ] Проверить scan пути с кириллицей и Unicode на Windows.
- [ ] Проверить UNC или сетевой путь на Windows, если окружение доступно.
- [ ] Проверить обычный абсолютный путь на Linux.
- [ ] Проверить путь с Unicode на Linux.
- [ ] Проверить обычный абсолютный путь на macOS.
- [ ] Проверить путь с Unicode на macOS.
- [ ] Проверить folder picker и ручной fallback на каждой доступной ОС.
- [ ] Проверить reveal/open original на каждой доступной ОС.

## 1.2 Source monitoring

- [ ] Проверить create event.
- [ ] Проверить modify event.
- [ ] Проверить rename event с сохранением identity и virtual relations.
- [ ] Проверить delete event.
- [ ] Проверить recursive source.
- [ ] Проверить массовое копирование файлов с debounce.
- [ ] Проверить временно недоступный диск без удаления записей.
- [ ] Проверить disable и повторный enable источника.
- [ ] Проверить reconcile после reconnect.
- [ ] Проверить desktop-synced cloud folder хотя бы с одним реальным клиентом.

## 1.3 Unified image/video behavior

- [ ] Проверить image indexing без установленного FFmpeg.
- [ ] Проверить video indexing с FFmpeg.
- [ ] Проверить video indexing без FFmpeg.
- [ ] Проверить poster generation failure без падения общего worker.
- [ ] Проверить album, favorite, rating, tag и note для video asset.
- [ ] Проверить открытие original video с range support.
- [ ] Проверить удаление video из index отдельно от physical Trash.

**Gate:** задачи 00, 02 и 04 возвращают верхнеуровневые галочки только после подтверждения соответствующих подпунктов.

---

# Phase 2. Workflow template contract

Цель: перейти от универсального workflow к небольшому набору технически различающихся templates.

## 2.1 Resource taxonomy

- [x] Зафиксировать канонические типы `checkpoint`.
- [x] Зафиксировать канонические типы `diffusion_model` / `unet`.
- [x] Зафиксировать канонические типы `diffusion_model_gguf`.
- [x] Зафиксировать канонические типы `clip` / `text_encoder`.
- [x] Зафиксировать канонические типы `clip_gguf`, если поддерживается установленными nodes.
- [x] Зафиксировать канонические типы `vae`.
- [x] Зафиксировать канонические типы `lora`, `locon`, `dora`.
- [x] Зафиксировать типы reference/control resources.
- [x] Зафиксировать video-specific model resources.
- [x] Обеспечить compatibility aliases для существующей схемы.

## 2.2 Manifest schema

Каждый template должен декларировать технические возможности, а не закрытый список имён моделей.

- [x] Добавить manifest version.
- [x] Добавить template category.
- [x] Добавить result media type.
- [x] Добавить supported model ecosystem или список ecosystems.
- [x] Добавить required node types.
- [x] Добавить semantic resource slots.
- [x] Добавить accepted resource types для каждого slot.
- [x] Добавить loader family или binding strategy.
- [x] Добавить optional/required state для CLIP и VAE.
- [x] Добавить editable fields.
- [x] Добавить advanced fields.
- [x] Добавить field-to-node/input bindings.
- [x] Добавить output nodes.
- [x] Добавить capability and limitation notes.
- [x] Добавить template validation schema.
- [x] Добавить миграцию manifests предыдущей версии.

## 2.3 Built-in templates: minimum supported set

### Basic text-to-image

- [x] Checkpoint-contained image generation для SDXL/Pony-like моделей.
- [x] Separate diffusion model + CLIP + VAE для Flux-like архитектур.
- [x] GGUF diffusion model template.
- [x] GGUF text encoder support там, где доступен проверенный loader.

### Image-conditioned generation

- [ ] Basic img2img/reference template.
- [ ] Inpainting template.
- [ ] ControlNet или pose-conditioning template.

### Derived and multi-stage generation

- [ ] Upscale template.
- [ ] Refiner или explicit two-stage template.
- [ ] Один проверенный video template.

## 2.4 Template behavior

- [ ] Primary UI показывает только обязательные поля.
- [ ] `More settings` показывает применимые advanced fields.
- [ ] CFG отображается только там, где он имеет реальный binding.
- [ ] CLIP skip отображается только для совместимых workflows.
- [ ] VAE скрыт при embedded/default behavior.
- [ ] CLIP скрыт при embedded/default behavior.
- [ ] Separate VAE/CLIP появляются при требовании template или обнаруженной ошибке.
- [ ] Смена template очищает или повторно валидирует неприменимые values.
- [ ] Смена model resource не удаляет пользовательский prompt.

**Gate:** нельзя подключать автоматический AI workflow selection, пока manifests не описывают resource slots и ограничения детерминированно.

---

# Phase 3. Workflow import and registry

Цель: пользовательский workflow становится зарегистрированным template с понятным состоянием, а не одноразовым JSON.

## 3.1 Import pipeline

- [x] Импорт API workflow JSON.
- [x] Импорт UI workflow JSON, если возможно преобразование или извлечение API graph.
- [ ] Импорт ZIP bundle с manifest и workflow.
- [x] Определение standard loader nodes.
- [x] Определение prompt encoder nodes.
- [x] Определение sampler/scheduler nodes.
- [x] Определение width/height/seed/steps/CFG bindings.
- [x] Определение reference inputs.
- [x] Определение output nodes.
- [ ] Обнаружение нескольких независимых pipelines.
- [x] Обнаружение неизвестных custom loaders.

Обычный API graph теперь анализируется до записи, получает schema-v2 manifest с сохранёнными field/resource bindings и регистрируется как user template. Современный UI workflow JSON детерминированно преобразуется из `nodes`, `links` и widget metadata; для старых positional-only файлов используются node contracts подключённого ComfyUI из `/object_info`, а без достаточной схемы импорт останавливается с явной диагностикой. Bypass и reroute links разрешаются до исходного executable node. Несколько sampler/output candidates и неизвестные loader inputs раскрываются в mapping wizard.

## 3.2 Mapping wizard

- [x] Показ автоматически найденных semantic mappings.
- [x] Показ confidence для неоднозначных mappings.
- [x] Ручной выбор роли для неизвестного model loader.
- [x] Ручной выбор positive prompt binding.
- [x] Ручной выбор negative prompt binding.
- [x] Ручной выбор primary output.
- [x] Возможность скрыть node input из обычного editor UI.
- [x] Возможность пометить field как advanced.
- [x] Preview итогового manifest до регистрации.
- [x] Проверка manifest до сохранения.

## 3.3 Registry statuses

- [x] `ready`.
- [x] `warning`.
- [x] `invalid`.
- [x] `expert` / `partially_mapped`.
- [x] Причина текущего статуса.
- [x] Дата последней проверки.
- [x] Версия ComfyUI или inventory fingerprint последней проверки.

## 3.4 Workflow management modal

Добавить отдельную модалку или страницу с таблицей зарегистрированных workflows.

- [x] Колонка name.
- [x] Колонка category.
- [x] Колонка family/ecosystem.
- [x] Колонка structure/loader strategy.
- [x] Колонка source: built-in/imported.
- [x] Колонка validation status.
- [x] Колонка last validation.
- [x] Колонка manifest version.
- [x] Поиск и фильтрация.
- [x] Открытие workflow в editor.
- [x] Переименование и изменение description.
- [x] Повторное открытие mapping wizard.
- [x] Revalidate against current ComfyUI.
- [x] Duplicate.
- [x] Export.
- [x] Delete imported template.
- [x] Restore built-in template не требуется: built-in templates read-only, не удаляются и не могут быть перекрыты user template с тем же ID.
- [x] Удаление template не затрагивает models, nodes и ComfyUI files.

Для imported workflows mapping wizard повторно открывается из management table с восстановленными sampler/prompt/output selections, manual model roles и field visibility. Preview не изменяет сохранённый manifest; apply атомарно заменяет semantic contract, повышает patch-version и сбрасывает runtime validation до явного revalidate. Любой валидный built-in или imported workflow можно дублировать в независимый user template с уникальным ID и экспортировать в переносимый ZIP bundle, который проходит обычный import round-trip.

**Gate:** Task 09 не закрывается без удобного управления импортированными templates и повторной проверки после изменений ComfyUI.

---

# Phase 4. Model resource compatibility and onboarding

Цель: не обещать запуск любого файла, но предотвращать заведомо неправильные комбинации.

## 4.1 Resource inventory

- [ ] Получать фактические resource options из connected ComfyUI.
- [ ] Иметь filesystem fallback для offline inventory.
- [ ] Хранить source path только там, где это безопасно и нужно.
- [ ] Хранить stable identity или content hash, если вычисление практически допустимо.
- [ ] Хранить resource type.
- [ ] Хранить architecture/ecosystem.
- [ ] Хранить prompt family отдельно от binary compatibility.
- [ ] Хранить доступность.
- [ ] Хранить обнаруженные metadata и trigger words.
- [ ] Хранить confidence происхождения metadata.

## 4.2 Compatibility resolver

- [x] Фильтровать resource list по active template slot.
- [x] Не показывать несовместимые resources как обычный selectable option.
- [ ] Иметь отдельный раздел incompatible/unknown с объяснением.
- [ ] Различать embedded и external CLIP.
- [ ] Различать embedded и external VAE.
- [x] Различать checkpoint loader и diffusion-model loader.
- [x] Различать standard safetensors и GGUF loader requirements.
- [x] Повторно валидировать LoRA при смене checkpoint.
- [x] Не удалять несовместимый пользовательский выбор молча.
- [x] Блокировать запуск только при доказанной incompatibility или unresolved required slot.
- [x] Разрешать запуск с предупреждением для состояния `experimental`.

## 4.3 Optional model registration wizard

Эта функция не должна автоматически перемещать неизвестные файлы без подтверждения.

- [ ] Выбор model file через UI.
- [ ] Чтение extension и доступных metadata.
- [ ] Анализ safetensors tensor keys там, где применимо.
- [ ] Распознавание GGUF container.
- [ ] Filename используется только как слабая эвристика.
- [ ] Показ предполагаемого resource type.
- [ ] Показ confidence.
- [ ] Ручное подтверждение или изменение type.
- [ ] Показ рекомендуемой директории ComfyUI.
- [ ] Опция copy с явным размером файла и подтверждением.
- [ ] Опция link только при поддерживаемом и понятном platform behavior.
- [ ] Опция показать директорию без копирования.
- [ ] Не использовать silent move.
- [ ] После действия обновить inventory через ComfyUI.
- [ ] Подтвердить, что ресурс действительно появился в нужном slot.

**Gate:** автоматический onboarding не является обязательным для первой стабильной версии. Обязательны slot filtering, preflight и понятная диагностика.

---

# Phase 5. Preflight and error diagnostics

Цель: превращать ошибки ComfyUI в понятные действия, не превращая основной editor в копию node graph.

## 5.1 Preflight before queue

- [x] Проверить runtime online.
- [x] Проверить required node types.
- [x] Проверить required model resources.
- [x] Проверить unresolved semantic slots.
- [x] Проверить basic architecture/ecosystem compatibility.
- [ ] Проверить required input files.
- [x] Проверить ranges известных editable parameters.
- [x] Разделить missing nodes, missing resources и compatibility issues.
- [x] Повторять preflight непосредственно перед каждым run.

## 5.2 Runtime error normalization

- [x] Сохранять raw ComfyUI error.
- [x] Извлекать node ID.
- [x] Извлекать class type.
- [x] Извлекать input name.
- [x] Извлекать expected/received type, если доступно.
- [x] Отличать missing file от incompatible tensor/model type.
- [x] Отличать invalid parameter от execution failure.
- [x] Отличать out-of-memory от workflow incompatibility.
- [x] Отличать cancellation от failure.

## 5.3 Editor guidance

- [x] Связать node/input с manifest field.
- [x] Автоматически открыть `More settings`, если проблема находится там.
- [x] Подсветить проблемное поле.
- [x] Прокрутить к проблемному полю.
- [x] Показать краткое пользовательское объяснение.
- [x] Показать рекомендуемое действие без автоматического изменения workflow.
- [x] Оставить raw technical details в раскрываемом блоке.
- [x] Не занижать художественный rating из-за technical error.

**Gate:** расширять основной editor всеми возможными node parameters запрещено. Новое поле добавляется только при наличии manifest binding и подтверждённого пользовательского сценария.

---

# Phase 6. AI layer integration with editor

Цель: замкнуть AI operations в редактируемый и воспроизводимый draft, не связывая prompt knowledge с техническими adapters.

## 6.1 Shared editor draft contract

- [x] Editor draft может ссылаться на PromptTask.
- [x] Editor draft хранит positive prompt.
- [x] Editor draft хранит negative prompt отдельно.
- [x] Editor draft хранит source text или SceneSpec.
- [x] Editor draft хранит family.
- [x] Editor draft хранит scenario.
- [x] Editor draft хранит modifiers.
- [x] Editor draft хранит execution backend metadata.
- [x] Editor draft хранит versions profiles/manifests/contracts.
- [x] Editor draft хранит выбранный workflow template отдельно от prompt scenario.
- [x] Draft переживает reload и restart.
- [x] Manual edits создают новую revision или явно сохраняются без потери исходного AI result.

## 6.2 Generate prompt

- [x] Пользователь вводит исходное описание.
- [x] Выбирает family или получает совместимое предложение от выбранного workflow.
- [x] Выбирает scenario из capability resolver.
- [x] Получает PromptResult.
- [x] Результат открывается в editor draft.
- [x] Generation не запускается автоматически.

При переносе PromptResult в workflow draft непустой AI negative prompt заменяет
значение поля шаблона. Если AI корректно вернул пустую строку, editor сохраняет
уже заданный пользователем negative prompt или default совместимого template;
для workflows без negative input поле не создаётся. Реальный запуск `core-image`
26 июля 2026 года подтвердил, что negative prompt попал в отдельный
`CLIPTextEncode`, использовался как negative conditioning KSampler и сохранился
в metadata импортированного результата.

## 6.3 Translate

- [x] Translation является отдельной операцией.
- [x] Source и translated prompt сохраняются раздельно.
- [x] Translation не выполняет family adaptation без явного запроса.
- [x] Пользователь видит результат до запуска workflow.

## 6.4 Adapt

- [x] Adapt является отдельной операцией.
- [x] Target family выбирается явно или определяется compatible template.
- [x] Checkpoint-specific triggers не удаляются без причины.
- [x] Adapted result создаёт новую draft revision.

Adapt вызывается из editor отдельным действием, использует сохранённый text profile, явно выбранные family/scenario и optional checkpoint profile. Source и adapted result хранятся в отдельном persistence contract, восстанавливаются при reload и открываются в сравнении; созданный workflow draft остаётся редактируемым и не запускает ComfyUI. Выбранный catalogued checkpoint передаётся по content identity: только его trusted triggers, уже присутствующие в source positive prompt, защищаются instruction contract и детерминированным normalized-result guard, а отсутствующие triggers не добавляются.

**Runtime evidence (2026-07-27):** реальный сохранённый OpenCode text profile выполнил Flux Adapt job `13` с checkpoint profile `runtime-trigger-preservation-v1`. Source содержал trusted trigger `cmvTrigger77`, а второй catalog trigger `absentTrigger88` отсутствовал. Persisted adaptation schema v2 сохранила `protected_triggers=["cmvTrigger77"]`; итоговый prompt сохранил `cmvTrigger77` и не получил `absentTrigger88`.

## 6.5 Reconstruct from image

- [x] Vision stage создаёт SceneSpec.
- [x] SceneSpec хранится в SQLite.
- [x] SceneSpec можно просмотреть.
- [x] SceneSpec можно исправить вручную.
- [x] PromptResult рендерится из сохранённого SceneSpec.
- [x] Повторный render не требует нового vision call.
- [x] Embedded metadata и AI reconstruction визуально различаются.

Reconstruct разделён на два явных этапа: OpenAI-compatible или OpenCode multimodal profile анализирует Library asset в strict `SceneSpec`, после чего JSON можно исправить и сохранить; отдельный text profile рендерит сохранённый SceneSpec в prompt draft. Editor восстанавливает SceneSpec после reload, сохраняет source asset и не запускает ComfyUI. Повторный render использует `scene_spec_job_id`, поэтому изображение не отправляется vision provider повторно.

**Runtime evidence (2026-07-26):** bundled `cmv-vision-test-garden.jpg` проанализирован реальным сохранённым OpenCode multimodal profile `opencode/mimo-v2.5-free`. Vision job `3` за 46.25 s создал strict `landscape_environment` SceneSpec с subjects, composition и explicit uncertain details. Сохранённый SceneSpec затем без image attachment отрендерен тем же OpenCode host в нормализованный PromptResult как отдельный job `4` за 35.19 s. Оба ответа прошли строгие contracts без JSON repair или Markdown normalization.

## 6.6 Remix

- [x] Пользователь выбирает source prompt: embedded, reconstructed, translated, adapted или manual.
- [x] Пользователь выбирает compatible workflow template.
- [x] Reference input подготавливается, если template его требует.
- [x] Source lineage сохраняется.
- [x] Открывается editor draft.
- [x] Run остаётся ручным действием.

Viewer Remix открывает отдельный review dialog и получает доступные источники из
embedded metadata, AI annotations, persisted Generate/Translate/Adapt drafts,
rendered SceneSpec и prompt, фактически использованного editor workflow. Выбранный
AI draft проверяется на принадлежность source asset. Manual edit хранит исходный
source type и draft ID в provenance. Список workflow ограничен media-compatible
templates; обязательные image fields заполняются одним upload reference, а offline
runtime оставляет их pending. Созданный workflow draft хранит `source_asset_id`,
поэтому импортированный output автоматически получает `derived_from_asset_id`.

**Runtime evidence (2026-07-26):** asset `6265` и persisted Translation draft `7`
выбраны через новый options contract для `core-reference`. Offline attempt создал
редактируемый draft `35` с явным pending reference и без workflow run. После
временного запуска Windows Portable ComfyUI online draft `36` загрузил reference
как `cmv/remix/Create_00008_.png`; preflight подтвердил ready graph и отдельный
negative conditioning. Только отдельное ручное действие Run создало run `23`,
который завершился за 39 s и импортировал asset `6338`. Результат сохранил
`template_id=core-reference`, negative prompt и lineage
`derived_from_asset_id=6265`. Временный runtime после проверки остановлен.

## 6.7 Execution backends

- [ ] Один PromptTask проверен через direct OpenAI-compatible profile.
- [ ] Тот же контракт проверен через OpenCode.
- [ ] Claude Code adapter проверен как реальная prompt operation, а не только connection test.
- [ ] Antigravity явно остаётся experimental до стабильного structured output.
- [ ] Codex exporter не дублирует prompt knowledge.
- [ ] Cancellation и timeout работают для direct и хотя бы одного agent host.
- [ ] Нормализованный результат не зависит от выбранного transport.

**Gate:** AI rating нельзя считать приоритетом, пока Generate, Translate, Adapt, Reconstruct и Remix не замкнуты на editor drafts и manual run.

---

# Phase 7. Prompt research and quality verification

Цель: подтвердить, что compiler и manifests действительно полезны целевым моделям, а не только структурно корректны.

## 7.1 Existing family coverage

- [x] Flux-like family profile существует.
- [x] SDXL family profile существует.
- [x] Pony family profile существует.
- [x] Базовые scenario manifests зарегистрированы.

## 7.2 Missing operation benchmarks

- [ ] Reconstruct benchmark.
- [ ] Adapt benchmark.
- [ ] Translate benchmark.
- [ ] Image-conditioned multimodal benchmark.
- [ ] SceneSpec correction and rerender benchmark.

## 7.3 Family-specific practical checks

- [x] Запустить выбранные Flux checks на реальной целевой модели.
- [ ] Запустить независимые SDXL checks.
- [ ] Запустить независимые Pony checks.
- [ ] Проверить weak/local model target.
- [ ] Зафиксировать unsupported и limited combinations.
- [ ] Добавить checkpoint capability profiles только после практической проверки.
- [ ] Добавить regression cases для подтверждённых checkpoint-specific rules.
- [ ] Добавить repeat-run statistics там, где нестабильность влияет на UX.

## 7.4 Multi-character boundary

- [x] `multi_character` не обещается базовым бюджетным набором.
- [ ] Добавлять multi-character capability только для конкретного проверенного checkpoint profile.
- [ ] Не выводить experimental capability как обычную поддерживаемую опцию.

---

# Phase 8. Optional AI rating

Цель: добавить экспериментальную оценку результатов без влияния provider policy на основной пользовательский сценарий.

## 8.1 Product behavior

- [x] AI rating выключен по умолчанию.
- [x] AI rating можно включить глобально.
- [x] AI rating можно включить для отдельного run.
- [x] AI rating можно запустить вручную для выбранного asset.
- [x] Отсутствие AI profile не мешает generation.
- [x] Отказ provider не мешает сохранению результата.

## 8.2 Status separation

- [x] `rated`.
- [x] `not_rated`.
- [x] `ai_rejected`.
- [x] `unreadable`.
- [x] `generation_error`.
- [x] Policy rejection не преобразуется в низкий rank.
- [x] Technical error не преобразуется в низкий rank.
- [x] Manual user stars и AI rank остаются разными полями.

## 8.3 Rating UI

- [ ] Показ technical quality.
- [ ] Показ composition.
- [ ] Показ prompt adherence.
- [ ] Показ defects.
- [ ] Показ explanation.
- [ ] Показ provider/model/version metadata.
- [ ] Возможность вручную изменить AI rank.
- [ ] Возможность удалить AI rating.
- [ ] Отдельный filter по AI rank.
- [ ] Отдельный filter по AI rating status.

Backend и Library DOM для всех перечисленных controls реализованы. Интерактивный
browser smoke диалога остаётся pending: доступный headless Chrome подтвердил
загрузку страницы, layout и наличие rank/status filters и rating dialog, но
окружение не содержит `agent-browser`/Playwright для надёжного click-flow.

## 8.4 Content-policy robustness

- [ ] Проверить обычный SFW asset.
- [ ] Проверить policy rejection.
- [ ] Проверить локальный профиль с отличающейся content policy.
- [ ] Не рекомендовать обход ограничений provider.
- [ ] Честно объяснять, что refusal относится к выбранному provider, а не к визуальному качеству asset.

---

# Phase 9. End-to-end release verification

Цель: проверить продуктовые потоки перед упаковкой desktop-версии.

## 9.1 Supported operating systems

- [ ] Windows verification.
- [ ] Linux verification.
- [ ] macOS verification.
- [ ] Составить таблицу непроверенных функций для недоступных окружений.

## 9.2 ComfyUI installations

- [ ] Windows Portable root selected.
- [ ] Nested `ComfyUI` directory selected.
- [ ] Windows venv installation.
- [ ] Linux venv installation.
- [ ] macOS venv installation.
- [ ] External running ComfyUI.
- [ ] Managed start/stop/restart.
- [ ] Interrupt generation отдельно от stop process.
- [ ] Port conflict.
- [ ] Missing Python.
- [ ] Missing custom node.
- [ ] Missing model resource.
- [ ] ComfyUI crash during run.

## 9.3 Workflow matrix

- [ ] Checkpoint-contained image generation.
- [ ] Separate-components image generation.
- [x] GGUF generation.
- [ ] Reference/img2img.
- [ ] Inpaint.
- [ ] Control/pose.
- [ ] Upscale/refiner.
- [ ] Video.
- [ ] Imported standard workflow.
- [ ] Imported partially mapped workflow.
- [x] Result imported into Library.
- [ ] Remix lineage preserved.

**GGUF evidence (2026-07-26):** Pony/SDXL GGUF проверен через `core-pony-gguf`: runtime inventory и preflight готовы, quality run выполнен в 832×1216 на 28 steps, полноразмерный output визуально проверен и импортирован в Library с provenance и корректной GGUF model identity. Ранний 512×512 run считается только техническим smoke. Flux-family GGUF отдельно подтверждён через `core-flux-gguf` на Krea-based `unstableEvolution_GGUFQ417GB.gguf`: run `9` выполнен в 832×1216 на целевых 8 steps, output визуально проверен и импортирован как Library asset `6261` с полным provenance. Z-Image остаётся дополнительной architecture-specific проверкой после загрузки её component set, а не blocker для уже подтверждённого Flux GGUF path.

## 9.4 Browser and UX checks

- [ ] Viewer reload without visible layout jumps.
- [ ] Library reload and selection behavior.
- [ ] AI settings reload and profile actions.
- [ ] Editor responsive layout.
- [ ] No overlapping controls at supported widths.
- [ ] Dropdowns and modals remain inside viewport.
- [ ] Keyboard navigation for critical actions.
- [ ] Error fields are highlighted correctly.
- [ ] Dark/light theme regression, если обе темы поддерживаются.
- [ ] ESLint or equivalent JS checks.
- [ ] Python tests.
- [ ] Browser smoke tests.

**Gate:** desktop packaging не начинается до закрытия обязательной release matrix или явного документирования отложенных ограничений.

---

# Phase 10. Desktop packaging

Цель: упаковать уже стабилизированный продукт, а не использовать desktop shell для маскировки незавершённой интеграции.

## 10.1 Technology decision

- [ ] Исследовать актуальные desktop wrappers для Python/web app.
- [ ] Сравнить размер, startup, process control и packaging complexity.
- [ ] Проверить system folder picker.
- [ ] Проверить system keyring.
- [ ] Проверить child-process management.
- [ ] Зафиксировать выбранный stack и причины.

## 10.2 Runtime packaging

- [ ] Backend запускается автоматически.
- [ ] UI открывается в собственном окне.
- [ ] Poetry не требуется пользователю.
- [ ] Системные app-data paths используются для DB/config/cache.
- [ ] User data переживает update.
- [ ] Managed ComfyUI корректно завершается вместе с app.
- [ ] Crash recovery не удаляет пользовательские данные.

## 10.3 Installers

- [ ] Windows installer.
- [ ] Linux package или portable format.
- [ ] macOS app bundle.
- [ ] Проверка clean install.
- [ ] Проверка update поверх предыдущей версии.
- [ ] Проверка uninstall без неожиданного удаления user data.

---

# Current execution slice

Следующий рабочий срез должен быть ограничен задачами ниже. Не следует одновременно начинать AI rating, desktop packaging и расширенный model importer.

## Slice A. Template and compatibility foundation

- [x] Инвентаризировать текущие built-in templates.
- [x] Утвердить resource taxonomy.
- [x] Обновить manifest schema.
- [x] Разделить checkpoint-contained и separate-components templates.
- [x] Добавить GGUF-aware template contract.
- [x] Фильтровать model resources по active slot.
- [x] Показывать incompatibility reason до запуска.

## Slice B. Workflow registry

- [x] Сохранить imported workflow как registered template.
- [x] Добавить mapping wizard для неоднозначных bindings.
- [x] Добавить workflow management modal/table.
- [x] Добавить revalidation against current ComfyUI.

## Slice C. AI draft integration

Начинается только после стабильного Slice A.

- [x] Подключить Generate prompt к editor draft.
- [x] Подключить Translate как отдельную операцию.
- [x] Подключить Adapt как отдельную операцию.
- [x] Подключить Reconstruct через editable SceneSpec.
- [x] Проверить Remix end-to-end.

## Slice D. Optional AI rating foundation

Начат после завершения основной AI-to-editor интеграции.

- [x] Хранить technical status без фиктивного художественного rank.
- [x] Выбирать только сохранённый multimodal profile и разрешать credentials server-side.
- [x] Добавить ручной запуск, rank override и удаление rating для Library asset.
- [x] Добавить отдельные Library filters по AI rank и evaluation status.
- [ ] Проверить интерактивный flow rating dialog в полноценном browser automation окружении.
- [x] Добавить global opt-in и per-run opt-in после определения run lifecycle hook.
- [x] Проверить SFW, policy rejection и отличающуюся local policy на реальных profiles.

## Явно отложено

- [ ] Полностью автоматическое определение и перемещение любой скачанной модели.
- [ ] Универсальный workflow для всех architectures.
- [ ] Полная замена ComfyUI Manager.
- [ ] Автоматический подбор VAE/CLIP без проверяемого manifest или metadata source.
- [x] AI rating не начинался до завершения основной AI-to-editor интеграции.
- [ ] Desktop packaging до release verification.
