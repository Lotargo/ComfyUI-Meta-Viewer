# Per-model prompt style: GonzaLomo Chroma v3.0 FP8

SYNTAX MODE: natural language (FLAN-T5 XXL text encoder).
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
A chromatic, film-inspired photorealistic model in the Chroma/Flux family
(FLAN-T5 XXL text encoder + Flux/Chroma AE VAE). It is steered with natural
English descriptions, especially rich color and film-character vocabulary.

## Positive prompt
- Write one coherent, descriptive English paragraph (not tag soup).
- Structure: subject and action, then appearance, framing, environment,
  lighting, and color/film medium.
- The model excels with pronounced color and film characteristics:
  kodak color palette, film grain, cinematic color science, vibrant but
  natural saturation, halation, analog film look.
- Emphasize concrete visual and color facts over generic quality words.
- Do not use score tokens or danbooru tag lists.

## Negative prompt
- Leave empty unless a specific defect must be excluded; state the desired
  alternative in the positive prompt instead.

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
