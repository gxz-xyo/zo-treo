from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading
import json
import time
import requests
import websocket
import os
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = "za_tools_secret_key_v9_bat_tu_cua_dangkhoi"

os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== CẤU HÌNH DATABASE MONGODB ==================
MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    saved_profiles_collection = db["saved_profiles"] # Bảng mới lưu cấu hình tĩnh
    client.server_info()
    print("✅ MongoDB OK! Đã kích hoạt Za Tools V9 - Dashboard Mode.")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}

# ================== CẤU HÌNH API DISCORD OAUTH2 ==================
DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url():
    return "https://zo-treo.onrender.com"

# ================== HÀM XỬ LÝ LƯU TRỮ ==================
def load_storage(username):
    try:
        data = {}
        for doc in accounts_collection.find({"owner": username}):
            data[doc["bot_key"]] = {
                'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'],
                'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True),
                'video': doc.get('video', False), 'stream': doc.get('stream', False)
            }
        return data
    except: return {}

def get_saved_profiles(username):
    try:
        return list(saved_profiles_collection.find({"owner": username}))
    except: return []

# ================== GIAO DIỆN HỆ THỐNG ĐĂNG NHẬP ==================
HTML_AUTH = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Za Tools - Đăng Nhập</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: '-apple-system', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0b0c10; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; color: #c5a059; }
        .container { max-width: 400px; width: 100%; background: #1f2833; border-radius: 16px; padding: 35px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #2f3e46; }
        .logo { color: #66fcf1; font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 8px; }
        .sub { text-align: center; color: #85929e; font-size: 13px; margin-bottom: 25px; }
        .input-group { margin-bottom: 16px; }
        .input-group label { display: block; color: #45f3ff; font-size: 11px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; }
        .input-group input { width: 100%; padding: 12px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #fff; font-size: 14px; outline: none; transition: 0.3s; }
        .input-group input:focus { border-color: #66fcf1; }
        .btn-primary { width: 100%; padding: 14px; background: linear-gradient(135deg, #1f4068, #162447); border: 1px solid #45f3ff; border-radius: 8px; color: #66fcf1; font-weight: 700; font-size: 14px; cursor: pointer; transition: 0.3s; }
        .btn-primary:hover { background: #66fcf1; color: #0b0c10; }
        .divider { display: flex; align-items: center; text-align: center; color: #566573; font-size: 11px; margin: 20px 0; font-weight: 600; text-transform: uppercase; }
        .divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #2f3e46; }
        .btn-oauth { width: 100%; padding: 12px; border: none; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; display: flex; justify-content: center; gap: 8px; text-decoration: none; background: #5865F2; color: #fff; }
        .switch-link { text-align: center; margin-top: 20px; font-size: 13px; color: #85929e; }
        .switch-link a { color: #66fcf1; text-decoration: none; font-weight: 600; }
        .msg { padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 500; }
        .error { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #e74c3c; }
        .success { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Za Tools</div>
        <div class="sub">Hệ thống phân tách tài khoản treo voice thông minh</div>
        {% if error %}<div class="msg error">❌ {{ error }}</div>{% endif %}
        {% if success %}<div class="msg success">✅ {{ success }}</div>{% endif %}

        <form method="POST" action="{{ '/login' if mode == 'login' else '/register' }}">
            <div class="input-group">
                <label>Tên tài khoản</label>
                <input type="text" name="username" required>
            </div>
            <div class="input-group">
                <label>Mật khẩu</label>
                <input type="password" name="password" required>
            </div>
            <button type="submit" class="btn-primary">{{ 'ĐĂNG NHẬP' if mode == 'login' else 'ĐĂNG KÝ TÀI KHOẢN' }}</button>
        </form>

        <div class="divider">Hoặc kết nối nhanh</div>
        <a href="/login/discord" class="btn-oauth">🎮 Đăng nhập tự động bằng Discord</a>

        <div class="switch-link">
            {% if mode == 'login' %}
                Chưa có tài khoản? <a href="/register">Đăng ký ngay</a>
            {% else %}
                Đã có tài khoản? <a href="/login">Đăng nhập</a>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD ĐA TAB (SPA) ==================
HTML_MAIN = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Za Tools - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: '-apple-system', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0b0c10; color: #fff; overflow-x: hidden; }
        
        /* Navbar & Sidebar */
        .navbar { background: #151a21; padding: 15px 20px; display: flex; align-items: center; border-bottom: 1px solid #2f3e46; position: sticky; top: 0; z-index: 100; }
        .menu-btn { background: none; border: none; color: #66fcf1; font-size: 24px; cursor: pointer; margin-right: 15px; }
        .logo { color: #66fcf1; font-size: 20px; font-weight: 800; }
        
        .sidebar { position: fixed; left: -250px; top: 0; width: 250px; height: 100%; background: #1f2833; box-shadow: 2px 0 10px rgba(0,0,0,0.5); transition: 0.3s; z-index: 1000; padding-top: 60px; border-right: 1px solid #2f3e46; }
        .sidebar.active { left: 0; }
        .close-btn { position: absolute; right: 15px; top: 15px; color: #ff4c4c; font-size: 24px; cursor: pointer; background: none; border: none; }
        .sidebar a { display: block; padding: 15px 25px; color: #85929e; text-decoration: none; font-size: 15px; font-weight: 600; transition: 0.2s; border-left: 3px solid transparent; }
        .sidebar a:hover, .sidebar a.active-link { color: #66fcf1; background: rgba(102,252,241,0.05); border-left: 3px solid #66fcf1; }
        .sidebar .logout { color: #e74c3c; margin-top: 20px; border-top: 1px solid #2f3e46; }
        .user-tag { text-align: center; color: #c5a059; font-size: 13px; margin-bottom: 20px; }

        /* Bố cục chính */
        .container { max-width: 500px; margin: 20px auto; padding: 0 15px; }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }

        /* Card & UI Components */
        .card { background: #151a21; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #2f3e46; }
        .card-title { color: #85929e; font-size: 11px; text-transform: uppercase; font-weight: 700; margin-bottom: 15px; letter-spacing: 1px; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; color: #66fcf1; font-size: 11px; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; }
        .input-group input { width: 100%; padding: 12px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #fff; font-size: 14px; outline: none; }
        .input-group input:focus { border-color: #66fcf1; }
        
        .options { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
        .options label { color: #85929e; font-size: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; background: #0b0c10; padding: 8px 12px; border-radius: 6px; border: 1px solid #2f3e46; }
        .options input[type="checkbox"] { accent-color: #66fcf1; width: 15px; height: 15px; }
        
        .btn-flex { display: flex; gap: 10px; }
        .btn { flex: 1; padding: 14px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; border: none; transition: 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #1f4068, #162447); border: 1px solid #66fcf1; color: #66fcf1; }
        .btn-primary:hover { background: #66fcf1; color: #0b0c10; }
        .btn-success { background: rgba(46, 204, 113, 0.1); border: 1px solid #2ecc71; color: #2ecc71; }
        .btn-success:hover { background: #2ecc71; color: #000; }
        .btn-danger { padding: 8px 14px; background: rgba(231, 76, 60, 0.1); border: 1px solid #e74c3c; border-radius: 6px; color: #e74c3c; font-size: 12px; cursor: pointer; }
        
        /* Items & Logs */
        .account-card { background: #0b0c10; border-radius: 8px; padding: 14px; margin: 10px 0; border: 1px solid #2f3e46; display: flex; justify-content: space-between; align-items: center; }
        .account-card .name { font-weight: 700; color: #fff; font-size: 14px; margin-bottom: 4px;}
        .log-box { background: #0b0c10; border-radius: 8px; padding: 12px; max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #39ff14; border: 1px solid #2f3e46; margin-bottom: 12px; white-space: pre-wrap; }
        
        .msg { padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 500; }
        .msg.success { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; }
        .msg.error { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #e74c3c; }

        /* Overlay */
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 900; display: none; }
        .overlay.active { display: block; }
    </style>
</head>
<body>

    <nav class="navbar">
        <button class="menu-btn" onclick="toggleSidebar()">☰</button>
        <div class="logo">Za Tools</div>
    </nav>

    <div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

    <div class="sidebar" id="sidebar">
        <button class="close-btn" onclick="toggleSidebar()">×</button>
        <div class="user-tag">Admin: @{{ current_user }}</div>
        <a href="#" class="nav-link active-link" onclick="switchTab('treo', this)">🎤 Treo Voice</a>
        <a href="#" class="nav-link" onclick="switchTab('saved', this)">💾 Tài khoản đã lưu</a>
        <a href="#" class="nav-link" onclick="switchTab('tools', this)">🛠️ Tools tiện ích</a>
        <a href="/logout" class="logout">🚪 Đăng xuất</a>
    </div>

    <div class="container">
        
        {% if flash_msg %}
            <div class="msg {{ flash_type }}">{{ flash_msg }}</div>
        {% endif %}

        <div id="tab-treo" class="tab-content active">
            <form method="POST">
                <div class="card">
                    <div class="card-title">Thiết lập kết nối</div>
                    <div class="input-group">
                        <label>Tên Cấu Hình Lại (Nếu muốn Lưu)</label>
                        <input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp (Không bắt buộc nếu chỉ chạy)">
                    </div>
                    <div class="input-group">
                        <label>Discord Token</label>
                        <input type="text" name="token" placeholder="Nhập Token" required autocomplete="off">
                    </div>
                    <div class="input-group">
                        <label>ID Máy chủ (Server ID)</label>
                        <input type="text" name="guild_id" required>
                    </div>
                    <div class="input-group">
                        <label>ID Kênh Voice (Channel ID)</label>
                        <input type="text" name="channel_id" required>
                    </div>
                    <div class="options">
                        <label><input type="checkbox" name="mute" checked> Mute</label>
                        <label><input type="checkbox" name="deaf" checked> Deaf</label>
                        <label><input type="checkbox" name="video"> Video</label>
                        <label><input type="checkbox" name="stream"> Stream</label>
                    </div>
                    <div class="btn-flex">
                        <button type="submit" formaction="/start" class="btn btn-primary">🚀 CHẠY NGAY</button>
                        <button type="submit" formaction="/save_profile" class="btn btn-success">💾 LƯU CẤU HÌNH</button>
                    </div>
                </div>
            </form>

            <div class="card">
                <div class="card-title">Đang chạy ngầm</div>
                {% for key, bot in bot_items %}
                <div class="account-card">
                    <div>
                        <div class="name">{{ bot.get('display_name', 'Đang kết nối...') }}</div>
                        <div style="font-size:11px; color:#2ecc71;">Treo vĩnh cửu • Trực tuyến</div>
                    </div>
                    <form method="POST" action="/stop" style="display:inline;">
                        <input type="hidden" name="bot_key" value="{{ key }}">
                        <button type="submit" class="btn-danger">Dừng</button>
                    </form>
                </div>
                {% endfor %}
                {% if not bot_items %}<div style="font-size:12px; color:#85929e; text-align:center;">Chưa có luồng nào hoạt động</div>{% endif %}
            </div>
            
            <div class="card">
                <div class="card-title">Nhật ký hệ thống</div>
                <div class="log-box">{{ log|join('\\n') if log else 'Hệ thống đang chờ lệnh...' }}</div>
                <form method="POST" action="/refresh"><input type="hidden" name="tab" value="treo"><button type="submit" class="btn btn-primary" style="width:100%; padding:10px;">LÀM MỚI</button></form>
            </div>
        </div>

        <div id="tab-saved" class="tab-content">
            <div class="card">
                <div class="card-title">Kho dữ liệu cá nhân</div>
                {% for profile in saved_profiles %}
                <div class="account-card">
                    <div>
                        <div class="name">{{ profile.profile_name }}</div>
                        <div style="font-size:11px; color:#85929e;">Server: {{ profile.guild_id }}</div>
                    </div>
                    <div style="display:flex; gap:5px;">
                        <form method="POST" action="/start_saved">
                            <input type="hidden" name="profile_id" value="{{ profile._id }}">
                            <button type="submit" class="btn-success" style="padding:6px 10px; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">▶️ Chạy</button>
                        </form>
                        <form method="POST" action="/delete_profile">
                            <input type="hidden" name="profile_id" value="{{ profile._id }}">
                            <button type="submit" class="btn-danger" style="padding:6px 10px; border:none;">🗑️</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
                {% if not saved_profiles %}
                <div style="text-align:center; font-size:13px; color:#85929e; padding: 20px 0;">Bạn chưa lưu cấu hình nào. Hãy sang mục Treo Voice nhập thông tin và bấm Lưu nhé.</div>
                {% endif %}
            </div>
        </div>

        <div id="tab-tools" class="tab-content">
            <div class="card">
                <div class="card-title">Cập nhật thông tin Discord</div>
                <p style="font-size:12px; color:#85929e; margin-bottom:15px;">Dùng Token để thay đổi thông tin hồ sơ Discord của bạn nhanh chóng.</p>
                <form method="POST" action="/update_discord_profile">
                    <div class="input-group">
                        <label>Discord Token (Bắt buộc)</label>
                        <input type="text" name="tool_token" required>
                    </div>
                    <div class="input-group">
                        <label>Tên hiển thị mới (Global Name)</label>
                        <input type="text" name="new_global_name" placeholder="Để trống nếu không đổi">
                    </div>
                    <div class="input-group">
                        <label>Tiểu sử mới (About me)</label>
                        <input type="text" name="new_bio" placeholder="Để trống nếu không đổi">
                    </div>
                    <button type="submit" class="btn btn-primary">🔄 ÁP DỤNG THAY ĐỔI</button>
                </form>
            </div>
        </div>
        
        <div style="text-align:center; margin-top:20px; font-size:12px;">
            <a href="https://t.me/thiendangcuaanh" style="color:#0088cc; font-weight:bold; text-decoration:none;">Hỗ trợ lỗi (Telegram)</a>
            <div style="color:#566573; margin-top:5px;">&copy; 2026 dangkhoi Tools.</div>
        </div>

    </div>

    <script>
        function toggleSidebar() {
            document.getElementById('sidebar').classList.toggle('active');
            document.getElementById('overlay').classList.toggle('active');
        }

        function switchTab(tabId, el) {
            // Chuyển nội dung
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            
            // Đổi màu menu
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active-link'));
            if(el) el.classList.add('active-link');
            
            // Đóng menu nếu ở Mobile
            document.getElementById('sidebar').classList.remove('active');
            document.getElementById('overlay').classList.remove('active');
            
            // Ghi nhớ tab
            localStorage.setItem('za_active_tab', tabId);
        }

        // Tự động load Tab cũ hoặc Tab được server yêu cầu
        window.onload = () => {
            let reqTab = '{{ active_tab }}';
            let tabToLoad = reqTab !== 'None' ? reqTab : (localStorage.getItem('za_active_tab') || 'treo');
            let links = document.querySelectorAll('.nav-link');
            let targetLink = Array.from(links).find(l => l.getAttribute('onclick').includes(tabToLoad));
            switchTab(tabToLoad, targetLink);
        };
        
        setInterval(() => { fetch('/ping'); }, 15000);
    </script>
</body>
</html>
"""

# ================== LUỒNG ĐỒNG BỘ WEBSOCKET DISCORD ==================
def run_bot(bot_key, config, username):
    token = config['token']
    guild_id = config['guild_id']
    channel_id = config['channel_id']
    mute = config.get('mute', True)
    deaf = config.get('deaf', True)
    video = config.get('video', False)
    stream = config.get('stream', False)

    ws = None; last_seq = None; heartbeat_interval = 41250; connected = False

    if username not in user_bots: user_bots[username] = {}
    user_bots[username][bot_key] = {'connected': False, 'log': [], 'running': True, 'display_name': 'Đang kết nối...'}

    def add_log(msg):
        if username in user_bots and bot_key in user_bots[username]:
            user_bots[username][bot_key]['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(user_bots[username][bot_key]['log']) > 60: user_bots[username][bot_key]['log'] = user_bots[username][bot_key]['log'][-60:]

    def update_status(st):
        if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['connected'] = st

    def send_voice_update(ws_client):
        if not ws_client or not ws_client.keep_running: return
        try: ws_client.send(json.dumps({"op": 4, "d": {"guild_id": guild_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf, "self_video": video, "self_stream": stream}}))
        except: pass

    def on_message(ws_client, message):
        nonlocal last_seq, connected, heartbeat_interval
        try: data = json.loads(message)
        except: return
        last_seq = data.get('s', last_seq)
        op = data.get('op')
        t = data.get('t')

        if op == 10:
            heartbeat_interval = data['d']['heartbeat_interval'] / 1000
            ws_client.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "Linux", "browser": "Chrome", "device": "ZaTools_Core"}, "compress": False, "large_threshold": 50}}))
            add_log("📤 Đã gửi gói IDENTIFY")
        elif op == 0:
            if t == 'READY':
                d_name = data['d']['user']['username']
                if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['display_name'] = d_name
                add_log(f"🎯 Trực tuyến: {d_name}")
                send_voice_update(ws_client)
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id and not connected:
                    connected = True; update_status(True); add_log("✅ Kết nối phòng thoại thành công!")
                elif d.get('channel_id') is None and connected:
                    connected = False; update_status(False); add_log("⚠️ Bị rời phòng! Đang tiến hành kết nối lại...")
                    send_voice_update(ws_client)
        elif op == 9: ws_client.close()

    def on_close(ws_client, code, msg):
        nonlocal connected
        if connected: connected = False; update_status(False)
        add_log("🔌 Kết nối đóng ngắt. Thử lại sau 5s...")
        time.sleep(5)
        if username in user_bots and bot_key in user_bots[username] and user_bots[username][bot_key]['running']: start_ws()

    def on_error(ws_client, error):
        if "Connection closed" not in str(error): add_log(f"💥 Lỗi: {error}")

    def heartbeat_loop():
        while username in user_bots and bot_key in user_bots[username] and user_bots[username][bot_key]['running']:
            time.sleep(heartbeat_interval)
            if ws and ws.keep_running:
                try: ws.send(json.dumps({"op": 1, "d": last_seq}))
                except: pass

    def keep_alive_loop():
        while username in user_bots and bot_key in user_bots[username] and user_bots[username][bot_key]['running']:
            time.sleep(25)
            if ws and ws.keep_running and connected: send_voice_update(ws)

    def start_ws():
        nonlocal ws
        if username not in user_bots or bot_key not in user_bots[username] or not user_bots[username][bot_key]['running']: return
        try: gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except: time.sleep(5); start_ws(); return
        ws = websocket.WebSocketApp(gateway + "/?v=9&encoding=json", on_message=on_message, on_error=on_error, on_close=on_close)
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws.run_forever()

    add_log("🚀 Khởi tạo cổng ngầm...")
    start_ws()

# ================== AUTO-BOOTLOADER ==================
def auto_bootloader():
    try:
        for doc in accounts_collection.find():
            username = doc.get("owner"); bot_key = doc.get("bot_key")
            if not username or not bot_key: continue
            config = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True), 'video': doc.get('video', False), 'stream': doc.get('stream', False) }
            if username not in user_bots: user_bots[username] = {}
            if bot_key not in user_bots[username]: threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
    except: pass
auto_bootloader()

# ================== ROUTES HỆ THỐNG ==================
@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        if users_collection.find_one({"username": username}):
            return render_template_string(HTML_AUTH, mode='register', error="Tên đăng nhập đã tồn tại!")
        users_collection.insert_one({"username": username, "password": generate_password_hash(password)})
        return redirect(url_for('login', success="Đăng ký thành công!"))
    return render_template_string(HTML_AUTH, mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    error = request.args.get('error')
    success = request.args.get('success')
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        user = users_collection.find_one({"username": username})
        if user and 'password' in user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        error = "Tài khoản hoặc mật khẩu không đúng!"
    return render_template_string(HTML_AUTH, mode='login', error=error, success=success)

@app.route('/login/discord')
def login_discord():
    discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord", scope=['identify'])
    auth_url, _ = discord.authorization_url(DISCORD_AUTH_URL)
    return redirect(auth_url)

@app.route('/callback/discord')
def callback_discord():
    try:
        auth_res = request.url.replace('http://', 'https://')
        if request.args.get('error'): return redirect(url_for('login', error="Hủy ủy quyền Discord."))
        discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord")
        discord.fetch_token(DISCORD_TOKEN_URL, client_secret=DISCORD_CLIENT_SECRET, authorization_response=auth_res)
        user_data = discord.get('https://discord.com/api/users/@me').json()
        username = f"{user_data['username']}_dc"
        if not users_collection.find_one({"username": username}): users_collection.insert_one({"username": username, "oauth": "discord"})
        session['username'] = username
        return redirect(url_for('index'))
    except Exception as e: return redirect(url_for('login', error=f"Lỗi: {e}"))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    
    storage_data = load_storage(usr)
    for key, config in storage_data.items():
        if usr not in user_bots or key not in user_bots[usr]:
            threading.Thread(target=run_bot, args=(key, config, usr), daemon=True).start()
            
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False) and k in storage_data]
    has_bot = len(active_bots) > 0
    log, status = [], False
    if has_bot:
        log = active_bots[0][1].get('log', [])
        status = active_bots[0][1].get('connected', False)
        
    saved_profiles = get_saved_profiles(usr)
    
    flash_msg = session.pop('flash_msg', None)
    flash_type = session.pop('flash_type', 'success')
    active_tab = request.args.get('tab', 'None')

    return render_template_string(HTML_MAIN, log=log, status=status, has_bot=has_bot, bot_items=active_bots, current_user=usr, saved_profiles=saved_profiles, flash_msg=flash_msg, flash_type=flash_type, active_tab=active_tab)

@app.route('/start', methods=['POST'])
def start_bot_route():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    bot_key = f"{request.form['guild_id'].strip()}_{request.form['channel_id'].strip()}"
    config = {'bot_key': bot_key, 'token': request.form['token'].strip(), 'guild_id': request.form['guild_id'].strip(), 'channel_id': request.form['channel_id'].strip(), 'mute': 'mute' in request.form, 'deaf': 'deaf' in request.form, 'video': 'video' in request.form, 'stream': 'stream' in request.form}
    save_storage_item(bot_key, config, usr)
    if usr not in user_bots: user_bots[usr] = {}
    user_bots[usr][bot_key] = {'connected': False, 'log': ["🚀 Đang thiết lập..."], 'running': True}
    threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/save_profile', methods=['POST'])
def save_profile():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    profile_name = request.form.get('profile_name', '').strip() or f"Cấu hình {int(time.time())}"
    config = {
        'owner': usr, '_id': str(int(time.time())), 'profile_name': profile_name,
        'token': request.form['token'].strip(), 'guild_id': request.form['guild_id'].strip(),
        'channel_id': request.form['channel_id'].strip(), 'mute': 'mute' in request.form,
        'deaf': 'deaf' in request.form, 'video': 'video' in request.form, 'stream': 'stream' in request.form
    }
    saved_profiles_collection.insert_one(config)
    session['flash_msg'] = f"Đã lưu cấu hình: {profile_name}"
    session['flash_type'] = "success"
    return redirect(url_for('index', tab='saved'))

@app.route('/start_saved', methods=['POST'])
def start_saved():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    profile_id = request.form.get('profile_id')
    prof = saved_profiles_collection.find_one({"owner": usr, "_id": profile_id})
    if prof:
        bot_key = f"{prof['guild_id']}_{prof['channel_id']}"
        config = {k:v for k,v in prof.items() if k not in ['_id', 'owner', 'profile_name']}
        config['bot_key'] = bot_key
        save_storage_item(bot_key, config, usr)
        if usr not in user_bots: user_bots[usr] = {}
        user_bots[usr][bot_key] = {'connected': False, 'log': ["🚀 Đang khởi động..."], 'running': True}
        threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/delete_profile', methods=['POST'])
def delete_profile():
    if 'username' not in session: return redirect(url_for('login'))
    saved_profiles_collection.delete_one({"owner": session['username'], "_id": request.form.get('profile_id')})
    return redirect(url_for('index', tab='saved'))

@app.route('/stop', methods=['POST'])
def stop_bot_route():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key, usr)
    if usr in user_bots and bot_key in user_bots[usr]:
        user_bots[usr][bot_key]['running'] = False
        del user_bots[usr][bot_key]
    return redirect(url_for('index', tab='treo'))

@app.route('/update_discord_profile', methods=['POST'])
def update_discord_profile():
    if 'username' not in session: return redirect(url_for('login'))
    token = request.form.get('tool_token').strip()
    g_name = request.form.get('new_global_name').strip()
    bio = request.form.get('new_bio').strip()
    
    payload = {}
    if g_name: payload["global_name"] = g_name
    if bio: payload["bio"] = bio
    
    if not payload:
        session['flash_msg'] = "Vui lòng nhập ít nhất Tên hiển thị hoặc Tiểu sử để đổi!"
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='tools'))

    headers = {"Authorization": token, "Content-Type": "application/json"}
    try:
        r = requests.patch("https://discord.com/api/v9/users/@me", headers=headers, json=payload)
        if r.status_code == 200:
            session['flash_msg'] = "Đã cập nhật thông tin tài khoản Discord thành công!"
            session['flash_type'] = "success"
        else:
            session['flash_msg'] = "Lỗi! Token không hợp lệ hoặc bị chặn."
            session['flash_type'] = "error"
    except:
        session['flash_msg'] = "Lỗi kết nối máy chủ Discord!"
        session['flash_type'] = "error"
    return redirect(url_for('index', tab='tools'))

@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

@app.route('/ping')
def ping(): return "pong"

# ================== TRANG QUẢN TRỊ ẨN CỦA DANGKHOI ==================
@app.route('/admin_dangkhoi')
def admin_dashboard():
    total_users = users_collection.count_documents({})
    total_bots = accounts_collection.count_documents({})
    active_running = sum(1 for usr, bots in user_bots.items() for k, d in bots.items() if d.get('running', False))
    return f"<html><body style='background:#0b0c10; color:#66fcf1; text-align:center; padding:50px; font-family:sans-serif;'><h1>👁️ MẮT THẦN DANGKHOI 👁️</h1><div style='background:#1f2833; padding:20px; border-radius:12px; display:inline-block; border:1px solid #45f3ff;'><p style='color:#fff'>👥 Users: <b style='color:#4cdf8b'>{total_users}</b></p><p style='color:#fff'>🤖 Tokens lưu database: <b style='color:#4cdf8b'>{total_bots}</b></p><p style='color:#fff'>⚡ Luồng chạy RAM: <b style='color:#4cdf8b'>{active_running}</b></p></div></body></html>"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
