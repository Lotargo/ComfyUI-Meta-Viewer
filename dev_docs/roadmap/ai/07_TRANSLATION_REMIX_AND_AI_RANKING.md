# 07. Translation, remix and AI ranking

## Цель

Добавить прикладные AI-инструменты поверх библиотеки: перевод prompt до отправки в ComfyUI, реконструкцию prompt по изображению, remix через выбранный workflow и экспериментальную оценку результатов.

Операции используют contracts и execution architecture из [06A. Prompt profile and agent execution architecture](06A_PROMPT_PROFILE_AND_AGENT_EXECUTION_ARCHITECTURE.md). UI не должен напрямую читать монолитный skill, собирать CLI-команду или зависеть от конкретного provider.

## Общий PromptTask

Каждая прикладная операция создаёт нормализованную задачу, включающую:

- asset или пользовательский текст;
- operation;
- model family;
- checkpoint profile, если известен;
- scenario;
- modifiers;
- execution backend;
- provider profile или agent host;
- ожидаемый output contract.

Prompt compiler формирует `InstructionBundle`, а ExecutionRouter передаёт задачу direct adapter или agent-host adapter.

## Выбор execution backend

Пользователь может выполнять AI-операцию через:

### Direct model

- OpenAI-compatible профиль;
- LM Studio preset;
- контролируемый приложением text или vision запрос.

### Agent host

- OpenCode;
- Claude Code;
- Antigravity;
- будущий Codex adapter.

Agent host использует штатную авторизацию, skills, tools и собственный agent loop. Приложение не должно заставлять его имитировать direct-provider pipeline. При этом любой backend возвращает одинаковый нормализованный `PromptResult` или другой operation-specific contract.

## Перевод prompt

Перевод выполняется внутри ComfyUI Meta Viewer до формирования и отправки workflow. Ноды автоматического перевода в граф ComfyUI не добавляются.

Пользователь должен иметь возможность:

- писать prompt на удобном языке;
- включить перевод перед запуском;
- выбрать целевой язык;
- использовать быстрый перевод или настроенный AI execution backend;
- отдельно запросить адаптацию под Flux-like, SDXL или Pony;
- увидеть исходный и итоговый текст до запуска.

Следует сохранять обе версии prompt.

AI-перевод и AI-адаптация являются отдельными операциями:

- `translate` сохраняет смысл и не перестраивает prompt без необходимости;
- `adapt` преобразует структуру под выбранный family/checkpoint profile.

Google Web Translate допускается как экспериментальный быстрый вариант без гарантии стабильности, но не заменяет family-aware adaptation.

## Реконструкция prompt

Для assets без metadata нужна команда `Создать prompt`.

Перед запуском пользователь выбирает или подтверждает:

- Flux-like;
- SDXL;
- Pony;
- поддерживаемый scenario;
- нужен ли negative prompt или режим `auto`;
- direct model или agent host.

Неподдерживаемые scenarios не показываются как обычный выбор. Ограниченные и экспериментальные сопровождаются предупреждением.

`multi_character` не входит в базовый бюджетный набор. Он может появиться только у checkpoint profile с подтверждённым capability-status.

### SceneSpec

При vision-реконструкции предпочтителен промежуточный `SceneSpec`:

1. Vision stage извлекает наблюдаемые субъекты, композицию, свет, окружение, видимый текст и uncertain details.
2. Пользователь при необходимости исправляет анализ.
3. Render stage преобразует `SceneSpec` через выбранные family, operation и scenario manifests.
4. Приложение валидирует `PromptResult` и сохраняет черновик.

Direct provider может выполнить стадии двумя запросами. Agent host может выполнить их внутри собственного agent loop. Число внутренних вызовов не является частью UI-контракта.

AI-реконструкция сохраняется как AI-аннотация, а не как исходные metadata файла.

## Prompt drafts

Каждая генерация или адаптация создаёт редактируемый черновик, содержащий:

- positive prompt;
- negative prompt;
- исходный пользовательский текст или `SceneSpec`;
- family, checkpoint profile и scenario;
- provider/agent host и Model ID;
- версии profiles, manifests и output schema;
- дату создания;
- technical status.

Черновик хранится в SQLite и переживает перезапуск приложения. Контекстное окно модели не используется как единственный источник состояния.

## Вход в редактор и ориентир интерфейса

Прикладные AI-операции должны приводить пользователя к лёгкому редактируемому draft, который позднее открывается на отдельной странице редактора из задания 09. На этапе 07 закладываются контракт черновика, выбор источника prompt, review lifecycle и точки входа `Создать prompt`, `Adapt` и `Remix`; полный workflow editor и запуск ComfyUI остаются ответственностью заданий 08–09.

В качестве визуального ориентира можно использовать [экспериментальный референс](../../image.png). Двухпанельная компоновка с основными controls слева и результатами справа выглядит практичным исходным направлением, но изображение не является утверждённым макетом или обязательной спецификацией. Финальную структуру редактора нужно выбрать во время реализации с учётом реальных workflow capabilities, разных media types, небольших экранов, accessibility, состояний jobs, ошибок, SceneSpec, AI-рейтинга и ограничений подключённого ComfyUI.

Интерфейс не должен быть перегружен. В основном режиме показываются только параметры, необходимые для выбранной операции и workflow: prompt, выбранные model resources, размеры и кнопка ручного запуска. Редкие настройки, технические metadata, раздельные LoRA strengths, сырой workflow и диагностические поля раскрываются через progressive disclosure. Смена family, backend или workflow не должна оставлять на экране неприменимые controls.

AI-команды над prompt должны оставаться различимыми действиями. Перевод, family adaptation и vision reconstruction нельзя скрывать за одной неоднозначной кнопкой улучшения без возможности увидеть, какая операция будет выполнена и какой результат попадёт в draft.

## Динамические checkpoint и LoRA

Checkpoint, LoRA и другие model resources не следует перечислять в коде формы или жёстко закреплять поимённо за каждым workflow. Подход SeaArt и Civitai используется только как архитектурный пример: отдельный каталог версионированных ресурсов, metadata моделей, фильтрация по model ecosystem и динамический список дополнительных ресурсов. Финальная реализация CMV должна учитывать локальный ComfyUI, доступные стандартные и custom nodes, metadata safetensors и фактическую структуру импортируемых workflows.

Локальный каталог ресурсов должен по возможности хранить:

- стабильную identity, предпочтительно content hash, а при наличии также внешний Model ID/version или Civitai AIR;
- локальный путь и фактическую доступность;
- тип ресурса: checkpoint, LoRA, LoCon, DoRA, VAE, embedding или другой поддержанный тип;
- architecture/model ecosystem и более общий prompt family;
- display name, version, preview и источник metadata;
- trigger words;
- default, minimum и maximum strength;
- technical compatibility status и причину ограничения.

Metadata извлекаются локально из структуры ComfyUI, заголовков safetensors и уже известных generation metadata. Необязательное обогащение через Civitai API по hash допускается как отдельная функция, но локальный редактор не должен зависеть от доступности внешнего сервиса.

Выбранный checkpoint задаёт целевую model ecosystem. Capability resolver фильтрует дополнительные ресурсы по типу и совместимости:

- совпадающая ecosystem считается обычным поддержанным случаем;
- отдельно проверенные cross-ecosystem сочетания могут иметь статус `limited` или `experimental`;
- несовместимые ресурсы скрываются из обычного выбора или явно блокируются с причиной;
- смена checkpoint повторно валидирует уже выбранные LoRA и не удаляет их молча;
- общее родство families не доказывает бинарную совместимость конкретных architectures.

Trigger words показываются как metadata/chips с явным добавлением в prompt. Приложение не должно незаметно дублировать их при каждом открытии draft. Базовый strength может управлять общим весом, а отдельные `strength_model` и `strength_clip`, если их поддерживает binding, относятся к расширенным настройкам.

Workflow template описывает поддерживаемые resource slots и способ их привязки, но не закрытый список конкретных checkpoint и LoRA. Подробный контракт slots, generic graph binding и исключения для неоднозначных workflows определяются в задании 09.

Полезные ориентиры, которые необходимо перепроверить перед реализацией, поскольку внешние продукты меняются:

- [SeaArt: Checkpoint и LoRA](https://docs.seaart.ai/guide-1/4-parameters/4-1-model);
- [SeaArt: базовый text-to-image workflow](https://docs.seaart.ai/guide-1/2-seaart-ai-basic-function/2-10-workflow/text-to-image-workflow);
- [Civitai: generation resource schema](https://github.com/civitai/civitai/blob/main/src/server/schema/generation.schema.ts);
- [Civitai: resource nodes и compatibility graph](https://github.com/civitai/civitai/blob/main/src/shared/data-graph/generation/common.ts);
- [Civitai: модель ecosystem compatibility](https://github.com/civitai/civitai/blob/main/docs/generation-support-redesign.md);
- [Civitai: AIR и ComfyUI resource loaders](https://github.com/civitai/civitai_comfy_nodes).

## Remix

Remix не запускает генерацию автоматически.

Ожидаемый сценарий:

1. Пользователь открывает asset.
2. Выбирает `Remix`.
3. Выбирает workflow template и источник prompt.
4. Приложение создаёт заполненный черновик редактора.
5. Пользователь проверяет prompt, model/checkpoint, seed, размеры и другие параметры.
6. Генерация запускается вручную.

В качестве источника можно использовать:

- оригинальные metadata;
- AI-реконструкцию;
- сохранённый `SceneSpec`;
- перевод;
- family adaptation;
- отредактированный пользователем prompt.

Новый результат связывается с исходным asset как производный вариант.

Workflow template может заранее задавать или ограничивать family/scenario. Prompt compiler должен учитывать эти требования и не собирать несовместимый profile.

## Экспериментальный AI-рейтинг

После генерации выбранная мультимодальная модель или agent host может оценить результат. Функция должна отключаться полностью.

Ранги:

`F`, `E`, `D`, `C`, `B`, `A`, `S`, `SS`, `SSS`, `SSS+`.

Технические состояния не смешиваются с художественным рейтингом:

- `generation_error`;
- `unreadable`;
- `ai_rejected`;
- `not_rated`.

Модель должна возвращать структурированную оценку, включающую хотя бы:

- техническое качество;
- композицию;
- соответствие prompt;
- найденные дефекты;
- итоговый ранг;
- краткое объяснение.

Пользователь может изменить ранг вручную.

Для сопоставимости сохраняются:

- execution backend;
- provider profile или agent host;
- Model ID;
- версия evaluation prompt/profile;
- версия output schema;
- дата оценки.

Ранги используются для фильтрации, сортировки и системных коллекций.

## Jobs и состояние UI

Прикладные операции выполняются как cancellable jobs со статусами минимум:

- `queued`;
- `running`;
- `waiting_for_review`;
- `completed`;
- `cancelled`;
- `failed`.

SQLite хранит job, промежуточный `SceneSpec`, draft, результат и technical error.

Для текущего локального однопользовательского приложения Redis не требуется. Прогресс UI можно передавать через локальный event mechanism. Redis рассматривается позднее только при появлении нескольких workers, отдельной очереди, pub/sub или другой подтверждённой необходимости.

## Ошибки и ограничения

Если AI-провайдер или agent host отклонил контент из-за своей policy, asset получает состояние `ai_rejected`, а не низкий художественный ранг.

Пользователю показывается понятное уведомление с предложением выбрать другой уже настроенный execution backend. Приложение не читает и не копирует штатные OAuth tokens CLI-инструментов.

Нужно различать:

- authentication error;
- network error;
- timeout;
- cancellation;
- content policy rejection;
- unsupported image input;
- malformed structured result;
- profile/scenario incompatibility;
- agent-host execution failure.

## Проверка интеграций

До массового переноса manifests нужно проверить один и тот же PromptTask минимум через:

- один direct OpenAI-compatible профиль;
- один agent host из уже поддерживаемых CLI;
- одинаковую нормализованную схему результата;
- cancellation и timeout;
- сохранение черновика после перезапуска;
- повторный render из сохранённого `SceneSpec` без нового vision-вызова.

Agent-host integration проверяется отдельно от простой connection test. Успешная команда `CMV_OK` не доказывает корректность skills, instruction package, structured result и cancellation.

## Критерии готовности

- Перевод выполняется до ComfyUI и не добавляет translation nodes в workflow.
- Исходный и переведённый prompt сохраняются раздельно.
- Translation и family adaptation являются разными операциями.
- Реконструкция использует compiled family/operation/scenario profile.
- `SceneSpec` можно просмотреть, исправить и повторно использовать.
- Direct model и agent host возвращают одинаковый нормализованный contract.
- Неподдерживаемые scenarios скрываются или отклоняются capability resolver.
- Базовый бюджетный набор не обещает универсальную multi-character поддержку.
- Черновики и промежуточные результаты хранятся в SQLite.
- Страница редактора использует лёгкий контекстный UI и не показывает неприменимые или редкие параметры без необходимости.
- Визуальный референс рассматривается как пример направления, а не как утверждённая финальная версия редактора.
- Checkpoint и LoRA выбираются из динамического каталога и не хардкодятся поимённо для каждого workflow.
- Совместимость model resources проверяется по ecosystem/architecture и явным capability rules.
- Remix всегда открывает редактируемый черновик и не запускается сам.
- Производные assets связаны с оригиналом.
- AI-рейтинг можно отключить, изменить вручную и использовать в фильтрах.
- Ошибка генерации, отказ AI и художественный ранг хранятся раздельно.
- OpenCode, Claude Code, Antigravity и будущий Codex подключаются без дублирования канонического prompt knowledge.
