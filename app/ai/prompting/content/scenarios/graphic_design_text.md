# Scenario: graphic_design_text (Typography & Graphic Design Engine)

Use for posters, covers, packaging, labels, cards, commercial advertising layouts, booklet covers, and images where typography and graphic layout are central visual objects.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 1 — CAPABILITY BOUNDARY & REALISTIC TEXT BUDGET
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

Text rendering is model- and checkpoint-dependent. A strong prompt can improve layout, letterforms, and casing, but do not claim deterministic typography.

• Practical Text Budget:
  - Prefer one short headline and at most one or two short secondary text blocks.
  - Quote every exact text block with explicit casing and font hints.
  - Treat large paragraphs, dense tables, and booklet interiors as separate post-processing passes.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 2 — TWO-ZONE TEXT SPLIT
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

2.1  IN-SCENE TEXT (PHYSICAL OBJECTS — ALWAYS PRESERVE)
     • Physical inscriptions embedded on objects inside the world: prints on clothing,
       storefront signage, license plates, vehicle decals, product labels, mug inscriptions,
       street posters.
     • Transcribe verbatim with casing, language, and physical material hints.

2.2  GRAPHIC DESIGN OVERLAYS (ARTISTIC — ON EXPLICIT REQUEST)
     • Brand logos, advertising slogans, poster plaques, magazine mastheads, platform badges.
     • Rendered on explicit user request or when creating a poster/packaging layout.

2.3  SCREENSHOT TECHNICAL GARBAGE (OMIT VIA SILENCE)
     • Technical artifacts (player buttons, scrub bars, subtitles, URL bars, OS chrome)
       are completely ignored and omitted through complete silence (T5 No-Negation rule).

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 3 — FLUX & KREA STRICT SYNTAX RULES (ANTI-ERROR)
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

3.1  BAN ON TECHNICAL SEPARATORS INSIDE QUOTES
     • Categorically FORBIDDEN to use `//`, `|`, `_`, or `#` inside quoted text strings.
     • Incorrect: `"BRAND // PREMIUM"`
     • Correct: `"BRAND" on the left and "PREMIUM" on the right in bold sans-serif lettering`.

3.2  MANDATORY CASING CONTROL (CASING LOCK)
     • For every textual element, explicitly specify the casing rule:
       - `strictly in ALL CAPS` (all uppercase)
       - `strictly in lowercase` (all lowercase)
       - `Title Case` (initial capitalization)

3.3  PRECISE CANVAS POSITIONING & BODY PROTECTION
     • Always specify exact canvas coordinates:
       `positioned near the top-center border`, `aligned to the lower-right margin`,
       `anchored to the bottom edge`.
     • Body Protection Guardrail (CRITICAL):
       To prevent text overlapping the character's face or body, append:
       “rendered strictly on the background, completely clear of the character's body and face”.

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 4 — FONTS, MATERIALS & EFFECTS LIBRARY
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

• Font Categorization Hints:
  - `thin, elegant, high-contrast serif typeface, similar to Didot` (luxury/fashion)
  - `bold, clean, condensed sans-serif typeface, similar to Helvetica` (modern/industrial/sport)
  - `fluid retro cursive neon script` (neon/retro bar)
  - `heavy, distressed gothic typeface with cracked texture` (grunge/metal)

• Material & Graphic Effects:
  - `neon glow with a soft cyan light aura`
  - `embossed gold metallic foil with subtle specular highlights`
  - `semi-translucent white with 50% opacity`
  - `enclosed inside a bright, rounded orange-yellow rectangular badge`

━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
SECTION 5 — CONSTRUCTION RULES & PATTERNS
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

1. Quote every exact text block.
2. Describe each block separately with placement and hierarchy (headline, subtitle, callout).
3. Keep mandatory wording short and visually separated.
4. Reserve clean negative space behind critical text blocks.
5. State reading order and alignment when layout matters.
6. Do not ask the model to invent legal copy, addresses, prices, or paragraphs.
7. For a booklet, distinguish cover generation from interior page layout.

GOOD PATTERN:
`vertical perfume poster, bottle centered in the lower half, exact headline "LUMIERE" at the top in widely spaced elegant serif lettering strictly in ALL CAPS, short subtitle "EAU DE PARFUM" below it, Reserve clean negative space, warm beige background, soft gold edge light, one short headline, do not claim deterministic typography`

BAD PATTERN:
`luxury perfume ad with lots of marketing copy, website URL, price, slogan, beautiful typography`

SELF-CHECK:
- Every mandatory text block is quoted exactly with casing specified.
- Headline, secondary text, placement and hierarchy, and reading order are clear.
- Critical text has simple negative space behind it, completely clear of character bodies.
- Separators `//`, `|`, `_`, `#` are not placed inside quoted text.
