"""
sa_languages.py — languages the pipeline detects and replies in.

Deliberately scoped to English + Afrikaans, not all 11 of South Africa's
official languages. Live testing surfaced two real failure modes on the
other languages (mainly the Nguni family — isiZulu, isiXhosa, siSwati,
isiNdebele): the 8B model's output was frequently garbled rather than
fluent, and short/ambiguous messages ("anyone else") were sometimes
misclassified into one of those languages entirely, producing a
nonsensical reply in a conversation that had been in English the whole
time. Afrikaans, by contrast, consistently came back fluent — likely
because it's close to English/Dutch, both far better-represented in the
model's training data than the Nguni/Sotho-Tswana languages.

Rather than ship a multilingual feature that embarrasses the person
demoing it, this trades breadth for reliability: two languages that
actually work, instead of eleven where nine are a coin flip.
"""

SA_LANGUAGES = (
    "English",
    "Afrikaans",
)
