// Home page: wires settings, the typing engine, the word card and results.
import { $, cfg, initTheme } from './util.js';
import * as store from './storage.js';
import { Engine } from './engine.js';
import { ApiSource, practiceItems, toItems } from './stream.js';
import { Card } from './card.js';
import { Results } from './results.js';
import { analyze } from './stats.js';

initTheme();

const form = $('#settings');
const input = $('#typing-input');
const live = $('#live-region');
let settings = { duration: String(cfg.defaultDuration), custom: 90, level: cfg.defaultLevel, mode: cfg.defaultMode, ...store.getSettings() };
let source = null, loading = false, testId = 0, practice = null, practiceLabel = '';
let learnedCount = 0, cueStep = 0, lastStats = 0, totalMs = 60000;

const announce = (msg) => { live.textContent = ''; setTimeout(() => (live.textContent = msg), 50); };
const seconds = () => {
  const v = settings.duration === 'custom' ? +settings.custom : +settings.duration;
  return Math.min(cfg.customMax, Math.max(cfg.customMin, v || cfg.defaultDuration));
};
const keepFocus = () => { if (engine.started && !engine.finished) input.focus({ preventScroll: true }); };

// ---------------------------------------------------------------- engine
const card = new Card($('#word-card'), $('#wc-body'), $('#learned-toast'), keepFocus);
const engine = new Engine({
  lines: $('#text-lines'),
  input,
  box: $('#textbox'),
  overlay: $('#pause-overlay'),
  hooks: {
    onItem(item) {
      card.show(item.rec, item.sentence);
      announce(engine.mode === 'speed' ? `Next word: ${item.rec.word}` : `New word: ${item.rec.word}. Type: ${item.sentence}`);
    },
    onItemDone(item) {
      if (engine.mode === 'speed') { if (item.allOk) learnedCount++; return; }
      learnedCount++;
      card.learned(item.rec.word);
    },
    onStart() { $('#typing-hint').innerHTML = '<kbd>esc</kbd> or <kbd>tab</kbd> restart test'; document.body.classList.add('is-running'); },
    onTick: tick,
    onLow: fill,
    onPause(paused) { if (paused) announce('Paused. Press any key to continue.'); },
    onRestart: () => newTest(),
    onFinish: finish,
  },
});

function showTime(leftMs) {
  const s = Math.ceil(leftMs / 1000);
  const long = totalMs > 120000;
  $('#stat-time').textContent = long ? `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}` : s;
  $('#time-fill').style.transform = `scaleX(${(leftMs / totalMs).toFixed(4)})`;
}

function showStats(st) {
  $('#stat-wpm').textContent = Math.round(st.net_wpm);
  $('#stat-cpm').textContent = Math.round(st.cpm);
  $('#stat-acc').textContent = engine.ins ? Math.round(st.accuracy) : 100;
}

function tick(left, act) {
  showTime(left);
  const now = performance.now();
  if (now - lastStats >= 250) { lastStats = now; showStats(engine.stats(now)); }
  if (engine.long) {
    const frac = act / totalMs;
    const steps = [[0.25, 'A quarter done'], [0.5, 'Halfway there'], [0.75, 'Almost there']];
    if (cueStep < steps.length && frac >= steps[cueStep][0]) {
      const cue = $('#goal-cue');
      cue.textContent = `${steps[cueStep][1]} - ${learnedCount} word${learnedCount === 1 ? '' : 's'} learned so far`;
      cue.hidden = false;
      cueStep++;
    }
  }
}

async function fill() {
  if (loading || !source) return;
  loading = true;
  const id = testId;
  try {
    const recs = await source.next(engine.mode === 'speed' ? 50 : 20);
    if (id === testId) engine.append(toItems(recs, engine.mode));
  } catch {
    if (id === testId && !engine.words.length) {
      $('#wc-body').innerHTML = '<p>Could not load words. Check your connection.</p><button type="button" class="btn btn-secondary" id="retry">Try again</button>';
      $('#retry').addEventListener('click', () => newTest());
    }
  } finally {
    loading = false;
  }
}

function newTest(opts = {}) {
  if ('practice' in opts) { practice = opts.practice; practiceLabel = opts.label || ''; }
  testId++;
  loading = false;
  totalMs = seconds() * 1000;
  learnedCount = 0;
  cueStep = 0;
  engine.reset({ duration: seconds(), finite: !!practice, long: seconds() >= cfg.longTest, idle: cfg.idlePause, mode: practice ? 'learn' : settings.mode });
  showTime(totalMs);
  showStats({ net_wpm: 0, cpm: 0, accuracy: 100 });
  $('#goal-cue').hidden = true;
  $('#typing-hint').innerHTML = '<kbd>esc</kbd> restart test <span aria-hidden="true">·</span> start typing to begin';
  document.body.classList.remove('is-running');
  $('#practice-banner').hidden = !practice;
  if (practice) {
    $('#practice-text').textContent = practiceLabel || `Practicing ${practice.length} words with new example sentences`;
    source = null;
    engine.append(practiceItems(shuffle(practice)));
  } else {
    source = new ApiSource(settings.level);
    fill();
  }
}

const shuffle = (a) => a.map((x) => [Math.random(), x]).sort((p, q) => p[0] - q[0]).map((p) => p[1]);

// ---------------------------------------------------------------- results
const results = new Results({
  onClose(reason) {
    if (reason === 'practice') return;
    if (reason === 'settings') {
      newTest({ practice: null });
      form.querySelector('input[name="duration"]:checked')?.focus();
      return;
    }
    newTest(practice ? { practice: practice.map((p) => ({ rec: p.rec, typed: p.typed })) } : {});
    input.focus({ preventScroll: true });
  },
  onPractice(items) {
    newTest({ practice: items.map((it) => ({ rec: it.rec, typed: it.sentence })), label: `Practicing ${items.length} words with new example sentences` });
    input.focus({ preventScroll: true });
  },
});

async function finish(res) {
  res.mode = engine.mode;
  const a = analyze(res.words, res.keystrokes, res.duration_ms, res.pauses);
  const prevBest = store.getBest();
  const wasPractice = !!practice;
  if (wasPractice) store.markPracticed(res.items);
  const sum = results.open(res, a, prevBest, { practice: wasPractice });
  store.addResult({ t: Date.now(), wpm: sum.wpm, acc: sum.acc, cpm: Math.round(a.cpm), learned: sum.learned, dur: seconds(), mode: res.mode, level: settings.level });
  announce(`Time's up. ${sum.wpm} words per minute, ${sum.acc}% accuracy. You're a ${sum.name}. You learned ${sum.learned} words.`);
  try {
    const ctrl = new AbortController();
    setTimeout(() => ctrl.abort(), 6000);
    const resp = await fetch('/api/analyze', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ words: res.words, keystrokes: res.keystrokes, duration_ms: res.duration_ms, pauses: res.pauses, mode: res.mode, level: settings.level }),
      signal: ctrl.signal,
    });
    if (resp.ok) results.renderAnalysis(await resp.json());
  } catch { /* keep the client-side analysis */ }
}

// ---------------------------------------------------------------- settings
function applySettings() {
  const dur = form.querySelector(`input[name="duration"][value="${settings.duration}"]`) || form.querySelector('input[name="duration"][value="60"]');
  dur.checked = true;
  for (const k of ['level', 'mode']) {
    const el = form.querySelector(`input[name="${k}"][value="${settings[k]}"]`);
    if (el) el.checked = true;
  }
  $('#custom-seconds').value = settings.custom;
  $('#custom-field').hidden = settings.duration !== 'custom';
  $('#bangla-toggle').checked = settings.bangla !== false;
  $('#textbox').classList.toggle('show-bn', settings.bangla !== false);
}

form.addEventListener('submit', (e) => e.preventDefault());
form.addEventListener('change', (e) => {
  const fd = new FormData(form);
  const custom = Math.min(cfg.customMax, Math.max(cfg.customMin, Math.round(+$('#custom-seconds').value || 90)));
  settings = { duration: fd.get('duration'), custom, level: fd.get('level'), mode: fd.get('mode'), bangla: fd.get('bangla') === 'on' };
  store.saveSettings(settings);
  applySettings();
  // Showing or hiding the Bangla labels doesn't need a new test.
  if (e.target.name === 'bangla') { engine.scroll(); engine.placeTip(); return; }
  newTest({ practice: null });
  if (e.target.name === 'duration' && settings.duration === 'custom' && e.target.type === 'radio') $('#custom-seconds').focus();
});

$('#practice-exit').addEventListener('click', () => { newTest({ practice: null }); input.focus(); });
$('#restart-btn').addEventListener('click', () => { newTest(); input.focus(); });

// Typing a letter anywhere on the page goes to the test, also right after picking an
// option in the config bar (radios ignore letters anyway). Space still toggles controls.
document.addEventListener('keydown', (e) => {
  const t = e.target;
  const free = t === document.body || t.type === 'radio' || t.type === 'checkbox';
  if (free && e.key.length === 1 && e.key !== ' ' && !e.ctrlKey && !e.metaKey && !e.altKey && !$('#result-dialog').open) input.focus({ preventScroll: true });
});

// ---------------------------------------------------------------- start
applySettings();
const params = new URLSearchParams(location.search);
if (params.get('practice') === 'saved') {
  const saved = Object.values(store.getWords()).filter((w) => !w.known).map((w) => ({ rec: w.r, typed: w.typed }));
  history.replaceState(null, '', '/');
  if (saved.length) newTest({ practice: saved, label: `Practicing your ${saved.length} saved word${saved.length === 1 ? '' : 's'}` });
  else newTest();
} else newTest();
input.focus({ preventScroll: true });

