from flask import Flask, render_template_string, request, session, jsonify
import threading
import json
import time
import requests
import websocket
import sys
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

# Lưu trạng thái các bot theo session_id
bots = {}  # session_id -> {"thread": thread, "ws": ws, "connected": bool, "log": list}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ZO Treo - Barra Edition</title>
    <style>
        body { background: #1a1a2e; color: #eee; font-family: Arial; padding: 20px; }
        .container { max-width: 600px; margin: auto; background: #16213e; padding: 30px; border-radius: 10px; }
        input, select { width: 100%; padding: 10px; margin: 8px 0; background: #0f3460; color: white; border: none; border-radius: 5px; }
        label { font-weight: bold; }
        .btn { background: #e94560; color: white; padding: 12px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }
        .log { background: #0a0a1a; padding: 10px; height: 200px; overflow-y: scroll; font-family: monospace; font-size: 12px; white-space: pre-wrap; border-radius: 5px; margin-top: 10px; }
        .status { padding: 8px; border-radius: 5px; margin: 10px 0; }
        .online { background: #2e7d32; }
        .offline { background: #c62828; }
        .info { color: #90caf9; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 ZO TREO - SHARE VERSION 🔥</h1>
        <form method="POST">
            <label>🔑 Token Discord</label>
            <input type="text" name="token" placeholder="Token của mày" required>
            <label>🏠 Server ID</label>
            <input type="text" name="guild_id" placeholder="Nhập server ID" required>
            <label>🎤 Channel ID (phòng voice)</label>
            <input type="text" name="channel_id" placeholder="Nhập channel ID" required>
            <label><input type="checkbox" name="mute" checked> Mute</label>
            <label><input type="checkbox" name="deaf" checked> Deaf</label>
            <label><input type="checkbox" name="video"> Video</label>
            <label><input type="checkbox" name="stream"> Stream</label>
            <button type="submit" class="btn">🚀 BẮT ĐẦU TREO</button>
        </form>
        <div class="status {{ 'online' if session.get('connected') else 'offline' }}">
            Trạng thái: {{ '✅ Đang treo' if session.get('connected') else '❌ Chưa treo' }}
        </div>
        <div class="log" id="log">{{ log|join('\\n') if log else 'Chưa có log...' }}</div>
        <form method="POST" action="/stop" style="margin-top:10px;">
            <button type="submit" class="btn" style="background:#c62828;">⏹️ DỪNG TREO</button>
        </form>
        <form method="POST" action="/refresh" style="margin-top:5px;">
            <button type="submit" class="btn" style="background:#1565c0;">🔄 REFRESH LOG</button>
        </form>
    </div>
    <script>
        setInterval(() => { location.reload(); }, 30000);
    </script>
</body>
</html>
"""

def run_bot(session_id, config):
    """Chạy bot treo trong thread riêng."""
    token = config['token']
    guild_id = config['guild_id']
    channel_id = config['channel_id']
    mute = config.get('mute', True)
    deaf = config.get('deaf', True)
    video = config.get('video', False)
    stream = config.get('stream', False)

    headers = {"Authorization": token, "Content-Type": "application/json"}
    ws = None
    last_seq = None
    heartbeat_interval = 41250
    connected = False
    running = True

    def send_voice_update(ws):
        ws.send(json.dumps({
            "op": 4,
            "d": {
                "guild_id": guild_id,
                "channel_id": channel_id,
                "self_mute": mute,
                "self_deaf": deaf,
                "self_video": video,
                "self_stream": stream
            }
        }))

    def on_message(ws, message):
        nonlocal last_seq, connected
        try:
            data = json.loads(message)
        except:
            return
        last_seq = data.get('s', last_seq)
        op = data.get('op')
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
            add_log(session_id, "📤 Đã gửi IDENTIFY")
        elif op == 0:
            t = data.get('t')
            if t == 'READY':
                add_log(session_id, f"🎯 Đã xác thực: {data['d']['user']['username']}")
                send_voice_update(ws)
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id:
                    connected = True
                    add_log(session_id, "✅ Đã vào phòng thành công! Đang treo...")
                    update_status(session_id, True)
                elif d.get('channel_id') is None and connected:
                    connected = False
                    add_log(session_id, "⚠️ Bị rời phòng, gửi lại voice state...")
                    send_voice_update(ws)
        elif op == 9:
            add_log(session_id, "⚠️ Session invalid, sẽ reconnect...")
            ws.close()

    def on_close(ws, code, msg):
        add_log(session_id, f"🔌 Mất kết nối (code {code}), reconnect sau 3s...")
        time.sleep(3)
        if running:
            start_ws()

    def on_error(ws, error):
        if "Connection closed" not in str(error):
            add_log(session_id, f"💥 Lỗi: {error}")

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
            time.sleep(30)
            if ws and ws.keep_running and connected:
                send_voice_update(ws)

    def start_ws():
        nonlocal ws
        try:
            gateway = requests.get("https://discord.com/api/v9/gateway").json()['url']
        except:
            add_log(session_id, "❌ Không lấy được gateway Discord")
            return
        ws = websocket.WebSocketApp(
            gateway + "/?v=9&encoding=json",
            on_message=on_message,
            on_close=on_close,
            on_error=on_error
        )
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws.run_forever()

    try:
        start_ws()
    except Exception as e:
        add_log(session_id, f"❌ Lỗi: {e}")
    finally:
        update_status(session_id, False)
        add_log(session_id, "🛑 Bot đã dừng.")

def add_log(session_id, msg):
    if session_id in bots:
        bots[session_id]['log'].append(f"[{time.strftime('%H:%M:%S')}] {msg}")
        if len(bots[session_id]['log']) > 100:
            bots[session_id]['log'] = bots[session_id]['log'][-100:]

def update_status(session_id, status):
    if session_id in bots:
        bots[session_id]['connected'] = status

@app.route('/', methods=['GET', 'POST'])
def index():
    session_id = session.get('_id', None)
    if not session_id:
        session['_id'] = os.urandom(16).hex()
        session_id = session['_id']

    if request.method == 'POST' and 'token' in request.form:
        token = request.form['token']
        guild_id = request.form['guild_id']
        channel_id = request.form['channel_id']
        mute = 'mute' in request.form
        deaf = 'deaf' in request.form
        video = 'video' in request.form
        stream = 'stream' in request.form

        if session_id in bots:
            bots[session_id]['running'] = False
            time.sleep(0.5)

        config = {
            'token': token,
            'guild_id': guild_id,
            'channel_id': channel_id,
            'mute': mute,
            'deaf': deaf,
            'video': video,
            'stream': stream
        }

        thread = threading.Thread(target=run_bot, args=(session_id, config), daemon=True)
        thread.start()
        bots[session_id] = {
            'thread': thread,
            'connected': False,
            'log': [f"🚀 Khởi tạo bot với token: {token[:10]}..."],
            'running': True
        }
        add_log(session_id, "🔁 Bot đang chạy...")

    log = bots.get(session_id, {}).get('log', [])
    connected = bots.get(session_id, {}).get('connected', False)
    session['connected'] = connected

    return render_template_string(HTML, log=log, connected=connected)

@app.route('/stop', methods=['POST'])
def stop():
    session_id = session.get('_id')
    if session_id and session_id in bots:
        bots[session_id]['running'] = False
        add_log(session_id, "⏹️ Đã yêu cầu dừng bot.")
    return index()

@app.route('/refresh', methods=['POST'])
def refresh():
    return index()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)