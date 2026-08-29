# Scenario: illustration_art (Comprehensive Medium & Style Engine)

Use for editorial, narrative, decorative, anime, manga, comic, traditional, and concept illustrations where shape language, medium, palette, stylisation, and visual storytelling matter more than photographic realism.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — MEDIUM SEPARATION GUARDRAIL
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Categorically FORBID importing photographic terminology into non-photographic artwork.
• FORBIDDEN in illustration/anime prompts: “photorealistic”, “hyperrealistic”, “real skin pores”,
  “camera lens”, “85mm lens look”, “ISO analog film grain”, “raw photo”, “DSLR”.
• INSTEAD describe medium-native techniques: line weight, cross-hatching, cel shading,
  halftone screentones, gouache texture, impasto brushwork, or watercolor washes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — STYLE & MEDIUM TAXONOMY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  ANIME & MANGA
     • 90s Retro Cel:
       “vintage hand-painted 90s anime cel, soft chromatic bloom, warm filmic color palette,
       hand-painted watercolor background scenery”.
       (Pony: `retro artstyle, 1990s (style), cel anime`)
     • Modern High-End Digital (Ufotable-style):
       “crisp vector lineart with dynamic line weight, digital compositing, volumetric particle bloom,
       rich cell gradients, vibrant digital lighting”.
       (Pony: `modern anime, digital illustration, ufotable (style)`)
     • Painterly / Ghibli Aesthetic:
       “storybook gouache painterly background, soft edge falloff, warm nostalgic color palette,
       delicate traditional brush textures”.
       (Pony: `ghibli (style), watercolor (medium), traditional media`)
     • Dynamic Action / Trigger Style:
       “bold angular contours, dynamic forced perspective distortion, kinetic smears, high-energy composition”.
       (Pony: `trigger (style), dynamic angle, stylized`)
     • B&W Manga Screentone:
       “black and white manga panel with fine screentone, crisp black ink lineart, halftone dot patterns,
       dramatic cross-hatching, dynamic speed lines”.
       (Pony: `monochrome, screentone, manga, lineart`)
     • Korean Manhwa / Webtoon:
       “high-polish digital webtoon aesthetic, clean digital lines, smooth cell gradients, glowing lighting accents”.
       (Pony: `manhwa, webtoon, digital drawing`)

2.2  COMICS & GRAPHIC NOVELS
     • American Golden/Silver Age:
       “vintage comic book panel with visible Ben-Day dots, heavy black inking, 4-color print offset alignment,
       aged pulp paper texture”.
       (Pony: `comic, american comic, vintage comic`)
     • Modern Inked Noir:
       “stark black ink shadows, heavy black pooling, high-contrast comic inking, gritty texture, moody silhouettes”.
       (Pony: `ink (medium), high contrast, noir`)
     • Franco-Belgian Ligne Claire (Clear Line):
       “clear line French comic style with flat colors, uniform clean line weight, zero hatching,
       precise architectural clarity”.
       (Pony: `ligne claire, comic, clean line`)

2.3  TRADITIONAL ART & 3D
     • Dark Fantasy Oil Painting:
       “classical oil on canvas with heavy impasto strokes, rich chiaroscuro lighting, tactile canvas texture,
       warm varnish patina”.
       (Pony: `oil painting (medium), traditional media, painterly`)
     • Watercolor & Wash:
       “delicate translucent watercolor wash with organic bleeds, wet-on-wet pigment diffusion, cold-press paper grain”.
       (Pony: `watercolor (medium), traditional media`)
     • Concept Art (Digital Matte):
       “cinematic matte painting with focused digital detail, textured brushwork, focal atmospheric haze”.
       (Pony: `concept art, digital painting, artstation`)
     • 3D Stylized CGI:
       “stylized 3D character render, sculpted stylized geometry, clean subsurface scattering, soft ambient occlusion”.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — CONSTRUCTION RULES
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. State the subject, narrative moment, setting, and story beat before decorative style labels.
2. Define a readable focal hierarchy through placement, scale, silhouette, value, colour, and overlap.
3. Translate abstract moods (cosy, playful, eerie, whimsical, solemn, magical) into visible shapes, palette, lighting, gesture, and environmental cues. When several mood directions are requested, keep each one separately traceable in the prompt with its own visible design evidence.
4. Choose a coherent medium and describe marks, edges, pigment, paper, layering, or print behaviour that the medium can actually produce.
5. Use shape language consistently across characters, architecture, props, foliage, and ornament.
6. Distinguish deliberate stylisation from anatomy, perspective, or continuity errors.
7. Keep foreground, middle ground, and background readable even when perspective is flattened or decorative.
8. Add secondary motifs only when they reinforce the narrative, rhythm, scale, or eye path.
9. Preserve requested cultural, historical, and genre details; do not replace them with a generic fantasy aesthetic.
10. Avoid empty quality slogans, contradictory media, accidental photorealism, uniform detail, and noisy ornament.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — PATTERNS & SELF-CHECK
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

GOOD PATTERN:
`subject and narrative action + setting and story beat + composition and focal hierarchy + shape language + coherent medium and mark-making + palette and value structure + motivated light + supporting motifs + intended mood`

BAD PATTERN:
`masterpiece whimsical illustration, magical, beautiful, ultra detailed, trending art, 8k, best quality`

SELF-CHECK:
- The subject, action, setting, and narrative moment are immediately readable.
- Focal hierarchy, silhouettes, overlaps, and eye path survive at thumbnail size.
- Shape language and stylisation remain consistent across the image.
- Choose a coherent medium where marks, edges, texture, and colour behaviour agree with one another.
- Every requested mood direction is separately traceable with its own visible design evidence rather than an adjective alone.
- Secondary detail supports the story and does not compete with the focal subject.
