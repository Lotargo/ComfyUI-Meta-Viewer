# Simple Mode Redesign

> Product, UX, visual direction, and migration rules for the simplified generation experience in ComfyUI Meta Viewer.

## Status

Simple Mode is a **frontend and interaction-model redesign**, not a backend teardown. Existing ComfyUI runtime, workflow, model discovery, validation, execution, registry, AI, resource, and media modules remain available unless a later task explicitly replaces them.

The current Create/editor page is transitional and should be removed as a user-facing page when Simple Mode replaces it. Backend modules that become unused must be explicitly marked as legacy/inactive rather than silently left looking like live architecture.

---

## 1. Product Goal

Simple Mode is for users who do not want to understand ComfyUI.

The core promise is:

> **Write what you want to see, or show an example. The application handles the rest.**

Target path:

```text
Choose an approved model/profile
        ↓
Describe the image in normal language
        ↓
Optional automatic AI improvement
        ↓
Choose quality, aspect ratio, and batch count
        ↓
Generate
        ↓
Watch a polished progress state
        ↓
Receive the result in the existing Meta Viewer library
```

Simple Mode must hide workflow graphs, nodes, samplers, schedulers, CFG internals, CLIP/text encoders, VAE selection, dependency topology, model directories, and other ComfyUI-specific terminology.

---

## 2. Strict Scope

### Included in the first polished release

- a small curated set of personally tested generation profiles;
- a human-facing **Model** selector;
- free-form prompt input in the user's language;
- persistent `Improve with AI` toggle;
- profile-specific prompt compilation and negative prompt generation;
- aspect ratio selection;
- profile-specific quality presets;
- batch count;
- polished generation progress;
- reference-image reconstruction through Vision/AI prompt compilation;
- optional persistent AI assistant sessions for deeper prompt work;
- automatic installation and health validation for approved profiles;
- generated outputs flowing into the existing Meta Viewer library/provenance pipeline;
- full integration with the existing theme system.

### Explicitly deferred

Do not design the first release around:

- LoRA management or Civitai adapter browsing;
- arbitrary local model selection;
- arbitrary workflow import;
- ControlNet;
- IP-Adapter;
- video;
- node editing;
- advanced workflow composition;
- universal dependency resolution for arbitrary third-party graphs;
- Studio/Advanced/Comfy editor modes.

These are future layers. They must not make Simple Mode larger now.

---

## 3. Approved Profiles and the Meaning of “Model”

Internally, generation remains profile-driven. A verified profile owns a tested combination of workflow, model, encoders, VAE/component policy, required nodes, defaults, quality presets, prompt family, download sources, and health-check expectations.

In the **user interface**, however, the selector is called **Model**, not Style.

`Style` is intentionally reserved for a possible future layer of curated LoRA/style adapters such as pixel art, animation aesthetics, illustration treatments, and similar transformations. That future work is out of scope now.

The main UI should not lead with technical filenames or architecture jargon. A model may have a friendly presentation name such as:

```text
Realism
Anime
Universal
```

The exact underlying model name remains available as secondary provenance for interested users.

Only personally tested and approved profiles appear by default. A reasonable initial catalog is deliberately small: selected SDXL/Pony profiles for realism and anime plus general-purpose Flux and/or Z-Image profiles.

---

## 4. Model Discovery Cards

Model selection should be visual rather than a plain technical dropdown.

A model card may use one of the author's own generated examples as artwork and expose a rich floating detail card on hover/click.

The detail card should eventually contain manually curated information:

- what the model is especially good at;
- known weak areas;
- minimum VRAM;
- recommended/comfortable VRAM;
- a small gallery of hand-picked examples;
- the real technical model name as a quiet footer/provenance note.

Example gallery transitions should be slow, polished crossfades rather than banner-like carousels. Automatic transition pauses while the user interacts with the card.

The descriptions and example images are curated manually rather than inferred automatically.

---

## 5. Main Screen

The page should have no marketing hero copy, product slogans, Studio button, or explanatory clutter. The user already opened Create and should immediately reach creation.

Conceptually:

```text
┌─────────────────────────────────────────────────────┐
│ Meta Viewer                         Library  Create ⚙│
│                                                     │
│          ambient artwork / soft glow                │
│                                                     │
│        ╭──────────────────────────────────╮         │
│        │ What do you want to create?      │         │
│        │                                  │         │
│        │ ┌──────────────────────────────┐ │         │
│        │ │ describe any idea...         │ │         │
│        │ │                              │ │         │
│        │ │ ✦ Improve with AI       ●    │ │         │
│        │ └──────────────────────────────┘ │         │
│        │                                  │         │
│        │ Model                            │         │
│        │ [Realism] [Anime] [Universal]    │         │
│        │                                  │         │
│        │ 1:1  3:4  4:3  16:9  9:16       │         │
│        │                                  │         │
│        │ Quality              Images      │         │
│        │ Standard             4           │         │
│        │                                  │         │
│        │          [ Create ]              │         │
│        ╰──────────────────────────────────╯         │
│                                                     │
└─────────────────────────────────────────────────────┘
```

The reference is the cognitive simplicity of products such as Шедеврум, not their exact visual design. Meta Viewer must have its own identity and should feel warmer, richer, and more alive than a dry form editor.

---

## 6. Ambient Visual System

The existing background-image/glow idea should become a signature part of Simple Mode.

At launch, the page may choose a random artwork from the existing media pool. The artwork is used as an ambient layer behind active surfaces rather than as competing content.

Recommended composition:

```text
source artwork
├── large heavily blurred ambient layer
└── very faint sharper texture/detail layer
        ↓
translucent active surface
        ↓
content
```

After generation succeeds, the ambient background should smoothly crossfade from the previous artwork to the newly generated result. The page therefore visually adopts the mood of the user's creation.

Background movement may use extremely slow scale/translation to prevent the page feeling frozen, but it must remain subtle enough not to distract from the prompt or result.

---

## 7. Theme Integration

Simple Mode must use the existing theme system rather than introduce a separate fixed palette.

Separate two concepts:

```text
Theme
├── structural palette
│   ├── surfaces
│   ├── text
│   ├── borders
│   ├── controls
│   └── functional accent
│
└── ambient artwork palette
    └── decorative glow/background mood only
```

Artwork-derived colors must never silently replace functional/accessibility colors. Dark and light themes retain predictable contrast while the ambient layer provides atmosphere.

---

## 8. Custom Visual Assets

Key product controls should not automatically fall back to generic dashboard buttons.

Custom visual assets may be generated specifically for Meta Viewer using image-generation tools and later replaced with hand-picked vector assets if suitable ones are found.

Raster PNG/WebP assets are acceptable when they provide the desired identity. Full vector purity is not a requirement.

However:

- text should remain HTML/CSS, not baked into images;
- interaction/accessibility state remains real UI state;
- assets should be optimized and resolution-aware;
- decorative assets must work with the theme system;
- generic utility controls such as close, settings, basic toggles, and ordinary modal actions do not need bespoke artwork.

Custom treatment should concentrate on signature controls such as:

- model cards;
- Create/generation control;
- aspect-ratio presentation;
- quality presentation;
- reference-image upload;
- AI enhancement affordance.

The goal is a distinctive product, not a page made entirely from image slices.

---

## 9. Motion Is Part of the Design System

Animation quality is a first-class requirement, not final polish added after implementation.

All major interactions should share a coherent motion language. Avoid each component inventing unrelated timings and easing.

Suggested motion classes:

```text
micro interaction     ~120–160 ms
control transition    ~180–220 ms
panel transition      ~280–360 ms
modal transition      ~320–420 ms
ambient crossfade     ~800–1400 ms
background drift      ~15–30 s
```

Exact values can change during implementation, but consistency is mandatory.

Important motion moments include:

- model-card selection;
- floating model information card opening/closing;
- example-image crossfades;
- AI enhancement state;
- Create button hover/press;
- transition from controls to generation state;
- generation progress;
- result reveal;
- ambient background transition to the new result;
- modal and mobile-sheet transitions.

Respect reduced-motion accessibility preferences.

---

## 10. Create Button and Generation State

The Create control should be a signature object rather than a generic framework button.

It may morph into the generation progress surface instead of spawning a separate unrelated progress bar:

```text
[ Create ]
    ↓
[ Creating · 34% ███████░░░░ ]
```

When generation starts, unnecessary controls may softly fade/blur away and allow the generation state to occupy the visual center. Raw ComfyUI logs remain hidden from the normal Simple Mode path.

On success, reveal the image calmly and transition the ambient background to it. Avoid loud `DONE` states or technical completion screens.

On failure, present a human-facing repair state first and technical details only on demand.

---

## 11. AI Prompt Improvement

`Improve with AI` is a persistent toggle rather than a mandatory extra button press.

A user may write, for example:

```text
белые зайки на фоне багрового неба
```

The internal path is:

```text
raw intent
→ active verified profile
→ profile/family prompt skill
→ AI prompt compiler
→ compatible positive prompt
→ compatible negative prompt when useful
→ approved workflow
```

Language detection/translation and model-family syntax are internal concerns. The user should not need to know whether Flux prefers natural language or another profile benefits from SDXL/Pony-style formatting.

When AI enhancement is disabled, use the profile's direct/non-AI prompt path and default negative prompt where appropriate.

---

## 12. Quality Presets

Quality is profile-specific. There is no global rule such as `Standard = 20 steps`.

Semantic levels may be presented as:

```text
Fast
Standard
High
Maximum
```

Each profile maps these to its own tested values. A preset may change steps, sampler, scheduler, guidance, resolution, shift, or any other approved workflow value.

The user sees the semantic choice, not the technical mapping.

---

## 13. Generation From Description

The default happy path is intentionally tiny:

```text
Open Create
→ choose model if needed
→ write one sentence
→ optionally keep AI improvement enabled
→ choose ratio / quality / batch
→ Create
→ result
```

No technical controls are added unless repeated real-world use proves them necessary.

---

## 14. Generation From Image

The second path is reference-based reconstruction. By default it does not require a separate image-conditioned ComfyUI graph.

```text
reference image
→ Vision analysis
→ active profile/family skill
→ structured reconstruction intent
→ compatible prompt
→ same approved generation workflow
```

The UI exposes the reference image, an optional natural-language instruction, and only a very small number of high-value options such as preserving composition or removing text/UI artifacts.

Prefer structured modifiers internally instead of concatenating arbitrary prompt fragments.

---

## 15. AI Assistant Sessions

A dedicated assistant modal is available for deeper work but does not occupy the main generation surface.

It can refine prompts, continue an idea, analyze an artifact, or iterate on a reference reconstruction. Sessions are persistent and retain the active profile, reference where applicable, conversation, intermediate prompts, final prompt, and timestamps.

Users can reopen a session or start a clean `New conversation` without stale dialogue context.

---

## 16. Approved Profile Installation

Missing resources are installed as part of a trusted profile rather than through arbitrary filesystem decisions.

```text
profile dependency
→ declared resource type
→ existing resource taxonomy/path resolver
→ correct ComfyUI directory
→ download progress
→ validation
→ workflow/runtime health check
→ Ready
```

A completed download is not equivalent to a healthy profile.

Useful states:

```text
Not installed
Installing
Checking
Ready
Broken
Update available
```

Progress should be streamed to the browser, preferably over the project's WebSocket path. If a required resource disappears later, expose `Repair` rather than a raw node error as the primary UX.

---

## 17. Desktop and Mobile Are Separate Presentations

Do not require the mobile experience to be an automatic compressed rendering of the desktop page.

The two views should share state, API contracts, business logic, design tokens, and reusable primitives, while being allowed to use different composition and assets.

Conceptually:

```text
shared generation state / API / tokens
              ↓
      ┌───────┴────────┐
      ↓                ↓
DesktopCreateView   MobileCreateView
```

Desktop can emphasize a floating central surface, ambient space, model cards, and large prompt area.

Mobile can use a vertically composed prompt-first experience, horizontal model carousel, compact ratio/quality controls, and a sticky Create action.

Custom mobile assets may be authored/generated separately where desktop assets do not adapt cleanly.

This is a permitted design direction, not a requirement to duplicate all frontend logic.

---

## 18. Result Integration

Simple Mode must not create a separate isolated gallery.

Results flow into the existing Meta Viewer library and preserve available provenance such as profile/model, workflow version, quality preset, original and compiled prompts, negative prompt, AI session linkage, seed, and execution metadata.

A future Remix action should be able to restore the relevant Simple Mode state from this provenance.

---

## 19. Current Editor Migration

Do not incrementally mutate the current editor into Simple Mode.

Preferred migration:

1. build the new Simple Mode page around approved profiles;
2. route the primary Create entry to it;
3. remove the old editor page from user-facing navigation/routes when replacement is ready;
4. preserve reusable backend services and data models;
5. mark editor-specific backend modules that become unused as legacy/inactive.

> **Remove the obsolete editor experience, not reusable backend capability.**

For a fully legacy module, prefer a clear module-level marker such as:

```python
# LEGACY: Used by the pre-Simple-Mode Create editor.
# Not registered in the active Simple Mode path.
# Retained for possible future Advanced Mode/workflow tooling reuse.
```

Unused modules must not look like active dependencies. Disconnect obsolete routes/registrations, document why the code is inactive and what may reuse it later, and keep tests only where they still protect reusable behavior.

---

## 20. Backend Capabilities to Preserve

The redesign does not require deleting existing capabilities such as:

- ComfyUI runtime detection/management and API execution;
- model/resource scanning and inspection;
- resource taxonomy/path resolution;
- workflow registry, manifests, bindings, compilation, validation, and execution;
- AI provider profiles and prompt skill/compiler architecture;
- persistent AI jobs/results/sessions where applicable;
- media/library persistence and provenance.

Whether individual files are reused immediately or marked legacy is an implementation decision made during migration.

---

## 21. Acceptance Criteria

- [ ] Old editor page is no longer the primary Create experience.
- [ ] Existing reusable backend capabilities are preserved.
- [ ] Unused editor-specific backend modules are explicitly marked legacy/inactive.
- [ ] Only approved profiles/models appear by default.
- [ ] Main selector is called **Model**, not Style.
- [ ] Technical model identity remains available as secondary provenance.
- [ ] Model information cards support curated strengths, weaknesses, VRAM guidance, and examples.
- [ ] Missing approved profiles can be installed without choosing filesystem paths manually.
- [ ] Installation exposes progress and validates health before reporting Ready.
- [ ] Short natural-language prompts work without technical prompt knowledge.
- [ ] AI improvement can remain enabled persistently.
- [ ] Negative prompt handling is automatic where appropriate.
- [ ] Quality presets are profile-specific.
- [ ] Aspect ratio and batch count are available without exposing workflow internals.
- [ ] Reference reconstruction works through Vision/AI prompt compilation.
- [ ] AI assistant conversations can be resumed or restarted cleanly.
- [ ] Generated results enter the existing library with provenance.
- [ ] Existing themes are respected.
- [ ] Ambient artwork/glow remains decorative and does not compromise functional contrast.
- [ ] Motion behavior follows a coherent design system and respects reduced-motion preferences.
- [ ] Signature controls may use custom raster/vector assets without baking UI text into them.
- [ ] Desktop and mobile may use dedicated layouts while sharing application logic.
- [ ] Raw ComfyUI errors are not the default user-facing failure state.

---

## 22. Non-Goal Reminder

Simple Mode is not another complete ComfyUI frontend and is not a Civitai/SeaArt clone.

Its value is the combination of:

```text
very small cognitive surface
+ personally verified generation profiles
+ invisible AI assistance
+ high-quality motion
+ ambient artwork
+ distinctive visual assets
+ existing Meta Viewer library/provenance
```

If a proposed feature requires the beginner to understand graphs, node compatibility, adapter ecosystems, arbitrary architecture differences, or dependency topology, it belongs outside the first Simple Mode release.