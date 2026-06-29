from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading, json, time, requests, websocket, os
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash, check_password_hash
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "za_tools_final_v17_light_dark"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

# ================== CẤU HÌNH DATABASE ==================
MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"
try:
    client = MongoClient(MONGO_URI)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    saved_profiles_collection = db["saved_profiles"]
    
    admin_user = "28012010"
    admin_pass = "itachi5867"
    if not users_collection.find_one({"username": admin_user}):
        users_collection.insert_one({"username": admin_user, "password": generate_password_hash(admin_pass), "max_tokens": 9999, "is_admin": True})
    else:
        users_collection.update_one({"username": admin_user}, {"$set": {"max_tokens": 9999, "is_admin": True}})
        
    print("✅ MongoDB OK! Đã kích hoạt V17 - Tích hợp Light/Dark Mode.")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}

DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

# ================== HÀM KIỂM TRA THỜI HẠN GÓI ==================
def get_user_limit(username):
    user = users_collection.find_one({"username": username})
    if not user: return 1, "Gói Free"
    if user.get('is_admin'): return 9999, "Vĩnh viễn (Admin)"
    
    expiry_ts = user.get('expiry_date', 0)
    if expiry_ts > 0:
        if int(time.time()) > expiry_ts:
            users_collection.update_one({"username": username}, {"$set": {"max_tokens": 1, "expiry_date": 0}})
            return 1, "Đã hết hạn"
        else:
            return user.get('max_tokens', 1), time.strftime('%d/%m/%Y %H:%M', time.localtime(expiry_ts))
    return 1, "Gói Free"

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
    try: accounts_collection.update_one({"bot_key": bot_key}, {"$set": {**config, "owner": username}}, upsert=True)
    except: pass

def delete_storage_item(bot_key, username):
    try: accounts_collection.delete_one({"bot_key": bot_key, "owner": username})
    except: pass

# ================== CẤU TRÚC HTML & CSS BIẾN SÁNG TỐI ==================
HTML_HEAD = """
<!DOCTYPE html>
<html lang="vi">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0, maximum-scale=1.0, user-scalable=no">
    <script>
        // KIỂM TRA THEME TỪ TRƯỚC KHI LOAD HTML ĐỂ TRÁNH NHÁY MÀN HÌNH MÀU ĐEN
        const savedTheme = localStorage.getItem('za_theme') || 'dark';
        if (savedTheme === 'light') document.documentElement.setAttribute('data-theme', 'light');
    </script>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;600;800&display=swap');
        
        /* ĐỊNH NGHĨA BIẾN MÀU CHO DARK MODE (MẶC ĐỊNH) */
        :root {
            --bg-main: #07090f;
            --text-main: #fff;
            --text-muted: #85929e;
            --accent: #66fcf1;
            --accent-hover: rgba(102, 252, 241, 0.1);
            --card-bg: rgba(21, 26, 33, 0.6);
            --border-light: rgba(102, 252, 241, 0.1);
            --input-bg: rgba(11, 12, 16, 0.8);
            --input-border: rgba(47, 62, 70, 0.8);
            --btn-bg: linear-gradient(135deg, #162447, #1f4068);
            --nav-bg: rgba(11, 12, 16, 0.9);
            --sidebar-bg: rgba(21, 26, 33, 0.98);
            --account-card: rgba(11, 12, 16, 0.5);
            --log-bg: rgba(0, 0, 0, 0.5);
            --log-text: #4cdf8b;
            --shadow: rgba(0,0,0,0.3);
            --switch-bg: rgba(47, 62, 70, 0.8);
            --success-text: #2ecc71;
            --danger-text: #e74c3c;
        }

        /* ĐỊNH NGHĨA BIẾN MÀU CHO LIGHT MODE */
        [data-theme="light"] {
            --bg-main: #f0f2f5;
            --text-main: #1e293b;
            --text-muted: #64748b;
            --accent: #0284c7;
            --accent-hover: rgba(2, 132, 199, 0.1);
            --card-bg: rgba(255, 255, 255, 0.9);
            --border-light: rgba(15, 23, 42, 0.1);
            --input-bg: #ffffff;
            --input-border: #cbd5e1;
            --btn-bg: linear-gradient(135deg, #0284c7, #0369a1);
            --nav-bg: rgba(255, 255, 255, 0.95);
            --sidebar-bg: rgba(255, 255, 255, 0.98);
            --account-card: #f8fafc;
            --log-bg: #f1f5f9;
            --log-text: #059669;
            --shadow: rgba(0,0,0,0.08);
            --switch-bg: #cbd5e1;
            --success-text: #059669;
            --danger-text: #dc2626;
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
        
        .svg-icon { width: 18px; height: 18px; stroke-width: 2; stroke: currentColor; fill: none; stroke-linecap: round; stroke-linejoin: round; display: inline-flex; flex-shrink: 0; vertical-align: middle;}
        
        .msg { padding: 14px; border-radius: 12px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 8px; animation: slideDown 0.3s ease;}
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
        .msg.success { background: rgba(46, 204, 113, 0.1); color: var(--success-text); border: 1px solid rgba(46, 204, 113, 0.2); }
        .msg.error { background: rgba(231, 76, 60, 0.1); color: var(--danger-text); border: 1px solid rgba(231, 76, 60, 0.2); }
        
        .switch-wrap { display: flex; align-items: center; justify-content: space-between; padding: 12px; background: var(--account-card); border-radius: 12px; border: 1px solid var(--input-border); }
        .switch-label { display: flex; align-items: center; gap: 8px; color: var(--text-main); font-size: 13px; font-weight: 600; }
        .switch { position: relative; display: inline-block; width: 44px; height: 24px; flex-shrink:0;}
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--switch-bg); transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 18px; width: 18px; left: 3px; bottom: 3px; background-color: #fff; transition: .4s; border-radius: 50%; box-shadow: 0 2px 4px rgba(0,0,0,0.2);}
        input:checked + .slider { background-color: var(--accent); }
        input:checked + .slider:before { transform: translateX(20px); }

        .theme-toggle-btn { background: var(--account-card); border: 1px solid var(--input-border); color: var(--text-main); border-radius: 10px; width: 40px; height: 40px; display: flex; align-items: center; justify-content: center; cursor: pointer; transition: 0.3s; flex-shrink:0;}
        .theme-toggle-btn:hover { background: var(--accent-hover); color: var(--accent); }

        @media (max-width: 600px) {
            .card { padding: 20px; border-radius: 16px;}
            .btn-flex { flex-direction: column; gap: 10px; }
        }
    </style>
"""

# ================== GIAO DIỆN ĐĂNG NHẬP ==================
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
    .btn-oauth { background: #5865F2; color: #fff; text-decoration:none; border:none;}
    .switch-link { text-align: center; margin-top: 20px; font-size: 13px; color: var(--text-muted); }
    .switch-link a { color: var(--accent); text-decoration: none; font-weight: 600; }
    
    .theme-corner { position: absolute; top: 20px; right: 20px; }
</style>
</head>
<body>
    <button class="theme-toggle-btn theme-corner" onclick="toggleTheme()" title="Chuyển chế độ Sáng/Tối">
        <svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
    </button>

    <div class="card auth-container">
        <div class="logo">Za <span>Tools</span></div>
        <div class="sub">Hệ thống treo voice siêu tốc</div>
        {% if error %}<div class="msg error"><svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> {{ error }}</div>{% endif %}
        {% if success %}<div class="msg success"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg> {{ success }}</div>{% endif %}

        <form method="POST" action="{{ '/login' if mode == 'login' else '/register' }}">
            <div class="input-group"><label>Tài khoản</label><input type="text" name="username" required placeholder="Tên đăng nhập..."></div>
            <div class="input-group"><label>Mật khẩu</label><input type="password" name="password" required placeholder="••••••••"></div>
            <button type="submit" class="btn btn-primary">
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M15 3h4a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2h-4"></path><polyline points="10 17 15 12 10 7"></polyline><line x1="15" y1="12" x2="3" y2="12"></line></svg>
                {{ 'ĐĂNG NHẬP' if mode == 'login' else 'TẠO TÀI KHOẢN' }}
            </button>
        </form>
        <div class="divider">Hoặc</div>
        <a href="/login/discord" class="btn btn-oauth">
            <svg class="svg-icon" viewBox="0 0 24 24" fill="currentColor" stroke="none"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg>
            Đăng nhập bằng Discord
        </a>
        <div class="switch-link">
            {% if mode == 'login' %}Chưa có tài khoản? <a href="/register">Tạo ngay</a>
            {% else %}Đã có tài khoản? <a href="/login">Vào đăng nhập</a>{% endif %}
        </div>
    </div>

    <script>
        function toggleTheme() {
            const root = document.documentElement;
            const isLight = root.getAttribute('data-theme') === 'light';
            if (isLight) {
                root.removeAttribute('data-theme');
                localStorage.setItem('za_theme', 'dark');
                document.getElementById('theme-icon').innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
            } else {
                root.setAttribute('data-theme', 'light');
                localStorage.setItem('za_theme', 'light');
                document.getElementById('theme-icon').innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
            }
        }
        window.addEventListener('DOMContentLoaded', () => {
            const isLight = document.documentElement.getAttribute('data-theme') === 'light';
            const iconBtn = document.getElementById('theme-icon');
            if(iconBtn) {
                if(isLight) iconBtn.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
                else iconBtn.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
            }
        });
    </script>
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD CHÍNH ==================
HTML_MAIN = HTML_HEAD + """
<title>Za Tools - Premium Dashboard</title>
<style>
    .navbar { background: var(--nav-bg); backdrop-filter: blur(10px); padding: 15px 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-light); position: sticky; top: 0; z-index: 100; transition: 0.3s;}
    .nav-left { display: flex; align-items: center; }
    .menu-btn { background: none; border: none; color: var(--text-main); padding: 5px; cursor: pointer; margin-right: 12px; }
    .logo { color: var(--text-main); font-size: 20px; font-weight: 800; letter-spacing: -0.5px;}
    .logo span { color: var(--accent); }
    
    .sidebar { position: fixed; left: -260px; top: 0; width: 260px; height: 100%; background: var(--sidebar-bg); box-shadow: 2px 0 15px var(--shadow); transition: 0.3s; z-index: 1000; padding: 70px 20px 20px; border-right: 1px solid var(--border-light); display: flex; flex-direction: column; }
    .sidebar.active { left: 0; }
    .close-btn { position: absolute; right: 15px; top: 15px; color: var(--text-muted); font-size: 24px; cursor: pointer; background: none; border: none; }
    
    .user-tag { background: var(--account-card); padding: 12px; border-radius: 12px; text-align: center; color: var(--text-main); font-size: 14px; font-weight: 600; margin-bottom: 20px; border: 1px solid var(--border-light); }
    .user-tag span { color: #ff416c; font-size: 11px; display: block; margin-top: 4px;}
    .user-tag .expiry { color: var(--success-text); font-size: 10px; margin-top: 2px; }
    
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
    
    .log-box { background: var(--log-bg); border-radius: 12px; padding: 12px; max-height: 150px; overflow-y: auto; font-family: monospace; font-size: 11px; color: var(--log-text); border: 1px solid var(--input-border); margin-bottom: 15px; }
    
    .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 900; display: none; }
    .overlay.active { display: block; }
    
    .limit-badge { background: var(--accent-hover); color: var(--accent); padding: 10px 15px; border-radius: 10px; font-size: 12px; border: 1px solid var(--border-light); margin-bottom: 20px; display: flex; align-items: center; gap: 8px; font-weight: 600;}
    
    .plan-box { background: var(--card-bg); border: 1px solid var(--input-border); border-radius: 14px; padding: 20px; margin-bottom: 15px; text-align: center; cursor: pointer; transition: 0.3s; position: relative; overflow: hidden;}
    .plan-box:hover { border-color: var(--accent); transform: translateY(-3px); }
    .plan-title { font-size: 13px; font-weight: 800; color: var(--text-muted); margin-bottom: 5px; }
    .plan-price { font-size: 24px; color: var(--text-main); font-weight: 800; margin-bottom: 12px; }
    .plan-price span { font-size: 12px; color: var(--text-muted); font-weight: 500;}
    .plan-feature { font-size: 12px; color: var(--text-main); margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 6px;}
    .plan-feature svg { color: var(--success-text); width: 14px; height: 14px;}
    .plan-vip { border-color: rgba(255, 65, 108, 0.5); background: linear-gradient(180deg, rgba(255, 65, 108, 0.05) 0%, transparent 100%); }
    .plan-vip .plan-title { color: #ff416c; }
    .plan-vip::before { content: 'HOT'; position: absolute; top: 10px; right: -25px; background: #ff416c; color: #fff; font-size: 10px; font-weight: 800; padding: 3px 25px; transform: rotate(45deg); }
    
    @media (max-width: 600px) {
        .account-card { flex-direction: column; align-items: flex-start; gap: 12px; }
        .account-card > div:last-child { width: 100%; display: flex; gap: 8px; }
        .account-card form { flex: 1; display:flex; }
        .account-card .btn { width: 100%; justify-content: center;}
        #qr_img { max-width: 100%; height: auto; }
    }
</style>
</head>
<body>

<nav class="navbar">
    <div class="nav-left">
        <button class="menu-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg></button>
        <div class="logo">Za <span>Tools</span></div>
    </div>
    <button class="theme-toggle-btn" onclick="toggleTheme()" title="Chuyển chế độ Sáng/Tối">
        <svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path></svg>
    </button>
</nav>
<div class="overlay" id="overlay" onclick="toggleSidebar()"></div>

<div class="sidebar" id="sidebar">
    <button class="close-btn" onclick="toggleSidebar()"><svg class="svg-icon" viewBox="0 0 24 24"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg></button>
    <div class="user-tag">
        @{{ current_user }}
        <span>Thành Viên {% if is_admin %}Admin{% else %}Tiêu chuẩn{% endif %}</span>
        <div class="expiry">Hạn gói: {{ expiry_info }}</div>
    </div>
    
    <a href="#" class="nav-link active-link" onclick="switchTab('treo', this)"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg> Treo Voice</a>
    <a href="#" class="nav-link" onclick="switchTab('saved', this)"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Tài khoản đã lưu</a>
    <a href="#" class="nav-link" onclick="switchTab('premium', this)" style="color: #ff416c;"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 22 22 7 12 2"></polygon><polyline points="2 7 12 7 22 7"></polyline><polyline points="12 22 12 7"></polyline></svg> Gia Hạn Premium</a>
    
    {% if is_admin %}
    <a href="/admin_dangkhoi" class="nav-link" style="color: #4cdf8b; margin-top: 15px; border-top: 1px dashed var(--input-border); padding-top: 20px;"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> Mắt Thần (Admin)</a>
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

    <!-- TAB TREO -->
    <div id="tab-treo" class="tab-content active">
        <div class="limit-badge"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> Đang chạy: {{ running_count }}/{{ max_tokens }} Slot</div>
        <form method="POST">
            <div class="card">
                <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M20 14.66V20a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V6a2 2 0 0 1 2-2h5.34"></path><polygon points="18 2 22 6 12 16 8 16 8 12 18 2"></polygon></svg> Thiết lập kết nối</div>
                <div class="input-group"><label>Tên gợi nhớ (Nếu lưu)</label><input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp..."></div>
                <div class="input-group"><label>Discord Token</label><input type="text" name="token" required placeholder="Nhập Token của bạn..."></div>
                <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required></div>
                <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required></div>
                
                <div class="options-grid">
                    <div class="switch-wrap"><div class="switch-label"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 1a3 3 0 0 0-3 3v8a3 3 0 0 0 6 0V4a3 3 0 0 0-3-3z"></path><path d="M19 10v2a7 7 0 0 1-14 0v-2"></path><line x1="12" y1="19" x2="12" y2="23"></line><line x1="8" y1="23" x2="16" y2="23"></line></svg> Mute</div><label class="switch"><input type="checkbox" name="mute" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M3 18v-6a9 9 0 0 1 18 0v6"></path><path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path></svg> Deaf</div><label class="switch"><input type="checkbox" name="deaf" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="23 7 16 12 23 17 23 7"></polygon><rect x="1" y="5" width="15" height="14" rx="2" ry="2"></rect></svg> Video</div><label class="switch"><input type="checkbox" name="video"><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label"><svg class="svg-icon" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg> Stream</div><label class="switch"><input type="checkbox" name="stream"><span class="slider"></span></label></div>
                </div>

                <div class="btn-flex">
                    <button type="submit" formaction="/start" class="btn btn-primary"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg> CHẠY NGAY</button>
                    <button type="submit" formaction="/save_profile" class="btn btn-success"><svg class="svg-icon" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> LƯU LẠI</button>
                </div>
            </div>
        </form>

        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><rect x="2" y="3" width="20" height="14" rx="2" ry="2"></rect><line x1="8" y1="21" x2="16" y2="21"></line><line x1="12" y1="17" x2="12" y2="21"></line></svg> Luồng đang chạy</div>
            {% for key, bot in bot_items %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--accent); width:16px; height:16px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> {{ bot.get('display_name', 'Đang kết nối...') }}</div>
                    <div style="font-size:11px; color:var(--success-text); margin-left: 22px; display:flex; align-items:center; gap:4px;">Treo vĩnh cửu</div>
                </div>
                <form method="POST" action="/stop"><input type="hidden" name="bot_key" value="{{ key }}"><button type="submit" class="btn btn-danger"><svg class="svg-icon" viewBox="0 0 24 24" style="margin:0;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg></button></form>
            </div>
            {% endfor %}
            {% if not bot_items %}<div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 10px 0;">Trống.</div>{% endif %}
        </div>
        <div class="card">
            <div class="card-title"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="4 17 10 11 4 5"></polyline><line x1="12" y1="19" x2="20" y2="19"></line></svg> Nhật Ký</div>
            <div class="log-box">{{ log|join('\\n') if log else 'Đang chờ hệ thống...' }}</div>
            <form method="POST" action="/refresh"><input type="hidden" name="tab" value="treo"><button type="submit" class="btn btn-primary" style="width:100%;"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="23 4 23 10 17 10"></polyline><polyline points="1 20 1 14 7 14"></polyline><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg> CẬP NHẬT TRẠNG THÁI</button></form>
        </div>
    </div>

    <!-- TAB ĐÃ LƯU -->
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

    <!-- TAB PREMIUM -->
    <div id="tab-premium" class="tab-content">
        <div class="card">
            <div class="card-title" style="color: #ff416c;"><svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 2 7 12 22 22 7 12 2"></polygon><polyline points="2 7 12 7 22 7"></polyline><polyline points="12 22 12 7"></polyline></svg> NÂNG CẤP DỊCH VỤ</div>
            <p style="font-size:12px; color:var(--text-muted); text-align:center; margin-bottom:20px;">Thanh toán bằng QR Code, hệ thống tự động nâng cấp sau 10 giây. <b style="color:var(--text-main);">Gói có hiệu lực 30 ngày.</b></p>
            
            <div class="plan-box" onclick="showQR(25000, 'STARTER')">
                <div class="plan-title">GÓI STARTER</div>
                <div class="plan-price">25.000đ <span>/ Tháng</span></div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo 2 Token cùng lúc</div>
            </div>
            
            <div class="plan-box" onclick="showQR(45000, 'PRO')">
                <div class="plan-title" style="color: var(--accent);">GÓI PRO</div>
                <div class="plan-price">45.000đ <span>/ Tháng</span></div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo 5 Token cùng lúc</div>
            </div>

            <div class="plan-box plan-vip" onclick="showQR(350000, 'VIP')">
                <div class="plan-title">GÓI VIP</div>
                <div class="plan-price">350.000đ <span>/ Tháng</span></div>
                <div class="plan-feature"><svg class="svg-icon" viewBox="0 0 24 24"><polyline points="20 6 9 17 4 12"></polyline></svg> Treo 35 Token cùng lúc</div>
            </div>

            <div id="qr_area" style="display: none; text-align: center; margin-top: 20px; border-top: 1px dashed var(--input-border); padding-top: 20px;">
                <p style="color: var(--text-main); margin-bottom: 12px; font-size:14px; font-weight: 600;">Quét mã cho gói <span id="qr_plan_name" style="color:#ff416c;"></span></p>
                <img id="qr_img" src="" style="width: 220px; max-width: 100%; height: auto; border-radius: 12px; border: 2px solid var(--accent);">
                <div style="margin-top: 15px; font-size: 13px; background: var(--input-bg); padding: 12px; border-radius: 10px;">
                    <span style="color:var(--text-muted);">App ngân hàng sẽ tự điền nội dung:</span><br>
                    <b style="color:var(--success-text); font-size: 16px; letter-spacing: 1px;">ZATOOLS {{ current_user }}</b>
                </div>
            </div>
        </div>
    </div>

    <div style="text-align:center; margin-top:30px; font-size:11px;">
        <a href="https://t.me/thiendangcuaanh" style="color:var(--accent); font-weight:700; text-decoration:none;">LIÊN HỆ HỖ TRỢ</a>
        <div style="color:var(--text-muted); margin-top:8px;">&copy; 2026 dangkhoi Tools. All rights reserved.</div>
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
        let addInfo = encodeURIComponent('ZATOOLS ' + user);
        let url = `https://img.vietqr.io/image/MB-1628012010-compact2.png?amount=${amount}&addInfo=${addInfo}&accountName=Phan%20Tran%20Dang%20Khoi`;
        document.getElementById('qr_img').src = url;
        document.getElementById('qr_plan_name').innerText = planName;
        document.getElementById('qr_area').style.display = 'block';
        window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' });
    }
    
    // JS CHO NÚT CHUYỂN THEME
    function toggleTheme() {
        const root = document.documentElement;
        const isLight = root.getAttribute('data-theme') === 'light';
        if (isLight) {
            root.removeAttribute('data-theme');
            localStorage.setItem('za_theme', 'dark');
            document.getElementById('theme-icon').innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
        } else {
            root.setAttribute('data-theme', 'light');
            localStorage.setItem('za_theme', 'light');
            document.getElementById('theme-icon').innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
        }
    }
    window.addEventListener('DOMContentLoaded', () => {
        const isLight = document.documentElement.getAttribute('data-theme') === 'light';
        const iconBtn = document.getElementById('theme-icon');
        if(iconBtn) {
            if(isLight) iconBtn.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
            else iconBtn.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
        }
    });

    setInterval(() => { fetch('/ping'); }, 15000);
</script>
</body>
</html>
"""

# ================== HÀM CHẠY LUỒNG ==================
def run_bot(bot_key, config, username):
    token, guild_id, channel_id = config['token'], config['guild_id'], config['channel_id']
    mute, deaf = config.get('mute', True), config.get('deaf', True)
    video, stream = config.get('video', False), config.get('stream', False)
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
                    w.send(json.dumps({"op": 4, "d": {"guild_id": guild_id, "channel_id": channel_id, "self_mute": mute, "self_deaf": deaf, "self_video": video, "self_stream": stream}}))
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
            
            limit, _ = get_user_limit(username)
            if username not in user_bots: user_bots[username] = {}
            if len(user_bots[username]) >= limit: continue 
            
            config = { 'token': doc['token'], 'guild_id': doc['guild_id'], 'channel_id': doc['channel_id'], 'mute': doc.get('mute', True), 'deaf': doc.get('deaf', True), 'video': doc.get('video', False), 'stream': doc.get('stream', False) }
            if bot_key not in user_bots[username]: threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
    except: pass
auto_bootloader()

# ================== SEPAY WEBHOOK (XỬ LÝ NÂNG CẤP 1 THÁNG) ==================
@app.route('/sepay_webhook', methods=['POST'])
def sepay_webhook():
    try:
        data = request.json
        if not data: return jsonify({"error": "No data"}), 400
        content = data.get('content', data.get('transferContent', '')).upper()
        amount = int(data.get('transferAmount', data.get('amount', 0)))
        
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
                    
                    if new_limit > 1: 
                        new_expiry = int(time.time()) + 2592000
                        users_collection.update_one(
                            {"username": username_part}, 
                            {"$set": {"max_tokens": new_limit, "expiry_date": new_expiry}}
                        )
        return jsonify({"success": True})
    except Exception as e: return jsonify({"error": str(e)}), 500

# ================== ROUTES ỨNG DỤNG CHÍNH ==================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    
    max_tokens, expiry_info = get_user_limit(usr)
    db_user = users_collection.find_one({"username": usr})
    is_admin = db_user.get('is_admin', False) if db_user else False
    
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    log = active_bots[0][1].get('log', []) if active_bots else []
    
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, 
                                  saved_profiles=get_saved_profiles(usr), max_tokens=max_tokens, 
                                  running_count=len(active_bots), is_admin=is_admin, expiry_info=expiry_info,
                                  flash_msg=session.pop('flash_msg', None), flash_type=session.pop('flash_type', 'success'),
                                  active_tab=request.args.get('tab', 'None'), log=log)

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    
    max_tokens, expiry_info = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    bot_key = f"{request.form['guild_id']}_{request.form['channel_id']}"
    
    if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
        session['flash_msg'] = f"Gói của bạn ({max_tokens} slot) đã đầy hoặc hết hạn!"
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
    max_tokens, _ = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    
    prof_id = request.form.get('profile_id')
    try: prof = saved_profiles_collection.find_one({"_id": prof_id}) or saved_profiles_collection.find_one({"_id": ObjectId(prof_id)})
    except: prof = None
    
    if prof:
        bot_key = f"{prof['guild_id']}_{prof['channel_id']}"
        if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
            session['flash_msg'] = f"Cần Gia Hạn VIP để chạy! Giới hạn: {max_tokens}"
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
        return render_template_string(HTML_AUTH, mode='login', error="Sai thông tin đăng nhập!")
    return render_template_string(HTML_AUTH, mode='login')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        usr = request.form['username'].strip().lower()
        if users_collection.find_one({"username": usr}): return render_template_string(HTML_AUTH, mode='register', error="Tên đăng nhập đã tồn tại!")
        users_collection.insert_one({"username": usr, "password": generate_password_hash(request.form['password'].strip()), "max_tokens": 1, "expiry_date": 0})
        return redirect(url_for('login', success="Đăng ký thành công!"))
    return render_template_string(HTML_AUTH, mode='register')

@app.route('/save_profile', methods=['POST'])
def save_profile():
    prof_name = request.form.get('profile_name', '').strip() or f"Config {int(time.time())}"
    saved_profiles_collection.insert_one({**request.form.to_dict(), "owner": session['username'], "_id": str(int(time.time())), "profile_name": prof_name})
    session['flash_msg'] = "Đã lưu vào Kho dữ liệu!"
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
    if not users_collection.find_one({"username": usr}): users_collection.insert_one({"username": usr, "oauth": "discord", "max_tokens": 1, "expiry_date": 0})
    session['username'] = usr
    return redirect(url_for('index'))

@app.route('/logout')
def logout(): session.clear(); return redirect(url_for('login'))
@app.route('/ping')
def ping(): return "ok"
@app.route('/refresh', methods=['POST'])
def refresh(): return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

# ================== TRANG ADMIN BÍ MẬT ==================
@app.route('/admin_dangkhoi')
def admin_dashboard():
    if session.get('username') != '28012010': return redirect(url_for('index'))
    total_users = users_collection.count_documents({})
    total_bots = accounts_collection.count_documents({})
    active_running = sum(1 for usr, bots in user_bots.items() for k, d in bots.items() if d.get('running', False))
    
    html = HTML_HEAD + f"""
    <title>Mắt Thần Dangkhoi</title>
    <body style="display:flex; justify-content:center; align-items:center; flex-direction:column;">
        <h1 style="color:var(--text-main); text-shadow: 0 0 20px var(--accent-hover); margin-bottom: 30px;"><svg class="svg-icon" viewBox="0 0 24 24" style="width:36px; height:36px; margin-right:12px; color:var(--accent);"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> MẮT THẦN ADMIN</h1>
        <div class="card" style="min-width: 320px; width: 90%;">
            <div style="font-size: 14px; margin-bottom: 20px; display:flex; justify-content:space-between; color:var(--text-muted); font-weight:600;">👥 Số thành viên: <b style='color:var(--text-main); font-size:18px;'>{total_users}</b></div>
            <div style="font-size: 14px; margin-bottom: 20px; display:flex; justify-content:space-between; color:var(--text-muted); font-weight:600;">🤖 Token đã nạp: <b style='color:var(--text-main); font-size:18px;'>{total_bots}</b></div>
            <div style="font-size: 14px; display:flex; justify-content:space-between; color:var(--text-muted); font-weight:600;">⚡ Luồng đang cày: <b style='color:var(--success-text); font-size:18px;'>{active_running}</b></div>
        </div>
        <a href="/" style="color:var(--accent); text-decoration:none; font-weight:700; margin-top:10px; font-size: 14px;">← QUAY LẠI HỆ THỐNG</a>
        
        <script>
            // Init theme for Admin page
            window.addEventListener('DOMContentLoaded', () => {{
                const savedTheme = localStorage.getItem('za_theme') || 'dark';
                if (savedTheme === 'light') document.documentElement.setAttribute('data-theme', 'light');
            }});
        </script>
    </body>
    </html>
    """
    return render_template_string(html)

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
