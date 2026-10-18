"""Pure, side-effect-free filters and normalizers for the vocabulary pipeline.

Kept separate from build_vocab.py so they can be unit-tested without the
Wiktionary dump, wordfreq or NLTK.
"""
from __future__ import annotations

import re

POS_MAP = {"noun": "noun", "verb": "verb", "adj": "adjective", "adv": "adverb"}

# Senses carrying any of these tags (or raw_tags, lowercased) are rejected.
BAD_TAGS = {
    "obsolete", "archaic", "dated", "rare", "dialectal", "dialect", "regional",
    "slang", "vulgar", "offensive", "derogatory", "pejorative", "slur", "ethnic",
    "nonstandard", "misspelling", "proscribed", "humorous-spelling", "eye-dialect",
    "internet-slang", "obsolete-sense", "historical-spelling", "archaic-spelling",
    "form-of", "alt-of", "abbreviation", "initialism", "acronym", "sexual",
}

# Glosses that only point at another word ("Plural of ...") are not real meanings.
REFERENCE_GLOSS = re.compile(
    r"^(alternative|archaic|obsolete|dated|nonstandard|rare|eye dialect|pronunciation)?\s*"
    r"(form|spelling|plural|singular|past|present|simple past|past participle|"
    r"present participle|third-person|comparative|superlative|misspelling|"
    r"abbreviation|initialism|acronym|ellipsis|clipping|synonym|contraction|"
    r"diminutive|euphemistic form|feminine|masculine|inflection)\b.*\bof\b",
    re.IGNORECASE,
)

_QUOTES = {
    "‘": "'", "’": "'", "‚": "'", "‛": "'", "′": "'",
    "“": '"', "”": '"', "„": '"', "‟": '"', "″": '"',
    "«": '"', "»": '"',
}
_DASHES = {"‐": "-", "‑": "-", "‒": "-", "–": "-", "—": "-", "―": "-", "−": "-"}
_SPACES = {" ": " ", " ": " ", " ": " ", " ": " ", " ": " ", "​": ""}

_TRANSLATE = str.maketrans({**_QUOTES, **_DASHES, **_SPACES, "…": "..."})

_WIKI_LINK = re.compile(r"\[\[(?:[^|\]]*\|)?([^\]]*)\]\]")
_TEMPLATE = re.compile(r"\{\{[^{}]*\}\}")
_HTML = re.compile(r"<[^>]+>")
_LEADING_PAREN = re.compile(r"^\s*\([^)]*\)\s*")
_TRAILING_PAREN = re.compile(r"\s*\([^)]*\)\s*$")
_TOKEN = re.compile(r"[A-Za-z]+(?:'[A-Za-z]+)?")
_CITATION = re.compile(r"(\b1[5-9]\d\d\b|\b20\d\d\b).*(,|:)|\bchapter\b|\bpage \d|\bvolume\b|\bISBN\b|→", re.IGNORECASE)


def normalize_text(text: str) -> str:
    """Make text easy to type: straight quotes, ASCII dashes, '...', single spaces."""
    text = text.translate(_TRANSLATE)
    text = re.sub(r"\s+", " ", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    return text.strip()


def strip_markup(text: str) -> str:
    """Remove wiki links/templates/bold/italic/HTML, keeping visible text."""
    prev = None
    while prev != text:  # nested templates
        prev = text
        text = _TEMPLATE.sub("", text)
    text = _WIKI_LINK.sub(r"\1", text)
    text = text.replace("'''", "").replace("''", "")
    return _HTML.sub("", text)


def is_typeable_ascii(text: str) -> bool:
    return all(32 <= ord(c) < 127 for c in text)


def word_count(text: str) -> int:
    return len(text.split())


def has_bad_tags(sense: dict) -> bool:
    tags = {t.lower() for t in sense.get("tags", [])}
    tags |= {t.lower().replace(" ", "-") for t in sense.get("raw_tags", [])}
    return bool(tags & BAD_TAGS)


def sense_is_usable(sense: dict) -> bool:
    if sense.get("form_of") or sense.get("alt_of"):
        return False
    if has_bad_tags(sense):
        return False
    return bool(sense.get("glosses"))


_CLAUSE_STARTS = {"with", "which", "that", "especially", "usually", "often", "typically", "such",
                  "as", "and", "or", "for", "from", "in", "used", "including", "whether", "but", "by",
                  "generally", "commonly", "particularly", "mostly", "sometimes", "powered", "steered"}


def clean_gloss(gloss: str) -> str | None:
    """Turn a raw gloss into a plain meaning fragment, or None if unusable.

    The result starts lowercase (unless an acronym) and has no final period so it
    reads naturally in "{Word} means {meaning}."
    """
    text = normalize_text(strip_markup(gloss))
    text = _LEADING_PAREN.sub("", text)
    text = _TRAILING_PAREN.sub("", text)
    text = text.strip(" .;:").replace("; ", ", ")
    if not text or REFERENCE_GLOSS.match(text):
        return None
    if not is_typeable_ascii(text) or any(ch in text for ch in "[]{}|=<>"):
        return None
    if word_count(text) > 25:
        # Cut at the last comma clause that starts with a connective and still fits, so
        # "a wheeled vehicle that moves independently, with at least three wheels, ..."
        # keeps its head phrase but "any other long, flexible material" is not split.
        parts = text.split(", ")
        best = None
        for i in range(1, len(parts)):
            if parts[i].split(" ")[0].lower() in _CLAUSE_STARTS and word_count(", ".join(parts[:i])) <= 25:
                best = i
        if best is None:
            return None
        text = ", ".join(parts[:best]).rstrip(" ,;:")
    if not 4 <= word_count(text) <= 25:
        return None
    first = text.split()[0]
    if not (len(first) > 1 and first[1].isupper()) and first != "I":
        text = text[0].lower() + text[1:]
    return text


def inflections(word: str, forms: list[str] | tuple[str, ...] = ()) -> set[str]:
    """The headword plus regular inflections plus single-word forms from Wiktionary."""
    w = word.lower()
    out = {w, w + "s", w + "es", w + "ed", w + "d", w + "ing", w + "er", w + "est", w + "'s"}
    if w.endswith("y") and len(w) > 2 and w[-2] not in "aeiou":
        stem = w[:-1]
        out |= {stem + "ies", stem + "ied", stem + "ier", stem + "iest"}
    if w.endswith("e"):
        out |= {w[:-1] + "ing", w[:-1] + "er", w[:-1] + "est"}
    if len(w) >= 3 and w[-1] not in "aeiouwxy" and w[-2] in "aeiou" and w[-3] not in "aeiou":
        out |= {w + w[-1] + "ed", w + w[-1] + "ing", w + w[-1] + "er", w + w[-1] + "est"}
    for f in forms:
        f = f.lower().strip()
        if re.fullmatch(r"[a-z]+(?:'[a-z]+)?", f):
            out.add(f)
    return out


def tokens(text: str) -> list[str]:
    return [t.lower() for t in _TOKEN.findall(text)]


def found_forms(text: str, forms: set[str]) -> set[str]:
    return {t for t in tokens(text) if t in forms}


def clean_example(text: str, forms: set[str], min_words: int = 6, max_words: int = 22) -> str | None:
    """Return the normalized example sentence, or None if it fails a filter."""
    if not text or any(ch in text for ch in "[]{}|<>=\n"):
        return None  # wiki markup
    text = normalize_text(text)
    text = text.strip()
    if len(text) >= 2 and text[0] == text[-1] == '"':
        text = text[1:-1].strip()
    if not text or not is_typeable_ascii(text) or "..." in text:
        return None  # non-ASCII, or an unfinished sentence
    if _CITATION.search(text) or re.search(r"\d", text):
        return None
    if not min_words <= word_count(text) <= max_words:
        return None
    if ";" in text and min(word_count(part) for part in text.split(";")) < 4:
        return None
    if re.match(r"(often |usually |sometimes |chiefly |also )?used", text, re.IGNORECASE):
        return None  # a usage note, not an example
    if not found_forms(text, forms):
        return None
    if text[0].islower():
        text = text[0].upper() + text[1:]
    if text[-1] not in ".!?\"'":
        text += "."
    return text


_LABEL_STOP_LEADING = {"a", "an", "the", "to", "any", "one", "some", "very", "of", "or"}
_LABEL_CUT = {"that", "which", "who", "whose", "when", "where", "especially", "usually",
              "often", "typically", "such", "as", "in", "for", "with", "by", "from", "on",
              "at", "into", "so", "because", "used", "being", "of", "to"}
_LABEL_BAD_END = {"a", "an", "the", "of", "or", "and", "to", "in", "for", "with", "by", "on", "at",
                  "very", "is", "are", "something", "someone", "one", "from", "into", "about",
                  "over", "up", "out", "off", "its", "their", "his", "her", "try", "attempt"}
_NEW_PHRASE = {"or", "and", "a", "an", "the", "to", "especially", "usually", "often", "such", "as",
               "which", "that", "used", "typically", "in", "of", "for", "with", "by", "from", "also"}
_PREPOSITION_START = {"of", "in", "on", "at", "by", "for", "with", "from", "as"}


def _label_words(clause: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z'-]*", clause)
    while words and words[0].lower() in _LABEL_STOP_LEADING:
        words.pop(0)
    return words


def make_label(meaning: str, pos: str) -> str:
    """2-5 word sense heading derived from the meaning's first clause."""
    clauses = re.split(r"[,;:(]| such as | especially | usually | often | - ", meaning)
    words = _label_words(clauses[0])
    single_clause_word = len(words) == 1
    if len(words) > 5:
        for i in range(2, min(len(words), 6)):
            if words[i].lower() in _LABEL_CUT:
                words = words[:i]
                break
        else:
            words = []
    while words and words[-1].lower() in _LABEL_BAD_END:
        words.pop()
    # "to deceive; to fool" -> "Deceive or fool"
    if single_clause_word and len(words) == 1 and len(clauses) > 1:
        nxt = _label_words(clauses[1])
        first_raw = clauses[0].strip().split(" ")[0].lower()
        if len(nxt) == 1 and first_raw not in _PREPOSITION_START and nxt[0].lower() != words[0].lower():
            words = [words[0], "or", nxt[0]]
    if len(words) == 1:
        # "an opening" -> "An opening", "to deceive" -> "To deceive"
        lead = clauses[0].strip().split(" ")[0].lower()
        nxt_word = clauses[1].strip().split(" ")[0].lower() if len(clauses) > 1 and clauses[1].strip() else ""
        # "a light, gentle wind": the clause is only an adjective, so no label from it.
        if lead in {"a", "an", "the", "to"} and (not nxt_word or nxt_word in _NEW_PHRASE):
            words = [lead, words[0]]
    if not 2 <= len(words) <= 5:
        return pos.capitalize()
    label = " ".join(words)
    return label[0].upper() + label[1:]


def quote_is_sentence(text: str) -> bool:
    """Quotations are only used if they look like one complete, plain sentence."""
    text = text.strip()
    return (bool(text) and text[0].isupper() and text[-1] in ".!?" and "..." not in text
            and "…" not in text and text.count('"') % 2 == 0)


_YEAR = re.compile(r"\b(1[5-9]\d\d|20\d\d)\b")


def quotation_year(ref: str) -> int | None:
    m = _YEAR.search(ref or "")
    return int(m.group(1)) if m else None


def pick_ipa(sounds: list[dict]) -> str:
    """Prefer US/General American, then Received Pronunciation, then the first IPA."""
    ipas = [s for s in sounds if s.get("ipa")]
    for wanted in (("US", "General-American"), ("Received-Pronunciation", "UK")):
        for s in ipas:
            if set(s.get("tags", [])) & set(wanted):
                return s["ipa"]
    return ipas[0]["ipa"] if ipas else ""
