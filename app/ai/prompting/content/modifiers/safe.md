# MODIFIER: SAFE (GENERAL AUDIENCE & SFW ENGINE)

Apply when the task enforces a general-audience, safe-for-work (SFW) content boundary.

This modifier guarantees that all generated, reconstructed, or enhanced prompts adhere strictly to non-sexualized, tasteful, general-audience aesthetic standards across all model families.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — HARD SFW BOUNDARIES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1.1  GENERAL AUDIENCE COMPLIANCE
     • Clothing, posing, framing, expression, and character interactions must remain
       fully appropriate for a broad, general audience.
     • Categorically FORBID nudity, suggestive or erotic framing, fetish elements,
       explicit anatomy, and unsolicited intimate escalation.

1.2  PROTECTION OF NEUTRAL SUBJECTS
     • Never introduce sexualized traits, cleavage, exposed underwear, or erotic undertones
       into neutral subjects, everyday professions, casual activities, portraits, or scenic views.
     • Preserve the requested artistic aesthetic and style without using sexualization
       as a shortcut for visual interest.

1.3  AGE & CONTEXT SAFETY
     • When age is uncertain or when depicting students, youths, or school settings,
       enforce strictly modest, non-suggestive, and wholesome character styling and framing.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — WARDROBE & MODESTY RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  OPAQUE DRAPE & NATURAL TAILORING
     • Keep clothing fully fastened and properly worn: standard modest necklines,
       appropriate hemlines, opaque cloth weaves, and fully covered underwear layers.
     • Focus on authentic textile qualities, material drape, seam construction,
       and color harmony (e.g. crisp cotton, heavy wool, tailored linen, structured denim).

2.2  FORBIDDEN REVEALING OPERATIONS
     • Categorically FORBID micro-cuts (underbutt exposure, ultra-low rise), see-through
       sheer lingerie, unbuttoned flies, hiked skirts, or fallen shoulder straps designed
       for exposure.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — EXPRESSION & POSING POISE
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3.1  AESTHETIC POISE & NATURAL BIOMECHANICS
     • Expressions must reflect natural, authentic emotions: warm Duchenne smiles,
       confident gaze, relaxed contemplation, professional focus, or serene tranquility.
     • Poses must emphasize natural weight distribution, graceful posture, balance,
       and authentic activity without exaggerated sexualized hip thrusts or arching.

3.2  FORBIDDEN EROTIC MICRO-MECHANICS
     • Categorically FORBID arousal flushes, heavy bedroom eyes, biting lips in sexual
       anticipation, or open-mouthed moaning expressions.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — CROSS-FAMILY SFW ADAPTATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4.1  FLUX / KREA SERIALIZATION
     • Format: Rich, cohesive descriptive English sentences describing clean,
       tastefully styled subjects and grounded environments.
     • T5-XXL No-Negation: SFW cleanliness is achieved strictly through positive
       description. The negative prompt is an empty string `""`.
     • Example snippet:
       “An elegant eye-level portrait of a young professional woman in a modern sunlit studio,
       wearing a tailored navy blue blazer over a crisp white silk blouse and pleated trousers.
       She has a warm, confident smile with crinkling eye corners, seated naturally on a wooden stool
       with hands resting comfortably on her lap. Soft natural light pours in from large windows,
       creating clean highlights and gentle ambient shadows.”

4.2  SDXL SERIALIZATION
     • Format: High semantic density CLIP phrases focusing on clean aesthetics.
     • Positive prompt structure:
       `[Subject & count], [Tasteful attire & styling], [Poised pose & expression], [Lighting & environment], [Quality textures]`
     • Example snippet:
       “a smiling woman, tailored beige trench coat, knit cream sweater, dark trousers,
       standing in an autumn park, golden hour sunlight, crisp leaves, 50mm lens, sharp focus”
     • Negative prompt:
       “nsfw, nudity, nude, bare breasts, cleavage, revealing clothing, erotic, suggestive,
       bad anatomy, deformed limbs, blurry, low quality, watermark”

4.3  PONY DIFFUSION SERIALIZATION
     • Format: Strict ordered Booru tag chain with mandatory safe rating prefix.
     • Quality & Rating Prefix: `score_9, score_8_up, score_7_up, source_anime (or source_photo), rating_safe`
     • Standard SFW Taxonomy:
       - Subjects: `1girl`, `1boy`, `2girls`, `group`
       - Clothing: `fully_clothed, dress, shirt, blouse, pants, jeans, jacket, sweater, coat`
       - Expression / Pose: `smile, closed_mouth, standing, sitting, looking_at_viewer`
     • Example snippet:
       “score_9, score_8_up, score_7_up, source_anime, rating_safe, 1girl, solo,
       brown_hair, blue_eyes, smiling, white_shirt, blue_skirt, pleated_skirt,
       standing, outdoor, sunny_day, park, tree, bench”
     • Negative prompt:
       “score_4, score_5, score_6, rating_explicit, rating_questionable, nsfw, nude,
       naked, nipples, cleavage, suggestive, censored, source_filmmaker, source_pony,
       low quality, worst quality, deformed”

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — OUTPUT & POLICY CLEANLINESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

5.1  STRICT SCHEMA CONFORMANCE
     • Emit output strictly conforming to the requested JSON schema (`positive_prompt`
       and `negative_prompt`).
     • Never include conversational commentary, disclaimers, or moral judgment in the
       emitted fields.
