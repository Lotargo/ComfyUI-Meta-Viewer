# AI Prompt Architecture

ComfyUI Meta Viewer compiles model-aware prompt instructions from one canonical registry and
then routes the prepared task to either a direct model profile or an agent host. Provider and
host adapters do not own prompt-family knowledge.

## Canonical instruction layers

The registry lives under `app/ai/prompting/content/`:

```text
profiles/<family>/base.md
operations/<operation>.md
scenarios/<scenario>.md
modifiers/<modifier>.md
output_contracts/prompt_result.md
```

`PromptCompiler` resolves a `PromptTask`, checks the selected family/scenario capability, reads
one applicable document from each layer, records versions and content hashes, and returns an
`InstructionBundle`. Compilation is deterministic and does not make an LLM request.

The base registry includes FLUX-like, SDXL, and Pony families. Scenario support is intentionally
asymmetric. `limited` combinations compile with a warning; `unsupported` combinations fail.
`multi_character` has no base scenario manifest and requires a separately tested checkpoint
capability profile.

The old `load_skill()` function remains available for compatibility. It reads the same canonical
family base and does not maintain a legacy copy.

## Contracts

`SceneSpec` is the neutral, editable artifact for image analysis. It separates observed scene
content and uncertainty from model-family syntax. `PromptResult` is the shared final contract:

```json
{
  "schema_version": "1",
  "positive_prompt": "...",
  "negative_prompt": "..."
}
```

Both contracts reject unknown fields and carry an explicit schema version. Direct and agent-host
responses use the same strict parser.

## Execution routing

`ExecutionRouter` registers adapters with an `ExecutionCapabilities` record. Routing asks adapters
whether they support a saved profile and verifies input capabilities such as file-path versus
data-URL image input. It does not grow provider-name branches.

The current adapters are:

| Adapter | Mode | Profile | Image input |
|---------|------|---------|-------------|
| `openai_compatible` | Direct | OpenAI-compatible HTTP profile | Data URL |
| `opencode` | Agent host, managed CLI | OpenCode CLI profile | Local file path |

The router compiles once, passes that exact bundle to the selected adapter, normalizes the result,
and persists the execution. Existing executor classes remain usable independently for smoke and
benchmark tools.

## Durable AI jobs

SQLite stores backend-neutral state in four tables:

| Table | Purpose |
|-------|---------|
| `ai_jobs` | Task selection, backend/profile/model, bundle metadata, status, and errors |
| `ai_scene_specs` | Current editable neutral scene analysis |
| `ai_prompt_drafts` | Append-only prompt draft history and profile versions |
| `ai_results` | Normalized final result and execution metadata |

Job transitions are checked and terminal states cannot silently become successful later. Deleting
a job cascades to its intermediate artifacts; deleting a media asset keeps the job and clears its
optional asset link.

## Native agent-host packages

`PromptSkillExporter` can generate packages for OpenCode, Claude Code, Antigravity, and Codex.
Each package contains a host-labelled `SKILL.md`, canonical references, generated JSON schemas,
a small standalone result validator, and a hash manifest. The exporter refuses to merge into a
non-empty directory.

Host packages are generated artifacts. Changes belong in the canonical prompting registry, never
in an exported reference copy.

## Verification

Compiler tests cover deterministic ordering, hashes, versions, modifiers, and asymmetric
capabilities. Contract tests cover strict `SceneSpec` and `PromptResult` parsing. Adapter and
router tests cover direct HTTP and managed OpenCode normalization, capability routing, timeouts,
malformed results, persistence, and failure state. Export tests verify that every host receives
identical reference hashes and byte-exact family bases.

Real-provider smoke calls remain explicit because free providers can be overloaded or temporarily
unavailable. See [OpenCode smoke testing](ai-opencode-smoke-testing.md) and
[AI smoke testing](ai-smoke-testing.md).
