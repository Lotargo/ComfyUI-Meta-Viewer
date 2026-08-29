# Operation: enhance

Surgically improve, refine, and elevate an existing prompt to satisfy user wishes and maximize target model fidelity without discarding the original creative intent.

---

## 1. Dual-Channel Execution Architecture

The agent operates in two strictly isolated channels:

1. **INTERNAL CHANNEL (Reasoning in `<thinking>`, never emitted in final prompt):**
   - Deconstruct the source prompt to isolate its existing foundation: subject, composition, wardrobe, lighting, environment, and style.
   - Parse user-provided wishes as **surgical deltas** (wardrobe delta, lighting delta, composition delta, detail delta).
   - Verify protected trigger words, LoRA invocations, and checkpoint tokens.
   - Plan family-specific enhancements (Two-Tier budget for Flux, semantic CLIP chunks for SDXL, ordered booru chain for Pony).
2. **EXTERNAL CHANNEL (The only emitted text):**
   - Emit a single, clean, refined prompt adhering strictly to the target family base profile and scenario manifest.
   - **Zero Meta-Leakage:** Never include delta logs, comparison notes, or internal reasoning in the emitted prompt.

---

## 2. Surgical Delta Architecture

Treat user wishes as targeted, non-destructive modifications applied to the source prompt:

1. **Wardrobe Delta:** Apply specific garment adjustments (e.g., adding an outer jacket, adjusting cut lines, adding sheer fabric accents) while maintaining the baseline outfit structure.
2. **Lighting & Atmosphere Delta:** Elevate key light direction, color temperature, volumetric fog, rim highlights, and ambient occlusion.
3. **Composition & Optics Delta:** Refine camera angle (e.g., shifting to front 3/4 or low-angle), lens focal length (e.g., 85mm portrait prime), and natural depth-of-field falloff.
4. **Micro-Texture & Surface Delta:** Replace vague terms with tactile material physics (e.g., skin pores with translucent SSS blush, brushed metal, woven silk, water reflections).
5. **Pure Polish Mode (Zero Wishes Provided):** If no specific wishes are provided, polish the prompt's sensory clarity, lighting physics, and model-specific syntax while strictly locking 1:1 scene composition, subject identity, and environment.

---

## 3. Core Preservation Guardrails

1. **Anti-Rewrite Guardrail:** Do not rewrite the prompt into a fundamentally different image. The subject count, core action, setting, mood, and intentional styling must remain intact unless a user wish explicitly alters them.
2. **Trigger Word & LoRA Protection:**
   - Always preserve user-provided trigger words, LoRA tokens (e.g. `<lora:name:weight>`), and checkpoint keywords verbatim.
   - Never remove a recognized trigger word under the assumption that it is redundant.
   - Never fabricate nonexistent trigger words or claim unsupported model capabilities.
3. **Negative Prompt Strategy by Family:**
   - **FLUX:** Enforce the **T5-XXL No-Negation Rule** — leave the negative prompt empty (`""`), achieving technical cleanliness through positive descriptive precision.
   - **SDXL:** Construct or refine a concise, targeted negative prompt addressing specific artifacts, anatomical flaws, and style clashes.
   - **PONY:** Ensure standard score-based negative boilerplate (`score_4, score_5, low quality...`) is present or maintain the existing negative tag chain.

---

## 4. Failure Patterns

- Rewriting the prompt into an entirely new scene and discarding the source composition.
- Dropping user-provided trigger words or LoRA invocation syntax.
- Padding the prompt with generic quality buzzwords (`"hyperrealistic, 8k, masterpiece"`) instead of concrete visual enhancements.
- Copying an SDXL negative prompt into Flux, violating the T5-XXL No-Negation rule.
- Emitting meta-commentary, diff summaries, or markdown formatting outside the strict output contract.

---

## 5. Self-Check Checklist

- [ ] Every user-provided wish is concretely represented in the enhanced positive prompt.
- [ ] Baseline scene composition, subject identity, count, and action are preserved.
- [ ] All checkpoint trigger words and LoRA tokens are preserved verbatim.
- [ ] Negative prompt follows the target model family convention (empty for Flux, targeted for SDXL, booru score chain for Pony).
- [ ] Output contains zero meta-commentary, formatted strictly per the target family output contract.
