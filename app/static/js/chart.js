// Tiny hand-written SVG line chart. series: [{ t, wpm }]
const fmtTime = (s) => (s >= 60 ? `${Math.floor(s / 60)}m${s % 60 ? ` ${Math.round(s % 60)}s` : ''}` : `${Math.round(s)}s`);

export function lineChart(series, { w = 640, h = 170, label = 'Words per minute over time', xFmt = fmtTime, x0 = 0, empty = '' } = {}) {
  if (series.length < 2) return empty ? `<p class="muted">${empty}</p>` : '';
  const pad = { l: 34, r: 10, t: 10, b: 24 };
  const peak = Math.max(...series.map((p) => p.wpm));
  const top = Math.max(10, Math.ceil(peak / 10) * 10);
  const tMax = series[series.length - 1].t;
  const span = tMax - x0 || 1;
  const x = (t) => (pad.l + ((t - x0) / span) * (w - pad.l - pad.r)).toFixed(1);
  const y = (v) => (pad.t + (1 - v / top) * (h - pad.t - pad.b)).toFixed(1);
  const pts = series.map((p) => `${x(p.t)},${y(p.wpm)}`).join(' ');
  const base = y(0);
  const grid = [0, top / 2, top]
    .map((v) => `<line class="grid" x1="${pad.l}" x2="${w - pad.r}" y1="${y(v)}" y2="${y(v)}"/><text class="axis" x="${pad.l - 6}" y="${+y(v) + 4}" text-anchor="end">${v}</text>`)
    .join('');
  const first = series[0], last = series[series.length - 1];
  const desc = `${label}: starts at ${Math.round(first.wpm)}, ends at ${Math.round(last.wpm)}, peak ${Math.round(peak)} WPM.`;
  return `<svg viewBox="0 0 ${w} ${h}" role="img" aria-label="${desc}">${grid}
<path class="area" d="M${x(first.t)},${base} L${pts.replaceAll(' ', ' L')} L${x(last.t)},${base} Z"/>
<polyline class="line" points="${pts}"/>
${series.length <= 12 ? series.map((p) => `<circle class="dot" cx="${x(p.t)}" cy="${y(p.wpm)}" r="3.5"/>`).join('') : ''}
<text class="axis" x="${pad.l}" y="${h - 6}">${xFmt(first.t)}</text><text class="axis" x="${w - pad.r}" y="${h - 6}" text-anchor="end">${xFmt(last.t)}</text></svg>`;
}
