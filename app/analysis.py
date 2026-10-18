"""Typing formulas and post-test analysis.

These mirror app/static/js/stats.js exactly; both are tested against
tests/fixtures/formula_cases.json.

Keystroke log entry: (t_ms, expected, typed, word_idx)
  t_ms      wall-clock ms since the first keystroke (pauses included; they are
            subtracted here using the pauses list)
  typed     one character for an insertion (" " commits the word), "" for backspace
  expected  what the client expected at that position (informational; the server
            recomputes it from `words`)
"""
from __future__ import annotations

import math
import statistics

BUCKET_MS = 5000


def round1(x: float) -> float:
    """Half-up rounding to 1 decimal, identical to the JS implementation."""
    return math.floor(x * 10 + 0.5) / 10


def paused_before(t: float, pauses: list[tuple[float, float]]) -> float:
    total = 0.0
    for start, end in pauses:
        if t >= end:
            total += end - start
        elif t > start:
            total += t - start
    return total


def active_ms(duration_ms: float, pauses: list[tuple[float, float]]) -> float:
    return max(0.0, duration_ms - paused_before(duration_ms, pauses))


def replay(words: list[str], keystrokes: list) -> dict:
    """Replay the log into per-word typed strings and per-keystroke correctness."""
    typed_words: list[str] = [""] * len(words)
    committed = [False] * len(words)
    events = []  # (t, correct, expected_char) for insertions only
    for t, _exp, typed, idx in keystrokes:
        target = words[idx]
        cur = typed_words[idx]
        if typed == "":
            typed_words[idx] = cur[:-1]
            continue
        pos = len(cur)
        if typed == " ":
            expected = " " if pos >= len(target) else target[pos]
            committed[idx] = True
        else:
            expected = target[pos] if pos < len(target) else ""
            typed_words[idx] = cur + typed
        events.append((t, typed == expected, expected))
    return {"typed": typed_words, "committed": committed, "events": events}


def correct_chars(words: list[str], typed: list[str], committed: list[bool]) -> int:
    n = 0
    for w, tw, done in zip(words, typed, committed):
        if done:
            if tw == w:
                n += len(w) + 1
        elif tw and w.startswith(tw):
            n += len(tw)
    return n


def core_stats(correct: int, typed_chars: int, correct_keys: int, total_keys: int, minutes: float) -> dict:
    if minutes <= 0:
        return {"net_wpm": 0.0, "raw_wpm": 0.0, "cpm": 0.0,
                "accuracy": round1(100.0 * correct_keys / total_keys) if total_keys else 0.0}
    return {
        "net_wpm": round1(correct / 5 / minutes),
        "raw_wpm": round1(typed_chars / 5 / minutes),
        "cpm": round1(correct / minutes),
        "accuracy": round1(100.0 * correct_keys / total_keys) if total_keys else 0.0,
    }


def analyze(words: list[str], keystrokes: list, duration_ms: float, pauses: list) -> dict:
    pauses = [tuple(p) for p in pauses]
    r = replay(words, keystrokes)
    events = r["events"]
    act = active_ms(duration_ms, pauses)
    correct = correct_chars(words, r["typed"], r["committed"])
    correct_keys = sum(1 for e in events if e[1])
    out = core_stats(correct, len(events), correct_keys, len(events), act / 60000)
    out.update({
        "correct_chars": correct,
        "typed_chars": len(events),
        "errors": len(events) - correct_keys,
        "active_seconds": round1(act / 1000),
    })

    # Per-5-second WPM series (correct keystrokes in each bucket of active time).
    n_buckets = max(0, math.ceil(act / BUCKET_MS))
    counts = [0] * n_buckets
    for t, ok, _ in events:
        if ok and n_buckets:
            b = min(n_buckets - 1, int((t - paused_before(t, pauses)) // BUCKET_MS))
            counts[b] += 1
    series = []
    for i, c in enumerate(counts):
        span = min(BUCKET_MS, act - i * BUCKET_MS)
        if span >= 1000:
            series.append({"t": round1((i * BUCKET_MS + span) / 1000), "wpm": round1(c / 5 / (span / 60000))})
    vals = [p["wpm"] for p in series]
    if len(vals) >= 2:
        sd = statistics.pstdev(vals)
        mean = statistics.fmean(vals)
        score = max(0.0, 100 - sd / mean * 100) if mean else 0.0
        out["consistency"] = {"stdev": round1(sd), "score": round1(score)}
    else:
        out["consistency"] = {"stdev": 0.0, "score": 0.0}
    out["series"] = series

    # Problem keys: expected characters most often mistyped.
    totals: dict[str, int] = {}
    misses: dict[str, int] = {}
    for _, ok, exp in events:
        if len(exp) == 1 and exp != " ":
            totals[exp] = totals.get(exp, 0) + 1
            if not ok:
                misses[exp] = misses.get(exp, 0) + 1
    ranked = sorted(misses.items(), key=lambda kv: (-kv[1], kv[0]))[:5]
    out["problem_keys"] = [{"key": k, "errors": v, "total": totals[k]} for k, v in ranked]

    seen, mistyped = set(), []
    for w, tw, done in zip(words, r["typed"], r["committed"]):
        if done and tw != w and w.lower() not in seen:
            seen.add(w.lower())
            mistyped.append({"word": w, "typed": tw})
    out["mistyped_words"] = mistyped[:20]
    return out


def max_window_insertions(keystrokes: list, pauses: list, window_ms: float = 10000) -> int:
    """Most character insertions in any window of active time (anti-cheat)."""
    pauses = [tuple(p) for p in pauses]
    times = [t - paused_before(t, pauses) for t, _e, typed, _i in keystrokes if typed != ""]
    best, lo = 0, 0
    for hi, t in enumerate(times):
        while t - times[lo] > window_ms:
            lo += 1
        best = max(best, hi - lo + 1)
    return best
