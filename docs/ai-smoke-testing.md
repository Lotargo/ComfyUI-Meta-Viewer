# Real-provider AI smoke testing

`app.ai.smoke` is an explicit console runner for checking prompt compilation and real OpenAI-compatible provider calls without opening the web UI.

It is intentionally separate from `unittest`:

- normal unit tests never spend provider tokens;
- a real call happens only after the user runs a named scenario;
- the runner uses the same `config.json`, profile validation, keyring/environment credentials, transport, prompt compiler, and strict result contracts as the application;
- API keys are never printed or written to reports.

Rich is used for tables, panels, status spinners, check results, and readable error output.

## Install the new dependency

After pulling the commit, refresh the virtual environment:

```powershell
.venv\Scripts\python.exe -m pip install -e .
```

For a minimal one-package update:

```powershell
.venv\Scripts\python.exe -m pip install "rich>=14.1,<15"
```

## List scenarios

```powershell
.venv\Scripts\python.exe -m app.ai.smoke list
```

Built-in scenarios:

| Scenario | Input | Purpose |
|---|---|---|
| `flux-portrait-generate` | text | Basic FLUX prompt generation and safe modifier compilation |
| `pony-portrait-generate` | text | Complete Pony score prefix, source tag, and `rating_safe` |
| `sdxl-graphic-text-generate` | text | Limited-capability warning and exact `VECTOR GARDEN` title preservation |
| `flux-graphic-text-reconstruct` | text + image | Real multimodal graphic-design reconstruction |

## Inspect configured profiles

```powershell
.venv\Scripts\python.exe -m app.ai.smoke profiles
```

The command shows profile IDs, names, models, multimodal support, credential availability, and text/vision defaults. It does not display API keys.

Use another application configuration file when needed:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke profiles --config "F:\path\config.json"
```

## Run text scenarios

Use the default text profile configured in the application:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate
```

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run pony-portrait-generate
```

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run sdxl-graphic-text-generate
```

Select a profile by exact name or ID:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run pony-portrait-generate --profile "LM Studio"
```

Override the scenario input:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate --input "Create a quiet editorial portrait in a ceramics workshop."
```

Or read it from a UTF-8 file:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate --input-file ".\prompt-test.txt"
```

## Run a multimodal scenario

The scenario requires a profile marked as multimodal and a local PNG, JPEG, WEBP, or GIF file:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-graphic-text-reconstruct --image "F:\tests\cover.png"
```

Use a specific vision profile:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-graphic-text-reconstruct --profile "Vision Provider" --image "F:\tests\cover.png"
```

The image is converted to a local base64 data URL in memory. The console and JSON report contain only its path, byte count, and SHA-256, not the base64 payload.

## Inspect the complete instruction bundle

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate --show-bundle
```

Normal output shows only the compiled section IDs, versions, and shortened hashes. `--show-bundle` prints all family, operation, scenario, modifier, and output-contract instructions.

## Save a JSON report

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run pony-portrait-generate --json-out ".\reports\pony-smoke.json"
```

The report includes:

- scenario and timestamp;
- non-secret profile metadata;
- normalized `PromptTask`;
- input text;
- image path/hash metadata when applicable;
- strict `PromptResult`;
- bundle versions and section hashes;
- latency and raw-response hash;
- individual smoke checks.

The JSON report intentionally contains the input and generated prompt. Do not publish a report containing private prompt content.

## Timeout and debugging

Override the stored timeout for one run:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate --timeout 120
```

Display normalized technical details after an error:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate --debug
```

Provider errors are redacted by the shared transport before the runner displays them.

## Exit codes

| Code | Meaning |
|---:|---|
| `0` | Provider call completed and all required checks passed; warnings are allowed |
| `1` | Prompt compilation, provider transport, or strict output-contract execution failed |
| `2` | Scenario configuration, profile, credential, image, input, or report-path error |
| `3` | The provider returned a valid `PromptResult`, but one or more scenario assertions failed |

This distinction allows scripts and later CI jobs to separate infrastructure failures from model-behavior regressions.

## Unit tests for the runner

These tests do not contact a provider:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_ai_smoke -v
```

Run the complete current AI test group:

```powershell
.venv\Scripts\python.exe -m unittest tests.test_ai_skills tests.test_prompt_compiler tests.test_ai_providers tests.test_direct_prompt_execution tests.test_ai_smoke -v
```
