# Per-model prompt style: CyberRealistic Pony v18.0 CoreShift

SYNTAX MODE: Pony score tags + natural language.
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
A Pony-family photorealistic checkpoint. It is score-tag driven and relies on
the standard Pony quality tokens (`score_9`, `score_8_up`, `score_7_up`) at the
start of the positive prompt to steer quality.

## Positive prompt
- Always begin the positive prompt with:
  `score_9, score_8_up, score_7_up` (the launcher already prepends this
  prefix; do not duplicate it).
- After the score tokens, write a natural English description of the subject,
  action, framing, environment, lighting, and photographic detail.
- Character/style definitions are commonly expressed as Pony tags
  (e.g. "photorealistic, cinematic lighting, detailed face") followed by the
  scene description in prose.
- Keep the model within photographic realism unless the user requests a
  stylized/anime look, which Pony also supports.

## Negative prompt
- Produce a complete Pony-appropriate negative that excludes quality defects
  and CGI leakage, for example: "worst quality, low quality, jpeg artifacts,
  cgi, render, cartoon, deformed, bad anatomy, extra limbs, watermark".
- Do not reuse an SDXL natural-style negative that conflicts with Pony
  conventions.

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
