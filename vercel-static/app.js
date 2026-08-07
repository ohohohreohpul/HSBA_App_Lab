/* Supplier Scorecard — static build.
   Reads the frozen data.json (produced by build_static.py) and renders the
   editorial dashboard entirely client-side: overview story stats, a sortable /
   filterable board, a per-supplier drilldown drawer, and inline-SVG analytics.
   No framework, no backend. */

'use strict';

const RISK_COLOR = { High: '#c0392b', Medium: '#b07400', Low: '#2f7d55', Unknown: '#6f6d66' };
const INK = '#1a1a1a', MUTED = '#6f6d66', LINE = '#dedcd5';

let DATA = null, META = null, SUPPLIERS = [];
const sortState = { key: 'overall', dir: 'desc' };
const filters = { search: '', country: '', category: '', risk: '', below: false, lowconf: false };

/* ---------- tiny DOM + format helpers ---------- */
const $ = (sel, root = document) => root.querySelector(sel);
const $$ = (sel, root = document) => [...root.querySelectorAll(sel)];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => (
  { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const eur = (v) => v == null ? '—' : '€' + Math.round(v).toLocaleString('en-US');
const sc = (v) => v == null ? '—' : Number(v).toFixed(2);
const pct = (v) => v == null ? '—' : Math.round(v * 100) + '%';

function tag(text, color) {
  return `<span class="badge" style="color:${color}">${esc(text)}</span>`;
}
function riskTag(level, prefix = '') {
  return tag((prefix ? prefix + ' ' : '') + level, RISK_COLOR[level] || MUTED);
}
function confTag(low, n) {
  return low ? tag(`Confidence: Low${n != null ? ` (${n})` : ''}`, RISK_COLOR.Medium)
             : tag('Confidence: OK', RISK_COLOR.Low);
}

/* ---------- SVG chart primitives ---------- */
function sparkline(values, w = 120, h = 30) {
  const pts = values.filter((v) => v != null);
  if (pts.length < 2) return '';
  const lo = Math.min(...pts), hi = Math.max(...pts), span = (hi - lo) || 1;
  const coords = pts.map((v, i) => {
    const x = (i / (pts.length - 1)) * (w - 2) + 1;
    const y = h - 1 - ((v - lo) / span) * (h - 2);
    return `${x.toFixed(1)},${y.toFixed(1)}`;
  }).join(' ');
  return `<svg class="s-spark" width="${w}" height="${h}" viewBox="0 0 ${w} ${h}"
    fill="none" preserveAspectRatio="none" aria-hidden="true">
    <polyline points="${coords}" stroke="${INK}" stroke-width="1.25"
      stroke-linejoin="round" stroke-linecap="round"/></svg>`;
}

function hBars(rows, { valueKey, labelKey, colorFn, max, fmt }) {
  const width = 460, rowH = 26, pad = 8, labelW = 130, barMax = width - labelW - 60;
  const top = max ?? Math.max(...rows.map((r) => r[valueKey]), 1);
  const body = rows.map((r, i) => {
    const y = pad + i * rowH;
    const bw = Math.max(1, (r[valueKey] / top) * barMax);
    const color = colorFn ? colorFn(r) : INK;
    return `<text x="0" y="${y + 14}" font-family="var(--font-mono)" font-size="11" fill="${MUTED}">${esc(r[labelKey])}</text>
      <rect x="${labelW}" y="${y + 4}" width="${bw}" height="15" fill="${color}"/>
      <text x="${labelW + bw + 6}" y="${y + 15}" font-family="var(--font-mono)" font-size="11" fill="${INK}">${fmt ? fmt(r[valueKey]) : r[valueKey]}</text>`;
  }).join('');
  const h = pad * 2 + rows.length * rowH;
  return `<svg width="100%" viewBox="0 0 ${width} ${h}" role="img">${body}</svg>`;
}

function histogram(counts, edges) {
  const width = 460, height = 220, padL = 34, padB = 26, padT = 8;
  const n = counts.length, top = Math.max(...counts, 1);
  const bw = (width - padL) / n;
  const bars = counts.map((c, i) => {
    const bh = (c / top) * (height - padB - padT);
    const x = padL + i * bw, y = height - padB - bh;
    return `<rect x="${x + 1}" y="${y}" width="${bw - 2}" height="${bh}" fill="${INK}"/>`;
  }).join('');
  const ticks = [0, Math.round(top / 2), top].map((t) => {
    const y = height - padB - (t / top) * (height - padB - padT);
    return `<text x="${padL - 6}" y="${y + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="10" fill="${MUTED}">${t}</text>`;
  }).join('');
  const xlabs = [0, Math.floor(n / 2), n - 1].map((i) => {
    const x = padL + i * bw + bw / 2;
    return `<text x="${x}" y="${height - 8}" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="${MUTED}">${edges[i].toFixed(1)}</text>`;
  }).join('');
  return `<svg width="100%" viewBox="0 0 ${width} ${height}" role="img">${bars}${ticks}${xlabs}</svg>`;
}

function donut(counts) {
  const order = ['High', 'Medium', 'Low'];
  const total = order.reduce((s, k) => s + (counts[k] || 0), 0) || 1;
  const cx = 90, cy = 90, r = 70, rin = 44;
  let a0 = -Math.PI / 2;
  const arcs = order.map((k) => {
    const frac = (counts[k] || 0) / total;
    const a1 = a0 + frac * 2 * Math.PI;
    const large = frac > 0.5 ? 1 : 0;
    const p = (ang, rad) => `${cx + rad * Math.cos(ang)},${cy + rad * Math.sin(ang)}`;
    const d = `M ${p(a0, r)} A ${r} ${r} 0 ${large} 1 ${p(a1, r)} L ${p(a1, rin)} A ${rin} ${rin} 0 ${large} 0 ${p(a0, rin)} Z`;
    a0 = a1;
    return frac > 0 ? `<path d="${d}" fill="${RISK_COLOR[k]}"/>` : '';
  }).join('');
  return `<svg width="180" height="180" viewBox="0 0 180 180" role="img">${arcs}</svg>`;
}

function heatmap(cells) {
  const cats = [...new Set(cells.map((c) => c.category))];
  const crits = [...new Set(cells.map((c) => c.criterion))];
  const cw = 96, ch = 30, padL = 150, padT = 26;
  const scoreColor = (v) => {
    if (v == null) return '#eee';
    const t = Math.max(0, Math.min(1, (v - 2) / 3)); // 2→red .. 5→green
    const r = Math.round(192 + (47 - 192) * t), g = Math.round(57 + (125 - 57) * t), b = Math.round(43 + (85 - 43) * t);
    return `rgb(${r},${g},${b})`;
  };
  const head = crits.map((c, j) => `<text x="${padL + j * cw + cw / 2}" y="${padT - 8}" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="${MUTED}">${esc(c)}</text>`).join('');
  const body = cats.map((cat, i) => {
    const rowLabel = `<text x="0" y="${padT + i * ch + 20}" font-family="var(--font-mono)" font-size="11" fill="${MUTED}">${esc(cat)}</text>`;
    const rects = crits.map((cr, j) => {
      const cell = cells.find((c) => c.category === cat && c.criterion === cr);
      const v = cell ? cell.score : null;
      return `<rect x="${padL + j * cw}" y="${padT + i * ch}" width="${cw - 2}" height="${ch - 2}" fill="${scoreColor(v)}"/>
        <text x="${padL + j * cw + cw / 2 - 1}" y="${padT + i * ch + 19}" text-anchor="middle" font-family="var(--font-mono)" font-size="10" fill="#fff">${v == null ? '—' : v.toFixed(1)}</text>`;
    }).join('');
    return rowLabel + rects;
  }).join('');
  const w = padL + crits.length * cw, h = padT + cats.length * ch + 6;
  return `<svg width="100%" viewBox="0 0 ${w} ${h}" role="img">${head}${body}</svg>`;
}

function trendLine(trend, threshold) {
  if (!trend || trend.length < 2) return '<p class="cap">Not enough dated orders to plot a trend.</p>';
  const width = 560, height = 200, padL = 34, padB = 28, padT = 10;
  const xs = trend.map((_, i) => padL + (i / (trend.length - 1)) * (width - padL - 10));
  const yOf = (v) => height - padB - ((v - 1) / 4) * (height - padB - padT); // 1..5
  const pts = trend.map((t, i) => `${xs[i].toFixed(1)},${yOf(t.overall).toFixed(1)}`).join(' ');
  const dots = trend.map((t, i) => `<circle cx="${xs[i].toFixed(1)}" cy="${yOf(t.overall).toFixed(1)}" r="3" fill="${INK}"/>`).join('');
  const thY = yOf(threshold);
  const xlabs = trend.map((t, i) => `<text x="${xs[i]}" y="${height - 10}" text-anchor="middle" font-family="var(--font-mono)" font-size="9" fill="${MUTED}">${esc(t.quarter)}</text>`).join('');
  const ylabs = [1, 3, 5].map((v) => `<text x="${padL - 6}" y="${yOf(v) + 3}" text-anchor="end" font-family="var(--font-mono)" font-size="10" fill="${MUTED}">${v}</text>`).join('');
  return `<svg width="100%" viewBox="0 0 ${width} ${height}" role="img">
    <line x1="${padL}" y1="${thY}" x2="${width - 10}" y2="${thY}" stroke="${RISK_COLOR.High}" stroke-width="1" stroke-dasharray="5 4"/>
    <polyline points="${pts}" fill="none" stroke="${INK}" stroke-width="2"/>${dots}${xlabs}${ylabs}</svg>`;
}

/* ---------- story stats ---------- */
function statCell({ label, value, delta, dir, spark }) {
  const dcls = dir === 'up' ? ' up' : dir === 'down' ? ' down' : '';
  return `<div class="stat"><div class="s-label">${esc(label)}</div>
    <div class="s-value tnum">${esc(value)}</div>
    ${delta ? `<div class="s-delta${dcls}">${esc(delta)}</div>` : ''}
    ${spark ? sparkline(spark) : ''}</div>`;
}

function renderOverview() {
  const t = META.totals, th = META.threshold;
  const worst = SUPPLIERS.reduce((a, b) => (a.overall ?? 9) < (b.overall ?? 9) ? a : b);
  $('#hero-head').textContent = t.below_threshold
    ? `${t.suppliers} suppliers. ${t.below_threshold} sit below the line.`
    : `${t.suppliers} suppliers. None below the line.`;
  const above = t.avg_score - th;
  $('#story-stats').innerHTML = [
    statCell({ label: 'Suppliers', value: t.suppliers, delta: `${t.countries} countries` }),
    statCell({ label: 'Avg. score', value: t.avg_score.toFixed(2),
      delta: `${above >= 0 ? '+' : ''}${above.toFixed(2)} vs the ${th.toFixed(1)} review line`,
      dir: above >= 0 ? 'up' : 'down', spark: META.score_distribution.counts }),
    statCell({ label: 'Below the line', value: t.below_threshold,
      delta: `${Math.round(t.below_threshold / t.suppliers * 100)}% of the book`,
      dir: t.below_threshold ? 'down' : 'up' }),
    statCell({ label: 'High risk', value: t.high_risk,
      delta: `worst ${worst.name} ${sc(worst.overall)}`, dir: t.high_risk ? 'down' : 'up' }),
    statCell({ label: 'Cancelled', value: t.cancelled,
      delta: `${Math.round(t.cancelled / t.total_orders * 100)}% of ${t.total_orders} orders` }),
  ].join('');
}

/* ---------- scorecards board ---------- */
const COLS = [
  { key: 'name', label: 'Supplier', num: false },
  { key: 'country', label: 'Country', num: false },
  { key: 'category', label: 'Category', num: false },
  { key: 'overall', label: 'Overall', num: true },
  { key: 'risk', label: 'Risk', num: false },
  { key: 'low_confidence', label: 'Confidence', num: false },
  { key: 'num_orders', label: 'Orders', num: true },
  { key: 'total_spend', label: 'Total spend', num: true },
];

function filtered() {
  const q = filters.search.trim().toLowerCase();
  let rows = SUPPLIERS.filter((s) => {
    if (q && !s.name.toLowerCase().includes(q)) return false;
    if (filters.country && s.country !== filters.country) return false;
    if (filters.category && s.category !== filters.category) return false;
    if (filters.risk && s.risk !== filters.risk) return false;
    if (filters.below && !(s.overall != null && s.overall < META.threshold)) return false;
    if (filters.lowconf && !s.low_confidence) return false;
    return true;
  });
  const { key, dir } = sortState, mul = dir === 'asc' ? 1 : -1;
  rows.sort((a, b) => {
    let x = a[key], y = b[key];
    if (typeof x === 'string') { x = x.toLowerCase(); y = (y || '').toLowerCase(); return x < y ? -mul : x > y ? mul : 0; }
    x = x == null ? -Infinity : x; y = y == null ? -Infinity : y;
    return (x - y) * mul;
  });
  return rows;
}

function renderBoard() {
  const rows = filtered(), th = META.threshold;
  $('#board thead').innerHTML = '<tr>' + COLS.map((c) => {
    const arrow = sortState.key === c.key ? `<span class="arrow"> ${sortState.dir === 'asc' ? '↑' : '↓'}</span>` : '';
    return `<th data-key="${c.key}" class="${c.num ? 'num' : ''}">${c.label}${arrow}</th>`;
  }).join('') + '</tr>';
  $('#board tbody').innerHTML = rows.map((s) => `
    <tr data-id="${s.id}">
      <td>${esc(s.name)}</td>
      <td>${esc(s.country)}</td>
      <td>${esc(s.category)}</td>
      <td class="num ${s.overall != null && s.overall < th ? 'below' : ''}">${sc(s.overall)}</td>
      <td>${riskTag(s.risk)}</td>
      <td class="${s.low_confidence ? 'lowconf' : ''}">${s.low_confidence ? 'Low' : 'OK'}</td>
      <td class="num">${s.num_orders}</td>
      <td class="num">${eur(s.total_spend)}</td>
    </tr>`).join('');
  const nBelow = rows.filter((s) => s.overall != null && s.overall < th).length;
  $('#count-note').textContent = `${rows.length} of ${SUPPLIERS.length} suppliers`
    + (nBelow ? ` · ${nBelow} below the ${th.toFixed(1)} line` : '')
    + ' · red = below the line · click a row for the full drilldown';
  $$('#board thead th').forEach((th2) => th2.addEventListener('click', () => {
    const k = th2.dataset.key;
    if (sortState.key === k) sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
    else { sortState.key = k; sortState.dir = (k === 'name' || k === 'country' || k === 'category') ? 'asc' : 'desc'; }
    renderBoard();
  }));
  $$('#board tbody tr').forEach((tr) => tr.addEventListener('click', () => openDrawer(+tr.dataset.id)));
}

/* ---------- drilldown drawer ---------- */
function tile(label, value, sub) {
  return `<div class="tile"><div class="t-label">${esc(label)}</div>
    <div class="t-value tnum">${esc(value)}</div>
    ${sub ? `<div class="t-sub">${esc(sub)}</div>` : ''}</div>`;
}

function openDrawer(id) {
  const s = SUPPLIERS.find((x) => x.id === id);
  if (!s) return;
  const th = META.threshold, cw = META.cancel_weight, baseShare = 1 - cw;
  const wmap = Object.fromEntries(META.criteria.map((c) => [c.key, c.weight]));

  // Components with effective weights (mirrors the Streamlit drilldown).
  const comps = [
    { key: 'delivery_time', label: 'Delivery', value: s.avg_delivery_days == null ? '—' : `${s.avg_delivery_days.toFixed(1)} days`, score: s.delivery_time, w: (wmap.delivery_time || 0) * baseShare },
    { key: 'quality', label: 'Quality', value: sc(s.quality), score: s.quality, w: (wmap.quality || 0) * baseShare },
    { key: 'price', label: 'Price', value: eur(s.avg_price_eur), score: s.price, w: (wmap.price || 0) * baseShare },
    { key: 'communication', label: 'Communication', value: sc(s.communication), score: s.communication, w: (wmap.communication || 0) * baseShare },
    { key: 'reliability', label: 'Reliability', value: s.cancel_rate == null ? '—' : `${pct(s.cancel_rate)} cancelled`, score: s.reliability, w: cw },
  ];

  const violations = comps.filter((c) => c.score != null && c.score < th);
  const recos = [];
  if (s.overall != null && s.overall < th) recos.push('Overall score is below the line — consider a formal review or corrective-action plan.');
  const weakest = comps.filter((c) => c.score != null).sort((a, b) => a.score - b.score)[0];
  if (weakest && weakest.score < 3.5) recos.push(`Weakest area is ${weakest.label} (${sc(weakest.score)}). Raise this in the next review.`);
  if (s.cancel_rate != null && s.cancel_rate >= 0.25) recos.push(`High cancellation rate (${pct(s.cancel_rate)}) — investigate why orders are being cancelled.`);
  if (s.low_confidence) recos.push('Few rated orders — gather more feedback before major decisions.');
  if (!recos.length) recos.push('Performing well across the board. Maintain the relationship.');

  const specialTag = s.has_special ? ' ' + tag(`Special circumstance${s.num_special > 1 ? ' x' + s.num_special : ''}`, INK) : '';

  const ordersRows = s.orders.map((o) => `<tr>
    <td class="mono">${esc(o.order)}</td><td class="mono">${esc(o.ordered || '—')}</td>
    <td class="mono">${esc(o.delivered || '—')}</td><td class="num">${o.days == null ? '—' : o.days + ' d'}</td>
    <td class="num">${eur(o.amount)}</td><td>${esc(o.status)}</td>
    <td class="num">${sc(o.quality)}</td><td class="num">${sc(o.communication)}</td></tr>`).join('');

  $('#drawer').innerHTML = `
    <button class="btn close" id="drawer-close">Close</button>
    <h2>${esc(s.name)}</h2>
    <div class="meta-line">${riskTag(s.risk, 'Risk:')} ${confTag(s.low_confidence, s.num_ratings)}${specialTag}</div>
    <div class="meta-line">${esc(s.country)} · ${esc(s.category)} · ${esc(s.email || '—')}</div>

    <div class="tiles section">
      ${tile('Overall', sc(s.overall))}
      ${tile('Orders', s.num_orders, `${s.num_delivered} delivered`)}
      ${tile('Total spend', eur(s.total_spend))}
      ${tile('Cancelled', s.num_cancelled, s.cancel_rate == null ? '' : `${pct(s.cancel_rate)} of resolved`)}
    </div>

    <h3 class="section">Score components</h3>
    <div class="tiles">
      ${comps.map((c) => tile(c.label, c.value,
        `${c.score == null ? '—' : 'score ' + sc(c.score) + '/5'} · ${Math.round(c.w * 100)}%`)).join('')}
    </div>

    <div class="grid-2 section">
      <div>
        <h3>Threshold violations</h3>
        ${violations.length
          ? violations.map((v) => `<div class="note bad"><strong>${esc(v.label)}</strong>: ${sc(v.score)} (below ${th.toFixed(1)})</div>`).join('')
          : `<div class="note ok">No component below the ${th.toFixed(1)} line.</div>`}
      </div>
      <div>
        <h3>Recommendations</h3>
        ${recos.map((r) => `<div class="reco">${esc(r)}</div>`).join('')}
      </div>
    </div>

    <h3 class="section">Performance trend</h3>
    ${trendLine(s.trend, th)}
    <p class="cap">Line = average overall score per quarter · dashed = the ${th.toFixed(1)} review line.</p>

    <h3 class="section">Orders</h3>
    <div class="tbl-wrap"><table><thead><tr>
      <th>Order</th><th>Ordered</th><th>Delivered</th><th class="num">Days</th>
      <th class="num">Amount</th><th>Status</th><th class="num">Qual.</th><th class="num">Comm.</th>
    </tr></thead><tbody>${ordersRows || '<tr><td colspan="8">No orders on record.</td></tr>'}</tbody></table></div>`;

  $('#drawer-close').addEventListener('click', closeDrawer);
  $('#overlay').classList.add('open');
  $('#drawer').classList.add('open');
  $('#drawer').setAttribute('aria-hidden', 'false');
}

function closeDrawer() {
  $('#overlay').classList.remove('open');
  $('#drawer').classList.remove('open');
  $('#drawer').setAttribute('aria-hidden', 'true');
}

/* ---------- analytics ---------- */
function renderAnalytics() {
  const t = META.totals;
  $('#an-stats').innerHTML = [
    statCell({ label: 'Suppliers', value: t.suppliers }),
    statCell({ label: 'Avg. score', value: t.avg_score.toFixed(2) }),
    statCell({ label: 'Below threshold', value: t.below_threshold }),
    statCell({ label: 'High risk', value: t.high_risk }),
    statCell({ label: 'Countries', value: t.countries }),
    statCell({ label: 'Categories', value: t.categories }),
  ].join('');

  const legend = ['High', 'Medium', 'Low'].map((k) =>
    `<span><i style="background:${RISK_COLOR[k]}"></i>${k} (${META.risk_counts[k]})</span>`).join('');
  $('#chart-risk').innerHTML = `<h3>Risk distribution</h3><p class="cap">Suppliers by risk band.</p>
    <div style="display:flex;justify-content:center">${donut(META.risk_counts)}</div>
    <div class="legend" style="justify-content:center">${legend}</div>`;

  $('#chart-hist').innerHTML = `<h3>Score distribution</h3><p class="cap">How overall scores spread, 1–5.</p>
    ${histogram(META.score_distribution.counts, META.score_distribution.edges)}`;

  $('#chart-country').innerHTML = `<h3>Suppliers by country</h3><p class="cap">Top 12 by count.</p>
    ${hBars(META.country_counts, { valueKey: 'count', labelKey: 'country' })}`;

  const scoreColor = (r) => r.avg == null ? MUTED : r.avg < 2.5 ? RISK_COLOR.High : r.avg < 3.5 ? RISK_COLOR.Medium : RISK_COLOR.Low;
  $('#chart-category').innerHTML = `<h3>Avg. score by category</h3><p class="cap">Coloured by risk band.</p>
    ${hBars([...META.category_avg].sort((a, b) => (b.avg || 0) - (a.avg || 0)),
      { valueKey: 'avg', labelKey: 'category', colorFn: scoreColor, max: 5, fmt: (v) => v == null ? '—' : v.toFixed(2) })}`;

  $('#chart-heat').innerHTML = `<h3>Category × criterion</h3>
    <p class="cap">Each cell is a category's average score for one criterion. Green = strong, red = weak.</p>
    ${heatmap(META.heatmap)}`;
}

/* ---------- nav + boot ---------- */
function switchView(view) {
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
  $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  window.scrollTo({ top: 0, behavior: 'auto' });
}

function initFilters() {
  const uniq = (key) => [...new Set(SUPPLIERS.map((s) => s[key]).filter(Boolean))].sort();
  const fill = (sel, opts, allLabel) => {
    $(sel).innerHTML = `<option value="">${allLabel}</option>` + opts.map((o) => `<option>${esc(o)}</option>`).join('');
  };
  fill('#f-country', uniq('country'), 'All countries');
  fill('#f-category', uniq('category'), 'All categories');
  fill('#f-risk', ['High', 'Medium', 'Low'], 'All risk levels');

  $('#search').addEventListener('input', (e) => { filters.search = e.target.value; renderBoard(); });
  $('#f-country').addEventListener('change', (e) => { filters.country = e.target.value; renderBoard(); });
  $('#f-category').addEventListener('change', (e) => { filters.category = e.target.value; renderBoard(); });
  $('#f-risk').addEventListener('change', (e) => { filters.risk = e.target.value; renderBoard(); });
  $('#t-below').addEventListener('change', (e) => { filters.below = e.target.checked; renderBoard(); });
  $('#t-lowconf').addEventListener('change', (e) => { filters.lowconf = e.target.checked; renderBoard(); });
}

async function boot() {
  try {
    const res = await fetch('./data.json');
    if (!res.ok) throw new Error(`data.json ${res.status}`);
    DATA = await res.json();
  } catch (e) {
    $('#hero-head').textContent = 'Could not load data.';
    console.error(e);
    return;
  }
  META = DATA.meta; SUPPLIERS = DATA.suppliers;
  renderOverview();
  initFilters();
  renderBoard();
  renderAnalytics();

  document.body.addEventListener('click', (e) => {
    const nav = e.target.closest('[data-view]');
    if (nav) switchView(nav.dataset.view);
  });
  $('#overlay').addEventListener('click', closeDrawer);
  document.addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
}

boot();
