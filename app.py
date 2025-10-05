from flask import Flask, render_template, request, send_file
import io
import os
import requests
import time

app = Flask(__name__, static_url_path='', static_folder='.', template_folder='templates')

@app.route('/')
def home():
    return render_template('index.html')

def convert_file_rest_api(file_stream, filename, output_format, mimetype, download_name):
    api_key = os.environ.get("CONVERTHUB_API_KEY", "")
    print("DEBUG: CONVERTHUB_API_KEY =", api_key)

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
        # Step 1: Submit file for conversion
        response = requests.post("https://api.converthub.com/v2/convert", headers=headers, files=files, data=data)
        job = response.json()
        print("DEBUG: ConvertHub Response =", job)

        if not job.get("success", False):
            error_msg = job.get("error", {}).get("message", "Unknown error")
            return f"कन्वर्ज़न एरर: ConvertHub ने job शुरू नहीं किया — {error_msg}", 500

        job_id = job.get("job_id")
        print("DEBUG: Job ID =", job_id)

        if not job_id:
            return "कन्वर्ज़न एरर: ConvertHub ने job ID return नहीं किया।", 500

        # Step 2: Poll job status
        for _ in range(12):
            status_response = requests.get(f"https://api.converthub.com/v2/jobs/{job_id}", headers=headers)
            status_data = status_response.json()
            print("DEBUG: Job Status =", status_data)

            if status_data.get("status") == "completed":
                file_url = status_data.get("file_url")
                if not file_url:
                    return "कन्वर्ज़न सफल नहीं हुआ: आउटपुट फाइल नहीं मिली।", 500

                download_response = requests.get(file_url)
                return send_file(io.BytesIO(download_response.content), as_attachment=True, mimetype=mimetype, download_name=download_name)

            elif status_data.get("status") == "failed":
                return "कन्वर्ज़न असफल: ConvertHub ने फाइल को प्रोसेस नहीं किया।", 500

            elif status_data.get("error", {}).get("code") == "JOB_NOT_FOUND":
                return f"कन्वर्ज़न एरर: ConvertHub ने job को नहीं पहचाना। Job ID: {job_id}", 500

            time.sleep(5)

        return "कन्वर्ज़न टाइमआउट: ConvertHub ने समय पर जवाब नहीं दिया।", 500

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

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(debug=True, host='0.0.0.0', port=port)
