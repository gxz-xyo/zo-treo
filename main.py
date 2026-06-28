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
# Khóa cố định chống văng session
app.secret_key = "za_tools_secret_key_v7_bat_tu_cua_dangkhoi"

# Cho phép chạy luồng OAuth2 qua HTTP trên Render
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== CẤU HÌNH CƠ SỞ DỮ LIỆU ĐÁM MÂY MONGODB ==================
MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"

try:
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    client.server_info()
    print("✅ Kết nối tới MongoDB Atlas thành công! Đã loại bỏ Google, kích hoạt V8 Clean.")
except Exception as e:
    print(f"💥 Lỗi kết nối dữ liệu: {e}")

user_bots = {}

# ================== CẤU HÌNH KHÓA API DISCORD OAUTH2 ==================
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
    except Exception as e:
        print(f"⚠️ Lỗi đọc cơ sở dữ liệu: {e}")
        return {}

def save_storage_item(bot_key, config, username):
    try:
        config["owner"] = username
        accounts_collection.update_one({"bot_key": bot_key}, {"$set": config}, upsert=True)
    except: pass

def delete_storage_item(bot_key, username):
    try: accounts_collection.delete_one({"bot_key": bot_key, "owner": username})
    except: pass

# ================== GIAO DIỆN HỆ THỐNG GỌN GÀNG TỐI GIẢN ==================
HTML_AUTH = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Za Tools - Hệ Thống Treo Voice</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: '-apple-system', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0b0c10; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; color: #c5a059; }
        .container { max-width: 400px; width: 100%; background: #1f2833; border-radius: 16px; padding: 35px 30px; box-shadow: 0 10px 30px rgba(0,0,0,0.5); border: 1px solid #2f3e46; }
        .logo { color: #66fcf1; font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 8px; letter-spacing: 0.5px; }
        .sub { text-align: center; color: #85929e; font-size: 13px; margin-bottom: 25px; }
        .input-group { margin-bottom: 16px; }
        .input-group label { display: block; color: #45f3ff; font-size: 11px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; }
        .input-group input { width: 100%; padding: 12px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #fff; font-size: 14px; outline: none; transition: all 0.3s ease; }
        .input-group input:focus { border-color: #66fcf1; }
        .btn-primary { width: 100%; padding: 14px; background: linear-gradient(135deg, #1f4068, #162447); border: 1px solid #45f3ff; border-radius: 8px; color: #66fcf1; font-weight: 700; font-size: 14px; cursor: pointer; transition: all 0.3s ease; letter-spacing: 1px; }
        .btn-primary:hover { background: linear-gradient(135deg, #162447, #1f4068); color: #fff; transform: translateY(-1px); }
        .divider { display: flex; align-items: center; text-align: center; color: #566573; font-size: 11px; margin: 20px 0; font-weight: 600; text-transform: uppercase; }
        .divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid #2f3e46; }
        .divider:not(:empty)::before { margin-right: .5em; }
        .divider:not(:empty)::after { margin-left: .5em; }
        .oauth-container { width: 100%; }
        .btn-oauth { width: 100%; padding: 12px; border: none; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; margin-bottom: 12px; text-decoration: none; }
        .btn-discord { background: #5865F2; color: #fff; }
        .btn-discord:hover { background: #4752C4; }
        .switch-link { text-align: center; margin-top: 20px; font-size: 13px; color: #85929e; }
        .switch-link a { color: #66fcf1; text-decoration: none; font-weight: 600; margin-left: 5px; }
        .switch-link a:hover { text-decoration: underline; }
        .error-msg { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #e74c3c; padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 500; }
        .success-msg { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 500; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">Za Tools</div>
        <div class="sub">Hệ thống phân tách tài khoản treo voice thông minh</div>
        
        {% if error %}<div class="error-msg">❌ {{ error }}</div>{% endif %}
        {% if success %}<div class="success-msg">✅ {{ success }}</div>{% endif %}

        <form method="POST" action="{{ '/login' if mode == 'login' else '/register' }}">
            <div class="input-group">
                <label>Tên tài khoản</label>
                <input type="text" name="username" placeholder="Nhập tên đăng nhập của bạn" required autocomplete="off">
            </div>
            <div class="input-group">
                <label>Mật khẩu</label>
                <input type="password" name="password" placeholder="Nhập mật khẩu truy cập" required>
            </div>
            <button type="submit" class="btn-primary">{{ 'ĐĂNG NHẬP HỆ THỐNG' if mode == 'login' else 'ĐĂNG KÝ TÀI KHOẢN MỚI' }}</button>
        </form>

        <div class="divider">Hoặc kết nối nhanh</div>

        <div class="oauth-container">
            <a href="/login/discord" class="btn-oauth btn-discord">🎮 Đăng nhập tự động bằng Discord</a>
        </div>

        <div class="switch-link">
            {% if mode == 'login' %}
                Chưa có tài khoản độc lập? <a href="/register">Đăng ký ngay</a>
            {% else %}
                Đã có tài khoản cá nhân? <a href="/login">Đăng nhập ngay</a>
            {% endif %}
        </div>
    </div>
</body>
</html>
"""

HTML_MAIN = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Za Tools - Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: '-apple-system', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0b0c10; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; color: #fff; }
        .container { max-width: 480px; width: 100%; background: #1f2833; border-radius: 16px; padding: 30px; box-shadow: 0 15px 35px rgba(0,0,0,0.6); border: 1px solid #2f3e46; }
        .top-bar { display: flex; justify-content: space-between; align-items: center; margin-bottom: 25px; padding-bottom: 15px; border-bottom: 1px solid #2f3e46; }
        .logo { color: #66fcf1; font-size: 24px; font-weight: 800; letter-spacing: 0.5px; }
        .btn-logout { color: #e74c3c; text-decoration: none; font-size: 12px; font-weight: 600; background: rgba(231, 76, 60, 0.1); padding: 6px 14px; border-radius: 6px; border: 1px solid #e74c3c; transition: 0.2s; }
        .btn-logout:hover { background: #e74c3c; color: #fff; }
        .user-welcome { font-size: 13px; color: #c5a059; margin-bottom: 20px; font-weight: 500; text-align: center; }
        .user-welcome span { color: #66fcf1; font-weight: bold; }
        .card { background: #151a21; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #2f3e46; }
        .card-title { color: #85929e; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; font-weight: 700; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; color: #66fcf1; font-size: 11px; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; }
        .input-group input { width: 100%; padding: 12px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #fff; font-size: 14px; outline: none; transition: 0.2s; }
        .input-group input:focus { border-color: #66fcf1; }
        .options { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
        .options label { color: #85929e; font-size: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; background: #0b0c10; padding: 8px 12px; border-radius: 6px; border: 1px solid #2f3e46; user-select: none; }
        .options input[type="checkbox"] { accent-color: #66fcf1; width: 15px; height: 15px; }
        .btn-primary { width: 100%; padding: 14px; background: linear-gradient(135deg, #1f4068, #162447); border: 1px solid #66fcf1; border-radius: 8px; color: #66fcf1; font-weight: 700; font-size: 14px; cursor: pointer; transition: 0.2s; letter-spacing: 0.5px; }
        .btn-primary:hover { background: #66fcf1; color: #0b0c10; }
        .btn-danger { padding: 8px 14px; background: rgba(231, 76, 60, 0.1); border: 1px solid #e74c3c; border-radius: 6px; color: #e74c3c; font-weight: 600; font-size: 12px; cursor: pointer; transition: 0.2s; }
        .btn-danger:hover { background: #e74c3c; color: #fff; }
        .btn-refresh { padding: 10px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #66fcf1; font-weight: 600; font-size: 13px; cursor: pointer; width: 100%; transition: 0.2s; }
        .btn-refresh:hover { background: #2f3e46; }
        .status-box { padding: 10px; border-radius: 8px; margin-bottom: 12px; text-align: center; font-weight: 700; font-size: 13px; letter-spacing: 0.5px; }
        .online { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; }
        .offline { background: rgba(149, 165, 166, 0.1); color: #95a5a6; border: 1px solid #95a5a6; }
        .log-box { background: #0b0c10; border-radius: 8px; padding: 12px; max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #39ff14; border: 1px solid #2f3e46; margin-bottom: 12px; white-space: pre-wrap; word-break: break-all; line-height: 1.5; }
        .log-box::-webkit-scrollbar { width: 4px; }
        .log-box::-webkit-scrollbar-thumb { background: #66fcf1; border-radius: 2px; }
        .account-card { background: #0b0c10; border-radius: 8px; padding: 14px; margin: 8px 0; border: 1px solid #2f3e46; display: flex; justify-content: space-between; align-items: center; }
        .account-info .name { font-weight: 700; color: #fff; font-size: 14px; }
        .account-info .status { font-size: 11px; margin-top: 2px; color: #85929e; }
        .status-online { color: #2ecc71; font-weight: bold; }
        .status-offline { color: #e74c3c; font-weight: bold; }
        .contact-area { text-align: center; font-size: 13px; margin: 15px 0 5px; font-weight: 500; }
        .contact-link { color: #0088cc; text-decoration: none; font-weight: bold; transition: 0.2s; }
        .contact-link:hover { text-decoration: underline; color: #00aacc; }
        .footer { text-align: center; color: #566573; font-size: 11px; margin-top: 25px; border-top: 1px solid #2f3e46; padding-top: 15px; letter-spacing: 0.5px; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="top-bar">
            <div class="logo">Za Tools</div>
            <a href="/logout" class="btn-logout">Đăng xuất</a>
        </div>
        <div class="user-welcome">Tài khoản quản lý: <span>@{{ current_user }}</span></div>

        <div id="form-container" class="{{ 'hidden' if has_bot else '' }}">
            <form method="POST" action="/start">
                <div class="card">
                    <div class="card-title">Cấu hình tài khoản treo</div>
                    <div class="input-group">
                        <label>Discord Token</label>
                        <input type="text" name="token" placeholder="Nhập Token Discord cá nhân" required autocomplete="off">
                    </div>
                    <div class="input-group">
                        <label>ID Máy chủ (Server ID)</label>
                        <input type="text" name="guild_id" placeholder="Nhập ID máy chủ" required autocomplete="off">
                    </div>
                    <div class="input-group">
                        <label>ID Kênh Voice (Channel ID)</label>
                        <input type="text" name="channel_id" placeholder="Nhập ID kênh thoại" required autocomplete="off">
                    </div>
                    <div class="options">
                        <label><input type="checkbox" name="mute" checked> Mute</label>
                        <label><input type="checkbox" name="deaf" checked> Deaf</label>
                        <label><input type="checkbox" name="video"> Video</label>
                        <label><input type="checkbox" name="stream"> Stream</label>
                    </div>
                    <button type="submit" class="btn-primary">KÍCH HOẠT TIẾN TRÌNH TREO</button>
                </div>
            </form>
        </div>

        <div id="account-container" class="{{ '' if has_bot else 'hidden' }}">
            <div class="card">
                <div class="card-title">Tài khoản đang chạy ngầm</div>
                {% for key, bot in bot_items %}
                <div class="account-card">
                    <div class="account-info">
                        <div class="name">{{ bot.get('display_name', 'Đang kết nối...') }}</div>
                        <div class="status">
                            Trạng thái: 
                            <span class="{{ 'status-online' if bot.get('connected') else 'status-offline' }}">
                                {{ 'Đang treo vĩnh cửu' if bot.get('connected') else 'Đang thiết lập cổng' }}
                            </span>
                        </div>
                    </div>
                    <div>
                        <form method="POST" action="/stop" style="display:inline;">
                            <input type="hidden" name="bot_key" value="{{ key }}">
                            <button type="submit" class="btn-danger">Dừng lại</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="card">
                <div class="card-title">Nhật ký tiến trình</div>
                <div class="status-box {{ 'online' if status else 'offline' }}">
                    {{ 'HỆ THỐNG HOẠT ĐỘNG ỔN ĐỊNH' if status else 'TIẾN TRÌNH ĐANG ĐỢI KHỞI CHẠY' }}
                </div>
                <div class="log-box">{{ log|join('\\n') if log else 'Đang cập nhật luồng xử lý dữ liệu...' }}</div>
                <form method="POST" action="/refresh">
                    <button type="submit" class="btn-refresh">CẬP NHẬT NHẬT KÝ</button>
                </form>
            </div>
        </div>

        <div class="contact-area">
            <a href="https://t.me/thiendangcuaanh" target="_blank" class="contact-link">👉 Liên hệ nếu tools lỗi</a>
        </div>

        <div class="footer">
            &copy; 2026 Bản quyền thuộc về dangkhoi. All rights reserved.
        </div>
    </div>

    <script>
        setInterval(() => { fetch('/ping').then(() => {}); }, 15000);
        setInterval(() => { location.reload(); }, 20000);
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

    ws = None
    last_seq = None
    heartbeat_interval = 41250
    connected = False

    if username not in user_bots: user_bots[username] = {}
    user_bots[username][bot_key] = {'connected': False, 'log': [], 'running': True, 'display_name': 'Đang kết nối...'}

    def add_log(msg):
        if username in user_bots and bot_key in user_bots[username]:
            user_bots[username][bot_key]['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(user_bots[username][bot_key]['log']) > 60: user_bots[username][bot_key]['log'] = user_bots[username][bot_key]['log'][-60:]

    def update_status(status):
        if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['connected'] = status

    def send_voice_update(ws_client):
        if not ws_client or not ws_client.keep_running: return
        try:
            ws_client.send(json.dumps({"op": 4, "d": {"guild_id": guild_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf, "self_video": video, "self_stream": stream}}))
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
                    connected = True
                    update_status(True)
                    add_log("✅ Kết nối phòng thoại thành công!")
                elif d.get('channel_id') is None and connected:
                    connected = False
                    update_status(False)
                    add_log("⚠️ Bị rời phòng! Đang tiến hành kết nối lại...")
                    send_voice_update(ws_client)
        elif op == 9: ws_client.close()

    def on_close(ws_client, code, msg):
        nonlocal connected
        if connected: connected = False; update_status(False)
        add_log("🔌 Cổng kết nối đóng ngắt. Khôi phục luồng sau 5s...")
        time.sleep(5)
        if username in user_bots and bot_key in user_bots[username] and user_bots[username][bot_key]['running']: start_ws()

    def on_error(ws_client, error):
        if "Connection closed" not in str(error): add_log(f"💥 Lỗi luồng: {error}")

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

    add_log("🚀 Khởi tạo cổng ngầm riêng biệt...")
    start_ws()

# ================== BỘ KHỞI ĐỘNG TỰ ĐỘNG (AUTO-BOOTLOADER) ==================
def auto_bootloader():
    print("🔄 Kích hoạt Bootloader: Khôi phục tiến trình từ Cloud...")
    try:
        for doc in accounts_collection.find():
            username = doc.get("owner")
            bot_key = doc.get("bot_key")
            if not username or not bot_key: continue
            
            config = {
                'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'],
                'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True),
                'video': doc.get('video', False), 'stream': doc.get('stream', False)
            }
            if username not in user_bots: user_bots[username] = {}
            if bot_key not in user_bots[username]:
                threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
        print("✅ Auto-Bootloader hoàn tất!")
    except Exception as e:
        print(f"⚠️ Lỗi Bootloader: {e}")

auto_bootloader()


# ================== ENDPOINTS ĐIỀU HƯỚNG & XÁC THỰC ==================

@app.route('/register', methods=['GET', 'POST'])
def register():
    if 'username' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        if users_collection.find_one({"username": username}):
            return render_template_string(HTML_AUTH, mode='register', error="Tên đăng nhập này đã tồn tại trên hệ thống!")
        hashed_password = generate_password_hash(password)
        users_collection.insert_one({"username": username, "password": hashed_password})
        return redirect(url_for('login', success="Đăng ký tài khoản thành công!"))
    return render_template_string(HTML_AUTH, mode='register')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    error = None
    success = request.args.get('success')
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        password = request.form['password'].strip()
        user = users_collection.find_one({"username": username})
        if user and 'password' in user and check_password_hash(user['password'], password):
            session['username'] = username
            return redirect(url_for('index'))
        error = "Thông tin tài khoản hoặc mật khẩu không chính xác!"
    # Bắt thêm thông báo lỗi từ redirect Discord nếu có
    if not error and request.args.get('error'):
        error = request.args.get('error')
    return render_template_string(HTML_AUTH, mode='login', error=error, success=success)

# --- LUỒNG DISCORD OAUTH2 (FIX ÉP HTTPS) ---
@app.route('/login/discord')
def login_discord():
    discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord", scope=['identify'])
    authorization_url, state = discord.authorization_url(DISCORD_AUTH_URL)
    return redirect(authorization_url)

@app.route('/callback/discord')
def callback_discord():
    try:
        # Bắt buộc ép URL thành HTTPS để thư viện không xóa mất biến `code`
        auth_response = request.url.replace('http://', 'https://')
        
        # Bắt trường hợp người dùng bấm "Hủy" trên trang Discord
        if request.args.get('error'):
            return redirect(url_for('login', error="Bạn đã hủy ủy quyền Discord."))

        discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord")
        discord.fetch_token(DISCORD_TOKEN_URL, client_secret=DISCORD_CLIENT_SECRET, authorization_response=auth_response)
        user_data = discord.get('https://discord.com/api/users/@me').json()
        
        username = f"{user_data['username']}_dc"
        if not users_collection.find_one({"username": username}):
            users_collection.insert_one({"username": username, "oauth": "discord"})
            
        session['username'] = username
        return redirect(url_for('index'))
    except Exception as e:
        return redirect(url_for('login', error=f"Lỗi cổng Discord: {str(e)}"))

@app.route('/logout')
def logout():
    session.pop('username', None)
    return redirect(url_for('login'))

@app.route('/', methods=['GET'])
def index():
    if 'username' not in session: return redirect(url_for('login'))
    current_user = session['username']
    
    storage_data = load_storage(current_user)
    for key, config in storage_data.items():
        if current_user not in user_bots or key not in user_bots[current_user]:
            threading.Thread(target=run_bot, args=(key, config, current_user), daemon=True).start()
            
    active_bots = []
    if current_user in user_bots:
        active_bots = [(k, v) for k, v in user_bots[current_user].items() if v.get('running', False) and k in storage_data]
    has_bot = len(active_bots) > 0
    log, status = [], False
    if has_bot:
        first_key = active_bots[0][0]
        log = user_bots[current_user][first_key].get('log', [])
        status = user_bots[current_user][first_key].get('connected', False)
    return render_template_string(HTML_MAIN, log=log, status=status, has_bot=has_bot, bot_items=active_bots, current_user=current_user)

@app.route('/start', methods=['POST'])
def start_bot_route():
    if 'username' not in session: return redirect(url_for('login'))
    current_user = session['username']
    token = request.form['token'].strip()
    guild_id = request.form['guild_id'].strip()
    channel_id = request.form['channel_id'].strip()
    bot_key = f"{guild_id}_{channel_id}"
    config = {'bot_key': bot_key, 'token': token, 'guild_id': guild_id, 'channel_id': channel_id, 'mute': 'mute' in request.form, 'deaf': 'deaf' in request.form, 'video': 'video' in request.form, 'stream': 'stream' in request.form}
    save_storage_item(bot_key, config, current_user)
    
    if current_user not in user_bots: user_bots[current_user] = {}
    user_bots[current_user][bot_key] = {'connected': False, 'log': ["🚀 Đang thiết lập luồng..."], 'running': True, 'display_name': 'Đang kết nối...'}
    threading.Thread(target=run_bot, args=(bot_key, config, current_user), daemon=True).start()
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_bot_route():
    if 'username' not in session: return redirect(url_for('login'))
    current_user = session['username']
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key, current_user)
    if current_user in user_bots and bot_key in user_bots[current_user]:
        user_bots[current_user][bot_key]['running'] = False
        del user_bots[current_user][bot_key]
    return redirect(url_for('index'))

@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index'))

@app.route('/ping')
def ping(): return "pong"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
