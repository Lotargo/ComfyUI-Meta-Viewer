# Output contract: PromptResult v1

Return strict JSON and nothing else.

```json
{
  "schema_version": "1",
  "positive_prompt": "...",
  "negative_prompt": "..."
}
```

## Rules

- `schema_version` must be exactly `"1"`.
- `positive_prompt` must be a non-empty string.
- `negative_prompt` must always be present; use an empty string when the selected family or task does not need one.
- Do not add analysis, markdown fences, comments, warnings, alternative versions, or extra keys.
- Escape quotation marks and line breaks so the response remains valid JSON.
