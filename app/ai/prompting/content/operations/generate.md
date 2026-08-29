# Operation: generate

Create a new, highly vivid, and executable image-generation prompt from a user text request or creative brief while strictly preserving the core intent and constraints.

---

## 1. Dual-Channel Execution Architecture

The agent operates in two strictly isolated channels:

1. **INTERNAL CHANNEL (Reasoning in `<thinking>`, never emitted in final prompt):**
   - Deconstruct the user request to isolate core constraints: subject, count, requested action, mood, environment, and medium.
   - Determine appropriate medium and style (Photography, Anime Cel, Manga, Comic, Oil Painting, 3D Render).
   - Plan spatial staging across depth planes (`foreground / midground / background`).
   - Select physical material textures, lighting direction, color palette, and camera optics.
   - Formulate family-specific serialization rules (Two-Tier budget for Flux, semantic CLIP chunks for SDXL, ordered booru tag chain for Pony).
2. **EXTERNAL CHANNEL (The only emitted text):**
   - Emit a single, clean, executable prompt adhering strictly to the target family base profile and scenario manifest.
   - **Zero Meta-Leakage:** Never include internal thoughts, planning notes, prefix headers, or conversational filler in the emitted prompt.

---

## 2. Creative Visual Expansion Protocol

Diffusion models require concrete visual specificity to render compelling scenes without default generic artifacts. Expand the user brief along core generative dimensions:

1. **Spatial Staging & Depth Hierarchy:**
   - Establish clear placement across depth layers (`foreground, middle ground, distant background`).
   - Define spatial laterality (`on the left, on the right, centered`) to anchor characters and primary props.
2. **Physical Materials & Surface Physics:**
   - Replace abstract concepts with tactile material descriptors (e.g., `"brushed matte aluminum"`, `"coarse woven linen"`, `"polished dark hardwood with soft reflections"`, `"translucent frosted glass"`).
   - Specify fabric drape, stretch tension over body contours, and natural seam gathering.
3. **Directional Lighting & Atmosphere:**
   - Define primary key light angle (`"warm directional sunlight streaming from a high 45-degree angle on the right"`).
   - Specify fill light, subtle rim highlights separating the subject from background, and grounding cast shadows with ambient occlusion.
4. **Photographic Optics & Camera Stance:**
   - Set focal length and lens behavior (`"35mm wide-angle prime lens"`, `"85mm telephoto portrait compression"`).
   - Apply natural depth-of-field falloff (avoiding harsh green-screen cutouts) and camera elevation (`eye-level, slightly low-angle, high overhead`).

---

## 3. Intent Preservation & Guardrails

1. **Non-Negotiable Core Intent:** The user's requested subject, character count, primary action, mood, and specified constraints are absolute. Never silently replace or contradict them.
2. **Anti-Clutter Guardrail:** Do not over-saturate the scene with unrequested secondary characters, chaotic background objects, or irrelevant narrative complexity.
3. **Ban on Generic Quality Fluff:**
   - For **Flux** and **SDXL**: Categorically forbid meaningless buzzwords such as `"photorealistic"`, `"hyperrealistic"`, `"ultra-detailed"`, `"8k resolution"`, `"masterpiece"`, `"trending on ArtStation"`. Express quality through concrete physical, optical, and material details.
   - For **Pony**: Use the official, structured score prefix hierarchy (`score_9, score_8_up...`) and Danbooru tags rather than ad-hoc natural language praise.
4. **Two-Zone Text Split:** If visible text in the image is requested, transcribe it verbatim in quotation marks with strict casing specifications, keeping it separated from background clutter.

---

## 4. Failure Patterns

- Turning a concise user request into an unrelated, bloated narrative with extra characters.
- Replacing concrete visual details with generic quality buzzwords (`"hyper-detailed, 8k, masterpiece"`).
- Losing the requested camera angle, medium, or artistic style during creative expansion.
- Adding contradictory lighting sources or physically impossible spatial geometry.
- Emitting commentary, markdown code block fences, or meta-explanations outside the output contract.

---

## 5. Self-Check Checklist

- [ ] The user's central subject, action, mood, and explicit constraints are fully honored.
- [ ] Creative additions expand visual executability (depth, lighting, materials, optics) without altering intent.
- [ ] No empty quality buzzwords are used (unless structured Pony score tags).
- [ ] Target family serialization and syntax rules are strictly respected.
- [ ] Output contains zero meta-commentary, formatted strictly per the target family output contract.
