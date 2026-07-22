# Prompt intent benchmark

The intent benchmark measures whether an AI can turn a short, ordinary user request into a useful model-specific image prompt without receiving a ready-made production brief.

It is separate from `quality_benchmark.py`, which measures preservation and organisation of a detailed brief.

## Independent family adaptations

The catalog contains independently runnable Flux-like, SDXL, and Pony adaptations. They are not a comparative leaderboard, paired sample, or mandatory matrix run. Selecting an adaptation compiles that family profile, runs only the chosen scenario, and evaluates the result using the scenario rubric plus the named family's prompt conventions.

The current catalog exposes:

- 7 Flux-like adaptations;
- 7 SDXL adaptations, including limited `graphic_design_text` support;
- 6 Pony adaptations; unsupported `graphic_design_text` is omitted, while limited scenarios remain selectable and compile an explicit warning.

The shared human request and scenario rubric make each family adaptation reproducible, but one result is never used to rank or automatically select another family.

## Execution model

One benchmark run makes two explicit OpenCode calls:

1. **Generator** — converts the short human request into `PromptResult`.
2. **Judge** — evaluates the candidate with a strict 100-point rubric.

By default the judge uses the same OpenCode profile and model as the generator. This keeps the benchmark free when the selected provider/model is free. A different judge profile can be supplied later with `--judge-profile`.

The same-model judge is treated as a potentially correlated evaluator. The free baseline therefore weights deterministic checks more heavily:

```text
same model: combined = round(deterministic_score * 0.60 + judge_score * 0.40)
separate judge: combined = round(deterministic_score * 0.50 + judge_score * 0.50)
```

The judge cannot override hard deterministic failures such as losing the core subject intent or violating the model-family negative prompt policy.

Missing a requested intent direction is not a hard failure for a free model, but it caps the final status at `WARN` even when the numerical score crosses the pass threshold.

## Benchmarks

### `flux-portrait-intent-basic`

Raw user request:

```text
Сделай атмосферный портрет взрослой девушки-керамиста в её мастерской. Хочется, чтобы кадр выглядел естественно, дорого и немного уютно.
```

The request deliberately omits camera, lens, lighting, materials, environment details, composition, and depth. The generator must infer useful visual decisions while preserving the subject and mood.

Required intent dimensions:

- `natural`;
- `premium_refined`, representing «дорого»;
- `cozy`.

Portrait-specific deterministic checks include:

- adult female ceramic artist in a workshop;
- camera and framing;
- motivated lighting;
- workshop-specific details;
- tactile materials;
- subject pose, gaze, or action;
- depth, colour, and photographic medium.

### `flux-single-character-intent-basic`

Raw user request:

```text
Нарисуй одного персонажа — взрослую девушку-следопыта в полный рост на лесной тропе. Образ должен быть практичным, уверенным и немного загадочным.
```

This benchmark checks full-character design rather than portrait detail. The input fixes one character, role, crop, location, and broad intent but leaves costume construction, equipment, stance, camera, lighting, terrain contact, and medium to the generator.

Required intent dimensions:

- `practical`;
- `confident`;
- `mysterious`.

Single-character-specific deterministic checks include:

- one adult woman ranger on a forest trail;
- explicit single-subject intent and full-body framing;
- motivated lighting;
- coherent functional clothing, equipment, and materials;
- stance, action, or gesture;
- physical grounding in the forest environment;
- depth, colour, and medium.

### `flux-architecture-interior-intent-basic`

Raw user request:

```text
Создай светлый интерьер небольшой современной библиотеки с зоной чтения. Пространство должно выглядеть спокойным, тёплым и функциональным.
```

This benchmark checks architectural reasoning rather than a decorative list. The input fixes the space type, scale, reading function, and broad atmosphere but leaves viewpoint, perspective, zoning, circulation, materials, lighting, furnishing, and spatial depth to the generator.

Required intent dimensions:

- `calm`;
- `warm`;
- `functional`.

Architecture-specific deterministic checks include:

- a compact library interior with an explicit reading area;
- camera position or coherent architectural perspective;
- natural or artificial lighting strategy;
- zoning, shelving, and circulation;
- surface-specific materials;
- human scale, furnishing, or functional clearance;
- spatial depth and architectural medium.

### `flux-landscape-environment-intent-basic`

Raw user request:

```text
Создай широкий пейзаж северной долины с рекой и далёкими горами на рассвете. Атмосфера должна быть просторной, прохладной и немного величественной.
```

This benchmark checks environmental structure rather than generic scenic praise. The input fixes the broad geography, time of day, and atmosphere but leaves viewpoint, foreground-to-background composition, terrain ecology, river behaviour, weather, lighting, and scale references to the generator.

Required intent dimensions:

- `spacious`;
- `cool`;
- `majestic`.

Landscape-specific deterministic checks include:

- a northern valley landscape with river, distant mountains, and dawn;
- viewpoint, horizon, and foreground-to-background composition;
- dawn lighting, sky, or atmospheric weather;
- terrain, geology, and climate-consistent vegetation;
- river course, banks, flow, or reflections;
- distance progression and environmental scale;
- depth, colour, and landscape medium.

### `flux-illustration-art-intent-basic`

Raw user request:

```text
Нарисуй сказочную книжную иллюстрацию маленького домика в форме чайника в осеннем лесу. Настроение должно быть уютным, причудливым и немного волшебным.
```

This benchmark checks visual storytelling and art direction rather than generic fantasy praise. The input fixes a storybook format, focal object, setting, and atmosphere but leaves composition, silhouette, shape language, medium, mark-making, palette, lighting, and supporting narrative detail to the generator.

Required intent dimensions:

- `cozy`;
- `whimsical`;
- `magical`.

Illustration-specific deterministic checks include:

- a storybook illustration of a teapot-shaped house in an autumn forest;
- focal hierarchy, silhouette, and layered composition;
- one coherent illustration medium with compatible mark-making;
- stylised shape language or legible teapot construction;
- palette, value structure, and motivated illustration lighting;
- forest or habitation details that support a readable story moment;
- depth, colour, and illustration medium.

### `flux-product-intent-basic`

Raw user request:

```text
Сделай красивую рекламную фотографию флакона духов. Нужен дорогой, чистый и немного тёплый образ.
```

This benchmark checks whether the same prompt system generalises from people to commercial object photography. The input does not specify lens, bottle placement, background, materials, reflections, light direction, or campaign art direction.

Required intent dimensions:

- `premium_refined`;
- `clean_minimal`;
- `warm`.

Product-specific deterministic checks include:

- perfume bottle and commercial product-image intent;
- camera and hero framing;
- motivated studio lighting;
- product set or background;
- glass, liquid, metal, reflections, or refraction;
- bottle placement, label readability, and negative space;
- depth, colour, and commercial photographic medium.

### `flux-graphic-design-text-intent-basic`

Raw user request:

```text
Создай вертикальную афишу вечернего джазового концерта. Главный текст — «NORTH JAZZ», ниже укажи «24 OCTOBER». Дизайн должен быть современным, ритмичным и немного ночным.
```

This benchmark checks graphic-design reasoning and exact-copy preservation rather than generic poster styling. The input fixes the format, event, headline, date, and broad art direction but leaves hierarchy, grid, placement, letter treatment, contrast, visual rhythm, palette, and print medium to the generator.

Required intent dimensions:

- `modern`;
- `rhythmic`;
- `nocturnal`.

Graphic-design-specific deterministic checks include:

- a vertical jazz concert poster preserving exact `NORTH JAZZ` and `24 OCTOBER` text;
- headline/date hierarchy and reading order;
- placement, alignment, grid, or margins;
- font category or visible letter treatment;
- clean text space, contrast, or explicit legibility;
- jazz-specific imagery or visual rhythm;
- colour and graphic/print medium decisions.

## Shared deterministic rubric

Every benchmark has a 100-point deterministic rubric:

- core intent preservation — 16;
- five scenario-specific coverage checks — 38;
- explicit coverage of requested intent dimensions — 24;
- non-trivial expansion through independent visual decision groups — 12;
- coherent structure — 4;
- family prompt policy — 3 (FLUX negative handling, SDXL conventions, or Pony base controls);
- absence of generic quality slogans — 3.

The expansion check is language-independent at the input/output boundary. It does not compare Russian input words with English output words. Instead it verifies scenario-specific visual decision groups.

## Model judge rubric

The model judge independently scores:

- intent fidelity — 20;
- useful visual expansion — 20;
- atmosphere translation — 15;
- composition and camera — 10;
- lighting — 10;
- environment and materials — 10;
- coherence and model fit — 10;
- restraint and consistency — 5.

The judge receives the required intent dimensions and family-specific policy. For FLUX, an empty `negative_prompt` is explicitly correct and must not be penalized or listed as a weakness.

## Managed process cleanup

OpenCode generator and judge calls use `app.ai.managed_process.run_managed_command`.

On Windows, the root npm/cmd process is attached to a Job Object with `KILL_ON_JOB_CLOSE`. This prevents an orphaned `node.exe` from surviving after its parent exits, retaining stdout pipes, or locking the temporary `cmv-opencode-*` workspace. On timeout, the job is terminated, `taskkill /T /F` remains as a fallback, and pipes are drained or closed before the temporary directory is removed.

The normal default timeout is five minutes per generator or judge call unless `--timeout` explicitly overrides it.

## Commands

Open the interactive launcher (also available explicitly as `interactive`):

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark
```

The menu asks for one prompt family, operation, scenario benchmark, generator profile, judge profile, and JSON report path. Pressing Enter accepts the displayed default; `q` cancels without making an LLM request. The default report is `reports/<benchmark-id>.json` and entering `-` disables it.

Non-interactive `list` and `run` commands remain available for scripts and repeatable point-in-time calls.

List benchmarks:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark list
```

Run the portrait benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-portrait-intent-basic `
  --profile "OpenCode" `
  --debug
```

Run the product benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-product-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-product-intent.json" `
  --debug
```

Run independent SDXL and Pony portrait adaptations:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run sdxl-portrait-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\sdxl-portrait-intent.json"

.venv\Scripts\python.exe -m app.ai.intent_benchmark run pony-portrait-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\pony-portrait-intent.json"
```

Run the single-character benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-single-character-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-single-character-intent.json" `
  --debug
```

Run the architecture-interior benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-architecture-interior-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-architecture-interior-intent.json" `
  --debug
```

Run the landscape-environment benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-landscape-environment-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-landscape-environment-intent.json" `
  --debug
```

Run the illustration-art benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-illustration-art-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-illustration-art-intent.json" `
  --debug
```

Run the graphic-design-text benchmark:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-graphic-design-text-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-graphic-design-text-intent.json" `
  --debug
```

Use a separate judge profile later:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-product-intent-basic `
  --profile "OpenCode Generator" `
  --judge-profile "OpenCode Judge"
```

## Exit codes

```text
0 — combined result passed
1 — generation, judge host, or structured contract failure
2 — profile, path, timeout, or argument error
3 — valid run, but quality result is WARN or FAIL
```

## Interpretation

A high same-model judge score is not independent proof of quality. Read all four signals:

- deterministic score;
- judge score;
- score gap;
- missing required intents.

A large score gap or a missing requested intent direction is surfaced as a warning even when the combined score crosses the pass threshold. Future versions can replace the judge profile without changing the generator or benchmark definition.
