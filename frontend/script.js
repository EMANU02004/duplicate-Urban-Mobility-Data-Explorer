const API_BASE =
  window.location.protocol === 'file:' || window.location.port !== '5050'
    ? 'http://127.0.0.1:5050'
    : '';

async function fetchJson(path) {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) {
    throw new Error(`API request failed (${response.status}): ${path}`);
  }
  return response.json();
}

async function loadDashboard() {
  const borough = document.getElementById('boroughFilter').value;
  const sort = document.getElementById('sortFilter').value;
  const minDist = document.getElementById('minDistance').value;
  const maxDist = document.getElementById('maxDistance').value;

  const params = new URLSearchParams({ sort, limit: 15 });
  if (borough !== 'all') params.set('borough', borough);
  if (minDist) params.set('min_distance', minDist);
  if (maxDist) params.set('max_distance', maxDist);

  try {
    const [overview, insights, tripsRes] = await Promise.all([
      fetchJson('/api/overview'),
      fetchJson('/api/insights'),
      fetchJson(`/api/trips?${params}`)
    ]);

    renderSummary(overview);
    renderTopZones(overview.top_zones || []);
    renderBoroughChart(insights.borough || []);
    renderHourlyChart(insights.hourly || []);
    renderTrips(tripsRes.trips || []);
  } catch (err) {
    console.error(err);
    const message = 'Could not load data. Start the Flask server with: python backend/app.py';
    document.getElementById('summary').innerHTML =
      `<div class="error-message">${message}</div>`;
    document.getElementById('topZones').innerHTML = `<p class="error-message">${message}</p>`;
    document.getElementById('boroughChart').innerHTML = `<p class="error-message">${message}</p>`;
    document.getElementById('hourlyChart').innerHTML = `<p class="error-message">${message}</p>`;
    document.getElementById('tripTableBody').innerHTML =
      `<tr><td colspan="5">${message}</td></tr>`;
  }
}

function renderSummary(data) {
  document.getElementById('summary').innerHTML = `
    <div class="stat-card"><h3>Total Trips</h3><p>${Number(data.total_trips).toLocaleString()}</p></div>
    <div class="stat-card"><h3>Avg Distance</h3><p>${Number(data.avg_distance).toFixed(2)} mi</p></div>
    <div class="stat-card"><h3>Avg Fare</h3><p>$${Number(data.avg_fare).toFixed(2)}</p></div>
    <div class="stat-card"><h3>Peak Hour</h3><p>${data.peak_hour}:00</p></div>
  `;
}

function renderTopZones(zones) {
  const max = zones.length ? Math.max(...zones.map(z => z.value)) : 1;
  document.getElementById('topZones').innerHTML = zones.map(z => `
    <div class="bar-row">
      <span class="bar-label">${z.name}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(z.value / max) * 100}%"></span></span>
      <span class="bar-count">${z.value}</span>
    </div>
  `).join('');
}

function renderBoroughChart(items) {
  const max = items.length ? Math.max(...items.map(i => Number(i.trip_count))) : 1;
  document.getElementById('boroughChart').innerHTML = items.map(item => `
    <div class="bar-row">
      <span class="bar-label">${item.borough}</span>
      <span class="bar-track"><span class="bar-fill" style="width:${(Number(item.trip_count) / max) * 100}%"></span></span>
      <span class="bar-count">${item.trip_count}</span>
    </div>
  `).join('');
}

function renderHourlyChart(items) {
  const max = items.length ? Math.max(...items.map(i => Number(i.trip_count))) : 1;
  document.getElementById('hourlyChart').innerHTML = items.map(item => `
    <div class="hour-col">
      <span class="bar" style="height:${(Number(item.trip_count) / max) * 100}%"></span>
      <span class="lbl">${item.hour}</span>
    </div>
  `).join('');
}

function renderTrips(trips) {
  document.getElementById('tripTableBody').innerHTML = trips.map(t => `
    <tr>
      <td>${t.pickup_borough} / ${t.pickup_zone}</td>
      <td>${t.dropoff_zone}</td>
      <td>${Number(t.trip_distance).toFixed(2)} mi</td>
      <td>$${Number(t.total_amount).toFixed(2)}</td>
      <td>${Number(t.trip_duration_minutes).toFixed(0)} min</td>
    </tr>
  `).join('');
}

document.getElementById('applyFilters').addEventListener('click', loadDashboard);

loadDashboard();
