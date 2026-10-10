document.addEventListener("DOMContentLoaded", () => {
    const filterBtn = document.getElementById("filterBtn");
    const zoneSelector = document.getElementById("zoneSelector");

    async function fetchDashboardData(zoneId = "") {
        // Fetch Key Performance Indicators
        let metricUrl = "/api/trips/metrics";
        if (zoneId) metricUrl += `?zoneId=${zoneId}`;
        
        const metricRes = await fetch(metricUrl);
        const metrics = await metricRes.json();
        
        document.getElementById("metricTotal").innerText = metrics.total_trips.toLocaleString();
        document.getElementById("metricSpeed").innerText = `${metrics.avg_speed_mph} mph`;
        document.getElementById("metricTip").innerText = `${metrics.avg_tip_percentage}%`;
    }

    async function fetchAlgorithmicTopZones() {
        // Fetch customized analytics compiled by our manual min-heap data structure
        const res = await fetch("/api/insights/top-zones?k=5");
        const topZones = await res.json();
        
        const tbody = document.querySelector("#topZonesTable tbody");
        tbody.innerHTML = ""; // Clear loader
        
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

    filterBtn.addEventListener("click", () => {
        fetchDashboardData(zoneSelector.value);
    });

    // Initial Bootstrap Core Invocations
    fetchDashboardData();
    fetchAlgorithmicTopZones();
});
