"""Pure helpers of scripts/build_bangla.py (no network)."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
from build_bangla import apply, clean_term, pick_meanings  # noqa: E402

RUN = {"t": "চালান", "bd": [
    ["verb", ["চালান", "হত্তয়া", "চলা", "পলায়ন করা"]],
    ["noun", ["ছুট", "ধাবন"]],
    ["", ["দৌড়ানো"]],
]}


def test_clean_term_fixes_legacy_spellings_and_rejects_non_bangla():
    assert clean_term(" হত্তয়া ") == "হওয়া"
    assert clean_term("পরিষত্সম্বন্ধীয়") == "পরিষৎসম্বন্ধীয়"
    assert clean_term("tailgate") is None
    assert clean_term("Hinged বোর্ড") is None
    assert clean_term("পরিমাণ, তীব্রতা, পদমর্যাদা ইত্যাদিতে নিম্নস্থ") is None  # an explanation, too long


def test_pick_meanings_by_part_of_speech():
    assert pick_meanings(RUN, ["verb"]) == {"verb": ["চালান", "হওয়া", "চলা"]}
    assert pick_meanings(RUN, ["noun", "verb", "noun"]) == {"noun": ["ছুট", "ধাবন"], "verb": ["চালান", "হওয়া", "চলা"]}
    # Unlabeled groups are ignored, and a missing part of speech gets nothing.
    assert pick_meanings(RUN, ["adjective"]) == {}


def test_plain_translation_only_without_dictionary_entry():
    assert pick_meanings({"t": "বোঝা", "bd": [["verb", ["চাপান"]]]}, ["adjective"]) == {}
    assert pick_meanings({"t": "নৌবহর", "bd": []}, ["noun"]) == {"noun": ["নৌবহর"]}
    assert pick_meanings({"t": "tailgate", "bd": []}, ["noun"]) == {}


def test_apply_sets_and_clears_bn():
    recs = [{"word": "run", "senses": [{"pos": "verb"}]}, {"word": "zzz", "senses": [{"pos": "noun"}], "bn": {"noun": ["x"]}}]
    assert apply(recs, {"run": RUN}) == 1
    assert recs[0]["bn"] == {"verb": ["চালান", "হওয়া", "চলা"]}
    assert "bn" not in recs[1]
