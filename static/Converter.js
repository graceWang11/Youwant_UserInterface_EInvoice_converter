document.addEventListener("DOMContentLoaded", function() {
    // Initialize Lucide icons
    lucide.createIcons();

    // Get DOM elements
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const vendorInput = document.getElementById('vendorInput');
    const fileList = document.getElementById('fileList');
    const fileList1 = document.getElementById('fileList1');
    const downloadButton = document.getElementById('downloadButton');
    const responseDiv = document.getElementById('response');
    const submitButton = document.getElementById('submitButton');
    const selectedFileText = document.getElementById('selectedFile');
    const buttonText = submitButton.querySelector('.button-text');

    //Initially hide download button
    if (downloadButton) {
        downloadButton.style.display = 'none';
    }

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
        const progressBar = document.getElementById('progress-bar');
        const progressText = document.getElementById('progress-text');
        const statusMessage = document.getElementById('status-message');

        if (!progressContainer || !progressBar || !progressText || !statusMessage) {
            console.error('Progress elements not found');
            return;
        }

        // Ensure the progress container is visible
        progressContainer.style.display = 'block';

        // Update the progress bar
        progressBar.style.width = `${percentage}%`;
        progressText.textContent = `${percentage}%`;
        statusMessage.textContent = status;

        // If completed, show success state
        if (percentage >= 100) {
            progressBar.style.backgroundColor = '#10B981'; // Change to success color
            setTimeout(() => {
                progressContainer.style.display = 'none';
            }, 2000); // Hide after 2 seconds
        }

        console.log(`Progress updated: ${percentage}% - ${status}`); // Add this for debugging
    }

    function resetProgress() {
        const progressContainer = document.getElementById('progressContainer');
        const progressBar = document.getElementById('progress-bar');
        const statusElement = document.getElementById('status-message');

        progressContainer.style.display = 'none';
        progressBar.style.width = '0%';
        progressBar.textContent = '0%';
        statusElement.textContent = 'Initializing...';
    }

    // Update the uploadAndPrepareDownload function
    async function uploadAndPrepareDownload(file, vendor) {
        try {
            resetProgress();
            updateProgress(0, 'Starting upload...');
            let processingInterval = null;
            let isCompleted = false;

            const formData = new FormData();
            formData.append('file', file);
            formData.append('vendor', vendor);

            // Create custom XMLHttpRequest to track upload progress
            const xhr = new XMLHttpRequest();
            
            const promise = new Promise((resolve, reject) => {
                xhr.upload.onprogress = function(e) {
                    if (e.lengthComputable) {
                        const percentComplete = Math.round((e.loaded / e.total) * 30);
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
            processingInterval = setInterval(async () => {
                if (isCompleted) {
                    clearInterval(processingInterval);
                    return;
                }

                try {
                    const response = await fetch(`/process-status/${vendor}/${encodeURIComponent(file.name)}`);
                    if (!response.ok) {
                        throw new Error('Network response was not ok');
                    }
                    const data = await response.json();
                    
                    console.log('Process status:', data); 
                    
                    if (data.status === 'Completed!' || data.progress >= 1.0) {
                        isCompleted = true;
                        clearInterval(processingInterval);
                        updateProgress(100, 'Processing completed!');
                        
                        // Update the success message immediately
                        const fileList = document.getElementById('fileList');
                        const fileList1 = document.getElementById('fileList1');
                        
                        console.log('Setting success message');
                        fileList.innerHTML = '<span style="color: #10B981; font-weight: bold;">✓ File converted successfully!</span>';
                        fileList1.innerHTML = '<span style="color: #10B981; font-weight: bold;">✓ 文件已成功转换！</span>';
                        
                        // Show the download button if URL is available
                        if (data.downloadUrl) {
                            console.log('Download URL received:', data.downloadUrl);
                            const downloadButton = document.getElementById('downloadButton');
                            if (downloadButton) {
                                console.log('Download button found, making visible');
                                downloadButton.style.display = 'inline-block';
                                downloadButton.onclick = function() {
                                    console.log('Download button clicked, navigating to:', data.downloadUrl);
                                    window.location.href = data.downloadUrl;
                                };
                            } else {
                                console.error('Download button not found in DOM');
                            }
                        } else {
                            console.error('No download URL received from server');
                        }
                        return;
                    } else if (data.status === 'Error') {
                        isCompleted = true;
                        clearInterval(processingInterval);
                        throw new Error(data.error || 'Processing failed');
                    }
                    
                    // Update progress based on actual progress
                    const processPercentage = Math.round((data.progress || 0) * 100);
                    updateProgress(processPercentage, data.status || 'Processing...');
                    
                } catch (error) {
                    console.error('Error checking process status:', error);
                    isCompleted = true;
                    clearInterval(processingInterval);
                    updateProgress(0, 'Error: ' + error.message);
                }
            }, 1000);

            const result = await promise;
            if (!result.success) {
                isCompleted = true;
                clearInterval(processingInterval);
                throw new Error(result.message || 'Upload failed');
            }

            return true;
        } catch (error) {
            console.error('Upload error:', error);
            alert(`Upload failed: ${error.message}`);
            resetProgress();
            return false;
        }
    }

    function showDownloadButton(downloadUrl) {
        console.log('showDownloadButton called with URL:', downloadUrl);
        
        const downloadButton = document.getElementById('downloadButton');
        const fileList = document.getElementById('fileList');
        const fileList1 = document.getElementById('fileList1');

        if (!downloadButton) {
            console.error('Download button not found in DOM');
            return;
        }

        console.log('Download button found:', downloadButton);

        // Update the converted files section with more visible success message
        fileList.innerHTML = '<span style="color: #10B981; font-weight: bold;">✓ File converted successfully!</span>';
        fileList1.innerHTML = '<span style="color: #10B981; font-weight: bold;">✓ 文件已成功转换！</span>';

        // Make the download button visible once the success message is set
        if (fileList.innerHTML.includes('File converted successfully!')) {
            downloadButton.style.display = 'inline-block';
            console.log('Download button display set to inline-block');
        }

        // Add click handler
        downloadButton.onclick = function() {
            console.log('Download button clicked, navigating to:', downloadUrl);
            window.location.href = downloadUrl;
        };

        // Show the download section
        // const downloadSection = document.querySelector('.download-section');
        // if (downloadSection) {
        //     downloadSection.style.display = 'block';
        //     console.log('Download section display set to block');
        // } else {
        //     console.error('Download section not found in DOM');
        // }
        
        console.log('Download button shown with URL:', downloadUrl); // Debug log
    }

    function blurBackground() {
        const overlay = document.createElement('div');
        overlay.classList.add('overlay');
        document.body.appendChild(overlay);
    }

    function unblurBackground() {
        const overlay = document.querySelector('.overlay');
        if (overlay) {
            document.body.removeChild(overlay);
        }
    }

    function downloadFile(url) {
        const link = document.createElement('a');
        link.href = url;
        link.setAttribute('download', '');
        document.body.appendChild(link);
        link.click();
        document.body.removeChild(link);
        
        // Reset progress and remove blur after download
        resetProgress();
        unblurBackground();
    }

    // Prevent default link behavior
    document.addEventListener('click', function(e) {
        if (e.target.tagName === 'A' && e.target.getAttribute('href').includes('/download/')) {
            e.preventDefault();
        }
    });

    // Add this to prevent any default navigation
    window.onbeforeunload = function(e) {
        const dialogText = 'Are you sure you want to leave?';
        e.returnValue = dialogText;
        return dialogText;
    };

    function showConvertedFile(filename) {
        const convertedFilesContainer = document.getElementById('converted-files');
        convertedFilesContainer.innerHTML = `
            <p>File has been converted:</p>
            <a href="/download/${encodeURIComponent(filename)}" download>${filename}</a>
        `;
    }
});
