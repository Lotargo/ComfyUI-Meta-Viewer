# Per-model prompt style: WAI-ANIMA v1.0

SYNTAX MODE: natural language (Qwen 3 0.6B text encoder).
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
An anime/illustration checkpoint built on the Anima architecture (Qwen 3 0.6B
text encoder + Qwen image VAE). It prefers descriptive English over the classic
danbooru long tag lists used by older SDXL anime checkpoints.

## Positive prompt
- Write a clear, natural English description of the anime scene.
- Structure: character and action, then character design (hair, eyes,
  clothing), mood/expression, composition, background, lighting, and style
  (anime illustration, soft shading, cel shading, detailed line art).
- Use descriptive language rather than massive tag dumps; short style tags
  are acceptable if they carry meaning, but keep the request readable.
- Match the intended art style explicitly (e.g. "clean anime style with
  vibrant colors and soft gradients").

## Negative prompt
- Add concise exclusions only for clear defects (extra limbs, bad anatomy,
  low quality, watermark) when appropriate; otherwise leave empty.

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
