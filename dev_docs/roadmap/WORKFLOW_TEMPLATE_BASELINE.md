# Workflow template and resource baseline

Проверенный снимок текущего контракта редактора на 2026-07-26. Документ фиксирует исходное состояние для Phase 2 и не означает, что перечисленные templates покрывают целевую workflow matrix.

## Built-in templates

| Template | Category / result | Loader strategy | Resource slots | Output | Текущее ограничение |
| --- | --- | --- | --- | --- | --- |
| `core-image` | `simple` / image | checkpoint-contained, `CheckpointLoaderSimple` | required `checkpoint`; optional multiple `loras` | `SaveImage` node `7` | Только checkpoint-contained модели с embedded CLIP/VAE |
| `core-flux` | `simple` / image | separate components, `UNETLoader` + `DualCLIPLoader` + `VAELoader` | required `diffusion_model`, `clip_l`, `t5xxl`, `vae` | `SaveImage` node `10` | Flux-like baseline без LoRA injection; совместимость компонентов требует metadata/preflight |
| `core-flux-gguf` | `simple` / image | GGUF, `UnetLoaderGGUF` + `DualCLIPLoaderGGUF` + `VAELoader` | required GGUF `diffusion_model`; regular/GGUF `clip_l` и `t5xxl`; required `vae` | `SaveImage` node `10` | Требует ComfyUI-GGUF; совместимость компонентов не выводится только из формата файла |
| `core-reference` | `reference` / image | checkpoint-contained img2img | required `checkpoint`; optional multiple `loras` | `SaveImage` node `8` | Только базовый `LoadImage` + `VAEEncode`, без inpaint/control |
| `core-two-stage` | `advanced` / image | два checkpoint-contained pipeline | required `base_checkpoint`, `refiner_checkpoint`; optional `base_loras` | `SaveImage` node `11` | Оба этапа требуют checkpoint loader; это не separate-components refiner |
| `core-video` | `video` / video | separate diffusion model + dual text encoder + VAE | required `diffusion_model`, `text_encoder_1`, `text_encoder_2`, `vae` | `SaveVideo` node `10` | Зависит от конкретного набора native video nodes; GGUF не заявлен |

Source of truth: `app/comfyui/workflow_templates/*/manifest.json` и соответствующие `workflow.json`. Registry загружает built-in и user manifests одной Pydantic-схемой; sampling choices built-in templates расширяются полным каталогом ComfyUI во время загрузки.

## Manifest v2

Текущий `schema_version` — `2`. Manifest содержит:

- identity: `id`, `name`, template `version`, `category`, result `media_type`;
- graph location: `workflow`, optional `preview` и `description`;
- runtime requirements: `required_nodes`, semantic `resource_slots`, `output_nodes`;
- compatibility contract: `supported_ecosystems`, `loader_family` и explicit `component_policy` для CLIP/VAE;
- UI contract: `fields`, primary/advanced state и declarative `bindings`;
- resource bindings: explicit `node_input`, automatic standard loader lookup или generic `lora_chain` transformation.
- human-readable `capability_notes` и `limitation_notes`.

Registry мигрирует schema v1 при чтении: loader family и component policy выводятся только из однозначных semantic slots, ecosystem становится `other`, а manifest получает заметку о необходимости compatibility review. При импорте результат сохраняется уже как v2. Неизвестная версия не мигрируется и отклоняется строгой Pydantic-схемой.

Валидация v2 проверяет обязательные поля, уникальность IDs/ecosystems/notes, согласованность loader family с resource slots и отсутствие противоречий между component policy и required CLIP/VAE slots. Registry validation status и inventory fingerprint относятся к будущему registry contract, а не к schema самого graph manifest.

## Каноническая resource taxonomy

| Canonical type | ComfyUI folders | Classification |
| --- | --- | --- |
| `checkpoint` | `checkpoints` | checkpoint-contained model |
| `diffusion_model` | `diffusion_models`, `unet` | model file с расширением, отличным от `.gguf` |
| `diffusion_model_gguf` | `diffusion_models`, `unet` | `.gguf`, регистр расширения не важен |
| `text_encoder` | `text_encoders`, `clip` | encoder file с расширением, отличным от `.gguf` |
| `text_encoder_gguf` | `text_encoders`, `clip` | `.gguf`, регистр расширения не важен |
| `vae` | `vae` | VAE |
| `lora`, `locon`, `dora` | `loras` | adapter role; точный subtype требует metadata, не выводится из папки |
| `embedding` | `embeddings` | text embedding |
| `clip_vision` | `clip_vision` | reference/image encoder |
| `controlnet` | `controlnet` | control/reference model |
| `upscale_model` | `upscale_models` | learned upscaler |
| `unknown` | — | ресурс без доказанной semantic role |

Video templates используют те же технические роли `diffusion_model*`, `text_encoder*` и `vae`; совместимость с конкретной video architecture задаётся `supported_ecosystems` и в будущем уточняется metadata каталога, а не новым типом файла только из-за media type результата.

Канонические ecosystems на этом этапе: `sd15`, `sdxl`, `flux_1`, `pony`, `illustrious`, `hunyuan_video`, `other`.

Совместимые aliases старых или сторонних manifests нормализуются при чтении и никогда не сериализуются обратно как отдельная taxonomy:

- `unet` → `diffusion_model`;
- `unet_gguf` → `diffusion_model_gguf`;
- `clip` → `text_encoder`;
- `clip_gguf` → `text_encoder_gguf`.

## Поддерживаемые bindings

Automatic single-node lookup поддерживает `CheckpointLoaderSimple.ckpt_name`, `VAELoader.vae_name`, `UNETLoader.unet_name`, `CLIPLoader.clip_name`, `CLIPVisionLoader.clip_name`, `ControlNetLoader.control_net_name` и `UpscaleModelLoader.model_name`.

GGUF loaders намеренно не добавлены в automatic lookup: их node types зависят от установленного custom-node package. GGUF-template должен объявлять проверенный `required_nodes` и explicit `node_input` binding. Неоднозначный graph с несколькими подходящими loader nodes также требует explicit binding.

`lora_chain` поддерживает несколько adapters через добавление стандартных `LoraLoader` nodes и переподключение downstream MODEL/CLIP edges. Он применим только к graph, где выбранный source node действительно отдаёт обе ветви.

## Compatibility diagnostics

Editor использует один template-aware evaluator для bootstrap options, dependency preview и run preflight:

- semantic resource type должен соответствовать active slot;
- известный model ecosystem сверяется с `supported_ecosystems` template;
- curated `technical_status` и `restriction_reason` имеют приоритет и сохраняются при следующем inventory sync;
- доказанный `incompatible` resource исключается из обычного selectable списка и показывается отдельно с причиной;
- ранее сохранённый несовместимый выбор остаётся видимым в disabled state и не удаляется молча;
- `limited` и `experimental` остаются selectable и показывают предупреждение;
- неизвестная архитектура primary model считается `experimental`, а не автоматически несовместимой;
- preflight блокирует run при `incompatible`, но не при `limited`/`experimental`.

LoRA повторно оценивается относительно выбранного checkpoint при каждом preview/run. Любое изменение resource selection сбрасывает готовность предыдущего preview, поэтому смена checkpoint не может использовать устаревший compatibility result.

## Editor persistence и imported result

`WorkflowDraft` сохраняет template identity/version, field values, resource selections, optional `source_asset_id` и `ai_prompt_draft_id`, status и timestamps. Смена template создаёт или открывает отдельное workspace state; запуск не является побочным эффектом создания draft.

`WorkflowRun` сохраняет draft, ComfyUI `prompt_id`/`client_id`, status/progress, current node, normalized error, output references и Library asset IDs.

Импортированный output получает `generation` provenance с run, draft, template, prompt и output-node identity. API graph сохраняется как `prompt_api_json`/`workflow`. Если draft создан из Library asset, result связывается через `derived_from_asset_id`.

## Регрессионные проверки baseline

- registry загружает четыре категории и проверяет manifest/graph references;
- basic image matrix содержит отдельные checkpoint, separate-components и GGUF templates;
- generic LoRA transformation и declarative field bindings покрыты unit tests;
- draft → preview → run dependency checks покрыты route/service tests;
- standard и GGUF resource lists разделяются по active semantic slot;
- bootstrap и preflight возвращают одинаковые compatibility statuses и причины;
- curated catalog restriction переживает повторный inventory sync;
- unknown, ecosystem mismatch и explicit incompatible состояния покрыты отдельными regression cases;
- legacy taxonomy aliases нормализуются в canonical values.

## Runtime evidence

26 июля 2026 года оба Flux-like manifests сверены с фактически запущенной Windows Portable установкой ComfyUI через `/object_info`:

- присутствуют все 11 используемых core/custom node types, включая `UnetLoaderGGUF` и `DualCLIPLoaderGGUF` из ComfyUI-GGUF 1.1.9;
- подтверждены все declarative input names, loader type `flux`, sampler `euler` и scheduler `simple`;
- unit/API regression suite проверяет compiled standard/GGUF graphs, mixed regular/GGUF text encoders и фильтрацию bootstrap resource options по active slot.

Фактическая генерация этими двумя templates остаётся в Phase 9 workflow matrix: текущая установка не содержит подтверждённого полного Flux component set, а ранее установленные GGUF models были удалены пользователем, поэтому наличие nodes не выдается за end-to-end generation evidence.

### Отложенная GGUF-проверка

После появления совместимого GGUF diffusion model и требуемых text encoders/VAE нужно повторить проверку без изменения уже подтверждённого node contract:

- убедиться, что inventory классифицирует `.gguf` как `diffusion_model_gguf` или `text_encoder_gguf` и показывает файл только в соответствующем slot;
- создать draft на `core-flux-gguf`, пройти dependency preview/preflight и подтвердить отсутствие unresolved resources;
- выполнить реальный generation run в ComfyUI и дождаться terminal status;
- проверить импорт output в Library, сохранение template/draft/run provenance и отсутствие ошибочной checkpoint/separate-components подстановки;
- только после этого закрыть `GGUF generation` в Phase 9 workflow matrix.
