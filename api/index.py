from flask import Flask, request, jsonify, render_template_string, Response
import yt_dlp
import requests

app = Flask(__name__)

# 更新後的 HTML，加入了「貼上」與「清除」按鈕
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X 影片下載器</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #f5f8fa; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
        
        /* 輸入框容器，讓按鈕橫向排列 */
        .input-group { display: flex; gap: 8px; margin: 15px 0; align-items: center; }
        input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; outline: none; }
        
        /* 小按鈕樣式 */
        .tool-btn { background-color: #657786; color: white; border: none; padding: 12px; border-radius: 8px; font-size: 14px; cursor: pointer; white-space: nowrap; transition: 0.2s; }
        .tool-btn:active { opacity: 0.7; }
        .clear-btn { background-color: #e0245e; } /* 清除用紅色 */

        .main-btn { background-color: #1DA1F2; color: white; border: none; padding: 15px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; }
        #download-area { margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X 影片下載器</h2>
        
        <div class="input-group">
            <input type="text" id="urlInput" placeholder="貼上 X 或 Twitter 連結...">
            <button class="tool-btn" onclick="pasteText()">貼上</button>
            <button class="tool-btn clear-btn" onclick="clearInput()">清除</button>
        </div>

        <button class="main-btn" id="submitBtn" onclick="fetchVideo()">獲取影片</button>
        
        <div id="status"></div>
        <div id="download-area">
            <video id="videoPlayer" controls style="width: 100%; border-radius: 10px;"></video>
            <br><br>
            <a id="downloadLink" href="#"><button style="background-color: #17bf63; border:none; color:white; padding:15px; width:100%; border-radius:8px; font-weight:bold;">點此下載 (彈出系統提示)</button></a>
        </div>
    </div>

    <script>
        // 一鍵清除功能
        function clearInput() {
            document.getElementById('urlInput').value = '';
            document.getElementById('status').innerHTML = '';
            document.getElementById('download-area').style.display = 'none';
        }

        // 一鍵貼上功能
        async function pasteText() {
            try {
                const text = await navigator.clipboard.readText();
                document.getElementById('urlInput').value = text;
            } catch (err) {
                alert("瀏覽器不支援或未開啟剪貼簿權限，請手動貼上。");
            }
        }

        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const btn = document.getElementById('submitBtn');
            if(!url) return;
            
            status.innerHTML = "解析中...";
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
                    document.getElementById('downloadLink').href = `/api/download?url=${encodeURIComponent(data.video_url)}`;
                    document.getElementById('download-area').style.display = "block";
                } else {
                    status.innerHTML = "<span style='color:red;'>解析失敗</span>";
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
        'no_warnings': True,
        'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    }
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=False)
            return jsonify({"video_url": info.get('url')})
    except:
        return jsonify({"error": "failed"}), 500

@app.route('/api/download')
def download():
    video_url = request.args.get('url')
    if not video_url: return "Missing URL", 400
    headers = {
        'Content-Disposition': 'attachment; filename="x_video.mp4"',
        'Content-Type': 'video/mp4'
    }
    req = requests.get(video_url, stream=True)
    return Response(req.iter_content(chunk_size=1024), headers=headers)
