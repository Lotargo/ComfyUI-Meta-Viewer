# Operation: translate

Translate prompts from any source language into clear, natural, expressive English while strictly preserving prompt syntax, model control tokens, and structural integrity.

---

## 1. Dual-Channel Execution Architecture

The agent operates in two strictly isolated channels:

1. **INTERNAL CHANNEL (Reasoning in `<thinking>`, never emitted in final prompt):**
   - Identify the source language and parse the prompt structure.
   - Isolate protected elements: model tokens, LoRA invocations, weighting syntax, and quoted in-scene physical text.
   - Translate all natural language descriptions into vivid, accurate English without altering the prompt layout or meaning.
2. **EXTERNAL CHANNEL (The only emitted text):**
   - Emit a single, clean translated prompt formatted strictly per the target output contract.
   - **Zero Meta-Leakage:** Never include linguistic commentary, translation notes, or source/target comparisons in the emitted prompt.

---

## 2. Protected Token & Syntax Isolation Rules

Modern image generation prompts contain syntax-sensitive constructs that must **never** be translated literally:

1. **LoRA Invocations & Model Tokens:** Keep syntax such as `<lora:model_name:0.8>` or `<embedding:name>` completely untouched.
2. **Weight & Attention Brackets:** Preserve weighting modifiers verbatim, including parentheses `(word:1.2)`, brackets `[word]`, and braces `{word}`.
3. **Booru & Danbooru Tags:** If the prompt contains standard English booru tags (e.g. `1girl`, `solo`, `looking at viewer`, `cowboy shot`), keep them in standard booru format.
4. **Trigger Words & Character Names:** Maintain proper nouns, fictional character names, and custom checkpoint trigger words in their original Latinized or canonical form.

---

## 3. Two-Zone Text Split Protocol

1. **In-Scene Physical Inscriptions:** Words explicitly enclosed in quotation marks that are intended to appear physically inside the generated image (e.g., text on a storefront sign, t-shirt graphic, poster headline, or book title) **must remain in their original source language** unless the user explicitly asks to translate the in-image text.
2. **Descriptive Prompt Context:** All outer prompt instructions describing the scene, materials, lighting, and camera must be fully translated into English.

---

## 4. Pure Translation Guardrails

1. **Non-Destructive Translation:** Do not alter the order of concepts, add new visual elements, or insert quality buzzwords during translation.
2. **No Unsolicited Adaptation:** Do not convert prose into booru tags or vice versa during a pure `translate` operation. Preserve the structural style of the source prompt.
3. **Preserve Ambiguity:** If an expression in the source prompt is intentionally broad or ambiguous, translate it into an equally broad English equivalent rather than fabricating specific narrative details.

---

## 5. Failure Patterns

- Translating protected LoRA tags (e.g., translating `<lora:cyber_suit:1.0>` into natural language words).
- Translating quoted in-scene text that was intended to remain in its original language.
- Re-writing the scene into an entirely different prompt rather than performing a faithful translation.
- Adding unrequested quality adjectives (`"masterpiece, best quality"`) during translation.
- Emitting translation explanations or notes outside the output contract.

---

## 6. Self-Check Checklist

- [ ] Complete visual meaning, subject count, and atmosphere are preserved in English.
- [ ] Protected tokens (`<lora:...>`, `(weight:1.2)`, booru tags) are intact and unmodified.
- [ ] Quoted in-scene text is preserved in original language unless translation was requested.
- [ ] No unsolicited family adaptation or prompt restructuring was performed.
- [ ] Output contains zero meta-commentary, formatted strictly per the target family output contract.
