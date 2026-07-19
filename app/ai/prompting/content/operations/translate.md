# Operation: translate

Translate the prompt into the requested language while preserving meaning and structure.

## Required behavior

1. Preserve subject count, action, relationships, composition, visual style, materials, colours, lighting, and visible text.
2. Do not adapt syntax to another model family unless the task also explicitly requests the separate `adapt` operation.
3. Preserve model tokens, LoRA triggers, checkpoint triggers, weights, delimiters, and syntax that should not be translated.
4. Preserve exact text intended to appear inside the generated image unless the user explicitly asks to translate that visible text.
5. Keep ambiguous source wording ambiguous rather than silently choosing a new interpretation.

## Failure patterns

- rewriting instead of translating;
- changing prompt order or family syntax without instruction;
- translating trigger tokens;
- translating quoted text that must remain visible in its original language;
- adding quality terms or new visual details.

## Self-check

- Meaning and constraints are unchanged.
- Protected tokens and quoted visible text are preserved.
- No family adaptation was performed accidentally.
- The final response follows the output contract exactly.
