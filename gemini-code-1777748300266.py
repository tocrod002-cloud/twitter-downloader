from flask import Flask, request, jsonify, render_template_string
import yt_dlp
import os

app = Flask(__name__)

# 手機版自適應的網頁前端程式碼
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X 影片下載器</title>
    <style>
        body { font-family: 'Arial', sans-serif; background-color: #f5f8fa; margin: 0; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        h2 { color: #1DA1F2; }
        .container { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
        input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; }
        button { background-color: #1DA1F2; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; }
        button:disabled { background-color: #aab8c2; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; }
        #download-area { margin-top: 20px; display: none; }
        .dl-btn { background-color: #17bf63; margin-top: 10px; text-decoration: none; display: inline-block; }
    </style>
</head>
<body>
    <div class="container">
        <h2>X (推特) 影片下載器</h2>
        <p>貼上貼文連結，獲取原畫質影片</p>
        <input type="text" id="urlInput" placeholder="例如: https://x.com/...">
        <button id="submitBtn" onclick="fetchVideo()">獲取影片</button>
        <div id="status"></div>
        <div id="download-area">
            <video id="videoPlayer" controls style="width: 100%; border-radius: 10px;"></video>
            <a id="downloadLink" class="dl-btn" href="#" target="_blank" download="twitter_video.mp4"><button style="background-color: #17bf63;">點此下載 / 儲存影片</button></a>
        </div>
    </div>

    <script>
        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const btn = document.getElementById('submitBtn');
            const dlArea = document.getElementById('download-area');
            const videoPlayer = document.getElementById('videoPlayer');
            const downloadLink = document.getElementById('downloadLink');

            if(!url) { alert("請先貼上連結！"); return; }

            status.innerHTML = "正在解析最高畫質影片，請稍候...";
            btn.disabled = true;
            dlArea.style.display = "none";

            try {
                const response = await fetch('/api/get_video', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();

                if(response.ok) {
                    status.innerHTML = "解析成功！";
                    videoPlayer.src = data.video_url;
                    downloadLink.href = data.video_url;
                    dlArea.style.display = "block";
                } else {
                    status.innerHTML = "<span style='color:red;'>錯誤: " + data.error + "</span>";
                }
            } catch (e) {
                status.innerHTML = "<span style='color:red;'>網路錯誤，請重試。</span>";
            }
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
    url = data.get('url')
    if not url:
        return jsonify({"error": "請提供連結"}), 400

    # 設定 yt-dlp 只提取真實的影片直連網址，不下載到伺服器 (節省伺服器空間並加快速度)
    ydl_opts = {
        'format': 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best',
        'quiet': True,
        'no_warnings': True,
    }

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            video_url = info.get('url')
            return jsonify({"video_url": video_url})
    except Exception as e:
        return jsonify({"error": "無法解析該影片，請確認連結是否公開有效。"}), 500

if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port)