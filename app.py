from flask import Flask, render_template, request, send_file
import io
import os
import requests
import time

app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

@app.route('/')
def home():
    return render_template('index.html')

def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name, extra_options=None):
    api_key = os.environ.get("CONVERTHUB_API_KEY", "")
    print("DEBUG: CONVERTHUB_API_KEY =", repr(api_key))

    if not api_key:
        return "कन्वर्ज़न एरर: API key सेट नहीं है।", 500

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

    if extra_options:
        data["options"] = extra_options

    try:
        response = requests.post("https://api.converthub.com/v2/convert", headers=headers, files=files, data=data)
        print("DEBUG: Raw ConvertHub Response =", response.text)

        job = response.json()
        if not job.get("success", False):
            error_msg = job.get("error", {}).get("message", "Unknown error")
            return f"कन्वर्ज़न एरर: ConvertHub ने job शुरू नहीं किया — {error_msg}", 500

        job_id = job.get("job_id")
        print("DEBUG: Job ID =", job_id)

        result = job.get("result", {})
        file_url = result.get("download_url")
        if job.get("status") == "completed" and file_url:
            download_response = requests.get(file_url)
            return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)

        print("DEBUG: First attempt incomplete — retrying silently...")
        time.sleep(5)
        retry_response = requests.post("https://api.converthub.com/v2/convert", headers=headers, files=files, data=data)
        retry_job = retry_response.json()
        retry_url = retry_job.get("result", {}).get("download_url")

        if retry_job.get("status") == "completed" and retry_url:
            download_response = requests.get(retry_url)
            return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)

        if output_format == "xlsx":
            return "कन्वर्ज़न एरर: PDF में टेबल डेटा नहीं मिला या फॉर्मेट सपोर्ट नहीं किया गया।", 500

        return "कन्वर्ज़न एरर: दोबारा कोशिश के बाद भी आउटपुट फाइल नहीं मिली।", 500

    except Exception as e:
        return f"नेटवर्क या API एरर: {str(e)}", 500

# ✅ All Conversion Routes with Fixes

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

@app.route('/pdf-to-jpg', methods=['POST'])
def pdf_to_jpg():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    options = {"quality": 90, "resolution": "300dpi"}
    return convert_file_rest_api(file.stream, file.filename, 'jpg', 'image/jpeg', 'Tranverto_PDF_to_JPG.jpg', options)

@app.route('/image-to-pdf', methods=['POST'])
def image_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png', '.gif')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Image_to_PDF.pdf')

@app.route('/pdf-to-ppt', methods=['POST'])
def pdf_to_ppt():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pptx', 'application/vnd.openxmlformats-officedocument.presentationml.presentation', 'Tranverto_PDF_to_PPT.pptx')

@app.route('/pdf-to-excel', methods=['POST'])
def pdf_to_excel():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Tranverto_PDF_to_Excel.xlsx')

@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.xlsx'):
        return "कृपया एक Excel फाइल सिलेक्ट करें", 400
    options = {"page_size": "A4", "fit_to_page": True}
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_Excel_to_PDF.pdf', options)

@app.route('/pdf-to-png', methods=['POST'])
def pdf_to_png():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    options = {"resolution": "300dpi"}
    return convert_file_rest_api(file.stream, file.filename, 'png', 'image/png', 'Tranverto_PDF_to_PNG.png', options)

@app.route('/jpg-to-pdf', methods=['POST'])
def jpg_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.jpg', '.jpeg', '.png')):
        return "कृपया एक इमेज फाइल सिलेक्ट करें", 400
    return convert_file_rest_api(file.stream, file.filename, 'pdf', 'application/pdf', 'Tranverto_JPG_to_PDF.pdf')

@app.route('/pdf-translate', methods=['POST'])
def pdf_translate():
    return "PDF अनुवाद फ़ीचर अभी निर्माणाधीन है। जल्द ही उपलब्ध होगा।", 501

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
