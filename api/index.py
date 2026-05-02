from flask import Flask, request, jsonify, render_template_string, Response
import yt_dlp
import requests

app = Flask(__name__)

# 前端介面保持不變，已優化「貼上」與「清除」功能
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
        .input-group { display: flex; gap: 8px; margin: 15px 0; align-items: center; }
        input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; outline: none; }
        .tool-btn { background-color: #657786; color: white; border: none; padding: 12px; border-radius: 8px; font-size: 14px; cursor: pointer; white-space: nowrap; }
        .clear-btn { background-color: #e0245e; }
        .main-btn { background-color: #1DA1F2; color: white; border: none; padding: 15px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; }
        #download-area { margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X 影片下載器</h2>
        <div class="input-group">
            <input type="text" id="urlInput" placeholder="貼上 X 連結...">
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
        function clearInput() { document.getElementById('urlInput').value = ''; document.getElementById('status').innerHTML = ''; document.getElementById('download-area').style.display = 'none'; }
        async function pasteText() { try { const text = await navigator.clipboard.readText(); document.getElementById('urlInput').value = text; } catch (err) { alert("請手動貼上連結"); } }
        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            if(!url) return;
            status.innerHTML = "正在深度解析中...";
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
                    status.innerHTML = "<span style='color:red;'>解析失敗：X 伺服器拒絕連線，請嘗試更換連結。</span>";
                }
            } catch (e) { status.innerHTML = "網路超時"; }
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
    # 移除網址末尾的查詢參數（如 ?s=46），這有助於提高解析成功率
    clean_url = data.get('url', '').split('?')[0].replace('twitter.com', 'x.com')
    
    ydl_opts = {
        'format': 'best',
        'quiet': True,
        'no_warnings': True,
        # 強制使用最新的瀏覽器標頭
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
        'add_header': [
            'Accept: text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8',
            'Accept-Language: zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Referer: https://x.com/',
        ],
    }
    
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(clean_url, download=False)
            video_url = info.get('url')
            # 某些情況下 yt-dlp 會返回多個格式，確保獲取最直接的一個
            if not video_url and 'formats' in info:
                video_url = info['formats'][-1]['url']
            return jsonify({"video_url": video_url})
    except Exception as e:
        print(f"Detailed Error: {e}")
        return jsonify({"error": "解析失敗"}), 500

@app.route('/api/download')
def download():
    video_url = request.args.get('url')
    if not video_url: return "Missing URL", 400
    headers = {
        'Content-Disposition': 'attachment; filename="x_video.mp4"',
        'Content-Type': 'video/mp4'
    }
    # 使用流式傳輸，確保大型影片也能穩定下載
    req = requests.get(video_url, stream=True, timeout=30)
    return Response(req.iter_content(chunk_size=4096), headers=headers)        
