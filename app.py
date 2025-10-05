from flask import Flask, render_template, request, send_file
import io
import os
import requests

# Flask App Setup
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

# Homepage Route
@app.route('/')
def home():
    return render_template('index.html')

# ConvertHub API Logic
def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name):
    api_key = os.environ.get("CONVERTHUB_API_KEY", "")
    if not api_key:
        return "कन्वर्ज़न एरर: CONVERTHUB_API_KEY environment variable सेट नहीं है।", 500

    file_bytes = file_stream.read()
    headers = {
        "Authorization": f"Bearer {api_key}"
    }
    files = {
        "file": (filename, file_bytes)
    }
    data = {
        "target_format": output_format
    }

    try:
        response = requests.post("https://api.converthub.com/v1/convert", headers=headers, files=files, data=data)
        if response.status_code != 200:
            return f"कन्वर्ज़न एरर: {response.text}", 500

        result = response.json()
        download_url = result.get("file_url")
        if not download_url:
            return "कन्वर्ज़न सफल नहीं हुआ: आउटपुट फाइल नहीं मिली।", 500

        download_response = requests.get(download_url)
        return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)

    except Exception as e:
        return f"नेटवर्क या API एरर: {str(e)}", 500

# Conversion Routes
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Tranverto_PDF_to_Word.docx')

@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.docx', '.doc')):
        return "कृपया एक Word फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Word_to_PDF.pdf')

@app.route('/jpg-to-pdf', methods=['POST'])
def jpg_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Image_to_PDF.pdf')

@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'jpg', 'image/jpeg', 'Tranverto_PDF_to_JPG.jpg')

# Gunicorn Compatibility
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
