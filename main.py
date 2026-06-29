from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading, json, time, requests, websocket, os, base64
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "za_tools_final_v14_god_mode"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== CẤU HÌNH DATABASE ==================
MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"
try:
    client = MongoClient(MONGO_URI)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    saved_profiles_collection = db["saved_profiles"]
    
    # TỰ ĐỘNG CẤP QUYỀN GOD MODE CHO ADMIN DANGKHOI
    admin_user = "28012010"
    admin_pass = "itachi5867"
    if not users_collection.find_one({"username": admin_user}):
        users_collection.insert_one({
            "username": admin_user,
            "password": generate_password_hash(admin_pass),
            "max_tokens": 9999,
            "is_admin": True
        })
    else:
        # Nếu đổi pass hoặc lỡ bị hạ quyền, tự set lại max cấu hình
        users_collection.update_one({"username": admin_user}, {"$set": {"max_tokens": 9999, "is_admin": True}})
        
    print("✅ MongoDB OK! Đã kích hoạt Za Tools V14 - God Mode & Auto-Fill QR.")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}
ANTI_CAPTCHA_API_KEY = '72cd105f15332c81afa5855ac4ce7d86'

# Thông tin ngân hàng nhận tiền
BANK_ID = "MB"
ACCOUNT_NO = "1628012010"
ACCOUNT_NAME = "Phan Tran Dang Khoi"

# ================== CẤU HÌNH STEALTH (NGỤY TRANG) ==================
STEALTH_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
    "X-Super-Properties": "eyJvcyI6IldpbmRvd3MiLCJicm93c2VyIjoiQ2hyb21lIiwib3NfdmVyc2lvbiI6IjEwIn0=",
    "Content-Type": "application/json"
}

DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

def solve_captcha(site_key):
    try:
        task = {"clientKey": ANTI_CAPTCHA_API_KEY, "task": {"type": "HCaptchaTaskProxyless", "websiteURL": "https://discord.com", "websiteKey": site_key}}
        task_id = requests.post("https://api.anti-captcha.com/createTask", json=task, timeout=10).json().get("taskId")
        for _ in range(20):
            time.sleep(5)
            res = requests.post("https://api.anti-captcha.com/getTaskResult", json={"clientKey": ANTI_CAPTCHA_API_KEY, "taskId": task_id}).json()
            if res.get("status") == "ready": return res["solution"]["gRecaptchaResponse"]
    except: return None
    return None

def load_storage(username):
    try:
        data = {}
        for doc in accounts_collection.find({"owner": username}):
            data[doc["bot_key"]] = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True), 'video': doc.get('video', False), 'stream': doc.get('stream', False) }
        return data
    except: return {}

def get_saved_profiles(username):
    try: return list(saved_profiles_collection.find({"owner": username}))
    except: return []

def save_storage_item(bot_key, config, username):
    try:
        config["owner"] = username
        accounts_collection.update_one({"bot_key": bot_key}, {"$set": config}, upsert=True)
    except: pass

def delete_storage_item(bot_key, username):
    try: accounts_collection.delete_one({"bot_key": bot_key, "owner": username})
    except: pass

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
        <div class="sub">Hệ thống treo voice tự động</div>
        {% if error %}<div class="msg error">❌ {{ error }}</div>{% endif %}
        {% if success %}<div class="msg success">✅ {{ success }}</div>{% endif %}
        <form method="POST" action="{{ '/login' if mode == 'login' else '/register' }}">
            <div class="input-group"><label>Tên tài khoản</label><input type="text" name="username" required></div>
            <div class="input-group"><label>Mật khẩu</label><input type="password" name="password" required></div>
            <button type="submit" class="btn-primary">{{ 'ĐĂNG NHẬP' if mode == 'login' else 'ĐĂNG KÝ' }}</button>
        </form>
        <div class="divider">Hoặc</div>
        <a href="/login/discord" class="btn-oauth">🎮 Đăng nhập bằng Discord</a>
        <div class="switch-link">
            {% if mode == 'login' %}Chưa có tài khoản? <a href="/register">Đăng ký ngay</a>
            {% else %}Đã có tài khoản? <a href="/login">Đăng nhập</a>{% endif %}
        </div>
    </div>
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD ĐA TAB ==================
HTML_MAIN = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Za Tools - Premium Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: '-apple-system', BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; }
        body { background: #0b0c10; color: #fff; overflow-x: hidden; }
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
        .container { max-width: 500px; margin: 20px auto; padding: 0 15px; }
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        .card { background: #151a21; border-radius: 12px; padding: 20px; margin-bottom: 20px; border: 1px solid #2f3e46; }
        .card-title { color: #85929e; font-size: 11px; text-transform: uppercase; font-weight: 700; margin-bottom: 15px; letter-spacing: 1px; }
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; color: #66fcf1; font-size: 11px; margin-bottom: 5px; font-weight: 600; text-transform: uppercase; }
        .input-group input { width: 100%; padding: 12px; background: #0b0c10; border: 1px solid #2f3e46; border-radius: 8px; color: #fff; font-size: 14px; outline: none; }
        .input-group input:focus { border-color: #66fcf1; }
        .options { display: flex; flex-wrap: wrap; gap: 10px; margin: 15px 0; }
        .options label { color: #85929e; font-size: 12px; display: flex; align-items: center; gap: 6px; cursor: pointer; background: #0b0c10; padding: 8px 12px; border-radius: 6px; border: 1px solid #2f3e46; }
        .btn-flex { display: flex; gap: 10px; }
        .btn { flex: 1; padding: 14px; border-radius: 8px; font-weight: 700; font-size: 13px; cursor: pointer; text-align: center; border: none; transition: 0.2s; }
        .btn-primary { background: linear-gradient(135deg, #1f4068, #162447); border: 1px solid #66fcf1; color: #66fcf1; }
        .btn-primary:hover { background: #66fcf1; color: #0b0c10; }
        .btn-success { background: rgba(46, 204, 113, 0.1); border: 1px solid #2ecc71; color: #2ecc71; }
        .btn-success:hover { background: #2ecc71; color: #000; }
        .btn-danger { padding: 10px 14px; background: rgba(231, 76, 60, 0.1); border: 1px solid #e74c3c; border-radius: 6px; color: #e74c3c; font-size: 12px; font-weight: bold; cursor: pointer; }
        .account-card { background: #0b0c10; border-radius: 8px; padding: 14px; margin: 10px 0; border: 1px solid #2f3e46; display: flex; justify-content: space-between; align-items: center; }
        .account-card .name { font-weight: 700; color: #fff; font-size: 14px; margin-bottom: 4px;}
        .log-box { background: #0b0c10; border-radius: 8px; padding: 12px; max-height: 160px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #39ff14; border: 1px solid #2f3e46; margin-bottom: 12px; white-space: pre-wrap; }
        .msg { padding: 10px; border-radius: 8px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 500; }
        .msg.success { background: rgba(46, 204, 113, 0.1); color: #2ecc71; border: 1px solid #2ecc71; }
        .msg.error { background: rgba(231, 76, 60, 0.1); color: #e74c3c; border: 1px solid #e74c3c; }
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 900; display: none; }
        .overlay.active { display: block; }
        .limit-badge { background: rgba(255, 65, 108, 0.1); color: #ff416c; padding: 5px 10px; border-radius: 4px; font-size: 12px; border: 1px solid #ff416c; margin-bottom: 15px; display: inline-block; font-weight: bold;}
        .plan-box { background: #0b0c10; border: 1px solid #2f3e46; border-radius: 12px; padding: 20px; margin-bottom: 15px; text-align: center; cursor: pointer; transition: 0.3s; }
        .plan-box:hover { border-color: #66fcf1; transform: translateY(-3px); }
        .plan-title { font-size: 16px; font-weight: bold; color: #85929e; margin-bottom: 5px; }
        .plan-price { font-size: 24px; color: #fff; font-weight: 800; margin-bottom: 15px; }
        .plan-price span { font-size: 14px; color: #85929e; }
        .plan-feature { font-size: 13px; color: #2ecc71; margin-bottom: 5px; }
        .plan-vip { border-color: #ff416c; box-shadow: 0 0 15px rgba(255, 65, 108, 0.2); }
        .plan-vip .plan-title { color: #ff416c; }
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
        <div class="user-tag">@{{ current_user }}</div>
        <a href="#" class="nav-link active-link" onclick="switchTab('treo', this)">🎤 Treo Voice</a>
        <a href="#" class="nav-link" onclick="switchTab('saved', this)">💾 Tài khoản đã lưu</a>
        <a href="#" class="nav-link" onclick="switchTab('tools', this)">🛠️ Tiện ích Token</a>
        <a href="#" class="nav-link" onclick="switchTab('premium', this)" style="color: #ff416c;">💎 Nâng cấp Premium</a>
        
        {% if is_admin %}
        <a href="/admin_dangkhoi" class="nav-link" style="color: #4cdf8b; margin-top: 15px; border-top: 1px dashed #2f3e46; padding-top: 20px;">👁️ Mắt Thần (Admin)</a>
        {% endif %}
        
        <a href="/logout" class="logout">🚪 Đăng xuất</a>
    </div>

    <div class="container">
        {% if flash_msg %}<div class="msg {{ flash_type }}">{{ flash_msg }}</div>{% endif %}

        <div id="tab-treo" class="tab-content active">
            <div class="limit-badge">Giới hạn gói: {{ running_count }}/{{ max_tokens }} Token đang chạy {% if is_admin %} (GOD MODE) {% endif %}</div>
            <form method="POST">
                <div class="card">
                    <div class="card-title">Thiết lập kết nối</div>
                    <div class="input-group"><label>Tên gợi nhớ (Tùy chọn)</label><input type="text" name="profile_name" placeholder="Acc cày cấp..."></div>
                    <div class="input-group"><label>Discord Token</label><input type="text" name="token" required></div>
                    <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required></div>
                    <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required></div>
                    <div class="options">
                        <label><input type="checkbox" name="mute" checked> Mute</label>
                        <label><input type="checkbox" name="deaf" checked> Deaf</label>
                        <label><input type="checkbox" name="video"> Video</label>
                        <label><input type="checkbox" name="stream"> Stream</label>
                    </div>
                    <div class="btn-flex">
                        <button type="submit" formaction="/start" class="btn btn-primary">🚀 CHẠY NGAY</button>
                        <button type="submit" formaction="/save_profile" class="btn btn-success">💾 LƯU LẠI</button>
                    </div>
                </div>
            </form>

            <div class="card">
                <div class="card-title">Đang chạy ngầm</div>
                {% for key, bot in bot_items %}
                <div class="account-card">
                    <div>
                        <div class="name">{{ bot.get('display_name', 'Đang kết nối...') }}</div>
                        <div style="font-size:11px; color:#2ecc71;">Treo vĩnh cửu</div>
                    </div>
                    <form method="POST" action="/stop" style="display:inline;"><input type="hidden" name="bot_key" value="{{ key }}"><button type="submit" class="btn-danger">Dừng</button></form>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <div class="card-title">Nhật ký</div>
                <div class="log-box">{{ log|join('\\n') if log else 'Đang chờ lệnh...' }}</div>
                <form method="POST" action="/refresh"><input type="hidden" name="tab" value="treo"><button type="submit" class="btn btn-primary" style="width:100%;">LÀM MỚI</button></form>
            </div>
        </div>

        <div id="tab-saved" class="tab-content">
            <div class="card">
                <div class="card-title">Kho dữ liệu cá nhân</div>
                {% for profile in saved_profiles %}
                <div class="account-card">
                    <div><div class="name">{{ profile.profile_name }}</div><div style="font-size:11px; color:#85929e;">Server: {{ profile.guild_id }}</div></div>
                    <div style="display:flex; gap:5px;">
                        <form method="POST" action="/start_saved"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn-success" style="padding:6px 10px; border:none; border-radius:4px; font-weight:bold; cursor:pointer;">▶️ Chạy</button></form>
                        <form method="POST" action="/delete_profile"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn-danger" style="padding:6px 10px; border:none;">🗑️</button></form>
                    </div>
                </div>
                {% endfor %}
            </div>
        </div>

        <div id="tab-tools" class="tab-content">
            {% if not tool_token %}
            <div class="card">
                <div class="card-title">BƯỚC 1: KIỂM TRA TOKEN</div>
                <form method="POST" action="/check_token">
                    <div class="input-group"><label>Discord Token</label><input type="text" name="tool_token" required></div>
                    <button type="submit" class="btn btn-primary" style="width:100%;">🔍 KIỂM TRA</button>
                </form>
            </div>
            {% else %}
            <div class="card">
                <div class="card-title">BƯỚC 2: HỒ SƠ TÀI KHOẢN</div>
                <div style="display:flex; align-items:center; gap:15px; margin-bottom:15px; border-bottom:1px solid #2f3e46; padding-bottom:15px;">
                    {% if tool_user.avatar %}<img src="https://cdn.discordapp.com/avatars/{{ tool_user.id }}/{{ tool_user.avatar }}.png" style="width:50px; height:50px; border-radius:50%;">{% endif %}
                    <div><b>{{ tool_user.global_name or tool_user.username }}</b><div style="font-size:12px; color:#85929e;">@{{ tool_user.username }}</div></div>
                </div>
                <form method="POST" action="/update_discord_profile" enctype="multipart/form-data">
                    <div class="input-group"><label>Tên hiển thị mới</label><input type="text" name="new_global_name"></div>
                    <div class="input-group"><label>Tiểu sử mới</label><input type="text" name="new_bio"></div>
                    <div class="input-group"><label>Avatar mới</label><input type="file" name="new_avatar" accept="image/*" style="background: transparent;"></div>
                    <button type="submit" class="btn btn-success" style="width:100%; margin-bottom:10px;">🔄 ÁP DỤNG</button>
                </form>
                <form method="POST" action="/clear_token"><button type="submit" class="btn btn-danger" style="width:100%; padding:12px;">❌ ĐÓNG</button></form>
            </div>
            {% endif %}
        </div>

        <div id="tab-premium" class="tab-content">
            <div class="card">
                <div class="card-title" style="color: #ff416c;">💎 Nâng Cấp Premium</div>
                <p style="font-size:12px; color:#85929e; text-align:center; margin-bottom:15px;">Khách chỉ cần quét mã QR, App ngân hàng sẽ <b>TỰ ĐỘNG ĐIỀN</b> nội dung. Hệ thống duyệt ngay sau 10s.</p>
                
                <div class="plan-box" onclick="showQR(25000, 'STARTER')">
                    <div class="plan-title">GÓI STARTER</div>
                    <div class="plan-price">25.000đ <span>/ vĩnh viễn</span></div>
                    <div class="plan-feature">✔️ Treo tối đa 2 Token cùng lúc</div>
                </div>
                
                <div class="plan-box" onclick="showQR(45000, 'PRO')">
                    <div class="plan-title" style="color: #66fcf1;">GÓI PRO</div>
                    <div class="plan-price">45.000đ <span>/ vĩnh viễn</span></div>
                    <div class="plan-feature">✔️ Treo tối đa 5 Token cùng lúc</div>
                </div>

                <div class="plan-box plan-vip" onclick="showQR(350000, 'VIP')">
                    <div class="plan-title">GÓI VIP</div>
                    <div class="plan-price">350.000đ <span>/ vĩnh viễn</span></div>
                    <div class="plan-feature">✔️ Treo tối đa 35 Token cùng lúc</div>
                </div>

                <div id="qr_area" style="display: none; text-align: center; margin-top: 20px; border-top: 1px dashed #2f3e46; padding-top: 20px;">
                    <p style="color: #fff; margin-bottom: 10px;">Quét mã thanh toán gói <b id="qr_plan_name" style="color:#ff416c;"></b></p>
                    <img id="qr_img" src="" style="width: 220px; border-radius: 10px; border: 2px solid #66fcf1;">
                    <div style="margin-top: 15px; font-size: 14px; background: #0b0c10; padding: 10px; border-radius: 8px;">
                        <span style="color:#85929e;">App ngân hàng sẽ tự điền nội dung:</span><br>
                        <b style="color:#4cdf8b; font-size: 16px; letter-spacing: 1px;">ZATOOLS {{ current_user }}</b>
                    </div>
                </div>
            </div>
        </div>

    </div>

    <script>
        function toggleSidebar() { document.getElementById('sidebar').classList.toggle('active'); document.getElementById('overlay').classList.toggle('active'); }
        function switchTab(tabId, el) {
            document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
            document.getElementById('tab-' + tabId).classList.add('active');
            document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active-link'));
            if(el) el.classList.add('active-link');
            document.getElementById('sidebar').classList.remove('active');
            document.getElementById('overlay').classList.remove('active');
            localStorage.setItem('za_active_tab', tabId);
        }
        window.onload = () => {
            let reqTab = '{{ active_tab }}';
            let tabToLoad = reqTab !== 'None' ? reqTab : (localStorage.getItem('za_active_tab') || 'treo');
            let links = document.querySelectorAll('.nav-link');
            let targetLink = Array.from(links).find(l => l.getAttribute('onclick').includes(tabToLoad));
            if(targetLink) switchTab(tabToLoad, targetLink);
        };
        
        function showQR(amount, planName) {
            let user = '{{ current_user }}';
            // Mã hóa chính xác nội dung để VietQR gắn trực tiếp vào QR, các app ngân hàng sẽ tự bắt lấy
            let addInfo = encodeURIComponent('ZATOOLS ' + user);
            let url = `https://img.vietqr.io/image/MB-1628012010-compact2.png?amount=${amount}&addInfo=${addInfo}&accountName=Phan%20Tran%20Dang%20Khoi`;
            document.getElementById('qr_img').src = url;
            document.getElementById('qr_plan_name').innerText = planName;
            document.getElementById('qr_area').style.display = 'block';
            window.scrollTo(0, document.body.scrollHeight);
        }
    </script>
</body>
</html>
"""

# ================== HÀM CHẠY LUỒNG ==================
def run_bot(bot_key, config, username):
    token, guild_id, channel_id = config['token'], config['guild_id'], config['channel_id']
    mute, deaf = config.get('mute', True), config.get('deaf', True)
    if username not in user_bots: user_bots[username] = {}
    user_bots[username][bot_key] = {'connected': False, 'log': ["🚀 Đang khởi động..."], 'running': True, 'display_name': 'Đang kết nối...'}

    def start_ws():
        try:
            ws = websocket.WebSocketApp(requests.get("https://discord.com/api/v9/gateway").json()['url'] + "/?v=9&encoding=json",
                on_message=lambda w, m: handle_msg(w, json.loads(m)))
            def handle_msg(w, d):
                if d.get('op') == 10: w.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "Linux"}, "compress": False}}))
                if d.get('t') == 'READY':
                    user_bots[username][bot_key]['display_name'] = d['d']['user']['username']
                    w.send(json.dumps({"op": 4, "d": {"guild_id": guild_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf}}))
                if d.get('t') == 'VOICE_STATE_UPDATE' and d['d'].get('channel_id') == channel_id:
                    user_bots[username][bot_key]['connected'] = True
            ws.run_forever()
        except: pass
    threading.Thread(target=start_ws, daemon=True).start()

# ================== AUTO-BOOTLOADER ==================
def auto_bootloader():
    try:
        for doc in accounts_collection.find():
            username = doc.get("owner"); bot_key = doc.get("bot_key")
            if not username or not bot_key: continue
            config = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True) }
            if username not in user_bots: user_bots[username] = {}
            if bot_key not in user_bots[username]: threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
    except: pass
auto_bootloader()

# ================== SEPAY WEBHOOK (XỬ LÝ THANH TOÁN TỰ ĐỘNG) ==================
@app.route('/sepay_webhook', methods=['POST'])
def sepay_webhook():
    try:
        data = request.json
        if not data: return jsonify({"error": "No data"}), 400
        content = data.get('content', data.get('transferContent', '')).upper()
        amount = int(data.get('transferAmount', data.get('amount', 0)))
        
        # Bắt nội dung "ZATOOLS tendangnhap" cực kỳ chính xác
        if 'ZATOOLS' in content:
            parts = content.split('ZATOOLS')
            if len(parts) > 1:
                username_part = parts[1].strip().split()[0].lower()
                user = users_collection.find_one({"username": username_part})
                
                if user:
                    current_limit = user.get('max_tokens', 1)
                    new_limit = current_limit
                    if amount >= 350000: new_limit = max(current_limit, 35)
                    elif amount >= 45000: new_limit = max(current_limit, 5)
                    elif amount >= 25000: new_limit = max(current_limit, 2)
                    
                    if new_limit > current_limit:
                        users_collection.update_one({"username": username_part}, {"$set": {"max_tokens": new_limit}})
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

# ================== ROUTES ỨNG DỤNG CHÍNH ==================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    
    db_user = users_collection.find_one({"username": usr})
    max_tokens = db_user.get('max_tokens', 1) if db_user else 1
    is_admin = db_user.get('is_admin', False) if db_user else False
    
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    log = active_bots[0][1].get('log', []) if active_bots else []
    
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, 
                                  saved_profiles=get_saved_profiles(usr), max_tokens=max_tokens, running_count=len(active_bots),
                                  is_admin=is_admin, tool_token=session.get('tool_token'), tool_user=session.get('tool_user', {}),
                                  flash_msg=session.pop('flash_msg', None), flash_type=session.pop('flash_type', 'success'),
                                  active_tab=request.args.get('tab', 'None'), log=log)

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    db_user = users_collection.find_one({"username": usr})
    max_tokens = db_user.get('max_tokens', 1) if db_user else 1
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    bot_key = f"{request.form['guild_id']}_{request.form['channel_id']}"
    
    if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
        session['flash_msg'] = f"Vượt quá giới hạn! Gói hiện tại cho phép {max_tokens} Token."
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='treo'))

    config = {k:v for k,v in request.form.items() if k not in ['profile_name']}
    save_storage_item(bot_key, config, usr)
    if usr not in user_bots: user_bots[usr] = {}
    if bot_key in user_bots[usr]: user_bots[usr][bot_key]['running'] = False; time.sleep(0.5)
    threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/start_saved', methods=['POST'])
def start_saved():
    usr = session.get('username')
    db_user = users_collection.find_one({"username": usr})
    max_tokens = db_user.get('max_tokens', 1) if db_user else 1
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    prof_id = request.form.get('profile_id')
    try: prof = saved_profiles_collection.find_one({"_id": prof_id}) or saved_profiles_collection.find_one({"_id": ObjectId(prof_id)})
    except: prof = None
    
    if prof:
        bot_key = f"{prof['guild_id']}_{prof['channel_id']}"
        if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
            session['flash_msg'] = f"Cần Nâng cấp VIP để chạy thêm! Giới hạn: {max_tokens}"
            session['flash_type'] = "error"
            return redirect(url_for('index', tab='saved'))
        config = {k:v for k,v in prof.items() if k not in ['_id', 'owner', 'profile_name']}
        config['bot_key'] = bot_key
        save_storage_item(bot_key, config, usr)
        if usr not in user_bots: user_bots[usr] = {}
        if bot_key in user_bots[usr]: user_bots[usr][bot_key]['running'] = False; time.sleep(0.5)
        threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/login', methods=['GET', 'POST'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    if request.method == 'POST':
        username = request.form['username'].strip().lower()
        pwd = request.form['password'].strip()
        u = users_collection.find_one({"username": username})
        if u and check_password_hash(u.get('password', ''), pwd):
            session['username'] = username
            return redirect(url_for('index'))
        return render_template_string(HTML_AUTH, mode='login', error="Sai thông tin!")
    return render_template_string(HTML_AUTH, mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usr = request.form['username'].strip().lower()
        if users_collection.find_one({"username": usr}): return render_template_string(HTML_AUTH, mode='register', error="Đã tồn tại!")
        users_collection.insert_one({"username": usr, "password": generate_password_hash(request.form['password'].strip()), "max_tokens": 1})
        return redirect(url_for('login', success="Thành công!"))
    return render_template_string(HTML_AUTH, mode='register')

@app.route('/save_profile', methods=['POST'])
def save_profile():
    prof_name = request.form.get('profile_name', '').strip() or f"Config {int(time.time())}"
    saved_profiles_collection.insert_one({**request.form.to_dict(), "owner": session['username'], "_id": str(int(time.time())), "profile_name": prof_name})
    session['flash_msg'] = "Đã lưu!"
    return redirect(url_for('index', tab='saved'))

@app.route('/delete_profile', methods=['POST'])
def del_prof():
    pid = request.form.get('profile_id')
    try:
        if not saved_profiles_collection.delete_one({"_id": pid}).deleted_count: saved_profiles_collection.delete_one({"_id": ObjectId(pid)})
    except: pass
    return redirect(url_for('index', tab='saved'))

@app.route('/stop', methods=['POST'])
def stop():
    usr = session['username']
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key, usr)
    if usr in user_bots and bot_key in user_bots[usr]:
        user_bots[usr][bot_key]['running'] = False
        del user_bots[usr][bot_key]
    return redirect(url_for('index', tab='treo'))

@app.route('/login/discord')
def login_discord(): return redirect(OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord", scope=['identify']).authorization_url(DISCORD_AUTH_URL)[0])

@app.route('/callback/discord')
def cb_discord():
    discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord")
    discord.fetch_token(DISCORD_TOKEN_URL, client_secret=DISCORD_CLIENT_SECRET, authorization_response=request.url.replace('http://', 'https://'))
    usr = f"{discord.get('https://discord.com/api/users/@me').json()['username']}_dc"
    if not users_collection.find_one({"username": usr}): users_collection.insert_one({"username": usr, "oauth": "discord", "max_tokens": 1})
    session['username'] = usr
    return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/ping')
def ping(): return "ok"
@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

# --- API CẬP NHẬT DISCORD ---
@app.route('/check_token', methods=['POST'])
def check_token():
    t = request.form.get('tool_token', '')
    h = STEALTH_HEADERS.copy(); h["Authorization"] = t
    r = requests.get("https://discord.com/api/v9/users/@me", headers=h)
    if r.status_code == 200: session['tool_token'] = t; session['tool_user'] = r.json()
    else: session['flash_msg'] = "Token chết!"; session['flash_type'] = "error"
    return redirect(url_for('index', tab='tools'))

@app.route('/update_discord_profile', methods=['POST'])
def update_discord():
    payload = {}
    if request.form.get('new_global_name'): payload["global_name"] = request.form['new_global_name']
    if request.form.get('new_bio'): payload["bio"] = request.form['new_bio']
    if request.files.get('new_avatar'): payload["avatar"] = f"data:image/jpeg;base64,{base64.b64encode(request.files['new_avatar'].read()).decode()}"
    
    h = STEALTH_HEADERS.copy(); h["Authorization"] = session['tool_token']
    r = requests.patch("https://discord.com/api/v9/users/@me", headers=h, json=payload)
    if r.status_code == 403 and "captcha_sitekey" in r.text:
        session['flash_msg'] = "Đang giải Captcha..."
        code = solve_captcha(r.json()["captcha_sitekey"])
        if code:
            h["X-Captcha-Key"] = code
            r = requests.patch("https://discord.com/api/v9/users/@me", headers=h, json=payload)
    return redirect(url_for('index', tab='tools'))

@app.route('/clear_token', methods=['POST'])
def clr(): session.pop('tool_token', None); return redirect(url_for('index', tab='tools'))

# ================== TRANG ADMIN BÍ MẬT ==================
@app.route('/admin_dangkhoi')
def admin_dashboard():
    if session.get('username') != '28012010': return redirect(url_for('index'))
    total_users = users_collection.count_documents({})
    total_bots = accounts_collection.count_documents({})
    active_running = sum(1 for usr, bots in user_bots.items() for k, d in bots.items() if d.get('running', False))
    
    html = f"""
    <html>
    <body style='background:#0b0c10; color:#66fcf1; text-align:center; padding:50px; font-family:sans-serif;'>
        <h1>👁️ MẮT THẦN DANGKHOI 👁️</h1>
        <div style='background:#1f2833; padding:20px; border-radius:12px; display:inline-block; border:1px solid #45f3ff;'>
            <p style='color:#fff'>👥 Số thành viên: <b style='color:#4cdf8b'>{total_users}</b></p>
            <p style='color:#fff'>🤖 Token đã nạp: <b style='color:#4cdf8b'>{total_bots}</b></p>
            <p style='color:#fff'>⚡ Luồng đang cày: <b style='color:#4cdf8b'>{active_running}</b></p>
        </div>
        <br><br><a href="/" style="color:#85929e; text-decoration:none;">← Quay lại Server</a>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
