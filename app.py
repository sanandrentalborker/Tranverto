from flask import Flask, render_template, request, send_file
import io
import os
import requests
import time
import json
import mimetypes
from requests_toolbelt.multipart.encoder import MultipartEncoder

app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')


@app.route('/')
def home():
    return render_template('index.html')


def _guess_mimetype(filename):
    mtype, _ = mimetypes.guess_type(filename)
    return mtype or 'application/octet-stream'


def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name, extra_options=None):
    api_key = os.environ.get("CONVERTHUB_API_KEY", "")
    print("DEBUG: CONVERTHUB_API_KEY =", repr(api_key))

    if not api_key:
        return "कन्वर्ज़न एरर: API key सेट नहीं है।", 500

    file_bytes = file_stream.read()

    # free plan limit in your original code
    if len(file_bytes) > 5 * 1024 * 1024:
        return "फाइल बहुत बड़ी है — फ्री प्लान में 5MB तक की फाइल सपोर्टेड है।", 400

    headers = {"Authorization": f"Bearer {api_key}"}

    # prepare fields for multipart
    file_mime = _guess_mimetype(filename)
    fields = {
        "target_format": output_format,
        # provide filename, content and content-type for the file part
        "file": (filename, file_bytes, file_mime),
    }

    # IMPORTANT: send options as a distinct multipart part with content-type application/json
    if extra_options:
        fields["options"] = ("options", json.dumps(extra_options), "application/json")

    multipart_data = MultipartEncoder(fields=fields)
    headers["Content-Type"] = multipart_data.content_type

    try:
        resp = requests.post(
            "https://api.converthub.com/v2/convert",
            headers=headers,
            data=multipart_data,
            timeout=60,
        )
    except requests.exceptions.RequestException as e:
        print("DEBUG: initial request exception:", e)
        return "नेटवर्क या API एरर: ConvertHub से कनेक्शन नहीं हो पाया।", 500

    print("DEBUG: Raw ConvertHub Response =", resp.text)

    try:
        job = resp.json()
    except Exception as e:
        print("DEBUG: failed to parse JSON from ConvertHub:", e)
        return "कन्वर्ज़न एरर: ConvertHub से अप्रत्याशित उत्तर मिला।", 500

    if not job.get("success", False):
        error_msg = job.get("error", {}).get("message", "Unknown error")
        return f"कन्वर्ज़न एरर: ConvertHub ने job शुरू नहीं किया — {error_msg}", 500

    # If conversion already completed, download file
    if job.get("status") == "completed":
        download_url = job.get("result", {}).get("download_url")
        if download_url:
            download_response = requests.get(download_url)
            return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)

    # If there's a job status link, poll it until completion (preferred over re-post)
    status_link = job.get("links", {}).get("status")
    if status_link:
        max_polls = 10
        poll_interval = 3  # seconds
        for i in range(max_polls):
            try:
                status_resp = requests.get(status_link, headers=headers, timeout=30)
                print(f"DEBUG: status poll {i+1} =>", status_resp.text)
                status_job = status_resp.json()
            except Exception as e:
                print("DEBUG: status poll exception:", e)
                status_job = {}

            if status_job.get("status") == "completed":
                download_url = status_job.get("result", {}).get("download_url")
                if download_url:
                    download_response = requests.get(download_url)
                    return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)
                else:
                    return "कन्वर्ज़न एरर: ConvertHub ने आउटपुट दिया लेकिन डाउनलोड लिंक उपलब्ध नहीं है।", 500

            if status_job.get("status") in ("failed", "error"):
                err = status_job.get("error", {}).get("message", "Unknown worker error")
                return f"कन्वर्ज़न एरर: ConvertHub processing failed — {err}", 500

            time.sleep(poll_interval)

        # timed out waiting for job completion
        return "कन्वर्ज़न एरर: ConvertHub पर जॉब प्रोसेसिंग समय सीमा समाप्त हो गई।", 500

    # Fallback: try one gentle retry (re-post) with a bit delay
    print("DEBUG: No status link — will retry posting once after 15s")
    time.sleep(15)
    try:
        retry_resp = requests.post(
            "https://api.converthub.com/v2/convert",
            headers=headers,
            data=multipart_data,
            timeout=60,
        )
        print("DEBUG: Retry response =", retry_resp.text)
        retry_job = retry_resp.json()
        if retry_job.get("status") == "completed":
            download_url = retry_job.get("result", {}).get("download_url")
            if download_url:
                download_response = requests.get(download_url)
                return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)
    except Exception as e:
        print("DEBUG: retry exception:", e)

    if output_format == "xlsx":
        return "कन्वर्ज़न एरर: PDF में टेबल डेटा नहीं मिला या फॉर्मेट सपोर्ट नहीं किया गया।", 500

    return "कन्वर्ज़न एरर: दोबारा कोशिश के बाद भी आउटपुट फाइल नहीं मिली।", 500


# ✅ All Conversion Routes

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


@app.route('/pdf-to-image', methods=['POST'])
def pdf_to_image():
    # alias route to avoid 405
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith('.pdf'):
        return "कृपया एक PDF फाइल सिलेक्ट करें", 400
    options = {"quality": 90, "resolution": "300dpi"}
    return convert_file_rest_api(file.stream, file.filename, 'jpg', 'image/jpeg', 'Tranverto_PDF_to_Image.jpg', options)


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
    options = {"table_detection": "aggressive"}
    return convert_file_rest_api(file.stream, file.filename, 'xlsx', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet', 'Tranverto_PDF_to_Excel.xlsx', options)


@app.route('/excel-to-pdf', methods=['POST'])
def excel_to_pdf():
    file = request.files.get('file')
    if not file or not file.filename.lower().endswith(('.xlsx', '.xls')):
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
