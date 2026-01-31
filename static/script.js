// Initialize Chart only if the element exists
let occupancyChart = null;
const chartCanvas = document.getElementById('occupancyChart');

if (chartCanvas) {
    const ctx = chartCanvas.getContext('2d');
    occupancyChart = new Chart(ctx, {
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: 'Occupied',
                data: [],
                borderColor: '#ef4444',
                backgroundColor: 'rgba(239, 68, 68, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0
            }, {
                label: 'Available',
                data: [],
                borderColor: '#10b981',
                backgroundColor: 'rgba(16, 185, 129, 0.1)',
                fill: true,
                tension: 0.4,
                borderWidth: 3,
                pointRadius: 0
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: { display: false },
                y: {
                    beginAtZero: true,
                    grid: { color: '#f1f5f9' },
                    ticks: { font: { size: 10 } }
                }
            }
        }
    });
}

// Update stats every 1 second
function updateStats() {
    fetch('/stats')
        .then(response => response.json())
        .then(data => {
            // Update Metric Cards
            const capVal = document.getElementById('capacity-val');
            const occVal = document.getElementById('occupied-val');
            const avaVal = document.getElementById('available-val');
            const utiVal = document.getElementById('utilization-val');

            if (capVal) capVal.innerText = data.total;
            if (occVal) occVal.innerText = data.occupied;
            if (avaVal) avaVal.innerText = data.vacant;
            if (utiVal) utiVal.innerText = data.utilization.toFixed(1) + '%';

            // Sync selector if updated from elsewhere
            const selector = document.getElementById('source-selector');
            if (selector && selector.value !== data.source) {
                selector.value = data.source;
            }

            // Update Chart
            if (occupancyChart) {
                const now = new Date().toLocaleTimeString();
                if (occupancyChart.data.labels.length > 20) {
                    occupancyChart.data.labels.shift();
                    occupancyChart.data.datasets[0].data.shift();
                    occupancyChart.data.datasets[1].data.shift();
                }
                occupancyChart.data.labels.push(now);
                occupancyChart.data.datasets[0].data.push(data.occupied);
                occupancyChart.data.datasets[1].data.push(data.vacant);
                occupancyChart.update();
            }

            // Update Logs
            const logsContainer = document.getElementById('slot-logs');
            if (logsContainer) {
                logsContainer.innerHTML = '';
                data.slots.forEach((status, index) => {
                    const row = document.createElement('tr');
                    const isOccupied = status === true;
                    row.innerHTML = `
                        <td>Slot #${(index + 1).toString().padStart(2, '0')}</td>
                        <td><span class="status-badge ${isOccupied ? 'status-occupied' : 'status-vacant'}">${isOccupied ? 'OCCUPIED' : 'VACANT'}</span></td>
                        <td>${data.durations[index] || '0m'}</td>
                    `;
                    logsContainer.appendChild(row);
                });
            }
        })
        .catch(err => console.error('Error fetching stats:', err));
}

// Handle source switch
const sourceSelector = document.getElementById('source-selector');
if (sourceSelector) {
    sourceSelector.addEventListener('change', (e) => {
        const source = e.target.value;
        fetch('/switch_source', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({ source: source }),
        })
            .then(response => response.json())
            .then(data => {
                console.log('Source switched to:', data.source);
                if (data.source !== source) {
                    alert('Warning: Requested source "' + source + '" not available. Using "' + data.source + '" instead.');
                }
                // Force video feed to reconnect by adding a timestamp
                const videoFeed = document.getElementById('video-feed');
                if (videoFeed) {
                    videoFeed.src = '/video_feed?v=' + new Date().getTime();
                }
            })
            .catch(err => console.error('Error switching source:', err));
    });
}

// Dark Mode Toggle
const darkModeToggle = document.getElementById('dark-mode');
if (darkModeToggle) {
    darkModeToggle.addEventListener('change', (e) => {
        if (e.target.checked) {
            document.body.classList.add('dark-theme');
        } else {
            document.body.classList.remove('dark-theme');
        }
    });
}

// Save Settings
const saveSettingsBtn = document.getElementById('save-settings-btn');
if (saveSettingsBtn) {
    saveSettingsBtn.addEventListener('click', () => {
        const sensitivity = document.getElementById('ai-sensitivity').value;
        const darkMode = document.getElementById('dark-mode').checked;
        const notifications = document.getElementById('notifications-toggle').checked;
        const priority = document.getElementById('source-priority').value;

        const settingsData = {
            sensitivity: parseFloat(sensitivity) / 100, // Map 10-90 to 0.1-0.9
            darkMode: darkMode,
            notifications: notifications,
            sourcePriority: priority
        };

        fetch('/save_settings', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(settingsData)
        })
            .then(response => response.json())
            .then(data => {
                if (data.status === 'success') {
                    alert('Settings saved successfully!');
                }
            })
            .catch(err => {
                console.error('Error saving settings:', err);
                alert('Failed to save settings.');
            });
    });
}

// Auto-run stats update if we are on a page that needs it
if (document.getElementById('capacity-val') || occupancyChart) {
    setInterval(updateStats, 1000);
    updateStats();
}
