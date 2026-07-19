# OpenCode real-provider smoke testing

`app.ai.opencode_smoke` runs the shared CMV prompt scenarios through a saved
OpenCode CLI profile. It is separate from `app.ai.smoke`, which uses direct
OpenAI-compatible HTTP profiles.

## What the runner exercises

The runner verifies the complete managed host path:

1. load a saved `kind=cli`, `cli_type=opencode` profile;
2. select its configured `provider/model` ID;
3. compile the canonical `PromptTask` into an `InstructionBundle`;
4. create a temporary isolated OpenCode workspace;
5. create a temporary primary agent named `cmv-prompt-smoke`;
6. deny every OpenCode tool permission for that temporary agent;
7. attach the compiled task package as `cmv-task.md`;
8. optionally attach a copied local image;
9. execute `opencode --pure run --format json`;
10. parse OpenCode JSON events;
11. validate the final assistant text through the shared `PromptResult` contract;
12. evaluate the same scenario checks used by the direct smoke runner.

The temporary workspace is removed when the process finishes. The runner does
not edit the project, read repository files through OpenCode tools, or copy API
keys from OpenCode. Provider authentication remains owned by OpenCode.

## Prerequisites

OpenCode must already be installed and authenticated:

```powershell
opencode --version
opencode auth list
```

The selected model must be visible to OpenCode:

```powershell
opencode models
```

The application must contain an OpenCode profile on the AI settings page. The
profile needs:

- kind: CLI;
- integration: OpenCode;
- exact model ID in `provider/model` form;
- multimodal enabled when image scenarios will be used;
- an executable path, or an `opencode` command available in `PATH`.

## List available scenarios

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke list
```

## List saved OpenCode profiles

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke profiles
```

This command shows profile IDs, names, model IDs, image capability, executable
selection, and text/vision default status. It does not display OpenCode
credentials.

## Run a text scenario

Use the application default text profile:

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate
```

Select a saved OpenCode profile explicitly by exact name:

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate --profile "OpenCode"
```

A profile ID can be used instead when names are duplicated.

## Run Pony validation

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run pony-portrait-generate --profile "OpenCode"
```

The built-in checks expect:

- all score tokens from `score_9` through `score_4_up`;
- one supported `source_*` tag;
- `rating_safe`;
- a strict `PromptResult` JSON object.

## Run an image reconstruction

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-graphic-text-reconstruct `
  --profile "OpenCode Vision" `
  --image "F:\tests\cover.png"
```

The selected profile must be marked as multimodal. The image is validated,
copied into the temporary isolated workspace, attached to the OpenCode message,
and removed with the workspace afterwards.

## Inspect the complete compiled bundle

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate `
  --profile "OpenCode" `
  --show-bundle
```

## Save a sanitized report

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate `
  --profile "OpenCode" `
  --json-out ".\reports\opencode-flux.json"
```

The report contains the input, normalized prompt result, bundle metadata,
section hashes, latency, host name, and checks. It does not contain an OpenCode
credential. Review input and generated prompt text before publishing a report.

## Override input or timeout

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate `
  --profile "OpenCode" `
  --input "Create a neutral studio portrait with soft window light." `
  --timeout 180
```

The timeout must be between 5 and 600 seconds.

## Debug normalized failures

```powershell
.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate `
  --profile "OpenCode" `
  --debug
```

The debug output is still sanitized by the existing CLI integration layer.

## Exit codes

- `0`: OpenCode execution and required scenario checks passed;
- `1`: compile, OpenCode host, provider, or output-contract failure;
- `2`: profile, command-line argument, config, input, or file error;
- `3`: valid `PromptResult`, but one or more scenario checks failed.

## Unit tests without a real provider call

```powershell
.venv\Scripts\python.exe -m unittest tests.test_opencode_prompt_execution -v
```

These tests mock the OpenCode process. They verify the isolated workspace,
tool-denied agent config, attached task package, JSON event parsing, profile
resolution, error categories, and smoke checks without spending provider quota.

## Comparing direct and OpenCode paths

Run the same scenario through both backends:

```powershell
.venv\Scripts\python.exe -m app.ai.smoke run flux-portrait-generate `
  --profile "Direct Provider" `
  --json-out ".\reports\direct-flux.json"

.venv\Scripts\python.exe -m app.ai.opencode_smoke run flux-portrait-generate `
  --profile "OpenCode" `
  --json-out ".\reports\opencode-flux.json"
```

The two reports share the same task, compiler, output contract, and scenario
checks. They differ only in execution ownership: direct HTTP adapter versus the
OpenCode host runtime.
