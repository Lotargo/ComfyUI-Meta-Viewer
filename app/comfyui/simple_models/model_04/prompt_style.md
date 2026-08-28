# Per-model prompt style: Moody Krea 2 Mix V7.0 FP8

SYNTAX MODE: natural language (Qwen3-VL text encoder).
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
A Krea-2-Family photorealistic model (Qwen3-VL text encoder + Qwen image VAE).
It is designed for natural, detailed English descriptions and benefits from a
strong moody/cinematic photographic direction. It does not use score tokens or
danbooru tag soup.

## Positive prompt
- Write a rich, descriptive English paragraph (not tag soup).
- Structure: subject and main action, then appearance, atmosphere, framing,
  environment, lighting, and photographic medium.
- The model is especially good with atmosphere-driven directions: moody
  lighting, desaturated color grade, cinematic contrast, film grain,
  dramatic shadows, atmospheric haze.
- Prefer concrete visual facts over generic quality buzzwords.
- Do not prepend Pony/sdxl score tags or quality-token prefixes.

## Negative prompt
- Normally leave empty; describe the desired visual alternative in the
  positive prompt instead. Only add concise exclusions for clear defects
  when needed.

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
