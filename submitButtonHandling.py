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

# Define folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DOWNLOAD_FOLDER = os.path.join(BASE_DIR, "processed")
UPLOAD_LOG_FILE = os.path.join(BASE_DIR, 'upload_log.json')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
        # Create log entry
        log_entry = {
            'filename': filename,
            'vendor': vendor_name,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'status': status
        }
        
        # Read existing logs
        if os.path.exists(UPLOAD_LOG_FILE):
            with open(UPLOAD_LOG_FILE, 'r') as f:
                logs = json.load(f)
        else:
            logs = []
        
        # Append new log
        logs.append(log_entry)
        
        # Write updated logs
        with open(UPLOAD_LOG_FILE, 'w') as f:
            json.dump(logs, f, indent=4)
            
        app.logger.info(f"Upload logged: {log_entry}")
    except Exception as e:
        app.logger.error(f"Error logging upload: {str(e)}")

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

@app.route('/upload', methods=['POST'])
def upload_file():
    """Handle file upload and processing."""
    try:
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
        vendor_folder = os.path.join(DOWNLOAD_FOLDER, vendor_name)
        os.makedirs(vendor_folder, exist_ok=True)
        
        output_filename = f"{vendor_name}_{os.path.splitext(filename)[0]}.xlsx"
        output_path = os.path.join(vendor_folder, output_filename)
        df.to_excel(output_path, index=False)
        
        # Set final status to Completed! with progress 1.0
        update_processing_status(vendor_name, original_filename, "Completed!", 1.0)
        
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
        
        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'downloadUrl': f'/downloads/{vendor_name}/{output_filename}'
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

@app.route('/download/<vendor>/<filename>')
def download_file(vendor, filename):
    """Handle file downloads without page navigation"""
    try:
        response = send_from_directory(
            os.path.join(DOWNLOAD_FOLDER, vendor),
            filename,
            as_attachment=True,
            download_name=filename
        )
        # Add headers to prevent caching and navigation
        response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
        response.headers["Pragma"] = "no-cache"
        response.headers["Expires"] = "0"
        response.headers["Content-Disposition"] = f"attachment; filename={filename}"
        return response
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'message': str(e)}), 500

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
        if os.path.exists(UPLOAD_LOG_FILE):
            with open(UPLOAD_LOG_FILE, 'r') as f:
                logs = json.load(f)
            return jsonify({'success': True, 'logs': logs})
        return jsonify({'success': True, 'logs': []})
    except Exception as e:
        app.logger.error(f"Error retrieving upload history: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})
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
                processed_filename = f"{vendor}_{filename}"
                if os.path.exists(os.path.join(DOWNLOAD_FOLDER, vendor, processed_filename)):
                    return jsonify({
                        'status': 'Completed!',
                        'progress': 1.0
                    })
                else:
                    # Update progress based on current status
                    return jsonify({
                        'status': status['status'],
                        'progress': status['progress'] if status['progress'] < 1.0 else 1.0
                    })
    except Exception as e:
        app.logger.error(f"Error getting process status: {str(e)}")
        return jsonify({
            'status': 'Error',
            'progress': 1.0
        })


def update_processing_status(vendor, filename, status, progress):
    """Update the processing status for a specific file"""
    try:
        status_key = f"{vendor}_{filename}"
        with status_lock:
            if progress >= 1.0:
                # If process is complete, remove the status
                if status_key in processing_status:
                    del processing_status[status_key]
                app.logger.info(f"Processing completed and status cleared for {status_key}")
            else:
                processing_status[status_key] = {
                    'status': status,
                    'progress': progress
                }
                app.logger.info(f"Status updated: {status} - {progress}")
    except Exception as e:
        app.logger.error(f"Error updating process status: {str(e)}")



if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
