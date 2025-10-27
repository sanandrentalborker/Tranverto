from flask import Flask, render_template, request, send_file, jsonify
import io
import os
import requests
import time
import json
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder
from PyPDF2 import PdfMerger

app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

@app.route('/')
def home():
    return render_template('index.html')

def _guess_mimetype(filename):
    mtype, _ = mimetypes.guess_type(filename)
    return mtype or 'application/octet-stream'

def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name, extra_options=None):
    api_key = os.environ.get("CONVERTHUB_API_KEY", "")
    if not api_key:
        return "Conversion error: API key not set", 500

    file_bytes = file_stream.read()
    if len(file_bytes) > 5 * 1024 * 1024:
        return "File too large — 5MB limit on free plan", 400

    headers = {"Authorization": f"Bearer {api_key}"}
    file_mime = _guess_mimetype(filename)
    fields = {
        "target_format": output_format,
        "file": (filename, file_bytes, file_mime),
    }
    if extra_options:
        fields["options"] = ("options", json.dumps(extra_options), "application/json")

    multipart_data = MultipartEncoder(fields=fields)
    headers["Content-Type"] = multipart_data.content_type

    try:
        resp = requests.post("https://api.converthub.com/v2/convert", headers=headers, data=multipart_data, timeout=60)
        job = resp.json()
    except Exception:
        return "Conversion error: API request failed", 500

    if not job.get("success", False):
        return f"Conversion error: {job.get('error', {}).get('message', 'Unknown')}", 500

    status_link = job.get("links", {}).get("status")
    if status_link:
        for _ in range(10):
            time.sleep(3)
            try:
                status_resp = requests.get(status_link, headers=headers, timeout=30)
                status_job = status_resp.json()
                if status_job.get("status") == "completed":
                    download_url = status_job.get("result", {}).get("download_url")
                    if download_url:
                        download_response = requests.get(download_url)
                        return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)
                elif status_job.get("status") in ("failed", "error"):
                    return f"Conversion failed: {status_job.get('error', {}).get('message', 'Unknown')}", 500
            except Exception:
                continue
        return "Conversion timed out", 500
    return "Conversion error: No status link", 500

# ✅ Conversion Endpoints

@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "Please upload a PDF file", 400
    return convert_file_rest_api(file.stream, file.filename, 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'converted.docx')

@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.docx', '.doc')):
        return "Please upload a Word file", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'converted.pdf')

@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "Please upload a PDF file", 400
    options = {"quality": 90, "resolution": "300dpi"}
    return convert_file_rest_api(file.stream, file.filename, 'jpg', 'image/jpeg', 'converted.jpg', options)

@app.route('/image-to-pdf', methods=['POST'])
def image_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return "Please upload an image file", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'converted.pdf')

# ✅ New: PDF Merge (Self-hosted)
@app.route('/pdf-merge', methods=['POST'])
def pdf_merge():
    files = request.files.getlist('files')
    if not files or len(files) < 2:
        return "Please upload at least two PDF files", 400
    merger = PdfMerger()
    for f in files:
        if f.filename.lower().endswith('.pdf'):
            merger.append(f.stream)
    output = io.BytesIO()
    merger.write(output)
    merger.close()
    output.seek(0)
    return send_file(output, as_attachment=True, download_name='merged.pdf', mimetype='application/pdf')

# 🕒 Coming Soon
@app.route('/pdf-translate', methods=['POST'])
def pdf_translate():
    return "PDF translation feature coming soon", 501

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
