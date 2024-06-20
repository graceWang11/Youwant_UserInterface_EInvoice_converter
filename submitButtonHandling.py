import os
import pandas as pd
import re
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from googletrans import Translator
from flask_cors import CORS  # Import CORS
import logging

logging.basicConfig(level=logging.DEBUG)
app = Flask(__name__,static_folder='static')
CORS(app)#enable CORS on all routes
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
DESKTOP_FOLDER = os.path.join(os.path.expanduser("~"), "Desktop")  # Path to the user's desktop
DOWNLOAD_FOLDER = os.path.join(DESKTOP_FOLDER, "Downloaded")

# Ensure the base download folder exists
os.makedirs(DOWNLOAD_FOLDER, exist_ok=True)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

def read_excel_file(file_path):
    """Read data from the Excel file."""
    return pd.read_excel(file_path)

def clean_descriptions(df):
    # Remove specific characters and leading special symbols except those followed by digits
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'[箱\\P#]', '', str(x)))
    # Clean up everything after '*' that does not involve 'KG' or 'g'
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'\*[^Kg]*', '', str(x)))
    # Remove leading numbers followed by a period
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'^\d+\.', '', str(x)))
    # Remove all three-digit numbers
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'\b\d{3}\b', '', str(x)))
    # If there are still numbers formatted as .XX., remove those as well
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'\.\d{2}\.', '', str(x)))
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'^[^\w\d]+', '', str(x)))
    df['Barcode'] = df['Barcode'].apply(lambda x: re.sub(r'-', '', str(x)))
    return df

def translate_text(text, source_lang='zh-cn', target_lang='en'):
    """Translate text from Chinese to English using Google Translate."""
    translator = Translator()
    try:
        return translator.translate(text, src=source_lang, dest=target_lang).text
    except Exception as e:
        print(f"Failed to translate text: {text} with error: {str(e)}")
        return text  # Fallback to original text on failure

def translate_descriptions(df):
    """Apply translation to all descriptions in the dataframe."""
    df['EnglishDescription'] = df['Description'].apply(translate_text)
    return df

def update_quantity(df):
    # Function to extract and multiply the quantities based on multipliers found after asterisks
    def extract_and_multiply_qty(row):
        try:
            # Find all numbers after each '*' symbol
            multipliers = re.findall(r'\*(\d+)', row['Description'])
            if len(multipliers) >= 2:
                # Multiply found numbers
                result = row['Qty'] * int(multipliers[0]) * int(multipliers[1])
            else:
                # If less than two multipliers, use the first one if available
                result = row['Qty'] * int(multipliers[0]) if multipliers else row['Qty']
            return result
        except:
            # Return original Qty if there's an issue in parsing
            return row['Qty']

    # Apply the function to the dataframe
    df['Qty'] = df.apply(extract_and_multiply_qty, axis=1)
    return df

def calculate_single_price(df):
    """Calculate the price per single unit."""
    df['SinglePrice'] = df.apply(lambda row: round(row['ExPrice'] / row['Qty'], 2) if row['Qty'] else row['ExPrice'], axis=1)
    return df

def save_translated_data(df, vendor_name, inv_number):
    """Save the processed data back to an Excel file in a vendor-specific folder on the desktop."""
    vendor_folder = os.path.join(DOWNLOAD_FOLDER, vendor_name)
    os.makedirs(vendor_folder, exist_ok=True)  # Make sure the vendor folder exists

    new_filename = f"{vendor_name}_{inv_number}.xlsx"
    output_path = os.path.join(vendor_folder, new_filename)
    df.to_excel(output_path, index=False)
    return output_path

def get_inv_number_from_filename(filename):
    # This assumes the format "Prefix_INVNumber_SomethingElse.xlsx" and you want "INVNumber"
    parts = filename.split('_')
    if len(parts) > 1:
        return parts[1]  # This should be INV240610111
    return None  # Return None or raise an error if the format is unexpected

@app.route('/upload', methods=['POST'])
def upload_file():
    app.logger.info("Received upload request")
    if 'file' not in request.files:
        app.logger.warning("No file part in request")
        return jsonify({'success': False, 'message': 'No file part'})
    
    file = request.files['file']
    vendor_name = request.form.get('vendor')

    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'No file provided'})

    if not vendor_name:
        return jsonify({'success': False, 'message': 'Vendor name is required'})

    filename = secure_filename(file.filename)
    base_name, _ = os.path.splitext(filename)
    inv_number = base_name.split('_')[0] if '_' in base_name else base_name

    if not inv_number:
        return jsonify({'success': False, 'message': 'Invalid filename format'})

    vendor_folder = os.path.join(DESKTOP_FOLDER, vendor_name)
    os.makedirs(vendor_folder, exist_ok=True)

    new_filename = f"{vendor_name}_{inv_number}.xlsx"
    file_path = os.path.join(vendor_folder, new_filename)

    file.save(file_path)  # Save the uploaded file first

    # Process the file
    try:
        file_path = os.path.join(UPLOAD_FOLDER, filename)
        file.save(file_path)  # Save the uploaded file first

        df = process_file(file_path)  # Assuming process_file reads, processes, and re-saves the file

        processed_file_path = save_translated_data(df, vendor_name, inv_number)

        download_url = f'/downloads/{vendor_name}/{os.path.basename(processed_file_path)}'
        return jsonify({'success': True, 'message': f'File saved as {os.path.basename(processed_file_path)}', 'downloadUrl': download_url})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})


@app.route('/downloads/<vendor_name>/<filename>')
#Updating Downloading function 
#Specify Downloading file path 
def download_file(vendor_name, filename):
    directory = os.path.join(DOWNLOAD_FOLDER, vendor_name)
    return send_from_directory(directory, filename, as_attachment=True)

@app.route('/converter.html')
def converter():
    """Serve the static HTML file."""
    return send_from_directory('static', 'converter.html')

def process_file(file_path):
    """Process the uploaded file by cleaning, translating, and recalculating data."""
    df = read_excel_file(file_path)
    #Update Quantity first
    df = update_quantity(df)
    #Calculates the single Price for each of the Item
    df = calculate_single_price(df)
    #Clean up the description 
    df = clean_descriptions(df)
    #Translate chinese description to English
    df = translate_descriptions(df)
    
    return save_translated_data(df, file_path)

if __name__ == '__main__':
    # Ensure the upload and processed folders exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    # Start the Flask application
    app.run(debug=True)
