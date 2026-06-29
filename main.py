from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading, json, time, requests, websocket, os
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from werkzeug.security import generate_password_hash
from bson.objectid import ObjectId

app = Flask(__name__)
app.secret_key = "za_tools_final_v24_ultimate_luxury"
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
    print("✅ MongoDB OK! Đã kích hoạt V24 - Giao diện Đẳng cấp & Discord Login Only.")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}

SEPAY_API_KEY = 'ZYIBFUMXFG6PJKXA0CNYCIQAKROTMD8Z3OQ5TDWVNX7E6DCDHXHGNOJM94FEWJ5Z'
DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

# ================== HÀM TIỆN ÍCH ==================
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

# ================== CSS LUXURY DESIGN ==================
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;700;900&display=swap');
        :root {
            --bg-main: #0B0A10; --text-main: #F4F4F5; --text-muted: #A1A1AA; --accent: #8B5CF6;
            --accent-hover: rgba(139, 92, 246, 0.15); --card-bg: rgba(24, 24, 27, 0.7);
            --border-light: rgba(255, 255, 255, 0.08); --input-bg: rgba(9, 9, 11, 0.8);
            --input-border: rgba(255, 255, 255, 0.1); --btn-bg: #8B5CF6;
            --nav-bg: rgba(11, 10, 16, 0.85); --success-text: #10B981; --danger-text: #EF4444; 
            --coin-color: #F59E0B; --plan-text: #EC4899;
        }
        [data-theme="light"] {
            --bg-main: #FAFAFA; --text-main: #18181B; --text-muted: #71717A; --accent: #6D28D9;
            --accent-hover: rgba(109, 40, 217, 0.1); --card-bg: #FFFFFF;
            --border-light: rgba(0, 0, 0, 0.08); --input-bg: #F4F4F5;
            --input-border: rgba(0, 0, 0, 0.1); --btn-bg: #6D28D9;
            --nav-bg: rgba(250, 250, 250, 0.9);
        }
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }
        body { background: var(--bg-main); color: var(--text-main); overflow-x: hidden; min-height: 100vh; transition: 0.3s; }
        
        /* NAVBAR ĐỈNH CAO */
        .navbar { display: flex; justify-content: space-between; align-items: center; padding: 15px 5%; background: var(--nav-bg); backdrop-filter: blur(20px); border-bottom: 1px solid var(--border-light); position: sticky; top: 0; z-index: 1000; }
        .logo { font-size: 22px; font-weight: 900; letter-spacing: -0.5px; display:flex; align-items:center; gap:8px;}
        .logo svg { color: var(--accent); }
        .nav-right { display: flex; align-items: center; gap: 15px; position: relative;}
        
        .user-menu-btn { display: flex; align-items: center; gap: 10px; background: var(--card-bg); border: 1px solid var(--border-light); padding: 5px 15px 5px 5px; border-radius: 30px; cursor: pointer; transition: 0.3s; color: var(--text-main);}
        .user-menu-btn:hover { border-color: var(--accent); background: var(--accent-hover); }
        .avatar-img { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 2px solid var(--accent); }
        .user-name { font-size: 13px; font-weight: 700; max-width: 100px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;}
        
        /* DROPDOWN MENU */
        .dropdown-menu { position: absolute; top: 50px; right: 0; background: var(--card-bg); border: 1px solid var(--border-light); border-radius: 16px; width: 220px; padding: 10px; box-shadow: 0 15px 40px rgba(0,0,0,0.4); backdrop-filter: blur(25px); opacity: 0; visibility: hidden; transform: translateY(-10px); transition: 0.3s; z-index: 1001;}
        .dropdown-menu.active { opacity: 1; visibility: visible; transform: translateY(0); }
        .dp-item { display: flex; align-items: center; gap: 12px; padding: 12px 15px; color: var(--text-muted); text-decoration: none; font-size: 13px; font-weight: 600; border-radius: 10px; transition: 0.2s; cursor: pointer;}
        .dp-item:hover, .dp-item.active-tab { background: var(--accent-hover); color: var(--accent); }
        .dp-logout { color: var(--danger-text); margin-top: 5px; border-top: 1px dashed var(--border-light); border-radius: 0 0 10px 10px; }
        .dp-logout:hover { background: rgba(239, 68, 68, 0.1); color: var(--danger-text); }

        .container { max-width: 700px; width: 100%; margin: 30px auto; padding: 0 15px; }
        
        /* STATS GRID MỚI */
        .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 15px; margin-bottom: 25px; }
        .stat-card { background: var(--card-bg); border: 1px solid var(--border-light); border-radius: 16px; padding: 20px; text-align: left; transition: 0.3s; backdrop-filter: blur(12px);}
        .stat-card:hover { border-color: var(--accent); transform: translateY(-3px); box-shadow: 0 10px 25px rgba(0,0,0,0.2); }
        .stat-card h3 { font-size: 11px; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 1px; margin-bottom: 8px; display:flex; align-items:center; gap:6px;}
        .stat-card h2 { font-size: 24px; font-weight: 900; color: var(--text-main); }
        .stat-card .highlight { color: var(--plan-text); }

        .card { background: var(--card-bg); backdrop-filter: blur(12px); border-radius: 20px; padding: 25px; margin-bottom: 20px; border: 1px solid var(--border-light); transition: 0.3s;}
        .card-title { color: var(--text-main); font-size: 15px; font-weight: 800; margin-bottom: 20px; display: flex; align-items: center; justify-content: space-between; border-bottom: 1px solid var(--border-light); padding-bottom: 15px;}
        
        .input-group { margin-bottom: 15px; }
        .input-group label { display: block; color: var(--text-muted); font-size: 12px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing:0.5px;}
        .input-group input { width: 100%; padding: 14px; background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 12px; color: var(--text-main); font-size: 14px; outline: none; transition: 0.3s; }
        .input-group input:focus { border-color: var(--accent); box-shadow: 0 0 0 2px var(--accent-hover); }
        
        .btn { width: 100%; padding: 14px; border-radius: 12px; font-weight: 800; font-size: 13px; cursor: pointer; text-align: center; border: none; transition: 0.2s; display: flex; align-items: center; justify-content: center; gap: 8px; text-transform: uppercase; }
        .btn-primary { background: var(--btn-bg); color: #fff; }
        .btn-primary:hover { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 8px 20px rgba(139, 92, 246, 0.4); }
        .btn-danger { background: rgba(239, 68, 68, 0.1); border: 1px solid rgba(239, 68, 68, 0.3); color: var(--danger-text); padding: 12px;}
        .btn-buy { background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); color: var(--coin-color); margin-top:15px;}
        
        .svg-icon { width: 18px; height: 18px; stroke-width: 2; stroke: currentColor; fill: none; stroke-linecap: round; stroke-linejoin: round; display: inline-flex; flex-shrink: 0; }
        .msg { padding: 14px; border-radius: 12px; font-size: 13px; margin-bottom: 15px; text-align: center; font-weight: 600; display: flex; align-items: center; justify-content: center; gap: 8px; }
        .msg.success { background: rgba(16, 185, 129, 0.1); color: var(--success-text); border: 1px solid rgba(16, 185, 129, 0.2); }
        .msg.error { background: rgba(239, 68, 68, 0.1); color: var(--danger-text); border: 1px solid rgba(239, 68, 68, 0.2); }

        .theme-toggle-btn { background: transparent; border: none; color: var(--text-muted); cursor: pointer; transition: 0.3s; padding: 5px;}
        .theme-toggle-btn:hover { color: var(--accent); transform: rotate(30deg);}
        
        .tab-content { display: none; animation: fadeIn 0.3s; }
        .tab-content.active { display: block; }
        @keyframes fadeIn { from { opacity: 0; transform: translateY(10px); } to { opacity: 1; transform: translateY(0); } }
        
        /* CUSTOM SWITCH TỐI GIẢN */
        .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; margin: 20px 0; }
        .switch-wrap { display: flex; align-items: center; justify-content: space-between; padding: 12px 15px; background: rgba(255,255,255,0.02); border-radius: 12px; border: 1px solid var(--input-border); }
        .switch-label { font-size: 13px; font-weight: 600; color: var(--text-main);}
        .switch { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink:0;}
        .switch input { opacity: 0; width: 0; height: 0; }
        .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--input-border); transition: .4s; border-radius: 34px; }
        .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: #fff; transition: .4s; border-radius: 50%;}
        input:checked + .slider { background-color: var(--accent); }
        input:checked + .slider:before { transform: translateX(18px); }

        /* LIST ACC ĐANG CHẠY */
        .account-card { background: rgba(255,255,255,0.02); border-radius: 12px; padding: 15px; margin-bottom: 10px; border: 1px solid var(--input-border); display: flex; justify-content: space-between; align-items: center; }
        .account-card .name { font-weight: 700; font-size: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 6px;}
        .log-box { background: rgba(0,0,0,0.4); border-radius: 12px; padding: 15px; max-height: 250px; overflow-y: auto; font-family: monospace; font-size: 11px; color: #4ade80; border: 1px solid var(--input-border); white-space: pre-wrap; word-break: break-word;}
        
        .footer { text-align: center; margin-top: 40px; padding-bottom: 30px; font-size: 12px; color: var(--text-muted); font-weight: 500;}
        
        /* OVERLAY KHI DROP DOWN BẬT TRÊN MOBILE */
        .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.5); z-index: 999; display: none; }
        .overlay.active { display: block; }
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
                root.removeAttribute('data-theme'); localStorage.setItem('za_theme', 'dark'); 
                if(iconBtn) iconBtn.innerHTML = MOON_ICON;
            } else { 
                root.setAttribute('data-theme', 'light'); localStorage.setItem('za_theme', 'light'); 
                if(iconBtn) iconBtn.innerHTML = SUN_ICON;
            }
        }
        document.addEventListener("DOMContentLoaded", setInitialThemeIcon);
        
        function toggleDropdown() {
            document.getElementById('userDropdown').classList.toggle('active');
            document.getElementById('mobileOverlay').classList.toggle('active');
        }
    </script>
"""

# ================== GIAO DIỆN LOGIN ONLY DISCORD (SIÊU XỊN) ==================
HTML_AUTH = HTML_HEAD + """
<title>ZaTools - Đăng Nhập</title>
<style>
    body { display: flex; justify-content: center; align-items: center; background: #0B0A10; background-image: radial-gradient(circle at 50% 0%, rgba(139, 92, 246, 0.15), transparent 50%);}
    .login-box { max-width: 380px; width: 90%; text-align: center; padding: 40px 30px; border-radius: 24px; background: rgba(24, 24, 27, 0.6); border: 1px solid rgba(255,255,255,0.08); backdrop-filter: blur(20px); box-shadow: 0 25px 50px -12px rgba(0,0,0,0.5);}
    .logo-big { font-size: 36px; font-weight: 900; letter-spacing: -1px; margin-bottom: 10px; display:flex; justify-content:center; align-items:center; gap:10px; color:#fff;}
    .logo-big svg { color: var(--accent); width: 36px; height: 36px;}
    .login-sub { color: #A1A1AA; font-size: 14px; margin-bottom: 35px; line-height: 1.5;}
    .btn-discord { width: 100%; padding: 16px; border-radius: 14px; font-weight: 800; font-size: 14px; cursor: pointer; text-align: center; border: none; transition: 0.3s; display: flex; align-items: center; justify-content: center; gap: 10px; background: #5865F2; color: #fff; text-decoration: none;}
    .btn-discord:hover { background: #4752C4; transform: translateY(-3px); box-shadow: 0 10px 25px rgba(88, 101, 242, 0.4); }
    .secure-text { font-size: 11px; color: #71717A; margin-top: 20px; display:flex; align-items:center; justify-content:center; gap:5px;}
</style>
</head>
<body>
    <div class="login-box">
        <div class="logo-big">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path></svg>
            ZaTools
        </div>
        <div class="login-sub">Nền tảng giữ Discord Online 24/7 với Custom RPC dành riêng cho bạn.</div>
        
        {% if error %}<div class="msg error">{{ error }}</div>{% endif %}
        
        <a href="/login/discord" class="btn-discord">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" stroke="none"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg>
            Đăng nhập bằng Discord
        </a>
        
        <div class="secure-text"><svg class="svg-icon" style="width:14px; height:14px;" viewBox="0 0 24 24"><rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect><path d="M7 11V7a5 5 0 0 1 10 0v4"></path></svg> Xác thực an toàn qua OAuth2</div>
    </div>
</body>
</html>
"""

# ================== GIAO DIỆN DASHBOARD CHÍNH MỚI ==================
HTML_MAIN = HTML_HEAD + """
<title>ZaTools - Dashboard</title>
</head>
<body>
<div class="overlay" id="mobileOverlay" onclick="toggleDropdown()"></div>

<nav class="navbar">
    <div class="logo">
        <svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path></svg>
        ZaTools
    </div>
    
    <div class="nav-right">
        <button class="theme-toggle-btn" onclick="toggleTheme()"><svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24"></svg></button>
        
        <div class="user-menu-btn" onclick="toggleDropdown()">
            <img src="{{ avatar_url }}" class="avatar-img" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
            <div class="user-name">{{ current_user }}</div>
            <svg class="svg-icon" style="width:16px; height:16px;" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </div>
        
        <div class="dropdown-menu" id="userDropdown">
            <a href="#" class="dp-item active-tab" onclick="switchTab('treo', this)"><svg class="svg-icon"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg> Thiết Lập Treo</a>
            <a href="#" class="dp-item" onclick="switchTab('saved', this)"><svg class="svg-icon"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg> Kho Dữ Liệu</a>
            <a href="#" class="dp-item" onclick="switchTab('premium', this)"><svg class="svg-icon"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> Nạp & Mua Gói</a>
            
            {% if is_admin %}
            <a href="/admin_dangkhoi" class="dp-item" style="color: var(--plan-text);"><svg class="svg-icon"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> Mắt Thần Admin</a>
            {% endif %}
            
            <a href="/logout" class="dp-item dp-logout"><svg class="svg-icon"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg> Đăng xuất</a>
        </div>
    </div>
</nav>

<div class="container">
    {% if flash_msg %}
        <div class="msg {{ flash_type }}">
            {% if flash_type == 'success' %} <svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
            {% else %} <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg> {% endif %}
            {{ flash_msg }}
        </div>
    {% endif %}

    <!-- STATS GRID -->
    <div class="stats-grid">
        <div class="stat-card">
            <h3><svg class="svg-icon"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg> Trạng Thái</h3>
            <h2>{{ running_count }} <span style="font-size:12px; color:var(--text-muted); font-weight:500;">đang chạy</span></h2>
        </div>
        <div class="stat-card">
            <h3><svg class="svg-icon"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg> Giới Hạn</h3>
            <h2>{{ max_tokens }} <span style="font-size:12px; color:var(--text-muted); font-weight:500;">acc tối đa</span></h2>
        </div>
        <div class="stat-card">
            <h3><svg class="svg-icon"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg> Số Dư Ví</h3>
            <h2 style="color: var(--coin-color);">{{ "{:,}".format(balance) }}đ</h2>
        </div>
        <div class="stat-card">
            <h3><svg class="svg-icon"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> Gói Cước</h3>
            <h2 class="highlight">{{ plan_name }}</h2>
        </div>
    </div>

    <div id="tab-treo" class="tab-content active">
        <form method="POST">
            <div class="card">
                <div class="card-title">Thiết Lập Kết Nối</div>
                <div class="input-group"><label>Tên gợi nhớ (Nếu lưu)</label><input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp..."></div>
                <div class="input-group"><label>Discord Token</label><input type="text" name="token" required placeholder="Nhập Token của bạn..."></div>
                <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required></div>
                <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required></div>
                
                <div style="border: 1px dashed var(--accent); padding: 15px; border-radius: 12px; margin-bottom: 15px; background: rgba(139, 92, 246, 0.03);">
                    <div style="color: var(--accent); font-size: 12px; font-weight: 800; margin-bottom: 15px; text-transform: uppercase; display:flex; align-items:center; gap:5px;"><svg class="svg-icon"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg> Thiết lập Rich Presence (RPC)</div>
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
                        <div class="input-group" style="flex:1;"><label>Tên Nút 2</label><input type="text" name="rpc_b2_name" placeholder="VD: ZaTools Group"></div>
                        <div class="input-group" style="flex:1;"><label>Link Nút 2</label><input type="text" name="rpc_b2_url" placeholder="https://..."></div>
                    </div>
                </div>
                
                <div class="options-grid">
                    <div class="switch-wrap"><div class="switch-label">Tắt Mic</div><label class="switch"><input type="checkbox" name="mute" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Tắt Âm</div><label class="switch"><input type="checkbox" name="deaf" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Cam Ảo</div><label class="switch"><input type="checkbox" name="video"><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Live Ảo</div><label class="switch"><input type="checkbox" name="stream"><span class="slider"></span></label></div>
                </div>

                <div class="btn-flex">
                    <button type="submit" formaction="/start" class="btn btn-primary">CHẠY NGAY</button>
                    <button type="submit" formaction="/save_profile" class="btn btn-success" style="background: rgba(16, 185, 129, 0.15); color: var(--success-text); border:none;">LƯU LẠI</button>
                </div>
            </div>
        </form>

        <div class="card">
            <div class="card-title">
                Phiên Đang Chạy
                {% if running_count > 0 %}
                <form method="POST" action="/stop_all" style="margin:0;"><button type="submit" class="btn btn-danger" style="padding: 6px 12px; font-size: 11px;">DỪNG HẾT</button></form>
                {% endif %}
            </div>
            {% for key, bot in bot_items %}
            <div class="account-card">
                <div>
                    <div class="name"><svg class="svg-icon" style="color:var(--accent); width:16px;"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg> {{ bot.get('display_name', 'Đang kết nối...') }}</div>
                    <div style="font-size:11px; color:var(--success-text); margin-left: 22px;" id="status-{{ loop.index0 }}">Treo vĩnh cửu</div>
                </div>
                <form method="POST" action="/stop"><input type="hidden" name="bot_key" value="{{ key }}"><button type="submit" class="btn btn-danger"><svg class="svg-icon" style="margin:0;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg></button></form>
            </div>
            {% endfor %}
            {% if not bot_items %}<div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 10px 0;">Chưa có phiên nào hoạt động.</div>{% endif %}
        </div>
        
        <div class="card">
            <div class="card-title">
                Live Terminal
                <form method="POST" action="/refresh" style="margin:0;"><input type="hidden" name="tab" value="treo"><button type="submit" style="background:transparent; border:none; color:var(--accent); cursor:pointer; font-size:12px; font-weight:700;">TẢI LẠI LỊCH SỬ</button></form>
            </div>
            <div class="log-box" id="live-log-box">Đang kết nối hệ thống...</div>
        </div>
    </div>

    <!-- TABS KHÁC GIỮ NGUYÊN CODE HTML NHƯ CŨ (RÚT GỌN CHO GỌN) -->
    <div id="tab-saved" class="tab-content">
        <div class="card">
            <div class="card-title">Kho Dữ Liệu Cá Nhân</div>
            {% for profile in saved_profiles %}
            <div class="account-card">
                <div>
                    <div class="name" style="color: var(--coin-color);">{{ profile.profile_name }}</div>
                    <div style="font-size:11px; color:var(--text-muted); margin-top:3px;">Máy chủ: {{ profile.guild_id }}</div>
                </div>
                <div style="display:flex; gap:8px;">
                    <form method="POST" action="/start_saved"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-success" style="padding:10px; background:rgba(16, 185, 129, 0.2);"><svg class="svg-icon" style="margin:0;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg></button></form>
                    <form method="POST" action="/delete_profile"><input type="hidden" name="profile_id" value="{{ profile._id }}"><button type="submit" class="btn btn-danger" style="padding:10px;"><svg class="svg-icon" style="margin:0;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg></button></form>
                </div>
            </div>
            {% endfor %}
            {% if not saved_profiles %}<div style="text-align:center; font-size:12px; color:var(--text-muted); padding: 20px 0;">Kho trống.</div>{% endif %}
        </div>
    </div>

    <div id="tab-premium" class="tab-content">
        <div class="card">
            <div class="card-title" style="color: var(--coin-color);">NẠP SỐ DƯ (1 VNĐ = 1 COIN)</div>
            <p style="font-size:12px; color:var(--text-muted); text-align:center; margin-bottom:15px;">Quét QR chuyển khoản. Tiền sẽ vào ví tự động sau 5s.</p>
            <div class="input-group"><input type="number" id="nap_amount" placeholder="Nhập số tiền muốn nạp..." min="10000" step="10000"></div>
            <button onclick="generateNapQR()" class="btn btn-primary" style="margin-bottom:20px;">TẠO MÃ NẠP</button>
            <div id="qr_nap_area" style="display: none; text-align: center; border-top: 1px dashed var(--input-border); padding-top: 20px; margin-top:20px;">
                <img id="qr_nap_img" src="" style="width: 200px; border-radius: 12px; border: 2px solid var(--coin-color);">
                <div style="margin-top: 15px; font-size: 13px; background: var(--input-bg); padding: 12px; border-radius: 10px;">
                    <span style="color:var(--text-muted);">Nội dung nạp tiền:</span><br>
                    <b style="color:var(--success-text); font-size: 16px; letter-spacing: 1px;">ZATOOLS <span id="clean_username"></span></b>
                </div>
                <div id="payment_status" class="msg" style="display:none; margin-top:15px; background:rgba(245, 158, 11, 0.1); color:var(--coin-color); border:1px solid rgba(245, 158, 11, 0.3);">Đang chờ ngân hàng xử lý...</div>
            </div>
        </div>
        
        <div class="card">
            <div class="card-title" style="color: var(--plan-text);">MUA GÓI (30 NGÀY)</div>
            <div style="display:grid; gap:15px;">
                <div class="plan-box" style="margin:0; padding:15px;">
                    <div class="plan-title">GÓI STARTER</div>
                    <div class="plan-price">20,000đ</div>
                    <div class="plan-feature">Treo tối đa 2 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="STARTER"><button type="submit" class="btn btn-buy" style="margin-top:10px;">MUA BẰNG COIN</button></form>
                </div>
                <div class="plan-box" style="margin:0; padding:15px; border-color:var(--accent);">
                    <div class="plan-title" style="color:var(--accent);">GÓI PRO</div>
                    <div class="plan-price">40,000đ</div>
                    <div class="plan-feature">Treo tối đa 5 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="PRO"><button type="submit" class="btn btn-buy" style="margin-top:10px;">MUA BẰNG COIN</button></form>
                </div>
                <div class="plan-box plan-vip" style="margin:0; padding:15px;">
                    <div class="plan-title">GÓI VIP</div>
                    <div class="plan-price">300,000đ</div>
                    <div class="plan-feature">Treo tối đa 35 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="VIP"><button type="submit" class="btn btn-buy" style="margin-top:10px; background:var(--plan-text); color:#fff;">MUA GÓI VIP</button></form>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div>&copy; 2026 ZaTools Premium - Developed by Dang Khoi</div>
        <div style="color: var(--success-text); display:flex; justify-content:center; align-items:center; gap:5px; margin-top:8px;"><span style="width:6px; height:6px; background:var(--success-text); border-radius:50%; box-shadow:0 0 8px var(--success-text);"></span> Hệ thống hoạt động bình thường</div>
    </div>
</div>

""" + THEME_SCRIPT + """
<script>
    function switchTab(tabId, el) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');
        document.querySelectorAll('.dp-item').forEach(l => l.classList.remove('active-tab'));
        if(el) el.classList.add('active-tab');
        document.getElementById('userDropdown').classList.remove('active');
        document.getElementById('mobileOverlay').classList.remove('active');
        localStorage.setItem('za_active_tab', tabId);
    }

    window.onload = () => {
        let reqTab = '{{ active_tab }}';
        let tabToLoad = reqTab !== 'None' ? reqTab : (localStorage.getItem('za_active_tab') || 'treo');
        let links = document.querySelectorAll('.dp-item');
        let targetLink = Array.from(links).find(l => l.getAttribute('onclick') && l.getAttribute('onclick').includes(tabToLoad));
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
        document.getElementById('payment_status').style.display = 'block';

        if(checkPaymentInterval) clearInterval(checkPaymentInterval);
        checkPaymentInterval = setInterval(checkBalance, 3000);
    }
    
    function checkBalance() {
        fetch('/api/get_balance')
        .then(res => res.json())
        .then(data => {
            if (data.balance > currentBalance) {
                clearInterval(checkPaymentInterval);
                currentBalance = data.balance;
                document.getElementById('payment_status').style.background = 'rgba(16, 185, 129, 0.1)';
                document.getElementById('payment_status').style.color = 'var(--success-text)';
                document.getElementById('payment_status').style.borderColor = 'rgba(16, 185, 129, 0.3)';
                document.getElementById('payment_status').innerHTML = `Đã nạp thành công! Vui lòng F5 lại trang.`;
            }
        });
    }
</script>
</body>
</html>
"""

# ================== TRANG ADMIN PANEL ==================
HTML_ADMIN = HTML_HEAD + """
<title>Admin Panel - ZaTools</title>
<style>
    .admin-container { max-width: 600px; width: 95%; margin: 30px auto; padding: 25px; background: var(--card-bg); border-radius: 20px; border: 1px solid var(--border-light); box-shadow: 0 10px 40px var(--shadow); }
    .stat-box { background: var(--input-bg); padding: 15px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; border: 1px solid var(--input-border); font-weight: 600; color: var(--text-muted);}
    .stat-val { color: var(--text-main); font-size: 18px; }
    .action-box { background: rgba(139, 92, 246, 0.05); border: 1px solid var(--accent); padding: 20px; border-radius: 15px; margin-top: 25px;}
</style>
<body>
    <div class="admin-container">
        <h2 style="color:var(--text-main); text-align:center; margin-bottom:25px; display:flex; justify-content:center; align-items:center; gap:10px;">
            <svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--plan-text); width:28px; height:28px;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg> BẢNG ĐIỀU KHIỂN DANG KHOI
        </h2>
        {% if msg %}<div class="msg success">{{ msg }}</div>{% endif %}
        
        <div class="stat-box">Khách hàng: <span class="stat-val">{{ stats.users }}</span></div>
        <div class="stat-box">Token đang lưu: <span class="stat-val">{{ stats.bots }}</span></div>
        <div class="stat-box">Luồng cày ngầm: <span class="stat-val" style="color:var(--success-text);">{{ stats.running }}</span></div>
        <div class="stat-box">Doanh thu: <span class="stat-val" style="color:var(--coin-color);">{{ "{:,}".format(stats.total_money) }} đ</span></div>
        
        <div class="action-box">
            <h3 style="color:var(--accent); font-size:13px; margin-bottom:15px; text-transform:uppercase;">Cộng tiền thủ công</h3>
            <form method="POST" action="/admin_action">
                <input type="hidden" name="action" value="add_coin">
                <div class="input-group"><input type="text" name="target_user" required placeholder="Nhập username khách..."></div>
                <div class="input-group"><input type="number" name="amount" required placeholder="Số Coin cần cộng..."></div>
                <button type="submit" class="btn btn-primary">XÁC NHẬN CỘNG</button>
            </form>
        </div>

        <div class="action-box" style="background: rgba(245, 158, 11, 0.05); border-color: var(--coin-color);">
            <h3 style="color:var(--coin-color); font-size:13px; margin-bottom:15px; text-transform:uppercase;">Đồng bộ SePay bị sót</h3>
            <form method="POST" action="/admin_action">
                <input type="hidden" name="action" value="sync_sepay">
                <button type="submit" class="btn btn-primary" style="background:var(--coin-color); color:#000; border:none;">QUÉT & ĐỒNG BỘ LẠI</button>
            </form>
        </div>
        <div style="text-align:center; margin-top:20px;"><a href="/" style="color:var(--text-muted); text-decoration:none; font-weight:600; font-size:13px;">← Trở về Dashboard</a></div>
    </div>
</body>
</html>
"""

# ================== HÀM CHẠY LUỒNG VÀ LOGGING (CUSTOM RPC CORE TỐI THƯỢNG) ==================
def run_bot(bot_key, config, username):
    token = config.get('token')
    guild_id = config.get('guild_id')
    channel_id = config.get('channel_id')
    
    mute = str(config.get('mute', 'False')).lower() in ['true', 'on', '1']
    deaf = str(config.get('deaf', 'False')).lower() in ['true', 'on', '1']
    video = str(config.get('video', 'False')).lower() in ['true', 'on', '1']
    stream = str(config.get('stream', 'False')).lower() in ['true', 'on', '1']

    ws = None; last_seq = None; heartbeat_interval = 41250; connected = False
    start_time = int(time.time() * 1000)

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
                            ws_client.send(json.dumps({"op": 18, "d": {"type": "guild", "guild_id": guild_id, "channel_id": channel_id, "preferred_region": None}}))
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
            presence_data = {"status": "online", "since": 0, "activities": [], "afk": False}
            
            status_text = config.get('status_text', '').strip()
            rpc_app_id = "1469298750613749934"
            
            if status_text:
                activity = {
                    "name": status_text, "type": 0, "application_id": rpc_app_id, "timestamps": {"start": start_time}
                }
                if config.get('rpc_details'): activity["details"] = config.get('rpc_details')
                if config.get('rpc_state'): activity["state"] = config.get('rpc_state')
                
                rpc_image = config.get('rpc_image', '').strip()
                if rpc_image.startswith('http'):
                    try:
                        res = requests.post(f"https://discord.com/api/v9/applications/{rpc_app_id}/external-assets", headers={"Authorization": token, "Content-Type": "application/json"}, json={"urls": [rpc_image]}, timeout=5)
                        if res.status_code == 200: rpc_image = f"mp:{res.json()[0]['external_asset_path']}"
                    except: pass
                
                if rpc_image: activity["assets"] = {"large_image": rpc_image, "large_text": status_text}
                
                buttons, metadata_urls = [], []
                if config.get('rpc_b1_name') and config.get('rpc_b1_url'):
                    buttons.append(config.get('rpc_b1_name')); metadata_urls.append(config.get('rpc_b1_url'))
                if config.get('rpc_b2_name') and config.get('rpc_b2_url'):
                    buttons.append(config.get('rpc_b2_name')); metadata_urls.append(config.get('rpc_b2_url'))
                    
                if buttons:
                    activity["buttons"] = buttons
                    activity["metadata"] = {"button_urls": metadata_urls}
                    
                presence_data["activities"].append(activity)
                add_log("🎨 Gắn khối Custom RPC thành công!")
                
            ws_client.send(json.dumps({"op": 2, "d": {"token": token, "properties": {"os": "Linux", "browser": "Chrome", "device": "ZaTools"}, "presence": presence_data, "compress": False}}))
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

    def start_ws():
        nonlocal ws
        if username not in user_bots or bot_key not in user_bots[username] or not user_bots[username][bot_key]['running']: return
        try: gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except: time.sleep(5); start_ws(); return
        add_log("🚀 Khởi tạo tiến trình...")
        ws = websocket.WebSocketApp(gateway + "/?v=9&encoding=json", on_message=on_message, on_error=on_error, on_close=on_close)
        threading.Thread(target=heartbeat_loop, daemon=True).start()
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
                'token': doc.get('token'), 'guild_id': doc.get('guild_id'), 'channel_id': doc.get('channel_id'), 
                'status_text': doc.get('status_text', ''), 'rpc_details': doc.get('rpc_details', ''), 'rpc_state': doc.get('rpc_state', ''),
                'rpc_image': doc.get('rpc_image', ''), 'rpc_b1_name': doc.get('rpc_b1_name', ''), 'rpc_b1_url': doc.get('rpc_b1_url', ''),
                'rpc_b2_name': doc.get('rpc_b2_name', ''), 'rpc_b2_url': doc.get('rpc_b2_url', ''),
                'mute': doc.get('mute'), 'deaf': doc.get('deaf'), 'video': doc.get('video'), 'stream': doc.get('stream') 
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

# ================== BÍ MẬT CỦA SẾP DANG KHOI ==================
@app.route('/khoideptrai_admin')
def claim_admin():
    if 'username' not in session:
        return "Hãy bấm nút 'Đăng nhập bằng Discord' ngoài trang chủ trước khi vào link này nhé sếp!"
    
    users_collection.update_one(
        {"username": session['username']}, 
        {"$set": {"is_admin": True, "max_tokens": 9999}}
    )
    return "✅ SẾP ĐÃ TRỞ THÀNH QUẢN TRỊ VIÊN TỐI CAO. HÃY QUAY LẠI TRANG CHỦ!"

# ================== ROUTES ỨNG DỤNG CHÍNH ==================
@app.route('/')
def index():
    if 'username' not in session: return redirect(url_for('login'))
    usr = session['username']
    avatar_url = session.get('avatar', 'https://cdn.discordapp.com/embed/avatars/0.png')
    
    max_tokens, expiry_info, plan_name = get_user_limit(usr)
    db_user = users_collection.find_one({"username": usr})
    is_admin = db_user.get('is_admin', False) if db_user else False
    balance = db_user.get('balance', 0) if db_user else 0
    
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    log = active_bots[0][1].get('log', []) if active_bots else []
    
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, avatar_url=avatar_url, balance=balance, plan_name=plan_name,
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
        'token': request.form.get('token', '').strip(), 'guild_id': request.form.get('guild_id', '').strip(), 'channel_id': request.form.get('channel_id', '').strip(),
        'status_text': request.form.get('status_text', '').strip(), 'rpc_details': request.form.get('rpc_details', '').strip(), 'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(), 'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(), 'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(), 'rpc_b2_url': request.form.get('rpc_b2_url', '').strip(),
        'mute': request.form.get('mute') == 'on', 'deaf': request.form.get('deaf') == 'on', 'video': request.form.get('video') == 'on', 'stream': request.form.get('stream') == 'on'
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
        'profile_name': prof_name, 'owner': session['username'], '_id': str(int(time.time())),
        'token': request.form.get('token', '').strip(), 'guild_id': request.form.get('guild_id', '').strip(), 'channel_id': request.form.get('channel_id', '').strip(),
        'status_text': request.form.get('status_text', '').strip(), 'rpc_details': request.form.get('rpc_details', '').strip(), 'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(), 'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(), 'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(), 'rpc_b2_url': request.form.get('rpc_b2_url', '').strip(),
        'mute': request.form.get('mute') == 'on', 'deaf': request.form.get('deaf') == 'on', 'video': request.form.get('video') == 'on', 'stream': request.form.get('stream') == 'on'
    }
    saved_profiles_collection.insert_one(config)
    session['flash_msg'] = "Đã lưu vào Kho dữ liệu!"
    return redirect(url_for('index', tab='saved'))

@app.route('/login', methods=['GET'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    return render_template_string(HTML_AUTH)

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
    user_data = discord.get('https://discord.com/api/users/@me').json()
    
    usr = f"{user_data.get('username')}_dc"
    user_id = user_data.get('id')
    avatar_hash = user_data.get('avatar')
    
    # LẤY AVATAR XỊN TỪ DISCORD
    if avatar_hash: avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
    else: avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
    
    if not users_collection.find_one({"username": usr}): 
        users_collection.insert_one({"username": usr, "oauth": "discord", "avatar": avatar_url, "max_tokens": 1, "expiry_date": 0, "balance": 0})
    else:
        users_collection.update_one({"username": usr}, {"$set": {"avatar": avatar_url}})
        
    session['username'] = usr
    session['avatar'] = avatar_url
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
    # CHỈ ADMIN MỚI VÀO ĐƯỢC
    db_user = users_collection.find_one({"username": session.get('username')})
    if not db_user or not db_user.get('is_admin'): return redirect(url_for('index'))
    
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
    db_user = users_collection.find_one({"username": session.get('username')})
    if not db_user or not db_user.get('is_admin'): return redirect(url_for('index'))
    
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
                    if process_sepay_transaction(tid, amt, content): synced_count += 1
            session['admin_msg'] = f"Đồng bộ hoàn tất! Tìm thấy và cộng bù {synced_count} giao dịch bị sót."
        except Exception as e:
            session['admin_msg'] = f"Lỗi đồng bộ: {str(e)}"
            
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__': app.run(host='0.0.0.0', port=8080)
