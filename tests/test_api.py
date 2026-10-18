import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)
CASES = json.loads((Path(__file__).parent / "fixtures" / "formula_cases.json").read_text())


def payload(**over):
    case = CASES[2]  # "perfect two words"
    body = {"words": case["words"], "keystrokes": case["keystrokes"], "duration_ms": case["duration_ms"], "pauses": case["pauses"]}
    body.update(over)
    return body


# ------------------------------------------------------------------ /api/vocab
def test_vocab_returns_full_records():
    r = client.get("/api/vocab", params={"level": "medium", "count": 5, "seed": 1})
    assert r.status_code == 200
    data = r.json()
    assert len(data["words"]) == 5
    rec = data["words"][0]
    assert {"id", "word", "level", "ipa", "senses", "source"} <= rec.keys()
    assert rec["level"] == "medium"
    assert rec["senses"][0]["examples"]


def test_vocab_pages_never_repeat_within_a_seed():
    seen, cursor = set(), 0
    for _ in range(5):
        data = client.get("/api/vocab", params={"level": "easy", "count": 50, "seed": 42, "cursor": cursor}).json()
        ids = [w["id"] for w in data["words"]]
        assert not seen & set(ids)
        seen |= set(ids)
        cursor = data["next_cursor"]
    assert len(seen) == 250


def test_vocab_exclude():
    first = client.get("/api/vocab", params={"level": "hard", "count": 3, "seed": 7}).json()["words"]
    ids = [w["id"] for w in first]
    again = client.get("/api/vocab", params={"level": "hard", "count": 3, "seed": 7, "exclude": ",".join(ids)}).json()["words"]
    assert not set(ids) & {w["id"] for w in again}


@pytest.mark.parametrize("params", [{"level": "expert"}, {"count": 0}, {"count": 51}, {"cursor": -1}])
def test_vocab_rejects_bad_params(params):
    assert client.get("/api/vocab", params=params).status_code == 422


# ------------------------------------------------------------------ /api/analyze
def test_analyze_ok():
    r = client.post("/api/analyze", json=payload())
    assert r.status_code == 200
    assert r.json()["net_wpm"] == 8
    assert r.json()["accuracy"] == 100


def test_analyze_rejects_negative_timestamp():
    keys = [[-5, "t", "t", 0]] + CASES[2]["keystrokes"][1:]
    assert client.post("/api/analyze", json=payload(keystrokes=keys)).status_code == 422


def test_analyze_rejects_non_monotonic_timestamps():
    keys = [list(k) for k in CASES[2]["keystrokes"]]
    keys[3][0] = 100
    assert client.post("/api/analyze", json=payload(keystrokes=keys)).status_code == 422


def test_analyze_rejects_negative_duration():
    assert client.post("/api/analyze", json=payload(duration_ms=-1)).status_code == 422


def test_analyze_rejects_impossible_speed():
    words = ["a"] * 2000
    keys = []
    for i in range(2000):  # 2 chars every 20 ms = 1200 WPM for 40 s
        keys += [[i * 20, "a", "a", i], [i * 20 + 10, " ", " ", i]]
    r = client.post("/api/analyze", json={"words": words, "keystrokes": keys, "duration_ms": 40000, "pauses": []})
    assert r.status_code == 422
    assert "250 WPM" in r.text


def test_analyze_rejects_burst_over_10s_window():
    # 300 WPM for 10 s inside an otherwise slow 60 s test
    words, keys, t = [], [], 0
    for i in range(130):
        words.append("abcd")
        for ch in "abcd ":
            keys.append([t, ch, ch, i])
            t += 15
    r = client.post("/api/analyze", json={"words": words, "keystrokes": keys, "duration_ms": 60000, "pauses": []})
    assert r.status_code == 422


def test_analyze_rejects_keystroke_inside_pause():
    keys = [list(k) for k in CASES[3]["keystrokes"]]
    keys[3][0] = 30000
    body = {"words": CASES[3]["words"], "keystrokes": keys, "duration_ms": 72000, "pauses": [[4000, 64000]]}
    assert client.post("/api/analyze", json=body).status_code == 422


def test_analyze_rejects_word_index_out_of_range():
    keys = CASES[2]["keystrokes"] + [[11000, "x", "x", 5]]
    assert client.post("/api/analyze", json=payload(keystrokes=keys)).status_code == 422


def test_analyze_payload_too_large():
    r = client.post("/api/analyze", content=b"x" * 3_100_000, headers={"content-type": "application/json"})
    assert r.status_code == 413


# ------------------------------------------------------------------ pages & SEO
def test_pages_render_with_metadata():
    html = client.get("/").text
    assert "<title>Typing Speed Test Online - Type Faster &amp; Learn English Words</title>" in html
    assert 'name="description" content="Test your typing speed and learn new English words as you type.' in html
    assert html.count("<h1") == 1
    assert '"@type":"WebApplication"' in html
    assert "{{" not in html
    about = client.get("/about").text
    assert '"@type":"FAQPage"' in about and 'id="faq"' in about and 'id="how"' in about
    for path in ("/about", "/my-words", "/privacy", "/terms"):
        page = client.get(path)
        assert page.status_code == 200 and page.text.count("<h1") == 1 and "{{" not in page.text


def test_analytics_script_only_on_vercel():
    import subprocess
    import sys
    assert "/_vercel/insights" not in client.get("/").text
    code = "from app.main import RENDERED; print('/_vercel/insights/script.js' in RENDERED['/'])"
    root = Path(__file__).resolve().parent.parent
    import os
    for env, expected in (({"VERCEL": "1"}, "True"), ({"VERCEL": "1", "ANALYTICS": "0"}, "False")):
        out = subprocess.run([sys.executable, "-c", code], cwd=root, capture_output=True, text=True,
                             env={**os.environ, **env}, check=True).stdout.strip()
        assert out == expected, env


def test_security_headers_and_404():
    r = client.get("/")
    assert "script-src 'self' 'sha256-" in r.headers["content-security-policy"]
    nf = client.get("/nope")
    assert nf.status_code == 404 and "Page not found" in nf.text
    assert client.get("/api/nope").status_code == 404


def test_robots_sitemap_manifest():
    assert "Sitemap:" in client.get("/robots.txt").text
    assert "/about</loc>" in client.get("/sitemap.xml").text
    assert client.get("/manifest.webmanifest").json()["icons"]
