# EDITOR / STUDIO: Visual Runtime Plan

> **Status:** active architecture plan for the CMV editor / studio.
>
> This document describes the direction that should replace the current Simple Mode, model zoo, and the old editor concepts. If implementation work concerns Create, Editor, Studio, visual sessions, image editing, reference composition, typography, or Comfy MCP, start here.

## 1. Product direction

CMV should stop growing as a universal front end for many unrelated image models.

The new Studio should be built around one tested visual backend:

```text
moodyKrea2Mix_v40.safetensors
```

The goal is not to expose model choice to the user. The goal is to expose visual intent:

- create a scene
- compose several references into a scene
- edit the current scene
- add or replace a character
- change pose, clothing, lighting, or environment
- relocate a character to another place
- create typography, poster, cover, or flyer treatment
- continue editing the result as a persistent visual session

The old concepts based on `Simple Mode`, multiple bundled models, FLUX / SDXL / Pony family selection, model cards, and separate editor modes are considered legacy candidates and should not shape the new Studio architecture.

## 2. Core UX principle

The user should describe what they want to happen to the scene instead of selecting a technical workflow.

Example requests:

```text
I uploaded a photo of my room, myself, and my girlfriend separately.
Make us lie on the bed together and read books.
```

```text
Add a generated girl next to me and match the lighting and perspective.
```

```text
Keep the character but move the scene from the current location to France.
```

```text
Turn this image into a fashion poster and add the title Midnight Heat.
```

The Studio resolves these requests into typed operations and executes the appropriate tested ComfyUI primitive.

## 3. Single-model principle

For Studio v1, `moodyKrea2Mix_v40.safetensors` is the only primary image model.

Reasons:

- it already works quickly on the current target hardware
- it behaves well on an 8 GB Turing-class mobile GPU with 32 GB system RAM
- it covers generation, image editing, reference-based composition, and typography well enough for the product scope
- it avoids repeated model unload/load hops
- it gives the runtime one predictable behavior profile
- it removes the need to maintain a broad compatibility matrix for unrelated model families

Other models such as SDXL, Pony, Flux variants, Ideogram, ERNIE, H3, and similar systems are out of scope for the primary Studio runtime.

This is a product constraint, not a claim that other models are worse in general.

## 4. VisualSession is the primary domain object

The new Studio should revolve around a persistent scene/session rather than a one-shot generation request.

Suggested contract:

```python
class ReferenceRole(str, Enum):
    CHARACTER = "character"
    ENVIRONMENT = "environment"
    STYLE = "style"
    TYPOGRAPHY = "typography"


class VisualReference(StrictModel):
    asset_id: int
    role: ReferenceRole
    label: str | None = None


class VisualSession(StrictModel):
    id: str
    original_asset_id: int | None = None
    current_asset_id: int | None = None
    references: tuple[VisualReference, ...] = ()
    instruction: str = ""
```

`original_asset_id` and `current_asset_id` must remain separate.

The original image is the stable anchor. The current image is the latest working state.

This allows a sequence such as:

```text
original
  -> change background
  -> change pose
  -> change clothes
  -> add typography
  -> final image
```

without losing the original source or the reference set.

## 5. Visual operations

The user does not need to select these manually. They are internal runtime intents.

Initial operation set:

```text
generate_scene
compose_scene
edit_scene
add_character
replace_character
change_pose
change_wardrobe
relocate
replace_background
adjust_lighting
typography
posterize
finalize
```

Several operations may share the same physical ComfyUI workflow.

For example `change_pose`, `replace_background`, `change_wardrobe`, `relocate`, and `add_character` can all be policies over one tested Krea edit primitive.

## 6. Separate scene state from workflow state

Do not overload `workflow_drafts` or `workflow_runs` with Studio semantics.

The layers should remain separate:

```text
VisualSession
    -> VisualAction
        -> ExecutionPlan
            -> WorkflowDraft
                -> WorkflowRun
                    -> Output Asset
                        -> VisualSession.current_asset_id
```

`VisualSession` answers:

> What visual scene is the user working on?

`WorkflowDraft` and `WorkflowRun` answer:

> What exactly was sent to ComfyUI and what happened during execution?

Suggested SQLite additions:

```text
visual_sessions
visual_references
visual_actions
```

`visual_actions` should preferably be append-only so that history, undo, comparison, provenance, and later branching are natural consequences of the data model.

## 7. Pydantic as runtime IR

Pydantic models should describe visual intent and execution policy, not raw ComfyUI graphs.

Example:

```python
class EditPolicy(StrictModel):
    preserve_identity: bool = True
    preserve_pose: bool = False
    preserve_environment: bool = False
    reference_strength: float
    grounding_resolution: int
    protected_regions: tuple[str, ...] = ()
```

The agent or skill layer converts natural language into typed runtime contracts.

The workflow layer then maps those contracts into actual ComfyUI node inputs.

This keeps the business logic independent from node IDs and graph details.

## 8. Skills architecture

A skill is a visual policy, not a workflow file.

Example skills:

```text
generate_scene
compose_scene
edit_scene
identity_preservation
add_character
relocate
wardrobe_edit
pose_edit
typography_layout
posterize
finalize
```

A skill should know:

- what needs to stay fixed
- what can change
- which references matter
- how strongly to preserve the source
- whether identity protection is required
- how to structure the prompt for `moodyKrea2Mix_v40`
- which tested workflow primitive should execute the request

The existing prompt compiler concept can be reused, but the FLUX / SDXL / Pony family matrix should not define the new Studio runtime.

A future structure can look like:

```text
visual_runtime/skills/
    base/moody_krea2.md
    operations/generate_scene.md
    operations/compose_scene.md
    operations/edit_scene.md
    operations/add_character.md
    operations/relocate.md
    operations/typography.md
    policies/identity_lock.md
    policies/multi_character.md
    policies/environment_lock.md
    policies/text_layout.md
```

## 9. Workflow primitives

The new runtime should use a small number of tested workflow primitives instead of a universal workflow zoo.

Initial target:

```text
moody-generate
moody-edit
```

Potentially typography can remain a policy over `moody-edit` rather than a separate graph.

The existing CMV `WorkflowTemplateRegistry`, `WorkflowCompiler`, dependency validation, execution service, run store, output import, and provenance infrastructure should be reused where useful.

The old model-oriented registries and bundled model catalog should not be carried into the new product domain merely for compatibility.

## 10. Studio UI

The main `/create` page should become the Studio.

Primary layout:

```text
References
[ room ] [ character A ] [ character B ] [ + add ]

                CURRENT IMAGE

What should happen?
[ natural-language instruction                       ]
                                                  [ Run ]

History
- generated base scene
- changed pose
- relocated scene
- added typography
```

The model picker should disappear from the main Studio UI.

The user should not need to choose between Generate, Edit, Reference, Typography, or Poster modes. The runtime resolves the operation from the instruction and current session state.

Advanced technical controls may remain in a secondary drawer for debugging and expert use:

```text
seed
resolution
reference strength
grounding
LoRA
other calibrated runtime parameters
```

## 11. Frontend migration

Do not keep expanding the current large Simple Mode controller.

Replace the current monolithic Create frontend with focused modules, for example:

```text
features/runtime/
    session.js
    references.js
    composer.js
    canvas.js
    history.js
    execution.js
    assistant.js
```

Browser storage should not be the source of truth for Studio state.

It may store only convenience data such as:

```text
last_open_session_id
```

The actual session, references, current asset, history, and execution state belong in SQLite.

## 12. Library and Viewer integration

Viewer and Library remain core parts of CMV.

Any image in the Library should be able to become the starting point of a new Studio session:

```text
Open asset -> Continue in Studio
```

This replaces the need for a separate Remix product concept.

The resulting image returns to the Library with full workflow provenance and VisualSession lineage.

## 13. Comfy MCP role

Comfy MCP is important, but it should not replace the typed runtime execution path.

Use two execution concepts:

### Runtime path

For capabilities officially supported by CMV:

```text
user intent
    -> Pydantic contract
        -> skill
            -> ExecutionPlan
                -> tested workflow primitive
                    -> CMV WorkflowCompiler / ExecutionService
                        -> ComfyUI
```

This is the deterministic product path.

### Free / Agent Lab path

For tasks outside the registered Studio runtime:

```text
VisualSession context
    -> free-form instruction
        -> agent
            -> Comfy MCP
                -> inspect local models and custom nodes
                -> build or modify arbitrary workflow
                -> execute experimental graph
                -> import outputs back into CMV
```

Comfy MCP therefore acts as an escape hatch and control plane for capabilities the typed runtime does not yet support.

It is especially useful for:

- discovering available custom nodes
- inspecting local ComfyUI capabilities
- prototyping new workflows
- debugging graph behavior
- trying one-off operations
- building new runtime primitives without adding them to product code first

The standard CMV direct ComfyUI client should remain the execution plane for stable production operations.

## 14. Free Mode / Agent Lab

The Free Mode should not be another old-style editor.

It should be the same Studio session with runtime restrictions relaxed.

Suggested contract:

```python
class FreeModeRequest(StrictModel):
    session_id: str
    instruction: str
    input_asset_ids: tuple[int, ...] = ()
    allow_install_nodes: bool = False
    allow_download_models: bool = False
```

The internals of the arbitrary Comfy graph do not need to fit the normal runtime IR.

Only the boundary needs to remain typed and auditable.

Every Free Mode run should still return:

- workflow snapshot
- output asset IDs
- execution metadata
- session history entry
- provenance

Suggested execution origin field:

```text
runtime
mcp_free
```

## 15. Permissions for Comfy MCP

Free Mode should default to using only what is already installed.

Recommended permission split:

```text
[x] use installed models
[x] use installed nodes
[ ] install new custom nodes
[ ] download new models
```

Changes to the local ComfyUI installation should require explicit permission.

This keeps Free Mode powerful without turning arbitrary agent experiments into silent environment mutation.

## 16. Free Mode as capability incubator

A successful MCP experiment can later become a supported Studio operation.

Lifecycle:

```text
free experiment
    -> working workflow
        -> validate behavior
            -> save workflow primitive
                -> define Pydantic contract
                    -> add skill
                        -> supported runtime capability
```

This gives CMV a clean evolution path:

```text
MCP = research / exploration
Runtime = tested product capability
```

## 17. What remains from the current project

Keep and reuse where possible:

- Viewer
- Library
- metadata extraction
- source monitoring
- SQLite
- ComfyUI detection and process management
- `ComfyUIClient`
- workflow execution and polling
- `WorkflowStore`
- output import
- workflow provenance
- Pydantic / `StrictModel`
- AI provider adapters
- local CLI / agent-host adapters
- skill export infrastructure where useful
- workflow registry/compiler internals that remain valuable for tested primitives

## 18. Legacy candidates

The following concepts should not define the new Studio and are candidates for deletion after migration:

- Simple Mode as a product concept
- bundled model zoo and `model_01...model_08`
- model selector in Create
- FLUX / SDXL / Pony selection as the primary prompt/runtime abstraction
- Simple profiles and per-model quality catalog
- old Create controller built around `modelId`, one reference, quality presets, and model health cards
- old Advanced Workflow Editor as a user-facing primary editor
- separate Remix workflow
- universal template zoo that exists only to support unrelated model ecosystems

Legacy code may remain temporarily for migration, debugging, or compatibility, but new Studio work should not extend it.

## 19. Migration order

1. Fix `moodyKrea2Mix_v40.safetensors` as the sole Studio v1 visual backend.
2. Add `app/visual_runtime/` with typed session, reference, action, and execution-plan contracts.
3. Add `visual_sessions`, `visual_references`, and `visual_actions` persistence.
4. Register and validate `moody-generate` and `moody-edit` workflow primitives.
5. Add Studio API endpoints around VisualSession instead of Simple Mode model profiles.
6. Replace `/create` with references + current canvas + instruction + history.
7. Move prompt logic to single-model visual skills and policies.
8. Connect agent orchestration to typed `ExecutionPlan` results.
9. Add Comfy MCP as the Free / Agent Lab control plane.
10. Import MCP-generated outputs back into VisualSession and Library provenance.
11. Remove the model zoo and Simple Mode implementation after the new path is stable end to end.
12. Keep the legacy editor only as a temporary engineering/debug tool, then reevaluate whether it is still useful.

## 20. Target architecture

```text
CMV
|
+-- Viewer
|
+-- Library
|
+-- Studio / Create
    |
    +-- VisualSession
    |   +-- references
    |   +-- current image
    |   +-- history
    |   +-- provenance
    |
    +-- Typed Visual Runtime
    |   +-- Pydantic IR
    |   +-- Skills
    |   +-- Moody workflow primitives
    |   +-- WorkflowCompiler
    |   +-- WorkflowExecutionService
    |   +-- ComfyUIClient
    |
    +-- Agent Lab / Free Mode
        +-- VisualSession context
        +-- Comfy MCP
        +-- arbitrary local nodes/workflows
        +-- experimental execution

All successful paths converge back into:

Library asset + workflow provenance + VisualSession history
```

## 21. Definition of success for Studio v1

The architecture is successful when the user can work naturally with scenes rather than workflows.

A complete Studio v1 should support at least these end-to-end stories:

```text
room reference + two character references + instruction
-> compose a new scene
```

```text
current image + instruction
-> edit the current scene while preserving required identities
```

```text
current image + instruction
-> relocate the character into a different environment
```

```text
current image + title/subtitle + instruction
-> create poster / typography treatment
```

```text
unsupported unusual request
-> open Free / Agent Lab
-> agent uses Comfy MCP
-> result returns to the same VisualSession
```

The user should not need to understand model families, node graphs, loader types, workflow categories, or ComfyUI internals to perform these operations.
