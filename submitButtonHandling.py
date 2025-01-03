import os
import pandas as pd
import re
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from googletrans import Translator
from flask_cors import CORS
import logging
import json
from datetime import datetime
from threading import Lock
import time

# Set up logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__, static_folder='static')
CORS(app)
logger = logging.getLogger(__name__)

# Define folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
PROCESSED_FOLDER = os.path.join(BASE_DIR, "processed")
DESKTOP_DOWNLOADS = os.path.join(os.path.expanduser("~/Downloads"))
UPLOAD_LOG_FILE = os.path.join(BASE_DIR, 'upload_log.json')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(PROCESSED_FOLDER, exist_ok=True)
os.makedirs(DESKTOP_DOWNLOADS, exist_ok=True)

# Add these after your other global variables
processing_status = {}
status_lock = Lock()

def read_excel_file(file_path):
    """Read data from Excel or CSV file."""
    try:
        file_extension = os.path.splitext(file_path)[1].lower()
        app.logger.info(f"Reading file: {file_path} with extension: {file_extension}")
        
        if file_extension == '.csv':
            return pd.read_csv(file_path)
        elif file_extension == '.xlsx':
            return pd.read_excel(file_path, engine='openpyxl')
        elif file_extension == '.xls':
            return pd.read_excel(file_path, engine='xlrd')
        else:
            raise ValueError(f"Unsupported file format: {file_extension}")
    except Exception as e:
        app.logger.error(f"Error reading file: {str(e)}")
        raise

def clean_descriptions(df):
    """Clean up the description field."""
    try:
        # Check if Description column exists
        if 'Description' not in df.columns:
            # Try to find a similar column name
            possible_desc_columns = [col for col in df.columns if 'desc' in col.lower()]
            if possible_desc_columns:
                df = df.rename(columns={possible_desc_columns[0]: 'Description'})
            else:
                raise ValueError("No 'Description' column found in the uploaded file")

        # Check if Barcode column exists
        if 'Barcode' not in df.columns:
            possible_barcode_columns = [col for col in df.columns if 'barcode' in col.lower() or 'code' in col.lower()]
            if possible_barcode_columns:
                df = df.rename(columns={possible_barcode_columns[0]: 'Barcode'})
            else:
                df['Barcode'] = ''  # Create empty Barcode column if none exists

        # Rest of the cleaning logic
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'[箱\\P#]', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\*[^Kg]*', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'^\d+\.', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\b\d{3}\b', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\.\d{2}\.', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'^[^\w\d]+', '', str(x)))
        
        if 'Barcode' in df.columns:
            df['Barcode'] = df['Barcode'].apply(lambda x: re.sub(r'-', '', str(x)))
        
        return df
    except Exception as e:
        app.logger.error(f"Error cleaning descriptions: {str(e)}")
        raise ValueError(f"Error processing file: {str(e)}")

def translate_text(text):
    """Translate text from Chinese to English."""
    translator = Translator()
    try:
        return translator.translate(text, src='zh-cn', dest='en').text
    except Exception as e:
        app.logger.error(f"Translation error for text '{text}': {str(e)}")
        return text

def translate_descriptions(df):
    """Translate all descriptions to Chinese."""
    try:
        translator = Translator()
        df['Description2'] = df['Description'].apply(lambda text: translator.translate(text, src='en', dest='zh-cn').text)
        return df
    except Exception as e:
        app.logger.error(f"Error translating descriptions: {str(e)}")
        raise

def update_quantity(df):
    """Update quantities based on multipliers in description."""
    try:
        def extract_and_multiply_qty(row):
            multipliers = re.findall(r'\*(\d+)', str(row['Description']))
            result_qty = row['Qty']
            for multiplier in multipliers:
                result_qty *= int(multiplier)
            return result_qty
        
        df['Qty'] = df.apply(extract_and_multiply_qty, axis=1)
        return df
    except Exception as e:
        app.logger.error(f"Error updating quantities: {str(e)}")
        raise

def calculate_single_price(df):
    """Calculate price per unit using StockPrice divided by Qty."""
    try:
        # Convert columns to numeric, replacing any non-numeric values with 0
        df['Qty'] = pd.to_numeric(df['Qty'], errors='coerce').fillna(0)
        df['Price'] = pd.to_numeric(df['Price'], errors='coerce').fillna(0)
        
        # Calculate SinglePrice as StockPrice divided by Qty
        df['SinglePrice'] = df.apply(
            lambda row: round(row['Price'] / row['Qty'], 2) if row['Qty'] > 0 else row['Price'],
            axis=1
        )
        
        # Log some sample calculations for debugging
        app.logger.info("Sample price calculations:")
        app.logger.info(df[['Qty', 'Price', 'SinglePrice']].head())
        
        return df
    except Exception as e:
        app.logger.error(f"Error calculating prices: {str(e)}")
        raise

def log_upload(filename, vendor_name, status):
    """
    Log file upload details to a JSON file
    """
    try:
        # Ensure the log file directory exists
        log_dir = os.path.dirname(UPLOAD_LOG_FILE)
        os.makedirs(log_dir, exist_ok=True)
        
        # Create log entry
        log_entry = {
            'filename': filename,
            'vendor': vendor_name,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': status
        }
        
        logs = []
        # Read existing logs if file exists
        if os.path.exists(UPLOAD_LOG_FILE):
            try:
                with open(UPLOAD_LOG_FILE, 'r') as f:
                    logs = json.load(f)
            except json.JSONDecodeError:
                logger.error("Error reading log file, starting fresh")
                logs = []
        
        # Append new log
        logs.append(log_entry)
        
        # Write updated logs with proper permissions
        with open(UPLOAD_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=4)
        
        # Set proper permissions for the log file
        if os.name != 'nt':  # If not Windows
            os.chmod(UPLOAD_LOG_FILE, 0o666)
            
        logger.info(f"Upload logged successfully: {log_entry}")
        
    except Exception as e:
        logger.error(f"Error logging upload: {str(e)}", exc_info=True)

def map_columns(df):
    """Map original column names to required column names"""
    try:
        # Create the mapping
        df = df.rename(columns={
            'Description1': 'Description',
            'StockQty': 'Qty',
            'StockPrice': 'Price',  # Map StockPrice instead of SalesPrice1
            'Barcode1': 'Barcode'
        })
        
        # Log the columns for debugging
        app.logger.info(f"Columns after mapping: {df.columns.tolist()}")
        
        # Verify the required columns exist
        required_columns = ['Description', 'Qty', 'Price']
        missing_columns = [col for col in required_columns if col not in df.columns]
        
        if missing_columns:
            # If columns are missing, check if they exist under original names
            original_names = {
                'Description': 'Description1',
                'Qty': 'StockQty',
                'Price': 'StockPrice'
            }
            
            # Try to map any missing columns from their original names
            for missing_col in missing_columns:
                original_name = original_names.get(missing_col)
                if original_name in df.columns:
                    df[missing_col] = df[original_name]
        
        return df
    except Exception as e:
        app.logger.error(f"Error mapping columns: {str(e)}")
        raise ValueError(f"Error mapping columns: {str(e)}")

def ensure_directory_permissions():
    """Ensure all required directories have correct permissions"""
    directories = [UPLOAD_FOLDER, PROCESSED_FOLDER, DESKTOP_DOWNLOADS]
    for directory in directories:
        try:
            os.makedirs(directory, exist_ok=True)
            # Ensure write permissions (on Unix systems)
            if os.name != 'nt':  # If not Windows
                os.chmod(directory, 0o755)
        except Exception as e:
            logger.error(f"Permission error creating directory {directory}: {str(e)}")
            raise

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing."""
    try:
        logger.debug(f"Operating System: {os.name}")
        logger.debug(f"Current working directory: {os.getcwd()}")
        logger.debug(f"Upload folder path: {UPLOAD_FOLDER}")
        logger.debug(f"Processed folder path: {PROCESSED_FOLDER}")
        
        ensure_directory_permissions()
        logger.debug("Starting file upload")
        if 'file' not in request.files:
            return jsonify({'success': False, 'message': 'No file uploaded'})
        
        file = request.files['file']
        vendor_name = request.form.get('vendor')
        
        if not file or not file.filename:
            return jsonify({'success': False, 'message': 'No file selected'})
        
        if not vendor_name:
            return jsonify({'success': False, 'message': 'Vendor name required'})

        # Create vendor-specific folder in uploads
        vendor_upload_folder = os.path.join(UPLOAD_FOLDER, vendor_name)
        os.makedirs(vendor_upload_folder, exist_ok=True)

        # Save uploaded file with timestamp
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        original_filename = secure_filename(file.filename)
        filename = f"{timestamp}_{original_filename}"
        upload_path = os.path.join(vendor_upload_folder, filename)
        
        update_processing_status(vendor_name, original_filename, "Saving file...", 0.1)
        file.save(upload_path)
        app.logger.info(f"File saved to: {upload_path}")

        # Log the upload
        log_upload(filename, vendor_name, 'uploaded')

        # Process file with detailed status updates
        update_processing_status(vendor_name, original_filename, "Reading Excel file...", 0.1)
        df = read_excel_file(upload_path)
        
        update_processing_status(vendor_name, original_filename, "Mapping columns...", 0.2)
        df = map_columns(df)
        
        update_processing_status(vendor_name, original_filename, "Processing quantities...", 0.4)
        df = update_quantity(df)
        
        update_processing_status(vendor_name, original_filename, "Calculating prices...", 0.6)
        df = calculate_single_price(df)
        
        update_processing_status(vendor_name, original_filename, "Cleaning descriptions...", 0.8)
        df = clean_descriptions(df)
        
        update_processing_status(vendor_name, original_filename, "Translating descriptions...", 0.9)
        df = translate_descriptions(df)
        
        # Save processed file
        update_processing_status(vendor_name, original_filename, "Saving converted file...", 0.95)
        vendor_folder = os.path.join(PROCESSED_FOLDER, vendor_name)
        os.makedirs(vendor_folder, exist_ok=True)
        
        output_filename = f"{vendor_name}_{os.path.splitext(filename)[0]}.xlsx"
        output_path = os.path.join(vendor_folder, output_filename)
        df.to_excel(output_path, index=False)
        
        # Set final status to Completed! with progress 1.0
        update_processing_status(vendor_name, original_filename, "Completed!", 1.0)
        log_upload(filename, vendor_name, 'completed')

        return jsonify({'success': True, 'message': 'File processed successfully'})

    except Exception as e:
        log_upload(filename, vendor_name, f'failed: {str(e)}')  # Log failure
        app.logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'success': False, 'message': f"An error occurred while processing the file: {str(e)}"})
        
        # Clear the status after a delay (optional)
        def clear_status():
            time.sleep(5)  # Wait 5 seconds
            with status_lock:
                status_key = f"{vendor_name}_{original_filename}"
                if status_key in processing_status:
                    del processing_status[status_key]
        
        # Start the cleanup in a separate thread
        from threading import Thread
        Thread(target=clear_status, daemon=True).start()
        
        logger.debug("Processing file...")
        logger.debug("File processing complete")
        return jsonify({
            'success': True,
            'message': 'File processed successfully',
        })

    except ValueError as e:
        # Log failed processing with specific error
        if 'filename' in locals():
            log_upload(filename, vendor_name, f'failed: {str(e)}')
            update_processing_status(vendor_name, original_filename, f"Error: {str(e)}", 1.0)
        app.logger.error(f"Validation error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
    except Exception as e:
        # Log failed processing
        if 'filename' in locals():
            log_upload(filename, vendor_name, f'failed: {str(e)}')
            update_processing_status(vendor_name, original_filename, f"Error: {str(e)}", 1.0)
        app.logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'success': False, 'message': f"An error occurred while processing the file: {str(e)}"})

@app.route('/downloads/<vendor>/<filename>')
def download_file(vendor, filename):
    """Handle file downloads."""
    try:
        # First, check if file exists in processed folder
        vendor_processed_folder = os.path.join(PROCESSED_FOLDER, vendor)
        processed_file_path = os.path.join(vendor_processed_folder, filename)
        
        if not os.path.exists(processed_file_path):
            app.logger.error(f"File not found in processed folder: {processed_file_path}")
            return jsonify({'success': False, 'message': 'File not found'}), 404

        # Create downloads directory if it doesn't exist
        os.makedirs(DESKTOP_DOWNLOADS, exist_ok=True)
        
        # Copy file to downloads folder
        import shutil
        download_path = os.path.join(DESKTOP_DOWNLOADS, filename)
        shutil.copy2(processed_file_path, download_path)
        
        app.logger.info(f"File copied to downloads: {download_path}")
        
        # Return the file from the processed folder
        return send_from_directory(
            vendor_processed_folder,
            filename,
            as_attachment=True,
            download_name=filename
        )
            
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'message': 'Download failed'}), 500

@app.route('/')
def home():
    return send_from_directory('static', 'converter.html')

@app.route('/history')
def history():
    return send_from_directory('static', 'upload-history.html')

@app.route('/upload-history')
def view_upload_history():
    """View the upload history"""
    try:
        logger.debug(f"Attempting to read upload history from: {UPLOAD_LOG_FILE}")
        
        if os.path.exists(UPLOAD_LOG_FILE):
            try:
                with open(UPLOAD_LOG_FILE, 'r') as f:
                    logs = json.load(f)
                
                # Add download status information
                for log in logs:
                    if 'downloaded_at' in log:
                        log['status'] = f"Downloaded at {log['downloaded_at']}"
                
                logger.debug(f"Successfully loaded {len(logs)} log entries")
                return jsonify({'success': True, 'logs': logs})
            except json.JSONDecodeError as e:
                logger.error(f"Error decoding JSON from log file: {str(e)}")
                return jsonify({'success': False, 'message': 'Error reading log file', 'logs': []})
        else:
            logger.debug("No upload history file found, returning empty list")
            return jsonify({'success': True, 'logs': []})
    except Exception as e:
        logger.error(f"Error retrieving upload history: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e), 'logs': []})

@app.route('/uploads/<vendor_name>')
def list_uploaded_files(vendor_name):
    """List all files uploaded by a specific vendor"""
    try:
        vendor_folder = os.path.join(UPLOAD_FOLDER, vendor_name)
        if not os.path.exists(vendor_folder):
            return jsonify({'success': True, 'files': []})
        
        files = []
        for filename in os.listdir(vendor_folder):
            file_path = os.path.join(vendor_folder, filename)
            if os.path.isfile(file_path):
                files.append({
                    'filename': filename,
                    'uploaded_at': datetime.fromtimestamp(os.path.getctime(file_path)).strftime('%Y-%m-%d %H:%M:%S'),
                    'size': os.path.getsize(file_path)
                })
        
        return jsonify({'success': True, 'files': files})
    except Exception as e:
        app.logger.error(f"Error listing uploaded files: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/uploads/<vendor_name>/<filename>')
def download_original_file(vendor_name, filename):
    """Download an original uploaded file"""
    try:
        return send_from_directory(
            os.path.join(UPLOAD_FOLDER, vendor_name),
            filename,
            as_attachment=True
        )
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'message': 'Download failed'})

@app.route('/process-status/<vendor>/<filename>')
def get_process_status(vendor, filename):
    """Get the processing status for a specific file"""
    try:
        status_key = f"{vendor}_{filename}"
        with status_lock:
            status = processing_status.get(status_key)
            if status is None:
                # Check if the processed file exists
                processed_filename = f"{vendor}_{os.path.splitext(filename)[0]}.xlsx"
                processed_path = os.path.join(PROCESSED_FOLDER, vendor, processed_filename)
                if os.path.exists(processed_path):
                    app.logger.info(f"Found processed file at: {processed_path}")
                    download_url = f'/downloads/{vendor}/{processed_filename}'
                    app.logger.info(f"Generated download URL: {download_url}")
                    return jsonify({
                        'status': 'Completed!',
                        'progress': 1.0,
                        'downloadUrl': download_url
                    })
            
            # If file is still processing, return current status
            if status:
                app.logger.info(f"Current processing status: {status}")
                return jsonify(status)
                
            # Default response if no status found
            return jsonify({
                'status': 'Processing...',
                'progress': 0.5
            })
    except Exception as e:
        app.logger.error(f"Error getting process status: {str(e)}")
        return jsonify({
            'status': 'Error',
            'progress': 0.0,
            'error': str(e)
        }), 200


def update_processing_status(vendor, filename, status, progress):
    """Update the processing status for a specific file"""
    try:
        status_key = f"{vendor}_{filename}"
        with status_lock:
            # When processing is complete, include the download URL
            if progress >= 1.0 or status == 'Completed!':
                processed_filename = f"{vendor}_{os.path.splitext(filename)[0]}.xlsx"
                # Save to processed folder path
                processed_path = os.path.join(PROCESSED_FOLDER, vendor, processed_filename)
                processing_status[status_key] = {
                    'status': status,
                    'progress': progress,
                    'downloadUrl': f'/downloads/{vendor}/{processed_filename}'
                }
                app.logger.info(f"Updated status with download URL for {status_key}")
                app.logger.info(f"Processed file path: {processed_path}")
            else:
                processing_status[status_key] = {
                    'status': status,
                    'progress': progress
                }
            app.logger.info(f"Status updated for {status_key}: {processing_status[status_key]}")
    except Exception as e:
        app.logger.error(f"Error updating process status: {str(e)}")

@app.route('/update-download-status', methods=['POST'])
def update_download_status():
    """Update the status of a file after download"""
    try:
        data = request.json
        vendor = data.get('vendor')
        filename = data.get('filename')
        
        if not vendor or not filename:
            return jsonify({'success': False, 'message': 'Vendor and filename required'})
        
        # Read current logs
        if os.path.exists(UPLOAD_LOG_FILE):
            with open(UPLOAD_LOG_FILE, 'r') as f:
                logs = json.load(f)
            
            # Find and update the relevant log entry
            for log in logs:
                if log['filename'] == filename and log['vendor'] == vendor:
                    log['status'] = 'Downloaded'
                    log['downloaded_at'] = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            
            # Write updated logs back to file
            with open(UPLOAD_LOG_FILE, 'w') as f:
                json.dump(logs, f, indent=4)
            
            logger.info(f"Updated download status for {filename}")
            return jsonify({'success': True})
        
        return jsonify({'success': False, 'message': 'No log file found'})
        
    except Exception as e:
        logger.error(f"Error updating download status: {str(e)}", exc_info=True)
        return jsonify({'success': False, 'message': str(e)})

def update_file_status(filename, vendor, status):
    """Update the status of a file in the upload log"""
    try:
        with open('upload_log.json', 'r') as f:
            logs = json.load(f)
        
        # Find and update the matching entry
        for log in logs:
            if log['filename'] == filename and log['vendor'] == vendor:
                log['status'] = status
                break
        
        with open('upload_log.json', 'w') as f:
            json.dump(logs, f, indent=4)
        
        return True
    except Exception as e:
        print(f"Error updating file status: {e}")
        return False

@app.route('/update-file-status', methods=['POST'])
def handle_status_update():
    try:
        data = request.json
        filename = data.get('filename')
        vendor = data.get('vendor')
        status = data.get('status')
        
        if not all([filename, vendor, status]):
            return jsonify({'success': False, 'message': 'Missing required fields'})
        
        success = update_file_status(filename, vendor, status)
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
