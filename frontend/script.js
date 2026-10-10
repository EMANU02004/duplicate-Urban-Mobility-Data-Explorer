document.addEventListener("DOMContentLoaded", () => {
    const filterBtn = document.getElementById("filterBtn");
    const zoneSelector = document.getElementById("zoneSelector");

    async function fetchDashboardData(zoneId = "") {
        let metricUrl = "/api/trips/metrics";
        if (zoneId) metricUrl += `?zoneId=${zoneId}`;
        
        const metricRes = await fetch(metricUrl);
        const metrics = await metricRes.json();
        
        document.getElementById("metricTotal").innerText = metrics.total_trips.toLocaleString();
        document.getElementById("metricSpeed").innerText = `${metrics.avg_speed_mph} mph`;
        document.getElementById("metricTip").innerText = `${metrics.avg_tip_percentage}%`;
    }

    async function fetchAlgorithmicTopZones() {
        const res = await fetch("/api/insights/top-zones?k=5");
        const topZones = await res.json();
        
        const tbody = document.querySelector("#topZonesTable tbody");
        tbody.innerHTML = "";
        
        topZones.forEach(item => {
            const row = document.createElement("tr");
            row.innerHTML = `
                <td><strong>Zone #${item.zone_id}</strong></td>
                <td>${item.trips.toLocaleString()} records</td>
                <td>$${item.avg_fare.toFixed(2)}</td>
            `;
            tbody.appendChild(row);
        });
    }

    function addBarCell(row, value, maximum, suffix) {
        const cell = document.createElement("td");
        const bar = document.createElement("span");
        bar.className = "insight-bar";
        bar.style.width = `${maximum ? (value / maximum) * 100 : 0}%`;
        cell.appendChild(bar);
        cell.append(` ${value.toLocaleString()}${suffix}`);
        row.appendChild(cell);
    }

    async function fetchPeakHours() {
        const response = await fetch("/api/insights/peak-hours");
        const rows = await response.json();
        const maximum = Math.max(...rows.map(item => item.trips), 0);
        const tbody = document.querySelector("#peakHoursTable tbody");
        tbody.innerHTML = "";
        rows.forEach(item => {
            const row = document.createElement("tr");
            row.innerHTML = `<td>${item.weekday} at ${String(item.hour).padStart(2, "0")}:00</td>`;
            addBarCell(row, item.trips, maximum, "");
            row.insertAdjacentHTML("beforeend", `<td>${item.avg_speed_mph || 0} mph</td>`);
            tbody.appendChild(row);
        });
    }

    async function fetchTipsByPayment() {
        const response = await fetch("/api/insights/tips-by-payment");
        const rows = await response.json();
        const maximum = Math.max(...rows.map(item => item.avg_tip_percentage || 0), 0);
        const tbody = document.querySelector("#tipsByPaymentTable tbody");
        tbody.innerHTML = "";
        rows.forEach(item => {
            const row = document.createElement("tr");
            row.innerHTML = `<td>${item.payment_description}</td><td>${item.trips.toLocaleString()}</td>`;
            addBarCell(row, item.avg_tip_percentage || 0, maximum, "%");
            tbody.appendChild(row);
        });
    }

    async function fetchBoroughFlows() {
        const response = await fetch("/api/insights/borough-flows");
        const rows = await response.json();
        const maximum = Math.max(...rows.map(item => item.trips), 0);
        const tbody = document.querySelector("#boroughFlowsTable tbody");
        tbody.innerHTML = "";
        rows.forEach(item => {
            const row = document.createElement("tr");
            row.innerHTML = `<td>${item.pickup_borough} to ${item.dropoff_borough}</td>`;
            addBarCell(row, item.trips, maximum, "");
            row.insertAdjacentHTML("beforeend", `<td>${item.avg_speed_mph || 0} mph</td>`);
            tbody.appendChild(row);
        });
    }

    filterBtn.addEventListener("click", () => {
        fetchDashboardData(zoneSelector.value);
    });

    fetchDashboardData();
    fetchAlgorithmicTopZones();
    fetchPeakHours();
    fetchTipsByPayment();
    fetchBoroughFlows();
});
