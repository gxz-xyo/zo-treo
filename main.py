from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading, json, time, requests, websocket, os
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "za_tools_final_v22_ultimate_live_logs"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== CẤU HÌNH DATABASE ==================
MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"
try:
    client = MongoClient(MONGO_URI)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    saved_profiles_collection = db["saved_profiles"]
    transactions_collection = db["transactions"]
    
    admin_user = "28012010"
    admin_pass = "itachi5867"
    if not users_collection.find_one({"username": admin_user}):
        users_collection.insert_one({"username": admin_user, "password": generate_password_hash(admin_pass), "security_pin": "admin123", "max_tokens": 9999, "is_admin": True, "balance": 0})
    else:
        users_collection.update_one({"username": admin_user}, {"$set": {"max_tokens": 9999, "is_admin": True}})
        
    print("✅ MongoDB OK! Đã kích hoạt V22.6 - Fix Ảnh RPC & Thêm Đếm Giờ.")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}

SEPAY_API_KEY = 'ZYIBFUMXFG6PJKXA0CNYCIQAKROTMD8Z3OQ5TDWVNX7E6DCDHXHGNOJM94FEWJ5Z'
DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

# ================== HÀM KIỂM TRA THỜI HẠN GÓI ==================
def get_user_limit(username):
    user = users_collection.find_one({"username": username})
    if not user: return 1, "Gói Free", "Free"
    if user.get('is_admin'): return 9999, "Vĩnh viễn (Admin)", "God Mode"
    
    current_limit = user.get('max_tokens', 1)
    plan_name = "Free"
    if current_limit == 2: plan_name = "STARTER"
    elif current_limit == 5: plan_name = "PRO"
    elif current_limit == 35: plan_name = "VIP"
    
    expiry_ts = user.get('expiry_date', 0)
    if expiry_ts > 0:
        if int(time.time()) > expiry_ts:
            users_collection.update_one({"username": username}, {"$set": {"max_tokens": 1, "expiry_date": 0}})
            return 1, "Đã hết hạn", "Free"
        else:
            return current_limit, time.strftime('%d/%m/%Y %H:%M', time.localtime(expiry_ts)), plan_name
    return 1, "Gói Free", "Free"

def get_saved_profiles(username):
    try: return list(saved_profiles_collection.find({"owner": username}))
    except: return []

def save_storage_item(bot_key, config, username):
    try: accounts_collection.update_one({"bot_key": bot_key}, {"$set": {**config, "owner": username}}, upsert=True)
    except: pass

def delete_storage_item(bot_key, username):
    try: accounts_collection.delete_one({"bot_key": bot_key, "owner": username})
    except: pass

def process_sepay_transaction(tid, amount, raw_content):
    if transactions_collection.find_one({"_id": str(tid)}): return False
    normalized_content = raw_content.lower().replace(" ", "").replace("-", "").replace("_", "")
    if 'zatools' in normalized_content:
        for user in users_collection.find():
            normalized_db_username = user['username'].lower().replace(" ", "").replace("-", "").replace("_", "")
            if "zatools" + normalized_db_username in normalized_content:
                users_collection.update_one({"username": user['username']}, {"$inc": {"balance": amount}})
                transactions_collection.insert_one({"_id": str(tid), "user": user['username'], "amount": amount, "time": time.time()})
                return True
    return False

# ================== CẤU TRÚC HTML & CSS ==================
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
        .card-title { color: var(--text-muted); font-size: 13px; text-transform: uppercase; font-weight: 800; margin-bottom: 20px; letter-spacing: 1px; display: flex; align-items: center; justify-content: space-between; gap: 8px;}
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
        .theme-toggle-btn { background: var(--account-card); border: 1px solid var(--input-border); color: var(--text-main); border-radius: 10px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.3s; flex-shrink:0;}
        .theme-toggle-btn:hover { background: var(--accent-hover); color: var(--accent); }
        @media (max-width: 600px) { .card { padding: 20px; border-radius: 16px;} .btn-flex { flex-direction: column; gap: 10px; } }
    </style>
"""

THEME_SCRIPT = """
    <script>
        const MOON_ICON = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
        const SUN_ICON = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
        
        function setInitialThemeIcon() {
            const root = document.documentElement;
            const iconBtn = document.getElementById('theme-icon');
            if(iconBtn) { iconBtn.innerHTML = root.getAttribute('data-theme') === 'light' ? SUN_ICON : MOON_ICON; }
        }
        
        function toggleTheme() {
            const root = document.documentElement;
            const isLight = root.getAttribute('data-theme') === 'light';
            const iconBtn = document.getElementById('theme-icon');
            
            if (isLight) { 
                root.removeAttribute('data-theme'); 
                localStorage.setItem('za_theme', 'dark'); 
                if(iconBtn) iconBtn.innerHTML = MOON_ICON;
            } else { 
                root.setAttribute('data-theme', 'light'); 
                localStorage.setItem('za_theme', 'light'); 
                if(iconBtn) iconBtn.innerHTML = SUN_ICON;
            }
        }
        document.addEventListener("DOMContentLoaded", setInitialThemeIcon);
    </script>
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
    .divider { display: flex; align-items: center; text-align: center; color: var(--text-muted); font-size: 11px; margin: 20px 0; font-weight: 800; text-transform: uppercase; }
    .divider::before, .divider::after { content: ''; flex: 1; border-bottom: 1px solid var(--input-border); transition: 0.3s;}
    .divider:not(:empty)::before { margin-right: 1em; } .divider:not(:empty)::after { margin-left: 1em; }
    .btn-oauth { width: 100%; padding: 14px; border-radius: 12px; font-weight: 800; font-size: 13px; cursor: pointer; text-align: center; border: none; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; text-transform: uppercase; background: #5865F2; color: #fff; text-decoration:none; margin-bottom: 15px;}
    .btn-oauth:hover { transform: translateY(-2px); box-shadow: 0 5px 15px rgba(88, 101, 242, 0.4); }
    .switch-link { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-muted); }
    .switch-link a { color: var(--accent); text-decoration: none; font-weight: 600; cursor: pointer; }
    .theme-corner { position: absolute; top: 20px; right: 20px; }
</style>
</head>
<body>
    <button class="theme-toggle-btn theme-corner" onclick="toggleTheme()"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"></svg></button>
    <div class="card auth-container">
        <div class="logo">Za <span>Tools</span></div>
        <div class="sub">{% if mode == 'login' %}Hệ thống treo voice siêu tốc{% elif mode == 'register' %}Đăng ký thành viên mới{% else %}Khôi phục mật khẩu{% endif %}</div>
        
        {% if error %}<div class="msg error"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> {{ error }}</div>{% endif %}
        {% if success %}<div class="msg success"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> {{ success }}</div>{% endif %}

        {% if mode == 'login' %}
        <form method="POST" action="/login">
            <div class="input-group"><label>Tài khoản</label><input type="text" name="username" required placeholder="Tên đăng nhập..."></div>
            <div class="input-group"><label>Mật khẩu</label><input type="password" name="password" required placeholder="••••••••"></div>
            <button type="submit" class="btn btn-primary">ĐĂNG NHẬP</button>
        </form>
        <div class="divider">Hoặc</div>
        <a href="/login/discord" class="btn-oauth"><svg class="svg-icon" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg>Đăng nhập bằng Discord</a>
        <div class="switch-link">Chưa có tài khoản? <a href="/register">Tạo ngay</a><br><br><a href="/forgot">Quên mật khẩu?</a></div>
        
        {% elif mode == 'register' %}
        <form method="POST" action="/register">
            <div class="input-group"><label>Tài khoản</label><input type="text" name="username" required placeholder="Tên đăng nhập..."></div>
            <div class="input-group"><label>Mật khẩu</label><input type="password" name="password" required placeholder="••••••••"></div>
            <div class="input-group"><label>Mã PIN bảo mật (Để lấy lại pass)</label><input type="text" name="pin" required placeholder="Ví dụ: 1234, khoideptrai..."></div>
            <button type="submit" class="btn btn-primary">ĐĂNG KÝ NGAY</button>
        </form>
        <div class="switch-link">Đã có tài khoản? <a href="/login">Đăng nhập</a></div>
        
        {% elif mode == 'forgot' %}
        <form method="POST" action="/forgot">
            <div class="input-group"><label>Tên tài khoản</label><input type="text" name="username" required placeholder="Tài khoản cần lấy lại..."></div>
            <div class="input-group"><label>Mã PIN bảo mật đã tạo</label><input type="text" name="pin" required placeholder="Nhập PIN lúc đăng ký..."></div>
            <div class="input-group"><label>Mật khẩu Mới</label><input type="password" name="new_password" required placeholder="Nhập pass mới..."></div>
            <button type="submit" class="btn btn-success">ĐỔI MẬT KHẨU</button>
        </form>
        <div class="switch-link"><a href="/login">← Quay lại đăng nhập</a></div>
        {% endif %}
    </div>
    """ + THEME_SCRIPT + """
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD CHÍNH ==================
HTML_MAIN = HTML_HEAD + """
<title>Za Tools - Dashboard</title>
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
    .user-tag .expiry { color: var(--text-muted); font-size: 11px; margin-top: 5px; border-top: 1px dashed var(--input-border); padding-top: 8px;}
    
    .nav-link { display: flex; align-items: center; gap: 10px; padding: 12px 16px; color: var(--text-muted); text-decoration: none; font-size: 13px; font-weight: 600; transition: 0.2s; border-radius: 10px; margin-bottom: 5px; }
    .nav-link:hover, .nav-link.active-link { color: var(--accent); background: var(--accent-hover); }
    .logout { margin-top: auto; color: var(--danger-text); background: rgba(231, 76, 60, 0.05); }
    
    .container { max-width: 500px; width: 100%; margin: 20px auto; padding: 0 15px; }
    .tab-content { display: none; animation: fadeIn 0.3s; }
    .tab-content.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
    
    .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 15px 0; }
    .btn-flex { display: flex; gap: 10px; margin-top: 15px; }
    
    .account-card { background: var(--account-card); border-radius: 14px; padding: 15px; margin-bottom: 12px; border: 1px solid var(--input-border); display: flex; justify-content: space-between; align-items: center; }
    .account-card .name { font-weight: 700; color: var(--text-main); font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
    .log-box { background: var(--log-bg); border-radius: 12px; padding: 12px; max-height: 200px; overflow-y: auto; font-family: monospace; font-size: 11px; color: var(--log-text); border: 1px solid var(--input-border); margin-bottom: 15px; white-space: pre-wrap; word-break: break-word;}
    .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 900; display: none; }
    .overlay.active { display: block; }
    .limit-badge { background: var(--accent-hover); color: var(--accent); padding: 10px 15px; border-radius: 10px; font-size: 12px; border: 1px solid var(--border-light); margin-bottom: 20px; display: flex; align-items: center; gap: 8px; font-weight: 600;}
    
    .plan-box { background: var(--card-bg); border: 1px solid var(--input-border); border-radius: 14px; padding: 20px; margin-bottom: 15px; text-align: center; transition: 0.3s; position: relative; overflow: hidden;}
    .plan-box:hover { border-color: var(--coin-color); transform: translateY(-3px); }
    .plan-title { font-size: 13px; font-weight: 800; color: var(--text-muted); margin-bottom: 5px; }
    .plan-price { font-size: 24px; color: var(--text-main); font-weight: 800; margin-bottom: 12px; display:flex; justify-content:center; align-items:center; gap:5px;}
    .plan-price span { font-size: 12px; color: var(--text-muted); font-weight: 500;}
    .plan-feature { font-size: 12px; color: var(--text-main); margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 6px;}
    .plan-feature svg { color: var(--success-text); width: 14px; height: 14px;}
    .plan-vip { border-color: rgba(255, 65, 108, 0.5); background: linear-gradient(180deg, rgba(255, 65, 108, 0.05) 0%, transparent 100%); }
    .plan-vip .plan-title { color: #ff416c; }
    .plan-vip::before { content: 'HOT'; position: absolute; top: 10px; right: -25px; background: #ff416c; color: #fff; font-size: 10px; font-weight: 800; padding: 3px 25px; transform: rotate(45deg); }
    
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
    
    .switch-wrap { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--account-card); border-radius: 12px; border: 1px solid var(--input-border); }
    .switch-label { display: flex; align-items: center; gap: 8px; color: var(--text-main); font-size: 13px; font-weight: 600; }
    .switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink:0;}
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--switch-bg); transition: .4s; border-radius: 34px; }
    .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: #fff; transition: .4s; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.2);}
    input:checked + .slider { background-color: var(--accent); }
    input:checked + .slider:before { transform: translateX(20px); }
</style>
</head>
<body>

<nav class="navbar">
    <div class="nav-left">
        <button class="menu-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg></button>
        <div class="logo">Za <span>Tools</span></div>
    </div>
    <button class="theme-toggle-btn" onclick="toggleTheme()">
        <svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"></svg>
    </button>
</nav>
<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

<div class="sidebar" id="sidebar">
    <button class="close-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
    <div class="user-tag">
        @{{ current_user }}
        <div class="plan-badge">Gói {{ plan_name }}</div>
        <div class="wallet-balance" id="wallet-display-sidebar"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> {{ "{:,}".format(balance) }} </div>
        <div class="expiry">Hạn gói: <span style="color:var(--success-text);">{{ expiry_info }}</span></div>
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
    {% if flash_msg %}
        <div class="msg {{ flash_type }}">
            {% if flash_type == 'success' %} <svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            {% else %} <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> {% endif %}
            {{ flash_msg }}
        </div>
    {% endif %}

    <div id="tab-treo" class="tab-content active">
        <div class="limit-badge"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> Đang chạy: {{ running_count }}/{{ max_tokens }} Slot</div>
        <form method="POST">
            <div class="card">
                <div class="card-title">
                    <span style="display:flex; align-items:center; gap:8px;"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M20 14.66V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5.34"></path></svg> Thiết lập kết nối</span>
                </div>
                <div class="input-group"><label>Tên gợi nhớ (Nếu lưu)</label><input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp..."></div>
                <div class="input-group"><label>Discord Token</label><input type="text" name="token" required placeholder="Nhập Token của bạn..."></div>
                <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required></div>
                <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required></div>
                
                <div style="border: 1px dashed var(--accent); padding: 15px; border-radius: 12px; margin-bottom: 15px; background: rgba(102, 252, 241, 0.02);">
                    <div style="color: var(--accent); font-size: 12px; font-weight: 800; margin-bottom: 10px; text-transform: uppercase;"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> Cấu hình Custom RPC (Phông bạt Profile)</div>
                    
                    <div class="input-group">
                        <label>Application ID (Bắt buộc để hiện Ảnh & Nút)</label>
                        <input type="text" name="rpc_app_id" placeholder="Lấy số ID ở Discord Developer Portal...">
                    </div>
                    
                    <div class="input-group"><label>Tiêu đề Game</label><input type="text" name="status_text" placeholder="VD: ZaTools Premium..."></div>
                    
                    <div style="display:flex; gap:10px;">
                        <div class="input-group" style="flex:1;"><label>Dòng chi tiết 1</label><input type="text" name="rpc_details" placeholder="VD: Đang leo Rank..."></div>
                        <div class="input-group" style="flex:1;"><label>Dòng chi tiết 2</label><input type="text" name="rpc_state" placeholder="VD: Trận 5/10..."></div>
                    </div>
                    
                    <div class="input-group"><label>Link Ảnh Lớn (HTTPS)</label><input type="text" name="rpc_image" placeholder="https://i.imgur.com/..."></div>
                    
                    <div style="display:flex; gap:10px;">
                        <div class="input-group" style="flex:1;"><label>Tên Nút 1</label><input type="text" name="rpc_b1_name" placeholder="VD: Facebook"></div>
                        <div class="input-group" style="flex:1;"><label>Link Nút 1</label><input type="text" name="rpc_b1_url" placeholder="https://..."></div>
                    </div>
                    
                    <div style="display:flex; gap:10px;">
                        <div class="input-group" style="flex:1;"><label>Tên Nút 2</label><input type="text" name="rpc_b2_name" placeholder="VD: Thuê Tool Ngay"></div>
                        <div class="input-group" style="flex:1;"><label>Link Nút 2</label><input type="text" name="rpc_b2_url" placeholder="https://..."></div>
                    </div>
                </div>
                
                <div class="options-grid">
                    <div class="switch-wrap"><div class="switch-label">Mute</div><label class="switch"><input type="checkbox" name="mute" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Deaf</div><label class="switch"><input type="checkbox" name="deaf" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Video (Cam ảo)</div><label class="switch"><input type="checkbox" name="video"><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Stream (Live ảo)</div><label class="switch"><input type="checkbox" name="stream"><span class="slider"></span></label></div>
                </div>

                <div class="btn-flex">
                    <button type="submit" formaction="/start" class="btn btn-primary">CHẠY NGAY</button>
                    <button type="submit" formaction="/save_profile" class="btn btn-success">LƯU LẠI</button>
                </div>
            </div>
        </form>

        <div class="card">
            <div class="card-title">
                <span style="display:flex; align-items:center; gap:8px;"><svg class="svg-icon" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect></svg> Luồng đang chạy</span>
                {% if running_count > 0 %}
                <form method="POST" action="/stop_all" style="margin:0;"><button type="submit" class="btn btn-danger" style="padding: 6px 12px; font-size: 11px;">DỪNG HẾT</button></form>
                {% endif %}
            </div>
            {% for key, bot in bot_items %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--accent); width:16px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> {{ bot.get('display_name', 'Đang kết nối...') }}</div>
                    <div style="font-size:11px; color:var(--success-text); margin-left: 22px;" id="status-{{ loop.index0 }}">Đang kết nối...</div>
                </div>
                <form method="POST" action="/stop"><input type="hidden" name="bot_key" value="{{ key }}"><button type="submit" class="btn btn-danger"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg></button></form>
            </div>
            {% endfor %}
            {% if not bot_items %}<div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 10px 0;">Trống.</div>{% endif %}
        </div>
        
        <div class="card">
            <div class="card-title" style="justify-content: space-between;">
                <span style="display:flex; align-items:center; gap:8px;"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg> Nhật Ký (Live)</span>
                <form method="POST" action="/refresh" style="margin:0;"><input type="hidden" name="tab" value="treo"><button type="submit" class="btn btn-primary" style="padding: 5px 10px; font-size: 10px;"><svg class="svg-icon" viewBox="0 0 24 24" style="width:12px; height:12px;"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> LÀM MỚI</button></form>
            </div>
            <div class="log-box" id="live-log-box">Đang chờ hệ thống...</div>
        </div>
    </div>

    <div id="tab-saved" class="tab-content">
        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg> Kho dữ liệu cá nhân</div>
            {% for profile in saved_profiles %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" viewBox="0 0 24 24" style="color:#c5a059; width:16px; height:16px;"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path></svg> {{ profile.profile_name }}</div>
                    <div style="font-size:11px; color:var(--text-muted); margin-left: 22px;">Máy chủ: {{ profile.guild_id }}</div>
                </div>
                <div style="display:flex; gap:8px;">
                    <form method="POST" action="/start_saved"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-success" style="padding:10px;"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></button></form>
                    <form method="POST" action="/delete_profile"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-danger" style="padding:10px;"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button></form>
                </div>
            </div>
            {% endfor %}
            {% if not saved_profiles %}<div style="text-align:center; font-size:12px; color:var(--text-muted); padding: 20px 0;">Chưa có tài khoản lưu trữ.</div>{% endif %}
        </div>
    </div>

    <div id="tab-premium" class="tab-content">
        <div class="tab-header">
            <div class="tab-btn active" id="btn-nap" onclick="switchSubTab('nap')">NẠP COIN</div>
            <div class="tab-btn" id="btn-mua" onclick="switchSubTab('mua')">CỬA HÀNG GÓI</div>
        </div>
        
        <div id="sub-nap" class="card">
            <div class="card-title" style="color: var(--coin-color);"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> NẠP SỐ DƯ (1 VNĐ = 1 COIN)</div>
            <p style="font-size:12px; color:var(--text-muted); text-align:center; margin-bottom:15px;">Quét QR chuyển khoản. Tiền sẽ vào ví tự động sau 5s.</p>
            
            <div class="input-group"><input type="number" id="nap_amount" placeholder="Nhập số tiền muốn nạp..." min="10000" step="10000"></div>
            <button onclick="generateNapQR()" class="btn btn-primary" style="margin-bottom:20px;">TẠO MÃ NẠP TIỀN</button>
            
            <div id="qr_nap_area" style="display: none; text-align: center; border-top: 1px dashed var(--input-border); padding-top: 20px; margin-top:20px;">
                <img id="qr_nap_img" src="" style="width: 220px; max-width: 100%; border-radius: 12px; border: 2px solid var(--coin-color);">
                <div style="margin-top: 15px; font-size: 13px; background: var(--input-bg); padding: 12px; border-radius: 10px;">
                    <span style="color:var(--text-muted);">Nội dung nạp tiền:</span><br>
                    <b style="color:var(--success-text); font-size: 16px; letter-spacing: 1px;">ZATOOLS <span id="clean_username"></span></b>
                </div>
                
                <div id="payment_status" class="msg pulsing" style="display:none; margin-top:15px; background:rgba(241, 196, 15, 0.1); color:var(--coin-color); border:1px solid rgba(241, 196, 15, 0.3);">
                    <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                    Đang chờ ngân hàng xử lý...
                </div>
            </div>
        </div>
        
        <div id="sub-mua" class="card" style="display: none;">
            <div class="card-title" style="color: var(--plan-text);"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 22 22 7 12 2"></polygon><polyline points="2 7 12 7 22 7"></polyline><polyline points="12 22 12 7"></polyline></svg> MUA GÓI (30 NGÀY)</div>
            
            <div class="plan-box">
                <div class="plan-title">GÓI STARTER</div>
                <div class="plan-price"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--coin-color);"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> 20,000</div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo tối đa 2 Token</div>
                <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="STARTER"><button type="submit" class="btn btn-buy">DÙNG COIN MUA</button></form>
            </div>
            
            <div class="plan-box">
                <div class="plan-title" style="color: var(--accent);">GÓI PRO</div>
                <div class="plan-price"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--coin-color);"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> 40,000</div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo tối đa 5 Token</div>
                <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="PRO"><button type="submit" class="btn btn-buy">DÙNG COIN MUA</button></form>
            </div>

            <div class="plan-box plan-vip">
                <div class="plan-title">GÓI VIP</div>
                <div class="plan-price"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--coin-color);"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> 300,000</div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo tối đa 35 Token</div>
                <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="VIP"><button type="submit" class="btn btn-buy">DÙNG COIN MUA</button></form>
            </div>
        </div>
    </div>

    <div style="text-align:center; margin-top:30px; font-size:11px;">
        <a href="https://t.me/thiendangcuaanh" style="color:var(--accent); font-weight:700; text-decoration:none;">LIÊN HỆ HỖ TRỢ</a>
        <div style="color:var(--text-muted); margin-top:8px;">&copy; 2026 dangkhoi Tools. All rights reserved.</div>
    </div>
</div>

""" + THEME_SCRIPT + """
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
        
        fetchLiveLogs();
        setInterval(fetchLiveLogs, 3000);
    };
    
    function fetchLiveLogs() {
        if(document.getElementById('tab-treo').classList.contains('active')) {
            fetch('/api/get_logs')
            .then(res => res.json())
            .then(data => {
                const logBox = document.getElementById('live-log-box');
                if (data.log.length > 0) {
                    let newLogContent = data.log.join('\\n');
                    if (logBox.innerHTML !== newLogContent) {
                        logBox.innerHTML = newLogContent;
                        logBox.scrollTop = logBox.scrollHeight;
                    }
                } else { logBox.innerHTML = 'Đang chờ hệ thống...'; }
                
                data.status.forEach((st, index) => {
                    let statusEl = document.getElementById('status-' + index);
                    if (statusEl) {
                        if(st.connected) {
                            statusEl.innerHTML = "Treo vĩnh cửu";
                            statusEl.style.color = "var(--success-text)";
                        } else {
                            statusEl.innerHTML = "Mất kết nối / Đang xử lý...";
                            statusEl.style.color = "var(--danger-text)";
                        }
                    }
                });
            });
        }
    }
    
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
        
        let statusDiv = document.getElementById('payment_status');
        statusDiv.style.display = 'flex';
        statusDiv.className = 'msg pulsing';
        statusDiv.style.background = 'rgba(241, 196, 15, 0.1)';
        statusDiv.style.color = 'var(--coin-color)';
        statusDiv.style.borderColor = 'rgba(241, 196, 15, 0.3)';
        statusDiv.innerHTML = '<svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg> Đang chờ ngân hàng xử lý...';

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
                statusDiv.innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> Nạp thành công +${diff.toLocaleString('vi-VN')} Coin!`;
                
                document.getElementById('wallet-display-sidebar').innerHTML = `<svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> ${currentBalance.toLocaleString('vi-VN')}`;
            }
        });
    }
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
</style>
<body>
    <button class="theme-toggle-btn" onclick="toggleTheme()" style="position: absolute; top:20px; right:20px;"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"></svg></button>
    <div class="admin-container">
        <h2 style="color:var(--text-main); text-align:center; margin-bottom:25px; display:flex; justify-content:center; align-items:center; gap:10px;">
            <svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--plan-text); width:28px; height:28px;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> MẮT THẦN DANGKHOI
        </h2>
        {% if msg %}<div class="msg success">{{ msg }}</div>{% endif %}
        
        <div class="stat-box">Thành viên hệ thống: <span class="stat-val">{{ stats.users }}</span></div>
        <div class="stat-box">Token đang lưu trữ: <span class="stat-val">{{ stats.bots }}</span></div>
        <div class="stat-box">Luồng cày ngầm (Active): <span class="stat-val" style="color:var(--success-text);">{{ stats.running }}</span></div>
        <div class="stat-box">Lợi nhuận (Tổng Coin đã nạp): <span class="stat-val" style="color:var(--coin-color);">{{ "{:,}".format(stats.total_money) }} đ</span></div>
        
        <div class="action-box">
            <h3 style="color:var(--accent); font-size:14px; margin-bottom:15px; text-transform:uppercase;">Cộng tiền thủ công</h3>
            <form method="POST" action="/admin_action">
                <input type="hidden" name="action" value="add_coin">
                <div class="input-group"><input type="text" name="target_user" required placeholder="Nhập username khách..."></div>
                <div class="input-group"><input type="number" name="amount" required placeholder="Số Coin cần cộng..."></div>
                <button type="submit" class="btn btn-primary" style="background:var(--success-text); border:none;">XÁC NHẬN CỘNG</button>
            </form>
        </div>

        <div class="action-box" style="background: rgba(241, 196, 15, 0.05); border-color: var(--coin-color);">
            <h3 style="color:var(--coin-color); font-size:14px; margin-bottom:15px; text-transform:uppercase;">Đồng bộ SePay bị sót</h3>
            <p style="font-size:12px; color:var(--text-muted); margin-bottom:15px;">Dùng khi Webhook bị lỗi không cộng tiền cho khách. Hệ thống sẽ quyét API để bù tiền.</p>
            <form method="POST" action="/admin_action">
                <input type="hidden" name="action" value="sync_sepay">
                <button type="submit" class="btn btn-primary" style="background:var(--coin-color); color:#000; border:none;">QUÉT & ĐỒNG BỘ NGAY</button>
            </form>
        </div>
        <div style="text-align:center; margin-top:20px;"><a href="/" style="color:var(--text-muted); text-decoration:none; font-weight:600;">← Trở về trang chủ</a></div>
    </div>
    """ + THEME_SCRIPT + """
</body>
</html>
"""

# ================== HÀM CHẠY LUỒNG VÀ LOGGING (FIX ẢNH BẰNG MP:) ==================
def run_bot(bot_key, config, username):
    token = config.get('token')
    guild_id = config.get('guild_id')
    channel_id = config.get('channel_id')
    
    mute = str(config.get('mute', 'False')).lower() in ['true', 'on', '1']
    deaf = str(config.get('deaf', 'False')).lower() in ['true', 'on', '1']
    video = str(config.get('video', 'False')).lower() in ['true', 'on', '1']
    stream = str(config.get('stream', 'False')).lower() in ['true', 'on', '1']

    ws = None; last_seq = None; heartbeat_interval = 41250; connected = False
    start_time = int(time.time() * 1000) # ĐẾM GIỜ CHƠI TỪ LÚC CHẠY BOT

    if username not in user_bots: user_bots[username] = {}
    user_bots[username][bot_key] = {'connected': False, 'log': [], 'running': True, 'display_name': 'Đang kết nối...'}

    def add_log(msg):
        if username in user_bots and bot_key in user_bots[username]:
            timestamp = time.strftime('%H:%M:%S')
            user_bots[username][bot_key]['log'].append(f"[{timestamp}] {msg}")
            if len(user_bots[username][bot_key]['log']) > 50: user_bots[username][bot_key]['log'] = user_bots[username][bot_key]['log'][-50:]

    def update_status(st):
        if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['connected'] = st

    def send_voice_update(ws_client, init_stream=False):
        if not ws_client or not ws_client.keep_running: return
        try: 
            ws_client.send(json.dumps({
                "op": 4, 
                "d": {
                    "guild_id": guild_id, 
                    "channel_id": channel_id, 
                    "self_mute": mute, 
                    "self_deaf": deaf, 
                    "self_video": video
                }
            }))
            
            if stream and init_stream:
                def fire_stream():
                    if ws_client and ws_client.keep_running:
                        try:
                            ws_client.send(json.dumps({
                                "op": 18,
                                "d": {
                                    "type": "guild",
                                    "guild_id": guild_id,
                                    "channel_id": channel_id,
                                    "preferred_region": None
                                }
                            }))
                            add_log("🔴 Đã bung cờ Đang Trực Tiếp (Live ảo)!")
                        except: pass
                threading.Timer(1.5, fire_stream).start()
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
            
            # XÂY DỰNG KHỐI CUSTOM RPC THẦN THÁNH BẰNG OP 2
            presence_data = {"status": "online", "since": 0, "activities": [], "afk": False}
            
            status_text = config.get('status_text', '').strip()
            rpc_app_id = config.get('rpc_app_id', '').strip()
            
            if status_text:
                activity = {
                    "name": status_text,
                    "type": 0,
                    "application_id": rpc_app_id if rpc_app_id else "1504310281625403544",
                    "timestamps": {"start": start_time} # 🕒 THÊM ĐẾM GIỜ Ở ĐÂY
                }
                
                if config.get('rpc_details'): activity["details"] = config.get('rpc_details')
                if config.get('rpc_state'): activity["state"] = config.get('rpc_state')
                
                rpc_image = config.get('rpc_image', '').strip()
                # 🛠️ FIX LỖI ẢNH: Thêm chữ "mp:" vào trước link trả về
                if rpc_image.startswith('http') and rpc_app_id:
                    try:
                        res = requests.post(
                            f"https://discord.com/api/v9/applications/{rpc_app_id}/external-assets",
                            headers={"Authorization": token, "Content-Type": "application/json"},
                            json={"urls": [rpc_image]},
                            timeout=5
                        )
                        if res.status_code == 200:
                            rpc_image = f"mp:{res.json()[0]['external_asset_path']}"
                    except: pass
                
                if rpc_image:
                    activity["assets"] = {"large_image": rpc_image, "large_text": status_text}
                
                buttons = []
                metadata_urls = []
                if config.get('rpc_b1_name') and config.get('rpc_b1_url'):
                    buttons.append(config.get('rpc_b1_name'))
                    metadata_urls.append(config.get('rpc_b1_url'))
                if config.get('rpc_b2_name') and config.get('rpc_b2_url'):
                    buttons.append(config.get('rpc_b2_name'))
                    metadata_urls.append(config.get('rpc_b2_url'))
                    
                if buttons:
                    activity["buttons"] = buttons
                    activity["metadata"] = {"button_urls": metadata_urls}
                    
                presence_data["activities"].append(activity)
                add_log("🎨 Gắn khối Custom RPC thành công!")
                
            ws_client.send(json.dumps({
                "op": 2, 
                "d": {
                    "token": token, 
                    "properties": {"os": "Linux", "browser": "Chrome", "device": "ZaTools"}, 
                    "presence": presence_data,
                    "compress": False
                }
            }))
            add_log("📤 Đã kết nối Gateway, đang tải dữ liệu...")
            
        elif op == 0:
            if t == 'READY':
                d_name = data['d']['user']['username']
                if username in user_bots and bot_key in user_bots[username]: user_bots[username][bot_key]['display_name'] = d_name
                add_log(f"🎯 Đăng nhập thành công: {d_name}")
                send_voice_update(ws_client, init_stream=True)
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id and not connected:
                    connected = True; update_status(True)
                    add_log("✅ Đã tham gia phòng thoại vĩnh cửu!")
                elif d.get('channel_id') is None and connected:
                    connected = False; update_status(False)
                    add_log("⚠️ Bị văng khỏi phòng! Đang kết nối lại...")
                    send_voice_update(ws_client, init_stream=True)
        elif op == 9: ws_client.close()

    def on_close(ws_client, code, msg):
        nonlocal connected
        if connected: connected = False; update_status(False)
        add_log("🔌 Mất kết nối! Tự động thử lại sau 5s...")
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
            time.sleep(30)
            if ws and ws.keep_running and connected: send_voice_update(ws, init_stream=False)

    def start_ws():
        nonlocal ws
        if username not in user_bots or bot_key not in user_bots[username] or not user_bots[username][bot_key]['running']: return
        try: gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except: time.sleep(5); start_ws(); return
        add_log("🚀 Khởi tạo tiến trình...")
        ws = websocket.WebSocketApp(gateway + "/?v=9&encoding=json", on_message=on_message, on_error=on_error, on_close=on_close)
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws.run_forever()
    start_ws()

def auto_bootloader():
    try:
        for doc in accounts_collection.find():
            username = doc.get("owner"); bot_key = doc.get("bot_key")
            if not username or not bot_key: continue
            limit, _, _ = get_user_limit(username)
            if username not in user_bots: user_bots[username] = {}
            if len(user_bots[username]) >= limit: continue 
            
            config = { 
                'token': doc.get('token'), 
                'guild_id': doc.get('guild_id'), 
                'channel_id': doc.get('channel_id'), 
                'status_text': doc.get('status_text', ''),
                'rpc_app_id': doc.get('rpc_app_id', ''),
                'rpc_details': doc.get('rpc_details', ''),
                'rpc_state': doc.get('rpc_state', ''),
                'rpc_image': doc.get('rpc_image', ''),
                'rpc_b1_name': doc.get('rpc_b1_name', ''),
                'rpc_b1_url': doc.get('rpc_b1_url', ''),
                'rpc_b2_name': doc.get('rpc_b2_name', ''),
                'rpc_b2_url': doc.get('rpc_b2_url', ''),
                'mute': doc.get('mute'), 
                'deaf': doc.get('deaf'), 
                'video': doc.get('video'), 
                'stream': doc.get('stream') 
            }
            if bot_key not in user_bots[username]: threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
    except: pass
auto_bootloader()

# ================== SEPAY WEBHOOK & API ==================
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

@app.route('/api/get_logs')
def api_get_logs():
    if 'username' not in session: return jsonify({"log": [], "status": []})
    usr = session['username']
    if usr not in user_bots or not user_bots[usr]: return jsonify({"log": [], "status": []})
    
    active_bots = [(k, v) for k, v in user_bots[usr].items() if v.get('running', False)]
    if not active_bots: return jsonify({"log": [], "status": []})
        
    log_data = active_bots[0][1].get('log', [])
    status_data = [{"bot_key": k, "connected": v.get('connected', False)} for k, v in active_bots]
    return jsonify({"log": log_data, "status": status_data})

# ================== API MUA GÓI BẰNG COIN ==================
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

# ================== ROUTES ỨNG DỤNG CHÍNH ==================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    
    max_tokens, expiry_info, plan_name = get_user_limit(usr)
    db_user = users_collection.find_one({"username": usr})
    is_admin = db_user.get('is_admin', False) if db_user else False
    balance = db_user.get('balance', 0) if db_user else 0
    
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    log = active_bots[0][1].get('log', []) if active_bots else []
    
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, balance=balance, plan_name=plan_name,
                                  saved_profiles=get_saved_profiles(usr), max_tokens=max_tokens, 
                                  running_count=len(active_bots), is_admin=is_admin, expiry_info=expiry_info,
                                  flash_msg=session.pop('flash_msg', None), flash_type=session.pop('flash_type', 'success'),
                                  active_tab=request.args.get('tab', 'None'), log=log)

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    max_tokens, _, _ = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    bot_key = f"{request.form.get('guild_id')}_{request.form.get('channel_id')}"
    if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
        session['flash_msg'] = f"Gói của bạn ({max_tokens} slot) đã đầy hoặc hết hạn!"
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='treo'))
        
    config = {
        'token': request.form.get('token', '').strip(),
        'guild_id': request.form.get('guild_id', '').strip(),
        'channel_id': request.form.get('channel_id', '').strip(),
        'status_text': request.form.get('status_text', '').strip(),
        'rpc_app_id': request.form.get('rpc_app_id', '').strip(),
        'rpc_details': request.form.get('rpc_details', '').strip(),
        'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(),
        'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(),
        'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(),
        'rpc_b2_url': request.form.get('rpc_b2_url', '').strip(),
        'mute': request.form.get('mute') == 'on',
        'deaf': request.form.get('deaf') == 'on',
        'video': request.form.get('video') == 'on',
        'stream': request.form.get('stream') == 'on'
    }
    
    save_storage_item(bot_key, config, usr)
    if usr not in user_bots: user_bots[usr] = {}
    if bot_key in user_bots[usr]: user_bots[usr][bot_key]['running'] = False; time.sleep(0.5)
    threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/start_saved', methods=['POST'])
def start_saved():
    usr = session.get('username')
    max_tokens, _, _ = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    prof_id = request.form.get('profile_id')
    try: prof = saved_profiles_collection.find_one({"_id": prof_id}) or saved_profiles_collection.find_one({"_id": ObjectId(prof_id)})
    except: prof = None
    if prof:
        bot_key = f"{prof.get('guild_id')}_{prof.get('channel_id')}"
        if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
            session['flash_msg'] = f"Cần Mua/Gia hạn VIP để chạy! Giới hạn: {max_tokens}"
            session['flash_type'] = "error"
            return redirect(url_for('index', tab='saved'))
        
        config = {k:v for k,v in prof.items() if k not in ['_id', 'owner', 'profile_name']}
        config['bot_key'] = bot_key
        save_storage_item(bot_key, config, usr)
        if usr not in user_bots: user_bots[usr] = {}
        if bot_key in user_bots[usr]: user_bots[usr][bot_key]['running'] = False; time.sleep(0.5)
        threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/save_profile', methods=['POST'])
def save_profile():
    prof_name = request.form.get('profile_name', '').strip() or f"Config {int(time.time())}"
    config = {
        'profile_name': prof_name,
        'owner': session['username'],
        '_id': str(int(time.time())),
        'token': request.form.get('token', '').strip(),
        'guild_id': request.form.get('guild_id', '').strip(),
        'channel_id': request.form.get('channel_id', '').strip(),
        'status_text': request.form.get('status_text', '').strip(),
        'rpc_app_id': request.form.get('rpc_app_id', '').strip(),
        'rpc_details': request.form.get('rpc_details', '').strip(),
        'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(),
        'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(),
        'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(),
        'rpc_b2_url': request.form.get('rpc_b2_url', '').strip(),
        'mute': request.form.get('mute') == 'on',
        'deaf': request.form.get('deaf') == 'on',
        'video': request.form.get('video') == 'on',
        'stream': request.form.get('stream') == 'on'
    }
    saved_profiles_collection.insert_one(config)
    session['flash_msg'] = "Đã lưu vào Kho dữ liệu!"
    return redirect(url_for('index', tab='saved'))

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
        return render_template_string(HTML_AUTH, mode='login', error="Sai thông tin đăng nhập!")
    return render_template_string(HTML_AUTH, mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usr = request.form['username'].strip().lower()
        pin = request.form['pin'].strip()
        if users_collection.find_one({"username": usr}): return render_template_string(HTML_AUTH, mode='register', error="Tên đăng nhập đã tồn tại!")
        users_collection.insert_one({"username": usr, "password": generate_password_hash(request.form['password'].strip()), "security_pin": pin, "max_tokens": 1, "expiry_date": 0, "balance": 0})
        return render_template_string(HTML_AUTH, mode='login', success="Đăng ký thành công! Hãy lưu kỹ mã PIN để lấy lại pass nhé.")
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
            return render_template_string(HTML_AUTH, mode='login', success="Đã đổi mật khẩu thành công!")
        else:
            return render_template_string(HTML_AUTH, mode='forgot', error="Tài khoản hoặc mã PIN không đúng!")
    return render_template_string(HTML_AUTH, mode='forgot')

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

@app.route('/stop_all', methods=['POST'])
def stop_all():
    usr = session.get('username')
    if usr in user_bots:
        for bot_key in list(user_bots[usr].keys()):
            delete_storage_item(bot_key, usr)
            user_bots[usr][bot_key]['running'] = False
            del user_bots[usr][bot_key]
    session['flash_msg'] = "Đã tắt thành công toàn bộ Token!"
    session['flash_type'] = "success"
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
    return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/ping')
def ping(): return "ok"
@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

# ================== TRANG ADMIN PANEL ==================
@app.route('/admin_dangkhoi')
def admin_dashboard():
    if session.get('username') != '28012010': return redirect(url_for('index'))
    total_users = users_collection.count_documents({})
    total_bots = accounts_collection.count_documents({})
    active_running = sum(1 for usr, bots in user_bots.items() for k, d in bots.items() if d.get('running', False))
    
    pipeline = [{"$group": {"_id": None, "total": {"$sum": "$amount"}}}]
    res = list(transactions_collection.aggregate(pipeline))
    total_money = res[0]["total"] if res else 0
    
    stats = {"users": total_users, "bots": total_bots, "running": active_running, "total_money": total_money}
    msg = session.pop('admin_msg', None)
    return render_template_string(HTML_ADMIN, stats=stats, msg=msg)

@app.route('/admin_action', methods=['POST'])
def admin_action():
    if session.get('username') != '28012010': return redirect(url_for('index'))
    action = request.form.get('action')
    
    if action == 'add_coin':
        t_user = request.form.get('target_user').strip().lower()
        amount = int(request.form.get('amount', 0))
        u = users_collection.find_one({"username": t_user})
        if u:
            users_collection.update_one({"username": t_user}, {"$inc": {"balance": amount}})
            session['admin_msg'] = f"Đã cộng {amount} Coin cho {t_user}!"
        else:
            session['admin_msg'] = "Không tìm thấy user này!"
            
    elif action == 'sync_sepay':
        try:
            headers = {"Authorization": f"Bearer {SEPAY_API_KEY}"}
            r = requests.get("https://my.sepay.vn/userapi/transactions/list", headers=headers, timeout=10)
            data = r.json()
            synced_count = 0
            if 'transactions' in data:
                for t in data['transactions']:
                    tid = str(t['id'])
                    amt = int(float(t['amount_in']))
                    content = t['transaction_content']
                    if process_sepay_transaction(tid, amt, content):
                        synced_count += 1
            session['admin_msg'] = f"Đồng bộ hoàn tất! Tìm thấy và cộng bù {synced_count} giao dịch bị sót."
        except Exception as e:
            session['admin_msg'] = f"Lỗi đồng bộ: {str(e)}"
            
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
