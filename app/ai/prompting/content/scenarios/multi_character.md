# Scenario: multi_character (Spatial Anchoring & Anti-Cloning Engine)

Use for scenes containing two or more distinct individuals, small groups (2–5 people), or crowd scenes (6+ people) where spatial placement, distinct identities, anti-cloning, interactive biomechanics, and clear block partitioning are critical.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — SPATIAL ANCHORING & BLOCK PARTITIONING
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1.1  STRICT SPATIAL PARTITIONING
     • Categorically avoid mingling character descriptions into a single ambiguous clause.
     • Anchor each character to an explicit canvas position:
       “On the left, [Character A]... On the right, [Character B]...”,
       “In the center foreground, [Character A]... Standing behind and slightly to the right, [Character B]...”.

1.2  SEQUENTIAL COMPLETE CHARACTER BLOCKS
     • Describe each character as a complete self-contained descriptive unit:
       `[Spatial Position] + [Identity & Ethnicity] + [Face & Hair] + [Build] + [Pose & Biomechanics] + [Wardrobe & Accessories]`
     • Complete the description of Character A entirely before initiating Character B.
       This prevents cross-character feature bleeding, fused outfits, and extra limbs.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — 2-TIER ANTI-CLONING PROTOCOL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  SMALL GROUP (2–5 CHARACTERS — INDIVIDUAL DIVERSIFICATION)
     • Every person MUST have distinct, individually specified visual traits:
       - Hair: distinct length, texture (`straight / wavy / curly`), color, bangs, and part.
       - Facial Structure: distinct eye shape, nose bridge, lip fullness, and skin undertones.
       - Body Build: distinct height, shoulder width, and frame proportions.
       - Wardrobe: distinct garment items, fabric textures, and contrasting color palettes.
     • Categorically FORBID identical cloned faces or duplicated outfits.

2.2  LARGE GROUP / CROWD (6+ CHARACTERS — LAYERED DIVERSITY)
     • Do NOT enumerate each person individually (to prevent token overflow).
     • Describe crowd diversity as a structured group:
       “a diverse group of ~N distinct individuals with varied hair colors, different heights and builds,
       and varied clothing styles — no cloned faces, no duplicated outfits”.
     • Add Count Anchors (“exactly N people”, “N distinct faces”) and Depth Layers
       (“front row / middle / back rows”) to prevent subject fusing.

2.3  TWINS EXCEPTION (THE ONLY EXCEPTION FOR CLONING)
     • If identical twins are explicitly requested or verified:
       explicitly state “identical twins, matching facial features, same hairstyle and outfit,
       standing side by side”.
     • In all other cases, individual diversification is strictly mandatory.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — INTERACTIVE BIOMECHANICS & GAZE VECTORS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3.1  PHYSICAL CONTACT POINTS
     • Explicitly anchor physical interactions:
       “Character A's right hand rests firmly on Character B's shoulder”,
       “both characters walking side-by-side with shoulders gently brushing”.

3.2  GAZE VECTOR LOCKING
     • Clearly define gaze direction for each subject:
       mutual eye contact (“looking directly into each other's eyes”),
       directed gaze (“Character A looks at Character B while Character B looks at the camera”),
       or environmental focus (“both gazing toward the horizon”).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — CROSS-FAMILY SERIALIZATION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

4.1  FLUX / KREA SERIALIZATION
     • Multi-paragraph spatial narrative structure:
       Base block establishes camera, setting, and spatial layout of both subjects.
       Detail blocks describe Character A and Character B in distinct descriptive sentences.
     • Example snippet:
       “A wide cinematic eye-level two-shot on a 35mm lens with natural depth of field,
       capturing two distinct colleagues standing in a sunlit architectural office.
       On the left, a tall woman of East Asian descent with straight black hair in a sleek bob...
       On the right, a man of Mediterranean descent with wavy dark hair and a neatly trimmed beard...
       Soft natural light illuminates both subjects with grounded contact shadows on the hardwood floor.”

4.2  SDXL SERIALIZATION
     • Compact spatial clauses with clear subject count anchors:
       “two detectives in an alley, man on left in trench coat holding flashlight,
       woman on right in dark jacket crouching near cobblestones, volumetric rain, 35mm lens”

4.3  PONY DIFFUSION SERIALIZATION
     • Strict subject count tags (`2girls`, `1girl, 1boy`, `2boys`, `group`), followed by
       spatial position tags and distinct attribute clusters:
       `score_9, score_8_up, score_7_up, source_anime, rating_safe, 2girls, standing, on_left, blonde_hair, blue_eyes, white_dress, on_right, black_hair, red_eyes, black_jacket, outdoors, daylight`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — CONSTRUCTION RULES & PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Establish total subject count and broad composition before describing individual figures.
2. Spatially anchor each character (left, right, center, foreground, background).
3. Enforce the Anti-Cloning Protocol: distinct faces, hair, builds, and clothing for small groups (2–5).
4. Organize crowd scenes (6+) into depth layers with count anchors.
5. Define mutual interaction, contact points, and gaze vectors explicitly.
6. Isolate character blocks to prevent feature bleeding.

GOOD PATTERN:
`total subject count + spatial layout + Character A [position + identity + pose + wardrobe] + Character B [position + identity + pose + wardrobe] + mutual interaction and gaze + grounded environment + motivated light`

BAD PATTERN:
`masterpiece, two beautiful people, detailed faces, epic scene, 8k, best quality`

SELF-CHECK:
- Total subject count and spatial positions (left/right/center) are explicitly defined.
- Each character in a small group (2–5) has distinct hair, facial structure, build, and wardrobe.
- No cloned faces or duplicated outfits appear unless the twins exception is validated.
- Physical contact points and gaze vectors are clear and physically plausible.
- Character blocks are sequentially separated without feature bleeding.
