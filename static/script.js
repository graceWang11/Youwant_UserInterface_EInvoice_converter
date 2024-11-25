document.addEventListener('DOMContentLoaded', () => {
    const noHistoryMessage = document.getElementById('no-history-message'); // Ensure this matches the HTML ID
    const tabs = document.querySelectorAll('.tab-button');
    const panels = document.querySelectorAll('.panel');

    // Function to render logs
    const renderLogs = (logs) => {
        const uploadedTable = panels[0].querySelector('tbody');
        const processingTable = panels[1].querySelector('tbody');
        const completedTable = panels[2].querySelector('tbody');

        // Clear existing rows
        [uploadedTable, processingTable, completedTable].forEach(table => table.innerHTML = '');

        logs.forEach(log => {
            const row = document.createElement('tr');
            row.innerHTML = `
                <td class="px-6 py-4">${log.timestamp}</td>
                <td class="px-6 py-4">${log.filename}</td>
                <td class="px-6 py-4">${log.vendor}</td>
                <td class="px-6 py-4">
                    <span class="status-badge ${getStatusClass(log.status)}">${log.status}</span>
                </td>
            `;

            if (log.status.toLowerCase() === 'processing') {
                row.innerHTML += `
                    <td class="px-6 py-4">
                        <div class="progress-bar-container">
                            <div class="progress-bar">
                                <div class="progress-fill" style="width: ${getProgressWidth(log.status)}%"></div>
                            </div>
                        </div>
                    </td>
                `;
                processingTable.appendChild(row);
            } else if (log.status.toLowerCase() === 'completed' || log.status.toLowerCase().includes('downloaded')) {
                const actionCell = document.createElement('td');
                actionCell.className = 'px-6 py-4';
                const downloadButton = document.createElement('button');
                downloadButton.textContent = log.status.toLowerCase().includes('downloaded') ? 'Downloaded' : 'Download';
                downloadButton.className = 'download-button';
                downloadButton.disabled = log.status.toLowerCase().includes('downloaded');
                downloadButton.addEventListener('click', () => handleDownload(log.vendor, log.filename));
                actionCell.appendChild(downloadButton);
                row.appendChild(actionCell);
                completedTable.appendChild(row);
            } else {
                uploadedTable.appendChild(row);
            }
        });

        // Handle empty states
        [uploadedTable, processingTable, completedTable].forEach((table, index) => {
            if (!table.hasChildNodes()) {
                const emptyRow = document.createElement('tr');
                emptyRow.innerHTML = `<td class="px-6 py-4 text-gray-500" colspan="5">No files in this category.</td>`;
                table.appendChild(emptyRow);
            }
        });
    };

    // Function to fetch and update the upload history
    const updateUploadHistory = async () => {
        try {
            const response = await fetch('/upload-history');
            const data = await response.json();
            if (data.success && data.logs) {
                renderLogs(data.logs);
            } else {
                console.error(data.message || 'Failed to fetch upload history');
            }
        } catch (error) {
            console.error('Error fetching upload history:', error);
        }
    };

    // Function to handle download actions
    const handleDownload = async (vendor, filename) => {
        window.location.href = `/downloads/${vendor}/${filename}`;
        try {
            const response = await fetch('/update-download-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify({ vendor, filename }),
            });
            const data = await response.json();
            if (!data.success) {
                console.error('Failed to update download status:', data.message);
            } else {
                await updateUploadHistory(); // Refresh history after download
            }
        } catch (error) {
            console.error('Error updating download status:', error);
        }
    };

    // Helper function to determine status badge class
    const getStatusClass = (status) => {
        const lowerStatus = status.toLowerCase();
        if (lowerStatus.includes('completed')) return 'status-completed';
        if (lowerStatus.includes('error') || lowerStatus.includes('failed')) return 'status-error';
        if (lowerStatus.includes('processing')) return 'status-processing';
        if (lowerStatus.includes('downloaded')) return 'status-downloaded';
        return 'status-uploaded';
    };

    // Helper function to determine progress percentage
    const getProgressWidth = (status) => {
        const match = status.match(/(\d+)%/);
        return match ? parseInt(match[1]) : 50; // Default to 50% if no match
    };

    // Tab functionality
    tabs.forEach((tab, index) => {
        tab.addEventListener('click', () => {
            tabs.forEach(t => t.classList.remove('selected'));
            panels.forEach(panel => panel.classList.remove('active'));
            tab.classList.add('selected');
            panels[index].classList.add('active');
        });
    });

    // Initial fetch and periodic updates
    updateUploadHistory();
    setInterval(updateUploadHistory, 30000); // Refresh every 30 seconds
});
