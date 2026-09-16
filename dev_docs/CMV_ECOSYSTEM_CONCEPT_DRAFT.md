# CMV Ecosystem Concept Draft

> Временный архитектурный документ. Фиксирует идеи по развитию ComfyViewer в модульную экосистему вокруг ComfyUI.
>
> Это не финальная спецификация и не обязательный roadmap. Цель документа - не потерять общую концепцию и позже разложить её на отдельные проекты, протоколы и этапы реализации.

## 1. Общая идея

CMV перестаёт быть только красивым просмотрщиком metadata и галереей генераций.

Целевая архитектура состоит из нескольких самостоятельных приложений и сервисов:

1. **CMV Desktop** - локальная библиотека, галерея, Simple Mode и центр пользовательской коллекции.
2. **Comfy Agent Studio** - отдельное desktop-приложение для агентной работы с ComfyUI.
3. **CMV Mobile** - лёгкий мобильный companion для просмотра, отбора, оценки, Simple Mode и экспорта.
4. **CMV Community** - опциональная публичная галерея для публикации работ.

Каждая часть должна быть полезна сама по себе.

Совместная установка нескольких компонентов не должна быть обязательной, но должна разблокировать дополнительные возможности.

Основной принцип:

```text
local-first core
      +
plugin architecture
      +
capability discovery
      +
optional network/social layers
```

CMV не должен превращаться в один огромный монолит.

---

## 2. CMV Desktop

CMV Desktop остаётся основным приложением для локальной библиотеки.

Базовые функции:

- просмотр изображений и видео;
- metadata и provenance;
- поиск;
- альбомы;
- избранное;
- рейтинг звёздами;
- история генераций;
- связи между исходными и производными файлами;
- Simple Mode генерации;
- локальный API для других компонентов;
- опциональная публикация в CMV Community.

CMV Desktop должен продолжать полноценно работать без Agent Studio, Mobile и Community.

---

## 3. Simple Mode как система плагинов

Текущую идею Simple Mode сохраняем, но меняем способ расширения.

Проблема текущего подхода не в самой типизации. Проблема в том, что модели, workflow, режимы и правила установки слишком сильно привязаны к ядру приложения.

Новая модель:

**Simple Mode = набор проверенных model plugins.**

Из коробки CMV может содержать условно 3 хорошо проверенных модели вместо большого количества частично поддерживаемых интеграций.

Каждая модель оформляется как самостоятельный plugin package.

Пример структуры:

```text
plugins/
  flux-schnell/
    manifest.json
    models.json
    workflows/
      txt2img.json
      img2img.json
    ui-schema.json
    install.json
```

Плагин может описывать:

- ID и версию;
- название;
- поддерживаемые режимы;
- необходимые модели;
- источники скачивания;
- workflow;
- параметры качества;
- aspect ratio;
- seed;
- reference image;
- дополнительные controls;
- совместимость;
- требования к ComfyUI/custom nodes.

Пример capability набора:

```json
{
  "id": "flux-schnell",
  "version": "1.0.0",
  "capabilities": [
    "txt2img"
  ]
}
```

### Импорт плагинов

Новые плагины должны устанавливаться через единый внутренний Plugin API.

Разные интерфейсы являются только транспортами:

```text
                CLI
                 |
MCP ------ Plugin API ------ HTTP
```

Например, следующие действия должны приводить к одному внутреннему механизму установки:

```text
cmv plugin install ./qwen-image-plugin
```

```text
MCP -> plugin.install(...)
```

```text
POST /api/plugins/install
```

Не должно существовать трёх независимых реализаций установки.

---

## 4. Comfy Agent Studio

Agent Studio создаётся отдельным desktop-приложением.

Главная идея:

> Codex для ComfyUI.

Агент выступает не только как генератор prompt, а как полноценный инженер среды ComfyUI.

Он может:

- исследовать установленный ComfyUI;
- читать доступные nodes;
- читать модели и адаптеры;
- создавать workflow;
- импортировать существующие workflow;
- скачивать workflow;
- устанавливать модели;
- устанавливать LoRA;
- устанавливать адаптеры;
- устанавливать custom nodes;
- запускать workflow;
- получать ошибки выполнения;
- читать логи;
- исправлять workflow;
- повторять выполнение;
- сохранять рабочие результаты.

Основной цикл:

```text
USER
  |
AGENT
  |
create/modify workflow
  |
COMFYUI
  |
run
  |
error/logs
  |
AGENT analyzes
  |
fix
  |
retry
```

Ошибка ComfyUI становится не тупиком, а observation для агента.

Жёсткая предварительная типизация всех возможных комбинаций моделей, nodes и workflow больше не требуется.

---

## 5. Использование CLI агентов

Agent Studio не требует отдельной обязательной sandbox-инфраструктуры.

Можно нативно использовать существующие CLI среды:

- Codex CLI;
- AGY;
- OpenCode;
- другие совместимые агенты.

Каждый CLI работает в своей среде и получает необходимые skills/tools.

Вместо обязательной sandbox можно использовать permission layer.

Пример:

```text
Read workflows           allow
Write workflows          allow
Download models          allow
Install custom nodes     ask
Run shell commands       ask
Delete models            ask
Modify ComfyUI config    ask
```

Sandbox может оставаться дополнительной возможностью для прямых API-сценариев, но не является фундаментальным требованием архитектуры.

---

## 6. Skills для Agent Studio

Ядро агента не должно содержать знания обо всём мире ComfyUI.

Расширение делается через skills.

Примеры:

```text
comfy-workflow-author
comfy-workflow-debugger
comfy-model-manager
comfy-custom-node-manager
comfy-dependency-resolver
comfy-runtime-diagnostics
civitai-resource-search
huggingface-resource-search
comfy-image-reconstruction
comfy-workflow-migration
```

Появление новой модели или нового семейства workflow не должно требовать переписывания всей Agent Studio.

---

## 7. Настоящий ComfyUI Editor внутри Agent Studio

Не нужно писать собственный аналог графового редактора ComfyUI.

Advanced Studio должна использовать настоящий frontend ComfyUI внутри desktop shell/WebView.

Схема:

```text
+------------------------------------------+
| Agent Studio shell                       |
+------------------------------------------+
| agent / toolbar / diagnostics            |
+------------------------------------------+
|                                          |
|       embedded ComfyUI frontend          |
|                                          |
|       local ComfyUI backend              |
|                                          |
+------------------------------------------+
```

Пользователь получает реальный редактор ComfyUI, а не его урезанный клон.

Поверх него Studio может добавить собственные действия:

- Ask Agent;
- Fix Workflow;
- Explain Error;
- Install Missing Nodes;
- Install Missing Models;
- Save to CMV;
- Return to Gallery.

### Human + Agent editing

Агент и человек должны работать с одним workflow document.

Пример:

```text
Human
  ^
  |
Workflow Document
  |
  v
Agent
  |
  v
ComfyUI
```

Если человек добавил node вручную, агент должен увидеть обновлённый graph.

Если агент изменил sampler или model, редактор должен получить обновление.

Если агент не смог исправить workflow автоматически, пользователь открывает настоящий ComfyUI Editor, завершает работу вручную и после сохранения агент может продолжить с новым состоянием.

---

## 8. Hugging Face и Civitai

Agent Studio должна уметь работать с внешними источниками моделей.

Основные источники:

- Hugging Face;
- Civitai.

Предпочтительный UX:

```text
Connect Hugging Face
       |
system browser
       |
authorization
       |
redirect/callback
       |
Agent Studio
```

Аналогично для Civitai.

Не заставлять пользователя вручную копировать API token, если поставщик поддерживает нормальный браузерный OAuth/device flow.

Токены должны храниться безопасно средствами ОС.

---

## 9. Resource Manager

Agent Studio получает единый Resource Manager.

Пример структуры:

```text
Resource Manager
  Installed
    Checkpoints
    LoRA
    VAE
    ControlNet
    Custom Nodes

  Hugging Face
  Civitai
  Comfy Registry
```

Агент и человек используют один механизм установки.

Пример:

```text
Workflow requires:

FLUX.1-dev
PuLID Flux
ComfyUI-PuLID-Flux

[Install all]
```

---

## 10. Capability discovery между Desktop приложениями

CMV Desktop и Agent Studio не должны быть жёстко сцеплены.

Они общаются через локальный protocol/API.

CMV при запуске обнаруживает Agent Studio и спрашивает её capabilities.

Пример:

```json
{
  "service": "comfy-agent",
  "version": "0.4.0",
  "capabilities": {
    "workflow.editor": true,
    "workflow.agent": true,
    "workflow.repair": true,
    "resource.install": true,
    "custom_nodes.install": true,
    "huggingface": true,
    "civitai": true,
    "codex": true,
    "opencode": true
  }
}
```

CMV не должен использовать логику вида:

```text
if agent_app_installed:
    show_everything()
```

Вместо этого UI строится по объявленным capabilities.

### Progressive unlock

Без Agent Studio CMV остаётся простым:

```text
Generate
Edit metadata
Open folder
```

После подключения Studio появляются дополнительные действия:

```text
Generate
Ask Agent
Open Studio
Remix
Repair Workflow
Install Model
Edit Workflow
```

Запускать одновременно два GUI не обязательно.

Если оба приложения установлены, одно может использовать background service второго.

---

## 11. Роли Desktop приложений

### CMV Desktop

```text
создать
хранить
искать
организовать
просматривать
оценивать
```

### Agent Studio

```text
строить
исследовать
устанавливать
чинить
отлаживать
адаптировать
```

Вместе они образуют полноценную локальную студию, но остаются самостоятельными приложениями.

---

# CMV Mobile

## 12. Общая роль Mobile

Mobile не является уменьшенной копией Desktop.

Это отдельный companion со своим UX.

Основной сценарий:

> просмотреть -> отобрать -> оценить -> разложить -> поделиться

Основные разделы:

```text
Gallery
Albums
Generate
Downloads
Servers
Settings
```

В Mobile не переносим:

- Agent Studio;
- полноценный workflow editor;
- управление custom nodes;
- сложный model manager;
- desktop diagnostics.

---

## 13. Local-first discovery

После установки Mobile изначально может иметь пустую библиотеку.

Приложение ищет запущенные CMV Desktop серверы в локальной сети.

Основной discovery механизм:

```text
mDNS / Bonjour
```

Например:

```text
_cmv._tcp.local
```

Mobile может обнаружить несколько серверов:

```text
Main PC
Laptop
Render Station
```

Пользователь может переключаться между ними.

Каждый сервер имеет постоянный `server_id`, поэтому приложение не зависит от текущего IP адреса.

Bluetooth можно использовать как дополнительный discovery/bootstrap механизм, но тяжёлые данные передаются по Wi-Fi/LAN.

---

## 14. Pairing без облачных аккаунтов

Для LAN соединения не нужен полноценный аккаунт или пароль.

Но сеть сама по себе не считается достаточной авторизацией.

Первое подключение выглядит примерно так:

```text
CMV Mobile
    |
find CMV Desktop
    |
Pair
    |
Desktop: Allow this device?
    |
exchange keys
    |
trusted device saved
```

После первого подтверждения последующие соединения происходят автоматически.

Цель:

- без облачного аккаунта;
- без логина;
- без пароля;
- без ручного API token;
- но с доверием между конкретными устройствами.

---

## 15. Mobile storage model

Для каждого asset существует три уровня состояния:

```text
REMOTE ONLY
preview есть локально
original только на Desktop

CACHED
preview + уменьшенная offline copy

DOWNLOADED
оригинал сохранён на телефоне
```

### Когда Desktop доступен по LAN

Mobile может показывать original напрямую с Desktop без обязательного постоянного сохранения файла на телефон.

```text
Phone
  |
Wi-Fi/LAN
  |
CMV Desktop
  |
original
```

Отдельная кнопка:

```text
Download to device
```

сохраняет оригинал локально.

### Когда Desktop недоступен

Порядок выбора:

```text
original downloaded
    -> original

cached display copy
    -> display copy

preview only
    -> CMV preview
```

---

## 16. Previews, display copies и originals

CMV Desktop уже генерирует preview, поэтому MVP Mobile может использовать существующий pipeline.

В дальнейшем можно хранить три представления:

```text
original
7680 x 4320
24 MB PNG

mobile display
2048 x 1152
650 KB WebP

preview
384 x 216
35 KB WebP
```

Для видео:

```text
thumbnail
proxy
original
```

Mobile SQLite хранит:

- asset ID;
- server ID;
- metadata;
- sync state;
- rating;
- favorite;
- album membership;
- availability;
- hashes;
- local file paths.

Сами изображения и видео хранятся обычными файлами, а не BLOB внутри SQLite.

---

## 17. Настройки offline sync

Возможные режимы:

```text
Offline library

Previews
Always

Offline copies
Never
Viewed items
Favorites
All

Original files
Manual download only
```

Можно отдельно включить автоматическую синхронизацию.

Интересный режим:

```text
Viewed items
```

Пользователь дома открыл несколько изображений в хорошем качестве. Они автоматически остаются доступными в offline cache после ухода из домашней сети.

---

## 18. Mobile Simple Mode

Mobile поддерживает Simple Mode, но не выполняет генерацию локально.

```text
Mobile
  |
Simple Generate request
  |
CMV Desktop
  |
Simple plugin
  |
ComfyUI
  |
GPU
```

Телефон:

- отправляет prompt;
- выбирает model plugin;
- выбирает aspect ratio;
- выбирает quality;
- показывает статус;
- получает результат.

Agent Mode сюда не добавляется.

---

## 19. Альбомы, звёзды и избранное

Это одна из ключевых функций Mobile.

Пользователь должен иметь возможность:

- создавать альбомы;
- просматривать альбомы;
- добавлять работы в альбомы;
- удалять работы из альбомов;
- ставить рейтинг 0-5 звёзд;
- добавлять в Favorites;
- при необходимости добавлять tags/notes.

Эти данные должны синхронизироваться с Desktop.

### Offline mutations

Оценка и организация библиотеки должны работать даже при выключенном Desktop.

Mobile хранит mutation queue:

```text
rate asset_123 -> 4
rate asset_124 -> 5
add asset_124 -> Portfolio
favorite asset_130
```

Когда сервер снова доступен, изменения синхронизируются.

---

## 20. Рейтинги как human feedback

Звёзды нужны не только для UI.

Со временем они создают собственный preference dataset:

```text
generation
+ model
+ workflow
+ prompt
+ parameters
+ user rating
```

Agent Studio сможет использовать эту историю как дополнительный контекст.

Например:

```text
Find my highest-rated Flux portraits
```

или:

```text
Create something similar to my 5-star generations
```

---

## 21. Export и Share

Mobile естественно подходит для публикации и отправки работ.

Первый уровень экспорта должен использовать системный Share Sheet iOS/Android.

```text
CMV Mobile
   |
Share
   |
System Share Sheet
   |
Telegram / Discord / Instagram / Files / Photos / etc.
```

Это позволяет не реализовывать сразу отдельный OAuth/API каждого социального сервиса.

### Поведение качества

Если Desktop доступен:

```text
Share
  |
fetch original
  |
temporary local file
  |
Share Sheet
```

Если original скачан на телефон, используется локальный файл.

Если доступна только offline display copy, можно отправить её с явным указанием качества.

Если есть только preview, можно попросить подключиться к Desktop для original export.

### Позже

Можно добавить export plugins:

```text
Native Share      built-in
Telegram          plugin
Bluesky           plugin
Mastodon          plugin
...
```

---

# CMV Community

## 22. Общая идея

Отдельный простой публичный сервер, куда пользователи могут публиковать свои работы.

Community не является обязательным облаком CMV.

Пользователь может никогда не регистрироваться и использовать всю локальную часть экосистемы без публичного сервиса.

Публикация доступна:

- с CMV Desktop;
- с CMV Mobile.

---

## 23. UI публичной галереи

Визуально можно ориентироваться на Pinterest и похожие сервисы:

- masonry grid;
- бесконечная лента;
- минимальные карточки;
- крупный визуальный контент;
- профили;
- коллекции/альбомы;
- likes/favorites;
- быстрый просмотр.

Но CMV Community получает дополнительную ценность за счёт генерационных metadata.

При открытии работы можно показывать:

```text
Model
Resolution
Prompt
Workflow
LoRA
Seed
Generation metadata
Created with CMV
```

Каждый блок публикуется только если автор разрешил его публикацию.

---

## 24. Publishing permissions

Автор сам выбирает, что публиковать:

- только изображение/видео;
- prompt;
- workflow;
- model info;
- LoRA info;
- generation parameters;
- downloadable original;
- downloadable workflow.

Не заставлять автора раскрывать prompt или workflow.

---

## 25. Open in CMV / Recreate

Если metadata доступны, Community может поддерживать действия:

```text
Open in CMV
Use this setup
Recreate
Download workflow
```

Если работа создана через verified Simple plugin:

```text
plugin: qwen-image
version: 1.3
```

CMV может определить отсутствие нужного plugin и предложить его установить.

После этого пользователь получает совместимую конфигурацию Simple Mode.

Более сложные произвольные workflow могут передаваться в Agent Studio.

---

## 26. Backend Community

Для публичного многопользовательского сервиса использовать PostgreSQL.

Причина выбора Postgres не в том, что SQLite обязательно медленнее.

SQLite остаётся отличным вариантом для локальных приложений.

Postgres лучше подходит публичному серверу из-за:

- конкурентных записей;
- нескольких пользователей;
- транзакций;
- фоновых задач;
- развитых индексов;
- дальнейшего масштабирования.

### Media storage

Изображения и видео не хранить непосредственно в PostgreSQL.

Схема:

```text
CMV Desktop -----+
                 |
CMV Mobile ------+--> Publish API
                        |
                    CMV Community
                   /      |       \
             Postgres    API    Object Storage
```

Postgres хранит:

- users;
- posts;
- albums;
- tags;
- likes;
- permissions;
- metadata;
- hashes;
- storage references.

Media хранится:

- сначала в filesystem через StorageProvider abstraction;
- позже в S3-compatible object storage.

---

## 27. Media pipeline Community

Для публичной ленты не нужно постоянно отдавать original.

Храним несколько представлений:

```text
thumbnail
  -> feed

display
  -> post view

original
  -> explicit download / zoom
```

Для видео аналогично:

```text
thumbnail
proxy
original
```

На ранней стадии основными ограничениями скорее станут storage и bandwidth, а не PostgreSQL или CPU.

---

## 28. Минимальный сервер

Для раннего MVP можно начать с небольшого VPS или бесплатного хостинга.

Ориентир для собственного VPS:

```text
2 vCPU
4 GB RAM
PostgreSQL
API
Web frontend
```

Частота CPU сама по себе не является главным критерием.

Гораздо важнее:

- количество одновременных соединений;
- RAM;
- storage;
- network bandwidth;
- размер previews;
- количество video traffic.

По мере роста object storage и CDN можно вынести отдельно.

---

# Общие архитектурные правила

## 29. Самодостаточность компонентов

Каждый компонент должен сохранять полезность отдельно.

### Только CMV Desktop

```text
Gallery
Metadata
Search
Albums
Ratings
Simple Mode
```

### Только Agent Studio

```text
ComfyUI management
Agent
Workflow editor
Model manager
Node manager
Diagnostics
```

### CMV Desktop + Agent Studio

```text
Gallery
Simple Mode
Agent workflows
Advanced editor
Repair
Models/nodes
Remix
```

### Mobile + Desktop

```text
Remote gallery
Ratings
Albums
Simple generation
Downloads
Share
```

### Community

```text
Public gallery
Profiles
Albums
Publishing
Workflow sharing
```

---

## 30. Общая схема экосистемы

```text
                         ComfyUI
                            |
                 +----------+----------+
                 |                     |
            CMV Desktop          Agent Studio
                 |                     |
                 +----------+----------+
                            |
                  Local capability/API
                            |
              +-------------+-------------+
              |                           |
         CMV Mobile                 CMV Community
        local companion             public service
```

Mobile не должен напрямую зависеть от Agent Studio.

Community не должен быть обязательным backend для Desktop или Mobile.

Agent Studio не должен превращаться в обязательный backend CMV.

Связь идёт через стабильные контракты и capabilities.

---

## 31. Главные контракты, которые нужно спроектировать отдельно

Перед активной реализацией стоит отдельно описать следующие протоколы.

### Plugin Contract

Для Simple Mode:

- manifest;
- versions;
- models;
- workflows;
- UI schema;
- compatibility;
- install/update/uninstall.

### Desktop Capability Protocol

Между CMV и Agent Studio:

- discovery;
- health;
- capabilities;
- jobs;
- workflow artifacts;
- logs;
- resource installs;
- events.

### LAN Mobile Protocol

Между CMV Desktop и Mobile:

- mDNS discovery;
- pairing;
- trusted devices;
- asset catalog sync;
- thumbnail access;
- display streaming;
- original streaming;
- downloads;
- mutation sync;
- Simple Mode jobs.

### Community Publish Protocol

Между CMV clients и публичным сервером:

- account auth;
- upload;
- media variants;
- metadata permissions;
- publish/update/delete;
- workflow/plugin references.

---

## 32. Возможный порядок развития

Это не строгий roadmap, а естественная последовательность, чтобы не раздувать проект раньше времени.

### Этап 1. Стабилизировать CMV Desktop

- сохранить текущий Simple Mode;
- выделить внутренний Plugin API;
- перевести существующие модели в первые verified plugins;
- не менять пользовательский UX сильнее необходимого.

### Этап 2. Plugin system

- manifest;
- install/update/remove;
- CLI transport;
- HTTP transport;
- MCP transport;
- compatibility checks.

### Этап 3. Agent Studio MVP

- отдельное desktop app;
- подключение к локальному ComfyUI;
- model/resource inventory;
- workflow creation;
- execution;
- logs;
- repair loop;
- один или два CLI агента.

### Этап 4. Embedded ComfyUI Editor

- настоящий ComfyUI frontend;
- shared workflow document;
- human/agent handoff;
- diagnostics overlay.

### Этап 5. Capability bridge

- CMV обнаруживает Agent Studio;
- unlock advanced actions;
- background service;
- version negotiation.

### Этап 6. CMV Mobile MVP

- LAN discovery;
- pairing;
- server switcher;
- gallery metadata sync;
- existing CMV previews;
- original streaming on LAN;
- explicit downloads.

### Этап 7. Mobile organization

- albums;
- stars;
- favorites;
- offline mutation queue;
- offline display cache;
- Simple Mode;
- native Share Sheet.

### Этап 8. CMV Community MVP

- accounts;
- PostgreSQL;
- storage abstraction;
- publish from Desktop/Mobile;
- Pinterest-style public feed;
- profiles/albums;
- metadata visibility controls.

### Этап 9. Community + ecosystem integration

- Open in CMV;
- plugin references;
- workflow sharing;
- Recreate;
- optional export plugins;
- scalable object storage/CDN.

---

## 33. Ключевая философия

Вся система строится вокруг нескольких правил.

### Local-first

Локальная библиотека и генерация не зависят от облачного аккаунта или Community.

### Accountless where possible

LAN Mobile pairing не требует облачной регистрации.

### Accounts only where necessary

Публичная Community требует нормальной авторизации, rate limits и abuse protection.

### Plugin-driven

Simple Mode расширяется плагинами, а не постоянным ростом hardcode в ядре.

### Agentic where uncertainty is unavoidable

Произвольные workflow, custom nodes и новые модели не пытаемся полностью типизировать заранее. Этим занимается Agent Studio.

### Deterministic path remains

Verified plugins Simple Mode сохраняют простой и предсказуемый путь для обычной генерации.

### Progressive disclosure

Новичок не обязан видеть workflow на 80 nodes.

Опытный пользователь при подключении Agent Studio получает полный контроль.

### No forced monolith

Desktop, Agent Studio, Mobile и Community развиваются независимо и общаются через стабильные контракты.

---

## 34. Итоговое позиционирование

CMV может вырасти из Meta Viewer в локальную генерационную экосистему:

```text
CMV Desktop
library + simple generation

Agent Studio
agentic ComfyUI development environment

CMV Mobile
browse + rate + organize + generate + share

CMV Community
publish + discover + reuse
```

Ключевой симбиоз:

```text
CMV знает, что было создано.
Agent Studio знает, как создать следующее.
ComfyUI умеет это выполнить.
Mobile помогает разобрать и публиковать результаты.
Community позволяет делиться ими с другими.
```

При этом ни один из дополнительных слоёв не должен становиться обязательным условием работы остальных.
