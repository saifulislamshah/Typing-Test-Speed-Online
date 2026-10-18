// The word card beside the typing box: word, IPA, pronunciation, meaning, examples.
import { esc, formsOf, highlight, meaningSentence, reducedMotion, sensesHtml, speakBtn, wireWordUi } from './util.js';

export class Card {
  constructor(root, body, toast, keepFocus) {
    Object.assign(this, { root, body, toast });
    wireWordUi(root, keepFocus);
    // Clicking the card must never take focus away from the typing input.
    root.addEventListener('pointerdown', (e) => { if (!e.target.closest('a')) e.preventDefault(); });
  }

  show(rec, sentence) {
    const html = cardHtml(rec, sentence);
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

export function cardHtml(rec, sentence) {
  const si = senseIndex(rec, sentence);
  const first = rec.senses[si];
  const rest = rec.senses.filter((_, i) => i !== si);
  const forms = formsOf(rec);
  // Collapsed view: the typed sentence first, then one more example of the same sense.
  const shown = sentence && first.examples.includes(sentence)
    ? [sentence, ...first.examples.filter((x) => x !== sentence)].slice(0, 2)
    : first.examples.slice(0, 2);
  const leftover = first.examples.filter((x) => !shown.includes(x));
  const more = [...(leftover.length ? [{ ...first, examples: leftover }] : []), ...rest];
  const label = rest.length ? 'More meanings' : 'More examples';
  return `<div class="wc-head"><h2 class="wc-word" id="wc-word">${esc(rec.word)}</h2><span class="pos-tag">${esc(first.pos)}</span></div>
<div class="wc-pron">${rec.ipa ? `<span class="ipa">${esc(rec.ipa)}</span>` : ''}${speakBtn(rec.word)}</div>
<p class="wc-meaning">${meaningSentence(rec, first)}</p>
<h3 class="ex-h">Example sentences</h3>
<p class="sense-label">${esc(first.label)}</p>
<ul class="examples">${shown.map((x) => `<li>${highlight(x, forms)}</li>`).join('')}</ul>
${more.length ? `<button type="button" class="link-btn" data-toggle="${label}" data-less="Show less" aria-expanded="false" aria-controls="wc-more">${label}</button>
<div class="wc-more" id="wc-more" hidden>${sensesHtml(rec, more)}</div>` : ''}`;
}
