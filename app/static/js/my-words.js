// My Words page: every learned word as a full card, with search, filters, practice,
// progress and backup (export/import a JSON file).
import { $, bnAllHtml, cap, esc, initTheme, sensesHtml, speakBtn, wireWordUi } from './util.js';
import * as store from './storage.js';
import { lineChart } from './chart.js';

initTheme();
const list = $('#mw-list');
wireWordUi(list);
const PAGE = 48; // cards rendered at a time; "Show more" adds the next page
let limit = PAGE;
const fmtDate = (t) => new Date(t).toLocaleDateString(undefined, { month: 'short', day: 'numeric', year: 'numeric' });

function render() {
  const all = Object.values(store.getWords()).sort((a, b) => (b.lastAt || b.savedAt || 0) - (a.lastAt || a.savedAt || 0));
  const ws = store.wordStats();
  renderProgress();
  $('#mw-empty').hidden = all.length > 0;
  $('#mw-toolbar').hidden = all.length === 0;
  $('#mw-summary').textContent = all.length
    ? `You have learned ${ws.saved} word${ws.saved === 1 ? '' : 's'} - ${ws.needPractice ? `${ws.needPractice} still need practice.` : 'all practiced. Nice work!'}`
    : 'Every word you learn in a test is added here automatically, with its meanings and examples.';
  const learning = all.filter((w) => !w.known).length;
  const practice = $('#mw-practice');
  practice.hidden = learning === 0;
  practice.textContent = `Practice my words (${learning})`;

  const q = $('#mw-search').value.trim().toLowerCase();
  const level = $('#mw-level').value;
  const status = $('#mw-status').value;
  const shown = all.filter(({ r, known }) =>
    (!level || r.level === level) &&
    (!status || (status === 'known') === !!known) &&
    (!q || r.word.includes(q) || r.senses.some((s) => s.meaning.toLowerCase().includes(q)) ||
      Object.values(r.bn || {}).some((m) => m.some((x) => x.includes(q)))));
  const page = shown.slice(0, limit);
  $('#mw-count').textContent = all.length ? `Showing ${page.length} of ${shown.length === all.length ? '' : `${shown.length} matching, `}${all.length} words` : '';
  list.innerHTML = page.map(cardHtml).join('');
  $('#mw-more').hidden = shown.length <= limit;
}

function cardHtml({ r, known, savedAt, seen }) {
  return `<li class="mw-card${known ? ' is-known' : ''}">
<div class="wc-head"><h2 class="wc-word">${esc(r.word)}</h2><span class="pos-tag">${esc(r.level)}</span>${known ? '<span class="known-tag">Known</span>' : ''}</div>
<div class="wc-pron">${r.ipa ? `<span class="ipa">${esc(r.ipa)}</span>` : ''}${speakBtn(r.word)}</div>
${bnAllHtml(r)}
<p class="wc-meaning"><strong>${esc(cap(r.word))}</strong> means ${esc(r.senses[0].meaning)}.</p>
<p class="mw-meta">${savedAt ? `Learned ${fmtDate(savedAt)}` : 'Learned'}${seen > 1 ? ` · typed ${seen} times` : ''}</p>
<h3 class="ex-h">Meanings and examples</h3>${sensesHtml(r, r.senses)}
<div class="mw-actions">
<button type="button" class="btn btn-secondary btn-sm" data-known="${esc(r.id)}" aria-pressed="${known ? 'true' : 'false'}">${known ? 'Known ✓ (practice again)' : 'Mark as known'}</button>
<button type="button" class="btn btn-ghost btn-sm" data-remove="${esc(r.id)}" aria-label="Remove ${esc(r.word)} from My Words">Remove</button>
</div></li>`;
}

list.addEventListener('click', (e) => {
  const k = e.target.closest('[data-known]');
  const rm = e.target.closest('[data-remove]');
  if (k) {
    const id = k.dataset.known;
    store.updateWord(id, { known: k.getAttribute('aria-pressed') !== 'true' });
    render();
    list.querySelector(`[data-known="${CSS.escape(id)}"]`)?.focus();
  }
  if (rm) {
    store.updateWord(rm.dataset.remove, null);
    render();
    $('#mw-search').focus();
  }
});
for (const id of ['#mw-search', '#mw-level', '#mw-status']) $(id).addEventListener('input', () => { limit = PAGE; render(); });
$('#mw-more').addEventListener('click', () => {
  const first = list.children.length;
  limit += PAGE;
  render();
  list.children[first]?.querySelector('button')?.focus(); // keep keyboard users at the new cards
});

// ---- backup
const backupStatus = (msg) => { $('#backup-status').textContent = msg; };
$('#export-btn').addEventListener('click', () => {
  const data = store.exportData();
  const blob = new Blob([JSON.stringify(data)], { type: 'application/json' });
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = `typing-test-backup-${new Date().toISOString().slice(0, 10)}.json`;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(a.href), 1000);
  const n = Object.keys(data.words).length;
  backupStatus(`Backup saved: ${n} word${n === 1 ? '' : 's'} and ${data.history.length} test${data.history.length === 1 ? '' : 's'}.`);
});
$('#import-btn').addEventListener('click', () => $('#import-file').click());
$('#import-file').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  e.target.value = '';
  if (!file) return;
  try {
    if (file.size > 10 * 1024 * 1024) throw new Error('That file is too large to be a backup.');
    const res = store.importData(JSON.parse(await file.text()));
    if (!res.ok) throw new Error('Could not save: browser storage is full or turned off.');
    limit = PAGE;
    render();
    backupStatus(`Backup imported: ${res.added} new word${res.added === 1 ? '' : 's'}, ${res.total} in total, ${res.tests} test${res.tests === 1 ? '' : 's'} in your history.`);
  } catch (err) {
    backupStatus(err instanceof SyntaxError ? 'That file is not a valid backup.' : err.message);
  }
});

// Personal best, totals and the last 10 tests.
function renderProgress() {
  const hist = store.getHistory();
  $('#progress').hidden = !hist.length;
  if (!hist.length) return;
  $('#pb-wpm').textContent = store.getBest();
  $('#saved-count').textContent = store.wordStats().saved;
  $('#tests-count').textContent = hist.length;
  const last = hist.slice(0, 10);
  $('#history-body').innerHTML = last
    .map((h) => `<tr><td>${new Date(h.t).toLocaleDateString(undefined, { month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}</td><td>${h.wpm}</td><td>${h.acc}%</td><td>${h.learned}</td><td>${h.dur >= 60 ? `${Math.round(h.dur / 60)} min` : `${h.dur} s`}</td></tr>`)
    .join('');
  const series = last.slice().reverse().map((h, i) => ({ t: i + 1, wpm: h.wpm }));
  $('#history-chart').innerHTML = lineChart(series, { h: 120, label: 'WPM in your last tests', x0: 1, xFmt: (t) => (t === 1 ? 'oldest' : 'latest') });
}

render();
