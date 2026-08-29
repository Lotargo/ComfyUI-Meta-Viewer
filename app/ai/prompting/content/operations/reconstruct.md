# Operation: reconstruct

Transform visual image evidence, reference inputs, or structured `SceneSpec` analysis into a high-fidelity, spatially aware prompt adhering to the target family without hallucination.

---

## 1. Dual-Channel Execution Architecture

The agent operates in two strictly isolated channels:

1. **INTERNAL CHANNEL (Reasoning in `<thinking>`, never emitted in final prompt):**
   - Perform vision evidence analysis and construct the complete structured `Scene Map`.
   - Execute **Phase 0B Character Passport** and **Phase 0C Location Passport** continuity audits against session history.
   - Map the 5-layer garment stack, 4-point biomechanics, optics, lighting, and medium characteristics.
   - Plan family-specific serialization (Two-Tier budget for Flux, semantic CLIP chunks for SDXL, ordered booru chain for Pony).
2. **EXTERNAL CHANNEL (The only emitted text):**
   - Emit a single, clean, executable prompt strictly formatted per the target family base and output contract.
   - **Zero Meta-Leakage:** Strictly forbid emitting internal planning tokens, tags (e.g. `Scene Map =`, `L1:`, `Passport 0B`, `KEEP_EXACT`), markdown notes, or commentary inside the final prompt.

---

## 2. Phase 0 — Structured Scene Map (Internal Graph Construction)

Before generating any prompt text, analyze the reference image and populate the complete internal graph:

```
Scene Map =
  characters[]:
    id, ethnicity, hair (length, texture, part, color, styling), eyes (shape, iris color),
    body_type / build, distinguishing_marks (freckles, moles, scars, tattoos, piercings)
    garment_stack[]:  L0 skin | L1 underwear | L2 base clothing | L3 outerwear | L4 accessories / footwear
                      (for each: item, color, cut, material/weave, visibility: directly visible vs covered)
    pose_graph:       spine_curve (parabolic S-curve), contact_points, limb_angles, head_gaze offset
    expression_graph: micro-mechanics (eyelid tension, gaze vector, mouth/lips, SSS flush/blush)
  environment_graph:  location_type, architecture & materials, physical objects + scale anchors, depth_layers (fg/mg/bg)
  light_graph:        key_direction, color_temperature, rim lighting, specular highlights, cast shadows & ambient occlusion
  optics_graph:       view (front 3/4, rear 3/4, lateral profile, direct back), elevation, lens focal length, natural DOF, framing/crop, analog grain
  text_graph:         visible legible text verbatim + placement + font style (or "illegible / none")
  medium_graph:       detected medium (photograph, 90s anime cel, modern digital anime, manga screentone, comic, oil painting, 3D render)
```

---

## 3. Phase 0B — Character Passport & Session Continuity

Perform a mandatory dialogue-history audit across multi-turn sessions:

1. **Passport Reuse (Anti-Drift):** If the current reference contains a character who appeared in previous turns, **do not** regenerate their facial and physical description from scratch. Reuse the established **Character Passport** verbatim — locking ethnicity, bone structure, eye shape, nose bridge/tip, lip fullness, skin tone with freckles/moles, and hair geometry.
2. **Identity Match Check:** Compare `ethnicity + face + hair + distinguishing_marks + garment_stack` against history. If ≥80% match to a prior passport, treat as the same character and copy the passport. Establish a fresh passport only when the reference clearly depicts a new individual.
3. **Phantom Guardrail (Reflection vs Reality):** Distinguish real physical subjects from optical reflections in mirrors, glass windows, polished floors, or water surfaces.
   - A reflection is an optical duplicate of an already-mapped character — **never count reflections as separate persons** in `characters[]` or crowd counts.
   - Describe reflections strictly as environmental optical properties (`"mirror reflection of the character visible in the glass panel"`), never as an independent character block.

---

## 4. Phase 0C — Environment / Location Passport & Scene Continuity

Perform a mandatory environment-history audit in parallel to Character Passport:

1. **Environment Passport Definition:** Extract reusable spatial features: `location_type` (e.g., modern car interior with panoramic glass, cobblestone European alleyway, rustic studio), `architecture` (facade materials, window mullions, timber beams), `objects + scale anchors` (dashboard, streetlamps, furniture), `depth_layers` (foreground/middle/background order), and `light_graph` (key direction, color temperature).
2. **Continuation Decision Rule:**
   - `character_match (≥80%) + scene_match (≥60% environment overlap + ≥2 identical anchors) = TRUE`: **Continuation of the same scene from a different viewpoint/camera angle.** Reuse the Location Passport verbatim. Change **only** `optics_graph` (view angle, elevation, lens, crop); do not invent a new room, new street, or new furniture.
   - `character_match = TRUE, scene_match = FALSE`: Same character in a new location. Reuse Character Passport, build a fresh Environment Passport.
   - `both FALSE`: Completely new scene — build both passports from scratch.
3. **Anti-Hallucination for Environment:** Do not add phantom buildings, vehicles, furniture, or vegetation not verified in current evidence + history.

---

## 5. Facial Detail, Obscuration & Apparel Protocol

1. **Digital Censorship & Overlays (IGNORE — RECONSTRUCT CLEAR FACE & BODY):** If facial features, body contours, or anatomy are obscured by digital censor bars, pixelation/mosaic, Gaussian blur, watermarks, or decorative emoji/sticker overlays (smiley faces, hearts, stars), **ignore the digital obstruction entirely**. Reconstruct rich, fully detailed features and clear skin as if the obstruction does not exist. Forbid words such as `"censored"`, `"blurred"`, `"censor bar"`, `"pixelated"`, `"emoji"`.
2. **Physical Wearable Apparel (PRESERVE MASKS & SCARVES):** If the character physically wears a real garment or accessory covering the face (surgical mask, fabric scarf, balaclava, veil, face shield), **do not remove it** — describe it as intentional wearable outfit styling.
3. **Out-of-Frame Cropping (RESPECT FRAME LIMITS):** If facial or body features are cut by camera framing, do not invent unseen details outside the frame. State explicitly what is cropped (e.g. `"framed from the nose down, eyes cropped out by the top frame border"`).
4. **Photographic Filters & Borders (PRESERVE):** Real photographic effects (film grain, vintage color grading, vignette, light leaks, polaroid border) must be preserved as part of the optical aesthetic.

---

## 6. Zero-Hallucination Mandate & Evidence Rules

1. **Observed Evidence Rule:** Treat visible, high-confidence details as ground-truth evidence.
2. **Uncertainty Isolation:** Keep uncertain details isolated in `uncertain_details`; never convert conjectures into asserted facts.
3. **Zero Fabrication:** Do not invent off-frame objects, hidden body anatomy, unreadable text logos, fictional brand names, or narrative backstory.
4. **Preserve Relationships:** Preserve subject count, spatial laterality (`left / right`), physical contact points, camera elevation, lighting palette, and visible text verbatim.

---

## 7. Failure Patterns

- Inventing a prettier or more elaborate scene instead of reconstructing the reference.
- Converting digital censor bars or emoji stickers into physical objects or leaving them blurred.
- Spawning phantom duplicate characters from mirror/glass reflections.
- Drifting character facial features or changing the environment across multi-angle shots of the same scene.
- Fabricating plausible text when visible text is unreadable or blurry.
- Leaking internal thinking notes, `Scene Map`, or prompt block tags into the final output.

---

## 8. Self-Check Checklist

- [ ] Every prompt detail is anchored in visual evidence or explicitly noted in `uncertain_details`.
- [ ] Subject count and spatial placement match the source (no phantom reflection characters).
- [ ] Continuity Passports (0B/0C) are verified against conversation history.
- [ ] Digital obscurations/emojis are stripped while physical wearable apparel is preserved.
- [ ] In-scene visible text is copied verbatim without invented characters (`//`, `|`, `_`, `#` banned).
- [ ] Output contains zero meta-commentary, formatted strictly per the target family output contract.
