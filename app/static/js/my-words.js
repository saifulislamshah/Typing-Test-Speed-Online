// My Words page: every saved word as a full card, with search, filters and practice.
import { $, bnAllHtml, cap, esc, initTheme, sensesHtml, speakBtn, wireWordUi } from './util.js';
import * as store from './storage.js';
import { lineChart } from './chart.js';

initTheme();
const list = $('#mw-list');
wireWordUi(list);

function render() {
  const all = Object.values(store.getWords()).sort((a, b) => b.savedAt - a.savedAt);
  const ws = store.wordStats();
  renderProgress();
  $('#mw-empty').hidden = all.length > 0;
  $('#mw-toolbar').hidden = all.length === 0;
  $('#mw-summary').textContent = all.length
    ? `You saved ${ws.saved} word${ws.saved === 1 ? '' : 's'} - ${ws.needPractice ? `${ws.needPractice} still need practice.` : 'all practiced. Nice work!'}`
    : 'Words you save after a test appear here, with every meaning and example.';
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
    (!q || r.word.includes(q) || r.senses.some((s) => s.meaning.toLowerCase().includes(q))));
  $('#mw-count').textContent = all.length ? `Showing ${shown.length} of ${all.length} words` : '';
  list.innerHTML = shown.map(cardHtml).join('');
}

function cardHtml({ r, known }) {
  return `<li class="mw-card${known ? ' is-known' : ''}">
<div class="wc-head"><h2 class="wc-word">${esc(r.word)}</h2><span class="pos-tag">${esc(r.level)}</span>${known ? '<span class="known-tag">Known</span>' : ''}</div>
<div class="wc-pron">${r.ipa ? `<span class="ipa">${esc(r.ipa)}</span>` : ''}${speakBtn(r.word)}</div>
${bnAllHtml(r)}
<p class="wc-meaning"><strong>${esc(cap(r.word))}</strong> means ${esc(r.senses[0].meaning)}.</p>
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
for (const id of ['#mw-search', '#mw-level', '#mw-status']) $(id).addEventListener('input', render);

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
