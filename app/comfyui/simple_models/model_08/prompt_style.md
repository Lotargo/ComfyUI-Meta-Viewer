# Per-model prompt style: LunarCherryMix Illustrious v2.4

SYNTAX MODE: danbooru tag list (Illustrious/painter booru style).
OUTPUT LANGUAGE: all tags and descriptions MUST be written in English.

## What this model is
An SDXL anime checkpoint in the Illustrious family, trained on booru tag data
with a painterly, detailed art style. It responds to comma-separated booru
tags and quality tags, with a strong emphasis on expressive anime characters.

## Positive prompt
- Build a comma-separated English booru tag list.
- Conventional order:
  1. Quality tags: `masterpiece, best quality, amazing quality`.
  2. Character/rating: `1girl, solo, detailed face`.
  3. Appearance: `silver hair, heterochromia, long hair`.
  4. Apparel/accessories: `modern clothes, jacket, choker`.
  5. Pose/emotion/action: `standing, looking at viewer, gentle smile`.
  6. Background/environment: `night city, neon lights, detailed background`.
  7. Style tags last: `painterly style, illustration, soft lighting`.
- Keep tags specific and minimal; do not write prose in the positive prompt.

## Negative prompt
- Provide a complete technical negative: "worst quality, low quality, bad
  anatomy, bad hands, missing fingers, extra digits, fused fingers, jpeg
  artifacts, watermark, blurry".

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
