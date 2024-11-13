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

# Set up logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__, static_folder='static')
CORS(app)

# Define folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DESKTOP_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop")
DOWNLOAD_FOLDER = os.path.join(DESKTOP_FOLDER, "Downloaded")
UPLOAD_LOG_FILE = os.path.join(BASE_DIR, 'upload_log.json')

# Ensure directories exist
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

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
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'[箱\\P#]', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\*[^Kg]*', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'^\d+\.', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\b\d{3}\b', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'\.\d{2}\.', '', str(x)))
        df['Description'] = df['Description'].apply(lambda x: re.sub(r'^[^\w\d]+', '', str(x)))
        df['Barcode'] = df['Barcode'].apply(lambda x: re.sub(r'-', '', str(x)))
        return df
    except Exception as e:
        app.logger.error(f"Error cleaning descriptions: {str(e)}")
        raise

def translate_text(text):
    """Translate text from Chinese to English."""
    translator = Translator()
    try:
        return translator.translate(text, src='zh-cn', dest='en').text
    except Exception as e:
        app.logger.error(f"Translation error for text '{text}': {str(e)}")
        return text

def translate_descriptions(df):
    """Translate all descriptions to English."""
    try:
        df['EnglishDescription'] = df['Description'].apply(translate_text)
        return df
    except Exception as e:
        app.logger.error(f"Error translating descriptions: {str(e)}")
        raise

def update_quantity(df):
    """Update quantities based on multipliers in description."""
    try:
        def extract_and_multiply_qty(row):
            multipliers = re.findall(r'\*(\d+)', str(row['Description']))
            if len(multipliers) >= 2:
                return row['Qty'] * int(multipliers[0]) * int(multipliers[1])
            elif multipliers:
                return row['Qty'] * int(multipliers[0])
            return row['Qty']
        
        df['Qty'] = df.apply(extract_and_multiply_qty, axis=1)
        return df
    except Exception as e:
        app.logger.error(f"Error updating quantities: {str(e)}")
        raise

def calculate_single_price(df):
    """Calculate price per unit."""
    try:
        df['SinglePrice'] = df.apply(
            lambda row: round(row['ExPrice'] / row['Qty'], 2) if row['Qty'] else row['ExPrice'], 
            axis=1
        )
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
        file.save(upload_path)
        app.logger.info(f"File saved to: {upload_path}")

        # Log the upload
        log_upload(filename, vendor_name, 'uploaded')

        # Process file
        df = read_excel_file(upload_path)
        df = update_quantity(df)
        df = calculate_single_price(df)
        df = clean_descriptions(df)
        df = translate_descriptions(df)

        # Save processed file
        vendor_folder = os.path.join(DOWNLOAD_FOLDER, vendor_name)
        os.makedirs(vendor_folder, exist_ok=True)
        
        output_filename = f"{vendor_name}_{os.path.splitext(filename)[0]}.xlsx"
        output_path = os.path.join(vendor_folder, output_filename)
        df.to_excel(output_path, index=False)
        
        # Log successful processing
        log_upload(filename, vendor_name, 'processed')

        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'downloadUrl': f'/downloads/{vendor_name}/{output_filename}'
        })

    except Exception as e:
        # Log failed processing
        if 'filename' in locals():
            log_upload(filename, vendor_name, f'failed: {str(e)}')
        app.logger.error(f"Error processing upload: {str(e)}")
        return jsonify({'success': False, 'message': str(e)})

@app.route('/downloads/<vendor_name>/<filename>')
def download_file(vendor_name, filename):
    """Handle file downloads."""
    try:
        return send_from_directory(
            os.path.join(DOWNLOAD_FOLDER, vendor_name),
            filename,
            as_attachment=True
        )
    except Exception as e:
        app.logger.error(f"Download error: {str(e)}")
        return jsonify({'success': False, 'message': 'Download failed'})

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
        app.logger.error(f"Error listing uploads: {str(e)}")
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

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)
