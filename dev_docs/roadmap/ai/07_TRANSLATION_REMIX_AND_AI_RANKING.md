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
- Remix всегда открывает редактируемый черновик и не запускается сам.
- Производные assets связаны с оригиналом.
- AI-рейтинг можно отключить, изменить вручную и использовать в фильтрах.
- Ошибка генерации, отказ AI и художественный ранг хранятся раздельно.
- OpenCode, Claude Code, Antigravity и будущий Codex подключаются без дублирования канонического prompt knowledge.
