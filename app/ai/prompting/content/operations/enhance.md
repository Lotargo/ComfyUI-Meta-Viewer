# Operation: enhance

Improve an existing prompt to fully express the user's stated wishes and the selected model family's style, without discarding the original creative intent.

## Required behavior

1. Start from the source prompt and expand it so every user wish is concretely represented in the positive prompt.
2. Strengthen detail, lighting, composition, and style vocabulary that the selected family and checkpoint profile handle well.
3. Keep the subject, count, action, relationships, setting, framing, and requested text unchanged unless a wish explicitly modifies them.
4. Preserve user-provided trigger words that belong to the selected checkpoint or extension.
5. Never invent checkpoint trigger words or claim unsupported capabilities.
6. Produce a complete negative prompt for families that use one (SDXL, Pony); keep the source negative prompt when it already fits, and leave it empty only for families that do not rely on it (Flux).
7. If no wishes are provided, polish the source prompt while strictly preserving its meaning.

## Failure patterns

- rewriting the prompt into a different image than the source described;
- dropping trusted trigger words or quality details;
- copying a negative prompt from another family unchanged when it conflicts with the target family;
- padding the prompt with generic filler instead of honoring the user's wishes;
- treating enhancement as a full rewrite that loses the original scene.

## Self-check

- Every stated wish maps to something in the final positive prompt.
- The scene and subject match the source; only clarity and style changed.
- The negative prompt matches the target family conventions.
- The final response follows the output contract exactly.
