# Decisions

Defaults chosen where the brief was ambiguous or had to give way. Each entry gives the
decision and the reason.

## Vocabulary data

| Decision | Why |
|---|---|
| We download the **`.jsonl.gz`** kaikki dump (523 MB) and stream it with `gzip.open`, instead of the raw 3.3 GB file. | It's the same data at a sixth of the download. A regex pre-filter on the top-level `"word"` key means only about 30k of the ~1.4M lines are JSON-parsed. The slimmed entries are cached (`scripts/.cache/entries-*.pkl`), so re-runs take about 1 minute. |
| **Curated `type: "example"` sentences come first.** If a sense has *none*, a short quotation dated 1950 or later may be used instead. The quotation must be one complete sentence that passes every other filter, and its citation line is dropped. | Many headline senses on Wiktionary only have quotations ("car" = vehicle, "passion" = emotion). Without this, words would lead with a minor sense such as "a railroad car". The brief bans *citation lines*, and we never show them. |
| **Quality gate:** one of a word's first two usable senses must have an example, or the word is skipped. | It guarantees that every card leads with what the word usually means. That rules out some common words whose main sense has no usable sentence ("magazine", "switch"). That is a deliberate quality-over-coverage choice: every level still clears 1,200. |
| Long glosses (over 25 words) are **trimmed at a comma clause that starts with a connective** ("with", "which", "especially"…), never mid-phrase. | Otherwise the main definitions of basic words ("car", "book") fail the 4–25 word rule. |
| `;` inside meanings becomes `,`. | "{Word} means …" should read as one plain sentence. |
| **Labels are sentence case** ("Strong feeling or emotion"), not Title Case. | The brief says "Title case", but its own example labels are sentence case. We followed the example. |
| Some labels are 2 words with a leading "To"/"A" ("To want", "A riddle"), and about 15% fall back to the part of speech ("Noun"). | Labels must be 2–5 words. Single-word clauses read naturally with the article, and the POS fallback is what the brief specifies. |
| Records carry an extra **`forms`** array (inflections that appear in the examples). | The client highlights "sank" or "running" without needing its own stemmer. |
| Examples are rejected when they contain digits, `...`, or `;`-lists of short fragments, or when they start with "Used…" (usage notes). | It keeps sentences complete and easy to type. |
| **Profanity:** we use `better_profanity`'s wordlist with set matching instead of `contains_profanity()`. A manual blocklist (`scripts/blocklist.txt`) adds distressing topics. | `contains_profanity()` is too slow for ~100k texts (the build would take about 1 hour). The wordlist and coverage are the same. |
| `wordfreq.top_n_list('en', 30000)` bottoms out near **zipf 2.97**, so Hard is effectively 3.0–3.5. | We followed the spec's 30k list. Raise `TOP_N` in `build_vocab.py` for rarer Hard words. |
| The build has a shortfall policy (a quotation tier, then lowering the Easy/Medium boundary). It is **not triggered** by the current data: Easy is 1,258, Medium 2,406, Hard 1,460. | The safety net stays in place for future dumps. Any boundary actually used is written to `meta.json`. |
| Words are ids. Each word appears in exactly one level. | Simple, unique and readable ids. |
| **Bangla meanings come from Google Translate's dictionary mode** (`dt=bd`), fetched once at build time by `scripts/build_bangla.py`. | It returns ranked meanings grouped by part of speech, which match our senses' `pos`, so a card shows the Bangla for the sense being typed. Wiktionary's own Bengali translations covered only 5 of 5,124 words; the offline `shobdo` package is a Bangla→Bangla dictionary whose reverse lookup returned unrelated words; plain translation of a single word often picked the wrong part of speech ("burdened" → "বোঝা"). The endpoint is unofficial, which is acceptable for a one-off build, but not for runtime calls. |
| The plain translation is used **only when Google has no dictionary entry at all**; meanings with Latin letters or over 28 characters (explanations) are dropped, and two legacy spellings are fixed (ত্তয় → ওয়, ত্স → ৎস). | A missing Bangla line is better than a wrong one. |

## Layout and design

| Decision | Why |
|---|---|
| **The home page is only the test**, sized to one screen (no scroll at 1280×720 and up, or at 390×844): header, config bar, live stats, three lines of text, word card, footer. How it works, modes, shortcuts and the FAQ moved to `/about` (with the FAQPage JSON-LD); progress history moved to `/my-words`. | The owner asked for a full-screen typing hero like monkeytype.com. The page keeps a visually hidden `<h1>` and the WebApplication JSON-LD for search. |
| **Dark theme by default**, light theme from the toggle. Our own palette (charcoal + teal), not monkeytype's. Untyped text keeps at least 4.5:1 contrast in both themes. | The look of a typing app, without copying another product's colors, and still readable. |
| Typing text uses the **system monospace font** (Cascadia Mono, SF Mono, Menlo, Consolas…), with no download. | Monospace is the typing-app look, and it adds no bytes. |
| The **word card sits under the text** on desktop and **above it on phones**, where the virtual keyboard covers the lower half. Examples and other meanings are behind a toggle that stays open across words once opened. | The card has to stay visible while typing without making the page scroll. |
| When the text box loses focus the text blurs and says "Click here or start typing to focus". Any letter typed on the page, or right after picking a config option, goes to the test. | It makes the focus state obvious, which matters now that the text box has no border. |
| **One Bangla tip above one word while typing** (owner's request): a small bubble with the first Bangla meaning for the sentence's sense, above the vocabulary word of the current sentence (Learn mode) or the current word (Speed mode). It is positioned outside the clipped 3-line window. The config bar's **বাংলা** toggle hides it; the choice is saved and doesn't restart the test. | The first version labeled every word: in Speed mode that stacked a line of Bangla over every line of text, and labels were clipped at the window edges. One tip where the eyes are is readable and never clipped. |
| Bangla text uses **system Bangla fonts** (Noto Sans Bengali, Nirmala UI, Kohinoor Bangla…) via `lang="bn"`. | Every current OS ships one, so there is nothing to download. |

## Typing engine and formulas

| Decision | Why |
|---|---|
| **Accuracy** = correct character insertions ÷ all insertions (spaces included). Corrected mistakes still count against you, and Backspace is not a keystroke. | This matches the brief's "correct keystrokes / total keystrokes" and is the common convention. |
| **CPM / net WPM** count the space after each fully correct word, plus the correct prefix of the word in progress. Committed wrong words count 0. | This is the brief's definition, made exact so the client and server agree (shared fixtures in `tests/fixtures/formula_cases.json`). |
| Values are rounded **half-up to 1 decimal** by the same function in Python and JS. The UI shows whole numbers. | Python's `round()` uses banker's rounding, which would make the two sides disagree. |
| **Tab restarts only while a test is running.** When the test is idle, Tab moves focus normally, and Shift+Tab always does. | This avoids a keyboard trap (WCAG 2.1.2). Esc always restarts. |
| **Auto-pause applies only to tests of 5 minutes or more.** An idle pause is *backdated to the last keystroke*, so the 30 idle seconds are excluded too. The countdown visibly gets that time back. | The brief says to exclude paused time. Counting 30 idle seconds as typing would unfairly lower a long test's WPM. |
| The key that resumes a paused test is not typed. | "Press any key to continue" means the key continues the test; it isn't text. |
| Arrow keys, Home/End, Enter and Ctrl+Z/Y/A/X are blocked in the typing input. iOS smart quotes and dashes are normalized to ASCII as you type. | The diff-based input model assumes the caret is always at the end. Smart punctuation would otherwise mark correct typing as wrong. |
| **No repeats in a session** comes from a server-side, seed-based shuffle with a `cursor`, rather than a growing `exclude` list. `exclude` is still supported. | A 1-hour test would otherwise send hundreds of ids in a URL. |
| The `/api/analyze` limits are: over 250 WPM over the whole test *or* within any 10-second window, keystrokes inside a pause, timestamps that go backwards or are negative, word indexes out of range, and bodies over 3 MB. | Implausible data is rejected with 422. The client then silently keeps its own (identical) numbers. |

## Learning UX

- **Text colors** (changed at the owner's request): text not typed yet is gray (`--dim`,
  #6B6761 in light mode), typed text is the full text color (black), and mistakes are red
  with a wavy underline. This replaces the brief's "completed text is dimmed".
- The bold/underlined vocabulary highlight appears in **Learn words** mode only. In Speed only
  mode every word is a vocabulary word, so highlighting them all would carry no meaning.

| Decision | Why |
|---|---|
| **"Learned"** means the sentence was completed (Learn mode) or the word was typed exactly (Speed mode). | Learn mode is about exposure to the word in context. In Speed mode, typing the word is the exposure. |
| On phones, the card hides its first example when there is more than one, because that sentence is already in the text box. | It keeps the typing box above the fold at 390×844. The second example shows a new usage instead of a duplicate. |
| The card always leads with the **sense used by the current sentence**. In practice runs this is often a second meaning. The results list does the same. | "Practice these words again" is meant to show each word used a new way. |
| A practice run ends when every word has been typed once, or when time is up. | Practice sets are small, so looping the same 8 words would be repetitive. |
| Closing the result dialog in any way starts a fresh test and returns focus to the typing input. "Change settings" focuses the duration chips instead. Focus starts on **Try again** when the dialog opens. | The brief's "focus returns to Try again" is read as Try again being the dialog's initial and primary focus. After closing, the input is the natural place to continue. |
| "Need practice" (for the Zeigarnik line) = saved, not marked known, and not yet typed in a practice run. | It's a simple and honest count. |
| My Words has **Remove** as well as **Mark as known**. | People will want to undo a save. |
| **Every learned word is saved to My Words automatically** (owner's request); the results dialog no longer has a Save button, and its checkboxes now choose which words to practice again. Each word keeps when it was learned and how many times it was typed. | People expected to find every word they learned. The whole library (~5,100 words) fits in the ~5 MB localStorage quota, so there is nothing to cap. |
| **Export / Import backup** on My Words: one JSON file with words, history, best and settings. Import merges (newer data wins per word, history de-duplicated) and validates every record. | Browser storage is per device and can be cleared; a file moves words between devices without a server or an account. |
| **Vercel Web Analytics**, only when deployed on Vercel (`VERCEL=1`; `ANALYTICS=0` turns it off). | Anonymous visitor counts with no cookies (no consent banner) and no server of our own. The script is served from our own domain, so the strict CSP is unchanged. |
| The share URL is the site root. Facebook and LinkedIn receive only the URL, because their share intents ignore text. X and the native share sheet get the full text. | That is how those platforms work. |

## Platform

| Decision | Why |
|---|---|
| Static assets are served under **`/assets/<content-hash>/…`** with `immutable` caching. HTML is `no-cache`. | There is no build step, but relative ES-module imports still bust the cache together on every deploy. |
| HTML pages are rendered **once at startup** from `app/templates/` (with partials and `{{PLACEHOLDERS}}`), not per request. | They're fast, and the FAQ text is defined once (`app/content.py`) for both the page and the FAQPage JSON-LD. |
| **Strict CSP** (`script-src 'self'` plus the sha256 of the tiny inline theme script, no `unsafe-inline` or `unsafe-eval`). | It satisfies Best Practices, and the inline script prevents a flash of the wrong theme. |
| Fonts are **Inter** (UI) and **Source Serif 4** (examples and results), as self-hosted variable woff2 Latin subsets with `font-display: swap`, preloaded. Both are OFL, and their licenses ship in `app/static/fonts/`. | This meets the brief's typography and performance requirements. IPA falls back to system fonts that contain IPA glyphs. |
| `CONTACT_EMAIL` is a **placeholder** (`hello@typingtestspeedonline.com`). It can be overridden with the env var. | We don't publish a personal address without asking. |
| Social proof is limited to the real library size, computed from the JSON files at startup. | The brief bans fake numbers, and there are none. |
| The OG image and icons are rendered by `scripts/make_images.py` with Playwright. | No extra imaging dependency is needed. |
