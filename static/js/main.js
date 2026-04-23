// Global Variables
let map;
let userMarker;
let routeLayer;
let hotspotLayer;
let policeLayer;
let riskChart;
let trendChart;

// Constants
const INDIA_CENTER = [20.5937, 78.9629]; // Geometric center of India
const DEFAULT_ZOOM = 5;
const RISK_THRESHOLD = 60; // Percent
const CHECK_INTERVAL = 5000; // 5 seconds

// Initialize Map
function initMap() {
    map = L.map('map').setView(INDIA_CENTER, DEFAULT_ZOOM);

    // Add OpenStreetMap Tile Layer
    L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
        attribution: '&copy; OpenStreetMap contributors'
    }).addTo(map);

    // Initialize Layers
    hotspotLayer = L.layerGroup().addTo(map);
    policeLayer = L.layerGroup().addTo(map);
    routeLayer = L.layerGroup().addTo(map);

    // Load Initial Data
    loadHotspots();
    startGeolocation();
}

// Load Hotspots from API
async function loadHotspots() {
    try {
        const response = await fetch('/api/hotspots');
        const hotspots = await response.json();

        hotspots.forEach(center => {
            L.circle([center[0], center[1]], {
                color: 'red',
                fillColor: '#f03',
                fillOpacity: 0.3,
                radius: 500 // 500m radius
            }).addTo(hotspotLayer).bindPopup("High Crime Density Area");
        });
    } catch (error) {
        console.error("Error loading hotspots:", error);
    }
}

// Start Geolocation Tracking
function startGeolocation() {
    if (navigator.geolocation) {
        navigator.geolocation.watchPosition(updateUserLocation, handleLocationError, {
            enableHighAccuracy: true,
            maximumAge: 10000,
            timeout: 5000
        });
    } else {
        alert("Geolocation is not supported by this browser.");
    }
}

// Update User Location Logic
function updateUserLocation(position) {
    const lat = position.coords.latitude;
    const lng = position.coords.longitude;
    const accuracy = position.coords.accuracy;

    if (!userMarker) {
        // Create pulsing marker icon (simple CSS implementation via divIcon or just standard blue marker)
        // For simplicity using standard marker but we can customize
        userMarker = L.marker([lat, lng], {
            icon: L.icon({
                iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-blue.png',
                shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                iconSize: [25, 41],
                iconAnchor: [12, 41],
                popupAnchor: [1, -34],
                shadowSize: [41, 41]
            })
        }).addTo(map).bindPopup("You are here");

        map.setView([lat, lng], 15);
    } else {
        userMarker.setLatLng([lat, lng]);
    }

    // Check Safety of current location
    checkSafety(lat, lng);
}

function handleLocationError(error) {
    console.warn(`ERROR(${error.code}): ${error.message}`);
}

// Check Safety API Call
async function checkSafety(lat, lng) {
    try {
        const response = await fetch('/api/predict_crime', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: lat, lng: lng })
        });
        const data = await response.json();

        if (data.risk_score > RISK_THRESHOLD) {
            triggerAlert(data);
        } else {
            document.getElementById('alertOverlay').classList.add('d-none');
        }

        // --- GNN Spatial Propagation Visualization ---
        if (data.gnn_active && data.spatial_influence) {
            visualizeGNNPropagation(data.spatial_influence);
        }
    } catch (error) {
        console.error("Error checking safety:", error);
    }
}

// Global layer for GNN links
let gnnLayer;

function visualizeGNNPropagation(links) {
    if (!map) return;
    if (gnnLayer) map.removeLayer(gnnLayer);
    gnnLayer = L.layerGroup().addTo(map);

    links.forEach(link => {
        const polyline = L.polyline([link.from, link.to], {
            color: 'cyan',
            weight: link.intensity * 5,
            opacity: link.intensity * 0.6,
            dashArray: '5, 10',
            className: 'gnn-propagation-line'
        }).addTo(gnnLayer);

        // Add a subtle ripple effect or indicator at the source of influence
        L.circle(link.to, {
            color: 'cyan',
            fillColor: '#0ff',
            fillOpacity: 0.2,
            radius: link.intensity * 500
        }).addTo(gnnLayer).bindPopup(`Neighboring Spatial Influence: ${Math.round(link.intensity * 100)}%`);
    });
}

// Trigger Alert UI
async function triggerAlert(data) {
    const alertOverlay = document.getElementById('alertOverlay');
    const alertMessage = document.getElementById('alertMessage');
    const nearestName = document.getElementById('nearestStationName');
    const nearestPhone = document.getElementById('nearestStationPhone');

    alertMessage.innerText = `Danger! ${data.predicted_crime} Risk: ${data.risk_score}%`;
    alertOverlay.classList.remove('d-none');

    // Fetch Nearest Police
    const userPos = userMarker.getLatLng();
    const policeResponse = await fetch('/api/nearby_police', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ lat: userPos.lat, lng: userPos.lng })
    });
    const stations = await policeResponse.json();

    if (stations.length > 0) {
        const nearest = stations[0];
        nearestName.innerText = `${nearest.name} (${nearest.distance_km}km)`;
        nearestPhone.href = `tel:${nearest.phone}`;

        // Show police on map
        policeLayer.clearLayers();
        stations.forEach(st => {
            L.marker([st.lat, st.lng], {
                icon: L.icon({
                    iconUrl: 'https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-violet.png',
                    shadowUrl: 'https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png',
                    iconSize: [25, 41],
                    iconAnchor: [12, 41],
                    popupAnchor: [1, -34],
                    shadowSize: [41, 41]
                })
            }).addTo(policeLayer).bindPopup(`<b>${st.name}</b><br>Ph: ${st.phone}<br>Dist: ${st.distance_km}km`);
        });
    }

    // Fetch Nearby Hospitals
    const hospitalInfo = document.getElementById('hospitalInfo');
    try {
        const hospResponse = await fetch('/api/nearby_hospitals', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: userPos.lat, lng: userPos.lng })
        });
        const hospitals = await hospResponse.json();

        if (hospitals.length > 0) {
            const count = hospitals.filter(h => h.distance_km <= 3.0).length;
            const nearestHosp = hospitals[0];
            hospitalInfo.innerHTML = `🚑 <b>${count}</b> Hospitals within 3km. Nearest: <b>${nearestHosp.name}</b> (${nearestHosp.distance_km}km)`;
        } else {
            hospitalInfo.innerText = "No hospitals nearby.";
        }
    } catch (e) {
        console.error("Error fetching hospitals:", e);
        hospitalInfo.innerText = "Medical services offline.";
    }
}

function dismissAlert() {
    document.getElementById('alertOverlay').classList.add('d-none');
}

// Route Form Submission
// Route Form Submission
document.getElementById('routeForm').addEventListener('submit', async function (e) {
    e.preventDefault();

    const start = document.getElementById('startLocation').value;
    const end = document.getElementById('endLocation').value;
    const date = document.getElementById('dateInput').value;
    const time = document.getElementById('timeInput').value;
    const weather = document.getElementById('weatherInput').value;

    // Show spinner
    document.getElementById('btnText').innerText = "Analyzing...";
    document.getElementById('btnSpinner').classList.remove('d-none');

    try {
        const response = await fetch('/api/predict_route', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ start_location: start, dest_location: end, date: date, time: time, weather: weather })
        });
        const data = await response.json();

        // Show Results Panel & SMS Share
        document.getElementById('resultsPanel').classList.remove('d-none');
        document.getElementById('smsShareSection').classList.remove('d-none');
        const routeOptions = document.getElementById('routeOptions');
        routeOptions.innerHTML = ''; // Clear previous

        if (data.routes && data.routes.length > 0) {
            data.routes.forEach((route, index) => {
                // Determine badge color
                let badgeClass = 'bg-danger';
                if (route.risk_level === 'Safe') badgeClass = 'bg-success';
                else if (route.risk_level === 'Moderate') badgeClass = 'bg-warning text-dark';

                const item = document.createElement('a');
                item.href = '#';
                item.className = 'list-group-item list-group-item-action border-0 shadow-sm mb-2 rounded';
                item.onclick = (e) => { e.preventDefault(); visualizeRoute(route); };
                item.innerHTML = `
                    <div class="d-flex w-100 justify-content-between align-items-center">
                        <h6 class="mb-1 fw-bold text-primary">${route.summary}</h6>
                        <span class="badge ${badgeClass}">${route.risk_level}</span>
                    </div>
                    <p class="mb-1 small"><i class="far fa-clock me-1"></i> ${route.duration} <span class="text-muted mx-1">|</span> <i class="fas fa-route me-1"></i> ${route.distance}</p>
                    <small class="text-muted">Safety Score: <b>${route.safety_score}/100</b></small>
                `;
                routeOptions.appendChild(item);
            });

            // Visualize the first/safest route by default
            visualizeRoute(data.routes[0]);
        } else {
            routeOptions.innerHTML = '<div class="alert alert-warning">No routes found.</div>';
        }

    } catch (error) {
        console.error("Error predicting route:", error);
        alert("Failed to analyze route.");
    } finally {
        document.getElementById('btnText').innerText = "🚨 Check Route Safety";
        document.getElementById('btnSpinner').classList.add('d-none');
    }
});

// Visualize a single route
function visualizeRoute(route) {
    // Clear previous layers
    if (routeLayer) map.removeLayer(routeLayer);

    // 1. Draw the full path line (base)
    const latlngs = route.path;

    // Create a feature group for the segments
    routeLayer = L.featureGroup().addTo(map);

    // If we have risk segments, draw them colorded
    if (route.risk_segments && route.risk_segments.length > 0) {
        // Draw the main line
        L.polyline(latlngs, {
            color: 'blue',
            weight: 5,
            opacity: 0.6
        }).addTo(routeLayer);

        // Add markers/circles for high risk spots
        route.risk_segments.forEach(seg => {
            let color = 'green';
            if (seg.risk > 70) color = 'red';
            else if (seg.risk > 40) color = 'orange';

            // Only show significant points to avoid clutter
            if (seg.risk > 40) {
                L.circle([seg.lat, seg.lng], {
                    color: color,
                    fillColor: color,
                    fillOpacity: 0.8,
                    radius: 30
                }).addTo(routeLayer).bindPopup(`Risk Score: ${seg.risk}`);
            }
        });

    } else {
        // Fallback simple line
        L.polyline(latlngs, { color: 'blue', weight: 5 }).addTo(routeLayer);
    }

    // Fit bounds
    map.fitBounds(L.polyline(latlngs).getBounds());
}

function updateChart(probabilities) {
    const ctx = document.getElementById('riskChart').getContext('2d');

    if (riskChart) {
        riskChart.destroy();
    }

    const labels = Object.keys(probabilities);
    const data = Object.values(probabilities);

    riskChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: labels,
            datasets: [{
                data: data,
                backgroundColor: [
                    '#ff6384',
                    '#36a2eb',
                    '#ffce56',
                    '#4bc0c0',
                    '#9966ff'
                ]
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'right',
                    labels: { boxWidth: 10 }
                }
            }
        }
    });
}

// Emergency Call Button
document.getElementById('sosBtn').addEventListener('click', async function () {
    // Determine closest station (simple logic: current location if tracked, else default)
    if (userMarker) {
        const userPos = userMarker.getLatLng();
        const response = await fetch('/api/nearby_police', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ lat: userPos.lat, lng: userPos.lng })
        });
        const stations = await response.json();
        if (stations.length > 0) {
            window.location.href = `tel:${stations[0].phone}`;
        }
    } else {
        window.location.href = "tel:100"; // Default emergency
    }
});

// Show Trends Logic
async function showTrends() {
    const modal = new bootstrap.Modal(document.getElementById('trendsModal'));
    modal.show();

    try {
        const response = await fetch('/api/crime_trends');
        const data = await response.json();

        const ctx = document.getElementById('trendChart').getContext('2d');
        if (trendChart) trendChart.destroy();

        const histDates = data.historical.map(d => d.date);
        const histCounts = data.historical.map(d => d.count);
        const forecastDates = data.forecast.map(d => d.date);
        const forecastCounts = data.forecast.map(d => d.count);

        // Combine for display
        const labels = [...histDates, ...forecastDates];
        // Pad forecast with nulls to align
        const histDataPoints = [...histCounts, ...new Array(forecastCounts.length).fill(null)];
        // Pad history with nulls (except last point to connect lines)
        const forecastDataPoints = [...new Array(histCounts.length - 1).fill(null), histCounts[histCounts.length - 1], ...forecastCounts];

        trendChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: labels,
                datasets: [
                    {
                        label: 'Historical Crimes',
                        data: histDataPoints,
                        borderColor: 'blue',
                        fill: false,
                        tension: 0.1
                    },
                    {
                        label: 'Forecast (BiLSTM)',
                        data: forecastDataPoints,
                        borderColor: 'red',
                        borderDash: [5, 5],
                        fill: false,
                        tension: 0.1
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false
            }
        });

    } catch (error) {
        console.error("Error fetching trends:", error);
    }
}

// Live Monitor Logic
let alertInterval;

function showMonitor() {
    const modal = new bootstrap.Modal(document.getElementById('monitorModal'));
    const feedImg = document.getElementById('liveFeed');

    // Set src to start streaming
    feedImg.src = "/video_feed";

    modal.show();

    // Start polling for alerts
    document.getElementById('alertTicker').classList.remove('d-none');
    alertInterval = setInterval(checkAlerts, 2000);

    // Stop streaming when modal closes
    document.getElementById('monitorModal').addEventListener('hidden.bs.modal', function () {
        feedImg.src = "";
        clearInterval(alertInterval);
    });
}

async function checkAlerts() {
    try {
        const response = await fetch('/api/alerts');
        const alerts = await response.json();

        const ticker = document.getElementById('alertTicker');

        if (alerts.length > 0) {
            const latest = alerts[alerts.length - 1];
            ticker.innerHTML = `<i class="fas fa-exclamation-circle me-2"></i> ${latest.message} at ${latest.time}`;

            // Flash effect
            ticker.classList.add('bg-warning', 'text-dark');
            ticker.classList.remove('bg-danger', 'text-white');
            setTimeout(() => {
                ticker.classList.remove('bg-warning', 'text-dark');
                ticker.classList.add('bg-danger', 'text-white');
            }, 500);

        } else {
            ticker.innerHTML = `<i class="fas fa-video me-2"></i> System Active. No threats detected.`;
        }
    } catch (e) {
        console.error("Error polling alerts:", e);
    }
}

async function triggerBlockchainSOS() {
    console.log("Triggering Web3 Emergency Network (IPFS + Blockchain)...");

    // Toggle UI visibility
    const alertOverlay = document.getElementById('alertOverlay');
    const statusSection = document.getElementById('blockchainStatusSection');
    const details = document.getElementById('blockchainDetails');
    const links = document.getElementById('blockchainLinks');

    alertOverlay.classList.remove('d-none');
    statusSection.classList.remove('d-none');
    links.classList.add('d-none');
    details.innerHTML = '<i class="fas fa-circle-notch fa-spin me-2"></i>Uploading metadata to IPFS & Logging on Polygon...';

    // Get current location
    let lat = 20.5937, lng = 78.9629; // Defaults
    if (userMarker) {
        const pos = userMarker.getLatLng();
        lat = pos.lat;
        lng = pos.lng;
    }

    try {
        const response = await fetch('/api/blockchain_alert', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lat: lat,
                lng: lng,
                crime_type: "Manual SOS (Blockchain)"
            })
        });

        const data = await response.json();

        if (data.blockchain_hash) {
            details.innerHTML = `<span class="text-success fw-bold"><i class="fas fa-check-circle me-1"></i>${data.verification_stamp}</span><br>
                                 <span class="small">IPFS CID: ${data.ipfs_cid.substring(0, 15)}...</span>`;

            // Set links
            document.getElementById('txLink').href = data.explorer_url;
            document.getElementById('ipfsLink').href = data.ipfs_url;
            links.classList.remove('d-none');

            console.log("Blockchain Alert Successful:", data.blockchain_hash);
        } else {
            throw new Error(data.error || "Web3 Transaction Failed");
        }
    } catch (e) {
        console.error("Web3 SOS Error:", e);
        details.innerHTML = `<span class="text-danger"><i class="fas fa-times-circle me-1"></i>Web3 Error: ${e.message}</span>`;
    }
}

async function sendSmsReport() {
    const phone = document.getElementById('phoneInput').value;
    if (!phone || phone.length !== 10) {
        alert("Please enter a valid 10-digit phone number.");
        return;
    }

    const start = document.getElementById('startLocation').value;
    const end = document.getElementById('endLocation').value;

    try {
        const response = await fetch('/api/twilio_webhook', {
            method: 'POST',
            headers: { 'Content-Type': 'application/x-www-form-urlencoded' },
            // Twilio expected format for simulation or direct call
            body: `Body=${start} -> ${end}&From=+91${phone}`
        });

        if (response.ok) {
            alert("Safety report sent successfully!");
        } else {
            alert("Failed to send SMS. Check terminal for errors.");
        }
    } catch (e) {
        console.error("Error sending SMS:", e);
        alert("System error sending SMS.");
    }
}

// Init on Load
window.onload = initMap;
