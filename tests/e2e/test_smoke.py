"""Playwright smoke tests (Chromium). Run: pytest tests/e2e"""
import json
import socket
import subprocess
import sys
import time
from pathlib import Path

import httpx
import pytest

ROOT = Path(__file__).resolve().parents[2]
CASES = json.loads((ROOT / "tests" / "fixtures" / "formula_cases.json").read_text())
DESKTOP = {"width": 1280, "height": 800}
MOBILE = {"width": 390, "height": 844}


@pytest.fixture(scope="session")
def server():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    proc = subprocess.Popen([sys.executable, "-m", "uvicorn", "app.main:app", "--port", str(port)], cwd=ROOT,
                            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    url = f"http://127.0.0.1:{port}"
    for _ in range(100):
        try:
            if httpx.get(url + "/api/health").status_code == 200:
                break
        except httpx.HTTPError:
            time.sleep(0.1)
    yield url
    proc.terminate()
    proc.wait(timeout=10)


def new_page(browser, viewport, **kw):
    ctx = browser.new_context(viewport=viewport, **kw)
    page = ctx.new_page()
    errors = []
    page.on("pageerror", lambda e: errors.append(str(e)))
    page.on("console", lambda m: m.type == "error" and errors.append(m.text))
    return page, errors


def start_custom_test(page, url, seconds=15):
    """Load the page with a saved Custom duration, as a returning visitor would have."""
    settings = json.dumps({"duration": "custom", "custom": seconds, "level": "medium", "mode": "learn"})
    page.add_init_script(f"localStorage.setItem('tt-settings', {json.dumps(settings)})")
    page.goto(url + "/")
    wait_for_fresh_card(page)
    assert page.is_checked("input[name='duration'][value='custom']")
    assert page.text_content("#stat-time") == str(seconds)
    page.locator("#typing-input").focus()


def wait_for_fresh_card(page):
    """The card shows the first sentence of the current stream (settings changes restart the test)."""
    page.wait_for_function("""() => {
        const ex = document.querySelector('.word-card .examples li');
        const text = document.querySelector('#text-lines').textContent;
        return ex && text && text.startsWith(ex.textContent);
    }""")


def no_horizontal_scroll(page):
    return page.evaluate("document.documentElement.scrollWidth <= window.innerWidth")


def test_full_flow_desktop(browser, server):
    page, errors = new_page(browser, DESKTOP)
    start_custom_test(page, server)
    word = page.text_content("#wc-word")
    assert f"{word.capitalize()} means" in page.text_content(".wc-meaning")
    assert page.locator(".word-card .examples li").count() >= 1
    # The first sentence in the stream is the typed example; it is shown first on the card.
    sentence = page.text_content(".word-card .examples li")
    assert page.text_content("#text-lines").startswith(sentence)
    assert page.locator("#text-lines .w.vocab").count() >= 1

    page.keyboard.type(sentence + " ", delay=70)
    assert page.text_content("#learned-toast") == f"✓ {word} learned"
    page.wait_for_function("(w) => document.querySelector('#wc-word')?.textContent !== w", arg=word)
    t1 = int(page.text_content("#stat-time"))
    assert t1 < 15 and int(page.text_content("#stat-wpm")) > 0

    page.wait_for_selector("#result-dialog[open]", timeout=20000)
    assert page.text_content("#result-title").startswith("You're a")
    assert "WPM" in page.text_content("#result-msg")
    assert page.evaluate("document.activeElement.id") == "try-again"
    assert page.text_content("#learned-title").startswith("You learned")
    assert word in page.text_content("#learned-list")
    page.wait_for_function("() => document.querySelectorAll('#analysis-grid div').length === 4")

    page.click("#save-words")
    assert "Saved" in page.text_content("#save-status")

    page.click("#try-again")
    assert not page.is_visible("#result-dialog")
    assert page.text_content("#stat-time") == "15"
    assert page.locator("#text-lines .w.done").count() == 0

    page.goto(server + "/my-words")
    assert word in page.text_content("#mw-list")
    page.click(f"[data-known='{word}']")
    assert page.locator(".known-tag").count() == 1
    assert not errors, errors


def test_escape_restarts_and_paste_is_blocked(browser, server):
    page, _ = new_page(browser, DESKTOP)
    start_custom_test(page, server, 60)
    first = page.evaluate("() => document.querySelector('#text-lines .w').textContent.trimEnd()")
    page.keyboard.type(first, delay=30)
    assert page.locator("#text-lines .c.ok").count() == len(first)
    page.keyboard.press("Escape")
    page.wait_for_function("() => document.querySelectorAll('#text-lines .c.ok, #text-lines .c.err').length === 0")
    # A real paste (Ctrl+V with text on the clipboard) inserts nothing.
    page.context.grant_permissions(["clipboard-read", "clipboard-write"])
    page.evaluate("() => navigator.clipboard.writeText('pasted text')")
    page.locator("#typing-input").focus()
    page.keyboard.press("Control+V")
    assert page.input_value("#typing-input") == ""
    assert page.locator("#text-lines .c.ok, #text-lines .c.err").count() == 0


def test_mobile_390_no_horizontal_scroll(browser, server):
    page, errors = new_page(browser, MOBILE, is_mobile=True, has_touch=True)
    page.goto(server + "/")
    wait_for_fresh_card(page)
    assert no_horizontal_scroll(page)
    box = page.locator("#textbox").bounding_box()
    assert box["y"] + box["height"] <= MOBILE["height"], "typing box should be above the fold"
    card = page.locator("#word-card").bounding_box()
    assert card["y"] + card["height"] <= box["y"] + 1, "card sits above the text, never covering it"
    for path in ("/about", "/my-words", "/privacy", "/terms"):
        page.goto(server + path)
        assert no_horizontal_scroll(page), path

    start_custom_test(page, server, 15)
    page.locator("#textbox").tap()
    sentence = page.text_content(".word-card .examples li")
    page.keyboard.type(sentence[:20], delay=60)
    page.wait_for_selector("#result-dialog[open]", timeout=20000)
    assert no_horizontal_scroll(page)
    assert page.evaluate("(() => { const d = document.querySelector('#result-dialog'); return d.scrollWidth <= d.clientWidth; })()")
    assert not errors, errors


@pytest.mark.parametrize("viewport", [DESKTOP, {"width": 1366, "height": 768}, {"width": 1280, "height": 720}])
def test_home_is_one_screen_with_card_under_text(browser, server, viewport):
    page, errors = new_page(browser, viewport)
    page.goto(server + "/")
    wait_for_fresh_card(page)
    assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight"), "home should not scroll"
    box = page.locator("#textbox").bounding_box()
    card = page.locator("#word-card").bounding_box()
    assert card["y"] >= box["y"] + box["height"], "card sits under the text on desktop"
    assert page.locator(".site-footer").bounding_box()["y"] < viewport["height"]
    assert not errors, errors


def test_card_shows_bangla_meaning_for_the_sense(browser, server):
    page, _ = new_page(browser, DESKTOP)
    page.goto(server + "/privacy")
    html = page.evaluate(
        """async () => {
            const cfg = JSON.parse(document.getElementById('app-config').textContent);
            const { cardHtml } = await import(cfg.assets + '/js/card.js');
            const rec = { word: 'run', ipa: '', forms: [], bn: { verb: ['দৌড়ানো', 'চলা'], noun: ['ছুট'] },
              senses: [{ pos: 'noun', label: 'A jog', meaning: 'an act of running', examples: ['We went for a run in the park today.'] },
                       { pos: 'verb', label: 'To move fast', meaning: 'to move quickly on foot', examples: ['I run to the shop every single morning.'] }] };
            return [cardHtml(rec, rec.senses[1].examples[0]), cardHtml({ ...rec, bn: undefined }, '')];
        }"""
    )
    assert '<span lang="bn">দৌড়ানো, চলা</span>' in html[0]
    assert 'class="bn"' not in html[1]


def test_bangla_label_above_vocab_word_and_toggle(browser, server):
    page, errors = new_page(browser, DESKTOP)

    def add_bn(route):
        data = route.fetch().json()
        for w in data["words"]:
            w["bn"] = {s["pos"]: ["বাংলা অর্থ"] for s in w["senses"]}
        route.fulfill(json=data)

    page.route("**/api/vocab*", add_bn)
    page.goto(server + "/")
    wait_for_fresh_card(page)
    label = page.locator("#text-lines .w.vocab[data-bn]").first
    assert label.get_attribute("data-bn") == "বাংলা অর্থ"
    assert page.locator("#text-lines .w[data-bn]:not(.vocab)").count() == 0, "Learn mode labels vocab words only"
    word_top = label.bounding_box()["y"]
    label_bottom = page.evaluate("""() => {
        const el = document.querySelector('#text-lines .w.vocab[data-bn]');
        const st = getComputedStyle(el, '::before');
        return el.getBoundingClientRect().top + parseFloat(st.top) + parseFloat(st.height);
    }""")
    assert label_bottom <= word_top + 2, "label sits above the word"
    assert page.evaluate("document.documentElement.scrollHeight <= window.innerHeight")

    page.keyboard.type("ab", delay=30)
    page.click("label:has(#bangla-toggle)")
    assert not page.is_checked("#bangla-toggle")
    assert "show-bn" not in page.get_attribute("#textbox", "class")
    assert page.locator("#text-lines .c.ok, #text-lines .c.err").count() == 2, "toggling does not restart the test"
    page.reload()
    wait_for_fresh_card(page)
    assert not page.is_checked("#bangla-toggle"), "the choice is remembered"
    assert not errors, errors


def test_about_page_sections(browser, server):
    page, errors = new_page(browser, MOBILE, is_mobile=True, has_touch=True)
    page.goto(server + "/about")
    for sid in ("how", "modes", "bangla", "why", "shortcuts", "faq"):
        assert page.locator(f"section#{sid}").count() == 1, sid
    assert page.locator(".faq-item").count() >= 8
    page.click("a.btn-primary[href='/']")
    page.wait_for_selector("#typing-input")
    assert not errors, errors


def test_js_formulas_match_python_fixtures(browser, server):
    page, _ = new_page(browser, DESKTOP)
    page.goto(server + "/privacy")
    out = page.evaluate(
        """async (cases) => {
            const cfg = JSON.parse(document.getElementById('app-config').textContent);
            const { analyze } = await import(cfg.assets + '/js/stats.js');
            return cases.map(c => analyze(c.words, c.keystrokes, c.duration_ms, c.pauses));
        }""",
        CASES,
    )
    for case, got in zip(CASES, out):
        for key, value in case["expected"].items():
            assert got[key] == pytest.approx(value), (case["name"], key)
