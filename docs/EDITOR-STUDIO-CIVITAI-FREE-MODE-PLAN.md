# EDITOR / STUDIO: Civitai + Free Mode Integration Plan

> **Status:** active companion plan for the CMV editor / studio.
>
> Read this together with [`EDITOR-STUDIO-RUNTIME-PLAN.md`](EDITOR-STUDIO-RUNTIME-PLAN.md).
>
> Scope: extend the Studio Free / Agent Lab path with Civitai discovery and controlled local resource installation. Civitai cloud generation and orchestration are intentionally out of scope.

## 1. Why this is a companion plan

The main Studio runtime remains intentionally small and stable:

```text
moodyKrea2Mix_v40.safetensors
+ typed Visual Runtime
+ tested workflow primitives
+ CMV execution stack
```

Civitai must not reintroduce the old model-zoo architecture into the primary Studio path.

Instead, Civitai belongs to Free / Agent Lab, where an agent can research optional external resources, ask the user before installing them, and then experiment with those resources through local ComfyUI.

The target split is:

```text
Studio Runtime
    -> stable, typed, single-model product path

Agent Lab
    -> Civitai discovery
    -> optional external resource installation
    -> Comfy MCP experimentation
    -> result returns to VisualSession / Library
```

## 2. Current Civitai integration audit

CMV already has a substantial Civitai implementation. It should be refactored and reused rather than replaced.

### 2.1 REST discovery and model metadata

`app/comfyui/civitai_downloader.py` already uses the Civitai REST API and supports:

- model search
- model-type filters
- sorting
- page and cursor pagination
- NSFW filtering
- creator, tags, ratings, download counts, and preview images
- model details
- version enumeration
- base-model metadata
- trained words
- downloadable file metadata

The current type mapping also knows where common Civitai resources belong inside ComfyUI:

```text
Checkpoint        -> checkpoints
LORA / LoCon / DOra -> loras
TextualInversion  -> embeddings
VAE               -> vae
ControlNet        -> controlnet
Upscaler          -> upscale_models
CLIP              -> text_encoders
```

This is already a useful deterministic integration layer and should remain authoritative for exact model/version/file metadata.

### 2.2 Controlled local downloads

`CivitaiDownloaderService` already provides the important trusted write path:

```text
Civitai model/version/file
    -> validate destination folder
    -> validate filename / extension
    -> create persistent download record
    -> background download worker
    -> write into configured ComfyUI/models folder
    -> update progress/status
    -> invalidate ComfyUI runtime inventory
```

The service resolves the configured ComfyUI installation and restricts installation targets to known model folders instead of allowing arbitrary filesystem destinations.

That behavior is exactly what Agent Lab needs later. The agent should discover resources, but this CMV-controlled service should remain responsible for actually writing model files.

### 2.3 Persistent download state

The database already tracks Civitai download identity and lifecycle through `model_downloads`, including:

- Civitai model ID
- model name
- version ID
- version name
- target folder
- filename
- expected and downloaded bytes
- status
- error
- source URL
- timestamps

Existing model infrastructure also includes `model_file_hashes`, `model_recommendations`, and `model_resources`.

This persistence should be reused rather than creating an independent MCP download history.

### 2.4 Local model identification by hash

`CivitaiModelRecommendationService` already resolves a local model file, computes and caches SHA-256, asks Civitai for the matching model version, and caches the result.

It also extracts common sampling values from Civitai example metadata:

```text
steps
CFG
clip skip
sampler
scheduler
```

For the new single-model Studio these sampling recommendations are no longer central product logic, but the hash lookup itself remains valuable for external-resource identity and provenance.

A downloaded or already-installed resource can therefore be associated with its Civitai origin without relying only on its filename.

### 2.5 Existing browser UI

CMV already contains a Civitai browser in the legacy Create editor:

```text
app/static/js/features/civitai-downloader.js
app/static/css/features/civitai-downloader.css
```

It supports:

- search
- filters
- sort
- NSFW toggle
- model cards and previews
- version loading
- destination-folder selection
- download queueing
- download progress
- cancel/delete controls

The feature itself is useful, but it is currently coupled to the legacy workflow editor and `/api/editor/*` routes.

### 2.6 Current authentication behavior

The current downloader resolves a Civitai token in this order:

```text
CMV comfyui.civitai_api_token
    -> CIVITAI_TOKEN / CIVITAI_API_TOKEN
        -> Civitai CLI config
```

The fallback to environment variables and the existing Civitai CLI configuration is convenient and worth preserving.

However, storing a Civitai credential under the `comfyui` configuration namespace is an architectural coupling that should disappear during the Studio migration.

CMV already has OS-keyring infrastructure in `app/ai/secrets.py`; the Civitai integration should reuse or generalize that mechanism rather than keep secrets in ordinary application JSON.

## 3. What should be kept

The following existing pieces are valuable and should survive the migration:

- Civitai REST search and exact model/version lookup
- trained-word and file metadata extraction
- preview/image proxy support where still useful
- model-type to ComfyUI-folder mapping
- validated local download path
- background download worker
- persistent progress and error state
- cancel/delete behavior
- runtime inventory invalidation after installation
- local file SHA-256 cache
- Civitai hash lookup for installed resources
- existing database records where their schema remains sufficient
- existing browser UX patterns where they fit Agent Lab
- environment and CLI credential fallback

The goal is not to rewrite the integration. The goal is to move it out of the old editor domain and make it a first-class external-resource integration.

## 4. Current coupling to remove

Several parts are tied to architecture that the new Studio considers legacy.

### Civitai under `app/comfyui/`

Civitai is an external provider, not a ComfyUI implementation detail.

A better target structure is:

```text
app/integrations/civitai/
    __init__.py
    models.py
    credentials.py
    client.py
    downloads.py
    discovery.py
    routes.py
```

ComfyUI-specific destination resolution can remain behind a small installation adapter.

### Legacy `/api/editor/*` routes

Current Civitai browser endpoints live under the old workflow editor surface.

The new integration should expose a non-legacy namespace such as:

```text
/api/integrations/civitai/status
/api/integrations/civitai/search
/api/integrations/civitai/models/{id}
/api/integrations/civitai/downloads
```

Exact naming can follow the final public API conventions, but the integration must not remain dependent on the legacy editor blueprint.

### Credential stored under ComfyUI settings

Move Civitai configuration into an integration-specific namespace.

Non-secret settings may remain in `config.json`; secrets should use the existing system credential-store abstraction when available.

### UI bound to the old workflow editor

The old Civitai downloader dialog should not be ported unchanged into the primary Studio.

The normal Studio should not expose a general model browser at all.

Civitai browsing belongs to Agent Lab and to explicit resource-management surfaces.

## 5. Target role of Civitai in Agent Lab

Civitai becomes the external discovery and supply layer for Free Mode.

Typical user request:

```text
Find a suitable film-look LoRA on Civitai and try it on the current image.
```

Target execution:

```text
VisualSession
    -> Agent Lab instruction
        -> Civitai MCP discovery
            -> candidate resources
                -> CMV REST verification / compatibility preflight
                    -> user approval if installation is required
                        -> CMV Civitai downloader
                            -> ComfyUI inventory refresh
                                -> Comfy MCP experiment
                                    -> output asset
                                        -> VisualSession history + Library + provenance
```

The primary Studio runtime does not automatically gain a new supported model or LoRA simply because Agent Lab can experiment with it.

## 6. Civitai MCP role

Use the official Civitai MCP as a semantic discovery tool for Agent Lab.

Primary MCP use cases:

- search for models and LoRAs from natural-language intent
- inspect models, versions, creators, examples, and related metadata
- obtain context that is inconvenient to expose through a rigid UI search form
- help the agent compare candidate resources before proposing one to the user

The MCP should not become CMV's file-installation authority.

For v1:

```text
Civitai MCP = discovery / research
Civitai REST = deterministic verification and exact file metadata
CMV downloader = trusted installation path
Comfy MCP = local workflow experimentation
```

This separation keeps writes, progress, filesystem validation, and provenance inside CMV.

### Read-oriented MCP permissions first

Agent Lab should initially expose only the Civitai capabilities required for discovery and inspection.

Account-mutating operations such as posting, commenting, reacting, following, publishing, or messaging are outside the initial Studio requirement.

### No Civitai cloud generation

Civitai orchestration/cloud-generation MCP is explicitly out of scope for this architecture.

CMV execution remains local through ComfyUI.

## 7. Typed external-resource boundary

The free-form research step should converge into a typed CMV contract before any installation occurs.

Suggested models:

```python
class CivitaiResourceCandidate(StrictModel):
    provider: Literal["civitai"] = "civitai"
    model_id: int
    version_id: int
    model_name: str
    version_name: str
    resource_type: str
    filename: str | None = None
    size_bytes: int | None = None
    base_model: str | None = None
    trained_words: tuple[str, ...] = ()
    preview_url: str | None = None
    discovery_reason: str = ""


class ExternalResourceInstallRequest(StrictModel):
    candidate: CivitaiResourceCandidate
    target_folder: str
    approved_by_user: bool


class InstalledExternalResource(StrictModel):
    provider: Literal["civitai"]
    model_id: int
    version_id: int
    filename: str
    local_path: str
    content_hash: str | None = None
```

The MCP response itself is not trusted as the final installation contract.

CMV should re-resolve the chosen model/version/file through its deterministic integration before queueing the download.

## 8. Compatibility policy

The normal Studio backend remains fixed to `moodyKrea2Mix_v40.safetensors`.

Therefore Agent Lab discovery should prefer resources that can sensibly augment that environment, especially LoRAs or utilities whose architecture is compatible with the active Krea-based graph.

Compatibility decisions should be explicit and conservative:

```text
supported / verified
experimental
unknown
incompatible
```

Unknown metadata must not silently become "compatible" merely because a file can be downloaded.

Free Mode may allow the user to continue with an experimental resource, but the UI should communicate that the runtime has not verified it.

## 9. Authentication and secrets

Civitai credentials should become an integration concern rather than part of ComfyUI settings.

Recommended resolution order:

```text
1. integration-specific secret from OS keyring
2. CIVITAI_TOKEN / CIVITAI_API_TOKEN
3. detected Civitai CLI credential/config when appropriate
4. anonymous read access when supported
```

The credential contract should distinguish between:

- REST/download authorization
- MCP authorization

They may resolve to the same user-provided API key, but code should not assume they are semantically identical forever.

Never expose the raw token to Studio frontend state, VisualSession records, workflow provenance, or logs.

## 10. Installation policy

Installing an external resource mutates the user's ComfyUI environment and should remain an explicit action.

Recommended default permissions:

```text
[x] search and inspect Civitai resources
[x] use already installed external resources
[ ] install a new resource without confirmation
[ ] perform Civitai account actions
```

Agent behavior:

```text
agent finds candidate
    -> shows model/version/type/size/reason
        -> user approves installation
            -> CMV downloader queues exact file
```

The agent should never bypass the CMV downloader and write arbitrary model files directly into `ComfyUI/models` in v1.

## 11. Provenance improvements

The current download table remembers Civitai model and version IDs, but Studio experiments need durable resource provenance after the download job is no longer the interesting object.

A resource used in an Agent Lab run should be traceable to:

```text
provider = civitai
model_id
version_id
filename
content_hash
local path/resource ID
trained words if relevant
```

Prefer a dedicated origin relation rather than overloading arbitrary display metadata.

Possible table:

```text
external_resource_origins
    resource_id
    provider
    provider_model_id
    provider_version_id
    provider_file_name
    provider_url
    discovered_at
```

The final exact schema can reuse `model_resources` where appropriate, but Civitai identity should survive independently from transient download history.

A VisualAction produced through Agent Lab should record which external resources were used.

## 12. Agent Lab UX

The main Studio should stay simple.

Civitai appears only when the user enters Agent Lab / Free Mode or explicitly manages external resources.

Example conversation:

```text
User:
Find something on Civitai that gives this image a dirty 1990s VHS look.

Agent:
Found three candidates. The closest match is X, a 210 MB LoRA.
It is not part of the tested Studio runtime. Install it and try an experimental pass?

User:
Yes.

CMV:
Download -> inventory refresh -> Comfy MCP experiment -> result
```

The result remains part of the same VisualSession and is labelled as an experimental / Agent Lab action.

## 13. Relationship with Comfy MCP

Civitai MCP and Comfy MCP solve different parts of the free-mode problem.

```text
Civitai MCP
    -> what external resource could help?

CMV Civitai integration
    -> which exact file is it and may it be installed safely?

Comfy MCP
    -> how can the installed local resource be used in a one-off graph?
```

This is intentionally separate from the stable runtime path:

```text
Typed Runtime
    -> approved skills / primitives

Agent Lab
    -> Civitai research
    -> optional controlled install
    -> Comfy MCP experimentation
```

## 14. Free Mode as a capability incubator

External resources should remain experimental until validated.

A useful lifecycle is:

```text
Civitai discovery
    -> controlled installation
        -> Comfy MCP experiment
            -> successful repeated behavior
                -> preserve workflow
                    -> validate dependency set
                        -> define typed policy / skill
                            -> optionally promote to supported runtime capability
```

Promotion is deliberate. An arbitrary Civitai model must never automatically expand the official Studio compatibility surface.

## 15. Refactor target

Suggested module boundary:

```text
app/integrations/civitai/
    models.py          # Pydantic contracts
    credentials.py     # token resolution / keyring / environment / CLI fallback
    client.py          # deterministic Civitai REST operations
    downloads.py       # controlled local installation lifecycle
    provenance.py      # provider identity for installed resources
    routes.py          # non-legacy API
    mcp.py             # Agent Lab discovery adapter / configuration
```

Existing code should be moved incrementally. Avoid a rewrite that temporarily loses proven download, validation, or progress behavior.

## 16. Testing requirements

The current repository does not appear to have a dedicated Civitai-focused test module. Before Agent Lab starts depending on this integration, add focused tests for at least:

- token-resolution precedence without leaking token values
- search/result normalization
- details/version/trained-word normalization
- destination-folder validation
- filename/path traversal rejection
- download lifecycle state transitions
- cancellation
- failed download cleanup
- inventory invalidation after completion
- hash-cache reuse
- model/version/file provenance persistence
- MCP candidate -> deterministic REST verification
- installation requiring explicit approval

Network calls should be mocked in normal tests. Real Civitai/MCP smoke tests should remain explicit and opt-in.

## 17. Migration phases

### Phase 1: stabilize current integration

- add dedicated Civitai tests
- document current API behavior
- preserve existing downloader semantics
- verify inventory invalidation and download recovery

### Phase 2: extract from legacy editor

- create `app/integrations/civitai/`
- move provider-specific code behind that package
- expose non-legacy integration routes
- migrate the useful browser/download UI away from `workflow_editor.html`

### Phase 3: fix credential ownership

- remove `civitai_api_token` from the ComfyUI configuration domain
- reuse/generalize the OS keyring abstraction
- preserve environment and CLI fallback
- add separate integration status reporting

### Phase 4: add typed external-resource provenance

- add candidate/install/result Pydantic contracts
- preserve Civitai model/version/file identity after installation
- attach external resource usage to Agent Lab VisualActions

### Phase 5: add Civitai MCP to Agent Lab

- connect the official Civitai MCP for read-oriented discovery
- translate free-form discoveries into typed candidates
- verify selected resources through CMV REST before installation
- require explicit install permission

### Phase 6: connect the full free-mode loop

```text
Civitai MCP research
    -> CMV install
        -> Comfy inventory refresh
            -> Comfy MCP experiment
                -> Library asset
                    -> VisualSession history / provenance
```

### Phase 7: optional capability promotion

- preserve successful experimental workflows
- validate dependencies and reproducibility
- promote only useful, tested behavior into a normal Studio skill

## 18. Non-goals

For this plan, do not:

- add Civitai cloud generation to CMV
- integrate Civitai orchestration MCP
- turn Civitai into a model picker for normal Studio
- make downloaded checkpoints part of the official Studio runtime automatically
- let MCP write arbitrary files into ComfyUI model directories
- give Agent Lab account-mutating Civitai tools by default
- replace the existing reliable downloader merely because MCP exists
- bypass user approval for environment-changing downloads

## 19. Target architecture

```text
CMV Studio
|
+-- Typed Visual Runtime
|   +-- moodyKrea2Mix_v40
|   +-- skills
|   +-- tested primitives
|   +-- CMV execution stack
|
+-- Agent Lab / Free Mode
    |
    +-- VisualSession context
    |
    +-- Civitai MCP
    |   +-- semantic discovery
    |   +-- models / versions / examples / creators
    |
    +-- CMV Civitai Integration
    |   +-- deterministic REST verification
    |   +-- credentials
    |   +-- compatibility preflight
    |   +-- trusted downloader
    |   +-- provenance
    |
    +-- Comfy MCP
        +-- inspect installed capabilities
        +-- build arbitrary experimental graph
        +-- execute locally

All successful experimental outputs return to:

Library asset + workflow snapshot + external-resource provenance + VisualSession history
```

## 20. Definition of success

This integration is successful when a user can say something like:

```text
Find a suitable Civitai LoRA for this look and try it on the current image.
```

and CMV can safely perform:

```text
natural-language discovery
-> explain candidate
-> exact resource verification
-> explicit installation approval
-> controlled local download
-> ComfyUI inventory refresh
-> Comfy MCP experiment
-> result returned to the current VisualSession
```

without changing the primary Studio runtime, without enabling Civitai cloud generation, and without sacrificing local provenance or control over the user's ComfyUI installation.
