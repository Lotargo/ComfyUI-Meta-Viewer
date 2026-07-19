# Prompt Engineering Research Notes

**Research date:** 2026-07-19  
**Last verification:** 2026-07-19  
**Scope:** Flux-like, SDXL, and Pony prompt profiles for task 06  
**Method:** official documentation and model cards first; current library documentation and author-provided model guidance second; community claims are treated as heuristics unless independently verified.

This document records the evidence used to design the prompt skills. It deliberately separates:

- documented model behavior;
- model-author recommendations;
- project heuristics that still require practical comparison tests.

A statement should not be promoted from a heuristic to a model rule only because it appears frequently in community prompt templates.

---

## 1. Flux-like profile

### 1.1 FLUX family: documented behavior

Black Forest Labs currently recommends clear natural-language descriptions. Its documentation says that there is no single mandatory prompt format and presents `Subject + Action + Style + Context` as a useful starting structure rather than a strict formula.

Confirmed findings:

- Natural language is the primary syntax for FLUX.
- The prompt should state what is visible, how elements relate to one another, and the intended visual direction.
- Subject, action, framing, lighting, style, and environment should be concrete rather than represented by generic quality words.
- Camera, lens, film stock, light direction, light quality, and material descriptions are valid steering vocabulary.
- Exact text intended to appear in an image should be placed in quotation marks.
- FLUX models do not support a separate negative prompt. Unwanted content should be replaced with a positive visual alternative.
- Front-loading important content is supported as a practical word-order strategy, but the documentation does not establish a universal numeric rule such as “the first 10–15 words receive maximum attention.”

Short source excerpts:

> “There is no single correct format.”

> “FLUX models don’t support negative prompts.”

### 1.2 Prompt length

No official BFL source found in this research establishes a universal 40–80-word optimum or a hard degradation point at 100 or 200 words.

Project heuristic:

- Start with roughly 40–100 words for ordinary single-scene generation.
- Prefer one coherent scene over an exhaustive inventory.
- Expand only when the scene genuinely needs more relations, characters, text, or layout constraints.
- Treat length as a practical budget, not a model guarantee.

### 1.3 Chroma

The original Chroma model is based on FLUX.1-schnell. The current Chroma1-HD model card describes it as an 8.9B foundational text-to-image model based on FLUX.1-schnell.

Implication:

- FLUX-style natural-language prompting is a reasonable baseline for Chroma.
- This architectural relationship does not prove that every FLUX prompting rule transfers unchanged to every Chroma checkpoint or finetune.
- Chroma-specific behavior should be validated on the exact checkpoint used by the application.

### 1.4 Z-Image is not identical to FLUX

Z-Image belongs in the broad natural-language profile for UI convenience, but it is a separate model family and must not inherit all FLUX runtime rules.

The official Z-Image repository states:

- Z-Image is a separate 6B single-stream diffusion-transformer family.
- The full Z-Image model supports classifier-free guidance.
- Negative prompts are strongly recommended for better control in the full model.
- Z-Image-Turbo uses guidance scale `0.0`; its runtime behavior therefore differs from the full model.

Consequences for the skill:

- FLUX and Chroma should normally return an empty `negative_prompt`.
- Full Z-Image may return a concise, targeted `negative_prompt`.
- Z-Image-Turbo should follow its own runtime parameters and must not be treated as full Z-Image.
- A single unconditional rule saying “Flux, Chroma, and Z-Image never use negative prompts” is incorrect.

### 1.5 Flux-like project template

Recommended baseline:

`[Primary subject and action] + [important attributes and relations] + [shot and composition] + [environment] + [lighting] + [style or medium]`

For multiple characters:

- identify each subject separately;
- use spatial or relational anchors;
- avoid interleaving attributes from different characters;
- state the interaction explicitly.

### Sources

1. **Black Forest Labs, Prompting Basics**  
   URL: https://docs.bfl.ai/guides/prompting_unified_basics  
   Publication date: not exposed on the page  
   Accessed: 2026-07-19  
   Used for: natural language, non-strict prompt structure, iteration, quoted text.

2. **Black Forest Labs, Working Without Negative Prompts**  
   URL: https://docs.bfl.ai/guides/prompting_guide_t2i_negative  
   Publication date: not exposed on the page  
   Accessed: 2026-07-19  
   Used for: unsupported negative prompts in FLUX, positive replacement strategy, word-order guidance.

3. **Black Forest Labs, Style, Aesthetics & Text**  
   URL: https://docs.bfl.ai/guides/prompting_unified_style  
   Publication date: not exposed on the page  
   Accessed: 2026-07-19  
   Used for: camera, lens, film stock, lighting, style, and typography guidance.

4. **Black Forest Labs, FLUX.2 Prompting Guide**  
   URL: https://docs.bfl.ai/guides/prompting_guide_flux2  
   Publication date: not exposed on the page  
   Accessed: 2026-07-19  
   Used for: current FLUX.2 prompt structure, structured JSON support, multi-reference prompting, prompt upsampling.

5. **lodestones/Chroma1-HD model card**  
   URL: https://huggingface.co/lodestones/Chroma1-HD  
   Publication date: page does not expose a stable publication date  
   Accessed: 2026-07-19  
   Used for: relationship to FLUX.1-schnell and current Chroma model status.

6. **Tongyi-MAI/Z-Image official repository**  
   URL: https://github.com/Tongyi-MAI/Z-Image  
   Published: 2025  
   Accessed: 2026-07-19  
   Used for: Z-Image architecture, CFG, recommended parameters, and negative-prompt behavior.

7. **Tongyi-MAI/Z-Image model card**  
   URL: https://huggingface.co/Tongyi-MAI/Z-Image  
   Published: 2025  
   Accessed: 2026-07-19  
   Used for: official usage examples and model-family distinction.

---

## 2. SDXL profile

### 2.1 Documented architecture and prompt inputs

Confirmed findings:

- SDXL uses two fixed pretrained text encoders: CLIP ViT-L and OpenCLIP ViT-bigG.
- Current Diffusers supports separate `prompt` and `prompt_2` values, plus `negative_prompt` and `negative_prompt_2`.
- Negative prompts are supported when classifier-free guidance is active.
- Prompt weighting is possible through generated prompt embeddings and external weighting helpers.
- Current Diffusers guidance recommends a structured prompt built from subject, style, and context, with concrete camera and lighting details.

Important correction:

- The two text encoders do not establish a documented two-stage semantic process of “layout first, fine details second.” That phrase should not be presented as SDXL architecture.

### 2.2 Positive prompt structure

Recommended project baseline:

`[Subject and scene] + [important attributes and relations] + [style or medium] + [camera and composition] + [lighting, environment, and mood]`

SDXL accepts both descriptive phrases and tag-like fragments. The best balance depends heavily on the checkpoint and its training captions.

For derived checkpoints:

- preserve the base structure;
- allow checkpoint-specific trigger words, quality tokens, and syntax only when supported by the checkpoint model card or practical tests;
- do not assume that RealVisXL, Juggernaut XL, DreamShaper XL, and unrelated SDXL finetunes respond identically.

### 2.3 Negative prompts

Documented fact:

- SDXL supports negative conditioning.

Project heuristic:

- Begin with an empty negative prompt.
- Add only terms that target likely or observed defects.
- Avoid contradictions with the positive prompt.
- Prefer concise negatives as a default for weak prompt-writing models.

Not established as a universal fact:

- There is no official SDXL architecture rule limiting negative prompts to 5–15 tokens.
- There is no official proof that every long negative prompt necessarily degrades every SDXL checkpoint.
- A 5–15-term target may remain a project default, but it must be labeled and tested as a heuristic.

### 2.4 Prompt length

The base SDXL encoders use CLIP tokenizers with finite context. Long-prompt techniques can generate embeddings beyond the ordinary tokenizer path, but support depends on the runtime and helper library.

Project rule:

- Keep the default generated prompt compact enough for normal ComfyUI conditioning.
- Do not claim that a specific word count is a universal tokenizer limit.
- Validate truncation behavior in the exact ComfyUI node path used by task 07.

### Sources

1. **Stability AI, SDXL base 1.0 model card**  
   URL: https://huggingface.co/stabilityai/stable-diffusion-xl-base-1.0  
   Released: 2023-07-26  
   Accessed: 2026-07-19  
   Used for: two fixed text encoders, base/refiner description, official model identity.

2. **Podell et al., SDXL: Improving Latent Diffusion Models for High-Resolution Image Synthesis**  
   URL: https://arxiv.org/abs/2307.01952  
   Published: 2023-07-04  
   Accessed: 2026-07-19  
   Used for: SDXL architecture, second text encoder, conditioning design, native high-resolution training.

3. **Hugging Face Diffusers, Stable Diffusion XL pipeline documentation**  
   URL: https://huggingface.co/docs/diffusers/main/api/pipelines/stable_diffusion/stable_diffusion_xl  
   Publication date: rolling documentation; no fixed date exposed  
   Accessed: 2026-07-19  
   Used for: `prompt_2`, `negative_prompt_2`, CFG behavior, text encoders, current pipeline API.

4. **Hugging Face Diffusers, Prompting guide**  
   URL: https://huggingface.co/docs/diffusers/main/using-diffusers/weighted_prompts  
   Publication date: rolling documentation; no fixed date exposed  
   Accessed: 2026-07-19  
   Used for: subject/style/context structure, concrete camera details, prompt weighting and embeddings.

5. **Stability AI generative-models repository**  
   URL: https://github.com/Stability-AI/generative-models  
   SDXL 1.0 release entry: 2023-07-26  
   Accessed: 2026-07-19  
   Used for: official release timeline and reference implementation.

---

## 3. Pony profile

### 3.1 Model-author guidance

Pony Diffusion V6 XL is an SDXL finetune trained with both detailed captions and dataset tags.

Confirmed findings from the author-provided model card:

- The model can respond to simple natural-language prompts.
- The training data combines captions and tags.
- Natural language works in most cases, and tags can be appended to strengthen concepts.
- The recommended quality prefix is:
  `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up`
- `source_pony`, `source_furry`, `source_cartoon`, and `source_anime` are supported source-selection tags.
- `rating_safe`, `rating_questionable`, and `rating_explicit` are supported rating tags.
- Clip skip 2 is explicitly required by the model author.
- The model is designed to work without a negative prompt in most cases.
- Generic modifiers such as `hd` and `masterpiece` are not required by the base model.

Short source excerpt:

> “trained on combination of natural language prompts and tags”

### 3.2 Syntax conclusion

Pony is not accurately described as a model that accepts only strict Danbooru tag lists.

A robust profile for weak LLMs may still prefer a deterministic hybrid layout:

`[score prefix] + [source tag] + [rating tag] + [clear natural-language scene or ordered tags] + [optional reinforcing tags]`

Why use a structured profile:

- it prevents weak models from forgetting score, source, or rating controls;
- it keeps character count, appearance, action, shot, and environment in a stable order;
- it makes output easier to validate and edit.

This is a project reliability decision, not proof that other Pony syntax is invalid.

### 3.3 Negative prompts

Model-author guidance:

- no negative prompt is needed in most cases;
- the default template is shown without one.

Project heuristic:

- default to an empty negative prompt for the base model;
- add a short targeted negative only for a concrete observed failure or a checkpoint-specific recommendation;
- do not require a five-to-fifteen-tag negative prompt unconditionally.

### 3.4 Derived Pony checkpoints

Pony-derived checkpoints may change:

- recommended score prefixes;
- source and rating token behavior;
- preferred natural-language versus tag balance;
- negative-prompt requirements;
- sampler, CFG, and clip-skip recommendations.

The base Pony skill should provide a safe default, while task 07 may later apply checkpoint-specific overrides from model metadata.

### Sources

1. **Pony Diffusion V6 XL author-provided model card mirror**  
   URL: https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL  
   Initial model-card commit: 2024-05-25  
   Accessed: 2026-07-19  
   Used for: natural language plus tags, score prefix, source/rating tags, clip skip 2, and negative-prompt guidance.

2. **Pony Diffusion V6 XL initial model-card commit**  
   URL: https://huggingface.co/LyliaEngine/Pony_Diffusion_V6_XL/commit/4ce8c4008b0436297f6c27ce5f916ef883a51bfd  
   Published: 2024-05-25  
   Accessed: 2026-07-19  
   Used for: stable dated evidence of the model-author recommendations.

3. **Model-author-linked score-tag explanation**  
   URL: https://civitai.com/articles/4248  
   Publication date: not verified by the current research tool  
   Accessed: 2026-07-19  
   Used only as a secondary explanation linked by the model card; no unsupported claims from it are treated as authoritative here.

---

## 4. Cross-family conclusions

| Area | FLUX / Chroma | Full Z-Image | SDXL | Pony V6 XL |
|---|---|---|---|---|
| Primary syntax | Natural language | Natural language | Hybrid, checkpoint-dependent | Hybrid: captions + tags |
| Separate negative prompt | Unsupported | Supported and recommended for control | Supported with CFG | Usually unnecessary |
| Strong family prefix | No | No universal prefix | Checkpoint-dependent | Full score prefix recommended |
| Source/rating tags | No | No | Checkpoint-dependent | Supported |
| Clip skip 2 | No family rule | No family rule | Checkpoint-dependent | Required by model author |
| Main risk | vague prose or overloaded constraints | treating it exactly like FLUX | universal rules applied to diverse finetunes | turning a recommended template into false mandatory syntax |

---

## 5. Audit of the current skill files

The source research exposes several statements that need correction before task 06 can be considered fully complete.

### `app/ai/skills/flux.txt`

- It groups Z-Image with FLUX and says the entire group does not use negative prompts.
- Official Z-Image guidance contradicts that rule for the full model.
- Numeric claims about first-word attention and ideal prompt length should be labeled as project heuristics, not documented model limits.

### `app/ai/skills/sdxl.txt`

- “Two text encoders” is correct.
- “Processes text in two stages: layout first, then fine details” is not supported by the SDXL paper or current Diffusers documentation.
- The 5–15-token negative-prompt limit should be labeled as a project default, not a universal architecture rule.

### `app/ai/skills/pony.txt`

- The current file describes strict tag-only syntax, while the model card explicitly supports natural language and tags.
- The current required prefix stops at `score_6_up`; the author-recommended V6 XL prefix continues with `score_5_up, score_4_up`.
- The current file requires a negative prompt, while the model author says the model usually does not need one.
- Score, source, and rating controls are strong defaults, but source and rating tags should not be described as mandatory architecture sections without practical evidence.

These are content corrections inside task 06, not runtime integration work from task 07.

---

## 6. Scope boundary with task 07

Task 06 owns:

- researched skill content;
- source records and research dates;
- stable JSON output contracts;
- static loader tests;
- practical prompt-quality verification.

Task 07 owns:

- selecting a syntax skill in an application operation;
- sending the assembled system prompt to an AI provider;
- parsing and validating runtime LLM responses;
- model-family or checkpoint routing;
- translation, reconstruction, remix, and ranking UI flows.

Therefore the following are intentionally not implemented as part of this research update:

- integration into `transport.py`;
- automatic skill selection in `library.py`;
- runtime JSON validation of provider output.

---

## 7. Verification still required

Static text review cannot replace image-generation tests.

Minimum practical matrix:

- portrait;
- full-body scene;
- two or more characters;
- dynamic action;
- unusual camera angle;
- object or interior scene;
- stylisation;
- prompt reconstruction from an image without metadata.

Each case should compare at least:

- the current skill output;
- a shorter baseline prompt;
- one controlled alternative changing only syntax or negative-prompt strategy.

Record model/checkpoint, sampler, steps, CFG, seed, resolution, clip skip, positive prompt, negative prompt, and the observed failure mode. The browser and ComfyUI generation checks remain manual for this task.
