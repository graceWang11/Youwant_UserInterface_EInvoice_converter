import os
import pandas as pd
import re
from flask import Flask, request, jsonify, send_from_directory
from werkzeug.utils import secure_filename
from googletrans import Translator
from flask_cors import CORS
import logging

# Set up logging
logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__, static_folder='static')
CORS(app)

# Define folders
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
UPLOAD_FOLDER = os.path.join(BASE_DIR, 'uploads')
DESKTOP_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop")
DOWNLOAD_FOLDER = os.path.join(DESKTOP_FOLDER, "Downloaded")

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

        # Save uploaded file
        filename = secure_filename(file.filename)
        upload_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(upload_path)
        app.logger.info(f"File saved to: {upload_path}")

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
        
        # Clean up upload
        os.remove(upload_path)

        return jsonify({
            'success': True,
            'message': 'File processed successfully',
            'downloadUrl': f'/downloads/{vendor_name}/{output_filename}'
        })

    except Exception as e:
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

if __name__ == '__main__':
    app.run(debug=True)
