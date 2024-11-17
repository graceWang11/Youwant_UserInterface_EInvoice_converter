document.addEventListener("DOMContentLoaded", function() {
    // Initialize Lucide icons
    lucide.createIcons();

    // Get DOM elements
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const vendorInput = document.getElementById('vendorInput');
    const fileList = document.getElementById('fileList');
    const fileList1 = document.getElementById('fileList1');
    const downloadLink = document.getElementById('downloadLink');
    const downloadButton = document.getElementById('downloadButton');
    const responseDiv = document.getElementById('response');
    const submitButton = document.getElementById('submitButton');
    const selectedFileText = document.getElementById('selectedFile');
    const buttonText = submitButton.querySelector('.button-text');

    // Initially hide download elements
    downloadButton.style.display = 'none';
    downloadLink.style.display = 'none';

    // File input change handler
    fileInput.addEventListener('change', function(event) {
        if (event.target.files && event.target.files[0]) {
            selectedFileText.textContent = `Selected file: ${event.target.files[0].name}`;
        } else {
            selectedFileText.textContent = '';
        }
    });

    // Drag and drop handlers
    const uploadArea = document.querySelector('.upload-area');

    uploadArea.addEventListener('dragover', function(e) {
        e.preventDefault();
        uploadArea.classList.add('drag-over');
    });

    uploadArea.addEventListener('dragleave', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
    });

    uploadArea.addEventListener('drop', function(e) {
        e.preventDefault();
        uploadArea.classList.remove('drag-over');
        
        if (e.dataTransfer.files.length) {
            fileInput.files = e.dataTransfer.files;
            selectedFileText.textContent = `Selected file: ${e.dataTransfer.files[0].name}`;
        }
    });

    // Submit button handler
    submitButton.addEventListener('click', function() {
        if (!fileInput.files.length) {
            alert('Please select a file to convert.');
            return;
        }
        if (!vendorInput.value.trim()) {
            alert('Please enter a vendor name.');
            return;
        }
        uploadAndPrepareDownload(fileInput.files[0], vendorInput.value.trim());
    });

    // Add these new functions
    function updateProgress(percentage, status) {
        const progressContainer = document.getElementById('progressContainer');
        const progressFill = document.querySelector('.progress-fill');
        const progressText = document.querySelector('.progress-text');
        const progressStatus = document.querySelector('.progress-status');
        
        progressContainer.style.display = 'block';
        progressFill.style.width = `${percentage}%`;
        progressText.textContent = `Processing: ${percentage}%`;
        if (status) {
            progressStatus.textContent = status;
        }
    }

    function resetProgress() {
        const progressContainer = document.getElementById('progressContainer');
        const progressFill = document.querySelector('.progress-fill');
        const progressText = document.querySelector('.progress-text');
        const progressStatus = document.querySelector('.progress-status');
        
        progressContainer.style.display = 'none';
        progressFill.style.width = '0%';
        progressText.textContent = 'Processing: 0%';
        progressStatus.textContent = 'Initializing...';
    }

    // Update the uploadAndPrepareDownload function
    async function uploadAndPrepareDownload(file, vendor) {
        try {
            resetProgress();
            updateProgress(0, 'Starting upload...');

            const formData = new FormData();
            formData.append('file', file);
            formData.append('vendor', vendor);

            // Create custom XMLHttpRequest to track upload progress
            const xhr = new XMLHttpRequest();
            
            const promise = new Promise((resolve, reject) => {
                xhr.upload.onprogress = function(e) {
                    if (e.lengthComputable) {
                        const percentComplete = Math.round((e.loaded / e.total) * 50);
                        updateProgress(percentComplete, 'Uploading file...');
                    }
                };

                xhr.onload = function() {
                    if (xhr.status === 200) {
                        const response = JSON.parse(xhr.responseText);
                        resolve(response);
                    } else {
                        reject(new Error('Upload failed'));
                    }
                };

                xhr.onerror = function() {
                    reject(new Error('Upload failed'));
                };
            });

            xhr.open('POST', '/upload', true);
            xhr.send(formData);

            // Start processing status updates
            const processingInterval = setInterval(() => {
                fetch(`/process-status/${vendor}/${file.name}`)
                    .then(response => response.json())
                    .then(data => {
                        if (data.status === 'completed') {
                            clearInterval(processingInterval);
                            updateProgress(100, 'Processing completed!');
                            setTimeout(() => {
                                resetProgress();
                            }, 2000);
                        } else {
                            const processPercentage = 50 + Math.round(data.progress * 50);
                            updateProgress(processPercentage, data.status);
                        }
                    })
                    .catch(error => {
                        console.error('Error checking process status:', error);
                    });
            }, 1000);

            const result = await promise;

            if (!result.success) {
                throw new Error(result.message || 'Upload failed');
            }

            // Trigger download
            window.location.href = result.downloadUrl;
            return true;
        } catch (error) {
            console.error('Upload error:', error);
            alert(`Upload failed: ${error.message}`);
            resetProgress();
            return false;
        }
    }
});
