from flask import Flask, render_template, request, send_file, redirect, url_for, session
import os
from werkzeug.utils import secure_filename
import zipfile
from datetime import datetime

app = Flask(__name__)
app.secret_key = 'your-secret-key-here'  # Change this to a secure secret key

# Configuration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif'}
PASSWORD = 'Egypten2025'

# Ensure upload folder exists
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

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
        return redirect(url_for('index'))
    
    if 'files[]' not in request.files:
        return 'No file part'
    
    files = request.files.getlist('files[]')
    for file in files:
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            # Add timestamp to filename to prevent overwrites
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S_')
            filename = timestamp + filename
            file.save(os.path.join(UPLOAD_FOLDER, filename))
    
    return redirect(url_for('index'))

@app.route('/download')
def download_all():
    if 'authenticated' not in session:
        return redirect(url_for('index'))
    
    # Create a zip file containing all photos
    zip_path = os.path.join(UPLOAD_FOLDER, 'all_photos.zip')
    with zipfile.ZipFile(zip_path, 'w') as zipf:
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                if file != 'all_photos.zip':  # Don't include the zip file itself
                    file_path = os.path.join(root, file)
                    zipf.write(file_path, file)
    
    return send_file(zip_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True) 