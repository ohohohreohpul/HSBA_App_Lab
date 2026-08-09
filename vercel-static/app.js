/* Supplier Scorecard — static build.
   Glassmorphism analytics, ZERO gradients. ApexCharts carries the data
   storytelling; scroll-reveal, KPI count-up, hover/focus tooltips and filter
   toasts make it feel alive. No framework, no backend. */

'use strict';

const C = {
  ink: '#171c26', ink2: '#3a4453', muted: '#6a7480',
  accent: '#0d9488', high: '#dc2626', med: '#d97706', low: '#16a34a',
  grid: 'rgba(23,28,38,0.08)',
};
const RISK_COLOR = { High: C.high, Medium: C.med, Low: C.low, Unknown: C.muted };
const FONT = 'Inter, sans-serif';
const reduce = matchMedia('(prefers-reduced-motion: reduce)').matches;

let META = null, SUPPLIERS = [];
const charts = {};
const rendered = { analytics: false };
const sortState = { key: 'overall', dir: 'desc' };
const filters = { search: '', country: '', category: '', risk: '', below: false, lowconf: false };
let lastFocus = null;

/* ---------- helpers ---------- */
const $ = (s, r = document) => r.querySelector(s);
const $$ = (s, r = document) => [...r.querySelectorAll(s)];
const esc = (s) => String(s ?? '').replace(/[&<>"]/g, (c) => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));
const eur = (v) => v == null ? '—' : '€' + Math.round(v).toLocaleString('en-US');
const sc = (v) => v == null ? '—' : Number(v).toFixed(2);
const pct = (v) => v == null ? '—' : Math.round(v * 100) + '%';
const fmtNum = (v, d = 0) => d > 0 ? Number(v).toFixed(d) : Math.round(v).toLocaleString('en-US');

const TIPS = {
  Suppliers: 'Every supplier on record, across all countries and categories.',
  'Average score': 'Mean overall score (1–5). The review line is 3.0.',
  'Below the line': 'Suppliers scoring under the 3.0 review threshold — triage these first.',
  'High risk': 'Overall score under 2.5. The most urgent to act on.',
  'In transit': 'Orders shipped but not yet delivered.',
  overall: 'Weighted 1–5 score: delivery, price, quality, communication and reliability.',
  risk: 'High &lt; 2.5 · Medium 2.5–3.5 · Low ≥ 3.5.',
  low_confidence: '“Low” means fewer than 3 rated orders, so the score is less certain.',
  total_spend: 'Value of delivered + in-transit orders. Cancellations are excluded.',
  Delivery: 'Scored from average days between order and delivery. Faster = higher.',
  Quality: 'Average of this supplier’s quality ratings (1–5).',
  Price: 'Average order value, scaled against category peers. Cheaper = higher.',
  Communication: 'Average of this supplier’s communication ratings (1–5).',
  Reliability: 'Penalises cancellations exponentially. 0% cancelled = 5.0.',
  gauge: 'Share of suppliers at or above the 3.0 review line.',
};
const tip = (key) => TIPS[key] ? ` data-tip="${TIPS[key]}"` : '';
const qmark = (key) => TIPS[key] ? `<span class="q"${tip(key)} tabindex="0" aria-label="More info">?</span>` : '';

function badge(text, color, tipKey) {
  return `<span class="badge has-tip" style="color:${color};background:${color}1f"${tip(tipKey)}><span class="d"></span>${esc(text)}</span>`;
}
const riskBadge = (level, prefix = '') => badge((prefix ? prefix + ' ' : '') + level, RISK_COLOR[level] || C.muted, 'risk');

/* ---------- tooltip ---------- */
function showTip(t) {
  const el = $('#tip'); el.innerHTML = t.getAttribute('data-tip'); el.classList.add('show');
  const r = t.getBoundingClientRect(), tw = el.offsetWidth, th = el.offsetHeight;
  let x = r.left + r.width / 2 - tw / 2, y = r.top - th - 9;
  if (y < 8) y = r.bottom + 9;
  x = Math.max(8, Math.min(x, innerWidth - tw - 8));
  el.style.left = x + 'px'; el.style.top = y + 'px';
}
const hideTip = () => $('#tip').classList.remove('show');
function bindTips() {
  document.addEventListener('mouseover', (e) => { const t = e.target.closest('[data-tip]'); if (t) showTip(t); });
  document.addEventListener('mouseout', (e) => { if (e.target.closest('[data-tip]')) hideTip(); });
  document.addEventListener('focusin', (e) => { const t = e.target.closest('[data-tip]'); if (t) showTip(t); });
  document.addEventListener('focusout', hideTip);
  addEventListener('scroll', hideTip, true);
}

/* ---------- toast ---------- */
let toastTimer;
function toast(msg) {
  const box = $('#toasts');
  box.innerHTML = `<div class="toast"><span class="t-dot"></span>${esc(msg)}</div>`;
  const el = box.firstElementChild;
  requestAnimationFrame(() => el.classList.add('show'));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { el.classList.remove('show'); setTimeout(() => { if (box.firstElementChild === el) box.innerHTML = ''; }, 300); }, 2600);
}

/* ---------- scroll reveal + count-up ---------- */
const observer = new IntersectionObserver((entries) => {
  entries.forEach((en) => {
    if (!en.isIntersecting) return;
    en.target.classList.add('in');
    $$('[data-count]', en.target).forEach(countUp);
    observer.unobserve(en.target);
  });
}, { threshold: 0.12 });
function observeReveals(scope = document) {
  $$('[data-reveal]:not(.in)', scope).forEach((el, i) => { el.style.transitionDelay = (Math.min(i, 6) * 55) + 'ms'; observer.observe(el); });
}
function countUp(el) {
  if (el.dataset.done) return; el.dataset.done = '1';
  const target = +el.dataset.count, d = +(el.dataset.dec || 0);
  if (reduce || isNaN(target)) { el.textContent = fmtNum(target, d); return; }
  const dur = 850, t0 = performance.now();
  const tick = (now) => { const p = Math.min((now - t0) / dur, 1), e = 1 - Math.pow(1 - p, 3);
    el.textContent = fmtNum(target * e, d); if (p < 1) requestAnimationFrame(tick); else el.textContent = fmtNum(target, d); };
  requestAnimationFrame(tick);
}

/* ---------- chart base (no gradients) ---------- */
const baseChart = (type, height) => ({
  chart: { type, height, fontFamily: FONT, toolbar: { show: false }, parentHeightOffset: 0,
    animations: { enabled: !reduce, easing: 'easeout', speed: 500 } },
  grid: { borderColor: C.grid, strokeDashArray: 4, padding: { left: 6, right: 6 } },
  tooltip: { theme: 'light', style: { fontFamily: FONT } },
  dataLabels: { enabled: false },
});

/* ---------- KPI cards ---------- */
function kpiCard(item) {
  const isNum = item.value != null && item.value !== '' && !isNaN(+String(item.value).replace(/,/g, ''));
  const dec = isNum && String(item.value).includes('.') ? String(item.value).split('.')[1].length : 0;
  const valAttr = isNum ? ` data-count="${+String(item.value).replace(/,/g, '')}" data-dec="${dec}"` : '';
  const valTxt = isNum ? fmtNum(0, dec) : esc(item.value);
  const dcls = item.dir === 'up' ? ' up' : item.dir === 'down' ? ' down' : '';
  const delta = item.delta ? `<div class="k-delta${dcls}">${item.pill ? `<span class="pill">${esc(item.pill)}</span>` : ''}${esc(item.delta)}</div>` : '';
  return `<div class="card kpi" data-reveal>
    <div class="k-label${TIPS[item.label] ? ' has-tip' : ''}"${tip(item.label)}>${esc(item.label)} ${qmark(item.label)}</div>
    <div class="k-value tnum"${valAttr}>${valTxt}</div>${delta}${item.spark ? '<div class="k-spark"></div>' : ''}</div>`;
}
function renderKpis(targetId, items) {
  $(targetId).innerHTML = items.map(kpiCard).join('');
  const cards = $$(`${targetId} .kpi`);
  items.forEach((it, i) => {
    if (!it.spark) return;
    const host = $('.k-spark', cards[i]);
    const opts = { ...baseChart('line', 40), series: [{ data: it.spark }], stroke: { curve: 'smooth', width: 2 },
      colors: [C.accent], fill: { type: 'solid', opacity: 0 }, chart: { sparkline: { enabled: true }, fontFamily: FONT, animations: { enabled: !reduce } },
      tooltip: { enabled: false } };
    new ApexCharts(host, opts).render();
  });
  observeReveals($(targetId));
}

/* ---------- chart builders (flat) ---------- */
function gaugeOptions(pctAbove) {
  return { ...baseChart('radialBar', 260), series: [Math.round(pctAbove)], colors: [C.accent],
    plotOptions: { radialBar: { hollow: { size: '62%' }, track: { background: 'rgba(23,28,38,0.07)', strokeWidth: '100%' },
      dataLabels: { name: { show: true, offsetY: 22, color: C.muted, fontSize: '13px', fontWeight: 600 },
        value: { show: true, offsetY: -14, color: C.ink, fontSize: '40px', fontFamily: 'Space Grotesk', fontWeight: 700, formatter: (v) => v + '%' } } } },
    fill: { type: 'solid', colors: [C.accent] }, stroke: { lineCap: 'round' }, labels: ['above the line'] };
}
function donutOptions(counts) {
  const order = ['High', 'Medium', 'Low'];
  return { ...baseChart('donut', 300), series: order.map((k) => counts[k] || 0), labels: order, colors: order.map((k) => RISK_COLOR[k]),
    legend: { position: 'bottom', fontSize: '13px', labels: { colors: C.ink2 }, markers: { radius: 4 } },
    stroke: { width: 2, colors: ['#ffffff'] },
    plotOptions: { pie: { donut: { size: '66%', labels: { show: true,
      total: { show: true, label: 'Suppliers', color: C.muted, fontSize: '13px', fontWeight: 600, formatter: () => order.reduce((s, k) => s + (counts[k] || 0), 0) },
      value: { color: C.ink, fontSize: '30px', fontFamily: 'Space Grotesk', fontWeight: 700 } } } } },
    tooltip: { y: { formatter: (v) => v + ' suppliers' } } };
}
function distOptions(dist, threshold) {
  const cats = dist.edges.slice(0, -1).map((e) => e.toFixed(2));
  const colors = dist.counts.map((_, i) => ((dist.edges[i] + dist.edges[i + 1]) / 2 < threshold ? C.high : C.accent));
  return { ...baseChart('bar', 300), series: [{ name: 'Suppliers', data: dist.counts }],
    xaxis: { categories: cats, tickAmount: 8, labels: { style: { colors: C.muted, fontSize: '11px' } }, axisBorder: { color: C.grid }, axisTicks: { color: C.grid },
      title: { text: 'Overall score', style: { color: C.muted, fontWeight: 500 } } },
    yaxis: { labels: { style: { colors: C.muted } } },
    plotOptions: { bar: { columnWidth: '78%', borderRadius: 3, distributed: true } }, colors, legend: { show: false },
    annotations: { xaxis: [{ x: threshold.toFixed(2), strokeDashArray: 5, borderColor: C.ink,
      label: { text: `review line ${threshold.toFixed(1)}`, style: { background: C.ink, color: '#fff', fontFamily: FONT, fontSize: '11px' } } }] },
    tooltip: { x: { formatter: (v) => 'score ' + v }, y: { formatter: (v) => v + ' suppliers' } } };
}
function countryOptions(rows) {
  return { ...baseChart('bar', 340), series: [{ name: 'Suppliers', data: rows.map((r) => r.count) }],
    xaxis: { categories: rows.map((r) => r.country), labels: { style: { colors: C.muted } } },
    yaxis: { labels: { style: { colors: C.ink2, fontSize: '12px' } } },
    plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '66%' } }, colors: [C.accent],
    dataLabels: { enabled: true, style: { colors: [C.ink2], fontSize: '11px' }, offsetX: 16 } };
}
function categoryOptions(rows, threshold) {
  const colorOf = (v) => v == null ? C.muted : v < 2.5 ? C.high : v < 3.5 ? C.med : C.low;
  return { ...baseChart('bar', 320),
    series: [{ name: 'Avg. score', data: rows.map((r) => ({ x: r.category, y: r.avg, fillColor: colorOf(r.avg) })) }],
    xaxis: { max: 5, tickAmount: 5, labels: { style: { colors: C.muted } } },
    yaxis: { labels: { style: { colors: C.ink2, fontSize: '12px' } } },
    plotOptions: { bar: { horizontal: true, borderRadius: 4, barHeight: '62%' } },
    dataLabels: { enabled: true, offsetX: 22, style: { colors: [C.ink2], fontSize: '11px' }, formatter: (v) => v == null ? '—' : v.toFixed(2) },
    annotations: { xaxis: [{ x: threshold, strokeDashArray: 5, borderColor: C.ink,
      label: { text: `review ${threshold.toFixed(1)}`, style: { background: C.ink, color: '#fff', fontSize: '11px' } } }] },
    tooltip: { y: { formatter: (v) => v == null ? '—' : v.toFixed(2) + ' / 5' } } };
}
function heatOptions(cells) {
  const cats = [...new Set(cells.map((c) => c.category))], crits = [...new Set(cells.map((c) => c.criterion))];
  const series = cats.map((cat) => ({ name: cat, data: crits.map((cr) => {
    const cell = cells.find((c) => c.category === cat && c.criterion === cr);
    return { x: cr, y: cell && cell.score != null ? Math.round(cell.score * 100) / 100 : 0 };
  }) }));
  return { ...baseChart('heatmap', 300), series, colors: [C.accent],
    dataLabels: { enabled: true, style: { colors: ['#fff'], fontSize: '11px' }, formatter: (v) => v.toFixed(1) },
    xaxis: { labels: { style: { colors: C.muted } } }, yaxis: { labels: { style: { colors: C.ink2, fontSize: '12px' } } },
    plotOptions: { heatmap: { radius: 4, enableShades: false, colorScale: { ranges: [
      { from: 0, to: 2.5, color: C.high, name: 'weak' }, { from: 2.5, to: 3.5, color: C.med, name: 'fair' }, { from: 3.5, to: 5, color: C.low, name: 'strong' } ] } } },
    tooltip: { y: { formatter: (v) => v.toFixed(2) + ' / 5' } }, legend: { position: 'bottom', labels: { colors: C.ink2 } } };
}
function trendOptions(trend, threshold) {
  return { ...baseChart('line', 260), series: [{ name: 'Avg. overall', data: trend.map((t) => ({ x: t.quarter, y: t.overall })) }],
    stroke: { curve: 'smooth', width: 3 }, colors: [C.accent], markers: { size: 4, colors: [C.accent], strokeColors: '#fff' },
    xaxis: { labels: { style: { colors: C.muted, fontSize: '11px' } } }, yaxis: { min: 1, max: 5, tickAmount: 4, labels: { style: { colors: C.muted } } },
    annotations: { yaxis: [{ y: threshold, strokeDashArray: 5, borderColor: C.high, label: { text: `review line ${threshold.toFixed(1)}`, style: { background: C.high, color: '#fff', fontSize: '11px' } } }] },
    fill: { type: 'solid', opacity: 0.06 }, tooltip: { y: { formatter: (v) => v.toFixed(2) + ' / 5' } } };
}
function chartCard(elId, title, sub, takeaway, tipKey) {
  const el = $('#' + elId);
  el.setAttribute('data-reveal', '');
  el.innerHTML = `<h3${tipKey ? ' class="has-tip"' + tip(tipKey) : ''}>${esc(title)} ${qmark(tipKey)}</h3><div class="sub">${esc(sub)}</div>
    <div class="chart-host"></div>${takeaway ? `<div class="takeaway">${takeaway}</div>` : ''}`;
  return el.querySelector('.chart-host');
}

/* ---------- overview ---------- */
function renderOverview() {
  const t = META.totals, th = META.threshold;
  const worst = SUPPLIERS.reduce((a, b) => (a.overall ?? 9) < (b.overall ?? 9) ? a : b);
  const above = t.suppliers - t.below_threshold, pctAbove = above / t.suppliers * 100;
  $('#hero-head').textContent = t.below_threshold ? `${t.below_threshold} of ${t.suppliers} suppliers need a review.` : `All ${t.suppliers} suppliers are above the line.`;
  $('#hero-gauge').setAttribute('data-tip', TIPS.gauge);
  charts['hero-gauge'] = new ApexCharts($('#hero-gauge'), gaugeOptions(pctAbove)); charts['hero-gauge'].render();
  $('#hero-gauge-cap').textContent = `${above} of ${t.suppliers} suppliers score at or above the ${th.toFixed(1)} review line.`;

  const overAvg = t.avg_score - th;
  renderKpis('#kpis', [
    { label: 'Suppliers', value: t.suppliers, delta: `across ${t.countries} countries, ${t.categories} categories` },
    { label: 'Average score', value: t.avg_score.toFixed(2), pill: `${overAvg >= 0 ? '+' : ''}${overAvg.toFixed(2)}`, dir: overAvg >= 0 ? 'up' : 'down', delta: `vs the ${th.toFixed(1)} review line`, spark: META.score_distribution.counts },
    { label: 'Below the line', value: t.below_threshold, pill: `${Math.round(t.below_threshold / t.suppliers * 100)}%`, dir: t.below_threshold ? 'down' : 'up', delta: 'of the book' },
    { label: 'High risk', value: t.high_risk, dir: t.high_risk ? 'down' : 'up', pill: t.high_risk ? 'watch' : 'clear', delta: `worst: ${worst.name} (${sc(worst.overall)})` },
  ]);
  let host = chartCard('ov-risk', 'Risk distribution', 'How the book splits across risk bands.',
    `<b>${META.risk_counts.High}</b> high · <b>${META.risk_counts.Medium}</b> medium · <b>${META.risk_counts.Low}</b> low risk.`);
  charts['ov-risk'] = new ApexCharts(host, donutOptions(META.risk_counts)); charts['ov-risk'].render();
  host = chartCard('ov-dist', 'Score distribution', 'Each bar is a score band; red bars fall below the review line.',
    `<b>${t.below_threshold}</b> suppliers sit left of the ${th.toFixed(1)} line and are the ones to triage first.`);
  charts['ov-dist'] = new ApexCharts(host, distOptions(META.score_distribution, th)); charts['ov-dist'].render();
  observeReveals($('#view-overview'));
}

/* ---------- analytics ---------- */
function renderAnalytics() {
  if (rendered.analytics) return; rendered.analytics = true;
  const t = META.totals, th = META.threshold;
  renderKpis('#an-kpis', [
    { label: 'Suppliers', value: t.suppliers }, { label: 'Average score', value: t.avg_score.toFixed(2) },
    { label: 'Below the line', value: t.below_threshold }, { label: 'High risk', value: t.high_risk },
    { label: 'In transit', value: t.in_transit, delta: 'orders on the way' },
  ]);
  let host = chartCard('an-risk', 'Risk distribution', 'Suppliers by risk band.');
  charts['an-risk'] = new ApexCharts(host, donutOptions(META.risk_counts)); charts['an-risk'].render();
  host = chartCard('an-dist', 'Score distribution', 'Red bars fall below the review line.', `<b>${t.below_threshold}</b> below · <b>${t.suppliers - t.below_threshold}</b> above.`);
  charts['an-dist'] = new ApexCharts(host, distOptions(META.score_distribution, th)); charts['an-dist'].render();
  host = chartCard('an-country', 'Suppliers by country', 'Top 12 by count.');
  charts['an-country'] = new ApexCharts(host, countryOptions(META.country_counts)); charts['an-country'].render();
  host = chartCard('an-category', 'Average score by category', 'Coloured by risk band; dashed line is the review threshold.');
  charts['an-category'] = new ApexCharts(host, categoryOptions([...META.category_avg].sort((a, b) => (b.avg || 0) - (a.avg || 0)), th)); charts['an-category'].render();
  host = chartCard('an-heat', 'Category × criterion', 'Each cell is a category’s average for one criterion. Green = strong, red = weak.');
  charts['an-heat'] = new ApexCharts(host, heatOptions(META.heatmap)); charts['an-heat'].render();
  observeReveals($('#view-analytics'));
}

/* ---------- scorecards board ---------- */
const COLS = [
  { key: 'name', label: 'Supplier' }, { key: 'country', label: 'Country' }, { key: 'category', label: 'Category' },
  { key: 'overall', label: 'Overall', num: true }, { key: 'risk', label: 'Risk' }, { key: 'low_confidence', label: 'Confidence' },
  { key: 'num_orders', label: 'Orders', num: true }, { key: 'total_spend', label: 'Total spend', num: true },
];
function filtered() {
  const q = filters.search.trim().toLowerCase();
  const rows = SUPPLIERS.filter((s) => {
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
    if (typeof x === 'string') return x.toLowerCase() < (y || '').toLowerCase() ? -mul : x.toLowerCase() > (y || '').toLowerCase() ? mul : 0;
    x = x == null ? -Infinity : x; y = y == null ? -Infinity : y; return (x - y) * mul;
  });
  return rows;
}
function renderBoard(animateRows = false) {
  const rows = filtered(), th = META.threshold;
  $('#board thead').innerHTML = '<tr>' + COLS.map((c) => {
    const arr = sortState.key === c.key ? (sortState.dir === 'asc' ? ' ↑' : ' ↓') : '';
    return `<th data-key="${c.key}" class="${c.num ? 'num' : ''} ${TIPS[c.key] ? 'has-tip' : ''}"${tip(c.key)}>${c.label}${arr}</th>`;
  }).join('') + '</tr>';

  if (!rows.length) {
    $('#board tbody').innerHTML = '';
    $('#board').style.display = 'none';
    let emp = $('#empty');
    if (!emp) { emp = document.createElement('div'); emp.id = 'empty'; emp.className = 'empty'; $('#board').after(emp); }
    emp.style.display = 'block';
    emp.innerHTML = `<h3>No suppliers match these filters</h3><p>Try widening or clearing the filters.</p><button class="btn ghost" id="clear-filters">Clear filters</button>`;
    $('#clear-filters').onclick = resetFilters;
  } else {
    $('#board').style.display = '';
    if ($('#empty')) $('#empty').style.display = 'none';
    $('#board tbody').innerHTML = rows.map((s) => `<tr data-id="${s.id}" tabindex="0" role="button" aria-label="Open ${esc(s.name)}">
      <td class="name">${esc(s.name)}</td><td>${esc(s.country)}</td><td>${esc(s.category)}</td>
      <td class="num ${s.overall != null && s.overall < th ? 'below' : ''}">${sc(s.overall)}</td>
      <td>${riskBadge(s.risk)}</td><td>${s.low_confidence ? '<span class="chip low">Low</span>' : 'OK'}</td>
      <td class="num">${s.num_orders}</td><td class="num">${eur(s.total_spend)}</td></tr>`).join('');
    if (animateRows && !reduce) $$('#board tbody tr').slice(0, 14).forEach((tr, i) => { tr.style.animationDelay = (i * 25) + 'ms'; tr.classList.add('row-in'); });
    $$('#board tbody tr').forEach((tr) => {
      tr.onclick = () => openDrawer(+tr.dataset.id);
      tr.onkeydown = (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); openDrawer(+tr.dataset.id); } };
    });
  }
  const nBelow = rows.filter((s) => s.overall != null && s.overall < th).length;
  const note = $('#count-note');
  note.textContent = `${rows.length} of ${SUPPLIERS.length} suppliers` + (nBelow ? ` · ${nBelow} below the ${th.toFixed(1)} line` : '') + ' · click a row for the full drilldown';
  $$('#board thead th').forEach((th2) => th2.onclick = () => {
    const k = th2.dataset.key;
    if (sortState.key === k) sortState.dir = sortState.dir === 'asc' ? 'desc' : 'asc';
    else { sortState.key = k; sortState.dir = ['name', 'country', 'category'].includes(k) ? 'asc' : 'desc'; }
    renderBoard();
  });
}
function flashNote() { const n = $('#count-note'); n.classList.add('flash'); setTimeout(() => n.classList.remove('flash'), 500); }
function onFilterChange(announce) {
  renderBoard(true); flashNote();
  if (announce) { const n = filtered().length; toast(n === 0 ? 'No suppliers match these filters' : `Showing ${n} of ${SUPPLIERS.length} suppliers`); }
}
function resetFilters() {
  Object.assign(filters, { search: '', country: '', category: '', risk: '', below: false, lowconf: false });
  $('#search').value = ''; $('#f-country').value = ''; $('#f-category').value = ''; $('#f-risk').value = '';
  $('#t-below').checked = false; $('#t-lowconf').checked = false;
  onFilterChange(false); toast('Filters cleared');
}

/* ---------- drilldown ---------- */
const tile = (label, value, sub) => `<div class="tile"><div class="t-label${TIPS[label] ? ' has-tip' : ''}"${tip(label)}>${esc(label)} ${qmark(label)}</div>
  <div class="t-value tnum">${esc(value)}</div>${sub ? `<div class="t-sub">${esc(sub)}</div>` : ''}</div>`;
function openDrawer(id) {
  const s = SUPPLIERS.find((x) => x.id === id); if (!s) return;
  lastFocus = document.activeElement;
  const th = META.threshold, cw = META.cancel_weight, base = 1 - cw;
  const w = Object.fromEntries(META.criteria.map((c) => [c.key, c.weight]));
  const comps = [
    { label: 'Delivery', value: s.avg_delivery_days == null ? '—' : `${s.avg_delivery_days.toFixed(1)} days`, score: s.delivery_time, w: (w.delivery_time || 0) * base },
    { label: 'Quality', value: sc(s.quality), score: s.quality, w: (w.quality || 0) * base },
    { label: 'Price', value: eur(s.avg_price_eur), score: s.price, w: (w.price || 0) * base },
    { label: 'Communication', value: sc(s.communication), score: s.communication, w: (w.communication || 0) * base },
    { label: 'Reliability', value: s.cancel_rate == null ? '—' : `${pct(s.cancel_rate)} cancelled`, score: s.reliability, w: cw },
  ];
  const violations = comps.filter((c) => c.score != null && c.score < th);
  const recos = [];
  if (s.overall != null && s.overall < th) recos.push('Overall score is below the line — consider a formal review or corrective-action plan.');
  const weakest = comps.filter((c) => c.score != null).sort((a, b) => a.score - b.score)[0];
  if (weakest && weakest.score < 3.5) recos.push(`Weakest area is ${weakest.label} (${sc(weakest.score)}). Raise this in the next review.`);
  if (s.cancel_rate != null && s.cancel_rate >= 0.25) recos.push(`High cancellation rate (${pct(s.cancel_rate)}) — investigate why orders are being cancelled.`);
  if (s.low_confidence) recos.push('Few rated orders — gather more feedback before major decisions.');
  if (!recos.length) recos.push('Performing well across the board. Maintain the relationship.');
  const special = s.has_special ? ' ' + badge(`Special circumstance${s.num_special > 1 ? ' ×' + s.num_special : ''}`, C.ink2) : '';
  const orders = s.orders.map((o) => `<tr><td>${esc(o.order)}</td><td>${esc(o.ordered || '—')}</td><td>${esc(o.delivered || '—')}</td>
    <td class="num">${o.days == null ? '—' : o.days + ' d'}</td><td class="num">${eur(o.amount)}</td><td>${esc(o.status)}</td>
    <td class="num">${sc(o.quality)}</td><td class="num">${sc(o.communication)}</td></tr>`).join('');

  $('#drawer').innerHTML = `<button class="btn ghost close" id="drawer-close">Close</button>
    <h2>${esc(s.name)}</h2>
    <div class="meta-line">${riskBadge(s.risk, 'Risk:')} ${s.low_confidence ? badge(`Low confidence (${s.num_ratings})`, C.med, 'low_confidence') : badge('Confidence OK', C.low, 'low_confidence')}${special}</div>
    <div class="meta-line">${esc(s.country)} · ${esc(s.category)} · ${esc(s.email || '—')}</div>
    <div class="tiles" style="margin-top:18px">${tile('Overall', sc(s.overall))}${tile('Orders', s.num_orders, `${s.num_delivered} delivered`)}${tile('Total spend', eur(s.total_spend))}${tile('Cancelled', s.num_cancelled, s.cancel_rate == null ? '' : `${pct(s.cancel_rate)} of resolved`)}</div>
    <h3 style="margin:24px 0 10px">Score components</h3>
    <div class="tiles">${comps.map((c) => tile(c.label, c.value, `${c.score == null ? '—' : 'score ' + sc(c.score) + '/5'} · ${Math.round(c.w * 100)}%`)).join('')}</div>
    <div class="grid-2" style="margin-top:24px">
      <div><h3>Threshold violations</h3>${violations.length ? violations.map((v) => `<div class="note bad"><b>${esc(v.label)}</b>: ${sc(v.score)} (below ${th.toFixed(1)})</div>`).join('') : `<div class="note ok">No component below the ${th.toFixed(1)} line.</div>`}</div>
      <div><h3>Recommendations</h3>${recos.map((r) => `<div class="reco">${esc(r)}</div>`).join('')}</div></div>
    <h3 style="margin:24px 0 6px">Performance trend</h3><div id="drawer-trend"></div>
    <h3 style="margin:24px 0 10px">Orders</h3>
    <div class="tbl-wrap card" style="padding:0"><table><thead><tr><th>Order</th><th>Ordered</th><th>Delivered</th><th class="num">Days</th><th class="num">Amount</th><th>Status</th><th class="num">Qual.</th><th class="num">Comm.</th></tr></thead>
      <tbody>${orders || '<tr><td colspan="8">No orders on record.</td></tr>'}</tbody></table></div>`;

  $('#drawer-close').onclick = closeDrawer;
  $('#overlay').classList.add('open');
  $('#drawer').classList.add('open'); $('#drawer').setAttribute('aria-hidden', 'false');
  $('#drawer').scrollTop = 0; $('#drawer-close').focus();
  if (charts['trend']) charts['trend'].destroy();
  const host = $('#drawer-trend');
  if (s.trend && s.trend.length >= 2) { charts['trend'] = new ApexCharts(host, trendOptions(s.trend, th)); setTimeout(() => charts['trend'].render(), 60); }
  else host.innerHTML = '<p class="sub">Not enough dated orders to plot a trend.</p>';
}
function closeDrawer() {
  $('#overlay').classList.remove('open');
  $('#drawer').classList.remove('open'); $('#drawer').setAttribute('aria-hidden', 'true');
  if (lastFocus) lastFocus.focus();
}

/* ---------- nav + boot ---------- */
function switchView(view) {
  $$('.view').forEach((v) => v.classList.toggle('active', v.id === `view-${view}`));
  $$('#nav button').forEach((b) => b.classList.toggle('active', b.dataset.view === view));
  if (view === 'analytics') renderAnalytics();
  scrollTo({ top: 0 });
}
function initFilters() {
  const uniq = (k) => [...new Set(SUPPLIERS.map((s) => s[k]).filter(Boolean))].sort();
  const fill = (sel, opts, all) => { $(sel).innerHTML = `<option value="">${all}</option>` + opts.map((o) => `<option>${esc(o)}</option>`).join(''); };
  fill('#f-country', uniq('country'), 'All countries');
  fill('#f-category', uniq('category'), 'All categories');
  fill('#f-risk', ['High', 'Medium', 'Low'], 'All risk levels');
  let searchT;
  $('#search').oninput = (e) => { filters.search = e.target.value; clearTimeout(searchT); searchT = setTimeout(() => onFilterChange(false), 120); };
  $('#f-country').onchange = (e) => { filters.country = e.target.value; onFilterChange(true); };
  $('#f-category').onchange = (e) => { filters.category = e.target.value; onFilterChange(true); };
  $('#f-risk').onchange = (e) => { filters.risk = e.target.value; onFilterChange(true); };
  $('#t-below').onchange = (e) => { filters.below = e.target.checked; onFilterChange(true); };
  $('#t-lowconf').onchange = (e) => { filters.lowconf = e.target.checked; onFilterChange(true); };
}
async function boot() {
  try {
    const res = await fetch('./data.json'); if (!res.ok) throw new Error('data.json ' + res.status);
    const data = await res.json(); META = data.meta; SUPPLIERS = data.suppliers;
  } catch (e) { $('#hero-head').textContent = 'Could not load data.'; console.error(e); return; }
  bindTips();
  renderOverview(); initFilters(); renderBoard();
  document.body.addEventListener('click', (e) => { const n = e.target.closest('[data-view]'); if (n) switchView(n.dataset.view); });
  $('#overlay').onclick = closeDrawer;
  addEventListener('keydown', (e) => { if (e.key === 'Escape') closeDrawer(); });
}
boot();
