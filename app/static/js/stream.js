// Word supply: random words from the API (paged by seed, so no repeats in a
// session), or a fixed list for practice sessions.
import { bnFor, formsOf } from './util.js';
import { senseIndex } from './card.js';

// The first Bangla meaning for the sense a sentence uses, shown above the word while typing.
const bnOf = (rec, sentence) => bnFor(rec, rec.senses[senseIndex(rec, sentence)].pos)?.[0] || '';

export class ApiSource {
  constructor(level) {
    this.level = level;
    this.seed = Math.floor(Math.random() * 2 ** 31);
    this.cursor = 0;
  }
  async next(count) {
    const q = new URLSearchParams({ level: this.level, count, seed: this.seed, cursor: this.cursor });
    const res = await fetch(`/api/vocab?${q}`);
    if (!res.ok) throw new Error(`vocab ${res.status}`);
    const data = await res.json();
    if (data.next_cursor == null) { this.seed = (this.seed + 1) % 2 ** 31; this.cursor = 0; }
    else this.cursor = data.next_cursor;
    return data.words;
  }
}

// One item per word: a sentence (Learn mode) or the bare word (Speed mode).
export function toItems(recs, mode) {
  return recs.map((rec) => ({ rec, forms: formsOf(rec), sentence: mode === 'speed' ? rec.word : rec.senses[0].examples[0], bn: bnOf(rec, rec.senses[0].examples[0]) }));
}

// A sentence the user has not typed yet, preferring a different meaning.
export function otherExample(rec, used) {
  const all = rec.senses.flatMap((s, si) => s.examples.map((x) => [x, si]));
  const usedSense = all.find(([x]) => x === used)?.[1] ?? 0;
  const fresh = all.filter(([x]) => x !== used);
  const otherSense = fresh.filter(([, si]) => si !== usedSense);
  const pool = otherSense.length ? otherSense : fresh.length ? fresh : all;
  return pool[Math.floor(Math.random() * pool.length)][0];
}

// entries: [{ rec, typed }] -> practice items with a new sentence each
export const practiceItems = (entries) =>
  entries.map(({ rec, typed }) => {
    const sentence = otherExample(rec, typed);
    return { rec, forms: formsOf(rec), sentence, bn: bnOf(rec, sentence), practice: true };
  });
