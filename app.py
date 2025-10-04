from flask import Flask, render_template, request, send_file
import io
import os
import requests 
import time

# --- Global Configuration ---
# सुनिश्चित करें कि CLOUDCONVERT_API_KEY Render environment variables में सेट है।
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")

# Flask App शुरू करें
# IMPORTANT: 'template_folder='templates' सेट किया गया है, यह मानकर कि index.html 'templates' फ़ोल्डर के अंदर है।
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

# Homepage रूट
@app.route('/')
def home():
    """वेबसाइट का मुख्य पेज दिखाता है (templates/index.html)"""
    return render_template('index.html')

# -------------------------
# कन्वर्ज़न फ़ंक्शन (सीधे REST API का उपयोग करके)
# -------------------------

def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name):
    """
    सीधे CloudConvert REST API का उपयोग करके फाइल को कन्वर्ट करने का जेनेरिक फ़ंक्शन।
    यह SDK पर निर्भरता से बचाता है।
    """
    # 0. API URL और Headers
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
    # इनपुट फ़ाइल एक्सटेंशन प्राप्त करें (जैसे 'pdf', 'docx', 'jpg')
    input_file_extension = filename.split('.')[-1]
    job_id = None

    try:
        # 1. Job Creation
        # tasks payload
        payload = {
            'tasks': {
                'upload-file': {
                    'operation': 'import/upload'
                },
                'convert-file': {
                    'operation': 'convert',
                    'input': 'upload-file',
                    'input_format': input_file_extension,
                    'output_format': output_format,
                    'engine': 'office' 
                },
                'download-file': {
                    'operation': 'export/url',
                    'input': 'convert-file'
                }
            }
        }
        
        response = requests.post(API_BASE_URL + 'jobs', headers=HEADERS, json=payload)
        response.raise_for_status() # HTTP errors के लिए
        job_data = response.json()
        job_id = job_data['id']
        
        # Upload task details प्राप्त करें
        upload_task = job_data['tasks'][0]
        upload_task_url = upload_task['result']['form']['url']
        upload_params = upload_task['result']['form']['parameters']

        # 2. File Uploading (Form Data)
        # requests.post को फ़ाइल के बाइट्स भेजें
        files = {'file': (filename, file_bytes, 'application/octet-stream')}
        
        upload_response = requests.post(upload_task_url, data=upload_params, files=files)
        upload_response.raise_for_status()
        
        # 3. Wait for Job Completion (Polling)
        MAX_POLLS = 12
        POLL_INTERVAL = 5 # seconds
        
        for _ in range(MAX_POLLS):
            time.sleep(POLL_INTERVAL)
            status_response = requests.get(API_BASE_URL + f'jobs/{job_id}', headers=HEADERS)
            status_response.raise_for_status()
            job_status = status_response.json()
            
            if job_status['status'] == 'finished':
                break
            if job_status['status'] in ['error', 'cancelled']:
                # Error state को हैंडल करें
                error_task = next((t for t in job_status['tasks'] if t['status'] == 'error'), None)
                error_message = error_task.get('code', 'Unknown Error') if error_task else 'Unknown Job Error'
                return f"कन्वर्ज़न असफल: {error_message}", 500
        else:
            return "कन्वर्ज़न समय पर पूरा नहीं हुआ। (Time Out)", 500

        # 4. Download URL Extraction
        download_task = next(t for t in job_status['tasks'] if t['name'] == 'download-file')
        if not download_task.get('result') or not download_task['result'].get('files'):
            return "कन्वर्ज़न सफल नहीं हुआ: आउटपुट फाइल नहीं मिली।", 500
                
        file_url = download_task['result']['files'][0]['url']
        
        # 5. Result File Download
        download_response = requests.get(file_url)
        download_response.raise_for_status()
        
        # User को फाइल भेजें
        return send_file(
            io.BytesIO(download_response.content),
            as_attachment=True,
            mimetype=mimetype,
            download_name=download_name
        )

    except requests.exceptions.RequestException as e:
        print(f"API Request Error: {e}")
        return f"नेटवर्क या API एरर: {e} (कृपया CloudConvert Dashboard में API Key और Usage जांचें)", 500
    except Exception as e:
        print(f"General Error during conversion: {e}")
        return f"सामान्य एरर: कृपया अपनी API Key या फ़ाइल फ़ॉर्मेट जाँचें।", 500


# PDF से Word कन्वर्ज़न (टूल 1)
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    """PDF को DOCX में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'docx', 
        'application/vnd.openxmlformats-officedocument.wordprocessingml.document', 
        'Tranverto_PDF_to_Word.docx'
    )

# Word से PDF कन्वर्ज़न (टूल 2)
@app.route('/word-to-pdf', methods=['POST'])
def word_to_pdf():
    """DOCX/DOC को PDF में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.docx', '.doc')):
        return " कृपया एक DOCX/DOC फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'pdf', 
        'application/pdf', 
        'Tranverto_Word_to_PDF.pdf'
    )

# PDF से JPG कन्वर्ज़न (टूल 3)
@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    """PDF को JPG में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return " कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'jpg', 
        'image/jpeg', 
        'Tranverto_PDF_to_JPG.jpg'
    )

# JPG से PDF कन्वर्ज़न (टूल 4)
@app.route('/jpg-to-pdf', methods=['POST'])
def jpg_to_pdf():
    """JPG को PDF में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'pdf', 
        'application/pdf', 
        'Tranverto_Image_to_PDF.pdf'
    )


# PDF से PPT कन्वर्ज़न (टूल 5)
@app.route('/pdf-to-ppt', methods=['POST'])
def pdf_to_ppt():
    """PDF को PPTX में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'pptx', 
        'application/vnd.openxmlformats-officedocument.presentationml.presentation', 
        'Tranverto_PDF_to_PPT.pptx'
    )

# PDF से Excel कन्वर्ज़न (टूल 6)
@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    """PDF को XLSX में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'xlsx', 
        'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 
        'Tranverto_PDF_to_Excel.xlsx'
    )

# Excel से PDF कन्वर्ज़न (टूल 7)
@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    """XLSX को PDF में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.xlsx', '.xls')):
        return "कृपया एक Excel फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'pdf', 
        'application/pdf', 
        'Tranverto_Excel_to_PDF.pdf'
    )

# PDF Translate - हम इसे अगले चरण में Gemini API से करेंगे।
@app.route('/pdf-translate', methods=['POST'])
def pdf_translate():
    return "अनुवाद टूल अभी निर्माणाधीन है।", 501

# PDF से Image (टूल 8)
@app.route('/pdf-to-image', methods=['POST'])
def pdf_to_image():
    """PDF को PNG में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'png', 
        'image/png', 
        'Tranverto_PDF_to_Image.png'
    )

# Image to PDF (टूल 9)
@app.route('/image-to-pdf', methods=['POST'])
def image_to_pdf_final():
    """Image को PDF में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    
    return convert_file_rest_api(
        file.stream, 
        file.filename,
        'pdf', 
        'application/pdf', 
        'Tranverto_Image_to_PDF_Final.pdf'
    )


# यह Render पर नहीं चलेगा (क्योंकि हम gunicorn का उपयोग कर रहे हैं)
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
