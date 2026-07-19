# Scenario: graphic design and visible text

Use for posters, covers, packaging, labels, cards, simple advertising layouts, booklet covers, and other images where typography is a central visual object.

## Capability boundary

Text rendering is model- and checkpoint-dependent. A strong prompt can improve layout and wording, but it cannot guarantee perfect spelling. Keep the result editable and do not claim deterministic typography.

For the first budget-oriented implementation:

- prefer one short headline and at most one or two short secondary text blocks;
- treat larger bodies of copy, paragraphs, tables, and dense booklet interiors as experimental;
- recommend separate layout or editing passes when exact long-form text matters.

This is a project heuristic, not a universal model token limit.

## Analysis

Determine:

- exact visible wording, including case, punctuation, and line breaks;
- which text is mandatory and which is decorative;
- hierarchy: headline, subtitle, label, caption, callout;
- placement, alignment, margins, and reading order;
- font category and visible letter treatment without inventing a specific licensed font;
- text colour, contrast, material, embossing, glow, print, or screen treatment;
- background complexity behind each text block;
- relationship between text, product, illustration, logo-like mark, and empty space;
- output format and aspect ratio when supplied.

## Construction rules

1. Quote every exact text block.
2. Describe each block separately with placement and hierarchy.
3. Keep mandatory wording short and visually separated.
4. Reserve clean negative space behind critical text.
5. State reading order and alignment when layout matters.
6. Do not ask the model to invent legal copy, addresses, prices, specifications, or long paragraphs.
7. If the source image contains uncertain text, preserve uncertainty rather than replacing it with plausible advertising copy.
8. For a booklet, distinguish cover generation from interior page layout. A cover may be generated as one image; text-heavy interior pages should use a later editing or compositing stage.

## Good pattern

`vertical perfume poster, bottle centered in the lower half, exact headline "LUMIERE" at the top in widely spaced elegant serif lettering, short subtitle "EAU DE PARFUM" below it, generous empty space, warm beige background, soft gold edge light, no other text`

## Bad pattern

`luxury perfume ad with lots of elegant marketing text, ingredients, price, slogan, website, product description, beautiful typography`

The bad pattern does not define exact wording, hierarchy, placement, or a realistic text budget.

## Self-check

- Every mandatory text block is quoted exactly.
- No unrequested copy was invented.
- Headline, secondary text, placement, and reading order are clear.
- Critical text has simple visual space behind it.
- The amount of text matches the target model's tested capability.
- Long-form exact copy is deferred to editing when necessary.
