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
        uploadAndPrepareDownload();
    });

    function uploadAndPrepareDownload() {
        const formData = new FormData();
        
        // Update UI to processing state
        buttonText.textContent = 'Processing...';
        submitButton.disabled = true;
        responseDiv.innerHTML = '';
        fileList.innerHTML = 'Converting...';
        
        formData.append('file', fileInput.files[0]);
        formData.append('vendor', vendorInput.value.trim());
    
        fetch('/upload', { 
            method: 'POST',
            body: formData
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                // Success case
                responseDiv.innerHTML = `
                    <div class="alert alert-success">
                        <h4>Success</h4>
                        <p>${data.message}</p>
                    </div>
                `;
                fileList.innerHTML = 'File converted successfully!';
                fileList1.innerHTML = '文件以转换成功！';
                // Setup download
                downloadLink.href = data.downloadUrl;
                downloadLink.style.display = 'block';
                downloadButton.style.display = 'block';
            } else {
                throw new Error(data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            responseDiv.innerHTML = `
                <div class="alert alert-error">
                    <h4>Error</h4>
                    <p>${error.message}</p>
                </div>
            `;
            fileList.innerHTML = 'Error processing your file. Please try again.';
            downloadButton.style.display = 'none';
            downloadLink.style.display = 'none';
        })
        .finally(() => {
            // Reset button state
            buttonText.textContent = 'Submit';
            submitButton.disabled = false;
        });
    }
});
