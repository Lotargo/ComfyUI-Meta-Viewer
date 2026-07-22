# 06A. Prompt profile and agent execution architecture

## Цель

Зафиксировать архитектуру prompt-конструктора между исследованными model-family skills и прикладными AI-операциями.

Система должна поддерживать два принципиально разных способа выполнения:

- прямой вызов модели через OpenAI-compatible профиль;
- выполнение через готовую агентную среду, например OpenCode, Claude Code, Antigravity или будущую интеграцию Codex.

Prompt knowledge хранится один раз в каноническом виде. Прямые провайдеры и агентные среды получают его через разные адаптеры и не дублируют собственные копии инструкций.

## Почему текущих монолитных skills недостаточно

Текущие `flux.txt`, `sdxl.txt` и `pony.txt` являются хорошим исследовательским срезом и рабочей базой. Однако дальнейшее добавление правил для портретов, предметной съёмки, архитектуры, иллюстраций, типографики и других сценариев быстро превратит каждый файл в большой монолит.

Слишком длинная универсальная инструкция особенно плохо подходит бюджетным моделям:

- нужные правила теряются среди нерелевантных разделов;
- примеры разных сценариев начинают конкурировать;
- слабая модель смешивает синтаксис, композиционные правила и ограничения;
- растёт стоимость контекста;
- ухудшается соблюдение структурированного формата результата.

Разделение не должно превращаться в набор независимых prompt-файлов, которые вручную выбираются или копируются для каждого провайдера. Нужен детерминированный компилятор инструкции.

## Основной принцип

Итоговая инструкция собирается из независимых слоёв:

```text
Family base
+ Operation manifest
+ Scenario manifest
+ Optional modifiers
+ Output contract
```

Обычная сборка файлов не является дополнительным AI-вызовом. Prompt compiler читает выбранные канонические документы, проверяет совместимость и формирует `InstructionBundle` до обращения к модели или агентной среде.

## Граница ответственности

### Prompt domain core

Доменное ядро ничего не знает об API, CLI, OAuth, MCP и конкретной агентной среде.

Оно отвечает за:

- `PromptTask`;
- выбор model family и checkpoint profile;
- выбор операции и сценария;
- capability-проверки;
- компиляцию `InstructionBundle`;
- схемы `SceneSpec` и `PromptResult`;
- валидацию структурированного результата;
- версии profiles, manifests и output contracts.

### Execution layer

Execution layer решает, как выполнить логические стадии задачи:

- через прямой OpenAI-compatible запрос;
- через установленный CLI;
- через native skill/plugin integration агентной среды;
- одним или несколькими внутренними вызовами.

Доменное ядро не должно требовать фиксированное число LLM-вызовов.

## Канонические prompt profiles

Предлагаемая структура:

```text
app/ai/prompting/
  profiles/
    flux/
      base.md
      scenarios/
    sdxl/
      base.md
      scenarios/
    pony/
      base.md
      scenarios/

  operations/
    generate.md
    reconstruct.md
    adapt.md
    translate.md

  modifiers/
    safe.md
    adult_only.md

  schemas/
    scene_spec.json
    prompt_result.json
```

### Family base

`base.md` содержит только устойчивые правила семейства:

- основной синтаксис;
- positive и negative prompt;
- checkpoint-specific overrides;
- порядок основных признаков;
- ограничения семейства;
- общие ошибки;
- базовую самопроверку.

Family base не должен подробно учить каждому типу изображения.

### Operation manifests

Операция описывает не содержимое изображения, а тип преобразования.

#### `generate`

Создание нового prompt по пользовательскому описанию. Разрешено раскрывать недостающие визуальные детали, но нельзя менять основной замысел.

#### `reconstruct`

Реконструкция prompt по изображению или нейтральному анализу изображения. Нельзя выдавать предположения за наблюдаемые детали или добавлять отсутствующие сюжетные элементы.

#### `adapt`

Перевод существующего prompt в синтаксис другого семейства или checkpoint без потери замысла и доверенных trigger words.

#### `translate`

Перевод смысла без автоматического изменения структуры. Адаптация под семейство выполняется отдельной операцией.

### Scenario manifests

Scenario manifest раскрывает один распространённый тип генерации: анализ, композицию, характерные ошибки, хорошие и плохие примеры и дополнительную самопроверку.

Начальный реестр для бюджетного сегмента:

- `portrait`;
- `single_character`;
- `product_object`;
- `architecture_interior`;
- `landscape_environment`;
- `illustration_art`;
- `graphic_design_text`.

`multi_character` не входит в базовый реестр. Хорошая инструкция может уменьшить смешивание атрибутов, но не создаёт у небольшой модели отсутствующую способность стабильно удерживать нескольких независимых персонажей.

Поддержка нескольких персонажей позднее может появиться как экспериментальный сценарий конкретного checkpoint, например полной Z-Image или другой модели с подтверждённой практической способностью. Число параметров не используется как единственный критерий: доступность определяется capability-профилем и тестами.

## Несимметричная поддержка сценариев

Семейства не обязаны поддерживать одинаковый набор manifests.

Рекомендуемый начальный срез:

| Сценарий | Flux-like | SDXL | Pony |
|---|---|---|---|
| `portrait` | supported | supported | supported |
| `single_character` | supported | supported | supported |
| `product_object` | supported | supported | limited |
| `architecture_interior` | supported | supported | limited |
| `landscape_environment` | supported | supported | supported |
| `illustration_art` | supported | supported | supported |
| `graphic_design_text` | supported | limited | unsupported |
| `multi_character` | checkpoint-only | checkpoint-only | unsupported |

Статусы должны храниться в профиле, а не быть захардкожены в UI.

Пример:

```yaml
capabilities:
  graphic_design_text: supported
  multi_character: unsupported
  complex_spatial_relations: limited
```

Возможные статусы:

- `supported`;
- `limited`;
- `experimental`;
- `unsupported`;
- `checkpoint_only`.

UI скрывает неподдерживаемые сценарии по умолчанию и честно предупреждает об ограниченных или экспериментальных.

## Modifiers и отсутствие комбинаторного взрыва

SFW и adult-only не являются отдельными типами сцены. Они пересекаются с портретами, иллюстрациями и другими сценариями, поэтому оформляются как modifiers.

Нельзя создавать отдельные копии вроде:

```text
sfw_portrait
adult_portrait
sfw_illustration
adult_illustration
```

Такой подход быстро создаст дублирование и противоречия.

Modifier задаёт только дополнительные границы и правила, не повторяя family base и scenario manifest.

## InstructionBundle

Prompt compiler возвращает нейтральный объект, а не готовую CLI-команду или OpenAI message:

```json
{
  "family": "flux",
  "checkpoint_profile": "flux-2",
  "operation": "reconstruct",
  "scenario": "graphic_design_text",
  "modifiers": ["safe"],
  "sections": {
    "family_base": "...",
    "operation": "...",
    "scenario": "...",
    "modifiers": ["..."],
    "output_contract": "..."
  },
  "versions": {
    "family": 2,
    "operation": 1,
    "scenario": 1,
    "schema": 1
  }
}
```

### Приоритет инструкций

При конфликте действует следующий порядок:

1. output contract и жёсткие content boundaries;
2. проверенные checkpoint-specific overrides;
3. selected scenario manifest;
4. selected operation manifest;
5. family base defaults.

Более специализированный слой может уточнить общий, но не должен незаметно отменять output schema или жёсткие ограничения.

## SceneSpec как промежуточный артефакт

Для реконструкции изображения предпочтителен явный нейтральный `SceneSpec`, а не сохранение скрытого контекстного окна между вызовами.

Пример:

```json
{
  "recommended_scenario": "graphic_design_text",
  "subjects": [
    {
      "type": "perfume_bottle",
      "position": "center",
      "material": "clear glass"
    }
  ],
  "composition": {
    "shot": "close-up product shot",
    "camera_angle": "slightly low",
    "background": "warm beige gradient"
  },
  "visible_text": [
    {
      "text": "LUMIERE",
      "placement": "front label",
      "confidence": 0.96
    }
  ],
  "uncertain_details": []
}
```

Преимущества:

- анализ изображения отделён от prompt-синтаксиса;
- один анализ можно преобразовать в Flux-like, SDXL или Pony;
- ошибки восприятия отличаются от ошибок рендеринга prompt;
- промежуточный результат можно просмотреть и исправить;
- повторная адаптация не требует нового vision-вызова;
- состояние переживает перезапуск приложения.

Прямой provider может выполнить `image -> SceneSpec -> PromptResult` двумя запросами. Агентная среда может выполнить те же логические стадии внутри собственного agent loop или subagent workflow.

## Детерминированный выбор без RAG

Для начальных семи сценариев RAG не нужен.

Scenario выбирается:

- явно пользователем;
- по уже доступным признакам asset;
- первым vision-анализом как `recommended_scenario`;
- по workflow template, если сценарий однозначно известен.

Автоматический выбор остаётся изменяемым пользователем до финального запуска.

RAG может появиться позднее только для дополнительных знаний:

- десятков checkpoint-specific profiles;
- импортированных model cards;
- пользовательских manifests;
- LoRA trigger rules;
- редких специализированных сценариев.

Базовый family, operation и scenario resolver должен оставаться детерминированным.

## Execution backends

### Direct model adapter

OpenAI-compatible профиль получает собранный `InstructionBundle` как обычную system-инструкцию и пользовательский input.

Адаптер отвечает за:

- text и vision запросы;
- streaming;
- timeout и cancellation;
- дополнительные совместимые параметры;
- JSON parsing;
- retry только для технически оправданных ошибок;
- нормализацию provider errors;
- сохранение `SceneSpec`, draft и результата.

LM Studio остаётся preset того же direct adapter, а не отдельной архитектурой.

### Agent host adapter

OpenCode, Claude Code, Antigravity и Codex рассматриваются не как обычные model providers, а как agent hosts.

Они уже имеют собственные:

- управление контекстом;
- skills и project instructions;
- agent loop;
- tools и permissions;
- MCP;
- subagents или аналогичные механизмы;
- штатную авторизацию.

Meta Viewer не должен подменять их внутреннюю архитектуру большим OpenAI-подобным system prompt или навязывать собственное число вызовов.

Общий интерфейс адаптера должен быть capability-based:

```python
class AgentHostAdapter(Protocol):
    def detect(self) -> HostDetectionResult: ...
    def capabilities(self) -> AgentHostCapabilities: ...
    def prepare_task(
        self,
        task: PromptTask,
        bundle: InstructionBundle,
    ) -> PreparedAgentTask: ...
    def invoke(self, task: PreparedAgentTask) -> AgentRunHandle: ...
    def cancel(self, run_id: str) -> None: ...
    def normalize_result(self, raw_result: str) -> PromptResult: ...
```

Capability-профиль может включать:

```text
supports_skills
supports_mcp
supports_subagents
supports_images
supports_json_output
supports_streaming
supports_cancellation
supports_session_resume
```

Execution router выбирает поведение по capabilities, а не через разрастающийся набор `if provider == ...`.

## Два режима agent-host integration

### Managed CLI

Meta Viewer вызывает установленный CLI, использует его штатную авторизацию и получает результат в non-interactive режиме.

Приложение контролирует:

- входные файлы;
- timeout;
- cancellation;
- ожидаемый result contract;
- сохранение результата;
- нормализацию ошибок.

Этот режим продолжает текущий подход задания 05, но адаптер должен передавать агенту нейтральную задачу и совместимый instruction package, а не копировать direct-provider pipeline.

### Native integration

Agent host самостоятельно загружает экспортированный skill/plugin package и при необходимости взаимодействует с Meta Viewer через MCP.

В этом режиме приложение предоставляет возможности, но не управляет внутренним agent loop.

## Канонические manifests и экспортируемые packages

Нельзя хранить независимые копии prompt knowledge для каждой среды:

```text
opencode/flux.md
claude/flux.md
antigravity/flux.md
codex/flux.md
```

Канонические profiles находятся только в `app/ai/prompting/`.

Отдельные exporters создают оболочки, совместимые с конкретной средой:

```text
app/integrations/skill_export/
  common/
  opencode/
  claude/
  antigravity/
  codex/
```

Экспортированный package может содержать:

```text
SKILL.md
references/
  flux-base.md
  flux-graphic-design-text.md
  sdxl-base.md
  pony-base.md
  output-schema.md
scripts/
  validate_prompt_result.py
```

Adapters и exporters не содержат собственных prompt-правил. Они только преобразуют каноническое содержимое в родной формат host.

## Skill и MCP

Skill описывает workflow и способы принятия решений:

- как выбрать family и scenario;
- когда использовать `SceneSpec`;
- какие references читать;
- как проверять результат;
- что запрещено додумывать при реконструкции.

MCP предоставляет операции и состояние приложения:

```text
cmv.get_asset_context
cmv.get_prompt_task
cmv.list_prompt_profiles
cmv.resolve_prompt_profile
cmv.validate_prompt_result
cmv.save_prompt_draft
cmv.complete_prompt_task
```

Не следует создавать один непрозрачный MCP tool, который скрывает весь workflow внутри `generate_everything`. Skill должен сохранять понятный процесс, а MCP — давать контролируемый доступ к данным и действиям.

## Хранение состояния

SQLite остаётся постоянным источником истины для локального однопользовательского приложения.

Минимальные сущности:

```text
ai_jobs
ai_scene_specs
ai_prompt_drafts
ai_results
```

Следует сохранять:

- asset и operation;
- family, checkpoint profile и scenario;
- provider или agent host;
- Model ID;
- `SceneSpec`;
- positive и negative prompt draft;
- версии profiles и schemas;
- status, technical error и timestamps.

Текущий прогресс UI можно передавать через локальный in-memory event bus или существующий механизм backend events.

Redis не входит в первый этап. Он может стать необязательным backend очереди позднее, если появятся несколько workers, отдельный AI-процесс, pub/sub, TTL state или многоклиентная работа. Redis не должен быть обязательной зависимостью desktop-версии без реальной необходимости.

## Предлагаемая структура реализации

```text
app/
  ai/
    prompting/
      domain/
        models.py
        schemas.py
        capabilities.py
      compiler/
        registry.py
        resolver.py
        compiler.py
        validator.py
      profiles/
      operations/
      modifiers/
      schemas/

    execution/
      router.py
      direct/
        openai_compatible.py
      agent_hosts/
        base.py
        opencode.py
        claude_code.py
        antigravity.py
        codex.py

  integrations/
    skill_export/
    mcp/
```

Это направление, а не требование создать каждый файл буквально в таком виде. Реализация должна учитывать существующую структуру проекта и не делать большой механический рефакторинг без необходимости.

## Правила зависимостей

```text
profiles не знают об adapters
compiler не знает о CLI и API
agent-host adapters не содержат prompt knowledge
skill exporters не изменяют канонические manifests
UI работает через PromptTask и ExecutionRouter
SQLite хранит состояние независимо от выбранного execution backend
```

## Миграция текущих skills

Текущие `flux.txt`, `sdxl.txt` и `pony.txt` не удаляются одним большим коммитом.

Предпочтительный переход:

1. Зафиксировать neutral domain schemas и registry.
2. Перенести неизменяемые family rules в `base.md`.
3. Выделить operation manifests без изменения поведения.
4. Добавить один или два scenario manifests и проверить сборку.
5. Сохранить compatibility loader для старых `load_skill()` до перевода потребителей.
6. Подключить direct OpenAI-compatible adapter.
7. После стабильной direct path добавить agent-host exporters и adapters.
8. Удалять старый монолитный путь только после эквивалентных тестов и браузерной проверки.

## Проверка качества

Нужны отдельные уровни тестов:

### Compiler tests

- детерминированная сборка одного и того же `InstructionBundle`;
- порядок приоритетов;
- отказ при несовместимом scenario;
- сохранение version metadata;
- отсутствие дублирующихся секций.

### Contract tests

- валидный `SceneSpec`;
- валидный `PromptResult`;
- понятные ошибки схемы;
- одинаковая нормализованная структура для direct и agent-host execution.

### Adapter tests

- direct OpenAI-compatible request;
- OpenCode CLI;
- Claude Code CLI;
- Antigravity CLI;
- будущий Codex adapter;
- cancellation, timeout и malformed result.

### Practical prompt tests

Для каждого поддерживаемого family/scenario:

- проверка на бюджетной модели целевого сегмента;
- сравнение монолитного skill и compiled bundle;
- отсутствие ухудшения основного prompt-синтаксиса;
- фиксация ограничений checkpoint;
- честный статус `limited`, `experimental` или `unsupported` при нестабильном результате.

Каталог practical tests не является сравнительным leaderboard между model families. Каждая family/scenario adaptation выбирается и запускается самостоятельно. Интерактивный CLI группирует проверки по family, затем operation и scenario, скрывает `unsupported` сочетания и сохраняет точечные команды для воспроизводимых запусков. Обязательный `run-all` и автоматический выбор «лучшего» семейства не требуются.

## Не входит в первый этап

- RAG для выбора семи базовых сценариев;
- обязательный Redis;
- универсальный multi-character manifest;
- автоматическое скачивание model cards и LoRA metadata;
- отдельная ручная копия prompt knowledge для каждого agent host;
- замена внутреннего agent loop OpenCode, Claude Code, Antigravity или Codex;
- поддержка всех существующих checkpoint и провайдеров.

## Критерии готовности

- Prompt knowledge хранится в одном каноническом наборе profiles и manifests.
- Family base, operation, scenario, modifiers и output contract компилируются детерминированно.
- Поддержка сценариев описывается capability-профилями и не считается симметричной между семействами.
- `multi_character` отсутствует в базовом бюджетном наборе.
- Direct OpenAI-compatible execution отделён от agent-host execution.
- OpenCode, Claude Code, Antigravity и будущий Codex подключаются через adapters/exporters без дублирования prompt knowledge.
- `SceneSpec` и `PromptResult` имеют версионированные схемы.
- SQLite сохраняет задачи, промежуточные данные, черновики и результаты.
- Базовый resolver работает без RAG.
- Старый `load_skill()` остаётся совместимым до завершения миграции потребителей.
- Архитектура проверена минимум на одном direct provider и одном agent host до массового переноса manifests.
