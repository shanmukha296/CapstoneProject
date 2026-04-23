// Nationwide Police Mapping & Tracking
let policeSearchLayer;
let gpsUpdateInterval;

document.addEventListener('DOMContentLoaded', () => {
    // Wait for main map to init
    setTimeout(() => {
        if (map) {
            policeSearchLayer = L.layerGroup().addTo(map);
            initNationwideTracking();
        }
    }, 1000);
});

function initNationwideTracking() {
    console.log("Initializing Nationwide Police Tracking (5s intervals)...");

    if (navigator.geolocation) {
        // Initial search
        navigator.geolocation.getCurrentPosition(pos => {
            fetchNearbyPolice(pos.coords.latitude, pos.coords.longitude);
        });

        // Set 5s interval for automatic updates
        gpsUpdateInterval = setInterval(() => {
            navigator.geolocation.getCurrentPosition(pos => {
                fetchNearbyPolice(pos.coords.latitude, pos.coords.longitude);
            });
        }, 5000);
    }
}

async function fetchNearbyPolice(lat, lng) {
    const state = document.getElementById('stateFilter').value;

    try {
        const response = await fetch('/api/police_search', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                lat: lat,
                lng: lng,
                state: state
            })
        });

        const data = await response.json();
        updatePoliceUI(data);
        renderPoliceMarkers(data.nearest);
    } catch (e) {
        console.error("Police search error:", e);
    }
}

function updatePoliceUI(data) {
    // Update the nearest station info in the sidebar if results exist
    const resultsPanel = document.getElementById('resultsPanel');
    const routeOptions = document.getElementById('routeOptions');

    if (data.nearest.length > 0) {
        // Proactive alert if crime rate is high
        const nearest = data.nearest[0];
        if (nearest.crime_rate > 1500) {
            showSafetyNotification(`Alert: Entering ${nearest.state} region with very high crime incidence (${nearest.crime_rate}/100k). Nearest station: ${nearest.name}`);
        }
    }
}

function renderPoliceMarkers(stations) {
    if (!policeSearchLayer) return;
    policeSearchLayer.clearLayers();

    const policeIcon = L.icon({
        iconUrl: 'https://cdn-icons-png.flaticon.com/512/1022/1022382.png', // Police Shield/Badge icon
        iconSize: [32, 32],
        iconAnchor: [16, 32],
        popupAnchor: [0, -32]
    });

    stations.forEach(ps => {
        let rateColor = 'green';
        if (ps.crime_rate > 1500) rateColor = 'red';
        else if (ps.crime_rate > 1000) rateColor = 'orange';
        else if (ps.crime_rate > 500) rateColor = 'gold';

        const marker = L.marker([ps.lat, ps.lng], { icon: policeIcon }).addTo(policeSearchLayer);

        const popupContent = `
            <div class="police-popup p-2 text-dark">
                <h6 class="fw-bold mb-1"><i class="fas fa-shield-alt me-2 text-primary"></i>${ps.name}</h6>
                <p class="small mb-2">
                    <b>State:</b> ${ps.state}<br>
                    <b>Dist:</b> <span class="badge bg-primary">${ps.distance_km} km</span><br>
                    <b>Crime Rate:</b> <span style="color: ${rateColor}">${ps.crime_rate}/100k</span>
                </p>
                <a href="tel:${ps.phone}" class="btn btn-danger btn-sm w-100 fw-bold">
                    <i class="fas fa-phone-alt me-2"></i> CALL ${ps.phone}
                </a>
            </div>
        `;

        marker.bindPopup(popupContent);

        // Safety Radius (200m)
        L.circle([ps.lat, ps.lng], {
            color: 'blue',
            fillColor: '#30f',
            fillOpacity: 0.1,
            radius: 200
        }).addTo(policeSearchLayer);
    });
}

function updatePoliceSearch() {
    if (navigator.geolocation) {
        navigator.geolocation.getCurrentPosition(pos => {
            fetchNearbyPolice(pos.coords.latitude, pos.coords.longitude);
        });
    }
}

function showSafetyNotification(msg) {
    // Simple console log or small UI toast could be added here
    console.log("SAFETY ALERT:", msg);
}
