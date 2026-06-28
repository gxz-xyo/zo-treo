from flask import Flask, render_template_string, request, jsonify, redirect, url_for
import threading
import json
import time
import requests
import websocket
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Lưu bot toàn cục, không phụ thuộc session
bots = {}

# ================== GIAO DIỆN CHÍNH ==================
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
        body { background: #0e0b16; display: flex; justify-content: center; align-items: center; min-height: 100vh; padding: 20px; }
        .container { max-width: 500px; width: 100%; background: #1a1a2e; border-radius: 24px; padding: 30px; box-shadow: 0 20px 60px rgba(0,0,0,0.8); border: 1px solid #2a2a4a; }
        .logo { color: #e94560; font-size: 28px; font-weight: 800; text-align: center; margin-bottom: 5px; letter-spacing: -0.5px; }
        .logo span { color: #fff; font-weight: 300; }
        .sub { text-align: center; color: #8888aa; font-size: 13px; margin-bottom: 25px; border-bottom: 1px solid #2a2a4a; padding-bottom: 15px; }
        .card { background: #12121f; border-radius: 16px; padding: 20px; margin-bottom: 20px; border: 1px solid #2a2a4a; }
        .card-title { color: #aaa; font-size: 12px; text-transform: uppercase; letter-spacing: 1px; margin-bottom: 12px; }
        .input-group { margin-bottom: 12px; }
        .input-group label { display: block; color: #ccc; font-size: 13px; margin-bottom: 4px; font-weight: 500; }
        .input-group input { width: 100%; padding: 12px 14px; background: #0e0b16; border: 1px solid #2a2a4a; border-radius: 12px; color: #fff; font-size: 14px; outline: none; transition: 0.3s; }
        .input-group input:focus { border-color: #e94560; box-shadow: 0 0 0 2px rgba(233,69,96,0.2); }
        .options { display: flex; flex-wrap: wrap; gap: 12px; margin: 15px 0; }
        .options label { color: #aaa; font-size: 13px; display: flex; align-items: center; gap: 6px; cursor: pointer; }
        .options input[type="checkbox"] { accent-color: #e94560; width: 16px; height: 16px; }
        .btn-primary { width: 100%; padding: 14px; background: #e94560; border: none; border-radius: 12px; color: #fff; font-weight: 700; font-size: 16px; cursor: pointer; transition: 0.3s; }
        .btn-primary:hover { background: #c73652; transform: scale(1.01); }
        .btn-danger { padding: 10px 20px; background: #2a1a1a; border: 1px solid #5a2a2a; border-radius: 10px; color: #ff6b6b; font-weight: 600; cursor: pointer; }
        .btn-refresh { padding: 10px 20px; background: #1a1a3a; border: 1px solid #2a2a5a; border-radius: 10px; color: #88aaff; font-weight: 600; cursor: pointer; }
        .btn-config { padding: 10px 20px; background: #1a2a1a; border: 1px solid #2a5a2a; border-radius: 10px; color: #88ff88; font-weight: 600; cursor: pointer; }
        .status-box { padding: 12px 16px; border-radius: 12px; margin: 15px 0; text-align: center; font-weight: 600; }
        .online { background: #0f3b2b; color: #4cdf8b; border: 1px solid #1e5a3a; }
        .offline { background: #3b1a1a; color: #ff6b6b; border: 1px solid #5a2a2a; }
        .log-box { background: #0a0a12; border-radius: 12px; padding: 10px; max-height: 180px; overflow-y: auto; font-family: monospace; font-size: 12px; color: #88ccff; border: 1px solid #1a1a2e; margin: 15px 0; white-space: pre-wrap; word-break: break-all; }
        .log-box::-webkit-scrollbar { width: 4px; }
        .log-box::-webkit-scrollbar-thumb { background: #e94560; border-radius: 4px; }
        .row-actions { display: flex; gap: 10px; margin-top: 10px; flex-wrap: wrap; }
        .account-card { background: #12121f; border-radius: 16px; padding: 16px; margin: 10px 0; border: 1px solid #2a2a4a; display: flex; justify-content: space-between; align-items: center; }
        .account-info { color: #ccc; }
        .account-info .name { font-weight: 700; color: #fff; }
        .account-info .status { font-size: 12px; }
        .status-online { color: #4cdf8b; }
        .status-offline { color: #ff6b6b; }
        .footer { text-align: center; color: #444; font-size: 11px; margin-top: 20px; }
        .highlight { color: #e94560; }
        .hidden { display: none; }
    </style>
</head>
<body>
    <div class="container">
        <div class="logo">ZO <span>Treo</span></div>
        <div class="sub">Treo tài khoản trong kênh voice Discord 24/7</div>

        <!-- FORM NHẬP THÔNG TIN (HIỆN KHI CHƯA CÓ BOT) -->
        <div id="form-container" class="{{ 'hidden' if has_bot else '' }}">
            <form method="POST" action="/start">
                <div class="card">
                    <div class="card-title">⚙️ Cấu hình tài khoản</div>
                    <div class="input-group">
                        <label>🔑 Token Discord</label>
                        <input type="text" name="token" placeholder="Nhập token của bạn" required>
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
                    <button type="submit" class="btn-primary">🚀 BẮT ĐẦU TREO</button>
                </div>
            </form>
        </div>

        <!-- CARD TÀI KHOẢN ĐANG TREO (HIỆN KHI CÓ BOT) -->
        <div id="account-container" class="{{ '' if has_bot else 'hidden' }}">
            <div class="card">
                <div class="card-title">📋 Tài khoản đang treo</div>
                {% for key, bot in bot_items %}
                <div class="account-card">
                    <div class="account-info">
                        <div class="name">{{ bot.get('display_name', 'Bot') }}</div>
                        <div class="status">
                            Trạng thái: 
                            <span class="{{ 'status-online' if bot.get('connected') else 'status-offline' }}">
                                {{ '✅ Đang treo' if bot.get('connected') else '⏸️ Đã dừng' }}
                            </span>
                        </div>
                    </div>
                    <div>
                        <form method="POST" action="/config" style="display:inline;">
                            <input type="hidden" name="bot_key" value="{{ key }}">
                            <button type="submit" class="btn-config">⚙️ Cấu hình</button>
                        </form>
                        <form method="POST" action="/stop" style="display:inline;">
                            <input type="hidden" name="bot_key" value="{{ key }}">
                            <button type="submit" class="btn-danger">⏹️ Dừng</button>
                        </form>
                    </div>
                </div>
                {% endfor %}
            </div>
            <div class="card">
                <div class="status-box {{ 'online' if status else 'offline' }}">
                    {{ '✅ Đang treo' if status else '⏸️ Chưa treo' }}
                </div>
                <div class="log-box">{{ log|join('\\n') if log else '💬 Chưa có log nào...' }}</div>
                <div class="row-actions">
                    <form method="POST" action="/refresh" style="flex:1;">
                        <button type="submit" class="btn-refresh" style="width:100%;">🔄 Refresh Log</button>
                    </form>
                </div>
            </div>
        </div>

        <div class="footer">⚡ <span class="highlight">ZO</span> - Bản Quyền Thuộc Về DISCORD @gietanhdi</div>
    </div>

    <script>
        // Tự động reload để cập nhật log (không làm mất bot)
        setInterval(() => {
            fetch('/ping').then(() => {});
        }, 20000);
        setInterval(() => {
            location.reload();
        }, 30000);
    </script>
</body>
</html>
"""

# ================== PHẦN XỬ LÝ BOT (TỐI ƯU) ==================
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
    running = True
    reconnect_attempts = 0
    display_name = ""

    def add_log(msg):
        if bot_key in bots:
            bots[bot_key]['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
            if len(bots[bot_key]['log']) > 100:
                bots[bot_key]['log'] = bots[bot_key]['log'][-100:]

    def update_status(status):
        if bot_key in bots:
            bots[bot_key]['connected'] = status

    def send_voice_update(ws):
        if not ws or not ws.keep_running:
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
            ws.send(json.dumps(payload))
        except:
            pass

    def on_message(ws, message):
        nonlocal last_seq, connected, heartbeat_interval, display_name
        try:
            data = json.loads(message)
        except:
            return
        last_seq = data.get('s', last_seq)
        op = data.get('op')
        t = data.get('t')

        if op == 10:
            heartbeat_interval = data['d']['heartbeat_interval'] / 1000
            ws.send(json.dumps({
                "op": 2,
                "d": {
                    "token": token,
                    "properties": {"os": "Linux", "browser": "Chrome", "device": "ZO"},
                    "compress": False,
                    "large_threshold": 50
                }
            }))
            add_log("📤 Đã gửi IDENTIFY")
        elif op == 0:
            if t == 'READY':
                display_name = data['d']['user']['username']
                if bot_key in bots:
                    bots[bot_key]['display_name'] = display_name
                add_log(f"🎯 Đã xác thực: {display_name}")
                send_voice_update(ws)
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id and not connected:
                    connected = True
                    update_status(True)
                    add_log("✅ Đã vào phòng thành công! Đang treo...")
                elif d.get('channel_id') is None and connected:
                    connected = False
                    update_status(False)
                    add_log("⚠️ Bị rời phòng! Thử vào lại...")
                    send_voice_update(ws)
        elif op == 9:
            add_log("⚠️ Session lỗi, reconnect...")
            ws.close()

    def on_close(ws, code, msg):
        nonlocal reconnect_attempts
        if connected:
            connected = False
            update_status(False)
        add_log(f"🔌 Mất kết nối, reconnect sau 5s...")
        time.sleep(5)
        if running:
            start_ws()

    def on_error(ws, error):
        if "Connection closed" not in str(error):
            add_log(f"💥 Lỗi: {error}")

    def heartbeat_loop():
        nonlocal ws, last_seq
        while running:
            time.sleep(heartbeat_interval)
            if ws and ws.keep_running:
                try:
                    ws.send(json.dumps({"op": 1, "d": last_seq}))
                except:
                    pass

    def keep_alive_loop():
        while running:
            time.sleep(20)
            if ws and ws.keep_running and connected:
                send_voice_update(ws)

    def start_ws():
        nonlocal ws, reconnect_attempts
        reconnect_attempts += 1
        if reconnect_attempts > 20:
            add_log("❌ Quá số lần reconnect, dừng bot.")
            update_status(False)
            if bot_key in bots:
                bots[bot_key]['running'] = False
            return
        try:
            gateway = requests.get("https://discord.com/api/v9/gateway").json()['url']
        except:
            add_log("❌ Không lấy được gateway, thử lại...")
            time.sleep(5)
            if running:
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

    add_log("🚀 Khởi tạo bot...")
    start_ws()
    add_log("🛑 Bot đã dừng.")
    update_status(False)
    if bot_key in bots:
        bots[bot_key]['running'] = False

# ================== ROUTES ==================
@app.route('/', methods=['GET'])
def index():
    bot_key = None
    for key in bots.keys():
        if bots[key].get('running', False):
            bot_key = key
            break
    if bot_key:
        log = bots[bot_key].get('log', [])
        status = bots[bot_key].get('connected', False)
        has_bot = True
        bot_items = [(key, bots[key]) for key in bots.keys() if bots[key].get('running', False)]
    else:
        log = []
        status = False
        has_bot = False
        bot_items = []
    return render_template_string(HTML_MAIN, log=log, status=status, has_bot=has_bot, bot_items=bot_items)

@app.route('/start', methods=['POST'])
def start_bot():
    token = request.form['token']
    guild_id = request.form['guild_id']
    channel_id = request.form['channel_id']
    mute = 'mute' in request.form
    deaf = 'deaf' in request.form
    video = 'video' in request.form
    stream = 'stream' in request.form

    bot_key = f"{guild_id}_{channel_id}"
    if bot_key in bots and bots[bot_key].get('running', False):
        bots[bot_key]['running'] = False
        time.sleep(0.5)

    config = {'token': token, 'guild_id': guild_id, 'channel_id': channel_id, 'mute': mute, 'deaf': deaf, 'video': video, 'stream': stream}
    thread = threading.Thread(target=run_bot, args=(bot_key, config), daemon=True)
    thread.start()
    bots[bot_key] = {'thread': thread, 'connected': False, 'log': [f"🚀 Khởi tạo bot..."], 'running': True, 'display_name': 'Đang kết nối...'}
    return redirect(url_for('index'))

@app.route('/stop', methods=['POST'])
def stop_bot():
    bot_key = request.form.get('bot_key')
    if bot_key and bot_key in bots:
        bots[bot_key]['running'] = False
        bots[bot_key]['log'].append("⏹️ Đã dừng bot.")
    return redirect(url_for('index'))

@app.route('/config', methods=['POST'])
def config_bot():
    # Chuyển về form cấu hình (chưa implement)
    return redirect(url_for('index'))

@app.route('/refresh', methods=['POST'])
def refresh():
    return redirect(url_for('index'))

@app.route('/ping')
def ping():
    return "pong"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
