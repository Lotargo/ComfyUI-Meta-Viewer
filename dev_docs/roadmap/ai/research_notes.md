# Prompt Engineering Research Notes (July 19, 2026)

This document compiles the research, sources, and best practices for creating optimized generative prompts for Flux, SDXL, and Pony model families.

---

## 1. Flux-like Models (Flux, Chroma, Z-Image)

### Core Findings
* **Aesthetic Philosophy:** Natural language description (storytelling). Traditional "tag soup" (comma-separated keyword lists) degrades performance.
* **Structural Template:** `[Subject] + [Action/Pose] + [Style/Aesthetic] + [Context/Setting/Lighting]`.
* **Ordering Priority:** Flux pays maximum attention to the first elements. The primary subject and its core action must be at the absolute start of the prompt.
* **Positive Prompt Best Practices:**
  * Define visual layers in order: foreground details, midground action, background environment.
  * Use descriptive camera terms (e.g., "shot on 35mm lens, f/2.8", "cinematic film style", "Wes Anderson color palette") rather than quality buzzwords.
  * Keep prompt length in the "sweet spot" of **40–80 words**. Long prompts (200+ words) risk semantic drift and truncation.
* **Negative Prompting:** Flux models do not use or respond to negative prompts. Exclusions should be phrased positively by describing what *is* there instead of what is not.
* **Common Weak LLM Pitfalls:** Recommending a negative prompt or writing comma-separated tag soup.

### Sources
* [getimg.ai Flux Prompt Guide](https://getimg.ai)
* [fal.ai Flux Documentation & Parameters](https://fal.ai)
* [Black Forest Labs Official Recommendations](https://blackforestlabs.ai)
* Community Experiments: Reddit `r/StableDiffusion`

---

## 2. SDXL (Stable Diffusion XL)

### Core Findings
* **Aesthetic Philosophy:** Hybrid structure. SDXL works well with a mix of descriptive phrases (sentence segments) and structural tags.
* **Structural Template:** `[Core Subject] + [Style & Medium] + [Lighting & Composition] + [Refinements]`.
* **Positive Prompt Best Practices:**
  * Compose in layers, detailing the environment, time of day (e.g., "golden hour", "foggy morning"), and camera parameters (e.g., "shot on 85mm lens", "shallow depth of field").
  * Use photography vocabulary rather than abstract artist names.
* **Negative Prompting:**
  * Must be surgical and brief (**5–15 tokens** max). Long, copy-pasted negative lists degrade the prompt attention.
  * Only exclude what is relevant (e.g., do not exclude "bad feet" in a close-up face portrait).
  * Avoid contradictions (do not exclude "blur" if you want "depth of field").
* **Quality Tokens:** Use simple modifiers like `low quality, worst quality, blurry, watermark, text, logo` in the negative prompt to suppress artifacts.

### Sources
* [Stable Diffusion Art - SDXL Prompting](https://stable-diffusion-art.com)
* Civitai Guide to SDXL Parameters & Aesthetics
* Community Benchmarks & Embedding Guides

---

## 3. Pony-like Models (Pony Diffusion V6 XL & Variants)

### Core Findings
* **Aesthetic Philosophy:** Rigid dataset-specific syntax. Pony is trained on structured anime-style tagging conventions and requires specific prefix/score strings.
* **Structural Template:** `[Score Tags], [Source Tag], [Safety Tag], [Subject/Description], [Composition/Style Tags]`.
* **Score Tags (Mandatory Prefix):**
  * Use the exact prefix string: `score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up`.
  * Do not use standard quality words (e.g. "masterpiece", "best quality") as they were pruned from training.
* **Source Tags (Choose One):**
  * `source_anime` (Anime/Manga style)
  * `source_cartoon` (Western cartoon style)
  * `source_furry` (Furry/Anthropomorphic style)
  * `source_pony` (My Little Pony aesthetic)
* **Safety Tags (Choose One):**
  * `rating_safe` (SFW)
  * `rating_questionable` (Suggestive)
  * `rating_explicit` (NSFW)
* **Clip Skip:** Must run with **Clip Skip 2** (otherwise output will look burned or degraded).
* **Tagging Syntax:** Describe the subject with short, comma-separated Danbooru-style tags (e.g., `1girl, solo, blue eyes, dynamic pose`) rather than long natural sentences.
* **Negative Prompting:** Use minimal negative prompts to avoid coloring the style (e.g., `3d, render, CGI, text, watermark` for flat 2D anime style).

### Sources
* Pony Diffusion V6 XL HuggingFace Model Card & Release Notes
* Civitai Pony Prompting Conventions & User Guides
