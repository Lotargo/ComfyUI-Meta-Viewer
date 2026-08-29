# Output contract: PromptResult v1

Return a single strict JSON object and nothing else.

```json
{
  "schema_version": "1",
  "positive_prompt": "...",
  "negative_prompt": "..."
}
```

## Contract Rules

1. `schema_version` must be exactly `"1"`.
2. `positive_prompt` must be a non-empty, serialized string adhering to the target family base profile and scenario manifest.
3. `negative_prompt` must always be present as a string:
   - For **FLUX / Chroma**: Always leave as an empty string `""` per the **T5-XXL No-Negation Rule**.
   - For **SDXL**: Provide a concise, targeted negative prompt removing specific defects and conflicting styles.
   - For **PONY**: Provide the standard author booru score/rating negative chain or leave empty `""`.
4. **Zero Meta-Leakage:** Strictly forbid leaking internal reasoning markers, planning notes, or system tags (e.g., `Scene Map =`, `garment_stack`, `L0:`, `L1:`, `L2:`, `L3:`, `L4:`, `Passport 0B:`, `Passport 0C:`, `KEEP_EXACT`, `INTIMACY_DIAL`, `WARDROBE_DELTA`) into either prompt field.
5. **Zero Conversational Filler:** Do not include conversational preambles (e.g. `"Here is your prompt:"`), markdown explanations, code fences outside the raw JSON object, or alternative options.
6. Escape quotation marks and line breaks so the response remains valid JSON.
