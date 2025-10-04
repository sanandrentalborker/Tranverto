from flask import Flask, render_template, request, send_file
import io
import os
import requests 
from cloudconvert import Client # <-- FIX: Standard named import पर revert किया गया

# Environment Variables से API Key प्राप्त करें
# Render पर इन्हें Environment Tab में सेट किया गया है
CLOUDCONVERT_API_KEY = os.environ.get("CLOUDCONVERT_API_KEY", "")

# अगर API Key सेट नहीं है, तो एरर लॉग करें
if not CLOUDCONVERT_API_KEY:
    print("WARNING: CLOUDCONVERT_API_KEY environment variable is NOT set. Conversions will fail.")

# CloudConvert SDK को API Key के साथ इनिशियलाइज़ करें
# FIX: 'CloudConvert' के बजाय 'Client' क्लास का उपयोग किया गया।
cloudconvert_api = Client(api_key=CLOUDCONVERT_API_KEY)


# Flask App शुरू करें
# static_url_path='' और static_folder='.' स्टाइलिंग को ठीक करते हैं।
app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')


# Homepage रूट (रास्ता)
@app.route('/')
def home():
    """वेबसाइट का मुख्य पेज दिखाता है (templates/index.html)"""
    return render_template('index.html')

# -------------------------
# कन्वर्ज़न फ़ंक्शन (CloudConvert का उपयोग करके)
# -------------------------

def convert_file_cloudconvert(file_stream, filename, output_format, mimetype, download_name):
    """
    CloudConvert API का उपयोग करके फाइल को कन्वर्ट करने का जेनेरिक फ़ंक्शन।
    यह क्लाउड में एक जॉब बनाता है, फाइल अपलोड करता है, कन्वर्ट करता है, और परिणाम डाउनलोड करता है।
    """
    file_bytes = file_stream.read()
    input_file_extension = filename.split('.')[-1]
    
    try:
        # 1. CloudConvert में एक जॉब बनाएँ
        job = cloudconvert_api.jobs.create(payload={
            'tasks': {
                'upload-file': {
                    'operation': 'import/upload'
                },
                'convert-file': {
                    'operation': 'convert',
                    'input': 'upload-file',
                    'input_format': input_file_extension, # जैसे 'pdf'
                    'output_format': output_format,       # जैसे 'docx'
                    'engine': 'office' # बेहतर डॉक्यूमेंट हैंडलिंग के लिए
                },
                'download-file': {
                    'operation': 'export/url',
                    'input': 'convert-file'
                }
            }
        })

        # 2. Upload Task को ढूँढें और फाइल अपलोड करें
        upload_task = job.tasks.get_by_name('upload-file')
        cloudconvert_api.tasks.upload(upload_task, file_bytes, filename)
        
        # 3. जॉब के पूरा होने का इंतज़ार करें
        job = cloudconvert_api.jobs.wait(job.id)

        # 4. Download URL प्राप्त करें
        download_task = job.tasks.get_by_name('download-file')
        # सुनिश्चित करें कि फाइल मिली है
        if not download_task.result or not download_task.result.get('files'):
             return f"कन्वर्ज़न सफल नहीं हुआ: आउटपुट फाइल नहीं मिली। (शायद फ़ाइल फ़ॉर्मेट समर्थित नहीं है)", 500
             
        file_url = download_task.result['files'][0]['url']
        
        # 5. परिणामी फाइल डाउनलोड करें
        response = requests.get(file_url)
        
        if response.status_code == 200:
            # User को फाइल भेजें
            return send_file(
                io.BytesIO(response.content),
                as_attachment=True,
                mimetype=mimetype,
                download_name=download_name
            )
        else:
            return f"कन्वर्ज़न असफल रहा: फाइल डाउनलोड नहीं हुई (स्थिति कोड: {response.status_code})", 500

    except Exception as e:
        print(f"Error during CloudConvert conversion: {e}")
        # यह एरर आमतौर पर गलत API Key, गलत फ़ॉर्मेट या मुफ़्त लिमिट खत्म होने पर आती है
        return f"कन्वर्ज़न एरर: कृपया अपनी CloudConvert API Key जाँचें या फ़ाइल फ़ॉर्मेट समर्थित नहीं है।", 500


# PDF से Word कन्वर्ज़न (टूल 1)
@app.route('/pdf-to-word', methods=['POST'])
def pdf_to_word():
    """PDF को DOCX में कन्वर्ट करता है।"""
    file = request.files.get('file')
    if not file or file.filename == '' or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
    
    return convert_file_cloudconvert(
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
