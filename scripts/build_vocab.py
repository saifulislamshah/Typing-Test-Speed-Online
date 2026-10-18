"""Build the vocabulary JSON files from Wiktionary (kaikki.org) + WordNet + wordfreq.

Usage:  python scripts/build_vocab.py [--target 1200] [--seed 7]

Outputs app/data/vocab_{easy,medium,hard}.json, app/data/meta.json and
app/data/ATTRIBUTION.md. Runs once at build time; the app never calls a
dictionary API at runtime.
"""
from __future__ import annotations

import argparse
import datetime as dt
import gzip
import json
import random
import re
import statistics
import sys
import urllib.request
from pathlib import Path

from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_bangla  # noqa: E402
from vocab_filters import (  # noqa: E402
    POS_MAP, clean_example, clean_gloss, found_forms, inflections, make_label,
    pick_ipa, quotation_year, quote_is_sentence, sense_is_usable,
)

ROOT = Path(__file__).resolve().parent.parent
CACHE = Path(__file__).resolve().parent / ".cache"
DATA = ROOT / "app" / "data"
DUMP_URL = "https://kaikki.org/dictionary/English/kaikki.org-dictionary-English.jsonl.gz"
DUMP = CACHE / "kaikki.org-dictionary-English.jsonl.gz"
BLOCKLIST = Path(__file__).resolve().parent / "blocklist.txt"

TOP_N = 30000
SKIP_ABOVE = 5.5
BANDS = {"easy": (4.5, 5.5), "medium": (3.5, 4.5), "hard": (2.5, 3.5)}
EASY_MIN_FLOOR = 4.0  # never lower the easy/medium boundary below this
MAX_SENSES, MAX_EXAMPLES = 3, 3
QUOTE_MIN_YEAR = 1950
BAD_FORM_TAGS = {"obsolete", "archaic", "alternative", "dated", "nonstandard", "rare",
                 "dialectal", "misspelling", "table-tags", "inflection-template"}
TOP_WORD = re.compile(r'"word": "([^"\\]*)", "lang": "English", "lang_code": "en"')


# ---------------------------------------------------------------- download
def download_dump() -> None:
    CACHE.mkdir(parents=True, exist_ok=True)
    head = urllib.request.Request(DUMP_URL, method="HEAD")
    with urllib.request.urlopen(head) as r:
        total = int(r.headers["Content-Length"])
        modified = r.headers.get("Last-Modified", "")
    have = DUMP.stat().st_size if DUMP.exists() else 0
    if have == total:
        print(f"Using cached dump {DUMP.name} ({total / 1e6:.0f} MB)")
    else:
        req = urllib.request.Request(DUMP_URL, headers={"Range": f"bytes={have}-"} if have else {})
        with urllib.request.urlopen(req) as r, open(DUMP, "ab" if have else "wb") as out, \
                tqdm(total=total, initial=have, unit="B", unit_scale=True, desc="Downloading") as bar:
            while chunk := r.read(1 << 20):
                out.write(chunk)
                bar.update(len(chunk))
    (CACHE / "dump-date.txt").write_text(modified)


# ---------------------------------------------------------------- profanity
def load_profanity():
    """better_profanity's wordlist + our blocklist, matched as whole words.

    better_profanity.contains_profanity() is far too slow for ~100k texts, so we
    read its wordlist and match tokens (and plural -s forms) against a set.
    """
    import better_profanity

    wordlist = Path(better_profanity.__file__).with_name("profanity_wordlist.txt")
    entries = {w.strip().lower() for w in wordlist.read_text(encoding="utf-8").splitlines() if w.strip()}
    extra = set()
    if BLOCKLIST.exists():
        extra = {w.strip().lower() for w in BLOCKLIST.read_text().splitlines()
                 if w.strip() and not w.startswith("#")}
    single = {e for e in entries if " " not in e} | extra
    phrases = [e for e in entries if " " in e]

    def is_profane(text: str) -> bool:
        toks = re.findall(r"[a-z0-9]+", text.lower())
        if any(t in single or (t.endswith("s") and t[:-1] in single) for t in toks):
            return True
        joined = f" {' '.join(toks)} "
        return any(f" {p} " in joined for p in phrases)

    return is_profane, extra


# ---------------------------------------------------------------- candidates
def candidate_words() -> dict[str, float]:
    from wordfreq import top_n_list, zipf_frequency

    out = {}
    for w in top_n_list("en", TOP_N):
        if re.fullmatch(r"[a-z]{3,}", w):
            z = zipf_frequency(w, "en")
            if z <= SKIP_ABOVE:
                out[w] = z
    return out


def slim_entry(d: dict) -> dict:
    """Keep only the fields the pipeline uses, so ~30k entries fit easily in memory."""
    return {
        "pos": d.get("pos"),
        "sounds": [{"ipa": s["ipa"], "tags": s.get("tags", [])} for s in d.get("sounds", []) if s.get("ipa")],
        "forms": [f["form"] for f in d.get("forms", [])
                  if f.get("form") and not set(f.get("tags", [])) & BAD_FORM_TAGS],
        "senses": [{
            "glosses": s.get("glosses", []),
            "tags": s.get("tags", []),
            "raw_tags": s.get("raw_tags", []),
            "form_of": bool(s.get("form_of")),
            "alt_of": bool(s.get("alt_of")),
            "examples": [{"text": e.get("text", ""), "type": e.get("type", ""), "ref": e.get("ref", "")}
                         for e in s.get("examples", [])],
        } for s in d.get("senses", [])],
    }


def read_entries(cands: set[str]) -> dict[str, list[dict]]:
    """Stream the dump once; the slimmed entries are cached for faster re-runs."""
    import hashlib
    import pickle

    key = hashlib.sha256((str(DUMP.stat().st_size) + "|".join(sorted(cands))).encode()).hexdigest()[:16]
    cache = CACHE / f"entries-{key}.pkl"
    if cache.exists():
        print(f"Using cached parsed entries {cache.name}")
        return pickle.loads(cache.read_bytes())
    entries: dict[str, list[dict]] = {}
    with gzip.open(DUMP, "rt", encoding="utf-8") as f:
        for line in tqdm(f, unit=" lines", desc="Parsing Wiktionary", mininterval=2):
            m = TOP_WORD.search(line)
            if not m or m.group(1) not in cands:
                continue
            d = json.loads(line)
            if d.get("word") in cands and d.get("lang_code") == "en" and d.get("pos") in POS_MAP:
                entries.setdefault(d["word"], []).append(slim_entry(d))
    for old in CACHE.glob("entries-*.pkl"):
        old.unlink()
    cache.write_bytes(pickle.dumps(entries))
    return entries


# ---------------------------------------------------------------- records
def wordnet_senses(word: str, forms: set[str], seen: set[str], is_profane):
    from nltk.corpus import wordnet as wn

    wn_pos = {"n": "noun", "v": "verb", "a": "adjective", "s": "adjective", "r": "adverb"}
    for syn in wn.synsets(word):
        if word not in {l.name().lower() for l in syn.lemmas()}:
            continue
        # Some WordNet definitions embed quoted examples with attributions ("; - Author").
        definition = re.split(r';\s*-|\s-\s|;\s*"', syn.definition())[0]
        meaning = clean_gloss(definition)
        if not meaning or is_profane(meaning):
            continue
        exs = []
        for raw in syn.examples():
            ex = clean_example(raw, forms)
            if ex and ex.lower() not in seen and not is_profane(ex):
                exs.append(ex)
                seen.add(ex.lower())
        if exs:
            pos = wn_pos.get(syn.pos(), "noun")
            yield {"pos": pos, "label": make_label(meaning, pos), "meaning": meaning, "examples": exs[:MAX_EXAMPLES]}


def pick_examples(examples: list[dict], forms: set[str], seen: set[str], is_profane, allow_quotes: bool) -> list[str]:
    curated = [e for e in examples if e["type"] == "example" and not e["ref"]]
    quotes = [e for e in examples if e["type"] == "quotation" and (quotation_year(e["ref"]) or 0) >= QUOTE_MIN_YEAR
              and quote_is_sentence(e["text"])] if allow_quotes else []
    out = []
    for ex in curated + sorted(quotes, key=lambda e: len(e["text"])):
        text = clean_example(ex["text"], forms)
        if text and text.lower() not in seen and not is_profane(text):
            out.append(text)
            seen.add(text.lower())
        if len(out) >= MAX_EXAMPLES:
            break
    return out


def build_record(word: str, entries: list[dict], is_profane, allow_quotes: bool = False) -> dict | None:
    all_forms = [f for e in entries for f in e["forms"]]
    forms = inflections(word, all_forms)
    ipa = ""
    senses, seen_meanings, seen_examples = [], set(), set()
    usable_seen = 0
    for e in entries:
        pos = POS_MAP[e["pos"]]
        ipa = ipa or pick_ipa(e["sounds"])
        for s in e["senses"]:
            if len(senses) >= MAX_SENSES:
                break
            if not sense_is_usable(s):
                continue
            meaning = clean_gloss(s["glosses"][-1])
            if not meaning or meaning.lower() in seen_meanings or is_profane(meaning):
                continue
            exs = pick_examples(s["examples"], forms, seen_examples, is_profane, allow_quotes)
            if not exs and not allow_quotes:
                # No curated example: fall back to short modern quotations for this sense
                # so the most common meaning is not lost (citation lines are dropped).
                exs = pick_examples(s["examples"], forms, seen_examples, is_profane, True)
            usable_seen += 1
            if usable_seen == 2 and not senses and not exs:
                # Quality gate: one of the word's first two usable meanings must have a
                # real example, so every card leads with what the word usually means.
                return None
            if exs:
                seen_meanings.add(meaning.lower())
                senses.append({"pos": pos, "label": make_label(meaning, pos), "meaning": meaning, "examples": exs})
    if not senses:
        return None  # WordNet may only fill in for a word Wiktionary already supports
    source = "wiktionary"
    if sum(len(s["examples"]) for s in senses) < 2:
        for extra in wordnet_senses(word, forms, seen_examples, is_profane):
            if len(senses) >= MAX_SENSES:
                break
            if extra["meaning"].lower() not in seen_meanings:
                senses.append(extra)
                source = "wiktionary+wordnet"
            if sum(len(s["examples"]) for s in senses) >= 2:
                break
    if sum(len(s["examples"]) for s in senses) < 2:
        return None
    used = set()
    for s in senses:
        for ex in s["examples"]:
            used |= found_forms(ex, forms)
    return {"id": word, "word": word, "level": "", "ipa": ipa, "senses": senses,
            "forms": sorted(used), "source": source}


def level_for(z: float, bands: dict) -> str | None:
    for name, (lo, hi) in bands.items():
        if lo <= z < hi or (name == "easy" and z == hi):
            return name
    return None


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--target", type=int, default=1200)
    ap.add_argument("--seed", type=int, default=7)
    args = ap.parse_args()

    download_dump()
    import nltk
    nltk.download("wordnet", quiet=True)
    nltk.download("omw-1.4", quiet=True)

    is_profane, blocklist = load_profanity()
    cands = {w: z for w, z in candidate_words().items() if w not in blocklist and not is_profane(w)}
    print(f"{len(cands)} candidate words (zipf <= {SKIP_ABOVE}, top {TOP_N})")
    entries = read_entries(set(cands))
    print(f"{len(entries)} candidates have English noun/verb/adjective/adverb entries")

    strict = {}
    for w in tqdm(sorted(entries), desc="Building records"):
        rec = build_record(w, entries[w], is_profane)
        if rec:
            strict[w] = rec

    bands = dict(BANDS)
    records: dict[str, dict] = dict(strict)
    report = []

    def counts():
        c = {k: 0 for k in bands}
        for w in records:
            lv = level_for(cands[w], bands)
            if lv:
                c[lv] += 1
        return c

    # Fallback tier 1: modern quotations, only for levels under target, most frequent first.
    for lv, n in counts().items():
        if n >= args.target:
            continue
        lo, hi = bands[lv]
        pool = sorted((w for w in entries if w not in records and lo <= cands[w] <= hi),
                      key=lambda w: -cands[w])
        added = 0
        for w in pool:
            if n + added >= args.target:
                break
            rec = build_record(w, entries[w], is_profane, allow_quotes=True)
            if rec:
                rec["source"] += "+quotations"
                records[w] = rec
                added += 1
        report.append(f"{lv}: added {added} words using post-{QUOTE_MIN_YEAR} quotations")

    # Fallback tier 2: lower the easy/medium boundary until easy reaches target.
    while counts()["easy"] < args.target and bands["easy"][0] > EASY_MIN_FLOOR + 1e-9:
        new = round(bands["easy"][0] - 0.1, 1)
        bands["easy"] = (new, bands["easy"][1])
        bands["medium"] = (bands["medium"][0], new)
    if bands != BANDS:
        report.append(f"easy/medium boundary moved to zipf {bands['easy'][0]}")

    levels: dict[str, list[dict]] = {k: [] for k in bands}
    for w, rec in records.items():
        lv = level_for(cands[w], bands)
        if lv:
            rec["level"] = lv
            levels[lv].append(rec)

    DATA.mkdir(parents=True, exist_ok=True)
    rng = random.Random(args.seed)
    meta = {"levels": {}, "bands": bands, "built": dt.date.today().isoformat(),
            "dump_date": (CACHE / "dump-date.txt").read_text() if (CACHE / "dump-date.txt").exists() else "",
            "fallbacks": report, "bangla": {}}
    bangla_cache = build_bangla.load_cache()  # re-applies cached Bangla meanings, no network
    print("\n=== Build report ===")
    for lv, recs in levels.items():
        recs.sort(key=lambda r: r["id"])
        meta["bangla"][lv] = build_bangla.apply(recs, bangla_cache)
        (DATA / f"vocab_{lv}.json").write_text(
            json.dumps(recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        n_ex = [sum(len(s["examples"]) for s in r["senses"]) for r in recs]
        n_se = [len(r["senses"]) for r in recs]
        meta["levels"][lv] = {"words": len(recs), "sentences": sum(n_ex)}
        flag = "" if len(recs) >= args.target else f"  (BELOW TARGET {args.target})"
        print(f"{lv:>6}: {len(recs):5d} words{flag} | avg senses {statistics.fmean(n_se or [0]):.2f}"
              f" | avg examples {statistics.fmean(n_ex or [0]):.2f} | zipf {bands[lv][0]}-{bands[lv][1]}")
    for line in report:
        print("  fallback:", line)
    missing = sum(len(r) for r in levels.values()) - sum(meta["bangla"].values())
    if missing:
        print(f"  {missing} words have no Bangla meaning yet: run python scripts/build_bangla.py")
    meta["total_words"] = sum(v["words"] for v in meta["levels"].values())
    meta["total_sentences"] = sum(v["sentences"] for v in meta["levels"].values())
    (DATA / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    write_attribution(meta)

    for lv, recs in levels.items():
        print(f"\n--- 10 random {lv} cards ---")
        for r in rng.sample(recs, min(10, len(recs))):
            print_card(r)


def print_card(r: dict) -> None:
    s0 = r["senses"][0]
    print(f"\n  {r['word']}  {r['ipa']}  ({s0['pos']})  [{r['source']}]")
    print(f"  {r['word'].capitalize()} means {s0['meaning']}.")
    for s in r["senses"]:
        print(f"   * {s['label']} ({s['pos']}): {s['meaning']}")
        for ex in s["examples"]:
            print(f"       - {ex}")


def write_attribution(meta: dict) -> None:
    (DATA / "ATTRIBUTION.md").write_text(f"""# Data attribution

The vocabulary files in this folder (`vocab_easy.json`, `vocab_medium.json`,
`vocab_hard.json`, `meta.json`) were generated by `scripts/build_vocab.py` on
{meta['built']}.

## Sources

- **Wiktionary** (English), via the machine-readable extraction published at
  [kaikki.org](https://kaikki.org/dictionary/English/) by the
  [wiktextract](https://github.com/tatuylonen/wiktextract) project
  (dump dated {meta['dump_date'] or 'unknown'}). Wiktionary content is available under the
  [Creative Commons Attribution-ShareAlike 4.0 License (CC BY-SA 4.0)](https://creativecommons.org/licenses/by-sa/4.0/)
  and the GNU FDL. Definitions and example sentences were filtered, shortened and
  normalized (straight quotes, ASCII dashes) for typing practice.
- **WordNet 3.0** (Princeton University), via NLTK, used only to fill a missing
  example sentence for a few words. WordNet is distributed under its own
  permissive [WordNet License](https://wordnet.princeton.edu/license-and-commercial-use);
  "WordNet 3.0 Copyright 2006 by Princeton University. All rights reserved."
- **wordfreq** (Robyn Speer, MIT license; data CC BY-SA 4.0) for word frequency and
  difficulty levels.
- **Bangla meanings** (the `bn` field) are machine translations from Google Translate's
  dictionary mode, added by `scripts/build_bangla.py`. They are not part of the
  Wiktionary-derived text.

## License of the generated files

Because they are derived from Wiktionary, the generated JSON files are shared under
**CC BY-SA 4.0**. If you reuse them, credit "Wiktionary contributors" and WordNet,
and share your adaptations under the same license.
""", encoding="utf-8")


if __name__ == "__main__":
    main()
