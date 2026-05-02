from flask import Flask, request, jsonify, render_template_string, Response
import requests
import re

app = Flask(__name__)

# 前端介面：加入了物理層圖片覆蓋技術，確保 100% 看到封面
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
        
        /* 影片容器與覆蓋封面樣式 */
        #download-area { margin-top: 20px; display: none; position: relative; width: 100%; }
        .video-wrapper { position: relative; width: 100%; border-radius: 10px; overflow: hidden; background: #000; line-height: 0; }
        #videoPlayer { width: 100%; z-index: 1; }
        #customPoster { 
            position: absolute; top: 0; left: 0; width: 100%; height: 100%; 
            object-fit: cover; z-index: 2; pointer-events: none; 
        }
        
        #status { margin-top: 15px; font-size: 14px; color: #657786; font-weight: bold; }
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
            <div class="video-wrapper">
                <img id="customPoster" src="" style="display:none;">
                <video id="videoPlayer" controls playsinline webkit-playsinline onplay="hidePoster()"></video>
            </div>
            <br>
            <a id="downloadLink" href="#"><button style="background-color: #17bf63; border:none; color:white; padding:15px; width:100%; border-radius:8px; font-weight:bold; font-size: 16px;">📥 點此儲存至相簿</button></a>
        </div>
    </div>

    <script>
        function hidePoster() {
            document.getElementById('customPoster').style.display = 'none';
        }

        function clearInput() { 
            document.getElementById('urlInput').value = ''; 
            document.getElementById('status').innerHTML = ''; 
            document.getElementById('download-area').style.display = 'none';
            document.getElementById('customPoster').src = '';
        }

        async function pasteText() { 
            try { 
                const text = await navigator.clipboard.readText(); 
                document.getElementById('urlInput').value = text; 
            } catch (err) { alert("請手動貼上連結"); } 
        }

        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const btn = document.getElementById('submitBtn');
            if(!url) return;
            
            status.innerHTML = "正在獲取影片內容...";
            status.style.color = "#1DA1F2";
            btn.disabled = true;
            
            try {
                const response = await fetch('/api/get_video', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                if(response.ok) {
                    status.innerHTML = "✅ 解析成功！";
                    status.style.color = "#17bf63";
                    
                    const videoPlayer = document.getElementById('videoPlayer');
                    const posterImg = document.getElementById('customPoster');
                    
                    videoPlayer.src = data.video_url;
                    
                    // 強制使用圖片中轉代理，並顯示在最上層
                    if (data.thumbnail_url) {
                        posterImg.src = `/api/proxy_image?url=${encodeURIComponent(data.thumbnail_url)}`;
                        posterImg.style.display = 'block';
                    }
                    
                    document.getElementById('downloadLink').href = `/api/download?url=${encodeURIComponent(data.video_url)}`;
                    document.getElementById('download-area').style.display = "block";
                } else {
                    status.innerHTML = "❌ 解析失敗";
                    status.style.color = "red";
                }
            } catch (e) { status.innerHTML = "❌ 請求超時"; }
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
    raw_url = data.get('url', '').strip()
    match = re.search(r'([a-zA-Z0-9_]+)/status/(\d+)', raw_url)
    if not match: return jsonify({"error": "格式錯誤"}), 400

    api_url = f"https://api.vxtwitter.com/{match.group(1)}/status/{match.group(2)}"
    try:
        # 增加 headers 模擬真實請求
        res = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=10)
        if res.status_code == 200:
            info = res.json()
            video_url, thumb = None, None
            if 'media_extended' in info:
                for m in info['media_extended']:
                    if m.get('type') == 'video':
                        video_url = m.get('url')
                        thumb = m.get('thumbnail_url')
                        break
            return jsonify({"video_url": video_url, "thumbnail_url": thumb})
        return jsonify({"error": "API 無回應"}), 500
    except: return jsonify({"error": "超時"}), 500

@app.route('/api/proxy_image')
def proxy_image():
    img_url = request.args.get('url')
    if not img_url: return "No URL", 400
    headers = {'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15'}
    res = requests.get(img_url, headers=headers, stream=True)
    return Response(res.iter_content(chunk_size=1024), content_type=res.headers.get('Content-Type'))

@app.route('/api/download')
def download():
    video_url = request.args.get('url')
    headers = {'Content-Disposition': 'attachment; filename="x_video.mp4"', 'Content-Type': 'video/mp4'}
    req = requests.get(video_url, stream=True, timeout=30)
    return Response(req.iter_content(chunk_size=4096), headers=headers)
