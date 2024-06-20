document.addEventListener("DOMContentLoaded", function() {
    const uploadForm = document.getElementById('uploadForm');
    const fileInput = document.getElementById('fileInput');
    const vendorInput = document.getElementById('vendorInput');
    const fileList = document.getElementById('fileList');
    const downloadLink = document.getElementById('downloadLink');
    const downloadButton = document.getElementById('downloadButton');
    const submitButton = document.querySelector('button[type="button"]'); // Selecting the submit button

    submitButton.addEventListener('click', function() {
        uploadAndPrepareDownload(); // Calls the function to upload and prepare the download link
    });

    uploadForm.addEventListener('submit', function(e) {
        e.preventDefault(); // Prevents the form from submitting traditionally
    });

    function uploadAndPrepareDownload() {
        const formData = new FormData();
        const fileInput = document.getElementById('fileInput');
        const vendorInput = document.getElementById('vendorInput');
        const responseDiv = document.getElementById('response');
    
        if (!fileInput.files.length) {
            alert('Please select a file to convert.');
            return;
        }
    
        formData.append('file', fileInput.files[0]);
        formData.append('vendor', vendorInput.value);
    
        fetch('/upload', { 
            method: 'POST',
            body: formData,
        })
        .then(response => {
            if (!response.ok) {
                throw new Error('Network response was not ok ' + response.statusText);
            }
            return response.json();
        })
        .then(data => {
            if (data.success) {
                console.log('File processed successfully:', data.message);
                responseDiv.innerHTML = data.message; // Display the step-by-step messages
                document.getElementById('fileList').innerHTML = "File converted successfully!";
                const downloadLink = document.getElementById('downloadLink');
                downloadLink.href = data.downloadUrl;
                downloadLink.style.display = 'block';
                document.getElementById('downloadButton').style.display = 'block';
            } else {
                document.getElementById('fileList').innerHTML = "Failed to convert the file.";
                throw new Error('Processing failed: ' + data.message);
            }
        })
        .catch(error => {
            console.error('Error:', error);
            document.getElementById('fileList').innerHTML = "Error processing your file. Please try again.";
        });
    }
    
});
