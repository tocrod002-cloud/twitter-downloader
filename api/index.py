from flask import Flask, request, jsonify, render_template_string
import yt_dlp
import os

app = Flask(__name__)

# 手機版自適應前端
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X 影片下載器</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f5f8fa; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
        input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; }
        button { background-color: #1DA1F2; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; }
        #download-area { margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X (推特) 影片下載器</h2>
        <input type="text" id="urlInput" placeholder="貼上 X 或 Twitter 連結...">
        <button id="submitBtn" onclick="fetchVideo()">獲取影片</button>
        <div id="status"></div>
        <div id="download-area">
            <video id="videoPlayer" controls style="width: 100%; border-radius: 10px;"></video>
            <br><br>
            <a id="downloadLink" href="#" target="_blank"><button style="background-color: #17bf63;">儲存影片至手機</button></a>
        </div>
    </div>
    <script>
        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const btn = document.getElementById('submitBtn');
            if(!url) { alert("請貼上連結！"); return; }
            status.innerHTML = "解析中，請稍候...";
            btn.disabled = true;
            try {
                const response = await fetch('/api/get_video', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                if(response.ok) {
                    status.innerHTML = "解析成功！";
                    document.getElementById('videoPlayer').src = data.video_url;
                    document.getElementById('downloadLink').href = data.video_url;
                    document.getElementById('download-area').style.display = "block";
                } else {
                    status.innerHTML = "<span style='color:red;'>錯誤: " + data.error + "</span>";
                }
            } catch (e) { status.innerHTML = "網路錯誤"; }
            btn.disabled = false;
        }
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML_PAGE)

@app.route('/api/get_video', methods=['POST'])
def get_video():
    data = request.json
    url = data.get('url', '').replace('twitter.com', 'x.com')
    
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"video_url": info.get('url')})
    except Exception as e:
        return jsonify({"error": "解析失敗，請確認連結是否有效。"}), 500
