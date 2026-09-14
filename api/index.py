from flask import Flask, request, jsonify, render_template_string, Response
import requests
import re
import time

app = Flask(__name__)

HTML_PAGE = """
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>X (Twitter) 高清影片下載器</title>
    <style>
        body { font-family: -apple-system, sans-serif; background-color: #f5f8fa; padding: 20px; display: flex; flex-direction: column; align-items: center; }
        .container { background: white; padding: 20px; border-radius: 15px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); width: 100%; max-width: 400px; text-align: center; }
        .input-group { display: flex; gap: 8px; margin: 15px 0; align-items: center; }
        input { flex: 1; padding: 12px; border: 1px solid #ccc; border-radius: 8px; font-size: 16px; outline: none; }
        .tool-btn { background-color: #657786; color: white; border: none; padding: 12px; border-radius: 8px; font-size: 14px; cursor: pointer; white-space: nowrap; }
        .clear-btn { background-color: #e0245e; }
        .main-btn { background-color: #1DA1F2; color: white; border: none; padding: 15px 20px; border-radius: 8px; font-size: 16px; cursor: pointer; width: 100%; font-weight: bold; margin-top: 10px; }
        #status { margin-top: 15px; font-size: 14px; color: #657786; font-weight: bold; }
        
        #video-list { margin-top: 20px; width: 100%; }
        .video-item { margin-bottom: 30px; position: relative; width: 100%; border-bottom: 1px solid #eee; padding-bottom: 20px; }
        .video-wrapper { position: relative; width: 100%; border-radius: 10px; overflow: hidden; background: #000; line-height: 0; }
        video { width: 100%; z-index: 1; }
        .poster-img { position: absolute; top: 0; left: 0; width: 100%; height: 100%; object-fit: cover; z-index: 2; pointer-events: none; }
        .dl-btn { background-color: #17bf63; border:none; color:white; padding:15px; width:100%; border-radius:8px; font-weight:bold; font-size: 16px; margin-top: 10px; cursor: pointer; text-decoration: none; display: block; text-align: center; box-sizing: border-box; }
    </style>
</head>
<body>
    <div class="container">
        <h2 style="color: #1DA1F2;">X 影片專屬下載器</h2>
        <div class="input-group">
            <input type="text" id="urlInput" placeholder="貼上 X (Twitter) 連結...">
            <button class="tool-btn" onclick="pasteText()">貼上</button>
            <button class="tool-btn clear-btn" onclick="clearInput()">清除</button>
        </div>
        <button class="main-btn" id="submitBtn" onclick="fetchVideo()">解析影片</button>
        <div id="status"></div>
        <div id="video-list"></div>
    </div>

    <script>
        function clearInput() { 
            document.getElementById('urlInput').value = ''; 
            document.getElementById('status').innerHTML = ''; 
            document.getElementById('video-list').innerHTML = ''; 
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
            const videoList = document.getElementById('video-list');
            const btn = document.getElementById('submitBtn');
            if(!url) return;
            
            videoList.innerHTML = "";
            status.innerHTML = "正在切換可用節點解析中...";
            status.style.color = "#1DA1F2";
            btn.disabled = true;
            
            try {
                const response = await fetch('/api/get_video', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ url: url })
                });
                const data = await response.json();
                
                if(response.ok && data.videos && data.videos.length > 0) {
                    status.innerHTML = `✅ 成功解析 ${data.videos.length} 個影片！`;
                    status.style.color = "#17bf63";
                    
                    data.videos.forEach((vid, index) => {
                        const item = document.createElement('div');
                        item.className = 'video-item';
                        item.innerHTML = `
                            <div class="video-wrapper">
                                ${vid.thumbnail ? `<img class="poster-img" id="poster-${index}" src="/api/proxy_image?url=${encodeURIComponent(vid.thumbnail)}">` : ''}
                                <video id="video-${index}" controls playsinline webkit-playsinline 
                                       onplay="if(document.getElementById('poster-${index}')) document.getElementById('poster-${index}').style.display='none'"
                                       src="${vid.url}"></video>
                            </div>
                            <a class="dl-btn" href="/api/download?url=${encodeURIComponent(vid.url)}">📥 下載最高清影片 ${data.videos.length > 1 ? index + 1 : ''}</a>
                        `;
                        videoList.appendChild(item);
                    });
                } else {
                    status.innerHTML = "❌ " + (data.error || "無法解析影片，可能被限制存取或節點全數失效");
                    status.style.color = "red";
                }
            } catch (e) { status.innerHTML = "❌ 請求失敗，伺服器超時"; }
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
    
    # 提取帳號與推文 ID
    match = re.search(r'([a-zA-Z0-9_]+)/status/(\d+)', raw_url)
    if not match: return jsonify({"error": "不支援的連結格式"}), 400

    username = match.group(1)
    tweet_id = match.group(2)
    
    # ==========================================
    # 多節點矩陣：只要有一個活著，就能下載成功
    # ==========================================
    x_api_nodes = [
        f"https://api.vxtwitter.com/{username}/status/{tweet_id}",
        f"https://api.fxtwitter.com/{username}/status/{tweet_id}",
        f"https://api.twxtter.com/{username}/status/{tweet_id}"
    ]
    
    last_error = ""
    for api_url in x_api_nodes:
        try:
            res = requests.get(api_url, headers={'User-Agent': 'Mozilla/5.0'}, timeout=8)
            if res.status_code == 200:
                info = res.json()
                videos = []
                
                # 解析影片資料
                if 'media_extended' in info:
                    for m in info['media_extended']:
                        if m.get('type') == 'video':
                            videos.append({
                                "url": m.get('url'),
                                "thumbnail": m.get('thumbnail_url')
                            })
                # 備用解析邏輯
                if not videos and 'mediaURLs' in info:
                    for url in info['mediaURLs']:
                        if '.mp4' in url:
                            videos.append({"url": url, "thumbnail": None})
                            
                if videos:
                    return jsonify({"videos": videos})
        except Exception as e:
            last_error = str(e)
            continue # 如果這個節點掛了，立刻換下一個

    return jsonify({"error": "目前所有 X 解析伺服器皆無回應，請稍後重試"}), 500

@app.route('/api/proxy_image')
def proxy_image():
    img_url = request.args.get('url')
    if not img_url: return "No URL", 400
    res = requests.get(img_url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True)
    return Response(res.iter_content(chunk_size=1024), content_type=res.headers.get('Content-Type'))

@app.route('/api/download')
def download():
    media_url = request.args.get('url')
    if not media_url: return "Missing URL", 400
        
    filename = f"X_video_{int(time.time())}.mp4"
    headers = {
        'Content-Disposition': f'attachment; filename="{filename}"', 
        'Content-Type': 'video/mp4'
    }
    
    try:
        req = requests.get(media_url, headers={'User-Agent': 'Mozilla/5.0'}, stream=True, timeout=30)
        return Response(req.iter_content(chunk_size=4096), headers=headers)
    except:
        return "Download Failed", 500
