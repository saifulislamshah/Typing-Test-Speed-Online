import json
from pathlib import Path

import pytest

from app.analysis import analyze, max_window_insertions, round1

CASES = json.loads((Path(__file__).parent / "fixtures" / "formula_cases.json").read_text())


@pytest.mark.parametrize("case", CASES, ids=[c["name"] for c in CASES])
def test_formula_cases(case):
    out = analyze(case["words"], case["keystrokes"], case["duration_ms"], case["pauses"])
    for key, value in case["expected"].items():
        assert out[key] == pytest.approx(value), key


def test_zero_duration_does_not_divide_by_zero():
    out = analyze(["a"], [], 0, [])
    assert out["net_wpm"] == out["raw_wpm"] == out["cpm"] == 0
    assert out["series"] == []


def test_series_and_consistency():
    words = ["ab"] * 40
    keys, t = [], 0
    for i in range(40):  # steady rhythm -> high consistency
        for ch in "ab ":
            keys.append([t, ch, ch, i])
            t += 250
    out = analyze(words, keys, t, [])
    assert len(out["series"]) == 6
    assert out["consistency"]["score"] > 90
    assert all(p["wpm"] > 0 for p in out["series"])


def test_problem_keys_and_mistyped_words():
    words = ["cat", "cot"]
    keys = [[0, "c", "c", 0], [100, "a", "o", 0], [200, "t", "t", 0], [300, " ", " ", 0],
            [400, "c", "c", 1], [500, "o", "a", 1], [600, "t", "t", 1], [700, " ", " ", 1]]
    out = analyze(words, keys, 1000, [])
    assert {k["key"] for k in out["problem_keys"]} == {"a", "o"}
    assert [m["word"] for m in out["mistyped_words"]] == ["cat", "cot"]


def test_round1_is_half_up():
    assert round1(2.25) == 2.3
    assert round1(0.05) == 0.1


def test_window_ignores_paused_time():
    keys = [[i * 10, "a", "a", 0] for i in range(5)] + [[60000 + i * 10, "a", "a", 0] for i in range(5)]
    assert max_window_insertions(keys, [[100, 60000]]) == 10
    assert max_window_insertions(keys, []) == 5
