# Operation: reconstruct

Reconstruct an image-generation prompt from an image analysis or `SceneSpec`.

## Evidence rules

1. Treat visible and high-confidence details as observed evidence.
2. Keep uncertain details uncertain; do not convert guesses into facts.
3. Do not invent hidden body parts, unreadable text, off-frame objects, brands, locations, or identities.
4. Preserve subject count, relative positions, interaction, framing, camera angle, lighting, background, and visible text.
5. When exact wording is uncertain, keep it in `uncertain_details` rather than fabricating a replacement.
6. Use the selected family and scenario only to express the scene, not to redesign it.

## Reconstruction priorities

1. subject identity and count;
2. action and spatial relationships;
3. composition and camera;
4. clothing, materials, surfaces, and colours;
5. lighting and environment;
6. style or medium;
7. exact visible text and layout when present.

## Failure patterns

- writing a prettier but different scene;
- adding common genre elements that are not visible;
- replacing uncertain text with plausible invented copy;
- losing the original framing while preserving minor details;
- mixing analysis commentary into the final prompt.

## Self-check

- Every important prompt detail is supported by the input or marked uncertain.
- Subject count and placement match the source.
- Visible text is copied exactly when confidence is sufficient.
- No unseen narrative detail was added.
- The final response follows the output contract exactly.
