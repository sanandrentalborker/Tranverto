from flask import Flask, render_template, request, send_file
import io
import os
import requests
import time

# --- Global Configuration ---
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")
print("DEBUG: CLOUDCONVERT_API_KEY =", CLOUDCONVERT_API_KEY)

# Flask App शुरू करें
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

# Homepage रूट
@app.route('/')
def home():
    if not CLOUDCONVERT_API_KEY:
        return "❌ API Key missing. Please set CLOUDCONVERT_API_KEY in Render environment.", 500
    return render_template('index.html')

# -------------------------
# कन्वर्ज़न फ़ंक्शन
# -------------------------
def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name):
    API_BASE_URL = "https://api.cloudconvert.com/v2/"
    HEADERS = {
        'Authorization': f'Bearer {CLOUDCONVERT_API_KEY}',
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    if not CLOUDCONVERT_API_KEY:
        print("ERROR: CLOUDCONVERT_API_KEY environment variable is NOT set.")
        return "कन्वर्ज़न एरर: CLOUDCONVERT_API_KEY environment variable सेट नहीं है।", 500

    file_bytes = file_stream.read()
    input_file_extension = filename.split('.')[-1]
    job_id = None

    try:
        payload = {
            'tasks': {
                'upload-file': {'operation': 'import/upload'},
                'convert-file': {
                    'operation': 'convert',
                    'input': 'upload-file',
                    'input_format': input_file_extension,
                    'output_format': output_format,
                    'engine': 'office'
                },
                'download-file': {'operation': 'export/url', 'input': 'convert-file'}
            }
        }

        response = requests.post(API_BASE_URL + 'jobs', headers=HEADERS, json=payload)
        response.raise_for_status()
        job_data = response.json()
        job_id = job_data['id']

        upload_task = job_data['tasks'][0]
        upload_task_url = upload_task['result']['form']['url']
        upload_params = upload_task['result']['form']['parameters']
        files = {'file': (filename, file_bytes, 'application/octet-stream')}
        upload_response = requests.post(upload_task_url, data=upload_params, files=files)
        upload_response.raise_for_status()

        for _ in range(12):
            time.sleep(5)
            status_response = requests.get(API_BASE_URL + f'jobs/{job_id}', headers=HEADERS)
            status_response.raise_for_status()
            job_status = status_response.json()

            if job_status['status'] == 'finished':
                break
            if job_status['status'] in ['error', 'cancelled']:
                error_task = next((t for t in job_status['tasks'] if t['status'] == 'error'), None)
                error_message = error_task.get('code', 'Unknown Error') if error_task else 'Unknown Job Error'
                return f"कन्वर्ज़न असफल: {error_message}", 500
        else:
            return "कन्वर्ज़न समय पर पूरा नहीं हुआ। (Time Out)", 500

        download_task = next(t for t in job_status['tasks'] if t['name'] == 'download-file')
        if not download_task.get('result') or not download_task['result'].get('files'):
            return "कन्वर्ज़न सफल नहीं हुआ: आउटपुट फाइल नहीं मिली।", 500

        file_url = download_task['result']['files'][0]['url']
        download_response = requests.get(file_url)
        download_response.raise_for_status()

        return send_file(
            io.BytesIO(download_response.content),
            as_attachment=True,
            mimetype=mimetype,
            download_name=download_name
        )

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return f"नेटवर्क या API एरर: {e}", 500
    except Exception as e:
        print(f"General Error during conversion: {e}")
        return f"सामान्य एरर: कृपया अपनी API Key या फ़ाइल फ़ॉर्मेट जाँचें।", 500

# Conversion Routes
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'docx', 'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 'Tranverto_PDF_to_Word.docx')

@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.docx', '.doc')):
        return " कृपया एक DOCX/DOC फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Word_to_PDF.pdf')

@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return " कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'jpg', 'image/jpeg', 'Tranverto_PDF_to_JPG.jpg')

@app.route('/jpg-to-pdf', methods=['POST'])
def jpg_to_pdf():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Image_to_PDF.pdf')

@app.route('/pdf-to-ppt', methods=['POST'])
def pdf_to_ppt():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'Tranverto_PDF_to_PPT.pptx')

@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Tranverto_PDF_to_Excel.xlsx')

@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.xlsx', '.xls')):
        return "कृपया एक Excel फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Excel_to_PDF.pdf')

@app.route('/pdf-translate', methods=['POST'])
def pdf_translate():
    return "अनुवाद टूल अभी निर्माणाधीन है।", 501

@app.route('/pdf-to-image', methods=['POST'])
def pdf_to_image():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'png', 'image/png', 'Tranverto_PDF_to_Image.png')

@app.route('/image-to-pdf', methods=['POST'])
def image_to_pdf_final():
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Image_to_PDF_Final.pdf')

# Gunicorn के लिए
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
