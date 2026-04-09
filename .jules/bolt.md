## 2024-04-09 - Faster Whitespace Normalization
**Learning:** Using `re.sub(r"\s+", " ", text).strip()` for collapsing and stripping whitespace adds unnecessary overhead from the regex engine.
**Action:** Replace this pattern with `" ".join(text.split())` for simple, fast whitespace normalization, which naturally strips ends and collapses middle spaces.
