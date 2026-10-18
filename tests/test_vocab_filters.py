import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))

from vocab_filters import (  # noqa: E402
    clean_example, clean_gloss, inflections, make_label, normalize_text, pick_ipa, sense_is_usable,
)

FORMS = inflections("passion", ["passions"])


def test_normalizes_curly_quotes_dashes_ellipsis_and_spaces():
    raw = "“She said…”  it’s a passion — really so"
    assert normalize_text(raw) == "\"She said...\" it's a passion - really so"


def test_rejects_obsolete_slang_and_other_bad_tags():
    for tag in ["obsolete", "archaic", "dated", "rare", "dialectal", "slang", "vulgar", "offensive", "derogatory"]:
        assert not sense_is_usable({"glosses": ["A strong feeling of love."], "tags": [tag]})
    assert not sense_is_usable({"glosses": ["x"], "raw_tags": ["Internet slang"]})
    assert sense_is_usable({"glosses": ["A strong feeling of love."], "tags": ["countable"]})


def test_rejects_form_of_and_alt_of():
    assert not sense_is_usable({"glosses": ["plural of passion"], "form_of": True})
    assert not sense_is_usable({"glosses": ["Alternative spelling of colour"], "alt_of": True})
    assert clean_gloss("plural of passion") is None
    assert clean_gloss("Alternative spelling of colour") is None


def test_gloss_cleanup_strips_markup_and_parentheticals():
    assert clean_gloss("(transitive) To [[move|move]] very '''quickly''' on foot.") == "to move very quickly on foot"
    assert clean_gloss("Love.") is None  # fewer than 4 words
    assert clean_gloss(" ".join(["word"] * 26)) is None  # more than 25 words


def test_example_requires_headword_or_inflection():
    assert clean_example("She argued her case with great passion.", FORMS)
    assert clean_example("Football fans have many passions in life.", FORMS)
    assert clean_example("She argued her case with great energy today.", FORMS) is None
    ran = inflections("run", ["ran", "running", "runs"])
    assert clean_example("He ran all the way to the station.", ran)
    assert clean_example("Running every morning keeps her healthy.", ran)


def test_example_rejects_citations_markup_length_and_non_ascii():
    assert clean_example("1930, Norman Lindsay, chapter 6, in Redheap, page 106: passion", FORMS) is None
    assert clean_example("She felt [[passion]] for the sea every single day.", FORMS) is None
    assert clean_example("Great passion.", FORMS) is None
    assert clean_example(" ".join(["passion"] * 23), FORMS) is None
    assert clean_example("Her passion for the café was obvious to everyone.", FORMS) is None


def test_example_normalizes_curly_quotes():
    out = clean_example("“It’s my passion,” she said with a smile.", FORMS)
    assert out == "\"It's my passion,\" she said with a smile."


def test_inflection_rules():
    assert {"stopped", "stopping"} <= inflections("stop")
    assert {"carries", "carried"} <= inflections("carry")
    assert "making" in inflections("make")


def test_label_and_ipa():
    assert make_label("a very strong feeling or emotion, such as love or anger", "noun") == "Strong feeling or emotion"
    assert make_label("love", "noun") == "Noun"
    sounds = [{"ipa": "/uk/", "tags": ["Received-Pronunciation"]}, {"ipa": "/us/", "tags": ["US"]}]
    assert pick_ipa(sounds) == "/us/"
    assert pick_ipa([]) == ""


def test_label_variants():
    assert make_label("to deceive, to fool, to trick", "verb") == "Deceive or fool"
    assert "illness" not in make_label("seeming to have fallen deeper back into the face due to tiredness, illness, or old age", "adjective")
    assert make_label("a riddle, or a difficult problem", "noun") == "A riddle"
    assert make_label("a light, gentle wind", "noun") == "Noun"
    assert make_label("to want, to wish for earnestly", "verb") == "To want"
    assert make_label("a going of the rounds along the chain of sentinels", "noun") != "A going"


def test_long_gloss_is_trimmed_at_a_clause_boundary():
    g = ("A wheeled vehicle that moves independently, with at least three wheels, powered mechanically, "
         "steered by a driver and mostly for personal transportation of people and their goods over long distances.")
    out = clean_gloss(g)
    assert out.startswith("a wheeled vehicle that moves independently") and len(out.split()) <= 25
