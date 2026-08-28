# Per-model prompt style: Animagine XL 3.1

SYNTAX MODE: danbooru tag list (booru-style).
OUTPUT LANGUAGE: all tags and descriptions MUST be written in English.

## What this model is
An SDXL anime checkpoint fine-tuned on booru (danbooru) tag data. It responds
primarily to comma-separated booru tags and quality tags, not long prose.

## Positive prompt
- Build a comma-separated English booru tag list.
- Conventional tag order:
  1. Quality/rating tags first if desired: `masterpiece, best quality`.
  2. Subject and character-defining tags: `1girl, solo, long hair,
     blue eyes`.
  3. Appearance/apparel tags: `school uniform, white shirt, red skirt`.
  4. Pose/action/emotion tags: `sitting, looking at viewer, smile`.
  5. Background/environment tags: `classroom, outdoors, cherry blossom`.
  6. Style tags last: `anime screencap style, detailed background, soft
     shading`.
- Use the model's known quality tokens (e.g. `masterpiece, best quality`)
  and avoid over-long generic praise.
- Keep tags terse and specific; avoid full sentences in the positive prompt.

## Negative prompt
- Provide a complete technical negative covering common defects and anatomy
  errors, e.g. "worst quality, low quality, bad anatomy, bad hands, missing
  fingers, extra digits, jpeg artifacts, watermark".

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
