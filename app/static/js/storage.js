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

// words: { id: { r: record, typed: last sentence typed, savedAt, known, practiced } }
export const getWords = () => get('words', {});
export function saveWords(entries) {
  const all = getWords();
  for (const { rec, typed } of entries) {
    const old = all[rec.id] || { savedAt: Date.now(), known: false, practiced: 0 };
    all[rec.id] = { ...old, r: rec, typed: typed || old.typed || '' };
  }
  return set('words', all);
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
