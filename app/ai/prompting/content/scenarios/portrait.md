# Scenario: portrait

Use for a single person or creature when the face, expression micro-mechanics, head, shoulders, or upper body is the main visual subject.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — ANALYSIS & DECONSTRUCTION
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Before constructing the prompt, determine:

1. IDENTITY & ETHNIC ANCHOR:
   - one primary subject, exact ethnicity prior, facial bone structure, skin undertones,
     hair texture and styling, eyes, and distinguishing marks (freckles, beauty marks).
2. EXPRESSION MICRO-MECHANICS:
   - eyelid aperture, pupil focus, micro-folds at eye corners (Duchenne smile),
     lip curvature, jaw tension, and physiological skin reaction.
3. HEAD & SHOULDER POSE:
   - head yaw/pitch/roll, neck turn angle, chin lift/tuck, shoulder tilt, and posture.
4. CROP & OPTICS:
   - shot size (extreme close-up, close-up, bust, head-and-shoulders crop);
   - camera elevation, lens focal length (e.g. 85mm prime lens look, natural spatial compression,
     soft aesthetic focus falloff).
5. LIGHTING & SUBSURFACE SCATTERING:
   - key light direction, fill, catchlights in the pupils, rim illumination,
     and natural subsurface scattering (SSS) along skin edges.
6. BACKGROUND & SEPARATION:
   - shallow depth of field, restrained background texture, and clear subject separation.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — EXPRESSION MICRO-MECHANICS & PHYSIOLOGY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  ZERO-ABSTRACT-EMOTION RULE
     • Never rely on flat emotional adjectives (“happy”, “sad”, “angry”).
     • Pair every state with physical facial micro-cues:
       - Warm Genuine Smile (Duchenne): “gentle micro-lift at mouth corners, soft relaxed lips,
         squinting outer eye corners with crinkling micro-folds, warm engaged gaze”.
       - Contemplative / Serene: “relaxed jawline, soft neutral mouth, calm steady eye focus,
         serene facial musculature”.
       - Playful / Inquisitive: “asymmetrical single-corner lip lift, raised single eyebrow,
         mischievous sparkle in the eyes, subtly tilted chin”.
       - Intense / Focused: “subtly narrowed eye aperture, direct locked pupil focus, firm jawline”.

2.2  BLUSH ANTI-PAINT RULE & SUBSURFACE SCATTERING (SSS)
     • Describe blush/flush ONLY when visibly present or implied by context.
     • FORBID opaque, clown-like red paint smears (“vivid red spots”, “blooming paint blush”).
     • Render flush strictly as **translucent subsurface scattering**:
       “natural subsurface scattering along flushed cheekbones, realistic micro-circulation
       redness beneath the skin surface, faint rosy translucency”.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — 9 LOCKED ETHNICITIES & 3-TIER LIKENESS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3.1  MANDATORY ETHNICITY PROTOCOL
     Lock exact recognized ethnicity from visual evidence to avoid generic drift:
     1. East Asian: “East Asian facial features, smooth porcelain/fair skin tone, dark raven hair,
        expressive almond-shaped eyes”.
     2. South / Southeast Asian: “South/Southeast Asian descent, warm golden/caramel skin tone,
        dark silky hair, rich brown expressive eyes”.
     3. Slavic / Eastern European: “Slavic facial features, Eastern European descent, high cheekbones,
        fair skin, soft natural undertones”.
     4. Nordic / Scandinavian: “Scandinavian features, fair porcelain skin, natural blonde/platinum hair,
        clear blue eyes”.
     5. Mediterranean / Southern European: “Mediterranean/Italian descent, warm olive skin tone,
        dark wavy hair, expressive hazel/brown eyes”.
     6. Celtic / British Isles: “Celtic/Irish descent, fair pale skin with subtle light freckles,
        natural red/auburn hair, green eyes”.
     7. Latina / Hispanic: “Latina heritage, warm golden-tan skin tone, dark voluminous wavy hair,
        deep brown eyes”.
     8. Middle Eastern / Levantine / Persian: “Middle Eastern/Levantine features, smooth olive skin,
        dark raven hair, deep brown eyes”.
     9. Afro-descendant / Afro-Latina: “Afro-Latina / African-American descent, rich dark bronze skin tone,
        natural curly hair texture, striking features”.

3.2  3-TIER LIKENESS PRIOR
     1. Confirmed Celebrity: If definitively identified, use the name as likeness anchor (“likeness of Margot Robbie”).
     2. Look-Alike Prior: If resemblance exists, state corrections (“resembling [Celebrity] but with narrower jawline,
        different eye shape”).
     3. Unknown / Pure Traits: Describe purely via physical traits (ethnicity, facial structure, skin, hair, eyes).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — CONSTRUCTION RULES & PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Keep one clear focal subject.
2. Put identity, expression, gaze, and head/shoulder pose before decorative background details.
3. Describe visible asymmetry, skin texture, and distinguishing features rather than generic beauty terms.
4. Match detail to the crop. Do not describe shoes or full-body pose in a close portrait.
5. Describe light by direction and visible effect on facial contours and materials.
6. Use lens and depth-of-field language (e.g. 85mm prime lens, organic falloff) to support subject isolation.
7. Keep the background subordinate unless an environmental portrait is explicitly requested.

GOOD PATTERN:
`single subject + expression and gaze + visible appearance + head/shoulder pose + crop and angle + light behavior + restrained background + medium/style`

BAD PATTERN:
`masterpiece, beautiful person, perfect face, 8k, detailed eyes, cinematic, best quality`

SELF-CHECK:
- Exactly one primary portrait single subject is described.
- Expression, gaze, crop, and head/shoulder pose are explicit.
- Visible appearance details match what the camera can see without full-body hallucination.
- Lighting describes direction and visible subsurface scattering effect.
- Background details do not overpower the focal subject.
