from flask import Flask, request, jsonify, render_template_string, Response
import requests
import re

app = Flask(__name__)

# 前端介面（保留你喜歡的一鍵貼上與清除功能，並優化了提示文字）
HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X 影片下載器 (終極版)</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #f5f8fa; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
        .input-group { display: flex; gap: 8px; margin: 15px 0; align-items: center; }
        input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; outline: none; }
        .tool-btn { background-color: #657786; color: white; border: none; padding: 12px; border-radius: 8px; font-size: 14px; cursor: pointer; white-space: nowrap; }
        .clear-btn { background-color: #e0245e; }
        .main-btn { background-color: #1DA1F2; color: white; border: none; padding: 15px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; font-weight: bold; }
        #download-area { margin-top: 20px; display: none; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X 影片下載器 <span style="font-size:12px;color:red;">(終極版)</span></h2>
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
            <a id="downloadLink" href="#"><button style="background-color: #17bf63; border:none; color:white; padding:15px; width:100%; border-radius:8px; font-weight:bold; font-size: 16px;">📥 點此儲存至相簿</button></a>
        </div>
    </div>
    <script>
        function clearInput() { document.getElementById('urlInput').value = ''; document.getElementById('status').innerHTML = ''; document.getElementById('download-area').style.display = 'none'; }
        async function pasteText() { try { const text = await navigator.clipboard.readText(); document.getElementById('urlInput').value = text; } catch (err) { alert("請手動貼上連結"); } }
        async function fetchVideo() {
            const url = document.getElementById('urlInput').value;
            const status = document.getElementById('status');
            const btn = document.getElementById('submitBtn');
            if(!url) return;
            
            status.innerHTML = "啟動終極 API 解析中...";
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
                    document.getElementById('videoPlayer').src = data.video_url;
                    document.getElementById('downloadLink').href = `/api/download?url=${encodeURIComponent(data.video_url)}`;
                    document.getElementById('download-area').style.display = "block";
                } else {
                    status.innerHTML = "❌ 解析失敗：" + (data.error || "請檢查連結是否正確");
                    status.style.color = "red";
                }
            } catch (e) { 
                status.innerHTML = "❌ 網路連線錯誤"; 
                status.style.color = "red";
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
    raw_url = data.get('url', '').strip()

    # 1. 精準提取用戶名與貼文 ID
    match = re.search(r'([a-zA-Z0-9_]+)/status/(\d+)', raw_url)
    if not match:
        return jsonify({"error": "這似乎不是有效的 X (推特) 貼文連結"}), 400

    username = match.group(1)
    tweet_id = match.group(2)

    # 2. 調用 VxTwitter 專用 API (無視 X 的防爬蟲機制)
    api_url = f"https://api.vxtwitter.com/{username}/status/{tweet_id}"

    try:
        # 加上基礎標頭防止 API 阻擋
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        res = requests.get(api_url, headers=headers, timeout=15)
        
        if res.status_code == 200:
            json_data = res.json()
            video_url = None

            # 3. 從回傳的 JSON 中精準抓取最高畫質的影片網址
            if 'media_extended' in json_data:
                for media in json_data['media_extended']:
                    if media.get('type') == 'video':
                        video_url = media.get('url')
                        break
            
            # 備用抓取邏輯
            if not video_url and 'mediaURLs' in json_data:
                for url in json_data['mediaURLs']:
                    if '.mp4' in url or '.m3u8' in url:
                        video_url = url
                        break

            if video_url:
                return jsonify({"video_url": video_url})
            else:
                return jsonify({"error": "該貼文中沒有影片，或對方是鎖頭私密帳號。"}), 404
        else:
            return jsonify({"error": "遠端破解伺服器無回應"}), 500

    except Exception as e:
        return jsonify({"error": "請求超時"}), 500

@app.route('/api/download')
def download():
    video_url = request.args.get('url')
    if not video_url: return "Missing URL", 400
    
    # 告訴 Safari 強制下載
    headers = {
        'Content-Disposition': 'attachment; filename="x_video.mp4"',
        'Content-Type': 'video/mp4'
    }
    
    # 加入手機端 User-Agent，確保推特圖片伺服器允許下載
    req_headers = {
        'User-Agent': 'Mozilla/5.0 (iPhone; CPU iPhone OS 16_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/16.0 Mobile/15E148 Safari/604.1'
    }
    
    req = requests.get(video_url, stream=True, headers=req_headers, timeout=30)
    return Response(req.iter_content(chunk_size=4096), headers=headers)
