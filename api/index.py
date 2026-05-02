from flask import Flask, request, jsonify, render_template_string, Response
import yt_dlp
import requests

app = Flask(__name__)

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
        input { width: 90%; padding: 12px; margin: 10px 0; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; }
        button { background-color: #1DA1F2; color: white; border: none; padding: 12px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; }
        #download-area { margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X 影片下載器</h2>
        <input type="text" id="urlInput" placeholder="貼上連結...">
        <button id="submitBtn" onclick="fetchVideo()">獲取影片</button>
        <div id="status"></div>
        <div id="download-area">
            <video id="videoPlayer" controls style="width: 100%; border-radius: 10px;"></video>
            <br><br>
            <!-- 這裡改為跳轉到我們的代理下載路徑 -->
            <a id="downloadLink" href="#"><button style="background-color: #17bf63; width:100%;">點此下載 (彈出系統提示)</button></a>
        </div>
    </div>
    <script>
        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            if(!url) return;
            status.innerHTML = "解析中...";
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
                    // 指向我們的下載代理，並帶上影片網址
                    document.getElementById('downloadLink').href = `/api/download?url=${encodeURIComponent(data.video_url)}`;
                    document.getElementById('download-area').style.display = "block";
                } else {
                    status.innerHTML = "解析失敗";
                }
            } catch (e) { status.innerHTML = "錯誤"; }
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
    except:
        return jsonify({"error": "failed"}), 500

# 新增這個路徑，專門用來欺騙 Safari 彈出下載框
@app.route('/api/download')
def download():
    video_url = request.args.get('url')
    if not video_url:
        return "Missing URL", 400
    
    # 這裡告訴瀏覽器這是一個要下載的附件，檔名為 x_video.mp4
    headers = {
        'Content-Disposition': 'attachment; filename="x_video.mp4"',
        'Content-Type': 'video/mp4'
    }
    
    # 透過伺服器讀取影片內容並回傳
    req = requests.get(video_url, stream=True)
    return Response(req.iter_content(chunk_size=1024), headers=headers)
