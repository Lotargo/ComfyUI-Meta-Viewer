# Operation: generate

Create a new image-generation prompt from the user's request.

## Required behavior

1. Preserve the user's central idea, subject, requested action, mood, and constraints.
2. Fill only visual details that make the scene executable: framing, placement, materials, lighting, environment, and style.
3. Do not silently replace the requested subject, setting, medium, or visual direction.
4. Separate confirmed user requirements from reasonable visual completion.
5. Use the selected family base and scenario manifest for syntax and ordering.
6. Keep the result editable. Do not hide uncertainty behind decorative language.

## Failure patterns

- turning a simple request into an unrelated elaborate story;
- adding extra people, objects, text, or scenery without a visual reason;
- copying an example instead of adapting it;
- using generic quality praise instead of visible details;
- returning commentary outside the output contract.

## Self-check

- The central request is still recognisable.
- Added details support the scene rather than changing it.
- The selected family syntax is respected.
- The selected scenario rules are present.
- The final response follows the output contract exactly.
