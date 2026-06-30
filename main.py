from flask import Flask, render_template_string, request, jsonify, redirect, url_for, session
import threading, json, time, requests, websocket, os
from pymongo import MongoClient
from requests_oauthlib import OAuth2Session
from bson.objectid import ObjectId
import concurrent.futures

app = Flask(__name__)
app.secret_key = "za_tools_final_v27_fixed"
os.environ['OAUTHLIB_INSECURE_TRANSPORT'] = '1'

MONGO_URI = "mongodb+srv://dangkhoi:itachi5867@cluster0.idnlwyd.mongodb.net/?appName=Cluster0"
try:
    client = MongoClient(MONGO_URI)
    db = client["za_tools_database"]
    accounts_collection = db["accounts"]
    users_collection = db["users"]
    saved_profiles_collection = db["saved_profiles"]
    transactions_collection = db["transactions"]
    print("✅ MongoDB OK! V27 - Fixed Icons & Telegram Float Button")
except Exception as e:
    print(f"💥 Lỗi DB: {e}")

user_bots = {}

SEPAY_API_KEY = 'ZYIBFUMXFG6PJKXA0CNYCIQAKROTMD8Z3OQ5TDWVNX7E6DCDHXHGNOJM94FEWJ5Z'
DISCORD_CLIENT_ID = '1504310281625403544'
DISCORD_CLIENT_SECRET = 'FuZ0Xru4xBnE0UoxpmEEbby51ZB8D0RN'
DISCORD_AUTH_URL = 'https://discord.com/api/oauth2/authorize'
DISCORD_TOKEN_URL = 'https://discord.com/api/oauth2/token'

def get_base_url(): return "https://zo-treo.onrender.com"

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

# ================== CSS GLOBAL ==================
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
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700;800;900&display=swap');
        :root {
            --bg-main: #030810;
            --text-main: #F0F4FF;
            --text-muted: #7a8db0;
            --accent: #00c8ff;
            --accent2: #7c3aed;
            --accent-hover: rgba(0, 200, 255, 0.12);
            --card-bg: rgba(8, 16, 36, 0.75);
            --border-light: rgba(0, 200, 255, 0.12);
            --border-hover: rgba(0, 200, 255, 0.4);
            --input-bg: rgba(3, 8, 16, 0.9);
            --input-border: rgba(0, 200, 255, 0.15);
            --btn-bg: linear-gradient(135deg, #0052d4, #00c8ff);
            --btn-bg2: linear-gradient(135deg, #7c3aed, #a855f7);
            --nav-bg: rgba(3, 8, 16, 0.92);
            --success-text: #00e676;
            --danger-text: #ff4458;
            --coin-color: #f5c518;
            --plan-text: #a855f7;
            --glow-accent: 0 0 20px rgba(0, 200, 255, 0.3);
            --glow-purple: 0 0 20px rgba(168, 85, 247, 0.3);
        }
        [data-theme="light"] {
            --bg-main: #f0f4fb;
            --text-main: #0f172a;
            --text-muted: #64748b;
            --accent: #2563eb;
            --accent2: #7c3aed;
            --accent-hover: rgba(37, 99, 235, 0.08);
            --card-bg: rgba(255,255,255,0.9);
            --border-light: rgba(37, 99, 235, 0.12);
            --border-hover: rgba(37, 99, 235, 0.4);
            --input-bg: #f8fafc;
            --input-border: rgba(37, 99, 235, 0.18);
            --btn-bg: linear-gradient(135deg, #2563eb, #3b82f6);
            --nav-bg: rgba(255,255,255,0.95);
            --glow-accent: 0 4px 20px rgba(37, 99, 235, 0.15);
        }

        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Inter', sans-serif; -webkit-tap-highlight-color: transparent; }

        body {
            background: var(--bg-main);
            color: var(--text-main);
            overflow-x: hidden;
            min-height: 100vh;
            background-image:
                radial-gradient(ellipse at 10% 0%, rgba(0, 200, 255, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 90% 100%, rgba(124, 58, 237, 0.08) 0%, transparent 50%),
                radial-gradient(ellipse at 50% 50%, rgba(0, 82, 212, 0.04) 0%, transparent 70%);
        }

        .svg-icon {
            width: 16px;
            height: 16px;
            min-width: 16px;
            min-height: 16px;
            stroke-width: 2;
            stroke: currentColor;
            fill: none;
            stroke-linecap: round;
            stroke-linejoin: round;
            display: inline-block;
            flex-shrink: 0;
            overflow: visible;
            vertical-align: middle;
        }

        .logo {
            font-size: 22px;
            font-weight: 900;
            letter-spacing: -0.5px;
            display: flex;
            align-items: center;
            gap: 8px;
            text-decoration: none;
            color: var(--text-main);
        }
        .logo-icon { color: var(--accent); width: 22px; height: 22px; min-width: 22px; overflow: visible; }

        .theme-toggle-btn {
            background: transparent;
            border: none;
            color: var(--text-muted);
            cursor: pointer;
            transition: 0.3s;
            padding: 6px;
            border-radius: 8px;
            display: flex;
            align-items: center;
        }
        .theme-toggle-btn:hover { color: var(--accent); background: var(--accent-hover); }

        .tg-float {
            position: fixed;
            bottom: 28px;
            right: 22px;
            z-index: 9999;
            width: 56px;
            height: 56px;
            border-radius: 50%;
            background: linear-gradient(135deg, #0088cc, #00b4ff);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            text-decoration: none;
            box-shadow: 0 4px 20px rgba(0, 136, 204, 0.5), 0 0 0 0 rgba(0, 136, 204, 0.4);
            animation: tg-pulse 2.5s infinite;
            transition: transform 0.2s, box-shadow 0.2s;
        }
        .tg-float:hover {
            transform: scale(1.12);
            box-shadow: 0 8px 30px rgba(0, 136, 204, 0.7);
            animation: none;
        }
        .tg-float svg {
            width: 28px;
            height: 28px;
            fill: white;
        }
        .tg-tooltip {
            position: absolute;
            right: 66px;
            background: rgba(10, 20, 40, 0.95);
            color: #fff;
            font-size: 12px;
            font-weight: 700;
            padding: 6px 12px;
            border-radius: 20px;
            white-space: nowrap;
            border: 1px solid rgba(0, 180, 255, 0.3);
            pointer-events: none;
            opacity: 0;
            transform: translateX(8px);
            transition: 0.25s;
        }
        .tg-float:hover .tg-tooltip { opacity: 1; transform: translateX(0); }
        @keyframes tg-pulse {
            0% { box-shadow: 0 4px 20px rgba(0, 136, 204, 0.5), 0 0 0 0 rgba(0, 136, 204, 0.4); }
            70% { box-shadow: 0 4px 20px rgba(0, 136, 204, 0.5), 0 0 0 14px rgba(0, 136, 204, 0); }
            100% { box-shadow: 0 4px 20px rgba(0, 136, 204, 0.5), 0 0 0 0 rgba(0, 136, 204, 0); }
        }

        .msg {
            display: flex;
            align-items: center;
            gap: 10px;
            padding: 14px 18px;
            border-radius: 14px;
            margin-bottom: 18px;
            font-size: 13px;
            font-weight: 600;
            animation: slideDown 0.3s ease;
        }
        .msg.success { background: rgba(0, 230, 118, 0.1); border: 1px solid rgba(0, 230, 118, 0.25); color: var(--success-text); }
        .msg.error { background: rgba(255, 68, 88, 0.1); border: 1px solid rgba(255, 68, 88, 0.25); color: var(--danger-text); }
        @keyframes slideDown { from { opacity: 0; transform: translateY(-10px); } to { opacity: 1; transform: translateY(0); } }
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
    </script>
"""

TG_FLOAT_BTN = """
<a href="https://t.me/thiendangcuaanh" target="_blank" class="tg-float" title="Liên hệ Telegram">
    <span class="tg-tooltip">Liên hệ hỗ trợ</span>
    <svg viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
        <path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L6.54 14.26l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.276.326z"/>
    </svg>
</a>
"""

# ================== LANDING PAGE ==================
HTML_LANDING = HTML_HEAD + """
<title>ZaTools - Nền Tảng Giữ Discord Luôn Online</title>
<style>
    /* ====== RESET & CƠ BẢN ====== */
    .reveal { opacity: 0; transform: translateY(40px); transition: 0.8s all cubic-bezier(0.5, 0, 0, 1); }
    .reveal.active { opacity: 1; transform: translateY(0); }

    .landing-nav {
        display: flex; justify-content: space-between; align-items: center;
        padding: 18px 5%;
        background: var(--nav-bg);
        backdrop-filter: blur(24px);
        position: sticky; top: 0; z-index: 1000;
        border-bottom: 1px solid var(--border-light);
    }
    .nav-right { display: flex; align-items: center; gap: 12px; }
    .landing-nav-btn {
        padding: 10px 22px; border-radius: 22px; font-weight: 800; font-size: 13px;
        text-decoration: none; color: #fff; background: var(--btn-bg);
        transition: 0.3s; box-shadow: 0 4px 16px rgba(0,200,255,0.25);
        border: none;
    }
    .landing-nav-btn:hover { opacity: 0.9; transform: translateY(-2px); box-shadow: 0 8px 24px rgba(0,200,255,0.4); }

    .hero {
        text-align: center; padding: 110px 20px 80px; max-width: 820px; margin: 0 auto;
    }
    .hero-badge {
        display: inline-flex; align-items: center; gap: 6px;
        padding: 8px 18px; border-radius: 30px;
        background: rgba(0, 200, 255, 0.08); color: var(--accent);
        font-size: 12px; font-weight: 800; text-transform: uppercase;
        margin-bottom: 24px; border: 1px solid var(--border-light); letter-spacing: 1.5px;
    }
    .hero-badge-dot { width: 7px; height: 7px; background: var(--success-text); border-radius: 50%; box-shadow: 0 0 8px var(--success-text); animation: blink 1.5s infinite; }
    @keyframes blink { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }

    .hero h1 { font-size: 54px; font-weight: 900; line-height: 1.1; margin-bottom: 22px; letter-spacing: -2px; }
    .hero h1 .gradient-text {
        background: linear-gradient(135deg, #00c8ff 0%, #7c3aed 60%, #a855f7 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        background-clip: text;
    }
    .hero p { font-size: 17px; color: var(--text-muted); line-height: 1.7; margin-bottom: 42px; max-width: 600px; margin-left: auto; margin-right: auto; }
    .hero-btns { display: flex; justify-content: center; gap: 14px; flex-wrap: wrap; }

    .hero-btn-primary {
        background: #5865F2; color: #fff; padding: 15px 30px; border-radius: 14px;
        font-weight: 800; font-size: 15px; text-decoration: none; transition: 0.3s;
        display: inline-flex; align-items: center; gap: 10px; border: none;
        box-shadow: 0 4px 20px rgba(88,101,242,0.35);
    }
    .hero-btn-primary:hover { background: #4752C4; transform: translateY(-3px); box-shadow: 0 12px 32px rgba(88,101,242,0.5); }
    .hero-btn-secondary {
        background: transparent; color: var(--text-main); padding: 15px 30px; border-radius: 14px;
        font-weight: 600; font-size: 15px; text-decoration: none;
        border: 1px solid var(--border-light); transition: 0.3s;
    }
    .hero-btn-secondary:hover { background: rgba(255,255,255,0.06); border-color: var(--accent); color: var(--accent); }

    .stats-container { display: flex; justify-content: center; gap: 18px; margin-top: 64px; flex-wrap: wrap; }
    .stat-box {
        background: var(--card-bg); border: 1px solid var(--border-light);
        padding: 20px 38px; border-radius: 18px; backdrop-filter: blur(12px);
        transition: 0.3s;
    }
    .stat-box:hover { border-color: var(--accent); box-shadow: var(--glow-accent); }
    .stat-val { font-size: 30px; font-weight: 900; color: var(--accent); margin-bottom: 4px; }
    .stat-label { font-size: 11px; color: var(--text-muted); font-weight: 700; text-transform: uppercase; letter-spacing: 1.5px; }

    /* ====== PHẦN GIỚI THIỆU ====== */
    .intro-section {
        max-width: 820px; margin: 40px auto; padding: 0 20px;
    }
    .intro-box {
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 28px; padding: 40px 36px;
        backdrop-filter: blur(12px);
        display: flex; flex-wrap: wrap; gap: 30px; align-items: center;
    }
    .intro-icon {
        flex: 0 0 80px; height: 80px;
        background: rgba(0,200,255,0.08); border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        color: var(--accent); border: 1px solid var(--border-light);
    }
    .intro-icon svg { width: 44px; height: 44px; stroke-width: 1.5; }
    .intro-text { flex: 1; }
    .intro-text h2 { font-size: 28px; font-weight: 900; margin-bottom: 12px; color: var(--text-main); }
    .intro-text p { font-size: 15px; color: var(--text-muted); line-height: 1.7; }

    /* ====== FEATURES ====== */
    .features { padding: 80px 20px; max-width: 1000px; margin: 0 auto; }
    .features-eyebrow { text-align: center; color: var(--accent); font-size: 12px; font-weight: 800; text-transform: uppercase; letter-spacing: 3px; margin-bottom: 14px; }
    .features-head h2 { font-size: 36px; font-weight: 900; margin-bottom: 14px; color: var(--text-main); text-align: center; }
    .features-head p { color: var(--text-muted); font-size: 15px; text-align: center; margin-bottom: 50px; }

    .feature-grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(250px, 1fr)); gap: 22px; }
    .feature-card {
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 22px; padding: 28px; transition: 0.3s;
        position: relative; overflow: hidden;
    }
    .feature-card::before {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, var(--f-color), transparent);
        opacity: 0; transition: 0.3s;
    }
    .feature-card:hover { transform: translateY(-6px); border-color: var(--f-color, var(--accent)); box-shadow: 0 16px 40px rgba(0,0,0,0.3); }
    .feature-card:hover::before { opacity: 1; }

    .f-icon { width: 48px; height: 48px; border-radius: 14px; display: flex; align-items: center; justify-content: center; margin-bottom: 18px; }
    .f-icon svg { width: 22px; height: 22px; overflow: visible; }
    .f-icon.pink { background: rgba(168, 85, 247, 0.12); color: #a855f7; --f-color: #a855f7; }
    .f-icon.blue { background: rgba(0, 200, 255, 0.12); color: #00c8ff; --f-color: #00c8ff; }
    .f-icon.green { background: rgba(0, 230, 118, 0.12); color: #00e676; --f-color: #00e676; }
    .f-icon.yellow { background: rgba(245, 197, 24, 0.12); color: #f5c518; --f-color: #f5c518; }
    .feature-card h3 { font-size: 18px; font-weight: 800; margin-bottom: 10px; color: var(--text-main); }
    .feature-card p { font-size: 13px; color: var(--text-muted); line-height: 1.7; }

    /* ====== HƯỚNG DẪN SỬ DỤNG ====== */
    .guide-section {
        max-width: 900px; margin: 60px auto; padding: 0 20px;
    }
    .guide-title { text-align: center; font-size: 32px; font-weight: 900; margin-bottom: 10px; color: var(--text-main); }
    .guide-sub { text-align: center; color: var(--text-muted); margin-bottom: 40px; }
    .guide-steps {
        display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
        gap: 24px;
    }
    .step-card {
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 20px; padding: 24px 20px; text-align: center;
        transition: 0.3s; backdrop-filter: blur(8px);
    }
    .step-card:hover { border-color: var(--accent); transform: translateY(-4px); box-shadow: var(--glow-accent); }
    .step-number {
        display: inline-flex; align-items: center; justify-content: center;
        width: 44px; height: 44px; border-radius: 50%;
        background: var(--accent-hover); color: var(--accent);
        font-weight: 900; font-size: 18px; margin-bottom: 16px;
        border: 1px solid var(--border-light);
    }
    .step-icon { font-size: 32px; margin-bottom: 12px; display: block; color: var(--accent); }
    .step-card h3 { font-size: 16px; font-weight: 800; margin-bottom: 8px; color: var(--text-main); }
    .step-card p { font-size: 13px; color: var(--text-muted); line-height: 1.6; }

    /* ====== TREO ROOM / TREO TOOLS ====== */
    .explain-section {
        max-width: 820px; margin: 60px auto; padding: 0 20px;
    }
    .explain-box {
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 28px; padding: 36px 30px;
        backdrop-filter: blur(12px);
    }
    .explain-box h2 { font-size: 28px; font-weight: 900; margin-bottom: 16px; color: var(--text-main); display: flex; align-items: center; gap: 12px; }
    .explain-box h2 svg { width: 32px; height: 32px; color: var(--accent); stroke-width: 1.5; }
    .explain-box p { font-size: 15px; color: var(--text-muted); line-height: 1.8; margin-bottom: 12px; }

    /* ====== FAQ ====== */
    .faq-section {
        max-width: 820px; margin: 60px auto; padding: 0 20px;
    }
    .faq-section .faq-title {
        text-align: center; font-size: 32px; font-weight: 900; margin-bottom: 10px;
        color: var(--text-main);
    }
    .faq-section .faq-sub {
        text-align: center; color: var(--text-muted); margin-bottom: 40px;
    }
    .faq-item {
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 16px; margin-bottom: 12px; overflow: hidden;
        transition: 0.3s; cursor: pointer;
    }
    .faq-item:hover { border-color: var(--border-hover); }
    .faq-question {
        display: flex; justify-content: space-between; align-items: center;
        padding: 16px 20px; font-weight: 700; font-size: 15px;
        color: var(--text-main); user-select: none;
    }
    .faq-question .arrow {
        transition: transform 0.3s; color: var(--accent);
        font-size: 20px; line-height: 1;
    }
    .faq-item.open .faq-question .arrow { transform: rotate(180deg); }
    .faq-answer {
        max-height: 0; overflow: hidden; transition: max-height 0.3s ease, padding 0.3s ease;
        padding: 0 20px; color: var(--text-muted); font-size: 14px; line-height: 1.6;
    }
    .faq-item.open .faq-answer {
        max-height: 300px; padding: 0 20px 20px 20px;
    }

    /* ====== AUTHOR ====== */
    .author-section {
        max-width: 820px; margin: 80px auto 40px; padding: 0 20px;
        display: flex; flex-wrap: wrap; gap: 30px;
        background: var(--card-bg); border: 1px solid var(--border-light);
        border-radius: 28px; padding: 36px 30px;
        backdrop-filter: blur(12px);
    }
    .author-left { flex: 1 1 200px; text-align: center; }
    .author-left img { width: 100%; max-width: 220px; border-radius: 20px; border: 2px solid var(--accent); box-shadow: var(--glow-accent); }
    .author-right { flex: 2 1 300px; }
    .author-name {
        font-size: 28px; font-weight: 900; color: var(--text-main);
        margin-bottom: 6px;
    }
    .author-role {
        font-size: 14px; color: var(--text-muted); margin-bottom: 18px;
    }
    .author-social {
        display: flex; gap: 18px; flex-wrap: wrap; margin: 16px 0 20px;
    }
    .social-link {
        display: inline-flex; align-items: center; gap: 8px;
        background: rgba(255,255,255,0.04); padding: 8px 16px;
        border-radius: 30px; border: 1px solid var(--border-light);
        text-decoration: none; color: var(--text-main); font-weight: 600;
        transition: 0.3s; font-size: 13px;
    }
    .social-link:hover { border-color: var(--accent); background: var(--accent-hover); color: var(--accent); }
    .social-link.discord { border-color: #5865F2; }
    .social-link.discord:hover { background: rgba(88,101,242,0.12); color: #5865F2; border-color: #5865F2; }
    .social-link.telegram { border-color: #0088cc; }
    .social-link.telegram:hover { background: rgba(0,136,204,0.12); color: #0088cc; border-color: #0088cc; }
    .social-link svg { width: 20px; height: 20px; fill: currentColor; flex-shrink: 0; }

    .contact-info {
        display: grid; grid-template-columns: 1fr 1fr; gap: 8px 20px;
        margin-top: 10px; font-size: 13px; color: var(--text-muted);
    }
    .contact-info .label { font-weight: 700; color: var(--text-main); }
    .contact-info a { color: var(--accent); text-decoration: none; }
    .contact-info a:hover { text-decoration: underline; }

    .footer { text-align: center; padding: 40px 20px; border-top: 1px solid var(--border-light); margin-top: 40px; color: var(--text-muted); font-size: 13px; }

    @media (max-width: 600px) {
        .hero h1 { font-size: 34px; }
        .hero p { font-size: 14px; }
        .hero-btns { flex-direction: column; align-items: center; }
        .stat-box { flex: 1 1 45%; min-width: 140px; padding: 16px 20px; }
        .author-section { flex-direction: column; align-items: center; text-align: center; }
        .contact-info { grid-template-columns: 1fr; }
        .author-social { justify-content: center; }
        .intro-box { flex-direction: column; text-align: center; }
        .guide-steps { grid-template-columns: 1fr 1fr; }
        .step-card { padding: 18px; }
    }
</style>
</head>
<body>

""" + TG_FLOAT_BTN + """

<nav class="landing-nav">
    <a href="/" class="logo">
        <svg class="logo-icon svg-icon" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path></svg>
        ZaTools
    </a>
    <div class="nav-right">
        <button class="theme-toggle-btn" onclick="toggleTheme()">
            <svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24" style="width:18px;height:18px;"></svg>
        </button>
        <a href="/login/discord" class="landing-nav-btn">Đăng nhập</a>
    </div>
</nav>

<div class="hero reveal">
    <div class="hero-badge"><span class="hero-badge-dot"></span> Hoạt động mượt mà 24/7</div>
    <h1>Giữ Discord của bạn<br><span class="gradient-text">Luôn Online & Đẳng Cấp</span></h1>
    <p>Lưu trữ nhiều tài khoản Discord trong Voice Channel, thiết lập Custom Rich Presence tuỳ chỉnh, và hoàn toàn không cần treo máy tính cá nhân.</p>
    <div class="hero-btns">
        <a href="/login/discord" class="hero-btn-primary">
            <svg viewBox="0 0 24 24" width="20" height="20" fill="currentColor" stroke="none"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189Z"/></svg>
            Bắt Đầu Miễn Phí
        </a>
        <a href="#guide" class="hero-btn-secondary">Hướng dẫn sử dụng ↓</a>
    </div>

    <div class="stats-container">
        <div class="stat-box"><div class="stat-val">500+</div><div class="stat-label">Người dùng</div></div>
        <div class="stat-box"><div class="stat-val">99.9%</div><div class="stat-label">Uptime</div></div>
        <div class="stat-box"><div class="stat-val">24/7</div><div class="stat-label">Hoạt động</div></div>
    </div>
</div>

<div class="intro-section reveal">
    <div class="intro-box">
        <div class="intro-icon">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor">
                <path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"/>
                <circle cx="12" cy="12" r="3"/>
            </svg>
        </div>
        <div class="intro-text">
            <h2>ZaTools là gì?</h2>
            <p><strong>ZaTools</strong> là nền tảng đám mây cho phép bạn giữ tài khoản Discord luôn <strong>Online 24/7</strong> mà không cần mở máy tính. Chỉ cần cung cấp Token và thông tin Voice Channel, hệ thống sẽ tự động kết nối và duy trì trạng thái <strong>trong phòng thoại</strong> cùng với <strong>Rich Presence</strong> tùy chỉnh – giúp bạn nổi bật và tăng cấp độ.</p>
        </div>
    </div>
</div>

<div id="features" class="features reveal">
    <div class="features-head">
        <div class="features-eyebrow">CHÚNG TÔI CUNG CẤP GÌ</div>
        <h2>Mọi Thứ Bạn Cần Để Trở Nên Khác Biệt</h2>
        <p>Tự động hóa hoàn toàn trên đám mây, an toàn và bảo mật.</p>
    </div>
    <div class="feature-grid">
        <div class="feature-card reveal" style="--f-color:#a855f7">
            <div class="f-icon pink">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
                    <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
                </svg>
            </div>
            <h3>Treo Voice Vĩnh Cửu</h3>
            <p>Khóa cứng tài khoản của bạn trong bất kỳ Voice Channel nào. Tự động nối mạng sau 5 giây nếu có sự cố.</p>
        </div>
        <div class="feature-card reveal" style="--f-color:#00c8ff">
            <div class="f-icon blue">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline>
                </svg>
            </div>
            <h3>Custom RPC Tối Thượng</h3>
            <p>Tự do cài đặt Tên Game, Dòng chi tiết, Thời gian chơi và Gắn Nút bấm URL nhảy link.</p>
        </div>
        <div class="feature-card reveal" style="--f-color:#00e676">
            <div class="f-icon green">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="3" y="11" width="18" height="11" rx="2" ry="2"></rect>
                    <path d="M7 11V7a5 5 0 0 1 10 0v4"></path>
                </svg>
            </div>
            <h3>Bảo Mật An Toàn</h3>
            <p>Không lưu trữ mật khẩu Discord. Mọi quá trình xác thực đều thông qua OAuth2 an toàn tuyệt đối.</p>
        </div>
        <div class="feature-card reveal" style="--f-color:#f5c518">
            <div class="f-icon yellow">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon>
                </svg>
            </div>
            <h3>Live Log Cực Nhanh</h3>
            <p>Theo dõi tiến trình kết nối theo thời gian thực. Mọi hoạt động hiển thị rõ ràng trên Dashboard.</p>
        </div>
    </div>
</div>

<div id="guide" class="guide-section reveal">
    <div class="guide-title">📘 Hướng dẫn sử dụng</div>
    <div class="guide-sub">Chỉ với 4 bước đơn giản, bạn đã có thể treo tài khoản Discord 24/7</div>
    <div class="guide-steps">
        <div class="step-card">
            <div class="step-number">1</div>
            <div class="step-icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path>
                    <circle cx="12" cy="7" r="4"></circle>
                </svg>
            </div>
            <h3>Đăng nhập Discord</h3>
            <p>Bấm nút <strong>"Đăng nhập"</strong> ở góc phải trang chủ, hệ thống sẽ chuyển hướng đến Discord để xác thực.</p>
        </div>
        <div class="step-card">
            <div class="step-number">2</div>
            <div class="step-icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <rect x="2" y="2" width="20" height="20" rx="2.5"></rect>
                    <line x1="6" y1="9" x2="18" y2="9"></line>
                    <line x1="6" y1="15" x2="18" y2="15"></line>
                    <line x1="10" y1="3" x2="10" y2="21"></line>
                </svg>
            </div>
            <h3>Lấy Token Discord</h3>
            <p>Sao chép Token của bạn từ trình duyệt (hướng dẫn chi tiết có trong phần FAQ). Token giúp hệ thống đăng nhập thay bạn.</p>
        </div>
        <div class="step-card">
            <div class="step-number">3</div>
            <div class="step-icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path>
                    <polyline points="17 21 17 13 7 13 7 21"></polyline>
                </svg>
            </div>
            <h3>Nhập thông tin</h3>
            <p>Điền Token, ID máy chủ (Guild) và ID kênh Voice. Có thể cấu hình Rich Presence nếu muốn.</p>
        </div>
        <div class="step-card">
            <div class="step-number">4</div>
            <div class="step-icon">
                <svg viewBox="0 0 24 24" width="36" height="36" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <polygon points="5 3 19 12 5 21 5 3"></polygon>
                </svg>
            </div>
            <h3>Bấm "Treo ngay"</h3>
            <p>Nhấn nút <strong>"CHẠY NGAY"</strong> để bắt đầu. Hệ thống sẽ tự động kết nối và giữ trạng thái online mãi mãi.</p>
        </div>
    </div>
</div>

<div class="explain-section reveal">
    <div class="explain-box">
        <h2>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M3 18v-6a9 9 0 0 1 18 0v6"></path>
                <path d="M21 19a2 2 0 0 1-2 2h-1a2 2 0 0 1-2-2v-3a2 2 0 0 1 2-2h3zM3 19a2 2 0 0 0 2 2h1a2 2 0 0 0 2-2v-3a2 2 0 0 0-2-2H3z"></path>
            </svg>
            Treo room / Treo tools là gì?
        </h2>
        <p><strong>Treo room</strong> (hay "treo voice") là hành động giữ tài khoản Discord của bạn ở trong một phòng thoại (Voice Channel) liên tục 24/7 mà không cần bạn phải mở ứng dụng Discord hay bật máy tính. Điều này giúp bạn <strong>luôn hiện diện</strong> trong server, tăng độ uy tín, và có thể dùng để tăng cấp độ (level) nếu server có tính năng cộng điểm khi online.</p>
        <p><strong>Treo tools</strong> là thuật ngữ chỉ việc sử dụng các công cụ tự động (như ZaTools) để thực hiện việc treo room này một cách ổn định và an toàn, với các tính năng nâng cao như <strong>Rich Presence</strong> (hiển thị trạng thái chơi game) giúp bạn trở nên nổi bật và chuyên nghiệp hơn.</p>
        <p>Với ZaTools, bạn có thể treo <strong>nhiều tài khoản</strong> cùng lúc (tùy gói), và hoàn toàn <strong>không lo bị ngắt kết nối</strong> nhờ cơ chế tự động kết nối lại khi có sự cố.</p>
    </div>
</div>

<div class="faq-section reveal">
    <div class="faq-title">💬 Câu Hỏi Thường Gặp</div>
    <div class="faq-sub">Những thắc mắc phổ biến khi sử dụng ZaTools</div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>🔒 Token của tôi có được bảo mật không?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            <strong>ZaTools</strong> không lưu trữ token Discord của bạn trên máy chủ dưới dạng văn bản thuần túy. Mọi quá trình xác thực đều thông qua OAuth2 và token được mã hóa. Bạn hoàn toàn có thể yên tâm về tính bảo mật.
        </div>
    </div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>🤔 Discord account token là gì?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            Token Discord là một chuỗi ký tự đặc biệt dùng để xác thực tài khoản của bạn với API Discord. Nó giống như mật khẩu phiên, cho phép ứng dụng (như ZaTools) thực hiện các tác vụ thay mặt bạn mà không cần đăng nhập lại.
        </div>
    </div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>📊 Tôi có thể treo nhiều tài khoản cùng lúc không?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            Có! Tùy vào gói dịch vụ của bạn (Free, Starter, Pro, VIP) mà số lượng token được phép treo khác nhau. Gói VIP cho phép lên đến 35 token cùng lúc.
        </div>
    </div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>🔄 Chuyện gì xảy ra khi tôi tắt trình duyệt?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            Các phiên treo token chạy hoàn toàn trên máy chủ đám mây của ZaTools, vì vậy bạn có thể tắt trình duyệt hoặc tắt máy tính mà các tài khoản vẫn duy trì trạng thái online 24/7.
        </div>
    </div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>⚠️ Tại sao trạng thái báo "Đang kết nối lại"?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            Khi mạng không ổn định hoặc Discord gặp sự cố, hệ thống sẽ tự động thử kết nối lại sau 5 giây. Bạn không cần làm gì cả, quá trình diễn ra tự động và trạng thái sẽ nhanh chóng trở lại bình thường.
        </div>
    </div>

    <div class="faq-item">
        <div class="faq-question" onclick="toggleFaq(this)">
            <span>🚫 Tài khoản của tôi có bị khóa không?</span>
            <span class="arrow">▼</span>
        </div>
        <div class="faq-answer">
            Việc sử dụng token để kết nối Voice Channel và thiết lập Rich Presence là hoàn toàn hợp lệ theo chính sách của Discord. Tuy nhiên, để đảm bảo an toàn, bạn không nên chia sẻ token với bất kỳ ai và chỉ sử dụng cho mục đích cá nhân.
        </div>
    </div>
</div>

<div class="author-section reveal">
    <div class="author-left">
        <img src="https://i.imgur.com/IeytfHP.jpeg" alt="ZaTools Creator" />
    </div>
    <div class="author-right">
        <div class="author-name">Phan Tran Dang Khoi</div>
        <div class="author-role">✨ Nhà sáng lập ZaTools</div>
        <div class="author-social">
            <a href="https://discord.gg/K2rqbgGBC" target="_blank" class="social-link discord">
                <svg viewBox="0 0 24 24"><path d="M20.317 4.3698a19.7913 19.7913 0 00-4.8851-1.5152.0741.0741 0 00-.0785.0371c-.211.3753-.4447.8648-.6083 1.2495-1.8447-.2762-3.68-.2762-5.4868 0-.1636-.3933-.4058-.8742-.6177-1.2495a.077.077 0 00-.0785-.037 19.7363 19.7363 0 00-4.8852 1.515.0699.0699 0 00-.0321.0277C.5334 9.0458-.319 13.5799.0992 18.0578a.0824.0824 0 00.0312.0561c2.0528 1.5076 4.0413 2.4228 5.9929 3.0294a.0777.0777 0 00.0842-.0276c.4616-.6304.8731-1.2952 1.226-1.9942a.076.076 0 00-.0416-.1057c-.6528-.2476-1.2743-.5495-1.8722-.8923a.077.077 0 01-.0076-.1277c.1258-.0943.2517-.1923.3718-.2914a.0743.0743 0 01.0776-.0105c3.9278 1.7933 8.18 1.7933 12.0614 0a.0739.0739 0 01.0785.0095c.1202.099.246.1981.3728.2924a.077.077 0 01-.0066.1276 12.2986 12.2986 0 01-1.873.8914.0766.0766 0 00-.0407.1067c.3604.698.7719 1.3628 1.225 1.9932a.076.076 0 00.0842.0286c1.961-.6067 3.9495-1.5219 6.0023-3.0294a.077.077 0 00.0313-.0552c.5004-5.177-.8382-9.6739-3.5485-13.6604a.061.061 0 00-.0312-.0286zM8.02 15.3312c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9555-2.4189 2.157-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.9555 2.4189-2.1569 2.4189zm7.9748 0c-1.1825 0-2.1569-1.0857-2.1569-2.419 0-1.3332.9554-2.4189 2.1569-2.4189 1.2108 0 2.1757 1.0952 2.1568 2.419 0 1.3332-.946 2.4189-2.1568 2.4189z"/></svg>
                Hỗ trợ Discord
            </a>
            <a href="https://t.me/thiendangcuaanh" target="_blank" class="social-link telegram">
                <svg viewBox="0 0 24 24"><path d="M12 0C5.373 0 0 5.373 0 12s5.373 12 12 12 12-5.373 12-12S18.627 0 12 0zm5.562 8.248l-1.97 9.28c-.145.658-.537.818-1.084.508l-3-2.21-1.447 1.394c-.16.16-.295.295-.605.295l.213-3.053 5.56-5.023c.242-.213-.054-.333-.373-.12L6.54 14.26l-2.96-.924c-.643-.204-.657-.643.136-.953l11.57-4.461c.537-.194 1.006.131.276.326z"/></svg>
                Telegram
            </a>
        </div>
        <div class="contact-info">
            <div><span class="label">📧 Email</span><br><a href="mailto:ptdk28012010@gmail.com">ptdk28012010@gmail.com</a></div>
            <div><span class="label">📞 SĐT</span><br><a href="tel:0347201938">0347201938</a></div>
            <div style="grid-column: 1 / -1;"><span class="label">🏠 Địa chỉ</span><br>Vạn Kiếp, Bình Thạnh, TP.HCM</div>
        </div>
    </div>
</div>

<div class="footer reveal">
    <p>&copy; 2026 ZaTools Premium — Developed by Dang Khoi</p>
    <p style="color: var(--success-text); margin-top: 10px; display:flex; align-items:center; justify-content:center; gap:6px; font-size:12px; font-weight:700;">
        <span style="width:7px; height:7px; background:var(--success-text); border-radius:50%; display:inline-block; box-shadow: 0 0 8px var(--success-text); animation: blink 1.5s infinite;"></span>
        All systems operational
    </p>
</div>

""" + THEME_SCRIPT + """
<script>
    function reveal() {
        document.querySelectorAll(".reveal").forEach(el => {
            if (el.getBoundingClientRect().top < window.innerHeight - 60) el.classList.add("active");
        });
    }
    window.addEventListener("scroll", reveal);
    reveal();

    function toggleFaq(element) {
        const item = element.closest('.faq-item');
        if (item.classList.contains('open')) {
            item.classList.remove('open');
        } else {
            item.classList.add('open');
        }
    }
</script>
</body>
</html>
"""

# ================== AUTH ERROR PAGE ==================
HTML_AUTH = HTML_HEAD + """
<title>ZaTools - Lỗi Đăng Nhập</title>
<style>
    body { display: flex; justify-content: center; align-items: center; min-height: 100vh; }
    .login-box { max-width: 380px; width: 90%; text-align: center; padding: 40px 30px; border-radius: 24px; background: var(--card-bg); border: 1px solid var(--border-light); backdrop-filter: blur(20px); }
</style>
</head>
<body>
    <div class="login-box">
        <div class="msg error">
            <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
            Hãy ra trang chủ đăng nhập bằng Discord!
        </div>
        <a href="/" style="color:var(--accent); text-decoration:none; font-weight:700;">← Quay lại trang chủ</a>
    </div>
""" + THEME_SCRIPT + """
</body>
</html>
"""

# ================== DASHBOARD CHÍNH (ĐÃ TÁCH TAB) ==================
HTML_MAIN = HTML_HEAD + """
<title>ZaTools - Dashboard</title>
<style>
    /* ===== NAVBAR ===== */
    .navbar {
        display: flex; justify-content: space-between; align-items: center;
        padding: 14px 5%;
        background: var(--nav-bg);
        backdrop-filter: blur(24px);
        border-bottom: 1px solid var(--border-light);
        position: sticky; top: 0; z-index: 1000;
    }
    .nav-right { display: flex; align-items: center; gap: 12px; position: relative; }

    .user-menu-btn {
        display: flex; align-items: center; gap: 10px;
        background: var(--card-bg);
        border: 1px solid var(--border-light);
        padding: 6px 14px 6px 6px;
        border-radius: 30px; cursor: pointer; transition: 0.3s; color: var(--text-main);
    }
    .user-menu-btn:hover { border-color: var(--accent); background: var(--accent-hover); }
    .avatar-img { width: 32px; height: 32px; border-radius: 50%; object-fit: cover; border: 2px solid var(--accent); }
    .user-name { font-size: 13px; font-weight: 700; max-width: 120px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis; }

    /* ===== DROPDOWN ===== */
    .dropdown-menu {
        position: absolute; top: 52px; right: 0;
        background: rgba(8,16,36,0.98);
        border: 1px solid var(--border-light);
        border-radius: 18px; width: 210px; padding: 8px;
        box-shadow: 0 20px 50px rgba(0,0,0,0.6);
        backdrop-filter: blur(30px);
        opacity: 0; visibility: hidden; transform: translateY(-8px); transition: 0.25s;
        z-index: 1001;
    }
    [data-theme="light"] .dropdown-menu { background: rgba(255,255,255,0.98); }
    .dropdown-menu.active { opacity: 1; visibility: visible; transform: translateY(0); }

    .dp-item {
        display: flex;
        align-items: center;
        gap: 11px;
        padding: 11px 14px;
        color: var(--text-muted);
        text-decoration: none;
        font-size: 13px;
        font-weight: 600;
        border-radius: 12px;
        transition: 0.2s;
        cursor: pointer;
        white-space: nowrap;
    }
    .dp-item .svg-icon {
        width: 16px; height: 16px; min-width: 16px; flex-shrink: 0;
        overflow: visible;
    }
    .dp-item:hover, .dp-item.active-tab { background: var(--accent-hover); color: var(--accent); }
    .dp-logout { color: var(--danger-text); border-top: 1px dashed rgba(255,68,88,0.15); margin-top: 6px; padding-top: 10px; border-radius: 0; }
    .dp-logout:hover { background: rgba(255, 68, 88, 0.08); color: var(--danger-text); border-radius: 12px; }

    /* ===== CONTAINER ===== */
    .container { max-width: 700px; width: 100%; margin: 28px auto; padding: 0 14px; }

    /* ===== STATS GRID ===== */
    .stats-grid { display: grid; grid-template-columns: repeat(2, 1fr); gap: 12px; margin-bottom: 22px; }
    .stat-card {
        background: var(--card-bg);
        border: 1px solid var(--border-light);
        border-radius: 18px; padding: 18px 16px;
        text-align: left; transition: 0.3s;
        backdrop-filter: blur(16px);
        position: relative; overflow: hidden;
    }
    .stat-card::after {
        content: ''; position: absolute; top: 0; left: 0; right: 0; height: 2px;
        background: linear-gradient(90deg, transparent, var(--stat-color, var(--accent)), transparent);
        opacity: 0; transition: 0.3s;
    }
    .stat-card:hover { border-color: var(--stat-color, var(--accent)); transform: translateY(-3px); box-shadow: 0 12px 28px rgba(0,0,0,0.25); }
    .stat-card:hover::after { opacity: 1; }

    .stat-card h3 {
        font-size: 10px;
        color: var(--text-muted);
        text-transform: uppercase;
        font-weight: 800;
        letter-spacing: 0.8px;
        margin-bottom: 10px;
        display: flex;
        align-items: center;
        gap: 6px;
        overflow: visible;
    }
    .stat-card h3 .svg-icon {
        width: 14px; height: 14px; min-width: 14px;
        overflow: visible;
        color: var(--stat-color, var(--accent));
        opacity: 0.8;
    }
    .stat-card h2 { font-size: 26px; font-weight: 900; color: var(--text-main); line-height: 1; }
    .stat-card h2 span { display: block; font-size: 11px; color: var(--text-muted); font-weight: 500; margin-top: 5px; }
    .stat-card .highlight { color: var(--plan-text); }
    .stat-card.accent-coin { --stat-color: var(--coin-color); }
    .stat-card.accent-success { --stat-color: var(--success-text); }
    .stat-card.accent-purple { --stat-color: var(--plan-text); }

    /* ===== CARDS ===== */
    .card {
        background: var(--card-bg);
        backdrop-filter: blur(16px);
        border-radius: 22px; padding: 24px;
        margin-bottom: 18px;
        border: 1px solid var(--border-light);
        transition: 0.3s;
    }
    .card-title {
        color: var(--text-main); font-size: 14px; font-weight: 800;
        margin-bottom: 20px;
        display: flex; align-items: center; justify-content: space-between;
        border-bottom: 1px solid var(--border-light); padding-bottom: 14px;
    }

    /* ===== INPUTS ===== */
    .input-group { margin-bottom: 14px; }
    .input-group label { display: block; color: var(--text-muted); font-size: 11px; margin-bottom: 6px; font-weight: 700; text-transform: uppercase; letter-spacing: 0.8px; }
    .input-group input {
        width: 100%; padding: 13px 15px;
        background: var(--input-bg);
        border: 1px solid var(--input-border);
        border-radius: 12px; color: var(--text-main); font-size: 13px; outline: none; transition: 0.3s;
    }
    .input-group input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-hover); }
    .input-group input::placeholder { color: var(--text-muted); opacity: 0.7; }

    /* ===== BUTTONS ===== */
    .btn {
        width: 100%; padding: 13px; border-radius: 12px; font-weight: 800; font-size: 12px;
        cursor: pointer; text-align: center; border: none; transition: 0.2s;
        display: flex; align-items: center; justify-content: center; gap: 8px;
        text-transform: uppercase; text-decoration: none; letter-spacing: 0.5px;
    }
    .btn-primary { background: var(--btn-bg); color: #fff; box-shadow: 0 4px 14px rgba(0,200,255,0.2); }
    .btn-primary:hover { opacity: 0.92; transform: translateY(-2px); box-shadow: 0 8px 22px rgba(0,200,255,0.35); }
    .btn-success { background: rgba(0, 230, 118, 0.1); border: 1px solid rgba(0, 230, 118, 0.25); color: var(--success-text); }
    .btn-success:hover { background: rgba(0, 230, 118, 0.18); transform: translateY(-1px); }
    .btn-danger { background: rgba(255, 68, 88, 0.1); border: 1px solid rgba(255, 68, 88, 0.25); color: var(--danger-text); padding: 11px; }
    .btn-danger:hover { background: rgba(255, 68, 88, 0.18); }
    .btn-buy { background: rgba(245, 197, 24, 0.1); border: 1px solid rgba(245, 197, 24, 0.25); color: var(--coin-color); margin-top:12px; }
    .btn-buy:hover { background: rgba(245, 197, 24, 0.18); }
    .btn-flex { display: flex; gap: 10px; }
    .btn-flex .btn { flex: 1; }

    /* ===== TAB SYSTEM ===== */
    .tab-header {
        display: flex; gap: 8px; margin-bottom: 18px;
        background: rgba(255,255,255,0.02); padding: 5px; border-radius: 14px;
        border: 1px solid var(--input-border);
        flex-wrap: wrap;
    }
    .tab-btn { flex: 1; padding: 10px; text-align: center; font-size: 12px; font-weight: 700; color: var(--text-muted); cursor: pointer; border-radius: 10px; transition: 0.3s; letter-spacing: 0.5px; text-transform: uppercase; min-width: 80px; }
    .tab-btn.active { background: var(--btn-bg); color: #fff; box-shadow: 0 4px 12px rgba(0,200,255,0.2); }

    .tab-content { display: none; animation: fadeIn 0.3s; }
    .tab-content.active { display: block; }
    @keyframes fadeIn { from { opacity: 0; transform: translateY(8px); } to { opacity: 1; transform: translateY(0); } }

    /* ===== RPC SECTION ===== */
    .rpc-section {
        border: 1px dashed rgba(0, 200, 255, 0.25);
        padding: 18px; border-radius: 14px; margin-bottom: 14px;
        background: rgba(0, 200, 255, 0.02);
    }
    .rpc-title {
        color: var(--accent); font-size: 11px; font-weight: 800; margin-bottom: 14px;
        text-transform: uppercase; display: flex; align-items: center; gap: 6px;
        letter-spacing: 1px;
    }
    .rpc-title .svg-icon { width: 13px; height: 13px; min-width: 13px; overflow: visible; }
    .input-row { display: flex; gap: 10px; }
    .input-row .input-group { flex: 1; }

    /* ===== SWITCHES ===== */
    .options-grid { display: grid; grid-template-columns: 1fr 1fr; gap: 10px; margin: 18px 0; }
    .switch-wrap {
        display: flex; align-items: center; justify-content: space-between;
        padding: 12px 14px; background: rgba(255,255,255,0.02);
        border-radius: 12px; border: 1px solid var(--input-border);
    }
    .switch-label { font-size: 13px; font-weight: 600; color: var(--text-main); }
    .switch { position: relative; display: inline-block; width: 40px; height: 22px; flex-shrink: 0; }
    .switch input { opacity: 0; width: 0; height: 0; }
    .slider { position: absolute; cursor: pointer; top: 0; left: 0; right: 0; bottom: 0; background-color: var(--input-border); transition: .4s; border-radius: 34px; }
    .slider:before { position: absolute; content: ""; height: 16px; width: 16px; left: 3px; bottom: 3px; background-color: #fff; transition: .4s; border-radius: 50%; }
    input:checked + .slider { background-color: var(--accent); }
    input:checked + .slider:before { transform: translateX(18px); }

    /* ===== ACCOUNT CARDS ===== */
    .account-card {
        background: rgba(255,255,255,0.02);
        border-radius: 14px; padding: 14px 16px;
        margin-bottom: 10px;
        border: 1px solid var(--input-border);
        transition: 0.2s;
    }
    .account-card:hover { border-color: var(--border-hover); }
    .account-card .name {
        font-weight: 700; font-size: 14px; margin-bottom: 4px;
        display: flex; align-items: center; gap: 7px;
    }
    .account-card .name .svg-icon { width: 15px; height: 15px; min-width: 15px; overflow: visible; color: var(--accent); }
    .account-card .status-badge {
        font-size: 11px; font-weight: 600; display: inline-flex; align-items: center; gap: 4px;
        padding: 2px 10px; border-radius: 30px;
    }
    .status-online { color: var(--success-text); background: rgba(0,230,118,0.1); border: 1px solid rgba(0,230,118,0.2); }
    .status-offline { color: var(--danger-text); background: rgba(255,68,88,0.1); border: 1px solid rgba(255,68,88,0.2); }

    .account-actions {
        display: flex; flex-wrap: wrap; gap: 6px; margin-top: 10px;
    }
    .account-actions .btn { width: auto; padding: 6px 14px; font-size: 11px; }
    .account-actions .btn-icon { padding: 6px 10px; }

    .log-container {
        margin-top: 12px; background: rgba(0,0,0,0.5); border-radius: 12px;
        padding: 12px; max-height: 180px; overflow-y: auto;
        font-family: 'Courier New', monospace; font-size: 11px; color: #00e676;
        border: 1px solid var(--input-border); white-space: pre-wrap; word-break: break-all;
        line-height: 1.6; display: none;
    }
    .log-container.open { display: block; }
    .log-container::-webkit-scrollbar { width: 4px; }
    .log-container::-webkit-scrollbar-track { background: transparent; }
    .log-container::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 4px; }

    .rpc-edit-form {
        margin-top: 12px; padding: 14px; background: rgba(255,255,255,0.03);
        border-radius: 12px; border: 1px solid var(--input-border); display: none;
    }
    .rpc-edit-form.open { display: block; }

    /* ===== LOG BOX (giữ cho tab treo nếu có) ===== */
    .log-box {
        background: rgba(0,0,0,0.5); border-radius: 14px; padding: 15px;
        max-height: 240px; overflow-y: auto;
        font-family: 'Courier New', monospace; font-size: 11px; color: #00e676;
        border: 1px solid var(--input-border); white-space: pre-wrap; word-break: break-all;
        line-height: 1.6;
    }
    .log-box::-webkit-scrollbar { width: 4px; }
    .log-box::-webkit-scrollbar-track { background: transparent; }
    .log-box::-webkit-scrollbar-thumb { background: var(--accent); border-radius: 4px; }

    /* ===== PLAN BOXES ===== */
    .plan-box {
        background: rgba(255,255,255,0.02); border: 1px solid var(--input-border);
        border-radius: 16px; padding: 20px; margin-bottom: 14px; text-align: center; transition: 0.3s;
    }
    .plan-box:hover { transform: translateY(-3px); border-color: var(--coin-color); box-shadow: 0 8px 24px rgba(0,0,0,0.2); }
    .plan-title { font-size: 12px; font-weight: 800; color: var(--text-muted); margin-bottom: 6px; text-transform: uppercase; letter-spacing: 1px; }
    .plan-price { font-size: 26px; font-weight: 900; color: var(--text-main); margin-bottom: 12px; }
    .plan-feature { font-size: 12px; color: var(--text-main); margin-bottom: 5px; display: flex; align-items: center; justify-content: center; gap: 6px; }
    .plan-vip { border-color: rgba(168, 85, 247, 0.4); }
    .plan-vip .plan-title { color: var(--plan-text); }

    /* ===== OVERLAY ===== */
    .overlay { position: fixed; top: 0; left: 0; width: 100%; height: 100%; background: rgba(0,0,0,0.4); z-index: 999; display: none; backdrop-filter: blur(2px); }
    .overlay.active { display: block; }

    /* ===== FOOTER ===== */
    .footer { text-align: center; margin-top: 40px; padding-bottom: 100px; font-size: 12px; color: var(--text-muted); font-weight: 500; }

    /* ===== MOBILE ===== */
    @media (max-width: 600px) {
        .account-card .account-actions { flex-direction: column; align-items: stretch; }
        .account-actions .btn { width: 100%; justify-content: center; }
        .input-row { flex-direction: column; gap: 0; }
        .tab-btn { font-size: 10px; padding: 8px; min-width: 60px; }
    }
</style>
</head>
<body>

<div class="overlay" id="mobileOverlay" onclick="toggleDropdown()"></div>

""" + TG_FLOAT_BTN + """

<nav class="navbar">
    <a href="/" class="logo">
        <svg class="logo-icon svg-icon" viewBox="0 0 24 24"><path d="M12 2L2 7l10 5 10-5-10-5zM2 17l10 5 10-5M2 12l10 5 10-5"></path></svg>
        ZaTools
    </a>
    <div class="nav-right">
        <button class="theme-toggle-btn" onclick="toggleTheme()">
            <svg class="svg-icon" id="theme-icon" viewBox="0 0 24 24" style="width:18px;height:18px;"></svg>
        </button>
        <div class="user-menu-btn" onclick="toggleDropdown()">
            <img src="{{ avatar_url }}" class="avatar-img" onerror="this.src='https://cdn.discordapp.com/embed/avatars/0.png'">
            <div class="user-name">{{ current_user }}</div>
            <svg class="svg-icon" style="width:15px;height:15px;" viewBox="0 0 24 24"><line x1="3" y1="12" x2="21" y2="12"></line><line x1="3" y1="6" x2="21" y2="6"></line><line x1="3" y1="18" x2="21" y2="18"></line></svg>
        </div>
        <div class="dropdown-menu" id="userDropdown">
            <a href="#" class="dp-item active-tab" onclick="switchTab('treo', this)">
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 20h9"></path><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z"></path></svg>
                Thiết Lập Treo
            </a>
            <a href="#" class="dp-item" onclick="switchTab('running', this)">
                <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"/><polyline points="12 6 12 12 16 14"/></svg>
                Acc Đang Hoạt Động
            </a>
            <a href="#" class="dp-item" onclick="switchTab('saved', this)">
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline><polyline points="7 3 7 8 15 8"></polyline></svg>
                Kho Dữ Liệu
            </a>
            <a href="#" class="dp-item" onclick="switchTab('premium', this)">
                <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                Nạp & Mua Gói
            </a>
            {% if is_admin %}
            <a href="/admin_dangkhoi" class="dp-item" style="color: var(--plan-text);">
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
                Mắt Thần Admin
            </a>
            {% endif %}
            <a href="/logout" class="dp-item dp-logout">
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"></path><polyline points="16 17 21 12 16 7"></polyline><line x1="21" y1="12" x2="9" y2="12"></line></svg>
                Đăng xuất
            </a>
        </div>
    </div>
</nav>

<div class="container">
    {% if flash_msg %}
    <div class="msg {{ flash_type }}">
        {% if flash_type == 'success' %}
        <svg class="svg-icon" viewBox="0 0 24 24"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        {% else %}
        <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>
        {% endif %}
        {{ flash_msg }}
    </div>
    {% endif %}

    <div class="stats-grid">
        <div class="stat-card accent-success">
            <h3>
                <svg class="svg-icon" viewBox="0 0 24 24"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                Trạng Thái
            </h3>
            <h2 style="color:var(--success-text);">{{ running_count }} <span>đang chạy</span></h2>
        </div>
        <div class="stat-card">
            <h3>
                <svg class="svg-icon" viewBox="0 0 24 24"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
                Giới Hạn
            </h3>
            <h2>{{ max_tokens }} <span>acc tối đa</span></h2>
        </div>
        <div class="stat-card accent-coin">
            <h3>
                <svg class="svg-icon" viewBox="0 0 24 24"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="16"></line><line x1="8" y1="12" x2="16" y2="12"></line></svg>
                Số Dư Ví
            </h3>
            <h2 style="color: var(--coin-color);">{{ "{:,}".format(balance) }}<small style="font-size:14px;">đ</small></h2>
        </div>
        <div class="stat-card accent-purple">
            <h3>
                <svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                Gói Cước
            </h3>
            <h2 class="highlight">{{ plan_name }}</h2>
        </div>
    </div>

    <!-- ======== TAB 1: THIẾT LẬP TREO ======== -->
    <div id="tab-treo" class="tab-content active">
        <form method="POST">
            <div class="card">
                <div class="card-title">Tạo Cấu Hình Mới</div>
                <div class="input-group"><label>Tên gợi nhớ (nếu lưu)</label><input type="text" name="profile_name" placeholder="Ví dụ: Acc Cày Cấp..."></div>
                <div class="input-group"><label>Discord Token</label><input type="text" name="token" required placeholder="Nhập Token của bạn..."></div>
                <div class="input-group"><label>ID Máy chủ</label><input type="text" name="guild_id" required placeholder="1234567890..."></div>
                <div class="input-group"><label>ID Kênh Voice</label><input type="text" name="channel_id" required placeholder="1234567890..."></div>

                <div class="rpc-section">
                    <div class="rpc-title">
                        <svg class="svg-icon" viewBox="0 0 24 24"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                        Thiết lập Rich Presence (RPC)
                    </div>
                    <div class="input-group"><label>Tiêu đề Game</label><input type="text" name="status_text" placeholder="VD: ZaTools Premium..."></div>
                    <div class="input-row">
                        <div class="input-group"><label>Dòng chi tiết 1</label><input type="text" name="rpc_details" placeholder="VD: Đang leo Rank..."></div>
                        <div class="input-group"><label>Dòng chi tiết 2</label><input type="text" name="rpc_state" placeholder="VD: Trận 5/10..."></div>
                    </div>
                    <div class="input-group"><label>Link Ảnh Lớn (HTTPS)</label><input type="text" name="rpc_image" placeholder="https://i.imgur.com/..."></div>
                    <div class="input-row">
                        <div class="input-group"><label>Tên Nút 1</label><input type="text" name="rpc_b1_name" placeholder="VD: Facebook"></div>
                        <div class="input-group"><label>Link Nút 1</label><input type="text" name="rpc_b1_url" placeholder="https://..."></div>
                    </div>
                    <div class="input-row">
                        <div class="input-group"><label>Tên Nút 2</label><input type="text" name="rpc_b2_name" placeholder="VD: ZaTools Group"></div>
                        <div class="input-group"><label>Link Nút 2</label><input type="text" name="rpc_b2_url" placeholder="https://..."></div>
                    </div>
                </div>

                <div class="options-grid">
                    <div class="switch-wrap"><div class="switch-label">Tắt Mic</div><label class="switch"><input type="checkbox" name="mute" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Tắt Âm</div><label class="switch"><input type="checkbox" name="deaf" checked><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Cam Ảo</div><label class="switch"><input type="checkbox" name="video"><span class="slider"></span></label></div>
                    <div class="switch-wrap"><div class="switch-label">Live Ảo</div><label class="switch"><input type="checkbox" name="stream"><span class="slider"></span></label></div>
                </div>

                <div class="btn-flex">
                    <button type="submit" formaction="/start" class="btn btn-primary">
                        <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        CHẠY NGAY
                    </button>
                    <button type="submit" formaction="/save_profile" class="btn btn-success">
                        <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><path d="M19 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11l5 5v11a2 2 0 0 1-2 2z"></path><polyline points="17 21 17 13 7 13 7 21"></polyline></svg>
                        LƯU LẠI
                    </button>
                </div>
            </div>
        </form>
        <!-- Không hiển thị danh sách bot hay terminal ở đây -->
    </div>

    <!-- ======== TAB 2: ACC ĐANG HOẠT ĐỘNG ======== -->
    <div id="tab-running" class="tab-content">
        <div class="card">
            <div class="card-title">
                Danh sách Acc Treo
                {% if running_count > 0 %}
                <form method="POST" action="/stop_all" style="margin:0;">
                    <button type="submit" class="btn btn-danger" style="padding:7px 14px; font-size:11px; width:auto;">DỪNG HẾT</button>
                </form>
                {% endif %}
            </div>
            {% for key, bot in bot_items %}
            <div class="account-card" data-bot-key="{{ key }}">
                <div style="display: flex; justify-content: space-between; align-items: flex-start; flex-wrap: wrap;">
                    <div>
                        <div class="name">
                            <svg class="svg-icon" viewBox="0 0 24 24"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="12" r="4"></circle></svg>
                            {{ bot.get('display_name', 'Đang kết nối...') }}
                        </div>
                        <div>
                            <span class="status-badge {% if bot.connected %}status-online{% else %}status-offline{% endif %}">
                                {% if bot.connected %}⬤ Online{% else %}● Offline{% endif %}
                            </span>
                        </div>
                    </div>
                    <div style="display: flex; gap: 6px; margin-top: 6px;">
                        <button class="btn btn-success btn-icon" onclick="toggleLog('{{ key }}')" style="padding:6px 10px;">
                            <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><polyline points="22 12 18 12 15 21 9 3 6 12 2 12"></polyline></svg>
                            Log
                        </button>
                        <button class="btn btn-primary btn-icon" onclick="toggleRPC('{{ key }}')" style="padding:6px 10px;">
                            <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
                            RPC
                        </button>
                        <form method="POST" action="/stop" style="margin:0;">
                            <input type="hidden" name="bot_key" value="{{ key }}">
                            <button type="submit" class="btn btn-danger btn-icon" style="padding:6px 10px;">
                                <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect></svg>
                            </button>
                        </form>
                    </div>
                </div>

                <!-- Log riêng -->
                <div class="log-container" id="log-{{ key }}">Đang tải log...</div>

                <!-- Form chỉnh sửa RPC -->
                <div class="rpc-edit-form" id="rpc-{{ key }}">
                    <form method="POST" action="/update_bot">
                        <input type="hidden" name="bot_key" value="{{ key }}">
                        <div class="input-group"><label>Tiêu đề Game</label><input type="text" name="status_text" value="{{ bot.get('status_text', '') }}" placeholder="Game..."></div>
                        <div class="input-row">
                            <div class="input-group"><label>Dòng 1</label><input type="text" name="rpc_details" value="{{ bot.get('rpc_details', '') }}" placeholder="Details..."></div>
                            <div class="input-group"><label>Dòng 2</label><input type="text" name="rpc_state" value="{{ bot.get('rpc_state', '') }}" placeholder="State..."></div>
                        </div>
                        <div class="input-group"><label>Ảnh lớn (URL)</label><input type="text" name="rpc_image" value="{{ bot.get('rpc_image', '') }}" placeholder="https://..."></div>
                        <div class="input-row">
                            <div class="input-group"><label>Tên Nút 1</label><input type="text" name="rpc_b1_name" value="{{ bot.get('rpc_b1_name', '') }}"></div>
                            <div class="input-group"><label>Link Nút 1</label><input type="text" name="rpc_b1_url" value="{{ bot.get('rpc_b1_url', '') }}"></div>
                        </div>
                        <div class="input-row">
                            <div class="input-group"><label>Tên Nút 2</label><input type="text" name="rpc_b2_name" value="{{ bot.get('rpc_b2_name', '') }}"></div>
                            <div class="input-group"><label>Link Nút 2</label><input type="text" name="rpc_b2_url" value="{{ bot.get('rpc_b2_url', '') }}"></div>
                        </div>
                        <button type="submit" class="btn btn-primary" style="margin-top:8px;">CẬP NHẬT RPC</button>
                    </form>
                </div>
            </div>
            {% else %}
            <div style="font-size:12px; color:var(--text-muted); text-align:center; padding: 25px 0;">Chưa có tài khoản nào đang hoạt động.</div>
            {% endfor %}
        </div>
    </div>

    <!-- ======== TAB 3: KHO DỮ LIỆU ======== -->
    <div id="tab-saved" class="tab-content">
        <div class="card">
            <div class="card-title">Kho Dữ Liệu Cá Nhân</div>
            {% for profile in saved_profiles %}
            <div class="account-card">
                <div>
                    <div class="name" style="color: var(--coin-color);">{{ profile.profile_name }}</div>
                    <div style="font-size:11px; color:var(--text-muted); margin-top:3px;">Máy chủ: {{ profile.guild_id }}</div>
                </div>
                <div style="display:flex; gap:8px; margin-top:6px;">
                    <form method="POST" action="/start_saved">
                        <input type="hidden" name="profile_id" value="{{ profile._id }}">
                        <button type="submit" class="btn btn-success" style="padding:10px 14px; width:auto;">
                            <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                        </button>
                    </form>
                    <form method="POST" action="/delete_profile">
                        <input type="hidden" name="profile_id" value="{{ profile._id }}">
                        <button type="submit" class="btn btn-danger" style="padding:10px 14px; width:auto;">
                            <svg class="svg-icon" viewBox="0 0 24 24" style="width:14px;height:14px;overflow:visible;"><polyline points="3 6 5 6 21 6"></polyline><path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path></svg>
                        </button>
                    </form>
                </div>
            </div>
            {% endfor %}
            {% if not saved_profiles %}<div style="text-align:center; font-size:12px; color:var(--text-muted); padding: 22px 0;">Kho trống. Hãy lưu cấu hình ở tab Thiết Lập Treo!</div>{% endif %}
        </div>
    </div>

    <!-- ======== TAB 4: NẠP & MUA GÓI ======== -->
    <div id="tab-premium" class="tab-content">
        <div class="tab-header" style="justify-content: center; gap: 6px;">
            <div class="tab-btn active" id="btn-nap" onclick="switchSubTab('nap')">NẠP COIN</div>
            <div class="tab-btn" id="btn-mua" onclick="switchSubTab('mua')">CỬA HÀNG GÓI</div>
        </div>

        <div id="sub-nap" class="card">
            <div class="card-title" style="color: var(--coin-color);">NẠP SỐ DƯ (1 VNĐ = 1 COIN)</div>
            <p style="font-size:12px; color:var(--text-muted); text-align:center; margin-bottom:15px;">Quét QR chuyển khoản. Tiền vào ví tự động sau ~5 giây.</p>
            <div class="input-group"><input type="number" id="nap_amount" placeholder="Nhập số tiền muốn nạp..." min="10000" step="10000"></div>
            <button onclick="generateNapQR()" class="btn btn-primary" style="margin-bottom:20px;">TẠO MÃ NẠP</button>
            <div id="qr_nap_area" style="display: none; text-align: center; border-top: 1px dashed var(--input-border); padding-top: 20px; margin-top:20px;">
                <img id="qr_nap_img" src="" style="width: 200px; border-radius: 14px; border: 2px solid var(--coin-color);">
                <div style="margin-top: 14px; font-size: 13px; background: var(--input-bg); padding: 12px 16px; border-radius: 12px; border: 1px solid var(--input-border);">
                    <span style="color:var(--text-muted); font-size:11px;">NỘI DUNG CHUYỂN KHOẢN</span><br>
                    <b style="color:var(--success-text); font-size: 18px; letter-spacing: 2px; margin-top:6px; display:block;">ZATOOLS <span id="clean_username"></span></b>
                </div>
                <div id="payment_status" class="msg" style="display:none; margin-top:14px; background:rgba(245, 197, 24, 0.08); color:var(--coin-color); border:1px solid rgba(245, 197, 24, 0.25);">⏳ Đang chờ ngân hàng xử lý...</div>
            </div>
        </div>

        <div id="sub-mua" class="card" style="display: none;">
            <div class="card-title" style="color: var(--plan-text);">MUA GÓI (30 NGÀY)</div>
            <div style="display:grid; gap:12px;">
                <div class="plan-box" style="margin:0;">
                    <div class="plan-title">GÓI STARTER</div>
                    <div class="plan-price">20,000đ</div>
                    <div class="plan-feature">✓ Treo tối đa 2 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="STARTER"><button type="submit" class="btn btn-buy">MUA BẰNG COIN</button></form>
                </div>
                <div class="plan-box" style="margin:0; border-color:var(--accent);">
                    <div class="plan-title" style="color:var(--accent);">GÓI PRO</div>
                    <div class="plan-price">40,000đ</div>
                    <div class="plan-feature">✓ Treo tối đa 5 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="PRO"><button type="submit" class="btn btn-buy">MUA BẰNG COIN</button></form>
                </div>
                <div class="plan-box plan-vip" style="margin:0;">
                    <div class="plan-title">GÓI VIP</div>
                    <div class="plan-price">300,000đ</div>
                    <div class="plan-feature">✓ Treo tối đa 35 Token</div>
                    <form method="POST" action="/buy_plan"><input type="hidden" name="plan" value="VIP"><button type="submit" class="btn" style="margin-top:12px; background:var(--btn-bg2); color:#fff; width:100%;">MUA GÓI VIP</button></form>
                </div>
            </div>
        </div>
    </div>

    <div class="footer">
        <div>&copy; 2026 ZaTools Premium — Developed by Dang Khoi</div>
        <div style="color: var(--success-text); display:flex; justify-content:center; align-items:center; gap:6px; margin-top:8px; font-size:11px; font-weight:700;">
            <span style="width:6px; height:6px; background:var(--success-text); border-radius:50%; box-shadow:0 0 8px var(--success-text); animation:blink 1.5s infinite;"></span>
            Hệ thống hoạt động bình thường
        </div>
        <div style="margin-top:10px;">
            <a href="https://t.me/thiendangcuaanh" target="_blank" style="color:var(--accent); text-decoration:none; font-size:11px; font-weight:700;">📞 Liên hệ hỗ trợ: t.me/thiendangcuaanh</a>
        </div>
    </div>
</div>

""" + THEME_SCRIPT + """
<style>
    @keyframes blink { 0%,100%{ opacity:1; } 50%{ opacity:0.3; } }
</style>
<script>
    function toggleDropdown() {
        document.getElementById('userDropdown').classList.toggle('active');
        document.getElementById('mobileOverlay').classList.toggle('active');
    }
    function switchTab(tabId, el) {
        document.querySelectorAll('.tab-content').forEach(t => t.classList.remove('active'));
        document.getElementById('tab-' + tabId).classList.add('active');
        document.querySelectorAll('.dp-item').forEach(l => l.classList.remove('active-tab'));
        if(el) el.classList.add('active-tab');
        document.getElementById('userDropdown').classList.remove('active');
        document.getElementById('mobileOverlay').classList.remove('active');
        localStorage.setItem('za_active_tab', tabId);
    }
    function switchSubTab(sub) {
        ['nap','mua'].forEach(s => {
            document.getElementById('sub-' + s).style.display = 'none';
            document.getElementById('btn-' + s).classList.remove('active');
        });
        document.getElementById('sub-' + sub).style.display = 'block';
        document.getElementById('btn-' + sub).classList.add('active');
    }

    // Toggle log container
    function toggleLog(botKey) {
        const logEl = document.getElementById('log-' + botKey);
        if (logEl.classList.contains('open')) {
            logEl.classList.remove('open');
        } else {
            logEl.classList.add('open');
            // Load log từ API
            fetch('/api/get_logs?bot_key=' + botKey)
                .then(r => r.json())
                .then(data => {
                    if (data.log && data.log.length > 0) {
                        logEl.innerHTML = data.log.join('\\n');
                    } else {
                        logEl.innerHTML = 'Chưa có log cho tài khoản này.';
                    }
                    logEl.scrollTop = logEl.scrollHeight;
                })
                .catch(() => { logEl.innerHTML = 'Lỗi tải log.'; });
        }
    }

    // Toggle RPC edit form
    function toggleRPC(botKey) {
        const form = document.getElementById('rpc-' + botKey);
        form.classList.toggle('open');
    }

    // Tự động load log cho các acc đang mở khi load trang (nếu có)
    document.addEventListener('DOMContentLoaded', function() {
        // Không tự động mở log khi tải trang
    });

    let checkPaymentInterval;
    let currentBalance = {{ balance }};
    function generateNapQR() {
        let amount = document.getElementById('nap_amount').value;
        if(!amount || amount < 10000) { alert('Vui lòng nạp tối thiểu 10.000 VNĐ'); return; }
        let rawUser = '{{ current_user }}';
        let cleanUser = rawUser.replace(/_/g,"").replace(/-/g,"").replace(/ /g,"");
        document.getElementById('clean_username').innerText = cleanUser;
        let addInfo = encodeURIComponent('ZATOOLS ' + cleanUser);
        document.getElementById('qr_nap_img').src = `https://img.vietqr.io/image/MB-1628012010-compact2.png?amount=${amount}&addInfo=${addInfo}&accountName=Phan%20Tran%20Dang%20Khoi`;
        document.getElementById('qr_nap_area').style.display = 'block';
        document.getElementById('payment_status').style.display = 'flex';
        if(checkPaymentInterval) clearInterval(checkPaymentInterval);
        checkPaymentInterval = setInterval(checkBalance, 3000);
    }
    function checkBalance() {
        fetch('/api/get_balance').then(r => r.json()).then(data => {
            if(data.balance > currentBalance) {
                clearInterval(checkPaymentInterval);
                currentBalance = data.balance;
                let ps = document.getElementById('payment_status');
                ps.style.background = 'rgba(0,230,118,0.08)'; ps.style.color = 'var(--success-text)'; ps.style.borderColor = 'rgba(0,230,118,0.25)';
                ps.innerHTML = '✅ Đã nạp thành công! Vui lòng F5 lại trang.';
            }
        });
    }

    // Xử lý active tab từ URL hoặc localStorage
    window.onload = () => {
        let reqTab = '{{ active_tab }}';
        let tabToLoad = reqTab !== 'None' ? reqTab : (localStorage.getItem('za_active_tab') || 'treo');
        let links = document.querySelectorAll('.dp-item');
        let targetLink = Array.from(links).find(l => l.getAttribute('onclick') && l.getAttribute('onclick').includes("'" + tabToLoad + "'"));
        if(targetLink) switchTab(tabToLoad, targetLink);
    };
</script>
</body>
</html>
"""

# ================== ADMIN PANEL ==================
HTML_ADMIN = HTML_HEAD + """
<title>Admin Panel - ZaTools</title>
<style>
    body { min-height: 100vh; }
    .admin-container { max-width: 580px; width: 95%; margin: 30px auto; padding: 28px; background: var(--card-bg); border-radius: 22px; border: 1px solid var(--border-light); box-shadow: 0 20px 50px rgba(0,0,0,0.3); backdrop-filter: blur(16px); }
    .stat-box { background: var(--input-bg); padding: 14px 18px; border-radius: 12px; margin-bottom: 10px; display: flex; justify-content: space-between; border: 1px solid var(--input-border); font-weight: 600; color: var(--text-muted); font-size: 13px; }
    .stat-val { color: var(--text-main); font-size: 18px; font-weight: 800; }
    .action-box { background: rgba(0, 200, 255, 0.04); border: 1px solid var(--accent); padding: 20px; border-radius: 16px; margin-top: 20px; }
    .action-box h3 { color: var(--accent); font-size: 12px; margin-bottom: 14px; text-transform: uppercase; letter-spacing: 1px; font-weight: 800; }
    .input-group { margin-bottom: 12px; }
    .input-group input { width: 100%; padding: 12px 14px; background: var(--input-bg); border: 1px solid var(--input-border); border-radius: 11px; color: var(--text-main); font-size: 13px; outline: none; transition: 0.3s; }
    .input-group input:focus { border-color: var(--accent); box-shadow: 0 0 0 3px var(--accent-hover); }
    .btn { width: 100%; padding: 13px; border-radius: 11px; font-weight: 800; font-size: 12px; cursor: pointer; text-align: center; border: none; transition: 0.2s; text-transform: uppercase; letter-spacing: 0.5px; }
    .btn-primary { background: var(--btn-bg); color: #fff; }
    .btn-primary:hover { opacity: 0.9; transform: translateY(-1px); }
</style>
</head>
<body>
""" + TG_FLOAT_BTN + """
<div class="admin-container">
    <h2 style="color:var(--text-main); text-align:center; margin-bottom:24px; display:flex; justify-content:center; align-items:center; gap:10px; font-size:18px;">
        <svg class="svg-icon" viewBox="0 0 24 24" style="color:var(--plan-text); width:24px; height:24px; min-width:24px; overflow:visible;"><path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"></path><circle cx="12" cy="12" r="3"></circle></svg>
        BẢNG ĐIỀU KHIỂN
    </h2>
    {% if msg %}<div class="msg success" style="display:flex; align-items:center; gap:8px; padding:12px 16px; background:rgba(0,230,118,0.08); border:1px solid rgba(0,230,118,0.2); border-radius:12px; color:var(--success-text); font-size:13px; font-weight:600; margin-bottom:16px;">{{ msg }}</div>{% endif %}

    <div class="stat-box">Khách hàng: <span class="stat-val">{{ stats.users }}</span></div>
    <div class="stat-box">Token đang lưu: <span class="stat-val">{{ stats.bots }}</span></div>
    <div class="stat-box">Luồng cày ngầm: <span class="stat-val" style="color:var(--success-text);">{{ stats.running }}</span></div>
    <div class="stat-box">Doanh thu: <span class="stat-val" style="color:var(--coin-color);">{{ "{:,}".format(stats.total_money) }} đ</span></div>

    <div class="action-box">
        <h3>Cộng tiền thủ công</h3>
        <form method="POST" action="/admin_action">
            <input type="hidden" name="action" value="add_coin">
            <div class="input-group"><input type="text" name="target_user" required placeholder="Nhập username khách..."></div>
            <div class="input-group"><input type="number" name="amount" required placeholder="Số Coin cần cộng..."></div>
            <button type="submit" class="btn btn-primary">XÁC NHẬN CỘNG</button>
        </form>
    </div>
    <div class="action-box" style="background: rgba(245, 197, 24, 0.04); border-color: var(--coin-color);">
        <h3 style="color:var(--coin-color);">Đồng bộ SePay bị sót</h3>
        <form method="POST" action="/admin_action">
            <input type="hidden" name="action" value="sync_sepay">
            <button type="submit" class="btn" style="background:var(--coin-color); color:#000;">QUÉT & ĐỒNG BỘ LẠI</button>
        </form>
    </div>
    <div style="text-align:center; margin-top:20px;">
        <a href="/" style="color:var(--text-muted); text-decoration:none; font-weight:600; font-size:13px;">← Trở về Dashboard</a>
    </div>
</div>
""" + THEME_SCRIPT + """
</body>
</html>
"""

# ================== BOT LOGIC CẢI TIẾN ==================
def run_bot(bot_key, config, username):
    token = config.get('token')
    guild_id = config.get('guild_id')
    channel_id = config.get('channel_id')
    mute = str(config.get('mute', 'False')).lower() in ['true', 'on', '1']
    deaf = str(config.get('deaf', 'False')).lower() in ['true', 'on', '1']
    video = str(config.get('video', 'False')).lower() in ['true', 'on', '1']
    stream = str(config.get('stream', 'False')).lower() in ['true', 'on', '1']
    start_time = int(time.time() * 1000)

    if username not in user_bots:
        user_bots[username] = {}
    user_bots[username][bot_key] = {
        'connected': False,
        'log': [],
        'running': True,
        'display_name': 'Đang kết nối...',
        'status_text': config.get('status_text', ''),
        'rpc_details': config.get('rpc_details', ''),
        'rpc_state': config.get('rpc_state', ''),
        'rpc_image': config.get('rpc_image', ''),
        'rpc_b1_name': config.get('rpc_b1_name', ''),
        'rpc_b1_url': config.get('rpc_b1_url', ''),
        'rpc_b2_name': config.get('rpc_b2_name', ''),
        'rpc_b2_url': config.get('rpc_b2_url', ''),
        'ws': None
    }

    def add_log(msg):
        if username in user_bots and bot_key in user_bots[username]:
            timestamp = time.strftime('%H:%M:%S')
            user_bots[username][bot_key]['log'].append(f"[{timestamp}] {msg}")
            if len(user_bots[username][bot_key]['log']) > 50:
                user_bots[username][bot_key]['log'] = user_bots[username][bot_key]['log'][-50:]

    def update_status(st):
        if username in user_bots and bot_key in user_bots[username]:
            user_bots[username][bot_key]['connected'] = st

    def send_voice_update(ws_client, init_stream=False):
        if not ws_client or not ws_client.keep_running:
            return
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
                        except:
                            pass
                threading.Timer(1.5, fire_stream).start()
        except:
            pass

    # Cache ảnh RPC để tránh upload lại
    rpc_image_cache = {}

    while user_bots[username][bot_key]['running']:
        try:
            gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except Exception as e:
            add_log(f"Không lấy được gateway: {e}")
            time.sleep(5)
            continue

        ws = None
        last_seq = None
        heartbeat_interval = 41250
        connected = False

        def on_message(ws_client, message):
            nonlocal last_seq, connected, heartbeat_interval
            try:
                data = json.loads(message)
            except:
                return
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
                        "name": status_text,
                        "type": 0,
                        "application_id": rpc_app_id,
                        "timestamps": {"start": start_time}
                    }
                    if config.get('rpc_details'):
                        activity["details"] = config.get('rpc_details')
                    if config.get('rpc_state'):
                        activity["state"] = config.get('rpc_state')

                    rpc_image = config.get('rpc_image', '').strip()
                    if rpc_image.startswith('http'):
                        # Kiểm tra cache
                        if rpc_image in rpc_image_cache:
                            rpc_image = rpc_image_cache[rpc_image]
                        else:
                            try:
                                res = requests.post(
                                    f"https://discord.com/api/v9/applications/{rpc_app_id}/external-assets",
                                    headers={"Authorization": token, "Content-Type": "application/json"},
                                    json={"urls": [rpc_image]},
                                    timeout=5
                                )
                                if res.status_code == 200:
                                    rpc_image = f"mp:{res.json()[0]['external_asset_path']}"
                                    rpc_image_cache[rpc_image] = rpc_image
                                else:
                                    add_log(f"⚠️ Upload ảnh RPC thất bại ({res.status_code})")
                            except Exception as e:
                                add_log(f"Lỗi upload ảnh RPC: {e}")

                    if rpc_image:
                        activity["assets"] = {"large_image": rpc_image, "large_text": status_text}

                    buttons, metadata_urls = [], []
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
                    add_log("🎨 Gắn Custom RPC thành công!")

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
                    if username in user_bots and bot_key in user_bots[username]:
                        user_bots[username][bot_key]['display_name'] = d_name
                    add_log(f"🎯 Đăng nhập thành công: {d_name}")
                    send_voice_update(ws_client, init_stream=True)

                elif t == 'VOICE_STATE_UPDATE':
                    d = data['d']
                    if d.get('channel_id') == channel_id and not connected:
                        connected = True
                        update_status(True)
                        add_log("✅ Đã tham gia phòng thoại vĩnh cửu!")
                    elif d.get('channel_id') is None and connected:
                        connected = False
                        update_status(False)
                        add_log("⚠️ Bị văng khỏi phòng! Đang kết nối lại...")
                        send_voice_update(ws_client, init_stream=True)

            elif op == 9:
                if data.get('d') == False:
                    add_log("❌ Token không hợp lệ hoặc đã hết hạn! Dừng bot.")
                    if username in user_bots and bot_key in user_bots[username]:
                        user_bots[username][bot_key]['running'] = False
                    ws_client.close()
                else:
                    add_log("🔄 Session không hợp lệ, đang reconnect...")
                    ws_client.close()

        def on_close(ws_client, code, msg):
            nonlocal connected
            if connected:
                connected = False
                update_status(False)
            add_log(f"🔌 Mất kết nối (code {code})! Sẽ thử lại sau 5s...")

        def on_error(ws_client, error):
            if "Connection closed" not in str(error):
                add_log(f"💥 Lỗi WebSocket: {error}")

        def heartbeat_loop():
            while (username in user_bots and bot_key in user_bots[username] and
                   user_bots[username][bot_key]['running'] and ws and ws.keep_running):
                time.sleep(heartbeat_interval)
                try:
                    if ws.keep_running:
                        ws.send(json.dumps({"op": 1, "d": last_seq}))
                except:
                    pass

        # Tạo WebSocketApp
        ws = websocket.WebSocketApp(
            gateway + "/?v=9&encoding=json",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        # Lưu ws để có thể đóng từ bên ngoài
        if username in user_bots and bot_key in user_bots[username]:
            user_bots[username][bot_key]['ws'] = ws

        # Khởi động heartbeat loop
        hb_thread = threading.Thread(target=heartbeat_loop, daemon=True)
        hb_thread.start()

        # Chạy WebSocket với ping tự động
        ws.run_forever(ping_interval=30, ping_timeout=10)

        # Khi run_forever kết thúc, nếu vẫn còn chạy thì đợi rồi reconnect
        if not (username in user_bots and bot_key in user_bots[username] and
                user_bots[username][bot_key]['running']):
            break
        add_log("⏳ Đang thử kết nối lại sau 5 giây...")
        time.sleep(5)

    add_log("🛑 Bot đã dừng hoàn toàn.")

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
            if bot_key not in user_bots[username]:
                threading.Thread(target=run_bot, args=(bot_key, config, username), daemon=True).start()
    except:
        pass
auto_bootloader()

# ================== ROUTES ==================
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
    bot_key = request.args.get('bot_key')
    if bot_key and usr in user_bots and bot_key in user_bots[usr]:
        bot = user_bots[usr][bot_key]
        return jsonify({"log": bot.get('log', []), "connected": bot.get('connected', False)})
    # Nếu không có bot_key, trả về log của bot đầu tiên (tương thích)
    if usr in user_bots and user_bots[usr]:
        first_key = next(iter(user_bots[usr]))
        bot = user_bots[usr][first_key]
        return jsonify({"log": bot.get('log', []), "connected": bot.get('connected', False)})
    return jsonify({"log": [], "connected": False})

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
        session['flash_msg'] = f"Đã mua thành công Gói {plan}! Hạn dùng: 30 ngày."
        session['flash_type'] = "success"
    else:
        session['flash_msg'] = "Ví của bạn không đủ Coin. Vui lòng nạp thêm!"
        session['flash_type'] = "error"
    return redirect(url_for('index', tab='premium'))

@app.route('/khoideptrai_admin')
def claim_admin():
    if 'username' not in session: return "Hãy ra trang chủ bấm 'Đăng nhập bằng Discord' trước nhé sếp!"
    users_collection.update_one({"username": session['username']}, {"$set": {"is_admin": True, "max_tokens": 9999}})
    return "✅ SẾP ĐÃ TRỞ THÀNH QUẢN TRỊ VIÊN TỐI CAO. HÃY QUAY LẠI TRANG CHỦ!"

@app.route('/')
def index():
    if 'username' not in session:
        return render_template_string(HTML_LANDING)
    usr = session['username']
    avatar_url = session.get('avatar', 'https://cdn.discordapp.com/embed/avatars/0.png')
    max_tokens, expiry_info, plan_name = get_user_limit(usr)
    db_user = users_collection.find_one({"username": usr})
    is_admin = db_user.get('is_admin', False) if db_user else False
    balance = db_user.get('balance', 0) if db_user else 0
    active_bots = [(k, v) for k, v in user_bots.get(usr, {}).items() if v.get('running', False)]
    return render_template_string(HTML_MAIN, bot_items=active_bots, current_user=usr, avatar_url=avatar_url, balance=balance, plan_name=plan_name,
                                  saved_profiles=get_saved_profiles(usr), max_tokens=max_tokens,
                                  running_count=len(active_bots), is_admin=is_admin, expiry_info=expiry_info,
                                  flash_msg=session.pop('flash_msg', None), flash_type=session.pop('flash_type', 'success'),
                                  active_tab=request.args.get('tab', 'None'))

@app.route('/start', methods=['POST'])
def start():
    if 'username' not in session: return redirect(url_for('index'))
    usr = session['username']
    max_tokens, _, _ = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    
    token = request.form.get('token', '').strip()
    token_suffix = token[-10:] if len(token) > 10 else token
    bot_key = f"{token_suffix}_{request.form.get('guild_id')}_{request.form.get('channel_id')}"
    
    if current_running >= max_tokens and bot_key not in user_bots.get(usr, {}):
        session['flash_msg'] = f"Gói của bạn ({max_tokens} slot) đã đầy hoặc hết hạn!"
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='treo'))
        
    config = {
        'token': token, 'guild_id': request.form.get('guild_id', '').strip(), 'channel_id': request.form.get('channel_id', '').strip(),
        'status_text': request.form.get('status_text', '').strip(), 'rpc_details': request.form.get('rpc_details', '').strip(), 'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(), 'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(), 'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(), 'rpc_b2_url': request.form.get('rpc_b2_url', '').strip(),
        'mute': request.form.get('mute') == 'on', 'deaf': request.form.get('deaf') == 'on', 'video': request.form.get('video') == 'on', 'stream': request.form.get('stream') == 'on'
    }
    
    save_storage_item(bot_key, config, usr)
    
    if usr not in user_bots: user_bots[usr] = {}
    if bot_key in user_bots[usr]:
        user_bots[usr][bot_key]['running'] = False
        time.sleep(0.5)
    
    threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
    return redirect(url_for('index', tab='treo'))

@app.route('/start_saved', methods=['POST'])
def start_saved():
    usr = session.get('username')
    if not usr:
        return redirect(url_for('index'))
        
    max_tokens, _, _ = get_user_limit(usr)
    current_running = sum(1 for v in user_bots.get(usr, {}).values() if v.get('running', False))
    prof_id = request.form.get('profile_id')
    
    try:
        prof = saved_profiles_collection.find_one({"_id": prof_id}) or saved_profiles_collection.find_one({"_id": ObjectId(prof_id)})
    except:
        prof = None
        
    if prof:
        token = prof.get('token', '').strip()
        token_suffix = token[-10:] if len(token) > 10 else token
        bot_key = f"{token_suffix}_{prof.get('guild_id')}_{prof.get('channel_id')}"
        
        if bot_key not in user_bots.get(usr, {}) and current_running >= max_tokens:
            session['flash_msg'] = f"Bạn đã dùng hết {max_tokens} slot. Vui lòng nâng cấp gói để treo thêm!"
            session['flash_type'] = "error"
            return redirect(url_for('index', tab='saved'))
            
        if bot_key in user_bots.get(usr, {}):
            session['flash_msg'] = "Tài khoản này đã được treo rồi!"
            session['flash_type'] = "success"
            return redirect(url_for('index', tab='treo'))
            
        config = {k:v for k,v in prof.items() if k not in ['_id', 'owner', 'profile_name']}
        config['bot_key'] = bot_key
        save_storage_item(bot_key, config, usr)
        
        if usr not in user_bots: user_bots[usr] = {}
        if bot_key in user_bots[usr]:
            user_bots[usr][bot_key]['running'] = False
            time.sleep(0.5)
            
        threading.Thread(target=run_bot, args=(bot_key, config, usr), daemon=True).start()
        session['flash_msg'] = "Đã bắt đầu treo tài khoản từ kho!"
        session['flash_type'] = "success"
    else:
        session['flash_msg'] = "Không tìm thấy cấu hình!"
        session['flash_type'] = "error"
        
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
    session['flash_type'] = "success"
    return redirect(url_for('index', tab='saved'))

@app.route('/login', methods=['GET'])
def login():
    if 'username' in session: return redirect(url_for('index'))
    return render_template_string(HTML_AUTH)

@app.route('/delete_profile', methods=['POST'])
def del_prof():
    pid = request.form.get('profile_id')
    try:
        if not saved_profiles_collection.delete_one({"_id": pid}).deleted_count:
            saved_profiles_collection.delete_one({"_id": ObjectId(pid)})
    except:
        pass
    return redirect(url_for('index', tab='saved'))

@app.route('/stop', methods=['POST'])
def stop():
    usr = session['username']
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key, usr)
    if usr in user_bots and bot_key in user_bots[usr]:
        user_bots[usr][bot_key]['running'] = False
        if 'ws' in user_bots[usr][bot_key]:
            try:
                user_bots[usr][bot_key]['ws'].close()
            except:
                pass
        del user_bots[usr][bot_key]
    return redirect(url_for('index', tab='running'))

@app.route('/stop_all', methods=['POST'])
def stop_all():
    usr = session.get('username')
    if usr in user_bots:
        for bot_key in list(user_bots[usr].keys()):
            delete_storage_item(bot_key, usr)
            user_bots[usr][bot_key]['running'] = False
            if 'ws' in user_bots[usr][bot_key]:
                try:
                    user_bots[usr][bot_key]['ws'].close()
                except:
                    pass
            del user_bots[usr][bot_key]
    session['flash_msg'] = "Đã tắt thành công toàn bộ Token!"
    session['flash_type'] = "success"
    return redirect(url_for('index', tab='running'))

@app.route('/login/discord')
def login_discord():
    return redirect(OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord", scope=['identify']).authorization_url(DISCORD_AUTH_URL)[0])

@app.route('/callback/discord')
def cb_discord():
    discord = OAuth2Session(DISCORD_CLIENT_ID, redirect_uri=f"{get_base_url()}/callback/discord")
    discord.fetch_token(DISCORD_TOKEN_URL, client_secret=DISCORD_CLIENT_SECRET, authorization_response=request.url.replace('http://', 'https://'))
    user_data = discord.get('https://discord.com/api/users/@me').json()
    usr = f"{user_data.get('username')}_dc"
    user_id = user_data.get('id')
    avatar_hash = user_data.get('avatar')
    if avatar_hash:
        avatar_url = f"https://cdn.discordapp.com/avatars/{user_id}/{avatar_hash}.png"
    else:
        avatar_url = "https://cdn.discordapp.com/embed/avatars/0.png"
    if not users_collection.find_one({"username": usr}):
        users_collection.insert_one({"username": usr, "oauth": "discord", "avatar": avatar_url, "max_tokens": 1, "expiry_date": 0, "balance": 0})
    else:
        users_collection.update_one({"username": usr}, {"$set": {"avatar": avatar_url}})
    session['username'] = usr
    session['avatar'] = avatar_url
    return redirect(url_for('index'))

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('index'))

@app.route('/ping')
def ping():
    return "ok"

@app.route('/refresh', methods=['POST'])
def refresh():
    return redirect(url_for('index', tab=request.form.get('tab', 'treo')))

# ===== ENDPOINT CẬP NHẬT RPC CHO BOT =====
@app.route('/update_bot', methods=['POST'])
def update_bot():
    if 'username' not in session:
        return redirect(url_for('index'))
    usr = session['username']
    bot_key = request.form.get('bot_key')
    if not bot_key or usr not in user_bots or bot_key not in user_bots[usr]:
        session['flash_msg'] = "Không tìm thấy bot!"
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='running'))
    
    # Lấy config mới từ form
    new_config = {
        'status_text': request.form.get('status_text', '').strip(),
        'rpc_details': request.form.get('rpc_details', '').strip(),
        'rpc_state': request.form.get('rpc_state', '').strip(),
        'rpc_image': request.form.get('rpc_image', '').strip(),
        'rpc_b1_name': request.form.get('rpc_b1_name', '').strip(),
        'rpc_b1_url': request.form.get('rpc_b1_url', '').strip(),
        'rpc_b2_name': request.form.get('rpc_b2_name', '').strip(),
        'rpc_b2_url': request.form.get('rpc_b2_url', '').strip()
    }
    # Lấy config hiện tại từ DB để giữ token, guild_id, channel_id, mute, deaf, video, stream
    doc = accounts_collection.find_one({"bot_key": bot_key, "owner": usr})
    if not doc:
        session['flash_msg'] = "Không tìm thấy cấu hình trong DB!"
        session['flash_type'] = "error"
        return redirect(url_for('index', tab='running'))
    
    # Cập nhật config mới
    updated_config = {**doc, **new_config}
    # Xóa các trường không cần thiết
    for key in ['_id', 'owner', 'bot_key']:
        updated_config.pop(key, None)
    # Lưu vào DB
    save_storage_item(bot_key, updated_config, usr)
    
    # Dừng bot hiện tại
    if bot_key in user_bots[usr]:
        user_bots[usr][bot_key]['running'] = False
        if 'ws' in user_bots[usr][bot_key]:
            try:
                user_bots[usr][bot_key]['ws'].close()
            except:
                pass
        time.sleep(0.5)
        del user_bots[usr][bot_key]
    
    # Khởi động lại bot
    threading.Thread(target=run_bot, args=(bot_key, updated_config, usr), daemon=True).start()
    session['flash_msg'] = "Đã cập nhật RPC và khởi động lại bot!"
    session['flash_type'] = "success"
    return redirect(url_for('index', tab='running'))

@app.route('/admin_dangkhoi')
def admin_dashboard():
    db_user = users_collection.find_one({"username": session.get('username')})
    if not db_user or not db_user.get('is_admin'):
        return redirect(url_for('index'))
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
    if not db_user or not db_user.get('is_admin'):
        return redirect(url_for('index'))
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
                    tid = str(t['id']); amt = int(float(t['amount_in'])); content = t['transaction_content']
                    if process_sepay_transaction(tid, amt, content):
                        synced_count += 1
            session['admin_msg'] = f"Đồng bộ hoàn tất! Cộng bù {synced_count} giao dịch bị sót."
        except Exception as e:
            session['admin_msg'] = f"Lỗi đồng bộ: {str(e)}"
    return redirect(url_for('admin_dashboard'))

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
