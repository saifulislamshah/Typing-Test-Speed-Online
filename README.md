# Typing Test Speed Online

A free typing speed test that teaches English vocabulary. Every sentence you type
teaches a word: you see its pronunciation, its plain-English meaning and its Bangla
(বাংলা) meaning, type a real example sentence, then see more examples grouped by meaning.

The home page is the test itself, on one screen with nothing to scroll: a config bar
(level, mode, length), the text, and the word card. How it works, modes, shortcuts
and the FAQ live on `/about`; personal progress lives on `/my-words`.

- No login and no sign-up. Progress (personal best, history, saved words) stays in the browser's `localStorage`.
- About 5,100 words in three levels, with more than 14,000 example sentences, from Wiktionary (CC BY-SA 4.0) and WordNet.
- Stack: Python 3.12, FastAPI, Pydantic, and vanilla JS ES modules (no build step, about 52 KB of JS). Charts are hand-written SVG.

> The product name lives in one constant: `APP_NAME` in `app/config.py`.

## Run locally

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Open <http://127.0.0.1:8000>. The generated vocabulary is committed (`app/data/`), so
there is nothing else to build.

Static assets are served from a content-hashed path that is computed at startup. When
you edit CSS, JS or templates during development, let uvicorn restart on those files
too:

```bash
uvicorn app.main:app --reload --reload-include "*.css" --reload-include "*.js" --reload-include "*.html"
```

## Project layout

```
app/
  config.py        name, URLs, durations, limits (single source of truth)
  main.py          FastAPI: pages, /api/vocab, /api/analyze, robots/sitemap/manifest
  analysis.py      formulas + post-test analysis (mirrored by static/js/stats.js)
  models.py        Pydantic request/response models + anti-cheat validation
  vocab_store.py   loads vocab_*.json, seeded no-repeat paging
  content.py       FAQ text (rendered into /about and its FAQPage JSON-LD)
  templates/       index (test), about, my-words, privacy, terms, 404 + partials
  static/          css/, js/, fonts/, img/ (served under /assets/<hash>/)
  data/            vocab_easy|medium|hard.json, meta.json, ATTRIBUTION.md
scripts/
  build_vocab.py   Wiktionary + WordNet + wordfreq pipeline
  build_bangla.py  adds Bangla meanings (the `bn` field) to the vocab files
  vocab_filters.py pure, unit-tested filters/normalizers
  make_images.py   renders icons + og-image.png with Playwright
tests/             pytest (formulas, filters, data, API) + e2e/ (Playwright)
```

## API

| Endpoint | Purpose |
|---|---|
| `GET /api/vocab?level=easy\|medium\|hard&count=N&seed=S&cursor=C&exclude=a,b` | Random full word records. Pages through a seed-specific shuffle, so a session never repeats a word. |
| `POST /api/analyze` | Body: `{words, keystrokes: [[t_ms, expected, typed, wordIdx]], duration_ms, pauses: [[start, end]]}`. Returns raw/net WPM, CPM, accuracy, per-5 s series, consistency, problem keys and mistyped words. Implausible data gets a 422. |
| `GET /api/health` | Liveness check plus word count. |

Interactive docs are at `/api/docs`.

## Rebuilding the vocabulary (optional)

```bash
pip install -r requirements-dev.txt
python scripts/build_vocab.py            # --target 1200 --seed 7
```

The first run downloads the kaikki.org English Wiktionary dump (523 MB gzip) into
`scripts/.cache/` and parses it in about 2 minutes. Later runs reuse a cached parse
and take about 1 minute. The script prints counts, averages and 10 random cards per
level, and rewrites `app/data/ATTRIBUTION.md`. See DECISIONS.md for the filtering
rules.

### Bangla meanings

```bash
python scripts/build_bangla.py           # --limit N to test, --offline to only re-apply the cache
```

This asks Google Translate's dictionary mode once per word (about 5,100 requests, roughly
40 minutes, standard library only) and stores up to three Bangla meanings per part of speech:
`"bn": {"verb": ["বরদাস্ত করা", "থাকা", "প্রতীক্ষা করা"]}`. Answers are cached in
`scripts/.cache/bangla.json`, so it resumes after an interruption, and `build_vocab.py`
re-applies the cache automatically. The app never calls a translation service at runtime.

## Tests

```bash
pip install -r requirements-dev.txt
python -m playwright install chromium    # once, for the e2e tests
pytest                                   # unit + API + data + e2e
pytest tests/e2e                         # Playwright only (1280px + 390px)
```

## Deploy

The app is a single ASGI process with no database. Anything that runs
`uvicorn app.main:app` works.

Environment variables:
- `SITE_URL` (for example `https://typingtestspeedonline.com`) is used for canonical URLs, OG tags, the sitemap and share links.
- `CONTACT_EMAIL` is the address in the footer and legal pages. The default is a placeholder.

**Render / Railway:**
- Build: `pip install -r requirements.txt`
- Start: `uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`

**VPS:** run the start command under systemd (or `gunicorn -k uvicorn.workers.UvicornWorker -w 2 app.main:app`) behind nginx or Caddy for TLS. Static assets are already served with immutable caching and gzip by the app. A CDN in front works as-is.

## Manual checklist (before launch)

- [ ] Typing can start within 2 s of page load (focus is in the test; just type).
- [ ] A 1-hour test doesn't run out of words or leak memory. Watch the DevTools Memory tab: DOM nodes stay flat (about 150 word spans) because lines that scroll off are removed.
- [ ] The Android virtual keyboard works (Chrome + Gboard): tapping the text opens the keyboard, letters, space and backspace all work, and autocorrect doesn't interfere.
- [ ] iOS Safari: smart punctuation (curly apostrophes) is accepted as straight quotes.
- [ ] Share links open correctly (Facebook, LinkedIn, X, Copy link). On a phone the native share sheet opens.
- [ ] 20 random word cards read naturally (`python scripts/build_vocab.py` prints samples).
- [ ] Set `SITE_URL` and a real `CONTACT_EMAIL` in production.
- [ ] Lighthouse (mobile) on the production URL.

## Credits

- Definitions and examples: [Wiktionary](https://en.wiktionary.org/) contributors, via [kaikki.org](https://kaikki.org/) / wiktextract, under [CC BY-SA 4.0](https://creativecommons.org/licenses/by-sa/4.0/). Some examples come from [Princeton WordNet](https://wordnet.princeton.edu/). The generated JSON is shared under CC BY-SA 4.0 (see `app/data/ATTRIBUTION.md`).
- Word frequency: [wordfreq](https://github.com/rspeer/wordfreq).
- Bangla meanings: machine translations from Google Translate's dictionary mode, generated once at build time.
- Fonts: Inter and Source Serif 4 (SIL Open Font License).
- Mascots and icons are original artwork made for this project.
