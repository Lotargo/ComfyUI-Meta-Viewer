# Simple Mode Redesign

> Target UX and migration rules for the simplified generation experience in ComfyUI Meta Viewer.

## Status

This document defines the current product direction for the **Simple Mode** generation UI.

The change is primarily a **frontend and interaction-model redesign**. It is **not** a backend teardown.
Existing ComfyUI runtime, workflow, model discovery, validation, execution, registry, AI, and resource modules remain available unless a later implementation task explicitly replaces them.

The current Create/editor page is considered a transitional implementation and should be removed as a user-facing page when the new Simple Mode replaces it.

---

## 1. Product Goal

Simple Mode is for users who do not want to understand ComfyUI.

The intended interaction is:

```text
Choose a verified creation profile
        ↓
Describe the desired image in normal language
        ↓
Optionally let AI improve the request
        ↓
Choose quality and batch count
        ↓
Generate
        ↓
Watch progress
        ↓
Receive results in the existing Meta Viewer library
```

The user should not need to know about:

- workflow graphs;
- nodes;
- samplers;
- schedulers;
- CFG internals;
- CLIP or text encoders;
- VAE selection;
- model folder structure;
- dependency graphs;
- ComfyUI-specific terminology.

The guiding product rule is:

> **Write what you want to see, or show an example. The application handles the rest.**

---

## 2. Scope Boundary

Simple Mode is intentionally small.

### Included

- a small set of personally tested and approved generation profiles;
- a human-readable model/style selector;
- free-form prompt input in the user's language;
- optional AI prompt improvement;
- automatic profile-specific prompt formatting;
- automatic negative prompt generation where the profile benefits from it;
- predefined quality presets per profile;
- batch count selection;
- generation progress and completion state;
- image-reference reconstruction through the AI/Vision layer;
- persistent AI conversation sessions for prompt work and reconstruction refinement;
- automatic profile installation and health validation for approved profiles;
- output import into the existing Meta Viewer media/library pipeline.

### Explicitly deferred

The following are not part of the first polished Simple Mode release:

- LoRA management;
- Civitai adapter browsing and installation;
- arbitrary local model selection;
- arbitrary workflow import;
- ControlNet;
- IP-Adapter;
- video workflows;
- node editing;
- advanced workflow composition;
- universal dependency resolution for arbitrary third-party graphs.

These may be introduced later in other modes or as optional extensions, but they must not shape the first Simple Mode implementation.

---

## 3. Verified Profiles Instead of Arbitrary Models

Simple Mode does not treat every detected model file as directly runnable.

The primary selectable object is a **verified generation profile**.

A profile represents a tested combination of:

- workflow;
- primary model;
- required encoders;
- VAE or embedded component policy;
- required ComfyUI nodes;
- tested default parameters;
- quality presets;
- supported prompt syntax/family;
- download sources;
- health-check expectations.

Example conceptual profile:

```text
Flux Krea — Universal
├── workflow: approved Flux workflow
├── model: tested Flux Krea model
├── encoder(s): fixed verified set
├── VAE: fixed verified set
├── default preset: Standard
├── quality presets:
│   ├── Fast
│   ├── Standard
│   ├── High
│   └── Maximum
└── prompt family: Flux
```

The first set should stay deliberately small. A reasonable initial catalog is approximately:

- one or two realistic SDXL/Pony profiles;
- one or two anime-oriented SDXL/Pony profiles;
- one general-purpose Flux profile;
- one general-purpose Z-Image profile if it remains useful and stable.

Only profiles that have been manually tested and approved should appear by default.

A future expert setting may allow unverified models, but that is not part of the core Simple Mode path.

---

## 4. Human-Facing Profile Selection

The UI should not force a beginner to choose between architecture names such as `SDXL`, `Pony`, `Flux`, or `Z-Image` without context.

The primary labels should describe intent, for example:

```text
Realism
Anime / Illustration
Universal
```

The underlying engine/model family may be shown as secondary information for advanced users.

Example:

```text
Realism
Photographic scenes, people, objects
Powered by SDXL
```

The goal is to make profile selection understandable to a child, elderly user, or first-time image-generation user without hiding provenance from users who care about it.

---

## 5. Main Simple Generation Screen

The main screen should contain only the controls needed for the shortest successful path.

Conceptual layout:

```text
┌─────────────────────────────────────────────┐
│ Create                                      │
├─────────────────────────────────────────────┤
│                                             │
│ [ From description ] [ From image ]         │
│                                             │
│ Style / Profile                             │
│ [ Universal ▼ ]                             │
│                                             │
│ What do you want to create?                 │
│ ┌─────────────────────────────────────────┐ │
│ │ white rabbits under a crimson sky      │ │
│ └─────────────────────────────────────────┘ │
│                                             │
│ ☑ Improve my request with AI                │
│                                             │
│ Quality                                     │
│ [ Fast ] [ Standard ] [ High ] [ Maximum ] │
│                                             │
│ Images                                      │
│ [ 1 ] [ 2 ] [ 4 ]                          │
│                                             │
│                     [ Create ]              │
└─────────────────────────────────────────────┘
```

The interface should feel closer to a consumer creative tool such as Shедеврум than to Civitai/SeaArt-style technical editors.

The design should be original and adapted to Meta Viewer rather than copying an existing generation service one-to-one.

---

## 6. AI Prompt Improvement

Prompt improvement should be a persistent mode toggle rather than a required extra action.

Example:

```text
☑ Improve my request with AI
```

When enabled, the user may write naturally in any supported language:

```text
белые зайки на фоне багрового неба
```

The system then performs:

```text
raw user intent
    ↓
active verified profile
    ↓
profile/family prompt skill
    ↓
AI prompt compiler
    ↓
profile-compatible positive prompt
    ↓
profile-compatible negative prompt when needed
    ↓
workflow execution
```

The user does not need to translate the request manually or know the prompt syntax expected by the active model family.

If AI improvement is disabled:

- the user's prompt is passed according to the profile's non-AI path;
- a profile-defined default negative prompt may be used where appropriate;
- technical prompt details remain hidden from Simple Mode.

---

## 7. Quality Presets

Quality is profile-specific.

There must not be one global rule such as `Standard = 20 steps` for every model family.

Each verified profile owns its own tested presets:

```text
Fast
Standard
High
Maximum
```

A preset may change any number of internal workflow values, including:

- steps;
- sampler;
- scheduler;
- guidance/CFG;
- resolution;
- shift or model-specific controls;
- multi-stage behavior if the approved workflow needs it.

Simple Mode exposes only the semantic quality level.

The exact parameter mapping is an implementation detail of the profile.

---

## 8. Mode A — Generation From Description

This is the default path.

Required controls:

- profile/style;
- prompt;
- AI improvement toggle;
- quality;
- batch count;
- Create button.

No additional technical controls should be added unless repeated real-world use proves they are necessary.

The target happy path is:

```text
Open Create
↓
Write one sentence
↓
Create
↓
Get an image
```

---

## 9. Mode B — Generation From Image

The second Simple Mode path is reference-based reconstruction.

This is **not** a new image-conditioned ComfyUI workflow by default.

The reference image is sent to the configured Vision/AI layer, which analyzes it and compiles a prompt for the currently active verified profile.

```text
reference image
      ↓
Vision analysis
      ↓
active profile / model-family skill
      ↓
reconstruction instructions
      ↓
profile-compatible prompt
      ↓
same approved generation workflow
```

The UI should remain simple.

Conceptual screen:

```text
Drop an image

[ reference preview ]

What should be changed?
[ optional natural-language instruction ]

☑ Preserve composition
☑ Remove text and UI elements

[ Create ]
```

Only a small number of high-value toggles should be exposed.

Other behavior should be expressed through natural language or internal modifiers rather than a large technical form.

---

## 10. Reconstruction Modifiers

Reference reconstruction should reuse the existing skill-oriented AI architecture.

The implementation should prefer structured intent/modifiers over concatenating arbitrary prompt fragments.

Conceptual internal request:

```json
{
  "operation": "reconstruct",
  "similarity": "high",
  "preserve_composition": true,
  "remove_ui": true,
  "preserve_text": false,
  "preserve_tattoos": false
}
```

The compiler can combine:

```text
base family skill
+ reconstruction skill
+ active profile rules
+ selected modifiers
+ user instruction
```

This keeps reconstruction deterministic at the orchestration level while still using an AI/Vision model for visual interpretation.

---

## 11. AI Assistant Sessions

Simple Mode should support a dedicated AI assistant modal without forcing chat interaction into the primary generation path.

The modal can be opened when the user wants to:

- improve a prompt interactively;
- refine a reconstruction;
- report an artifact and ask for a corrected prompt;
- continue developing the same visual idea;
- ask the agent to create another variation in the same style.

The assistant must operate as a persistent conversation session rather than isolated one-shot requests.

A session should retain enough context to restore the work later, including conceptually:

```text
session id
active profile
model/prompt family
reference image when applicable
conversation messages
intermediate prompts
active/final prompt
created/updated timestamps
```

The user should be able to:

- reopen a previous session;
- continue it;
- use a generated prompt;
- create a completely new conversation without inheriting stale dialogue context.

A clear `New conversation` action is required.

Conversation history should integrate with the existing journal/persistence approach rather than exist only in browser memory.

---

## 12. Profile Installation

Approved profiles may depend on model files that are not installed on first launch.

The user experience should be profile-oriented, not file-system-oriented.

Example:

```text
Flux Krea

Required files:
✓ VAE
✗ Diffusion model
✗ Text encoder

[ Install ]
```

The profile owns the trusted download metadata and expected resource type/destination.

The application should never infer the destination directory only from a Hugging Face or other download URL.

Instead:

```text
profile dependency
      ↓
resource type
      ↓
existing resource taxonomy/path resolver
      ↓
correct ComfyUI model directory
```

Download progress should be streamed to the browser, preferably through the existing/new WebSocket progress channel.

Example:

```text
Downloading Flux Krea
██████████████░░░░ 67%
```

After download, the profile must pass a health/preflight stage before it becomes available for generation.

```text
download complete
      ↓
file/resource validation
      ↓
required node validation
      ↓
workflow validation
      ↓
ComfyUI/runtime health check
      ↓
Ready
```

A completed download is not equivalent to a healthy profile.

Suggested visible profile states:

```text
Not installed
Installing
Checking
Ready
Broken
Update available
```

If a user later removes a required file manually, Simple Mode should report a repairable profile state rather than exposing a raw ComfyUI node error as the primary message.

---

## 13. Generation Progress

After generation starts, the UI should become calm and minimal.

The user should primarily see:

- generation animation or preview;
- progress percentage where available;
- current batch position;
- active profile;
- selected quality level.

Example:

```text
Creating…

Flux Krea · High
██████████████░░░░ 72%
Image 3 / 4
```

Raw technical logs should not be part of the normal Simple Mode experience.

On failure:

```text
Generation stopped
The selected profile needs attention.

[ Repair ] [ Details ]
```

`Details` may expose technical diagnostics for experienced users.

---

## 14. Result Integration

Simple Mode must not create a separate isolated gallery subsystem.

Generated assets should flow directly into the existing Meta Viewer library and provenance model.

A generated result should preserve, where available:

- profile ID and version;
- workflow version;
- model/resource identifiers;
- selected quality preset;
- original user prompt;
- compiled prompt;
- negative prompt if generated;
- AI session linkage where relevant;
- seed and execution metadata;
- generation timestamp.

This allows later inspection and Remix/reuse without duplicating media-management logic.

---

## 15. Current Editor Migration

The current Create/workflow editor page should not be incrementally expanded into the new Simple Mode.

The preferred migration is:

1. build the new Simple Mode page around verified profiles;
2. route the primary Create entry point to Simple Mode;
3. remove the current editor page from the user-facing navigation and routes when replacement is ready;
4. preserve useful backend services and data models;
5. mark editor-specific backend modules that are no longer used as legacy rather than silently leaving them as apparently active architecture.

The key distinction is:

> **Remove the obsolete editor experience, not the backend capabilities that may be reused later.**

---

## 16. Legacy Backend Policy

Existing backend modules are not a problem simply because the new Simple Mode uses only part of them.

They should not be deleted merely to make the first redesign smaller.

However, an unused module must not look like an active architectural dependency.

For editor-specific backend code that becomes unused after the page migration:

- disconnect it from active routes/registrations where appropriate;
- add a clear legacy/deprecated module-level marker or comment;
- document what previously used it;
- document why it is currently inactive;
- document what future mode could reuse it;
- avoid importing/registering it in the active Simple Mode path;
- keep tests only where they still protect reusable backend behavior;
- remove or archive tests that assert obsolete editor UX contracts.

Suggested marker style:

```python
# LEGACY: Used by the pre-Simple-Mode Create editor.
# Not registered in the active Simple Mode path.
# Retained for possible future Advanced Mode/workflow tooling reuse.
```

Where a whole module is legacy, prefer a module-level docstring/marker rather than scattering comments across every function.

The purpose is to prevent a future developer or agent from seeing a module and incorrectly assuming:

```text
module exists
→ therefore it is active
→ therefore another missing caller/route is an architectural bug
```

Instead the intended state must be explicit:

```text
module exists
→ intentionally inactive legacy capability
→ not part of current Simple Mode architecture
```

This keeps the codebase understandable without destroying useful work.

---

## 17. Backend Components That Should Remain Available

The redesign should preserve reusable backend capabilities such as:

- ComfyUI runtime detection and management;
- ComfyUI API client/execution;
- model/resource scanning;
- model inspection;
- resource taxonomy/path resolution;
- workflow registry;
- workflow manifest models;
- workflow compilation/bindings;
- workflow validation/preflight;
- workflow execution and output import;
- AI provider profiles;
- prompt skill/compiler architecture;
- persistent AI jobs/results/sessions where applicable;
- media/library persistence and provenance.

Whether each existing file is reused directly or adapted later is an implementation decision. The redesign does not require deleting these subsystems.

---

## 18. Deferred Future Modes

Advanced Mode and native ComfyUI/editor integration remain valid future directions, but they are intentionally deferred.

They must not block or expand the Simple Mode scope.

The project should first make this path extremely reliable:

```text
select profile
→ describe/show idea
→ optional AI help
→ select quality/batch
→ generate
→ result
```

Only after Simple Mode is stable and polished should additional generation modes be designed or implemented.

---

## 19. Acceptance Criteria

Simple Mode is successful when a first-time user can generate without understanding ComfyUI.

Minimum acceptance criteria:

- [ ] The old editor page is no longer the primary Create experience.
- [ ] Only approved profiles are shown by default.
- [ ] A user can install a missing approved profile without manually choosing filesystem paths.
- [ ] Profile installation reports download progress.
- [ ] Profile installation performs post-download validation before reporting `Ready`.
- [ ] A user can generate from a short natural-language request.
- [ ] AI prompt improvement can be enabled as a persistent option.
- [ ] AI improvement follows the active profile's prompt family/syntax.
- [ ] Negative prompt generation is automatic where required by the profile.
- [ ] Quality presets are profile-specific.
- [ ] Batch count is available without exposing technical workflow settings.
- [ ] Image-reference reconstruction works through Vision/AI prompt compilation.
- [ ] AI assistant conversations can be resumed later.
- [ ] A user can start a clean new AI conversation at any time.
- [ ] Generated results enter the existing Meta Viewer library with provenance.
- [ ] Raw ComfyUI errors are not the default failure UX.
- [ ] Editor-specific backend modules that become unused are explicitly marked as legacy/inactive.
- [ ] Reusable backend capabilities are preserved rather than deleted as part of the UI redesign.

---

## 20. Non-Goal Reminder

Simple Mode is not intended to become another complete ComfyUI frontend.

Its job is to provide a deliberately curated, low-friction creation surface backed by tested workflows and profiles.

If a proposed feature requires users to understand the graph, dependency topology, node compatibility, adapter ecosystem, or arbitrary model architecture, it probably belongs outside Simple Mode.
