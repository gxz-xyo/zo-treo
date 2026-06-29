from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
from datetime import timedelta
import threading, json, time, requests, websocket, os, logging, secrets
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

# Bật Logging có cấu trúc
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

app = Flask(__name__)
app.config['SECRET_KEY'] = os.getenv("SECRET_KEY", "za_tools_fallback_dev_key")
app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(days=7)

# Tắt Insecure Transport trên Production
if os.getenv("FLASK_ENV") != "production":
    os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== TỰ TẠO BỘ BẢO MẬT CSRF (KHÔNG DÙNG THƯ VIỆN NGOÀI) ==================
@app.before_request
def csrf_protect():
    if request.method == "POST":
        # Bỏ qua xác thực cho cổng nhận tiền tự động SePay
        if request.path == '/sepay_webhook': 
            return
        
        token = session.get('csrf_token', None)
        form_token = request.form.get('csrf_token')
        
        if not token or token != form_token:
            session.pop('csrf_token', None) # Xóa token cũ
            return "LỖI BẢO MẬT: Lỗi Token CSRF (Phiên làm việc hết hạn). Vui lòng quay lại và F5 tải lại trang!", 403

def generate_csrf_token():
    if 'csrf_token' not in session:
        session['csrf_token'] = secrets.token_hex(16)
    return session['csrf_token']

app.jinja_env.globals['csrf_token'] = generate_csrf_token

# ================== CẤU HÌNH DATABASE (CHỐNG LỖI NAMEERROR) ==================
MONGO_URI = os.getenv("MONGO_URI", "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0")
client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
db = client["za_tools_database"]
accounts_collection = db["accounts"]
users_collection = db["users"]
saved_profiles_collection = db["saved_profiles"]
transactions_collection = db["transactions"]

try:
    admin_user = "28012010"
    admin_pass = "itachi5867"
    if not users_collection.find_one({"username": admin_user}):
        users_collection.insert_one({"username": admin_user, "password": generate_password_hash(admin_pass), "security_pin": "admin123", "max_tokens": 9999, "is_admin": True, "balance": 0})
    else:
        users_collection.update_one({"username": admin_user}, {"$set": {"max_tokens": 9999, "is_admin": True}})
    logging.info("✅ MongoDB OK! Đã kích hoạt V24 - Fix Lỗi 500 Tuyệt Đối.")
except Exception as e:
    logging.error(f"💥 Lỗi DB: {e}")

user_bots = {}
bots_lock = threading.Lock()

SEPAY_API_KEY = os.getenv("SEPAY_API_KEY", "ZYIBFUMXFG6PJKXA0CNYCIQAKROTMD8Z3OQ5TDWVNX7E6DCDHXHGNOJM94FEWJ5Z")
DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

# ================== HÀM TIỆN ÍCH ==================
def get_user_limit(username):
    user = users_collection.find_one({"username": username})
    if not user: return 1, "Gói Free", "Free", ""
    if user.get('is_admin'): return 9999, "Vĩnh viễn", "God Mode", "var(--success-text)"
    
    current_limit = user.get('max_tokens', 1)
    plan_name = "Free"
    if current_limit == 2: plan_name = "STARTER"
    elif current_limit == 5: plan_name = "PRO"
    elif current_limit == 35: plan_name = "VIP"
    
    expiry_ts = user.get('expiry_date', 0)
    if expiry_ts > 0:
        time_left = expiry_ts - time.time()
        if time_left < 0:
            users_collection.update_one({"username": username}, {"$set": {"max_tokens": 1, "expiry_date": 0}})
            return 1, "Đã hết hạn", "Free", "var(--danger-text)"
        else:
            color = "var(--danger-text)" if time_left < 3 * 86400 else "var(--success-text)"
            days_str = f" (Còn {int(time_left // 86400)} ngày)"
            return current_limit, time.strftime('%d/%m/%Y', time.localtime(expiry_ts)) + days_str, plan_name, color
    return 1, "Gói Free", "Free", ""

def load_storage(username):
    data = {}
    for doc in accounts_collection.find({"owner": username}):
        data[doc["bot_key"]] = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True), 'video': doc.get('video', False), 'stream': doc.get('stream', False) }
    return data

def process_sepay_transaction(tid, amount, raw_content):
    if transactions_collection.find_one({"_id": str(tid)}): return False
    normalized_content = raw_content.lower().replace(" ", "").replace("-", "").replace("_", "")
    if 'zatools' in normalized_content:
        for user in users_collection.find():
            normalized_db_username = user['username'].lower().replace(" ", "").replace("-", "").replace("_", "")
            if "zatools" + normalized_db_username in normalized_content:
                users_collection.update_one({"username": user['username']}, {"$inc": {"balance": amount}})
                transactions_collection.insert_one({"_id": str(tid), "user": user['username'], "amount": amount, "time": time.time()})
                logging.info(f"💰 SePay: Đã nạp {amount} cho {user['username']} (Mã: {tid})")
                return True
    return False

# ================== HTML & CSS CHUNG ==================
HTML_HEAD = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script>
        const savedTheme = localStorage.getItem('za_theme') || 'dark';
        if (savedTheme === 'light') document.documentElement.setAttribute('data-theme', 'light');
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        :root {
            --bg-main: #07090f; --text-main: #fff; --text-muted: #85929e; --accent: #66fcf1;
            --accent-hover: rgba(102, 252, 241, 0.1); --card-bg: rgba(21, 26, 33, 0.6);
            --border-light: rgba(102, 252, 241, 0.1); --input-bg: rgba(11, 12, 16, 0.8);
            --input-border: rgba(47, 62, 70, 0.8); --btn-bg: linear-gradient(135deg, #162447, #1f4068);
            --nav-bg: rgba(11, 12, 16, 0.9); --sidebar-bg: rgba(21, 26, 33, 0.98);
            --account-card: rgba(11, 12, 16, 0.5); --log-bg: rgba(0, 0, 0, 0.5);
            --log-text: #4cdf8b; --shadow: rgba(0,0,0,0.3); --switch-bg: rgba(47, 62, 70, 0.8);
            --success-text: #2ecc71; --danger-text: #e74c3c; --coin-color: #f1c40f; --plan-text: #ff416c;
        }
        [data-theme="light"] {
            --bg-main: #f0f2f5; --text-main: #1e293b; --text-muted: #64748b; --accent: #0284c7;
            --accent-hover: rgba(2, 132, 199, 0.1); --card-bg: rgba(255, 255, 255, 0.9);
            --border-light: rgba(15, 23, 42, 0.1); --input-bg: #ffffff; --input-border: #cbd5e1;
            --btn-bg: linear-gradient(135deg, #0284c7, #0369a1); --nav-bg: rgba(255, 255, 255, 0.95);
            --sidebar-bg: rgba(255, 255, 255, 0.98); --account-card: #f8fafc; --log-bg: #f1f5f9;
            --log-text: #059669; --shadow: rgba(0,0,0,0.08); --switch-bg: #cbd5e1;
            --success-text: #059669; --danger-text: #dc2626; --coin-color: #d4ac0d; --plan-text: #e11d48;
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent;}
        body { background: var(--bg-main); color: var(--text-main); overflow-x: hidden; min-height: 100vh; transition: background 0.3s, color 0.3s; }
        .card { background: var(--card-bg); backdrop-filter: blur(12px); border-radius: 20px; padding: 25px; margin-bottom: 20px; border: 1px solid var(--border-light); box-shadow: 0 8px 32px var(--shadow); transition: 0.3s;}
        .card-title { color: var(--text-muted); font-size: 13px; text-transform: uppercase; font-weight: 800; margin-bottom: 20px; letter-spacing: 1px; display: flex; align-items: center; gap: 8px;}
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; color: var(--accent); font-size: 12px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; }
        .input-group input { width: 100%; padding: 14px; background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 12px; color: var(--text-main); font-size: 14px; outline: none; transition: 0.3s; }
        .input-group input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-hover); }
        .btn { width: 100%; padding: 14px; border-radius: 12px; font-weight: 800; font-size: 13px; cursor: pointer; text-align: center; border: none; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; text-transform: uppercase; }
        .btn-primary { background: var(--btn-bg); border: 1px solid var(--accent-hover); color: #fff; }
        .btn-primary:hover { transform: translateY(-2px); box-shadow: 0 5px 15px var(--accent-hover); }
        .btn-success { background: rgba(46, 204, 113, 0.1); border: 1px solid rgba(46, 204, 113, 0.3); color: var(--success-text); }
        .btn-danger { background: rgba(231, 76, 60, 0.1); border: 1px solid rgba(231, 76, 60, 0.3); color: var(--danger-text); padding: 12px; }
        .btn-buy { background: rgba(241, 196, 15, 0.1); border: 1px solid rgba(241, 196, 15, 0.3); color: var(--coin-color); margin-top:15px;}
        .btn-buy:hover { background: var(--coin-color); color: #000; transform: translateY(-2px);}
        .svg-icon { width: 18px; height: 18px; stroke-width: 2; stroke: currentColor; fill: none; stroke-linecap: round; stroke-linejoin: round; display: inline-flex; flex-shrink: 0; vertical-align: middle;}
        .msg { padding: 14px; border-radius: 12px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 8px; animation: slideDown 0.3s ease;}
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .msg.success { background: rgba(46, 204, 113, 0.1); color: var(--success-text); border: 1px solid rgba(46, 204, 113, 0.2); }
        .msg.error { background: rgba(231, 76, 60, 0.1); color: var(--danger-text); border: 1px solid rgba(231, 76, 60, 0.2); }
        .msg.warning { background: rgba(241, 196, 15, 0.1); color: var(--coin-color); border: 1px solid rgba(241, 196, 15, 0.3); }
        .theme-toggle-btn { background: var(--account-card); border: 1px solid var(--input-border); color: var(--text-main); border-radius: 10px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.3s; flex-shrink:0;}
        .theme-toggle-btn:hover { background: var(--accent-hover); color: var(--accent); }
        
        #global-loader { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; justify-content:center; align-items:center; flex-direction:column; color:var(--accent); font-weight:800; font-size:14px; letter-spacing:1px; backdrop-filter:blur(5px);}
        .spinner { width: 50px; height: 50px; border: 4px solid rgba(102, 252, 241, 0.2); border-top: 4px solid var(--accent); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px; }
        @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
        @media (max-width: 600px) { .card { padding: 20px; border-radius: 16px;} .btn-flex { flex-direction: column; gap: 10px; } }
    </style>
"""

# ================== GIAO DIỆN AUTH ==================
HTML_AUTH = HTML_HEAD + """
<title>Za Tools - Login</title>
<style>
    body { display: flex; justify-content: center; align-items: center; position: relative;}
    .auth-container { max-width: 400px; width: 90%; padding: 35px 25px; margin: 15px;}
    .logo { color: var(--text-main); font-size: 32px; font-weight: 800; text-align: center; margin-bottom: 5px; transition: 0.3s;}
    .logo span { color: var(--accent); }
    .sub { text-align: center; color: var(--text-muted); font-size: 13px; margin-bottom: 25px; transition: 0.3s;}
    .switch-link { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-muted); }
    .switch-link a { color: var(--accent); text-decoration: none; font-weight: 600; cursor: pointer; }
    .theme-corner { position: absolute; top: 20px; right: 20px; }
</style>
</head>
<body>
    <div id="global-loader"><div class="spinner"></div>ĐANG XỬ LÝ...</div>
    <button class="theme-toggle-btn theme-corner" onclick="toggleTheme()"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button>
    <div class="card auth-container">
        <div class="logo">Za <span>Tools</span></div>
        <div class="sub">
            {% if mode == 'login' %}Hệ thống treo voice siêu tốc{% elif mode == 'register' %}Đăng ký thành viên mới{% else %}Khôi phục mật khẩu{% endif %}
        </div>
        
        {% if error %}<div class="msg error"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> {{ error }}</div>{% endif %}
        {% if success %}<div class="msg success"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> {{ success }}</div>{% endif %}

        <form method="POST" action="/{{ mode }}" onsubmit="showLoader()">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <div class="input-group"><label>Tài khoản</label><input type="text" name="username" required placeholder="Tên đăng nhập..."></div>
            {% if mode == 'forgot' %}
                <div class="input-group"><label>Mã PIN bảo mật đã tạo</label><input type="text" name="pin" required placeholder="Nhập PIN lúc đăng ký..."></div>
                <div class="input-group"><label>Mật khẩu Mới</label><input type="password" name="new_password" required placeholder="Nhập pass mới..."></div>
                <button type="submit" class="btn btn-success">ĐỔI MẬT KHẨU</button>
            {% else %}
                <div class="input-group"><label>Mật khẩu</label><input type="password" name="password" required placeholder="••••••••"></div>
                {% if mode == 'register' %}
                <div class="input-group"><label>Mã PIN bảo mật (Để lấy lại pass)</label><input type="text" name="pin" required placeholder="Ví dụ: 1234, khoideptrai..."></div>
                {% endif %}
                <button type="submit" class="btn btn-primary">{{ 'ĐĂNG NHẬP' if mode == 'login' else 'ĐĂNG KÝ NGAY' }}</button>
            {% endif %}
        </form>
        
        <div class="switch-link">
            {% if mode == 'login' %}
                Chưa có tài khoản? <a href="/register">Tạo ngay</a><br><br><a href="/forgot">Quên mật khẩu?</a>
            {% elif mode == 'register' %}
                Đã có tài khoản? <a href="/login">Đăng nhập</a>
            {% else %}
                <a href="/login">← Quay lại đăng nhập</a>
            {% endif %}
        </div>
    </div>
    <script>
        function toggleTheme() {
            const root = document.documentElement;
            if (root.getAttribute('data-theme') === 'light') { root.removeAttribute('data-theme'); localStorage.setItem('za_theme', 'dark'); } 
            else { root.setAttribute('data-theme', 'light'); localStorage.setItem('za_theme', 'light'); }
        }
        function showLoader() { document.getElementById('global-loader').style.display = 'flex'; }
    </script>
</body>
</html>
"""

# ================== GIAO DIỆN ADMIN LOGIN CHỐNG HACK ==================
HTML_ADMIN_LOGIN = HTML_HEAD + """
<title>Xác thực Admin</title>
<style>
    body { display: flex; justify-content: center; align-items: center; position: relative;}
    .auth-container { max-width: 400px; width: 90%; padding: 35px 25px; margin: 15px;}
    .theme-corner { position: absolute; top: 20px; right: 20px; }
</style>
</head>
<body>
    <button class="theme-toggle-btn theme-corner" onclick="toggleTheme()"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button>
    <div class="card auth-container">
        <h2 style="color:var(--plan-text); text-align:center; margin-bottom: 20px;">XÁC THỰC ADMIN</h2>
        {% if error %}<div class="msg error">{{ error }}</div>{% endif %}
        <form method="POST" action="/admin_dangkhoi">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <div class="input-group"><label>Mật khẩu Bộ Chỉ Huy</label><input type="password" name="admin_pass" required placeholder="Nhập mật khẩu Admin..."></div>
            <button type="submit" class="btn btn-primary" style="background:var(--plan-text); border:none;">XÁC NHẬN TRUY CẬP</button>
        </form>
        <div style="text-align:center; margin-top:20px;"><a href="/" style="color:var(--text-muted); text-decoration:none; font-weight:600;">← Về trang chủ</a></div>
    </div>
    <script>
        function toggleTheme() {
            const root = document.documentElement;
            if (root.getAttribute('data-theme') === 'light') { root.removeAttribute('data-theme'); localStorage.setItem('za_theme', 'dark'); } 
            else { root.setAttribute('data-theme', 'light'); localStorage.setItem('za_theme', 'light'); }
        }
    </script>
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD CHÍNH ==================
HTML_MAIN = HTML_HEAD + """
<title>Za Tools - Premium Dashboard</title>
<style>
    .navbar { background: var(--nav-bg); backdrop-filter: blur(10px); padding: 15px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-light); position: sticky; top: 0; z-index: 100;}
    .nav-left { display: flex; align-items: center; }
    .menu-btn { background: none; border: none; color: var(--text-main); padding: 5px; cursor: pointer; margin-right: 12px; }
    .logo { color: var(--text-main); font-size: 20px; font-weight: 800; letter-spacing: -0.5px;}
    .logo span { color: var(--accent); }
    .sidebar { position: fixed; left: -260px; top: 0; width: 260px; height: 100%; background: var(--sidebar-bg); box-shadow: 2px 0 15px var(--shadow); transition: 0.3s; z-index: 1000; padding: 70px 20px 20px; border-right: 1px solid var(--border-light); display: flex; flex-direction: column; }
    .sidebar.active { left: 0; }
    .close-btn { position: absolute; right: 15px; top: 15px; color: var(--text-muted); font-size: 24px; cursor: pointer; background: none; border: none; }
    .user-tag { background: var(--account-card); padding: 15px 12px; border-radius: 12px; text-align: center; color: var(--text-main); font-size: 14px; font-weight: 600; margin-bottom: 20px; border: 1px solid var(--border-light); }
    .plan-badge { display:inline-block; margin-top:5px; background: rgba(102, 252, 241, 0.1); border: 1px solid var(--accent); color: var(--accent); font-size: 10px; padding: 3px 10px; border-radius: 20px; text-transform: uppercase; font-weight: 800;}
    .wallet-balance { color: var(--coin-color); font-size: 18px; font-weight: 800; margin: 8px 0; display:flex; justify-content:center; align-items:center; gap:5px;}
    .user-tag .expiry { font-size: 11px; margin-top: 5px; border-top: 1px dashed var(--input-border); padding-top: 8px;}
    .nav-link { display: flex; align-items: center; gap: 10px; padding: 12px 16px; color: var(--text-muted); text-decoration: none; font-size: 13px; font-weight: 600; transition: 0.2s; border-radius: 10px; margin-bottom: 5px; }
    .nav-link:hover, .nav-link.active-link { color: var(--accent); background: var(--accent-hover); }
    .logout { margin-top: auto; color: var(--danger-text); background: rgba(231, 76, 60, 0.05); }
    .container { max-width: 500px; width: 100%; margin: 20px auto; padding: 0 15px; }
    .tab-content { display: none; animation: fadeIn 0.3s; }
    .tab-content.active { display: block; }
    .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 15px 0; }
    .btn-flex { display: flex; gap: 10px; margin-top: 15px; }
    .account-card { background: var(--account-card); border-radius: 14px; padding: 15px; margin-bottom: 12px; border: 1px solid var(--input-border); display: flex; justify-content: space-between; align-items: center; }
    .account-card .name { font-weight: 700; color: var(--text-main); font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
    .log-box { background: var(--log-bg); border-radius: 12px; padding: 12px; max-height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; color: var(--log-text); border: 1px solid var(--input-border); margin-bottom: 15px; white-space: pre-wrap; word-break: break-word;}
    .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 900; display: none; }
    .overlay.active { display: block; }
    .limit-badge { background: var(--accent-hover); color: var(--accent); padding: 10px 15px; border-radius: 10px; font-size: 12px; border: 1px solid var(--border-light); margin-bottom: 20px; display: flex; align-items: center; gap: 8px; font-weight: 600;}
    .plan-box { background: var(--card-bg); border: 1px solid var(--input-border); border-radius: 14px; padding: 20px; margin-bottom: 15px; text-align: center; transition: 0.3s; position: relative; overflow: hidden;}
    .plan-box:hover { border-color: var(--coin-color); transform: translateY(-3px); }
    .plan-title { font-size: 13px; font-weight: 800; color: var(--text-muted); margin-bottom: 5px; }
    .plan-price { font-size: 24px; color: var(--text-main); font-weight: 800; margin-bottom: 12px; display:flex; justify-content:center; align-items:center; gap:5px;}
    .plan-feature { font-size: 12px; color: var(--text-main); margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 6px;}
    .plan-vip { border-color: rgba(255, 65, 108, 0.5); background: linear-gradient(180deg, rgba(255, 65, 108, 0.05) 0%, transparent 100%); }
    .plan-vip .plan-title { color: #ff416c; }
    .tab-header { display: flex; gap: 10px; margin-bottom: 20px; background: var(--account-card); padding: 5px; border-radius: 12px;}
    .tab-btn { flex: 1; padding: 10px; text-align: center; font-size: 13px; font-weight: 600; color: var(--text-muted); cursor: pointer; border-radius: 8px; transition: 0.3s;}
    .tab-btn.active { background: var(--btn-bg); color: #fff; }
    @keyframes pulse { 0% { opacity: 1; } 50% { opacity: 0.5; } 100% { opacity: 1; } }
    .pulsing { animation: pulse 1.5s infinite; }
    @media (max-width: 600px) {
        .account-card { flex-direction: column; align-items: flex-start; gap: 12px; }
        .account-card > div:last-child { width: 100%; display: flex; gap: 8px; }
        .account-card form { flex: 1; display:flex; }
        .account-card .btn { width: 100%; justify-content: center;}
    }
</style>
</head>
<body>
<div id="global-loader"><div class="spinner"></div>ĐANG XỬ LÝ...</div>
<nav class="navbar">
    <div class="nav-left">
        <button class="menu-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg></button>
        <div class="logo">Za <span>Tools</span></div>
    </div>
    <button class="theme-toggle-btn" onclick="toggleTheme()"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button>
</nav>
<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

<div class="sidebar" id="sidebar">
    <button class="close-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
    <div class="user-tag">
        @{{ current_user }}
        <div class="plan-badge">Gói {{ plan_name }}</div>
        <div class="wallet-balance" id="wallet-display-sidebar"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> {{ "{:,}".format(balance) }} </div>
        <div class="expiry" style="color: {{ expiry_color }};">Hạn gói: {{ expiry_info }}</div>
    </div>
    
    <a href="#" class="nav-link active-link" onclick="switchTab('treo', this)"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg> Treo Voice</a>
    <a href="#" class="nav-link" onclick="switchTab('saved', this)"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Tài khoản đã lưu</a>
    <a href="#" class="nav-link" onclick="switchTab('premium', this)" style="color: var(--coin-color);"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> Ví Coin & Nâng Cấp</a>
    
    {% if is_admin %}
    <a href="/admin_dangkhoi" class="nav-link" style="color: var(--plan-text); margin-top: 15px; border-top: 1px dashed var(--input-border); padding-top: 20px;"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> Mắt Thần (Admin)</a>
    {% endif %}
    <a href="/logout" class="nav-link logout"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg> Đăng xuất</a>
</div>

<div class="container">
    {% if flash_msg %}<div class="msg {{ flash_type }}">{{ flash_msg }}</div>{% endif %}

    <!-- TAB TREO -->
    <div id="tab-treo" class="tab-content active">
        <div class="limit-badge"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> Đang chạy: {{ running_count }}/{{ max_tokens }} Slot</div>
        <form method="POST" onsubmit="showLoader()">
            <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
            <div class="card">
                <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M20 14.66V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5.34"></path></svg> Thiết lập kết nối</div>
                <div class="input-group"><label>Tên gợi nhớ (Nếu lưu)</label><input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp..."></div>
                <div class="input-group"><label>Discord Token</label><input type="text" name="token" required placeholder="Nhập Token của bạn..."></div>
                <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required></div>
                <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required></div>
                <div class="options-grid">
                    <div class="switch-wrap"><div class="switch-label">Mute</div><label class="switch"><input type="checkbox" name="mute" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Deaf</div><label class="switch"><input type="checkbox" name="deaf" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Video</div><label class="switch"><input type="checkbox" name="video"><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Stream</div><label class="switch"><input type="checkbox" name="stream"><span class="slider"></span></label></div>
                </div>
                <div class="btn-flex">
                    <button type="submit" formaction="/start" class="btn btn-primary">CHẠY NGAY</button>
                    <button type="submit" formaction="/save_profile" class="btn btn-success">LƯU LẠI</button>
                </div>
            </div>
        </form>

        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg> Luồng đang chạy</div>
            {% for key, bot in bot_items %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--accent); width:16px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> {{ bot.get('display_name', 'Đang kết nối...') }}</div>
                    <div style="font-size:11px; color:var(--success-text); margin-left: 22px;">Treo vĩnh cửu</div>
                </div>
                <form method="POST" action="/stop" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="bot_key" value="{{ key }}"><button type="submit" class="btn btn-danger"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg></button></form>
            </div>
            {% endfor %}
            {% if not bot_items %}<div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 10px 0;">Trống.</div>{% endif %}
        </div>
        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg> Nhật Ký</div>
            <div class="log-box">{{ log|join('\\n') if log else 'Đang chờ hệ thống...' }}</div>
            <form method="POST" action="/refresh" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="tab" value="treo"><button type="submit" class="btn btn-primary" style="width:100%;">CẬP NHẬT TRẠNG THÁI</button></form>
        </div>
    </div>

    <!-- TAB ĐÃ LƯU -->
    <div id="tab-saved" class="tab-content">
        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg> Kho dữ liệu cá nhân</div>
            {% for profile in saved_profiles %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" viewBox="0 0 24 24" style="color:#c5a059; width:16px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg> {{ profile.profile_name }}</div>
                    <div style="font-size:11px; color:var(--text-muted); margin-left: 22px;">Máy chủ: {{ profile.guild_id }}</div>
                </div>
                <div style="display:flex; gap:8px;">
                    <form method="POST" action="/start_saved" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-success" style="padding:10px;"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></button></form>
                    <form method="POST" action="/delete_profile" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-danger" style="padding:10px;"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button></form>
                </div>
            </div>
            {% endfor %}
            {% if not saved_profiles %}<div style="text-align:center; font-size:12px; color:var(--text-muted); padding: 20px 0;">Chưa có tài khoản lưu trữ.</div>{% endif %}
        </div>
    </div>

    <!-- TAB PREMIUM & VÍ -->
    <div id="tab-premium" class="tab-content">
        <div class="tab-header">
            <div class="tab-btn active" id="btn-nap" onclick="switchSubTab('nap')">NẠP COIN</div>
            <div class="tab-btn" id="btn-mua" onclick="switchSubTab('mua')">CỬA HÀNG GÓI</div>
        </div>
        
        <div id="sub-nap" class="card">
            <div class="card-title" style="color: var(--coin-color);">NẠP SỐ DƯ (1 VNĐ = 1 COIN)</div>
            <div class="input-group"><input type="number" id="nap_amount" placeholder="Nhập số tiền muốn nạp..." min="10000" step="10000"></div>
            <button onclick="generateNapQR()" class="btn btn-primary" style="margin-bottom:20px;">TẠO MÃ NẠP TIỀN</button>
            <div id="qr_nap_area" style="display: none; text-align: center; border-top: 1px dashed var(--input-border); padding-top: 20px;">
                <img id="qr_nap_img" src="" style="width: 220px; border-radius: 12px; border: 2px solid var(--coin-color);">
                <div style="margin-top: 15px; font-size: 13px; background: var(--input-bg); padding: 12px; border-radius: 10px;">
                    <span style="color:var(--text-muted);">Nội dung chuyển khoản tự động:</span><br>
                    <b style="color:var(--success-text); font-size: 16px; letter-spacing: 1px;">ZATOOLS <span id="clean_username"></span></b>
                </div>
                <div id="payment_status" class="msg pulsing" style="display:none; margin-top:15px; background:rgba(241, 196, 15, 0.1); color:var(--coin-color); border:1px solid rgba(241, 196, 15, 0.3);">
                    Đang chờ ngân hàng xử lý...
                </div>
            </div>
        </div>
        
        <div id="sub-mua" class="card" style="display: none;">
            <div class="card-title" style="color: var(--plan-text);">MUA GÓI PREMIUM (30 NGÀY)</div>
            <div class="plan-box">
                <div class="plan-title">GÓI STARTER</div>
                <div class="plan-price">20,000</div>
                <div class="plan-feature">Treo tối đa 2 Token</div>
                <form method="POST" action="/buy_plan" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="plan" value="STARTER"><button type="submit" class="btn btn-buy">DÙNG COIN MUA GÓI</button></form>
            </div>
            <div class="plan-box">
                <div class="plan-title" style="color: var(--accent);">GÓI PRO</div>
                <div class="plan-price">40,000</div>
                <div class="plan-feature">Treo tối đa 5 Token</div>
                <form method="POST" action="/buy_plan" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="plan" value="PRO"><button type="submit" class="btn btn-buy">DÙNG COIN MUA GÓI</button></form>
            </div>
            <div class="plan-box plan-vip">
                <div class="plan-title">GÓI VIP</div>
                <div class="plan-price">300,000</div>
                <div class="plan-feature">Treo tối đa 35 Token</div>
                <form method="POST" action="/buy_plan" onsubmit="showLoader()"><input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/><input type="hidden" name="plan" value="VIP"><button type="submit" class="btn btn-buy">DÙNG COIN MUA GÓI</button></form>
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
    function switchSubTab(sub) {
        document.getElementById('sub-nap').style.display = 'none';
        document.getElementById('sub-mua').style.display = 'none';
        document.getElementById('btn-nap').classList.remove('active');
        document.getElementById('btn-mua').classList.remove('active');
        document.getElementById('sub-' + sub).style.display = 'block';
        document.getElementById('btn-' + sub).classList.add('active');
    }
    window.onload = () => {
        let reqTab = '{{ active_tab }}';
        let tabToLoad = reqTab !== 'None' ? reqTab : (localStorage.getItem('za_active_tab') || 'treo');
        let links = document.querySelectorAll('.nav-link');
        let targetLink = Array.from(links).find(l => l.getAttribute('onclick').includes(tabToLoad));
        if(targetLink) switchTab(tabToLoad, targetLink);
    };
    
    let checkPaymentInterval;
    let currentBalance = {{ balance }};

    function generateNapQR() {
        let amount = document.getElementById('nap_amount').value;
        if (!amount || amount < 10000) { alert('Vui lòng nạp tối thiểu 10.000 VNĐ'); return; }
        let rawUser = '{{ current_user }}';
        let cleanUser = rawUser.replace(/_/g, "").replace(/-/g, "").replace(/ /g, "");
        document.getElementById('clean_username').innerText = cleanUser;
        let addInfo = encodeURIComponent('ZATOOLS ' + cleanUser);
        let url = `https://img.vietqr.io/image/MB-1628012010-compact2.png?amount=${amount}&addInfo=${addInfo}&accountName=Phan%20Tran%20Dang%20Khoi`;
        document.getElementById('qr_nap_img').src = url;
        document.getElementById('qr_nap_area').style.display = 'block';
        document.getElementById('payment_status').style.display = 'flex';
        if(checkPaymentInterval) clearInterval(checkPaymentInterval);
        checkPaymentInterval = setInterval(checkBalance, 3000);
    }
    
    function checkBalance() {
        fetch('/api/get_balance')
        .then(res => res.json())
        .then(data => {
            if (data.balance > currentBalance) {
                clearInterval(checkPaymentInterval);
                let diff = data.balance - currentBalance;
                currentBalance = data.balance;
                let statusDiv = document.getElementById('payment_status');
                statusDiv.className = 'msg';
                statusDiv.style.background = 'rgba(46, 204, 113, 0.1)';
                statusDiv.style.color = 'var(--success-text)';
                statusDiv.style.borderColor = 'rgba(46, 204, 113, 0.3)';
                statusDiv.innerHTML = `Nạp thành công +${diff.toLocaleString('vi-VN')} Coin!`;
                document.getElementById('wallet-display-sidebar').innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> ${currentBalance.toLocaleString('vi-VN')}`;
            }
        });
    }
    function toggleTheme() {
        const root = document.documentElement;
        if (root.getAttribute('data-theme') === 'light') { root.removeAttribute('data-theme'); localStorage.setItem('za_theme', 'dark'); } 
        else { root.setAttribute('data-theme', 'light'); localStorage.setItem('za_theme', 'light'); }
    }
    function showLoader() { document.getElementById('global-loader').style.display = 'flex'; }
</script>
</body>
</html>
"""

# ================== TRANG ADMIN PANEL ==================
HTML_ADMIN = HTML_HEAD + """
<title>Admin Panel - Za Tools</title>
<style>
    .admin-container { max-width: 600px; width: 95%; margin: 30px auto; padding: 25px; background: var(--card-bg); border-radius: 20px; border: 1px solid var(--border-light); box-shadow: 0 10px 40px var(--shadow); }
    .stat-box { background: var(--input-bg); padding: 15px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; border: 1px solid var(--input-border); font-weight: 600; color: var(--text-muted);}
    .stat-val { color: var(--text-main); font-size: 18px; }
    .action-box { background: rgba(102, 252, 241, 0.05); border: 1px solid var(--accent); padding: 20px; border-radius: 15px; margin-top: 25px;}
    #global-loader { display:none; position:fixed; top:0; left:0; width:100%; height:100%; background:rgba(0,0,0,0.8); z-index:9999; justify-content:center; align-items:center; flex-direction:column; color:var(--accent); font-weight:800; font-size:14px; letter-spacing:1px; backdrop-filter:blur(5px);}
    .spinner { width: 50px; height: 50px; border: 4px solid rgba(102, 252, 241, 0.2); border-top: 4px solid var(--accent); border-radius: 50%; animation: spin 1s linear infinite; margin-bottom: 15px; }
    @keyframes spin { 0% { transform: rotate(0deg); } 100% { transform: rotate(360deg); } }
</style>
<body>
    <div id="global-loader"><div class="spinner"></div>ĐANG XỬ LÝ...</div>
    <button class="theme-toggle-btn" onclick="toggleTheme()" style="position: absolute; top:20px; right:20px;"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg></button>
    <div class="admin-container">
        <h2 style="color:var(--text-main); text-align:center; margin-bottom:25px;">MẮT THẦN DANGKHOI</h2>
        {% if msg %}<div class="msg success">{{ msg }}</div>{% endif %}
        
        <div class="stat-box">Thành viên: <span class="stat-val">{{ stats.users }}</span></div>
        <div class="stat-box">Token đang lưu: <span class="stat-val">{{ stats.bots }}</span></div>
        <div class="stat-box">Luồng cày ngầm: <span class="stat-val" style="color:var(--success-text);">{{ stats.running }}</span></div>
        <div class="stat-box">Tổng nạp: <span class="stat-val" style="color:var(--coin-color);">{{ "{:,}".format(stats.total_money) }} đ</span></div>
        
        <div class="action-box">
            <h3 style="color:var(--accent); font-size:14px; margin-bottom:15px;">CỘNG TIỀN THỦ CÔNG</h3>
            <form method="POST" action="/admin_action" onsubmit="document.getElementById('global-loader').style.display='flex'">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="add_coin">
                <div class="input-group"><input type="text" name="target_user" required placeholder="Nhập username khách..."></div>
                <div class="input-group"><input type="number" name="amount" required placeholder="Số Coin cần cộng..."></div>
                <button type="submit" class="btn btn-primary" style="background:var(--success-text); border:none;">XÁC NHẬN CỘNG</button>
            </form>
        </div>

        <div class="action-box" style="background: rgba(241, 196, 15, 0.05); border-color: var(--coin-color);">
            <h3 style="color:var(--coin-color); font-size:14px; margin-bottom:15px;">ĐỒNG BỘ SEPAY (BÙ TIỀN BỊ LỖI)</h3>
            <form method="POST" action="/admin_action" onsubmit="document.getElementById('global-loader').style.display='flex'">
                <input type="hidden" name="csrf_token" value="{{ csrf_token() }}"/>
                <input type="hidden" name="action" value="sync_sepay">
                <button type="submit" class="btn btn-primary" style="background:var(--coin-color); color:#000; border:none;">QUÉT & ĐỒNG BỘ NGAY</button>
            </form>
        </div>
        <div style="text-align:center; margin-top:20px;"><a href="/" style="color:var(--text-muted); text-decoration:none;">← Trở về trang chủ</a></div>
    </div>
    <script>
        function toggleTheme() {
            const root = document.documentElement;
            if (root.getAttribute('data-theme') === 'light') { root.removeAttribute('data-theme'); localStorage.setItem('za_theme', 'dark'); } 
            else { root.setAttribute('data-theme', 'light'); localStorage.setItem('za_theme', 'light'); }
        }
    </script>
</body>
</html>
"""

# ================== HÀM CHẠY LUỒNG AN TOÀN (THREAD-SAFE) ==================
def run_bot(bot_key, config, username):
    token, guild_id, channel_id = config['token'], config['guild_id'], config['channel_id']
    mute, deaf = config.get('mute', True), config.get('deaf', True)
    video, stream = config.get('video', False), config.get('stream', False)

    stop_event = threading.Event()
    ws_container = {"ws": None}

    with bots_lock:
        if username not in user_bots: user_bots[username] = {}
        user_bots[username][bot_key] = {'connected': False, 'log': ["🚀 Khởi tạo tiến trình an toàn..."], 'running': True, 'display_name': 'Đang kết nối...', 'stop_event': stop_event}

    def add_log(msg):
        with bots_lock:
            if username in user_bots and bot_key in user_bots[username]:
                timestamp = time.strftime('%H:%M:%S')
                user_bots[username][bot_key]['log'].append(f"[{timestamp}] {msg}")
                if len(user_bots[username][bot_key]['log']) > 50: user_bots[username][bot_key]['log'] = user_bots[username][bot_key]['log'][-50:]

    def update_status(st):
        with bots_lock:
            if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['connected'] = st

    def send_voice_update(ws_client):
        if not ws_client or not ws_client.keep_running: return
        try: ws_client.send(json.dumps({"op": 4, "d": {"guild_id": guild_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf, "self_video": video, "self_stream": stream}}))
        except: pass

    def on_message(ws_client, message):
        try: data = json.loads(message)
        except: return
        op, t = data.get('op'), data.get('t')

        if op == 10:
            ws_client.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "Linux"}, "compress": False}}))
            add_log("📤 Gửi gói danh tính Gateway...")
        elif op == 0:
            if t == 'READY':
                with bots_lock:
                    if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['display_name'] = data['d']['user']['username']
                add_log(f"🎯 Đăng nhập: {data['d']['user']['username']}")
                send_voice_update(ws_client)
            elif t == 'VOICE_STATE_UPDATE':
                if data['d'].get('channel_id') == channel_id:
                    update_status(True); add_log("✅ Đã chốt vị trí trong phòng thoại!")
                elif data['d'].get('channel_id') is None:
                    update_status(False); add_log("⚠️ Bị văng! Hệ thống đang nối lại...")
                    send_voice_update(ws_client)
        elif op == 9: ws_client.close()

    def on_close(ws_client, code, msg):
        update_status(False)
        add_log("🔌 Ngắt kết nối mạng...")
        if not stop_event.is_set():
            time.sleep(5)
            start_ws()

    def heartbeat_loop():
        while not stop_event.is_set():
            if stop_event.wait(41): break
            if ws_container["ws"] and ws_container["ws"].keep_running:
                try: ws_container["ws"].send(json.dumps({"op": 1, "d": None}))
                except: pass

    def keep_alive_loop():
        while not stop_event.is_set():
            if stop_event.wait(30): break
            if ws_container["ws"] and ws_container["ws"].keep_running: send_voice_update(ws_container["ws"])

    def start_ws():
        if stop_event.is_set(): return
        try: gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except: time.sleep(5); start_ws(); return
        
        ws_container["ws"] = websocket.WebSocketApp(gateway + "/?v=9&encoding=json", on_message=on_message, on_close=on_close, on_error=lambda w,e: add_log(f"💥 Lỗi: {e}"))
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws_container["ws"].run_forever()

    start_ws()

def auto_bootloader():
    try:
        for doc in accounts_collection.find():
            username = doc.get("owner"); bot_key = doc.get("bot_key")
            if not username or not bot_key: continue
            limit, _, _, _ = get_user_limit(username)
            with bots_lock:
                current_running = sum(1 for v in user_bots.get(username, {}).values() if v.get('running', False))
            if current_running >= limit: continue 
            config = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True), 'video': doc.get('video', False), 'stream': doc.get('stream', False) }
            threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
            time.sleep(0.5)
    except: pass
threading.Thread(target=auto_bootloader, daemon=True).start()

# ================== SEPAY WEBHOOK ==================
@app.route('/sepay_webhook', methods=['POST'])
def sepay_webhook():
    try:
        data = request.json
        if not data: return jsonify({"error": "No data"}), 400
        tid = data.get('id', data.get('transactionId', str(int(time.time()))))
        amount = int(data.get('transferAmount', data.get('amount', 0)))
        raw_content = data.get('content', data.get('transferContent', ''))
        process_sepay_transaction(tid, amount, raw_content)
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

@app.route('/api/get_balance')
def api_get_balance():
    if 'username' not in session: return jsonify({"balance": 0})
    user = users_collection.find_one({"username": session['username']})
    return jsonify({"balance": user.get('balance', 0) if user else 0})

# ================== MUA GÓI BẰNG COIN ==================
@app.route('/buy_plan', methods=['POST'])
def buy_plan():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    plan = request.form.get('plan')
    costs = {"STARTER": 20000, "PRO": 40000, "VIP": 300000}
    limits = {"STARTER": 2, "PRO": 5, "VIP": 35}
    if plan not in costs: return redirect(url_for('index', tab='premium'))
    
    user_db = users_collection.find_one({"username": usr})
    current_balance = user_db.get('balance', 0)
    cost = costs[plan]
    if current_balance >= cost:
        new_balance = current_balance - cost
        new_limit = max(user_db.get('max_tokens', 1), limits[plan])
        new_expiry = int(time.time()) + 2592000
        users_collection.update_one({"username": usr}, {"$set": {"balance": new_balance, "max_tokens": new_limit, "expiry_date": new_expiry}})
        session['flash_msg'] = f"Đã mua thành công Gói {plan}!"
        session['flash_type'] = "success"
    else:
        session['flash_msg'] = "Ví của bạn không đủ Coin. Vui lòng nạp thêm!"
        session['flash_type'] = "error"
    return redirect(url_for('index', tab='premium'))

# ================== ROUTES ỨNG DỤNG ==================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    max_tokens, expiry_info, plan_name, expiry_color = get_user_limit(usr)
    db_user = users_collection.find_one({"username": usr})
    balance = db_user.get('balance', 0) if db_user else 0
    is_admin = db_user.get('is_admin', False) if db_user else False
    with bots_lock: active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    log = active_bots[0][1].get('log', []) if active_bots else []
    
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, balance=balance, plan_name=plan_name,
                                  saved_profiles=get_saved_profiles(usr), max_tokens=max_tokens, 
                                  running_count=len(active_bots), is_admin=is_admin, expiry_info=expiry_info, expiry_color=expiry_color,
                                  flash_msg=session.pop('flash_msg', None), flash_type=session.pop('flash_type', 'success'),
                                  active_tab=request.args.get('tab', 'None'), log=log)

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    max_tokens, _, _, _ = get_user_limit(usr)
    with bots_lock: current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    bot_key = f"{request.form['guild_id']}_{request.form['channel_id']}"
    
    if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
        session['flash_msg'] = f"Gói đã đầy! Giới hạn: {max_tokens} slot."
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='treo'))

    config = {k:v for k,v in request.form.items() if k not in ['profile_name', 'csrf_token']}
    save_storage_item(bot_key, config, usr)
    with bots_lock:
        if usr not in user_bots: user_bots[usr] = {}
        if bot_key in user_bots[usr]: 
            user_bots[usr][bot_key]['stop_event'].set()
            user_bots[usr][bot_key]['running'] = False
    threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/start_saved', methods=['POST'])
def start_saved():
    usr = session.get('username')
    max_tokens, _, _, _ = get_user_limit(usr)
    with bots_lock: current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    
    prof_id = request.form.get('profile_id')
    try: prof = saved_profiles_collection.find_one({"_id": prof_id, "owner": usr}) or saved_profiles_collection.find_one({"_id": ObjectId(prof_id), "owner": usr})
    except: prof = None
    if prof:
        bot_key = f"{prof['guild_id']}_{prof['channel_id']}"
        if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
            session['flash_msg'] = f"Cần Nạp/Gia Hạn VIP để chạy! Giới hạn: {max_tokens}"
            session['flash_type'] = "error"
            return redirect(url_for('index', tab='saved'))
        config = {k:v for k,v in prof.items() if k not in ['_id', 'owner', 'profile_name']}
        config['bot_key'] = bot_key
        save_storage_item(bot_key, config, usr)
        with bots_lock:
            if usr not in user_bots: user_bots[usr] = {}
            if bot_key in user_bots[usr]: 
                user_bots[usr][bot_key]['stop_event'].set()
                user_bots[usr][bot_key]['running'] = False
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
            session.permanent = True
            return redirect(url_for('index'))
        return render_template_string(HTML_AUTH, mode='login', error="Sai thông tin đăng nhập!")
    return render_template_string(HTML_AUTH, mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usr = request.form['username'].strip().lower()
        pin = request.form['pin'].strip()
        if users_collection.find_one({"username": usr}): return render_template_string(HTML_AUTH, mode='register', error="Tên đăng nhập đã tồn tại!")
        users_collection.insert_one({"username": usr, "password": generate_password_hash(request.form['password'].strip()), "security_pin": pin, "max_tokens": 1, "expiry_date": 0, "balance": 0})
        return render_template_string(HTML_AUTH, mode='login', success="Đăng ký thành công! Hãy nhớ mã PIN.")
    return render_template_string(HTML_AUTH, mode='register')

@app.route('/forgot', methods=['GET', 'POST'])
def forgot():
    if request.method == 'POST':
        usr = request.form['username'].strip().lower()
        pin = request.form['pin'].strip()
        new_pwd = request.form['new_password'].strip()
        user_db = users_collection.find_one({"username": usr})
        if user_db and user_db.get('security_pin') == pin:
            users_collection.update_one({"username": usr}, {"$set": {"password": generate_password_hash(new_pwd)}})
            return render_template_string(HTML_AUTH, mode='login', success="Đổi mật khẩu thành công!")
        return render_template_string(HTML_AUTH, mode='forgot', error="Tài khoản hoặc PIN sai!")
    return render_template_string(HTML_AUTH, mode='forgot')

@app.route('/save_profile', methods=['POST'])
def save_profile():
    prof_name = request.form.get('profile_name', '').strip() or f"Config {int(time.time())}"
    config_dict = {k:v for k,v in request.form.to_dict().items() if k != 'csrf_token'}
    saved_profiles_collection.insert_one({**config_dict, "owner": session['username'], "_id": str(int(time.time())), "profile_name": prof_name})
    session['flash_msg'] = "Đã lưu vào Kho dữ liệu!"
    return redirect(url_for('index', tab='saved'))

@app.route('/delete_profile', methods=['POST'])
def del_prof():
    pid = request.form.get('profile_id')
    try:
        if not saved_profiles_collection.delete_one({"_id": pid, "owner": session['username']}).deleted_count:
            saved_profiles_collection.delete_one({"_id": ObjectId(pid), "owner": session['username']})
    except: pass
    return redirect(url_for('index', tab='saved'))

@app.route('/stop', methods=['POST'])
def stop():
    usr = session['username']
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key, usr)
    with bots_lock:
        if usr in user_bots and bot_key in user_bots[usr]:
            user_bots[usr][bot_key]['stop_event'].set()
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
    if not users_collection.find_one({"username": usr}): users_collection.insert_one({"username": usr, "oauth": "discord", "security_pin": "discord", "max_tokens": 1, "expiry_date": 0, "balance": 0})
    session['username'] = usr
    session.permanent = True
    return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/ping')
def ping(): return "ok"
@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

# ================== TRANG ADMIN PANEL (CÓ BẢO MẬT PASS) ==================
@app.route('/admin_dangkhoi', methods=['GET', 'POST'])
def admin_dashboard():
    if session.get('username') != '28012010': return redirect(url_for('index'))
    
    # Check Admin Pass
    if not session.get('admin_unlocked'):
        if request.method == 'POST':
            if request.form.get('admin_pass') == 'itachi5867':
                session['admin_unlocked'] = True
                return redirect(url_for('admin_dashboard'))
            else:
                return render_template_string(HTML_ADMIN_LOGIN, error="Mật khẩu Admin không đúng!")
        return render_template_string(HTML_ADMIN_LOGIN)

    total_users = users_collection.count_documents({})
    total_bots = accounts_collection.count_documents({})
    with bots_lock: active_running = sum(1 for usr, bots in user_bots.items() for k, d in bots.items() if d.get('running', False))
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    res = list(transactions_collection.aggregate(pipeline))
    total_money = res[0]["total"] if res else 0
    
    stats = {"users": total_users, "bots": total_bots, "running": active_running, "total_money": total_money}
    msg = session.pop('admin_msg', None)
    return render_template_string(HTML_ADMIN, stats=stats, msg=msg)

@app.route('/admin_action', methods=['POST'])
def admin_action():
    if session.get('username') != '28012010' or not session.get('admin_unlocked'): return redirect(url_for('index'))
    action = request.form.get('action')
    
    if action == 'add_coin':
        t_user = request.form.get('target_user').strip().lower()
        amount = int(request.form.get('amount', 0))
        u = users_collection.find_one({"username": t_user})
        if u:
            users_collection.update_one({"username": t_user}, {"$inc": {"balance": amount}})
            session['admin_msg'] = f"Đã cộng {amount} Coin cho {t_user}!"
        else: session['admin_msg'] = "Không tìm thấy user này!"
            
    elif action == 'sync_sepay':
        try:
            headers = {"Authorization": f"Bearer {SEPAY_API_KEY}"}
            r = requests.get("https://my.sepay.vn/userapi/transactions/list", headers=headers, timeout=10)
            data = r.json()
            synced_count = 0
            if 'transactions' in data:
                for t in data['transactions']:
                    tid, amt, content = str(t['id']), int(float(t['amount_in'])), t['transaction_content']
                    if process_sepay_transaction(tid, amt, content): synced_count += 1
            session['admin_msg'] = f"Đồng bộ hoàn tất! Tìm thấy và cộng bù {synced_count} giao dịch bị sót."
        except Exception as e: session['admin_msg'] = f"Lỗi đồng bộ: {str(e)}"
            
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
