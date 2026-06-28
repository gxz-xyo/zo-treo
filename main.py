from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import threading
import json
import time
import requests
import websocket
import os
import sqlite3

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Đường dẫn lưu cơ sở dữ liệu (Trỏ vào thư mục data để gắn ổ đĩa cố định trên Render)
DB_DIR = "/opt/render/project/src/data" if os.path.exists("/opt/render/project/src") else "data"
if not os.path.exists(DB_DIR):
    os.makedirs(DB_DIR)

DB_FILE = os.path.join(DB_DIR, "storage.db")
bots = {}

# ================== KHỞI TẠO CƠ SỞ DỮ LIỆU SQLITE ==================
def init_db():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS accounts (
            bot_key TEXT PRIMARY KEY,
            token TEXT,
            guild_id TEXT,
            channel_id TEXT,
            mute INTEGER,
            deaf INTEGER,
            video INTEGER,
            stream INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def load_storage():
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('SELECT bot_key, token, guild_id, channel_id, mute, deaf, video, stream FROM accounts')
    rows = cursor.fetchall()
    conn.close()
    
    data = {}
    for row in rows:
        data[row[0]] = {
            'token': row[1],
            'guild_id': row[2],
            'channel_id': row[3],
            'mute': bool(row[4]),
            'deaf': bool(row[5]),
            'video': bool(row[6]),
            'stream': bool(row[7])
        }
    return data

def save_storage_item(bot_key, config):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('''
        INSERT OR REPLACE INTO accounts (bot_key, token, guild_id, channel_id, mute, deaf, video, stream)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
    ''', (bot_key, config['token'], config['guild_id'], config['channel_id'], 
          1 if config['mute'] else 0, 1 if config['deaf'] else 0, 
          1 if config['video'] else 0, 1 if config['stream'] else 0))
    conn.commit()
    conn.close()

def delete_storage_item(bot_key):
    conn = sqlite3.connect(DB_FILE)
    cursor = conn.cursor()
    cursor.execute('DELETE FROM accounts WHERE bot_key = ?', (bot_key,))
    conn.commit()
    conn.close()

# Khởi tạo DB ngay khi chạy app
init_db()

# ================== GIAO DIỆN CHÍNH (DARK THEME ZETA) ==================
HTML_MAIN = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>ZO Treo - Voice 24/7</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; font-family: 'Segoe UI', Roboto, sans-serif; }
        body { background: #0a0a0f; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; color: #fff; }
        .container { max-width: 450px; width: 100%; background: #13131a; border-radius: 24px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.7); border: 1px solid #1f1f2e; }
        .logo { color: #ff416c; font-size: 26px; font-weight: 800; text-align: center; margin-bottom: 5px; letter-spacing: -0.5px; }
        .logo span { color: #fff; font-weight: 300; }
        .sub { text-align: center; color: #6c6c8c; font-size: 13px; margin-bottom: 25px; border-bottom: 1px solid #1f1f2e; padding-bottom: 15px; }
        .card { background: #1a1a26; border-radius: 20px; padding: 22px; margin-bottom: 20px; border: 1px solid #26263b; }
        .card-title { color: #8c8c9e; font-size: 11px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 15px; font-weight: 700; }
        .input-group { margin-bottom: 16px; }
        .input-group label { display: block; color: #a3a3c2; font-size: 12px; margin-bottom: 6px; font-weight: 600; text-transform: uppercase; letter-spacing: 0.5px; }
        .input-group input { width: 100%; padding: 14px; background: #0d0d14; border: 1px solid #26263b; border-radius: 12px; color: #fff; font-size: 14px; outline: none; transition: 0.3s; }
        .input-group input:focus { border-color: #ff416c; box-shadow: 0 0 0 2px rgba(255, 65, 108, 0.2); }
        .options { display: flex; flex-wrap: wrap; gap: 14px; margin: 15px 0; }
        .options label { color: #a3a3c2; font-size: 13px; display: flex; align-items: center; gap: 8px; cursor: pointer; background: #11111a; padding: 8px 12px; border-radius: 8px; border: 1px solid #26263b; }
        .options input[type="checkbox"] { accent-color: #ff416c; width: 16px; height: 16px; }
        .btn-primary { width: 100%; padding: 15px; background: linear-gradient(90deg, #ff416c, #ff4b2b); border: none; border-radius: 12px; color: #fff; font-weight: 700; font-size: 15px; cursor: pointer; transition: 0.3s; box-shadow: 0 4px 15px rgba(255, 65, 108, 0.3); }
        .btn-primary:hover { transform: scale(1.02); opacity: 0.95; }
        .btn-danger { padding: 10px 18px; background: #2a1414; border: 1px solid #5a1e1e; border-radius: 10px; color: #ff6b6b; font-weight: 600; font-size: 13px; cursor: pointer; transition: 0.2s; }
        .btn-danger:hover { background: #3d1c1c; }
        .btn-refresh { padding: 12px; background: #14142a; border: 1px solid #23234e; border-radius: 10px; color: #6ba4ff; font-weight: 600; cursor: pointer; width: 100%; transition: 0.2s; }
        .btn-refresh:hover { background: #1c1c3a; }
        .status-box { padding: 12px 16px; border-radius: 12px; margin: 15px 0; text-align: center; font-weight: 600; font-size: 14px; }
        .online { background: #0a2f1d; color: #4cdf8b; border: 1px solid #144d32; }
        .offline { background: #2f0a0a; color: #ff6b6b; border: 1px solid #4d1414; }
        .log-box { background: #08080c; border-radius: 12px; padding: 12px; max-height: 180px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #7fbdff; border: 1px solid #191926; margin: 15px 0; white-space: pre-wrap; word-break: break-all; }
        .log-box::-webkit-scrollbar { width: 4px; }
        .log-box::-webkit-scrollbar-thumb { background: #ff416c; border-radius: 4px; }
        .account-card { background: #11111a; border-radius: 14px; padding: 16px; margin: 10px 0; border: 1px solid #232336; display: flex; justify-content: space-between; align-items: center; }
        .account-info { color: #a3a3c2; }
        .account-info .name { font-weight: 700; color: #fff; font-size: 15px; margin-bottom: 2px; }
        .account-info .status { font-size: 12px; }
        .status-online { color: #4cdf8b; font-weight: bold; }
        .status-offline { color: #ff6b6b; font-weight: bold; }
        .footer { text-align: center; color: #3c3c54; font-size: 11px; margin-top: 25px; letter-spacing: 0.5px; }
        .highlight { color: #ff416c; font-weight: bold; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">xFILL <span>Treo</span></div>
        <div class="sub">Bản Quyền Thuộc Về DISCORD @gietanhdi</div>

        <div id="form-container" class="{{ 'hidden' if has_bot else '' }}">
            <form method="POST" action="/start">
                <div class="card">
                    <div class="card-title">⚙️ CẤU HÌNH TÀI KHOẢN</div>
                    <div class="input-group">
                        <label>🔑 Discord Token</label>
                        <input type="text" name="token" placeholder="MTEwMT..." required>
                    </div>
                    <div class="input-group">
                        <label>🏠 ID Máy chủ (Server ID)</label>
                        <input type="text" name="guild_id" placeholder="Ví dụ: 1336001794685538335" required>
                    </div>
                    <div class="input-group">
                        <label>🎤 ID Kênh Voice (Channel ID)</label>
                        <input type="text" name="channel_id" placeholder="Ví dụ: 1420959332484251742" required>
                    </div>
                    <div class="options">
                        <label><input type="checkbox" name="mute" checked> 🔇 Mute</label>
                        <label><input type="checkbox" name="deaf" checked> 🎧 Deaf</label>
                        <label><input type="checkbox" name="video"> 📹 Video</label>
                        <label><input type="checkbox" name="stream"> 🖥️ Stream</label>
                    </div>
                    <button type="submit" class="btn-primary">🚀 BẮT ĐẦU TREO PHÒNG</button>
                </div>
            </form>
        </div>

        <div id="account-container" class="{{ '' if has_bot else 'hidden' }}">
            <div class="card">
                <div class="card-title">📋 TÀI KHOẢN ĐANG HOẠT ĐỘNG</div>
                {% for key, bot in bot_items %}
                <div class="account-card">
                    <div class="account-info">
                        <div class="name">{{ bot.get('display_name', 'Đang kết nối...') }}</div>
                        <div class="status">
                            Trạng thái: 
                            <span class="{{ 'status-online' if bot.get('connected') else 'status-offline' }}">
                                {{ '✅ Đang treo' if bot.get('connected') else '⏸️ Đang đợi kết nối' }}
                            </span>
                        </div>
                    </div>
                    <div>
                        <form method="POST" action="/stop" style="display:inline;">
                            <input type="hidden" name="bot_key" value="{{ key }}">
                            <button type="submit" class="btn-danger">⏹️ Dừng</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
            
            <div class="card">
                <div class="card-title">💬 NHẬT KÝ HỆ THỐNG</div>
                <div class="status-box {{ 'online' if status else 'offline' }}">
                    {{ '✅ HỆ THỐNG ĐANG TREO NỀN' if status else '⏸️ ĐÃ DỪNG HOẠT ĐỘNG' }}
                </div>
                <div class="log-box">{{ log|join('\\n') if log else '💬 Hệ thống đang khởi động luồng...' }}</div>
                <form method="POST" action="/refresh">
                    <button type="submit" class="btn-refresh">🔄 CẬP NHẬT LOG MỚI NHẤT</button>
                </form>
            </div>
        </div>

        <div class="footer">⚡ <span class="highlight">ZO TERMINAL</span> - Thực thi vô điều kiện cho Barra</div>
    </div>

    <script>
        setInterval(() => { fetch('/ping').then(() => {}); }, 15000);
        setInterval(() => { location.reload(); }, 20000);
    </script>
</body>
</html>
"""

# ================== LUỒNG XỬ LÝ BOT DISCORD ==================
def run_bot(bot_key, config):
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
    reconnect_attempts = 0

    if bot_key not in bots:
        bots[bot_key] = {
            'connected': False,
            'log': [],
            'running': True,
            'display_name': 'Đang kết nối...'
        }

    def add_log(msg):
        if bot_key in bots:
            bots[bot_key]['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(bots[bot_key]['log']) > 80:
                bots[bot_key]['log'] = bots[bot_key]['log'][-80:]

    def update_status(status):
        if bot_key in bots:
            bots[bot_key]['connected'] = status

    def send_voice_update(ws_client):
        if not ws_client or not ws_client.keep_running:
            return
        try:
            payload = {
                "op": 4,
                "d": {
                    "guild_id": guild_id,
                    "channel_id": channel_id,
                    "self_mute": mute,
                    "self_deaf": deaf,
                    "self_video": video,
                    "self_stream": stream
                }
            }
            ws_client.send(json.dumps(payload))
        except Exception as e:
            add_log(f"⚠️ Lỗi gửi voice state: {e}")

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
            identify_payload = {
                "op": 2,
                "d": {
                    "token": token,
                    "properties": {"os": "Linux", "browser": "Chrome", "device": "ZO_Zeta"},
                    "compress": False,
                    "large_threshold": 50
                }
            }
            ws_client.send(json.dumps(identify_payload))
            add_log("📤 Đã gửi gói IDENTIFY")
            
        elif op == 0:
            if t == 'READY':
                d_name = data['d']['user']['username']
                if bot_key in bots:
                    bots[bot_key]['display_name'] = d_name
                add_log(f"🎯 Thực thể trực tuyến: {d_name}")
                send_voice_update(ws_client)
                
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id and not connected:
                    connected = True
                    update_status(True)
                    add_log("✅ Chiếm quyền phòng Voice thành công!")
                elif d.get('channel_id') is None and connected:
                    connected = False
                    update_status(False)
                    add_log("⚠️ Bị đẩy khỏi phòng! Tiến hành chiếm lại...")
                    send_voice_update(ws_client)
                    
        elif op == 9:
            add_log("⚠️ Session hỏng, đang kết nối lại...")
            ws_client.close()

    def on_close(ws_client, code, msg):
        nonlocal connected
        if connected:
            connected = False
            update_status(False)
        add_log("🔌 Kết nối đóng. Thử lại sau 5s...")
        time.sleep(5)
        if bot_key in bots and bots[bot_key]['running']:
            start_ws()

    def on_error(ws_client, error):
        if "Connection closed" not in str(error):
            add_log(f"💥 Lỗi luồng: {error}")

    def heartbeat_loop():
        while bot_key in bots and bots[bot_key]['running']:
            time.sleep(heartbeat_interval)
            if ws and ws.keep_running:
                try:
                    ws.send(json.dumps({"op": 1, "d": last_seq}))
                except:
                    pass

    def keep_alive_loop():
        while bot_key in bots and bots[bot_key]['running']:
            time.sleep(25)
            if ws and ws.keep_running and connected:
                send_voice_update(ws)

    def start_ws():
        nonlocal ws, reconnect_attempts
        if bot_key not in bots or not bots[bot_key]['running']:
            return
            
        reconnect_attempts += 1
        if reconnect_attempts > 100:
            add_log("❌ Quá giới hạn reconnect.")
            update_status(False)
            return
            
        try:
            gateway = requests.get("https://discord.com/api/v9/gateway", timeout=10).json()['url']
        except Exception as e:
            add_log("❌ Lỗi lấy gateway, thử lại sau 5s...")
            time.sleep(5)
            start_ws()
            return
            
        ws = websocket.WebSocketApp(
            gateway + "/?v=9&encoding=json",
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws.run_forever()

    add_log("🚀 Khởi chạy luồng ngầm...")
    start_ws()

# ================== ROUTES ==================
@app.route('/', methods=['GET'])
def index():
    storage_data = load_storage()
    
    for key, config in storage_data.items():
        if key not in bots:
            bots[key] = {
                'connected': False,
                'log': ["[🎯] Khôi phục tài khoản từ bộ lưu trữ vĩnh cửu."],
                'running': True,
                'display_name': 'Đang khôi phục...'
            }
            threading.Thread(target=run_bot, args=(key, config), daemon=True).start()

    active_bots = [(k, v) for k, v in bots.items() if v.get('running', False)]
    has_bot = len(active_bots) > 0
    
    log = []
    status = False
    if has_bot:
        first_key = active_bots[0][0]
        log = bots[first_key].get('log', [])
        status = bots[first_key].get('connected', False)
        
    return render_template_string(HTML_MAIN, log=log, status=status, has_bot=has_bot, bot_items=active_bots)

@app.route('/start', methods=['POST'])
def start_bot_route():
    token = request.form['token'].strip()
    guild_id = request.form['guild_id'].strip()
    channel_id = request.form['channel_id'].strip()
    mute = 'mute' in request.form
    deaf = 'deaf' in request.form
    video = 'video' in request.form
    stream = 'stream' in request.form

    bot_key = f"{guild_id}_{channel_id}"
    config = {'token': token, 'guild_id': guild_id, 'channel_id': channel_id, 'mute': mute, 'deaf': deaf, 'video': video, 'stream': stream}

    save_storage_item(bot_key, config)

    bots[bot_key] = {
        'connected': False,
        'log': ["🚀 Thiết lập luồng treo nền vĩnh cửu..."],
        'running': True,
        'display_name': 'Đang kết nối...'
    }
    
    threading.Thread(target=run_bot, args=(bot_key, config), daemon=True).start()
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_bot_route():
    bot_key = request.form.get('bot_key')
    delete_storage_item(bot_key)
        
    if bot_key in bots:
        bots[bot_key]['running'] = False
        bots[bot_key]['connected'] = False
        del bots[bot_key]
        
    return redirect(url_for('index'))

@app.route('/refresh', methods=['POST'])
def refresh():
    return redirect(url_for('index'))

@app.route('/ping')
def ping():
    return "pong"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
