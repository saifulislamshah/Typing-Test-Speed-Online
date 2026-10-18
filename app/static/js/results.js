// Result dialog: rank, message, personal best, words learned, analysis, sharing.
import { $, cfg, esc, formsOf, highlight, meaningSentence, sensesHtml, speakBtn, wireWordUi } from './util.js';
import { lineChart } from './chart.js';
import { canNativeShare, copyText, shareLinks } from './share.js';
import { burst } from './confetti.js';
import { saveWords } from './storage.js';
import { senseIndex } from './card.js';

const RANKS = [
  [70, 'falcon', 'Falcon', "Outstanding! That's elite-level typing. Can you keep it up with near-perfect accuracy?"],
  [50, 'cheetah', 'Cheetah', 'Fast! You type quicker than most people. Stay relaxed and keep your accuracy high.'],
  [35, 'rabbit', 'Rabbit', "That's a solid, comfortable speed. A little practice each day will make you a Cheetah."],
  [20, 'penguin', 'Penguin', 'Nice and steady! Short daily practice sessions will move you up quickly.'],
  [0, 'turtle', 'Turtle', 'Every fast typist started here. Keep your eyes on the text and let your fingers find a rhythm.'],
];
export const rankFor = (wpm) => RANKS.find(([min]) => wpm >= min);
const SHOW_FIRST = 3;

export class Results {
  constructor(hooks) {
    this.hooks = hooks;
    this.dlg = $('#result-dialog');
    wireWordUi(this.dlg);
    this.dlg.addEventListener('close', () => hooks.onClose(this.dlg.returnValue));
    this.dlg.addEventListener('keydown', (e) => this.trap(e));
    $('#try-again').addEventListener('click', () => this.dlg.close('again'));
    $('#change-settings').addEventListener('click', () => this.dlg.close('settings'));
    $('#result-close').addEventListener('click', () => this.dlg.close('close'));
    $('#show-all').addEventListener('click', (e) => {
      this.dlg.querySelectorAll('.lw[hidden]').forEach((li) => (li.hidden = false));
      e.target.hidden = true;
    });
    $('#save-words').addEventListener('click', () => this.save());
    $('#practice-again').addEventListener('click', () => {
      const picked = this.checked();
      if (!picked.length) return;
      this.dlg.close('practice');
      hooks.onPractice(picked);
    });
    $('#share-copy').addEventListener('click', async (e) => {
      const ok = await copyText(`${this.shareText} ${cfg.siteUrl}`);
      e.target.textContent = ok ? 'Link copied' : 'Copy failed';
      setTimeout(() => (e.target.textContent = 'Copy link'), 2000);
    });
    $('#share-native').addEventListener('click', () => navigator.share({ title: cfg.appName, text: this.shareText, url: cfg.siteUrl }).catch(() => {}));
  }

  trap(e) {
    if (e.key !== 'Tab') return;
    const f = [...this.dlg.querySelectorAll('button, a[href], input, [tabindex]:not([tabindex="-1"])')].filter((el) => !el.closest('[hidden]') && el.offsetParent !== null);
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && document.activeElement === first) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }

  // r: engine result; a: client analysis; prevBest: best WPM before this test
  open(r, a, prevBest, { practice = false } = {}) {
    const wpm = Math.round(a.net_wpm), cpm = Math.round(a.cpm), acc = Math.round(a.accuracy);
    const [, key, name, cheer] = rankFor(wpm);
    $('#mascot-use').setAttribute('href', `${cfg.assets}/img/mascots.svg#${key}`);
    $('#mascot-title').textContent = `${name} mascot`;
    $('#result-title').textContent = `You're a ${name}.`;
    const tip = acc < 85 ? '<span class="tip">Tip: slow down a little. Aim for accuracy first - speed follows once your fingers learn the right keys.</span>' : '';
    $('#result-msg').innerHTML = `Well... You type with the speed of <span class="hl">${wpm} WPM</span> (${cpm} CPM). Your accuracy was ${acc}%. ${cheer}${tip}`;

    const pb = $('#pb-line');
    pb.classList.remove('is-best');
    if (wpm > prevBest && wpm > 0) {
      pb.textContent = 'New personal best! \u{1F389}';
      pb.classList.add('is-best');
      burst($('#confetti'));
    } else if (wpm === prevBest && wpm > 0) pb.textContent = 'You matched your personal best!';
    else pb.textContent = wpm > 0 ? `${prevBest - wpm} WPM away from your best (${prevBest} WPM).` : '';

    // Words learned: one entry per word, with the sentence the user typed.
    const seen = new Set();
    this.learned = r.items.filter((it) => (r.mode === 'speed' ? it.allOk : true) && !seen.has(it.rec.id) && seen.add(it.rec.id));
    const n = this.learned.length;
    $('#learned-title').textContent = n
      ? `You ${practice ? 'practiced' : 'learned'} ${n} ${practice ? '' : 'new '}word${n === 1 ? '' : 's'}`
      : 'Finish a sentence to learn your first word';
    $('#learned-list').innerHTML = this.learned.map((it, i) => learnedHtml(it, i, r.mode)).join('');
    $('#show-all').hidden = n <= SHOW_FIRST;
    $('#show-all').textContent = `Show all ${n} words`;
    $('#save-words').hidden = $('#practice-again').hidden = !n;
    $('#save-words').textContent = 'Save to My Words';
    $('#save-words').classList.remove('is-done');
    $('#save-status').textContent = '';

    this.renderAnalysis(a);

    this.shareText = `I type ${wpm} WPM with ${acc}% accuracy - I'm a ${name}! I also learned ${n} new English word${n === 1 ? '' : 's'} on ${cfg.appName}.`;
    const links = shareLinks(this.shareText, cfg.siteUrl);
    $('#share-fb').href = links.fb;
    $('#share-li').href = links.li;
    $('#share-x').href = links.x;
    const native = canNativeShare();
    $('#share-native').hidden = !native;
    for (const id of ['#share-fb', '#share-li', '#share-x']) $(id).hidden = native;

    this.dlg.showModal();
    this.dlg.scrollTop = 0;
    $('#try-again').focus({ preventScroll: true });
    return { wpm, acc, name, learned: n };
  }

  renderAnalysis(a) {
    const cons = a.series.length >= 2 ? `${Math.round(a.consistency.score)}%` : '-';
    const cells = [
      ['Net speed', `${Math.round(a.net_wpm)} WPM`],
      ['Raw speed', `${Math.round(a.raw_wpm)} WPM`],
      ['Accuracy', `${Math.round(a.accuracy)}%`],
      ['Consistency', cons, a.series.length >= 2 ? `±${a.consistency.stdev} WPM` : ''],
    ];
    $('#analysis-grid').innerHTML = cells
      .map(([k, v, sub]) => `<div><dt>${k}</dt><dd>${v}</dd>${sub ? `<dd class="muted">${esc(sub)}</dd>` : ''}</div>`)
      .join('');
    $('#wpm-chart').innerHTML = lineChart(a.series, { empty: 'Type for at least 10 seconds to see your speed over time.' });
    $('#problem-keys').innerHTML = a.problem_keys.length
      ? a.problem_keys.map((k) => `<li><kbd>${esc(k.key)}</kbd><span class="muted">${k.errors} of ${k.total} wrong</span></li>`).join('')
      : '<li class="muted">No problem keys. Great accuracy!</li>';
    $('#mistyped').innerHTML = a.mistyped_words.length
      ? a.mistyped_words.slice(0, 10).map((m) => `<li><span class="sr-only">You typed </span><del>${esc(m.typed)}</del> <span aria-hidden="true">→</span><span class="sr-only">instead of</span> ${esc(m.word)}</li>`).join('')
      : '<li class="muted">None. Every word was right.</li>';
  }

  checked() {
    const ids = new Set([...this.dlg.querySelectorAll('.lw input:checked')].map((c) => c.value));
    return this.learned.filter((it) => ids.has(it.rec.id));
  }

  save() {
    const picked = this.checked();
    if (!picked.length) { $('#save-status').textContent = 'Select at least one word to save.'; return; }
    const ok = saveWords(picked.map((it) => ({ rec: it.rec, typed: it.sentence })));
    $('#save-status').innerHTML = ok
      ? `Saved ${picked.length} word${picked.length === 1 ? '' : 's'}. <a href="/my-words">Open My Words</a>`
      : 'Could not save: browser storage is unavailable.';
    if (ok) { $('#save-words').textContent = 'Saved ✓'; $('#save-words').classList.add('is-done'); }
    this.hooks.onSaved?.();
  }
}

function learnedHtml(it, i, mode) {
  const { rec } = it;
  const sentence = mode === 'speed' ? rec.senses[0].examples[0] : it.sentence;
  const id = `lw-more-${i}`;
  return `<li class="lw"${i >= SHOW_FIRST ? ' hidden' : ''}>
<div class="lw-head"><label><input type="checkbox" value="${esc(rec.id)}" checked><span class="sr-only">Save ${esc(rec.word)}</span></label>
<span class="lw-word">${esc(rec.word)}</span>${rec.ipa ? `<span class="ipa muted">${esc(rec.ipa)}</span>` : ''}${speakBtn(rec.word)}</div>
<p class="lw-meaning">${meaningSentence(rec, rec.senses[senseIndex(rec, sentence)])}</p>
<p class="lw-typed">${mode === 'speed' ? 'Example: ' : 'You typed: '}“${highlight(sentence, formsOf(rec))}”</p>
<button type="button" class="link-btn" data-toggle="All meanings and examples" data-less="Hide meanings" aria-expanded="false" aria-controls="${id}">All meanings and examples</button>
<div class="lw-more" id="${id}" hidden>${sensesHtml(rec, rec.senses)}</div></li>`;
}

