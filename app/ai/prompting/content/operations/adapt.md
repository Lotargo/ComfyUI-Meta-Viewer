# Operation: adapt

Adapt an existing prompt from one model family to another (e.g., Flux, SDXL, Pony Diffusion) while strictly preserving the scene's visual meaning, subject identity, composition, and aesthetic intent.

---

## 1. Dual-Channel Execution Architecture

The agent operates in two strictly isolated channels:

1. **INTERNAL CHANNEL (Reasoning in `<thinking>`, never emitted in final prompt):**
   - Deconstruct the source prompt into its core visual components: subject count, identity, wardrobe, pose, environment, lighting, and style.
   - Strip source-family-specific boilerplate (e.g., score prefixes, obsolete quality tags, or unsupported negative embedding codes).
   - Identify and isolate protected trigger words, character concepts, and LoRA tokens.
   - Re-synthesize the scene according to the target family's syntax, encoder architecture, and prompt conventions.
2. **EXTERNAL CHANNEL (The only emitted text):**
   - Emit a single, clean prompt formatted strictly according to the target family base profile and scenario manifest.
   - **Zero Meta-Leakage:** Never include translation notes, family comparison commentary, or markdown fences in the emitted prompt.

---

## 2. Cross-Family Paradigm Translation Rules

### 2.1. Adapting to FLUX / KREA
- **Syntax Paradigm:** Natural, descriptive, grammatically coherent English prose.
- **Conversion Strategy:** Convert comma-separated booru tags or CLIP fragments into fluid, full-sentence descriptions.
- **Budget Architecture:** Format into the Two-Tier structure: a 4-sentence Base Block (subject, composition, lighting, style) up to 500 tokens, followed by Detail Blocks A/B/C (wardrobe micro-textures, background, analog grain) up to 2000 tokens.
- **T5-XXL No-Negation:** Strip all source negative prompts. If the source negative prompt contained important aesthetic exclusions, express them positively in the description or eliminate them entirely through complete silence. Leave the target negative prompt empty (`""`).

### 2.2. Adapting to SDXL
- **Syntax Paradigm:** Dense, high-signal semantic CLIP chunks separated by commas.
- **Conversion Strategy:** Condense verbose prose into high-density descriptive phrases; eliminate filler words and conversational padding.
- **Negative Prompt:** Extract unwanted elements and defects from the source into a concise, targeted negative prompt.

### 2.3. Adapting to PONY DIFFUSION
- **Syntax Paradigm:** Ordered booru tag chain adhering strictly to Danbooru taxonomy.
- **Conversion Strategy:** Translate prose sentences and concept phrases into standard Danbooru tags.
- **Tag Ordering Hierarchy:**
  `[Quality Score Prefixes], [Source / Rating], [Subject Count], [Identity], [Face / Hair], [Body], [Expression], [Pose], [Wardrobe], [Camera / View], [Environment], [Lighting], [Style]`.
- **Quality & Rating Prefixes:** Prepend author-recommended score tags (`score_9, score_8_up, score_7_up, score_6_up, score_5_up, score_4_up`) and rating tags (`rating_safe`, `rating_explicit`).

---

## 3. Boilerplate Cleanup & Trigger Word Preservation

1. **Source Boilerplate Removal:**
   - When adapting **away from Pony**, remove score prefixes (`score_9`, `score_8_up`), source tags (`source_anime`), and rating tags.
   - When adapting **away from SDXL to Flux**, remove negative embedding tokens (e.g. `bad_prompt`, `easynegative`) and generic quality dumps.
2. **Protected Trigger Preservation:**
   - Checkpoint trigger words and LoRA tokens present in the source prompt that belong to the target model must be preserved verbatim.
   - Never drop a recognized trigger word simply because it looks like a quality tag.
   - Never invent trigger words that were not in the source prompt.

---

## 4. Failure Patterns

- Treating adaptation as an unconstrained rewrite and altering the character, clothing, pose, or setting.
- Carrying over source-family negative prompts into Flux, violating the T5-XXL No-Negation rule.
- Leaving comma-separated booru tags unchanged when adapting to Flux natural prose.
- Discarding recognized LoRA or checkpoint trigger words.
- Emitting meta-commentary or explanation outside the output contract.

---

## 5. Self-Check Checklist

- [ ] The adapted prompt depicts the identical visual scene (subject, count, pose, wardrobe, lighting, environment).
- [ ] Source-family boilerplate is stripped and target-family syntax is correctly applied.
- [ ] Protected trigger words from the source prompt are preserved.
- [ ] Negative prompt strategy matches the target family (empty for Flux, targeted for SDXL, score chain for Pony).
- [ ] Output contains zero meta-commentary, formatted strictly per the target family output contract.
