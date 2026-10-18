// Typing engine: reads a hidden <input> via `input` events (works with Android's
// keyCode 229), renders a 3-line scrolling window and logs every keystroke.
import { coreStats } from './stats.js';
import { esc, reducedMotion } from './util.js';

const AHEAD = 60; // words rendered ahead of the caret; older lines are removed
const LOW_WATER = 40; // ask for more words when fewer than this remain
const NORMALIZE = { '‘': "'", '’': "'", '“': '"', '”': '"', '–': '-', '—': '-', ' ': ' ' };
const TOKEN = /[A-Za-z]+(?:'[A-Za-z]+)?/g;

export class Engine {
  constructor({ lines, input, box, overlay, hooks }) {
    Object.assign(this, { lines, input, box, overlay, hooks });
    input.addEventListener('input', (e) => this.onInput(e));
    input.addEventListener('keydown', (e) => this.onKey(e));
    input.addEventListener('beforeinput', (e) => {
      if (/FromPaste|FromDrop|Replacement|history/.test(e.inputType)) e.preventDefault();
    });
    for (const t of ['drop', 'cut']) input.addEventListener(t, (e) => e.preventDefault());
    input.addEventListener('focus', () => box.classList.add('is-focused'));
    input.addEventListener('blur', () => box.classList.remove('is-focused'));
    box.addEventListener('pointerup', () => {
      if (this.paused) this.resume();
      input.focus({ preventScroll: true });
    });
    document.addEventListener('visibilitychange', () => {
      if (document.hidden) this.pause(performance.now());
    });
    this.reset({ duration: 60 });
  }

  reset({ duration, finite = false, long = false, idle = 30, mode = 'learn' }) {
    clearInterval(this.timer);
    Object.assign(this, {
      duration: duration * 1000, finite, long, idleMs: idle * 1000, mode,
      words: [], wordItem: [], vocab: [], items: [], typedWords: [],
      wi: 0, typed: '', keys: [], pauses: [], paused: false, pauseStart: 0,
      started: false, finished: false, t0: 0, lastKey: 0,
      ins: 0, okIns: 0, okChars: 0, curItem: -1, firstEl: 0, rendered: 0, shifting: false,
    });
    this.lines.textContent = '';
    this.lines.style.transform = '';
    this.input.value = '';
    this.overlay.hidden = true;
    this.box.classList.remove('is-typing', 'is-paused');
  }

  // items: [{ rec, sentence, forms }]
  append(items) {
    for (const it of items) {
      const idx = this.items.length;
      const forms = new Set(it.forms.map((f) => f.toLowerCase()));
      it.start = this.words.length;
      for (const w of it.sentence.split(' ')) {
        this.words.push(w);
        this.wordItem.push(idx);
        // Speed mode streams only vocab words, so highlighting would mark every word.
        this.vocab.push(this.mode === 'learn' && (w.match(TOKEN) || []).some((t) => forms.has(t.toLowerCase())));
      }
      it.end = this.words.length - 1;
      this.items.push(it);
    }
    this.render();
    this.checkItem();
  }

  get remaining() { return this.words.length - this.wi; }

  // ------------------------------------------------------------ rendering
  charsHtml(target, typed, current) {
    let h = '';
    for (let k = 0; k < target.length; k++) {
      let cls = 'c';
      if (k < typed.length) cls += typed[k] === target[k] ? ' ok' : ' err';
      if (current && k === typed.length) cls += ' caret';
      h += `<span class="${cls}">${esc(target[k])}</span>`;
    }
    for (let k = target.length; k < typed.length; k++) h += `<span class="c extra">${esc(typed[k])}</span>`;
    return h + `<span class="c sp${current && typed.length >= target.length ? ' caret' : ''}"> </span>`;
  }

  render() {
    const end = Math.min(this.words.length, this.wi + AHEAD);
    if (this.rendered >= end) return;
    const frag = document.createDocumentFragment();
    for (let i = this.rendered; i < end; i++) {
      const el = document.createElement('span');
      el.className = this.vocab[i] ? 'w vocab' : 'w';
      if (i === this.wi) el.innerHTML = this.charsHtml(this.words[i], '', true);
      else if (this.vocab[i]) el.innerHTML = `<span class="vw">${esc(this.words[i])}</span> `;
      else el.textContent = `${this.words[i]} `;
      frag.append(el);
    }
    this.lines.append(frag);
    this.rendered = end;
  }

  el(i) { return this.lines.children[i - this.firstEl]; }

  paint() {
    const el = this.el(this.wi);
    if (!el) return;
    el.classList.add('cur');
    el.innerHTML = this.charsHtml(this.words[this.wi], this.typed, true);
    this.scroll();
  }

  // Keep the caret on line 1 or 2: when it reaches line 3, slide the first line out.
  scroll() {
    const el = this.el(this.wi);
    const first = this.lines.firstElementChild;
    if (!el || !first || this.shifting) return;
    const lh = parseFloat(getComputedStyle(this.lines).lineHeight) || 40;
    const line = Math.round((el.offsetTop - first.offsetTop) / lh);
    if (line < 2) return;
    const dy = (line - 1) * lh;
    const drop = () => {
      const cut = this.lines.firstElementChild.offsetTop + dy - lh / 2;
      while (this.lines.firstElementChild && this.lines.firstElementChild.offsetTop < cut && this.firstEl < this.wi) {
        this.lines.firstElementChild.remove();
        this.firstEl++;
      }
    };
    if (reducedMotion()) return drop();
    this.shifting = true;
    this.lines.style.transition = 'transform .18s ease';
    this.lines.style.transform = `translateY(${-dy}px)`;
    setTimeout(() => {
      this.lines.style.transition = 'none';
      drop();
      this.lines.style.transform = '';
      void this.lines.offsetHeight;
      this.lines.style.transition = '';
      this.shifting = false;
      this.scroll();
    }, 190);
  }

  checkItem() {
    const idx = this.wordItem[this.wi];
    if (idx !== undefined && idx !== this.curItem) {
      this.curItem = idx;
      this.hooks.onItem?.(this.items[idx]);
    }
  }

  // ------------------------------------------------------------ input
  onKey(e) {
    if (e.key === 'Escape') { e.preventDefault(); this.hooks.onRestart?.(); return; }
    if (e.key === 'Tab' && !e.shiftKey && this.started && !this.finished) { e.preventDefault(); this.hooks.onRestart?.(); return; }
    if (this.paused && !/^(Shift|Control|Alt|Meta|CapsLock|Tab|Unidentified|Process)$/.test(e.key)) {
      e.preventDefault();
      this.resume();
      return;
    }
    if (/^(Arrow|Home|End|Page)/.test(e.key) || ((e.ctrlKey || e.metaKey) && /^[azyx]$/i.test(e.key)) || e.key === 'Enter') e.preventDefault();
  }

  onInput(e) {
    if (e && /FromPaste|FromDrop/.test(e.inputType)) { this.input.value = this.typed; return; } // pasting is not typing
    const v = this.input.value;
    const now = performance.now();
    if (this.finished || this.wi >= this.words.length) { this.input.value = ''; return; }
    if (this.paused) { this.resume(); this.input.value = this.typed; return; }
    if (this.started && this.activeAt(now) >= this.duration) { this.finish(now); return; }
    const prev = this.typed;
    let p = 0;
    while (p < prev.length && p < v.length && prev[p] === v[p]) p++;
    for (let k = prev.length; k > p; k--) this.backspace(now);
    for (let ch of v.slice(p)) {
      ch = NORMALIZE[ch] || ch;
      if (ch === ' ') this.space(now);
      else if (ch >= ' ') this.insert(ch, now);
      if (this.finished || this.wi >= this.words.length) break;
    }
    if (this.input.value !== this.typed) this.input.value = this.typed;
    this.paint();
  }

  log(now, exp, ch) {
    this.keys.push([Math.round(now - this.t0), exp, ch, this.wi]);
    this.lastKey = now;
  }

  insert(ch, now) {
    if (!this.started) this.start(now);
    const target = this.words[this.wi];
    if (this.typed.length >= target.length + 12) return;
    const exp = target[this.typed.length] ?? '';
    this.log(now, exp, ch);
    this.ins++;
    if (ch === exp) this.okIns++;
    this.typed += ch;
  }

  backspace(now) {
    if (!this.typed) return;
    this.log(now, this.words[this.wi][this.typed.length - 1] ?? '', '');
    this.typed = this.typed.slice(0, -1);
  }

  space(now) {
    if (!this.typed) return; // a leading space does nothing
    const target = this.words[this.wi];
    const exp = this.typed.length >= target.length ? ' ' : target[this.typed.length];
    this.log(now, exp, ' ');
    this.ins++;
    if (exp === ' ') this.okIns++;
    this.commit();
  }

  commit() {
    const i = this.wi, target = this.words[i], ok = this.typed === target;
    if (ok) this.okChars += target.length + 1;
    this.typedWords[i] = this.typed;
    const el = this.el(i);
    if (el) {
      el.className = `w done${ok ? '' : ' wrong'}${this.vocab[i] ? ' vocab' : ''}`;
      el.innerHTML = this.charsHtml(target, this.typed, false);
    }
    const item = this.items[this.wordItem[i]];
    item.allOk = (item.allOk ?? true) && ok;
    this.wi++;
    this.typed = '';
    if (i === item.end) {
      item.done = true;
      this.hooks.onItemDone?.(item);
    }
    if (this.wi >= this.words.length && this.finite) { this.finish(performance.now()); return; }
    this.render();
    this.checkItem();
    if (!this.finite && this.remaining < LOW_WATER) this.hooks.onLow?.();
  }

  // ------------------------------------------------------------ time
  start(now) {
    this.started = true;
    this.t0 = now;
    this.lastKey = now;
    this.box.classList.add('is-typing');
    this.timer = setInterval(() => this.tick(), 100);
    this.hooks.onStart?.();
  }

  pausedTotal() { return this.pauses.reduce((a, [s, e]) => a + e - s, 0); }

  activeAt(now) {
    const wall = now - this.t0;
    return wall - this.pausedTotal() - (this.paused ? wall - this.pauseStart : 0);
  }

  stats(now = performance.now()) {
    if (!this.started) return coreStats(0, 0, 0, 0, 0);
    const target = this.words[this.wi] || '';
    const partial = this.typed && target.startsWith(this.typed) ? this.typed.length : 0;
    return coreStats(this.okChars + partial, this.ins, this.okIns, this.ins, this.activeAt(now) / 60000);
  }

  tick() {
    const now = performance.now();
    if (this.paused || this.finished) return;
    if (this.long && now - this.lastKey > this.idleMs) { this.pause(this.lastKey); return; }
    const act = this.activeAt(now);
    const left = Math.max(0, this.duration - act);
    this.hooks.onTick?.(left, act);
    if (left <= 0) this.finish(now);
  }

  // Long tests only. Idle pauses are backdated to the last keystroke, so idle time is excluded.
  pause(at) {
    if (!this.long || !this.started || this.finished || this.paused) return;
    this.paused = true;
    this.pauseStart = Math.round(at - this.t0);
    this.overlay.hidden = false;
    this.box.classList.add('is-paused');
    this.hooks.onPause?.(true);
    this.emitTime(performance.now()); // show the idle time being given back
  }

  emitTime(now) {
    const act = this.activeAt(now);
    this.hooks.onTick?.(Math.max(0, this.duration - act), act);
  }

  resume() {
    if (!this.paused) return;
    const now = performance.now();
    this.pauses.push([this.pauseStart, Math.round(now - this.t0)]);
    this.paused = false;
    this.lastKey = now;
    this.overlay.hidden = true;
    this.box.classList.remove('is-paused');
    this.hooks.onPause?.(false);
  }

  finish(now = performance.now()) {
    if (this.finished || !this.started) return;
    this.finished = true;
    clearInterval(this.timer);
    this.box.classList.remove('is-typing');
    const active = Math.min(this.activeAt(now), this.duration);
    const last = Math.min(this.wi, this.words.length - 1);
    this.hooks.onFinish?.({
      words: this.words.slice(0, last + 1),
      keystrokes: this.keys,
      duration_ms: Math.round(active + this.pausedTotal()),
      pauses: this.pauses,
      items: this.items.filter((it) => it.done),
      live: this.stats(now),
    });
  }
}
