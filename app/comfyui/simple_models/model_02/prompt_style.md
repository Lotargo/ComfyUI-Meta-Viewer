# Per-model prompt style: Juggernaut XL Ragnarok

SYNTAX MODE: natural language.
OUTPUT LANGUAGE: all prompts MUST be written in English.

## What this model is
A very high-quality photorealistic SDXL checkpoint known for well-composed,
detailed photography with excellent lighting and skin rendering. It handles
both people and environments gracefully using descriptive language.

## Positive prompt
- Write natural, descriptive English sentences (not tag soup).
- Structure: primary subject and action first, then appearance, wardrobe,
  pose, framing, environment, lighting, and lens/medium.
- Use rich but concrete photography vocabulary: golden hour, rim light,
  softbox key light, 35mm environmental portrait, shallow depth of field,
  natural skin detail, cinematic color grade.
- Prefer concrete visual facts over generic praise ("masterpiece", "8k").
- You may open with a short set of quality tags if it helps, but the bulk
  must remain connected prose.

## Negative prompt
- Leave empty unless the user supplies one or a specific defect must be
  excluded. Do not copy unrelated families' negatives.

## Output contract
Return strict JSON with English `positive_prompt` and `negative_prompt`.
