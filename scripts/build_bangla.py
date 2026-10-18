"""Add Bangla (Bengali) meanings to the vocabulary files.

Usage:  python scripts/build_bangla.py [--limit N] [--offline]

For every word in app/data/vocab_*.json this asks Google Translate's dictionary
mode for its Bangla meanings, grouped by part of speech, and stores up to three
per part of speech the word is used as:

    "bn": {"verb": ["বরদাস্ত করা", "থাকা", "সহ্য করা"]}

The card then shows the meanings for the part of speech of the sentence being
typed. Answers are cached in scripts/.cache/bangla.json, so the script can be
stopped and resumed, and build_vocab.py re-applies the cache without the network.
Runs once at build time; the app never calls a translation service at runtime.
Uses only the standard library.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "app" / "data"
CACHE_FILE = Path(__file__).resolve().parent / ".cache" / "bangla.json"
LEVELS = ("easy", "medium", "hard")
ENDPOINT = "https://translate.googleapis.com/translate_a/single"
MAX_PER_POS = 3
MAX_CHARS = 28  # longer "meanings" are explanations, not translations
BENGALI = re.compile(r"[ঀ-৿]")
LATIN = re.compile(r"[A-Za-z]")
# Legacy spellings in Google's Bangla dictionary data: ওয় written as ত্তয় (হত্তয়া -> হওয়া),
# and khanda ta written as ত্ before স (পরিষত্সম্বন্ধীয় -> পরিষৎসম্বন্ধীয়).
FIXES = (("ত্তয়", "ওয়"), ("ত্স", "ৎস"))


# ---------------------------------------------------------------- pure helpers
def clean_term(term: str) -> str | None:
    """Normalize one Bangla meaning, or None if it is not a usable translation."""
    t = " ".join(term.split())
    for bad, good in FIXES:
        t = t.replace(bad, good)
    t = t.strip(" ,;.।")
    if not t or not BENGALI.search(t) or LATIN.search(t) or len(t) > MAX_CHARS:
        return None
    return t


def pick_meanings(raw: dict, pos_list: list[str]) -> dict[str, list[str]]:
    """Choose up to MAX_PER_POS meanings for each part of speech the word is used as.

    raw = {"t": plain translation, "bd": [[pos, [terms...]], ...]} from the cache.
    The plain translation is used only when Google has no dictionary entry at all,
    because out of context it is often the wrong part of speech ("burdened" -> "বোঝা").
    """
    groups: dict[str, list[str]] = {}
    for pos, terms in raw.get("bd") or []:
        if pos:
            groups.setdefault(pos, []).extend(terms)
    out: dict[str, list[str]] = {}
    for pos in dict.fromkeys(pos_list):
        seen: list[str] = []
        for term in groups.get(pos, []):
            c = clean_term(term)
            if c and c not in seen:
                seen.append(c)
            if len(seen) == MAX_PER_POS:
                break
        if seen:
            out[pos] = seen
    if not out and not raw.get("bd") and pos_list:
        t = clean_term(raw.get("t") or "")
        if t:
            out[pos_list[0]] = [t]
    return out


def apply(records: list[dict], cache: dict) -> int:
    """Set rec["bn"] from the cache; returns how many records have Bangla meanings."""
    n = 0
    for rec in records:
        raw = cache.get(rec["word"])
        bn = pick_meanings(raw, [s["pos"] for s in rec["senses"]]) if raw else {}
        if bn:
            rec["bn"] = bn
            n += 1
        else:
            rec.pop("bn", None)
    return n


# ---------------------------------------------------------------- network
def fetch(word: str, retries: int = 12) -> dict:
    """One word; waits out short network drops (about 15 minutes in total) before giving up."""
    q = urllib.parse.urlencode([("client", "gtx"), ("sl", "en"), ("tl", "bn"), ("dt", "t"), ("dt", "bd"), ("q", word)])
    req = urllib.request.Request(f"{ENDPOINT}?{q}", headers={"User-Agent": "Mozilla/5.0"})
    delay = 2.0
    for attempt in range(retries):
        try:
            with urllib.request.urlopen(req, timeout=20) as r:
                data = json.loads(r.read().decode("utf-8"))
            t = "".join(seg[0] for seg in data[0] or [] if seg and seg[0])
            bd = [[e[0], e[1]] for e in (data[1] or [])] if len(data) > 1 and data[1] else []
            return {"t": t, "bd": bd}
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, IndexError) as e:
            if attempt == retries - 1:
                raise
            print(f"  {word}: {e} - retrying in {delay:.0f}s", flush=True)
            time.sleep(delay)
            delay = min(delay * 2, 120)
    raise RuntimeError("unreachable")


def load_cache() -> dict:
    return json.loads(CACHE_FILE.read_text(encoding="utf-8")) if CACHE_FILE.exists() else {}


def save_cache(cache: dict) -> None:
    CACHE_FILE.parent.mkdir(parents=True, exist_ok=True)
    tmp = CACHE_FILE.with_suffix(".tmp")
    tmp.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    tmp.replace(CACHE_FILE)


# ---------------------------------------------------------------- main
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--limit", type=int, default=0, help="fetch at most N new words (0 = all)")
    ap.add_argument("--offline", action="store_true", help="only apply the cache, no network")
    args = ap.parse_args()

    levels = {lv: json.loads((DATA / f"vocab_{lv}.json").read_text(encoding="utf-8")) for lv in LEVELS}
    cache = load_cache()
    todo = [r["word"] for recs in levels.values() for r in recs if r["word"] not in cache]
    if args.limit:
        todo = todo[:args.limit]
    if todo and not args.offline:
        print(f"Fetching Bangla meanings for {len(todo)} words ({len(cache)} cached)", flush=True)
        try:
            for i, word in enumerate(todo, 1):
                cache[word] = fetch(word)
                if i % 50 == 0 or i == len(todo):
                    save_cache(cache)
                    print(f"  {i}/{len(todo)}", flush=True)
                time.sleep(0.25 + random.random() * 0.2)
        finally:
            save_cache(cache)  # keep progress on errors and Ctrl+C; re-run to resume

    meta_path = DATA / "meta.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    meta["bangla"] = {}
    for lv, recs in levels.items():
        n = apply(recs, cache)
        meta["bangla"][lv] = n
        (DATA / f"vocab_{lv}.json").write_text(json.dumps(recs, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        print(f"{lv:>6}: {n}/{len(recs)} words have Bangla meanings")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")

    sample = random.Random(7).sample([r for recs in levels.values() for r in recs if "bn" in r], 12)
    sys.stdout.reconfigure(encoding="utf-8")
    print("\n--- 12 random words ---")
    for r in sample:
        print(f"  {r['word']:<14} " + " | ".join(f"{p}: {', '.join(v)}" for p, v in r["bn"].items()))


if __name__ == "__main__":
    main()
