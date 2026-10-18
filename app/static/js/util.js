// Small shared helpers: DOM, escaping, highlighting, speech, theme.
export const $ = (sel, root = document) => root.querySelector(sel);
export const cfg = JSON.parse(document.getElementById('app-config')?.textContent || '{}');

const ESC = { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' };
export const esc = (s) => String(s).replace(/[&<>"']/g, (c) => ESC[c]);
export const cap = (s) => s.charAt(0).toUpperCase() + s.slice(1);
export const reducedMotion = () => matchMedia('(prefers-reduced-motion: reduce)').matches;

export const formsOf = (rec) => [rec.word, ...(rec.forms || [])];

// Wrap the headword (or an inflection) inside a sentence in <mark class="hw">.
export function highlight(text, forms) {
  const set = new Set(forms.map((f) => f.toLowerCase()));
  return text
    .split(/([A-Za-z]+(?:'[A-Za-z]+)?)/)
    .map((part, i) => (i % 2 && set.has(part.toLowerCase()) ? `<mark class="hw">${esc(part)}</mark>` : esc(part)))
    .join('');
}

// "{Word} means {meaning}."
export const meaningSentence = (rec, sense = rec.senses[0]) =>
  `<strong>${esc(cap(rec.word))}</strong> means ${esc(sense.meaning)}.`;

// ---- pronunciation (Web Speech API)
export const canSpeak = 'speechSynthesis' in window && 'SpeechSynthesisUtterance' in window;
let voice = null;
function pickVoice() {
  const vs = speechSynthesis.getVoices();
  voice = vs.find((v) => v.lang === 'en-US') || vs.find((v) => v.lang === 'en-GB') || vs.find((v) => /^en/i.test(v.lang)) || null;
}
if (canSpeak) {
  pickVoice();
  speechSynthesis.addEventListener?.('voiceschanged', pickVoice);
}
export function speak(word) {
  if (!canSpeak) return;
  speechSynthesis.cancel();
  const u = new SpeechSynthesisUtterance(word);
  u.lang = voice ? voice.lang : 'en-US';
  if (voice) u.voice = voice;
  u.rate = 0.9;
  speechSynthesis.speak(u);
}
export const speakBtn = (word) =>
  canSpeak
    ? `<button type="button" class="icon-btn speak" data-speak="${esc(word)}" aria-label="Pronounce ${esc(word)}"><svg viewBox="0 0 24 24" aria-hidden="true" focusable="false"><path d="M4 9v6h4l5 4V5L8 9H4z"/><path d="M16.5 8.5a5 5 0 0 1 0 7M19 6a8.5 8.5 0 0 1 0 12"/></svg></button>`
    : '';

// Delegated handlers for pronounce buttons and sense expanders anywhere in `root`.
export function wireWordUi(root, keepFocus) {
  root.addEventListener('pointerdown', (e) => {
    if (keepFocus && e.target.closest('button')) e.preventDefault();
  });
  root.addEventListener('click', (e) => {
    const sp = e.target.closest('[data-speak]');
    if (sp) speak(sp.dataset.speak);
    const tg = e.target.closest('[data-toggle]');
    if (tg) {
      const panel = document.getElementById(tg.getAttribute('aria-controls'));
      const open = tg.getAttribute('aria-expanded') !== 'true';
      tg.setAttribute('aria-expanded', String(open));
      panel.hidden = !open;
      if (tg.dataset.toggle) tg.textContent = open ? tg.dataset.less : tg.dataset.toggle;
    }
    if ((sp || tg) && keepFocus) keepFocus();
  });
}

// Senses as label + meaning + highlighted examples.
export function sensesHtml(rec, senses, { meaning = true } = {}) {
  const forms = formsOf(rec);
  return senses
    .map(
      (s) => `<div class="sense"><p class="sense-label">${esc(s.label)}<span class="pos-tag">${esc(s.pos)}</span></p>` +
        (meaning ? `<p class="sense-meaning">${esc(cap(s.meaning))}.</p>` : '') +
        `<ul class="examples">${s.examples.map((x) => `<li>${highlight(x, forms)}</li>`).join('')}</ul></div>`,
    )
    .join('');
}

// ---- theme toggle
export function initTheme() {
  const btn = document.getElementById('theme-toggle');
  if (!btn) return;
  const root = document.documentElement;
  const isDark = () => (root.dataset.theme || (matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light')) === 'dark';
  const sync = () => btn.setAttribute('aria-label', isDark() ? 'Switch to light theme' : 'Switch to dark theme');
  btn.addEventListener('click', () => {
    const t = isDark() ? 'light' : 'dark';
    root.dataset.theme = t;
    try { localStorage.setItem('tt-theme', t); } catch { /* storage unavailable */ }
    sync();
  });
  sync();
}
