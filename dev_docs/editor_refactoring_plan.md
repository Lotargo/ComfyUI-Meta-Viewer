# Create / Simple Mode - план рефакторинга

## Статус документа

Этот документ является рабочим планом для пользовательской страницы `/create`.

Simple Mode не должен быть упрощённой копией ComfyUI. Пользователь выбирает подготовленную модель, описывает изображение, при необходимости добавляет референс, выбирает соотношение сторон, качество и количество изображений. Все технические детали конкретного ComfyUI workflow остаются внутри подготовленного профиля модели.

`docs/simple-mode-redesign.md` остаётся источником продуктовой концепции. Этот документ фиксирует текущую реализацию и новую техническую структуру после проверки реального интерфейса.

---

## 1. Проблемы текущей реализации

### 1.1 Модели появляются с задержкой

Сейчас frontend ждёт полный `/api/simple/bootstrap`, и только после ответа строит selector моделей.

В bootstrap одновременно выполняются:

- сканирование / чтение runtime inventory;
- проверка профилей;
- чтение AI settings;
- получение ambient candidates;
- подготовка прочих данных.

Из-за этого основной selector появляется спустя заметное время после самой формы.

### Решение

Каталог моделей должен быть доступен сразу при рендере страницы.

```text
render /create
  -> сразу показать 8 моделей
  -> независимо запросить health выбранной модели
  -> независимо загрузить ambient background
  -> независимо проверить AI integration
```

Ни ambient, ни ComfyUI health, ни AI provider не должны блокировать отображение каталога.

---

### 1.2 Ambient background не получает изображения

Текущая реализация Simple Mode использует отдельный сырой SQL-запрос вместо уже существующего media/library контура.

Это плохое решение по двум причинам:

1. запрос дублирует знание о структуре БД;
2. он расходится с реальной схемой и API Viewer / Library.

Simple Mode должен получать изображения тем же способом, которым их уже получает библиотека / галерея, и использовать существующие preview / thumbnail endpoints.

### Решение

Сделать отдельный лёгкий endpoint Simple Mode, например:

```text
GET /api/simple/ambient
```

Но внутри он не создаёт собственный индекс и не пишет новый SQL. Он использует существующий media/library слой и возвращает небольшой случайный набор доступных изображений:

```json
{
  "items": [
    {
      "id": 123,
      "preview_url": "/api/preview/123",
      "thumbnail_url": "/api/thumbnail/123"
    }
  ]
}
```

Правила:

- источником является существующая библиотека;
- видео исключаются;
- недоступные assets исключаются;
- для основного background используется preview;
- thumbnail является fallback;
- отсутствие изображений не является ошибкой - остаётся CSS fallback background;
- загрузка ambient происходит отдельно от model catalog и не задерживает форму.

---

### 1.3 Текущая модель профилей неправильная

Сейчас backend пытается свести разные семейства моделей к нескольким общим профилям (`Realism`, `Anime`, `Universal`) и двум общим workflow.

Это не соответствует реальной задаче.

Новая модель:

> Одна пользовательская модель = один заранее проверенный собственный workflow + собственные зависимости + собственные quality presets.

Никакого выбора случайного checkpoint внутри общего workflow не будет.

---

### 1.4 Текущая логика Quality неправильная

Нельзя интерпретировать качество как универсальное увеличение `steps`.

Разные модели работают в разных режимах:

- одной модели достаточно около 8 шагов;
- другой требуется 10-15;
- третья использует другой sampler / scheduler / guidance;
- отдельный preset может менять несколько параметров workflow одновременно;
- для некоторых архитектур изменение steps вообще не является главным отличием quality level.

Поэтому frontend не должен показывать пользователю `18 шагов`, `25 шагов`, `50 шагов` как смысл выбора качества.

Пользователь видит только три семантических режима:

```text
Быстро
Стандартно
Детально
```

Их техническое значение определяется отдельно для каждой модели.

---

## 2. Утверждённый каталог моделей

На первом этапе в Simple Mode будет ровно 8 подготовленных моделей.

Пользовательские названия пока нейтральные:

| UI | Источник |
|---|---|
| Model 1 | https://civitai.red/models/4201/realistic-vision-v60-b1 |
| Model 2 | https://civitai.red/models/133005/juggernaut-xl |
| Model 3 | https://civitai.red/models/443821/cyberrealistic-pony?modelVersionId=2884631 |
| Model 4 | https://civitai.red/models/2731187/moody-krea-2-mix-uncensored?modelVersionId=3209007 |
| Model 5 | https://civitai.red/models/2544636/wai-anima?modelVersionId=2983680 |
| Model 6 | https://civitai.red/models/2182526/gonzalomo-chroma?modelVersionId=2627397 |
| Model 7 | https://civitai.red/models/260267/animagine-xl-v31?modelVersionId=403131 |
| Model 8 | https://civitai.red/models/1412760/lunarcherrymix-illustrious |

В UI не обязательно показывать реальное название Civitai модели. Реальное имя, version id и provenance хранятся внутри manifest.

Для моделей 1, 2 и 8 перед включением автоматической установки необходимо отдельно зафиксировать конкретный version id и конкретные download URLs. Bare model page не считается стабильной зависимостью.

---

## 3. Структура model pack

Нельзя хранить все 8 workflow и все preset-конфигурации в одном гигантском Python-файле.

Каждая модель получает отдельную директорию.

```text
app/comfyui/simple_models/
  model_01/
    manifest.json
    resources.json
    bindings.json
    workflow.json
    presets/
      fast.json
      standard.json
      detailed.json

  model_02/
    manifest.json
    resources.json
    bindings.json
    workflow.json
    presets/
      fast.json
      standard.json
      detailed.json

  ...

  model_08/
    ...
```

### `manifest.json`

Человекочитаемая информация о профиле:

```json
{
  "id": "model_01",
  "display_name": "Model 1",
  "source_name": "Realistic Vision V6.0 B1",
  "source_page": "...",
  "model_id": 4201,
  "version_id": null,
  "prompt_family": "sd15",
  "default_quality": "standard"
}
```

Здесь же могут храниться:

- короткое описание для UI;
- минимальная / комфортная VRAM;
- поддерживаемые ratios;
- UI artwork / preview metadata;
- версия самого model pack.

### `resources.json`

Только необходимые для запуска workflow файлы.

```json
{
  "resources": [
    {
      "id": "checkpoint",
      "folder": "checkpoints",
      "filename": "...safetensors",
      "size_bytes": 0,
      "sha256": null,
      "download_url": "https://..."
    }
  ]
}
```

Если модели необходимы отдельные text encoders / VAE / diffusion model, они перечисляются здесь отдельными entries.

В первую версию не включаем:

- LoRA adapters;
- upscalers;
- ControlNet;
- IP-Adapter;
- дополнительные optional resources.

### `workflow.json`

Полный проверенный ComfyUI API workflow именно этой модели.

Модель и необходимые компоненты уже выбраны нами в workflow. Пользователь их не подменяет.

### `bindings.json`

Явные места, в которые Simple Mode может подставлять runtime values.

Например:

```json
{
  "positive_prompt": {"node": "6", "input": "text"},
  "negative_prompt": {"node": "7", "input": "text"},
  "width": {"node": "5", "input": "width"},
  "height": {"node": "5", "input": "height"},
  "batch_size": {"node": "5", "input": "batch_size"},
  "seed": {"node": "3", "input": "seed"}
}
```

Это заменяет текущую эвристику вида "найти все KSampler / CLIPTextEncode и догадаться, что в них менять".

### `presets/*.json`

Каждый preset является patch именно для конкретного workflow.

Пример только формата:

```json
{
  "nodes": {
    "3": {
      "inputs": {
        "steps": 10,
        "cfg": 1.2,
        "sampler_name": "euler",
        "scheduler": "simple"
      }
    }
  }
}
```

Но значения не должны копироваться между моделями автоматически. Для каждой модели `fast`, `standard`, `detailed` калибруются отдельно.

Preset может менять любой разрешённый input workflow, а не только steps.

---

## 4. Новый compiler

Текущий compiler с проверками `class_type == KSampler`, `CLIPTextEncode`, `FluxGuidance` должен уйти из основного Simple Mode path.

Новый pipeline:

```text
selected model id
  -> load model/manifest.json
  -> load model/workflow.json
  -> load model/presets/<quality>.json
  -> apply exact preset patch
  -> apply explicit bindings
       prompt
       negative prompt
       width / height
       batch
       seed
  -> validate resulting workflow
  -> queue to ComfyUI
```

Compiler не знает, сколько шагов "хорошо" для модели. Это знает только её preset file.

Compiler не угадывает node topology. Это знает только `bindings.json` и preset patch.

---

## 5. Выбор модели в UI

Восемь больших dashboard-карточек на основной форме будут занимать слишком много места.

Основной selector делаем компактным списком / popover:

```text
Модель
[ Model 1                         v ]

open:
  Model 1     Готова
  Model 2     Требуется установка
  Model 3     Готова
  ...
  Model 8     Требуется установка
```

В дальнейшем пользовательские названия заменят `Model 1 ... Model 8` без изменения внутренних ids.

Каталог из 8 строк должен появляться сразу. Health status подгружается отдельно и обновляет уже существующие строки.

Выбор модели не должен ждать полного runtime scan.

---

## 6. Проверка установки модели

При выборе модели выполняется health check только её declared resources.

```text
Model 5
  -> resources.json
  -> checkpoints / diffusion_models / text_encoders / vae
  -> runtime inventory
  -> compare exact filenames / hashes where available
```

Результаты:

```text
ready
missing_resources
checking
installing
broken
```

Если всё найдено - модель готова к генерации.

Если чего-то нет - рядом с selector показывается ненавязчивое состояние `Требуется установка`.

---

## 7. Установка отсутствующих компонентов

При выборе неустановленной модели открываем install panel / modal только после действия пользователя.

Пример:

```text
Для Model 5 не хватает 3 компонентов

[ ] WAI-ANIMA checkpoint        3.9 GB
[ ] Qwen text encoder           1.1 GB
[ ] Qwen Image VAE              242 MB

Итого: 5.2 GB

[ Скачать всё ]
```

После запуска:

```text
checkpoint        48%  [Пауза]
text encoder       0%  ожидает
VAE                0%  ожидает
```

При ошибке:

```text
checkpoint        Ошибка сети  [Повторить]
```

После завершения:

```text
download complete
  -> invalidate model inventory
  -> rescan target folders
  -> health check selected model
  -> Ready
```

---

## 8. Download architecture

Для curated Simple Mode не используем Civitai search API и не запрашиваем Civitai metadata во время работы приложения.

Все источники заранее зафиксированы в `resources.json` как прямые download URLs.

### Важное ограничение браузера

Не используем нативный browser download manager как механизм установки модели.

Причина: браузер не может надёжно сохранить скачанный файл прямо в необходимый `ComfyUI/models/<folder>` без дополнительного пользовательского выбора и разрешений. Также приложение не получает нормальный переносимый контроль над resume state браузерной загрузки.

Поэтому браузер отвечает только за UI управления загрузкой, а файл скачивает существующий backend downloader worker.

Это не новый механизм с нуля. В проекте уже есть:

- background download worker;
- запись в `.part`;
- progress bytes;
- сохранение в папки ComfyUI;
- download records;
- polling статуса.

Его нужно обобщить для direct URLs и добавить недостающие состояния.

### Требуемые операции

```text
start
pause
resume
retry
cancel
```

### Resume

Для pause / network failure `.part` не удаляется.

Resume выполняется через HTTP Range:

```http
Range: bytes=<current_part_size>-
```

Если сервер поддерживает Range - продолжаем запись в `.part`.

Если источник не поддерживает Range - безопасно начинаем конкретный файл заново.

На `completed` выполняется атомарный rename `.part -> final`.

---

## 9. Quality

В UI ровно три режима:

```text
Быстро
Стандартно
Детально
```

Не показываем:

- количество steps;
- CFG;
- sampler;
- scheduler;
- guidance;
- внутренние названия preset files.

Frontend передаёт только:

```json
{"quality": "fast"}
```

или `standard` / `detailed`.

Все технические различия находятся в:

```text
model_xx/presets/fast.json
model_xx/presets/standard.json
model_xx/presets/detailed.json
```

---

## 10. Ambient loading

Ambient не входит в critical rendering path.

```text
/create HTML
  -> render controls + model catalog
  -> request ambient candidates
  -> preload one preview
  -> crossfade into background
```

После успешной генерации новое изображение временно становится главным ambient artwork.

Через заданный интервал можно снова перейти к случайному изображению библиотеки.

---

## 11. Reference / prompt / assistant

Сохраняются уже утверждённые правила:

- native file input скрыт;
- reference preview использует собственный UI;
- drag and drop поддерживается;
- prompt auto-grow имеет максимальную высоту;
- `Улучшать с ИИ` является режимом, а не отдельным обязательным шагом;
- assistant открывается поверх Create и не меняет layout;
- технический ComfyUI status постоянно в header не показывается;
- слово `masterpiece / шедевр` не используется как product language или fallback prompt.

---

## 12. Порядок реализации

### Этап 1 - исправить текущие runtime/UI ошибки

- [ ] Ambient получает assets через существующий library/media слой.
- [ ] Исправить неправильные поля БД в Simple Mode output/ambient code.
- [ ] Background загружается отдельно от bootstrap.
- [ ] Model selector отображается сразу, без ожидания inventory.
- [ ] Quality UI сокращён до `Быстро / Стандартно / Детально`.
- [ ] Убрать отображение steps из quality controls.

### Этап 2 - model pack architecture

- [ ] Создать `app/comfyui/simple_models/`.
- [ ] Создать отдельную директорию для каждой из 8 моделей.
- [ ] Ввести loader / registry для manifest files.
- [ ] Убрать giant hardcoded `APPROVED_PROFILES` из active path.
- [ ] Ввести explicit bindings.
- [ ] Ввести exact workflow patch presets.

### Этап 3 - 8 workflow

Для каждой модели отдельно:

- [ ] зафиксировать точную версию;
- [ ] зафиксировать прямые URL всех обязательных ресурсов;
- [ ] зафиксировать filename / folder;
- [ ] собрать базовый ComfyUI API workflow;
- [ ] проверить text encoder / VAE / architecture requirements;
- [ ] подготовить `fast`;
- [ ] подготовить `standard`;
- [ ] подготовить `detailed`;
- [ ] провести реальную генерацию каждого preset;

### Этап 4 - installer

- [ ] Direct URL download без Civitai API.
- [ ] Missing resources list.
- [ ] Download all.
- [ ] Progress per resource и общий progress.
- [ ] Pause.
- [ ] Resume через Range.
- [ ] Retry после network failure.
- [ ] Correct ComfyUI target folder.
- [ ] Post-download rescan + health validation.

### Этап 5 - полировка UI

- [ ] Compact model list / popover для 8 моделей.
- [ ] Статусы Ready / Требуется установка / Installing / Broken.
- [ ] Install modal.
- [ ] Ambient crossfade.
- [ ] Generation result reveal.
- [ ] Responsive presentation.

---

## 13. Acceptance criteria

- [ ] Все 8 моделей видны сразу после открытия `/create`.
- [ ] Selector не ждёт ComfyUI inventory или ambient запрос.
- [ ] У каждой модели собственный base workflow.
- [ ] У каждой модели собственные `fast / standard / detailed` configs.
- [ ] Нет глобального правила `качество = больше steps`.
- [ ] Compiler не ищет KSampler / CLIP nodes эвристически.
- [ ] Пользователь не выбирает checkpoint / encoder / VAE вручную.
- [ ] При отсутствии ресурсов показывается точный список missing files.
- [ ] `Скачать всё` использует заранее подготовленные direct URLs.
- [ ] Civitai API не требуется для curated model installation.
- [ ] Загрузка поддерживает progress, pause, resume и retry.
- [ ] Файлы попадают сразу в правильные ComfyUI model folders.
- [ ] После установки выполняется повторный health check.
- [ ] Ambient использует изображения существующей Library / Gallery.
- [ ] При наличии изображений ambient реально виден на странице.
- [ ] При пустой библиотеке интерфейс остаётся корректным.
- [ ] В Quality UI только `Быстро / Стандартно / Детально` без технических параметров.
- [ ] LoRA и upscalers отсутствуют в первой версии Simple Mode.

---

## 14. Что намеренно откладываем

Не включаем сейчас:

- LoRA как styles;
- upscalers;
- Civitai browser / API для Simple Mode;
- произвольный выбор локальных моделей;
- arbitrary workflow import;
- ControlNet;
- IP-Adapter;
- video generation;
- Advanced / node editor controls.

Сначала доводим восемь curated model packs до полностью воспроизводимого состояния.