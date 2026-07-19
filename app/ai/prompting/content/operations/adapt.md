# Operation: adapt

Adapt an existing prompt to the selected model family or checkpoint profile without changing its creative intent.

## Required behavior

1. Preserve the subject, count, action, relationships, setting, framing, lighting, style, and requested text.
2. Change syntax, ordering, negative-prompt strategy, and supported control tokens only where the target profile requires it.
3. Preserve user-provided trigger words when they belong to the selected checkpoint or extension.
4. Never invent checkpoint trigger words or claim unsupported capabilities.
5. Remove source-family boilerplate only when it is meaningless or harmful for the target family.
6. Keep details that carry visual meaning even when their original wording changes.

## Failure patterns

- treating adaptation as unrestricted prompt improvement;
- changing the character, scene, clothing, mood, or composition;
- discarding a trusted trigger because it resembles a quality token;
- copying source-family negative prompts into a family that does not use them;
- translating words while leaving the wrong family syntax unchanged.

## Self-check

- The adapted result describes the same intended image.
- Only family/checkpoint syntax and supported controls changed.
- Trusted triggers are preserved.
- Unsupported source conventions are removed or transformed.
- The final response follows the output contract exactly.
