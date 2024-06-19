import os
import pandas as pd
import re
from flask import Flask, request, jsonify, send_from_directory, render_template
from werkzeug.utils import secure_filename
from googletrans import Translator
from flask_cors import CORS  # Import CORS

app = Flask(__name__,static_folder='static')
CORS(app)#enable CORS on all routes
UPLOAD_FOLDER = 'uploads'
PROCESSED_FOLDER = 'processed'
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['PROCESSED_FOLDER'] = PROCESSED_FOLDER

def read_excel_file(file_path):
    """Read data from the Excel file."""
    return pd.read_excel(file_path)

def clean_descriptions(df):
    """Clean up product descriptions to remove unwanted characters and formats."""
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'[箱\\P#]', '', str(x)))
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'\*[^Kg]*', '', str(x)))
    df['Description'] = df['Description'].apply(lambda x: re.sub(r'^[^\w\d]+', '', str(x)))
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
    """Update product quantity based on multipliers found in the descriptions."""
    def extract_and_multiply_qty(row):
        try:
            multipliers = re.findall(r'\*(\d+)', row['Description'])
            result = row['Qty']
            for multiplier in multipliers:
                result *= int(multiplier)
            return result
        except Exception as e:
            print(f"Error processing quantity for row: {row['Description']} with error: {str(e)}")
            return row['Qty']
    df['Qty'] = df.apply(extract_and_multiply_qty, axis=1)
    return df

def calculate_single_price(df):
    """Calculate the price per single unit."""
    df['SinglePrice'] = df.apply(lambda row: round(row['ExPrice'] / row['Qty'], 2) if row['Qty'] else row['ExPrice'], axis=1)
    return df

def save_translated_data(df, file_path):
    """Save the processed data back to an Excel file in the processed folder."""
    output_path = os.path.join(app.config['PROCESSED_FOLDER'], os.path.basename(file_path))
    df.to_excel(output_path, index=False)
    return output_path

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'file' not in request.files:
        print("No file part")
        return jsonify({'success': False, 'message': 'No file part'})

    file = request.files['file']
    if file.filename == '':
        print("No selected file")
        return jsonify({'success': False, 'message': 'No selected file'})

    if file:
        filename = secure_filename(file.filename)
        file_path = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(file_path)
        print(f"File {filename} uploaded successfully")
        response_message = f"File {filename} uploaded successfully."

        # Process the file
        processed_file_path = process_file(file_path)
        print(f"File {filename} processed successfully")
        response_message += f" File {filename} processed successfully."

        return jsonify({'success': True, 'message': response_message, 'downloadUrl': f'/downloads/{os.path.basename(processed_file_path)}'})

    return jsonify({'success': False, 'message': 'File upload failed'})


@app.route('/downloads/<filename>')
def download_file(filename):
    """Serve processed files for download."""
    return send_from_directory(app.config['PROCESSED_FOLDER'], filename)

@app.route('/converter.html')
def converter():
    """Serve the static HTML file."""
    return send_from_directory('static', 'converter.html')

def process_file(file_path):
    """Process the uploaded file by cleaning, translating, and recalculating data."""
    df = read_excel_file(file_path)
    df = clean_descriptions(df)
    df = translate_descriptions(df)
    df = update_quantity(df)
    df = calculate_single_price(df)
    return save_translated_data(df, file_path)

if __name__ == '__main__':
    # Ensure the upload and processed folders exist
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(PROCESSED_FOLDER, exist_ok=True)
    # Start the Flask application
    app.run(debug=True)
