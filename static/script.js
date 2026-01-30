// Initialize Chart
const ctx = document.getElementById('occupancyChart').getContext('2d');
const occupancyChart = new Chart(ctx, {
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

// Update stats every 1 second
function updateStats() {
    fetch('/stats')
        .then(response => response.json())
        .then(data => {
            document.getElementById('capacity-val').innerText = data.total;
            document.getElementById('occupied-val').innerText = data.occupied;
            document.getElementById('available-val').innerText = data.vacant;
            document.getElementById('utilization-val').innerText = data.utilization.toFixed(1) + '%';

            // Update Chart
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

            // Update Logs
            const logsContainer = document.getElementById('slot-logs');
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
        })
        .catch(err => console.error('Error fetching stats:', err));
}

setInterval(updateStats, 1000);
updateStats();
