/* Urban Mobility Data Explorer — dashboard logic.
 * One filter bar drives every panel. Each panel: fetch -> render -> one-line insight
 * computed from the numbers actually returned by the API.
 */
const API_BASE = window.location.protocol === 'file:' ? 'http://127.0.0.1:5050' : '';
const DAYS = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'];
const METRIC = {
  avg_speed: { label: 'Avg speed', unit: 'mph', color: '#d94f2b', invert: true, fmt: v => `${v.toFixed(1)} mph` },
  fare_per_mile: { label: 'Fare per mile', unit: '$/mi', color: '#7048a8', invert: false, fmt: v => `$${v.toFixed(2)}/mi` },
  trips: { label: 'Trips', unit: 'trips', color: '#2b6cb0', invert: false, fmt: v => Math.round(v).toLocaleString() },
};
const MIN_TRIPS = 30; // ignore near-empty cells/zones when naming extremes

const state = {
  filters: new URLSearchParams(),
  map: 'avg_speed', heatmap: 'avg_speed', distribution: 'avg_speed_mph', rankings: 'zones:slowest',
  sort: 'pickup_datetime', order: 'desc', page: 1,
  selectedZone: null, overview: null,
};

// ------------------------------------------------------------------ helpers
const $ = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
const num = (v, d = 1) => (v == null ? '—' : Number(v).toFixed(d));
const hh = h => `${String(h).padStart(2, '0')}:00`;

async function api(path, extra = {}) {
  const params = new URLSearchParams(state.filters);
  Object.entries(extra).forEach(([k, v]) => params.set(k, v));
  const res = await fetch(`${API_BASE}${path}?${params}`);
  const body = await res.json().catch(() => ({}));
  if (!res.ok) throw new Error(body.error || `Request failed (${res.status})`);
  return body;
}

function showError(el, err) {
  el.innerHTML = `<div class="error">${esc(err.message)}</div>`;
}

function mix(hex, t) {
  // Blend from a warm off-white (t=0) to the metric colour (t=1).
  const a = [244, 239, 230];
  const b = [1, 3, 5].map(i => parseInt(hex.slice(i, i + 2), 16));
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * t));
  return `rgb(${c.join(',')})`;
}

function colorFor(metric, value, lo, hi) {
  if (value == null) return '#e9e9ec';
  let t = hi > lo ? (value - lo) / (hi - lo) : 0.5;
  t = Math.max(0, Math.min(1, t));
  if (METRIC[metric].invert) t = 1 - t;
  return mix(METRIC[metric].color, 0.12 + 0.88 * t);
}

function robustRange(values) {
  // 5th–95th percentile so one extreme zone doesn't wash out the colour scale.
  const v = values.filter(x => x != null).sort((a, b) => a - b);
  if (!v.length) return [0, 1];
  return [v[Math.floor(v.length * 0.05)], v[Math.min(v.length - 1, Math.floor(v.length * 0.95))]];
}

// ------------------------------------------------------------------ meta + filters
async function loadMeta() {
  const meta = await api('/api/meta');
  const run = meta.run;
  if (run) {
    $('provenance').textContent =
      `${run.source_file} · ${run.raw_rows.toLocaleString()} raw trips → ` +
      `${run.excluded_rows.toLocaleString()} excluded → ${run.loaded_rows.toLocaleString()} analysed`;
  }
  const f = $('filters');
  if (meta.date_range.first) {
    for (const name of ['start_date', 'end_date']) {
      f[name].min = meta.date_range.first;
      f[name].max = meta.date_range.last;
    }
  }
  f.borough.insertAdjacentHTML('beforeend', meta.boroughs.map(b => `<option>${esc(b)}</option>`).join(''));
  f.zone.insertAdjacentHTML('beforeend', meta.zones
    .filter(z => z.borough !== 'Unknown' && z.borough !== 'N/A')
    .map(z => `<option value="${z.location_id}">${esc(z.zone_name)} (${esc(z.borough)})</option>`).join(''));
  f.payment.insertAdjacentHTML('beforeend', meta.payment_types
    .map(p => `<option value="${p.id}">${esc(p.description)}</option>`).join(''));
}

function readFilters() {
  const data = new FormData($('filters'));
  const params = new URLSearchParams();
  for (const [k, v] of data.entries()) if (v !== '') params.set(k, v);
  state.filters = params;
  state.page = 1;
}

// ------------------------------------------------------------------ KPIs
async function loadOverview() {
  const el = $('kpis');
  try {
    const o = await api('/api/overview');
    state.overview = o;
    const t = o.totals;
    if (!t.trips) {
      el.innerHTML = '<div class="empty">No trips match these filters.</div>';
      $('kpi-insight').textContent = '';
      return;
    }
    el.innerHTML = `
      <div class="kpi"><h3>Trips analysed</h3><p>${t.trips.toLocaleString()}</p><small>after cleaning</small></div>
      <div class="kpi"><h3>Average speed</h3><p>${num(t.avg_speed)} <small>mph</small></p><small>distance ÷ duration</small></div>
      <div class="kpi"><h3>Fare per mile</h3><p>$${num(t.fare_per_mile, 2)}</p><small>metered fare ÷ miles</small></div>
      <div class="kpi"><h3>Avg trip</h3><p>${num(t.avg_duration, 0)} <small>min</small></p><small>${num(t.avg_distance)} mi · $${num(t.avg_total, 2)} total</small></div>`;
    const s = o.slowest_hour, f = o.fastest_hour;
    $('kpi-insight').textContent = s && f && s.hour !== f.hour
      ? `Taxis are slowest at ${hh(s.hour)} (${num(s.avg_speed)} mph) — ${Math.round((1 - s.avg_speed / f.avg_speed) * 100)}% ` +
        `slower than at ${hh(f.hour)} (${num(f.avg_speed)} mph). At the slow hour riders pay $${num(s.fare_per_mile, 2)} per mile ` +
        `versus $${num(f.fare_per_mile, 2)} at the fast hour.`
      : '';
  } catch (err) { showError(el, err); }
}

// ------------------------------------------------------------------ map
let leafletMap, zoneLayer, geojson;

async function initMap() {
  leafletMap = L.map('map', { scrollWheelZoom: false }).setView([40.73, -73.94], 10);
  L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
    attribution: '&copy; OpenStreetMap contributors &copy; CARTO', maxZoom: 16,
  }).addTo(leafletMap);
  geojson = await api('/api/zones/geojson');
}

async function loadMap() {
  const metric = state.map;
  try {
    const data = await api('/api/map', { metric });
    const byZone = Object.fromEntries(data.zones.map(z => [z.location_id, z]));
    const usable = data.zones.filter(z => z.trips >= MIN_TRIPS || metric === 'trips');
    const [lo, hi] = robustRange(usable.map(z => z.value));
    if (zoneLayer) zoneLayer.remove();
    zoneLayer = L.geoJSON(geojson, {
      style: feat => {
        const z = byZone[feat.properties.location_id];
        const value = z && (z.trips >= MIN_TRIPS || metric === 'trips') ? z.value : null;
        const selected = feat.properties.location_id === state.selectedZone;
        return { fillColor: colorFor(metric, value, lo, hi), fillOpacity: value == null ? 0.25 : 0.85,
                 color: selected ? '#1d1f24' : '#ffffff', weight: selected ? 2.5 : 0.6 };
      },
      onEachFeature: (feat, layer) => {
        const p = feat.properties, z = byZone[p.location_id];
        layer.bindTooltip(`<b>${esc(p.zone)}</b><br>${esc(p.borough)}<br>` +
          (z ? `${METRIC[metric].fmt(z.value)} · ${z.trips.toLocaleString()} trips` : 'no pickups'), { sticky: true });
        layer.on('click', () => selectZone(p.location_id));
      },
    }).addTo(leafletMap);
    if (geojson.features.length && !leafletMap._fitted) {
      leafletMap.fitBounds(zoneLayer.getBounds(), { padding: [10, 10] });
      leafletMap._fitted = true;
    }
    const lowLabel = METRIC[metric].invert ? 'fast' : 'low', highLabel = METRIC[metric].invert ? 'slow' : 'high';
    $('map-legend').innerHTML =
      `<span>${highLabel === 'slow' ? METRIC[metric].fmt(hi) : METRIC[metric].fmt(lo)} (${lowLabel})</span>` +
      `<span class="ramp" style="background:linear-gradient(90deg, ${mix(METRIC[metric].color, .12)}, ${METRIC[metric].color})"></span>` +
      `<span>${highLabel === 'slow' ? METRIC[metric].fmt(lo) : METRIC[metric].fmt(hi)} (${highLabel})</span>` +
      `<span>· grey = fewer than ${MIN_TRIPS} pickups</span>`;
    mapInsight(metric, usable);
  } catch (err) { showError($('map-legend'), err); }
}

function mapInsight(metric, zones) {
  const names = Object.fromEntries(geojson.features.map(f => [f.properties.location_id, f.properties]));
  const ranked = zones.filter(z => names[z.location_id] && z.trips >= MIN_TRIPS);
  const avg = state.overview?.totals;
  if (!ranked.length || !avg) { $('map-insight').textContent = ''; return; }
  const pick = metric === 'avg_speed'
    ? ranked.reduce((a, b) => (b.value < a.value ? b : a))
    : ranked.reduce((a, b) => (b.value > a.value ? b : a));
  const z = names[pick.location_id];
  const base = metric === 'trips' ? null : avg[metric];
  $('map-insight').textContent = metric === 'avg_speed'
    ? `Slowest pickup zone: ${z.zone} (${z.borough}) at ${num(pick.value)} mph — ${Math.round((1 - pick.value / base) * 100)}% below the average of ${num(base)} mph.`
    : metric === 'fare_per_mile'
      ? `Most expensive per mile: ${z.zone} (${z.borough}) at $${num(pick.value, 2)}/mi, against an average of $${num(base, 2)}/mi.`
      : `Busiest pickup zone: ${z.zone} (${z.borough}) with ${pick.value.toLocaleString()} trips (${Math.round(pick.value / avg.trips * 100)}% of all trips).`;
}

async function selectZone(id) {
  state.selectedZone = id;
  const panel = $('zone-panel');
  panel.classList.add('loading');
  try {
    const d = await api(`/api/zones/${id}`);
    const t = d.totals, hours = d.hourly;
    const maxTrips = Math.max(1, ...hours.map(h => h.trips));
    const slow = hours.filter(h => h.trips >= 5).reduce((a, b) => (!a || b.avg_speed < a.avg_speed ? b : a), null);
    panel.innerHTML = `
      <h3>${esc(d.zone.zone_name)}</h3>
      <p class="sub">${esc(d.zone.borough)} · ${esc(d.zone.service_zone)} · zone ${d.zone.location_id}</p>
      <dl>
        <dt>Pickups</dt><dd>${(t.trips || 0).toLocaleString()}</dd>
        <dt>Avg speed</dt><dd>${num(t.avg_speed)} mph</dd>
        <dt>Fare per mile</dt><dd>$${num(t.fare_per_mile, 2)}</dd>
        <dt>Avg duration</dt><dd>${num(t.avg_duration, 0)} min</dd>
        <dt>Slowest hour</dt><dd>${slow ? `${hh(slow.hour)} · ${num(slow.avg_speed)} mph` : '—'}</dd>
      </dl>
      <strong>Pickups by hour</strong>
      <div class="spark">${Array.from({ length: 24 }, (_, h) => {
        const row = hours.find(x => x.hour === h);
        return `<span title="${hh(h)}: ${row ? row.trips : 0} trips, ${row ? num(row.avg_speed) : '—'} mph" style="height:${row ? (row.trips / maxTrips) * 100 : 0}%"></span>`;
      }).join('')}</div>
      <div class="spark-axis"><span>00</span><span>06</span><span>12</span><span>18</span><span>23</span></div>
      <p style="margin:12px 0 0"><strong>Top destinations</strong></p>
      <ol>${d.top_destinations.map(r => `<li>${esc(r.zone)} — ${r.trips.toLocaleString()} trips, ${num(r.avg_speed)} mph</li>`).join('') || '<li class="muted">none</li>'}</ol>`;
    if (zoneLayer) zoneLayer.resetStyle();
  } catch (err) { showError(panel, err); }
  panel.classList.remove('loading');
}

// ------------------------------------------------------------------ heatmap
async function loadHeatmap() {
  const metric = state.heatmap, el = $('heatmap');
  el.classList.add('loading');
  try {
    const { cells } = await api('/api/heatmap', { metric });
    const lookup = {};
    cells.forEach(c => { lookup[`${c.dow}-${c.hour}`] = c; });
    const usable = cells.filter(c => c.trips >= MIN_TRIPS || metric === 'trips');
    const [lo, hi] = robustRange(usable.map(c => c.value));
    let html = '<span></span>' + Array.from({ length: 24 }, (_, h) => `<span class="collab">${h % 3 === 0 ? h : ''}</span>`).join('');
    DAYS.forEach((day, d) => {
      html += `<span class="rowlab">${day}</span>`;
      for (let h = 0; h < 24; h++) {
        const c = lookup[`${d}-${h}`];
        const ok = c && (c.trips >= MIN_TRIPS || metric === 'trips');
        html += `<span class="cell" style="background:${colorFor(metric, ok ? c.value : null, lo, hi)}"
          title="${day} ${hh(h)} — ${c ? `${METRIC[metric].fmt(c.value)}, ${c.trips.toLocaleString()} trips` : 'no trips'}"></span>`;
      }
    });
    el.innerHTML = html;
    if (usable.length) {
      const by = (cmp) => usable.reduce((a, b) => (cmp(b.value, a.value) ? b : a));
      const low = by((x, y) => x < y), high = by((x, y) => x > y);
      const label = c => `${DAYS[c.dow]} ${hh(c.hour)}`;
      $('heat-insight').textContent = metric === 'avg_speed'
        ? `The city is slowest on ${label(low)} (${num(low.value)} mph) and fastest on ${label(high)} (${num(high.value)} mph) — a ${num(high.value / low.value, 1)}× difference for the same taxi network.`
        : metric === 'fare_per_mile'
          ? `Each mile costs most on ${label(high)} ($${num(high.value, 2)}) and least on ${label(low)} ($${num(low.value, 2)}): time stuck in traffic is billed too.`
          : `Demand peaks on ${label(high)} (${high.value.toLocaleString()} trips) and bottoms out on ${label(low)} (${low.value.toLocaleString()}).`;
    } else $('heat-insight').textContent = '';
  } catch (err) { showError(el, err); }
  el.classList.remove('loading');
}

// ------------------------------------------------------------------ distribution
async function loadDistribution() {
  const metric = state.distribution, el = $('histogram');
  el.classList.add('loading');
  try {
    const d = await api('/api/distribution', { metric, bins: 24 });
    const max = Math.max(1, ...d.bins.map(b => b.trips));
    const total = d.bins.reduce((s, b) => s + b.trips, 0);
    const unit = { avg_speed_mph: 'mph', fare_per_mile: '$/mi', trip_distance: 'mi', trip_duration_min: 'min' }[metric];
    el.innerHTML = d.bins.map((b, i) => `<span class="bar" style="height:${(b.trips / max) * 100}%"
      title="${b.from}–${b.to}${i === d.bins.length - 1 ? '+' : ''} ${unit}: ${b.trips.toLocaleString()} trips"></span>`).join('');
    let axis = el.nextElementSibling;
    if (!axis || !axis.classList.contains('hist-axis')) {
      axis = document.createElement('div'); axis.className = 'hist-axis'; el.after(axis);
    }
    axis.innerHTML = `<span>${d.range[0]} ${unit}</span><span>${(d.range[0] + d.range[1]) / 2}</span><span>${d.range[1]}+ ${unit}</span>`;
    const share = (pred) => total ? Math.round(d.bins.filter(pred).reduce((s, b) => s + b.trips, 0) / total * 100) : 0;
    $('dist-insight').textContent = !total ? '' : metric === 'avg_speed_mph'
      ? `${share(b => b.to <= 10)}% of trips average 10 mph or less — slower than a typical cyclist.`
      : metric === 'fare_per_mile'
        ? `${share(b => b.from >= 10)}% of trips cost $10 or more per mile — mostly very short or slow trips where waiting time dominates.`
        : `${share(b => b.to <= 2.5)}% of trips are 2.5 miles or shorter.`;
  } catch (err) { showError(el, err); }
  el.classList.remove('loading');
}

// ------------------------------------------------------------------ rankings
async function loadRankings() {
  const [type, by] = state.rankings.split(':'), el = $('rankings');
  el.classList.add('loading');
  try {
    const r = await api('/api/rankings', { type, by, k: 10 });
    el.innerHTML = r.items.map(it => {
      const name = type === 'routes' ? `${esc(it.pickup_zone)} → ${esc(it.dropoff_zone)}` : esc(it.pickup_zone);
      const val = by === 'trips' ? `${it.trips.toLocaleString()} trips`
        : by === 'fare_per_mile' ? `$${num(it.fare_per_mile, 2)}/mi` : `${num(it.avg_speed)} mph`;
      const meta = by === 'trips' ? `${num(it.avg_speed)} mph · $${num(it.fare_per_mile, 2)}/mi` : `${it.trips.toLocaleString()} trips`;
      return `<li><span>${name}<span class="meta">${meta}</span></span><span class="val">${val}</span></li>`;
    }).join('') || '<li class="empty">No groups match.</li>';
    $('rank-note').textContent = `Heap selected the top ${r.items.length} from ${r.groups_scanned.toLocaleString()} ${type}` +
      (r.min_trips > 1 ? ` with at least ${r.min_trips} trips.` : '.');
  } catch (err) { showError(el, err); }
  el.classList.remove('loading');
}

// ------------------------------------------------------------------ trips
async function loadTrips() {
  const body = $('trip-rows');
  body.classList.add('loading');
  try {
    const r = await api('/api/trips', { sort: state.sort, order: state.order, page: state.page, page_size: 15 });
    body.innerHTML = r.trips.map(t => `
      <tr data-id="${t.trip_id}" tabindex="0">
        <td>${esc(t.pickup_datetime.slice(5, 16))}</td>
        <td>${esc(t.pickup_zone)} → ${esc(t.dropoff_zone)}</td>
        <td class="num">${num(t.trip_distance, 2)}</td>
        <td class="num">${num(t.trip_duration_min, 0)}</td>
        <td class="num">${num(t.avg_speed_mph)}</td>
        <td class="num">${num(t.fare_per_mile, 2)}</td>
        <td class="num">$${num(t.total_amount, 2)}</td>
      </tr>`).join('') || '<tr><td colspan="7" class="empty">No trips match these filters.</td></tr>';
    $('trip-count').textContent = `${r.total.toLocaleString()} matching trips · click a row for the full record`;
    $('page-info').textContent = `Page ${r.page} of ${r.pages.toLocaleString()}`;
    $('prev').disabled = r.page <= 1;
    $('next').disabled = r.page >= r.pages;
    document.querySelectorAll('th .sort').forEach(b => {
      b.classList.toggle('active', b.dataset.sort === state.sort);
      b.dataset.dir = state.order === 'desc' ? '↓' : '↑';
    });
  } catch (err) { body.innerHTML = `<tr><td colspan="7">${esc(err.message)}</td></tr>`; }
  body.classList.remove('loading');
}

async function showTrip(id) {
  const t = await (await fetch(`${API_BASE}/api/trips/${id}`)).json();
  const rows = [
    ['Pickup', `${t.pickup_datetime} · ${t.pickup_zone}, ${t.pickup_borough}`],
    ['Drop-off', `${t.dropoff_datetime} · ${t.dropoff_zone}, ${t.dropoff_borough}`],
    ['Distance', `${num(t.trip_distance, 2)} mi`], ['Duration', `${num(t.trip_duration_min)} min`],
    ['Avg speed', `${num(t.avg_speed_mph)} mph${t.is_speed_outlier ? ' (flagged outlier)' : ''}`],
    ['Fare per mile', `$${num(t.fare_per_mile, 2)}${t.is_fare_outlier ? ' (flagged outlier)' : ''}`],
    ['Fare', `$${num(t.fare_amount, 2)}`], ['Tip', `$${num(t.tip_amount, 2)}${t.tip_pct != null ? ` (${num(t.tip_pct)}%)` : ' (not recorded for cash)'}`],
    ['Tolls / surcharges', `$${num(t.tolls_amount, 2)} / congestion $${num(t.congestion_surcharge, 2)}, airport $${num(t.airport_fee, 2)}${t.cbd_congestion_fee != null ? `, CBD $${num(t.cbd_congestion_fee, 2)}` : ''}`],
    ['Total', `$${num(t.total_amount, 2)}`], ['Payment', t.payment], ['Rate code', t.rate_code], ['Vendor', t.vendor],
    ['Passengers', t.passenger_count ?? 'unknown'],
    ['Segments', [t.is_airport_trip && 'airport', t.is_cross_borough && 'cross-borough', t.pays_cbd_fee && 'paid CBD fee', t.is_weekend && 'weekend', t.time_band].filter(Boolean).join(' · ')],
    ['Source row', t.source_row],
  ];
  $('trip-detail').innerHTML = `<h3 style="margin-top:0">Trip #${t.trip_id}</h3><dl>${rows.map(([k, v]) => `<dt>${k}</dt><dd>${esc(v)}</dd>`).join('')}</dl>`;
  $('trip-dialog').showModal();
}

// ------------------------------------------------------------------ data quality
async function loadQuality() {
  try {
    const { run, log } = await api('/api/data-quality');
    if (!run) return;
    $('dq-summary').innerHTML =
      `<span>Raw rows <b>${run.raw_rows.toLocaleString()}</b></span>` +
      `<span>Excluded <b>${run.excluded_rows.toLocaleString()}</b> (${num(run.excluded_rows / run.raw_rows * 100)}%)</span>` +
      `<span>Loaded <b>${run.loaded_rows.toLocaleString()}</b></span>` +
      `<span class="muted">raw − excluded = loaded ✓</span>`;
    $('dq-rows').innerHTML = log.map(e => `
      <tr><td>${esc(e.stage)}</td><td>${esc(e.rule.replaceAll('_', ' '))}</td>
      <td><span class="tag ${esc(e.action)}">${esc(e.action.replace('_', ' '))}</span></td>
      <td class="num">${e.rows_affected.toLocaleString()}</td>
      <td>${esc([e.threshold, e.detail].filter(Boolean).join(' — '))}</td></tr>`).join('');
  } catch (err) { showError($('dq-summary'), err); }
}

// ------------------------------------------------------------------ wiring
function refreshAll() {
  loadOverview().then(loadMap);
  loadHeatmap(); loadDistribution(); loadRankings(); loadTrips();
  if (state.selectedZone) selectZone(state.selectedZone);
}

document.querySelectorAll('.seg').forEach(group => {
  group.addEventListener('click', e => {
    const btn = e.target.closest('button');
    if (!btn) return;
    group.querySelectorAll('button').forEach(b => b.classList.toggle('on', b === btn));
    state[group.dataset.target] = btn.dataset.metric;
    ({ map: loadMap, heatmap: loadHeatmap, distribution: loadDistribution, rankings: loadRankings })[group.dataset.target]();
  });
});

$('filters').addEventListener('submit', e => { e.preventDefault(); readFilters(); refreshAll(); });
$('filters').addEventListener('reset', () => setTimeout(() => { readFilters(); refreshAll(); }, 0));
document.querySelectorAll('th .sort').forEach(btn => btn.addEventListener('click', () => {
  if (state.sort === btn.dataset.sort) state.order = state.order === 'desc' ? 'asc' : 'desc';
  else { state.sort = btn.dataset.sort; state.order = 'desc'; }
  state.page = 1; loadTrips();
}));
$('prev').addEventListener('click', () => { state.page -= 1; loadTrips(); });
$('next').addEventListener('click', () => { state.page += 1; loadTrips(); });
$('trip-rows').addEventListener('click', e => { const tr = e.target.closest('tr[data-id]'); if (tr) showTrip(tr.dataset.id); });
$('trip-rows').addEventListener('keydown', e => { const tr = e.target.closest('tr[data-id]'); if (tr && e.key === 'Enter') showTrip(tr.dataset.id); });

(async function start() {
  try {
    await loadMeta();
    await initMap();
    refreshAll();
    loadQuality();
  } catch (err) {
    $('provenance').innerHTML = `<span class="error">${esc(err.message)} — run <code>python -m pipeline.run</code>, then <code>python app.py</code>.</span>`;
  }
})();
