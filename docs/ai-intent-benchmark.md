# Prompt intent benchmark

The intent benchmark measures whether an AI can turn a short, ordinary user request into a useful model-specific image prompt without receiving a ready-made production brief.

It is separate from `quality_benchmark.py`, which measures preservation and organisation of a detailed brief.

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

The judge cannot override hard deterministic failures such as losing the core subject intent or returning a non-empty FLUX negative prompt.

Missing a requested mood direction is not a hard failure for a free model, but it caps the final status at `WARN` even when the numerical score crosses the pass threshold.

## Current benchmark

### `flux-portrait-intent-basic`

Raw user request:

```text
Сделай атмосферный портрет взрослой девушки-керамиста в её мастерской. Хочется, чтобы кадр выглядел естественно, дорого и немного уютно.
```

The request deliberately omits camera, lens, lighting, materials, environment details, composition, and depth. The generator must infer useful visual decisions while preserving the subject and mood.

Required intent dimensions are evaluated independently:

- `natural`;
- `premium_refined`, representing «дорого»;
- `cozy`.

The deterministic checks score:

- core intent preservation;
- invented camera/framing language;
- motivated lighting;
- workshop-specific details;
- tactile material language;
- subject pose, gaze, or action;
- explicit coverage of every requested intent dimension;
- non-trivial expansion through independent visual decision groups;
- coherent structure;
- FLUX empty-negative policy;
- absence of generic quality slogans.

The expansion check is language-independent at the input/output boundary. It no longer compares Russian input words against English output words. Instead it verifies concrete visual decision groups such as camera, lighting, environment, materials, subject direction, and depth/colour/medium.

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

## Commands

List benchmarks:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark list
```

Run with the same OpenCode profile as generator and judge:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-portrait-intent-basic `
  --profile "OpenCode" `
  --debug
```

Use a separate judge profile later:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-portrait-intent-basic `
  --profile "OpenCode Generator" `
  --judge-profile "OpenCode Judge"
```

Save a sanitized JSON report:

```powershell
.venv\Scripts\python.exe -m app.ai.intent_benchmark run flux-portrait-intent-basic `
  --profile "OpenCode" `
  --json-out ".\reports\flux-portrait-intent.json"
```

Both calls use the managed OpenCode five-minute timeout unless `--timeout` explicitly overrides it.

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
