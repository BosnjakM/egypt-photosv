from flask import Flask, render_template, request, send_file, redirect, url_for, session, jsonify
import os
from werkzeug.utils import secure_filename
import zipfile
from datetime import datetime
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload, MediaIoBaseDownload
import io
import json

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key
app.config['MAX_CONTENT_LENGTH'] = 1024 * 1024 * 1024  # 1GB max-size

# Configuration
TEMP_FOLDER = '/tmp/uploads'  # Temporary folder for processing
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic', 'heif'}
PASSWORD = 'Egypten2025'

# Ensure temp folder exists
os.makedirs(TEMP_FOLDER, exist_ok=True)

# Google Drive setup
SCOPES = ['https://www.googleapis.com/auth/drive.file']

# Load credentials from environment variable
try:
    creds_dict = json.loads(os.environ.get('GOOGLE_CREDENTIALS', '{}'))
    credentials = service_account.Credentials.from_service_account_info(creds_dict, scopes=SCOPES)
    drive_service = build('drive', 'v3', credentials=credentials)
    FOLDER_ID = os.environ.get('GOOGLE_DRIVE_FOLDER_ID', '')
except Exception as e:
    print(f"Error setting up Google Drive: {e}")
    drive_service = None
    FOLDER_ID = None

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def upload_to_drive(file_path, filename):
    """Upload a file to Google Drive and return the file ID"""
    try:
        file_metadata = {
            'name': filename,
            'parents': [FOLDER_ID]
        }
        media = MediaFileUpload(file_path, resumable=True)
        file = drive_service.files().create(
            body=file_metadata,
            media_body=media,
            fields='id'
        ).execute()
        return file.get('id')
    except Exception as e:
        print(f"Error uploading to Drive: {e}")
        return None

def download_from_drive(file_id):
    """Download a file from Google Drive"""
    try:
        request = drive_service.files().get_media(fileId=file_id)
        file = io.BytesIO()
        downloader = MediaIoBaseDownload(file, request)
        done = False
        while done is False:
            status, done = downloader.next_chunk()
        return file
    except Exception as e:
        print(f"Error downloading from Drive: {e}")
        return None

@app.route('/')
def index():
    if 'authenticated' not in session:
        return render_template('login.html')
    return render_template('index.html')

@app.route('/login', methods=['POST'])
def login():
    if request.form['password'] == PASSWORD:
        session['authenticated'] = True
        return redirect(url_for('index'))
    return render_template('login.html', error='Incorrect password')

@app.route('/logout')
def logout():
    session.pop('authenticated', None)
    return redirect(url_for('index'))

@app.route('/upload', methods=['POST'])
def upload_file():
    if 'authenticated' not in session:
        return jsonify({'error': 'Not authenticated'}), 401
    
    if not drive_service:
        return jsonify({'error': 'Google Drive service not available'}), 500
    
    if 'files[]' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    files = request.files.getlist('files[]')
    uploaded_files = []
    errors = []
    
    for file in files:
        if file and allowed_file(file.filename):
            try:
                filename = secure_filename(file.filename)
                timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
                filename = timestamp + filename
                temp_path = os.path.join(TEMP_FOLDER, filename)
                
                # Save temporarily
                file.save(temp_path)
                
                # Upload to Google Drive
                file_id = upload_to_drive(temp_path, filename)
                if file_id:
                    uploaded_files.append({'name': filename, 'id': file_id})
                else:
                    errors.append(f"Failed to upload {filename} to Google Drive")
                
                # Clean up temp file
                os.remove(temp_path)
            except Exception as e:
                errors.append(f"Error uploading {file.filename}: {str(e)}")
        else:
            errors.append(f"Invalid file type for {file.filename}")
    
    if errors:
        return jsonify({
            'success': False,
            'errors': errors,
            'uploaded': uploaded_files
        }), 400
    
    return jsonify({
        'success': True,
        'files': uploaded_files
    })

@app.route('/download')
def download_all():
    if 'authenticated' not in session:
        return redirect(url_for('index'))
    
    if not drive_service:
        return jsonify({'error': 'Google Drive service not available'}), 500
    
    try:
        # Get all files in the folder
        results = drive_service.files().list(
            q=f"'{FOLDER_ID}' in parents",
            pageSize=1000,
            fields="files(id, name)"
        ).execute()
        files = results.get('files', [])
        
        # Create a zip file
        zip_buffer = io.BytesIO()
        with zipfile.ZipFile(zip_buffer, 'w') as zip_file:
            for file in files:
                file_content = download_from_drive(file['id'])
                if file_content:
                    zip_file.writestr(file['name'], file_content.getvalue())
        
        zip_buffer.seek(0)
        return send_file(
            zip_buffer,
            mimetype='application/zip',
            as_attachment=True,
            download_name='all_photos.zip'
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# For Vercel, we need to expose the app
app.debug = True

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5003, debug=True) 