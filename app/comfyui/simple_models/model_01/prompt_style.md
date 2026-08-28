# Per-model prompt style: Realistic Vision V6.0 B1

SYNTAX MODE: natural language + restrained quality tags.
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
Photorealistic checkpoint with a strong bias toward natural, photographic
imagery (people, skin texture, environments). It responds to descriptive
English sentences and is sensitive to style leakage into anime/cartoon.

## Positive prompt
- Write one coherent camera-style description in English.
- Lead with the subject and its main action, then add appearance, framing,
  environment, lighting, and lens language.
- Use natural-light, realistic photography vocabulary:
  cinematic lighting, shallow depth of field, 85mm portrait look,
  natural skin texture, film grain, realistic materials.
- You may prepend a short comma-list of high-impact quality tags
  (e.g. best quality, ultra detailed, realistic) BEFORE the description,
  but do not turn the whole prompt into tag soup.
- Never inject anime, cartoon, 3D render, or illustration terms unless the
  user explicitly asks for them.

## Negative prompt
Keep a solid technical negative to suppress CGI and artifacts, for example:
"deformed iris, deformed pupils, cgi, 3d, render, sketch, cartoon, drawing,
anime, text, cropped, out of frame, worst quality, low quality, jpeg
artifacts, bad anatomy, extra limbs, malformed hands, watermark".

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
