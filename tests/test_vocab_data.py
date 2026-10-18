"""Checks every committed vocabulary record."""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from vocab_filters import found_forms, inflections  # noqa: E402

DATA = Path(__file__).resolve().parent.parent / "app" / "data"
LEVELS = ("easy", "medium", "hard")
RECORDS = {lv: json.loads((DATA / f"vocab_{lv}.json").read_text(encoding="utf-8")) for lv in LEVELS}


@pytest.mark.parametrize("level", LEVELS)
def test_level_meets_target(level):
    assert len(RECORDS[level]) >= 1200


@pytest.mark.parametrize("level", LEVELS)
def test_every_record_is_well_formed(level):
    for r in RECORDS[level]:
        assert r["level"] == level and r["id"] == r["word"]
        assert 1 <= len(r["senses"]) <= 3, r["id"]
        assert sum(len(s["examples"]) for s in r["senses"]) >= 2, r["id"]
        assert r["senses"][0]["examples"], r["id"]
        forms = inflections(r["word"], r["forms"])
        for s in r["senses"]:
            assert s["pos"] in {"noun", "verb", "adjective", "adverb"}
            assert 4 <= len(s["meaning"].split()) <= 25, (r["id"], s["meaning"])
            assert 1 <= len(s["label"].split()) <= 5, (r["id"], s["label"])
            assert len(s["examples"]) <= 3
            for ex in s["examples"]:
                assert 6 <= len(ex.split()) <= 22, (r["id"], ex)
                assert all(32 <= ord(c) < 127 for c in ex), (r["id"], ex)
                assert not re.search(r"[‘’“”—–]|  ", ex)
                assert found_forms(ex, forms), (r["id"], ex)


@pytest.mark.parametrize("level", LEVELS)
def test_bangla_meanings_are_well_formed(level):
    for r in RECORDS[level]:
        if "bn" not in r:
            continue
        assert r["bn"], r["id"]
        assert set(r["bn"]) <= {s["pos"] for s in r["senses"]}, r["id"]
        for meanings in r["bn"].values():
            assert 1 <= len(meanings) <= 3 and len(set(meanings)) == len(meanings), r["id"]
            for m in meanings:
                assert re.search(r"[ঀ-৿]", m) and not re.search(r"[A-Za-z]", m), (r["id"], m)


def test_ids_unique_across_levels():
    ids = [r["id"] for lv in LEVELS for r in RECORDS[lv]]
    assert len(ids) == len(set(ids))


def test_attribution_present():
    text = (DATA / "ATTRIBUTION.md").read_text(encoding="utf-8")
    assert "CC BY-SA 4.0" in text and "WordNet" in text
