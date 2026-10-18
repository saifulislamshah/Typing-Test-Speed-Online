// Everything persists in this browser only (localStorage), never on a server.
const P = 'tt-';

export function get(key, fallback) {
  try {
    const v = localStorage.getItem(P + key);
    return v == null ? fallback : JSON.parse(v);
  } catch {
    return fallback;
  }
}
export function set(key, value) {
  try {
    localStorage.setItem(P + key, JSON.stringify(value));
    return true;
  } catch {
    return false;
  }
}

export const getSettings = () => get('settings', {});
export const saveSettings = (s) => set('settings', s);

export const getHistory = () => get('history', []);
export const getBest = () => get('best', 0);
export function addResult(r) {
  set('history', [r, ...getHistory()].slice(0, 50));
  if (r.wpm > getBest()) set('best', r.wpm);
}

// words: { id: { r: record, typed: last sentence typed, savedAt, lastAt, seen, known, practiced } }
// Every word learned in a test is saved automatically. The whole library (about 5,100
// words at ~600 characters each) fits well inside the ~5 MB localStorage quota.
export const getWords = () => get('words', {});
export function saveWords(entries) {
  const all = getWords();
  const now = Date.now();
  for (const { rec, typed } of entries) {
    const old = all[rec.id] || { savedAt: now, known: false, practiced: 0, seen: 0 };
    all[rec.id] = { ...old, r: rec, typed: typed || old.typed || '', lastAt: now, seen: (old.seen ?? 1) + 1 };
  }
  return set('words', all);
}

// ---- backup: one JSON file with everything this browser stores
const BACKUP_APP = 'typingtestspeedonline';
export const exportData = () => ({
  app: BACKUP_APP, version: 1, exportedAt: new Date().toISOString(),
  words: getWords(), history: getHistory(), best: getBest(), settings: getSettings(),
});

const isStr = (x) => typeof x === 'string';
const validRec = (r, id) => r && r.id === id && isStr(r.word) && isStr(r.level) && Array.isArray(r.senses) && r.senses.length > 0 &&
  r.senses.every((s) => s && isStr(s.pos) && isStr(s.label) && isStr(s.meaning) && Array.isArray(s.examples) && s.examples.every(isStr));
const when = (w) => w.lastAt || w.savedAt || 0;

// Merges a backup into this browser: nothing here is lost, newer data wins per word.
export function importData(d) {
  if (!d || d.app !== BACKUP_APP || typeof d.words !== 'object' || d.words === null) throw new Error('This is not a backup file from this site.');
  const words = getWords();
  let added = 0;
  for (const [id, w] of Object.entries(d.words)) {
    if (!w || !validRec(w.r, id)) continue;
    const cur = words[id];
    if (!cur) { words[id] = w; added++; continue; }
    words[id] = {
      ...(when(w) > when(cur) ? w : cur),
      savedAt: Math.min(cur.savedAt || Infinity, w.savedAt || Infinity),
      seen: Math.max(cur.seen || 1, w.seen || 1),
      practiced: Math.max(cur.practiced || 0, w.practiced || 0),
      known: !!(cur.known || w.known),
    };
  }
  const ts = new Set();
  const history = [...getHistory(), ...(Array.isArray(d.history) ? d.history : [])]
    .filter((h) => h && typeof h.t === 'number' && typeof h.wpm === 'number' && !ts.has(h.t) && ts.add(h.t))
    .sort((a, b) => b.t - a.t)
    .slice(0, 50);
  const ok = set('words', words) && set('history', history) && set('best', Math.max(getBest(), Number(d.best) || 0));
  return { ok, added, total: Object.keys(words).length, tests: history.length };
}
export function updateWord(id, patch) {
  const all = getWords();
  if (!all[id]) return;
  if (patch === null) delete all[id];
  else all[id] = { ...all[id], ...patch };
  set('words', all);
}
export function markPracticed(items) {
  const all = getWords();
  for (const { rec, sentence } of items) {
    if (all[rec.id]) {
      all[rec.id].practiced = (all[rec.id].practiced || 0) + 1;
      all[rec.id].typed = sentence;
    }
  }
  set('words', all);
}
export function wordStats() {
  const list = Object.values(getWords());
  return { saved: list.length, needPractice: list.filter((w) => !w.known && !w.practiced).length };
}
