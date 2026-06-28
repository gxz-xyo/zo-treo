from flask import Flask, render_template_string, request
import threading
import json
import time
import requests
import websocket
import os

app = Flask(__name__)
app.secret_key = os.urandom(24)

bots = {}

HTML = """
<!DOCTYPE html>
<html>
<head>
    <title>ZO Treo 24/7 - Barra</title>
    <style>
        body { background: #1a1a2e; color: #eee; font-family: Arial; padding: 20px; }
        .container { max-width: 600px; margin: auto; background: #16213e; padding: 30px; border-radius: 10px; }
        input { width: 100%; padding: 10px; margin: 8px 0; background: #0f3460; color: white; border: none; border-radius: 5px; }
        label { font-weight: bold; }
        .btn { background: #e94560; color: white; padding: 12px; border: none; border-radius: 5px; cursor: pointer; width: 100%; font-size: 16px; }
        .log { background: #0a0a1a; padding: 10px; height: 200px; overflow-y: scroll; font-family: monospace; font-size: 12px; white-space: pre-wrap; border-radius: 5px; margin-top: 10px; }
        .status { padding: 8px; border-radius: 5px; margin: 10px 0; }
        .online { background: #2e7d32; }
        .offline { background: #c62828; }
        .btn-stop { background: #c62828; }
        .btn-refresh { background: #1565c0; }
    </style>
</head>
<body>
    <div class="container">
        <h1>🔥 ZO TREO 24/7 🔥</h1>
        <form method="POST" action="/start">
            <label>🔑 Token Discord (nên dùng token bot)</label>
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
        <div class="status {{ 'online' if status else 'offline' }}">
            Trạng thái: {{ '✅ Đang treo' if status else '❌ Chưa treo' }}
        </div>
        <div class="log" id="log">{{ log|join('\\n') if log else 'Chưa có log...' }}</div>
        <form method="POST" action="/stop">
            <button type="submit" class="btn btn-stop">⏹️ DỪNG TREO</button>
        </form>
        <form method="POST" action="/refresh">
            <button type="submit" class="btn btn-refresh">🔄 REFRESH LOG</button>
        </form>
    </div>
    <script>
        setInterval(() => { location.reload(); }, 15000);
    </script>
</body>
</html>
"""

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
    session_id_discord = None
    reconnect_attempts = 0
    max_reconnect_attempts = 50

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
            voice_payload = {
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
            ws.send(json.dumps(voice_payload))
            add_log("📤 Đã gửi VOICE_STATE_UPDATE")
        except Exception as e:
            add_log(f"⚠️ Lỗi gửi voice update: {e}")

    def on_message(ws, message):
        nonlocal last_seq, connected, session_id_discord, heartbeat_interval
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
                session_id_discord = data['d']['session_id']
                add_log(f"🎯 Session ID: {session_id_discord}")
                send_voice_update(ws)
            elif t == 'VOICE_STATE_UPDATE':
                d = data['d']
                if d.get('channel_id') == channel_id:
                    if not connected:
                        connected = True
                        update_status(True)
                        add_log("✅ Đã vào phòng thành công! Đang treo...")
                elif d.get('channel_id') is None and connected:
                    connected = False
                    update_status(False)
                    add_log("⚠️ Bị rời phòng! Đang thử vào lại...")
                    time.sleep(1)
                    if ws and ws.keep_running:
                        send_voice_update(ws)

        elif op == 9:
            add_log("⚠️ Session invalid! Sẽ identify lại...")
            ws.close()

    def on_error(ws, error):
        if "Connection closed" not in str(error):
            add_log(f"💥 Lỗi: {error}")

    def on_close(ws, close_code, close_msg):
        nonlocal reconnect_attempts, connected
        if connected:
            connected = False
            update_status(False)
        add_log(f"🔌 Mất kết nối (code {close_code}), reconnect sau 5s...")
        time.sleep(5)
        if running:
            start_ws()

    def on_open(ws):
        add_log("🔓 WebSocket mở")

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
                try:
                    send_voice_update(ws)
                except:
                    pass

    def start_ws():
        nonlocal ws, reconnect_attempts
        reconnect_attempts += 1
        if reconnect_attempts > max_reconnect_attempts:
            add_log("❌ Quá số lần reconnect, dừng bot.")
            update_status(False)
            if bot_key in bots:
                bots[bot_key]['running'] = False
            return

        try:
            gateway = requests.get("https://discord.com/api/v9/gateway").json()['url']
        except Exception as e:
            add_log(f"❌ Không lấy được gateway: {e}")
            time.sleep(10)
            if running:
                start_ws()
            return

        ws = websocket.WebSocketApp(
            gateway + "/?v=9&encoding=json",
            on_open=on_open,
            on_message=on_message,
            on_error=on_error,
            on_close=on_close
        )
        threading.Thread(target=heartbeat_loop, daemon=True).start()
        threading.Thread(target=keep_alive_loop, daemon=True).start()
        ws.run_forever()

    add_log("🚀 Khởi tạo bot...")
    start_ws()
    add_log("🛑 Bot đã dừng hẳn.")
    update_status(False)
    if bot_key in bots:
        bots[bot_key]['running'] = False

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
    else:
        log = []
        status = False
    return render_template_string(HTML, log=log, status=status)

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

    config = {
        'token': token,
        'guild_id': guild_id,
        'channel_id': channel_id,
        'mute': mute,
        'deaf': deaf,
        'video': video,
        'stream': stream
    }

    thread = threading.Thread(target=run_bot, args=(bot_key, config), daemon=True)
    thread.start()
    bots[bot_key] = {
        'thread': thread,
        'connected': False,
        'log': [f"🚀 Khởi tạo bot với token: {token[:10]}..."],
        'running': True
    }
    return index()

@app.route('/stop', methods=['POST'])
def stop_bot():
    for key in list(bots.keys()):
        if bots[key].get('running', False):
            bots[key]['running'] = False
            bots[key]['log'].append("⏹️ Đã yêu cầu dừng bot.")
    return index()

@app.route('/refresh', methods=['POST'])
def refresh():
    return index()

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080)
