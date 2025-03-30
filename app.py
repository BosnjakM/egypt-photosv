from flask import Flask, request, render_template, send_file, redirect, url_for, session, jsonify
import os
from werkzeug.utils import secure_filename
from functools import wraps
import zipfile
import io
import logging
from PIL import Image

app = Flask(__name__)
app.secret_key = os.urandom(24)  # Sicherer Secret Key für Sessions

# Logging konfigurieren
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Konfiguration
UPLOAD_FOLDER = 'uploads'
ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'heic', 'HEIC'}
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50MB

if not os.path.exists(UPLOAD_FOLDER):
    os.makedirs(UPLOAD_FOLDER)

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['MAX_CONTENT_LENGTH'] = 100 * 1024 * 1024  # 100MB max-body-size

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def login_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

@app.route('/')
@login_required
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        password = request.form.get('password')
        if password == os.getenv('PHOTO_PASSWORD', 'test123'):
            session['logged_in'] = True
            return redirect(url_for('index'))
        return render_template('login.html', error=True)
    return render_template('login.html', error=False)

@app.route('/logout')
def logout():
    session.pop('logged_in', None)
    return redirect(url_for('login'))

@app.route('/upload', methods=['POST'])
@login_required
def upload_file():
    if 'files[]' not in request.files:
        return jsonify({'success': False, 'errors': ['Keine Dateien gefunden']}), 400
    
    files = request.files.getlist('files[]')
    if not files:
        return jsonify({'success': False, 'errors': ['Keine Dateien ausgewählt']}), 400

    errors = []
    success_count = 0

    for file in files:
        if file and file.filename:
            if not allowed_file(file.filename):
                errors.append(f'Ungültiges Dateiformat: {file.filename}')
                continue

            try:
                filename = secure_filename(file.filename)
                # Überprüfe Dateigröße
                file.seek(0, os.SEEK_END)
                size = file.tell()
                file.seek(0)
                
                if size > MAX_FILE_SIZE:
                    errors.append(f'Datei zu groß: {filename}')
                    continue

                # Speichere die Datei
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file.save(filepath)
                
                # Versuche das Bild zu öffnen um sicherzustellen, dass es valide ist
                try:
                    with Image.open(filepath) as img:
                        img.verify()
                    success_count += 1
                except Exception as e:
                    os.remove(filepath)  # Lösche die ungültige Datei
                    errors.append(f'Ungültiges Bildformat: {filename}')
                    logger.error(f'Fehler beim Validieren von {filename}: {str(e)}')

            except Exception as e:
                errors.append(f'Fehler beim Hochladen: {filename}')
                logger.error(f'Fehler beim Hochladen von {filename}: {str(e)}')

    response = {
        'success': len(errors) == 0,
        'uploaded': success_count,
        'errors': errors if errors else None
    }
    
    return jsonify(response)

@app.route('/download_all')
@login_required
def download_all():
    if not os.path.exists(UPLOAD_FOLDER):
        return "Keine Fotos vorhanden", 404

    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zf:
        for root, dirs, files in os.walk(UPLOAD_FOLDER):
            for file in files:
                if allowed_file(file):
                    file_path = os.path.join(root, file)
                    arcname = os.path.relpath(file_path, UPLOAD_FOLDER)
                    try:
                        zf.write(file_path, arcname)
                    except Exception as e:
                        logger.error(f'Fehler beim Hinzufügen von {file} zum ZIP: {str(e)}')

    memory_file.seek(0)
    return send_file(
        memory_file,
        mimetype='application/zip',
        as_attachment=True,
        download_name='familienfotos.zip'
    )

if __name__ == '__main__':
    app.run(debug=True, host='0.0.0.0') 