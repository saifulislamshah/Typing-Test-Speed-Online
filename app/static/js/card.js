// The word card under the typing text: word, IPA, pronunciation, English and Bangla
// meaning, with examples and other meanings behind a toggle.
import { bnHtml, esc, formsOf, highlight, meaningSentence, reducedMotion, sensesHtml, speakBtn, wireWordUi } from './util.js';

export class Card {
  constructor(root, body, toast, keepFocus) {
    Object.assign(this, { root, body, toast, open: false });
    wireWordUi(root, keepFocus);
    // Clicking the card must never take focus away from the typing input.
    root.addEventListener('pointerdown', (e) => { if (!e.target.closest('a')) e.preventDefault(); });
    // Remember whether the examples are open, so the next word keeps the same view.
    root.addEventListener('click', (e) => {
      const tg = e.target.closest('[data-toggle]');
      if (tg) this.open = tg.getAttribute('aria-expanded') === 'true';
    });
  }

  show(rec, sentence) {
    const html = cardHtml(rec, sentence, this.open);
    if (reducedMotion() || !this.body.innerHTML.includes('wc-word')) { this.body.innerHTML = html; return; }
    this.body.classList.add('is-changing');
    clearTimeout(this.t);
    this.t = setTimeout(() => { this.body.innerHTML = html; this.body.classList.remove('is-changing'); }, 140);
  }

  learned(word) {
    this.toast.textContent = `✓ ${word} learned`;
    this.toast.classList.add('show');
    clearTimeout(this.tt);
    this.tt = setTimeout(() => this.toast.classList.remove('show'), 900);
  }
}

// The sense a sentence belongs to (practice sentences may come from any sense).
export const senseIndex = (rec, sentence) => Math.max(0, rec.senses.findIndex((s) => s.examples.includes(sentence)));

export function cardHtml(rec, sentence, open = false) {
  const si = senseIndex(rec, sentence);
  const first = rec.senses[si];
  const rest = rec.senses.filter((_, i) => i !== si);
  const forms = formsOf(rec);
  // The typed sentence first, then the other examples of the same sense.
  const shown = sentence && first.examples.includes(sentence)
    ? [sentence, ...first.examples.filter((x) => x !== sentence)]
    : first.examples;
  const label = rest.length ? 'Examples and more meanings' : 'Examples';
  return `<div class="wc-head"><h2 class="wc-word" id="wc-word">${esc(rec.word)}</h2><span class="pos-tag">${esc(first.pos)}</span>
${rec.ipa ? `<span class="ipa">${esc(rec.ipa)}</span>` : ''}${speakBtn(rec.word)}</div>
${bnHtml(rec, first.pos)}
<p class="wc-meaning">${meaningSentence(rec, first)}</p>
<button type="button" class="link-btn wc-toggle" data-toggle="${label}" data-less="Hide examples" aria-expanded="${open}" aria-controls="wc-more">${open ? 'Hide examples' : label}</button>
<div class="wc-more" id="wc-more"${open ? '' : ' hidden'}>
<h3 class="ex-h">Example sentences</h3>
<p class="sense-label">${esc(first.label)}</p>
<ul class="examples">${shown.map((x) => `<li>${highlight(x, forms)}</li>`).join('')}</ul>
${rest.length ? sensesHtml(rec, rest) : ''}</div>`;
}
