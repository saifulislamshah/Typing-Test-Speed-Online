// Typing formulas. Mirrors app/analysis.py exactly; both are tested against
// tests/fixtures/formula_cases.json. Keystroke: [t_ms, expected, typed, wordIdx]
// where typed "" is a backspace and " " commits the word.
const BUCKET = 5000;
export const round1 = (x) => Math.floor(x * 10 + 0.5) / 10;

export function pausedBefore(t, pauses) {
  let total = 0;
  for (const [s, e] of pauses) {
    if (t >= e) total += e - s;
    else if (t > s) total += t - s;
  }
  return total;
}
export const activeMs = (dur, pauses) => Math.max(0, dur - pausedBefore(dur, pauses));

export function replay(words, keys) {
  const typed = words.map(() => '');
  const committed = words.map(() => false);
  const events = [];
  for (const [t, , ch, i] of keys) {
    const target = words[i];
    const cur = typed[i];
    if (ch === '') { typed[i] = cur.slice(0, -1); continue; }
    const pos = cur.length;
    let exp;
    if (ch === ' ') { exp = pos >= target.length ? ' ' : target[pos]; committed[i] = true; }
    else { exp = pos < target.length ? target[pos] : ''; typed[i] = cur + ch; }
    events.push([t, ch === exp, exp]);
  }
  return { typed, committed, events };
}

export function correctChars(words, typed, committed) {
  let n = 0;
  words.forEach((w, i) => {
    const tw = typed[i];
    if (committed[i]) { if (tw === w) n += w.length + 1; }
    else if (tw && w.startsWith(tw)) n += tw.length;
  });
  return n;
}

export function coreStats(correct, typedChars, correctKeys, totalKeys, minutes) {
  const accuracy = totalKeys ? round1((100 * correctKeys) / totalKeys) : 0;
  if (minutes <= 0) return { net_wpm: 0, raw_wpm: 0, cpm: 0, accuracy };
  return {
    net_wpm: round1(correct / 5 / minutes),
    raw_wpm: round1(typedChars / 5 / minutes),
    cpm: round1(correct / minutes),
    accuracy,
  };
}

const pstdev = (v) => { const m = v.reduce((a, b) => a + b, 0) / v.length; return Math.sqrt(v.reduce((a, b) => a + (b - m) ** 2, 0) / v.length); };

export function analyze(words, keys, durationMs, pauses) {
  const r = replay(words, keys);
  const ev = r.events;
  const act = activeMs(durationMs, pauses);
  const correct = correctChars(words, r.typed, r.committed);
  const correctKeys = ev.filter((e) => e[1]).length;
  const out = coreStats(correct, ev.length, correctKeys, ev.length, act / 60000);
  Object.assign(out, { correct_chars: correct, typed_chars: ev.length, errors: ev.length - correctKeys, active_seconds: round1(act / 1000) });

  const nb = Math.max(0, Math.ceil(act / BUCKET));
  const counts = new Array(nb).fill(0);
  for (const [t, ok] of ev) if (ok && nb) counts[Math.min(nb - 1, Math.floor((t - pausedBefore(t, pauses)) / BUCKET))]++;
  const series = [];
  counts.forEach((c, i) => {
    const span = Math.min(BUCKET, act - i * BUCKET);
    if (span >= 1000) series.push({ t: round1((i * BUCKET + span) / 1000), wpm: round1(c / 5 / (span / 60000)) });
  });
  const vals = series.map((p) => p.wpm);
  if (vals.length >= 2) {
    const sd = pstdev(vals);
    const mean = vals.reduce((a, b) => a + b, 0) / vals.length;
    out.consistency = { stdev: round1(sd), score: round1(mean ? Math.max(0, 100 - (sd / mean) * 100) : 0) };
  } else out.consistency = { stdev: 0, score: 0 };
  out.series = series;

  const totals = {}, misses = {};
  for (const [, ok, exp] of ev) {
    if (exp.length === 1 && exp !== ' ') {
      totals[exp] = (totals[exp] || 0) + 1;
      if (!ok) misses[exp] = (misses[exp] || 0) + 1;
    }
  }
  out.problem_keys = Object.entries(misses)
    .sort((a, b) => b[1] - a[1] || (a[0] < b[0] ? -1 : 1))
    .slice(0, 5)
    .map(([key, errors]) => ({ key, errors, total: totals[key] }));

  const seen = new Set(), mistyped = [];
  words.forEach((w, i) => {
    if (r.committed[i] && r.typed[i] !== w && !seen.has(w.toLowerCase())) { seen.add(w.toLowerCase()); mistyped.push({ word: w, typed: r.typed[i] }); }
  });
  out.mistyped_words = mistyped.slice(0, 20);
  return out;
}
