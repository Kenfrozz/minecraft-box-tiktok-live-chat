"""OBS Browser Source icin seffaf HTML overlay'ler + SSE event stream.

Endpoint'ler:
  /feed      - son aksiyonlar (TNT/effect/gift)
  /likes     - like progress bar + bir sonraki esik
  /alerts    - buyuk hediye ortada flash
  /gifters   - top 5 hediye liderlik tablosu
  /stream    - SSE event kanali (tum overlay'ler ayni kanaldan dinliyor)
  /state     - JSON snapshot (debug)

Calistirma:
  python overlay_server.py   (standalone)
  veya main.py icinde thread olarak baslatilir (default port 5011).
"""
import json
import queue
import threading
import time
from pathlib import Path

from flask import Flask, Response, jsonify, render_template_string
from flask.logging import default_handler
import logging

from overlay_bus import BUS

app = Flask(__name__)
app.logger.removeHandler(default_handler)
logging.getLogger("werkzeug").setLevel(logging.WARNING)

ROOT = Path(__file__).parent
STATS_PATH = ROOT.parent / "server" / "plugins" / "TikTokBox" / "stats.yml"


def _read_top_gifters(limit: int = 5) -> list[dict]:
    """Lightweight YAML parser: sadece top gifters kismini ayiklar."""
    if not STATS_PATH.exists():
        return []
    try:
        text = STATS_PATH.read_text(encoding="utf-8")
    except Exception:
        return []
    # stats.yml formati: "gifters:\n  user1: 1500\n  user2: 800"
    in_gifters = False
    out: list[tuple[str, int]] = []
    for raw in text.splitlines():
        line = raw.rstrip()
        if not line:
            continue
        if line.startswith("gifters:"):
            in_gifters = True
            continue
        if in_gifters:
            if not line.startswith((" ", "\t")):
                break
            stripped = line.strip()
            if ":" not in stripped:
                continue
            name, _, val = stripped.partition(":")
            try:
                out.append((name.strip(), int(val.strip())))
            except ValueError:
                continue
    out.sort(key=lambda p: p[1], reverse=True)
    return [{"user": n, "coins": c} for n, c in out[:limit]]


# ---------------- SSE ----------------

@app.route("/stream")
def stream():
    def gen():
        q = BUS.subscribe()
        try:
            # initial snapshot
            yield f"event: state\ndata: {json.dumps(BUS.state())}\n\n"
            while True:
                try:
                    ev = q.get(timeout=15)
                    yield f"data: {json.dumps(ev)}\n\n"
                except queue.Empty:
                    yield ": keepalive\n\n"
        finally:
            BUS.unsubscribe(q)

    return Response(gen(), mimetype="text/event-stream", headers={
        "Cache-Control": "no-cache",
        "X-Accel-Buffering": "no",
        "Connection": "keep-alive",
    })


@app.route("/state")
def state():
    return jsonify(BUS.state())


@app.route("/api/gifters")
def api_gifters():
    return jsonify({"gifters": _read_top_gifters()})


# ---------------- Overlay HTML'ler ----------------

BASE_CSS = """
<style>
  :root { color-scheme: dark; }
  * { box-sizing: border-box; }
  html, body {
    margin: 0; padding: 0; height: 100%;
    background: transparent !important;
    color: #fff;
    font-family: 'Inter', 'Segoe UI', system-ui, sans-serif;
    overflow: hidden;
    -webkit-font-smoothing: antialiased;
  }
</style>
"""

FEED_HTML = BASE_CSS + """
<style>
  body { padding: 16px; }
  #feed { display: flex; flex-direction: column-reverse; gap: 8px; }
  .card {
    background: linear-gradient(90deg, rgba(10,10,20,0.85), rgba(30,20,50,0.75));
    border-left: 4px solid var(--accent, #ff2d6f);
    border-radius: 10px;
    padding: 10px 14px;
    font-size: 20px;
    font-weight: 600;
    box-shadow: 0 6px 24px rgba(0,0,0,0.4);
    display: flex; gap: 10px; align-items: center;
    animation: slide 0.35s ease-out;
    backdrop-filter: blur(6px);
  }
  .card .icon { font-size: 22px; }
  .card .user {
    color: #ff6ec7; font-weight: 800;
    text-shadow: 0 0 8px rgba(255,110,199,0.5);
  }
  .card .label { color: var(--accent, #ffd23f); font-weight: 800; }
  .card .sub { opacity: 0.7; font-weight: 500; }
  .card.fade-out { animation: fadeout 0.6s ease-in forwards; }
  @keyframes slide {
    from { transform: translateX(-30px); opacity: 0; }
    to { transform: translateX(0); opacity: 1; }
  }
  @keyframes fadeout {
    from { opacity: 1; }
    to { opacity: 0; transform: translateX(-20px); }
  }
</style>
<div id="feed"></div>
<script>
  const FEED = document.getElementById('feed');
  const MAX = 6;
  const LIFE_MS = 9000;

  const TIER_STYLE = {
    normal:  { icon: '💥', color: '#ffd23f', label: 'TNT' },
    mega:    { icon: '💣', color: '#ff9a3c', label: 'MEGA TNT' },
    rain:    { icon: '🌧️', color: '#3fc3ff', label: 'TNT YAGMURU' },
    creeper: { icon: '👹', color: '#4ade80', label: 'CREEPER ORDUSU' },
    nuke:    { icon: '☢️', color: '#ff2d2d', label: 'NUKLEER' },
    meteor:  { icon: '☄️', color: '#ff4d00', label: 'METEOR' },
  };
  const EFFECT_STYLE = {
    blindness:    { icon: '🌑', color: '#a78bfa', label: 'KORLUK' },
    nausea:       { icon: '🤢', color: '#4ade80', label: 'SARHOSLUK' },
    slowness:     { icon: '🐢', color: '#60a5fa', label: 'YAVASLIK' },
    levitation:   { icon: '🎈', color: '#38bdf8', label: 'UCUS' },
    darkness:     { icon: '🕳️', color: '#888',    label: 'TERS DUNYA' },
    speed:        { icon: '⚡', color: '#84cc16', label: 'HIZ' },
    mega_sabotaj: { icon: '🔥', color: '#ef4444', label: 'MEGA SABOTAJ' },
    combo_nuke:   { icon: '💀', color: '#dc2626', label: 'FELAKET' },
    wipe:         { icon: '🧹', color: '#dc2626', label: 'ARENA WIPE' },
    jail:         { icon: '⛓️', color: '#a855f7', label: 'HAPIS' },
    gauntlet:     { icon: '👾', color: '#b91c1c', label: 'CANAVAR ARENASI' },
  };

  function render(ev) {
    if (ev.type !== 'action') return;
    const style = ev.category === 'effect'
      ? (EFFECT_STYLE[ev.key] || { icon: '✨', color: '#fff', label: ev.key.toUpperCase() })
      : (TIER_STYLE[ev.key]    || { icon: '💥', color: '#fff', label: ev.key.toUpperCase() });
    const user = ev.user || 'anonim';
    const sub = ev.source === 'gift' ? `(${ev.gift || 'hediye'})` :
                ev.source === 'likes' ? `(${ev.milestone || ''} begeni)` :
                '';
    const card = document.createElement('div');
    card.className = 'card';
    card.style.setProperty('--accent', style.color);
    card.innerHTML = `
      <span class="icon">${style.icon}</span>
      <span class="user">@${user}</span>
      <span>→</span>
      <span class="label">${style.label}</span>
      <span class="sub">${sub}</span>
    `;
    FEED.appendChild(card);
    while (FEED.children.length > MAX) FEED.removeChild(FEED.firstChild);
    setTimeout(() => {
      card.classList.add('fade-out');
      setTimeout(() => card.remove(), 600);
    }, LIFE_MS);
  }

  const es = new EventSource('/stream');
  es.onmessage = (e) => {
    try { render(JSON.parse(e.data)); } catch {}
  };
</script>
"""

LIKES_HTML = BASE_CSS + """
<style>
  body { padding: 20px; display: flex; align-items: center; justify-content: center; }
  .wrap {
    width: 100%; max-width: 560px;
    background: rgba(10,10,20,0.85);
    border: 2px solid rgba(255,45,111,0.4);
    border-radius: 16px;
    padding: 16px 20px;
    backdrop-filter: blur(8px);
    box-shadow: 0 8px 32px rgba(255,45,111,0.25);
  }
  .head {
    display: flex; justify-content: space-between; align-items: baseline;
    margin-bottom: 10px;
  }
  .head .title {
    font-size: 18px; font-weight: 800; letter-spacing: 1px;
    color: #ff6ec7;
    text-shadow: 0 0 10px rgba(255,110,199,0.6);
  }
  .head .target { font-size: 14px; opacity: 0.8; }
  .head .target b { color: #ffd23f; }
  .bar {
    position: relative;
    height: 22px;
    background: rgba(255,255,255,0.08);
    border-radius: 11px;
    overflow: hidden;
  }
  .fill {
    height: 100%;
    background: linear-gradient(90deg, #ff2d6f, #ffd23f);
    border-radius: 11px;
    width: 0%;
    transition: width 0.6s ease-out;
    box-shadow: 0 0 16px rgba(255,45,111,0.7);
  }
  .nums {
    position: absolute; inset: 0;
    display: flex; align-items: center; justify-content: center;
    font-size: 14px; font-weight: 700;
    text-shadow: 0 1px 2px rgba(0,0,0,0.8);
  }
  .foot {
    margin-top: 8px; font-size: 13px; opacity: 0.75;
    display: flex; justify-content: space-between;
  }
  .pulse { animation: pulse 0.4s ease-out 3; }
  @keyframes pulse {
    0% { transform: scale(1); }
    50% { transform: scale(1.03); filter: brightness(1.3); }
    100% { transform: scale(1); }
  }
</style>
<div class="wrap" id="wrap">
  <div class="head">
    <div class="title">❤ BEGENI YAGMURU</div>
    <div class="target">Hedef: <b id="target">—</b> = <b id="reward">—</b> TNT</div>
  </div>
  <div class="bar">
    <div class="fill" id="fill"></div>
    <div class="nums"><span id="cur">0</span> / <span id="max">—</span></div>
  </div>
  <div class="foot">
    <span>Toplam: <b id="total">0</b></span>
    <span id="next">Sonraki esik: —</span>
  </div>
</div>
<script>
  const $ = id => document.getElementById(id);
  let prevAt = 0;

  function fmt(n) { return n.toLocaleString('tr-TR'); }

  function update(total, threshold) {
    $('total').textContent = fmt(total);
    if (!threshold) {
      $('target').textContent = '—';
      $('reward').textContent = '—';
      $('cur').textContent = fmt(total);
      $('max').textContent = '—';
      $('fill').style.width = '0%';
      return;
    }
    const at = threshold.at;
    const reward = threshold.tnt;
    // Onceki esik: listedeki son gecilen, yoksa 0
    const base = prevAt < at ? prevAt : 0;
    const prog = Math.max(0, Math.min(1, (total - base) / (at - base)));
    $('target').textContent = fmt(at);
    $('reward').textContent = reward;
    $('cur').textContent = fmt(Math.max(total, base));
    $('max').textContent = fmt(at);
    $('fill').style.width = (prog * 100).toFixed(1) + '%';
    $('next').textContent = `Kaldi: ${fmt(Math.max(0, at - total))}`;
  }

  function flashMilestone(milestone, tnt) {
    const w = $('wrap');
    w.classList.remove('pulse');
    void w.offsetWidth;
    w.classList.add('pulse');
  }

  const es = new EventSource('/stream');
  es.addEventListener('state', (e) => {
    try {
      const s = JSON.parse(e.data);
      update(s.likes_total || 0, s.next_threshold);
    } catch {}
  });
  es.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'likes') {
        if (ev.next_threshold && ev.next_threshold.at !== undefined) {
          // prevAt = en son gecilen esik - basitce: eger total > threshold.at degilse ayni kalir
        }
        update(ev.total || 0, ev.next_threshold);
      } else if (ev.type === 'like_milestone') {
        prevAt = ev.milestone;
        flashMilestone(ev.milestone, ev.tnt);
      }
    } catch {}
  };
</script>
"""

ALERT_HTML = BASE_CSS + """
<style>
  body {
    display: flex; align-items: center; justify-content: center;
  }
  #alert {
    display: none;
    padding: 40px 80px;
    text-align: center;
    border-radius: 24px;
    background: radial-gradient(circle, rgba(255,45,111,0.95), rgba(90,0,30,0.95));
    box-shadow: 0 0 80px rgba(255,45,111,0.9), inset 0 0 40px rgba(255,255,255,0.15);
    animation: bigflash 0.6s ease-out;
    border: 3px solid rgba(255,255,255,0.3);
  }
  #alert.show { display: block; }
  #alert .icon {
    font-size: 96px; line-height: 1;
    filter: drop-shadow(0 0 24px rgba(255,210,63,0.8));
  }
  #alert .label {
    font-size: 48px; font-weight: 900; letter-spacing: 3px;
    margin: 8px 0 4px;
    text-shadow: 0 0 20px rgba(255,255,255,0.6), 0 4px 12px rgba(0,0,0,0.5);
  }
  #alert .user {
    font-size: 28px; font-weight: 700;
    color: #ffd23f;
    text-shadow: 0 2px 8px rgba(0,0,0,0.6);
  }
  @keyframes bigflash {
    0% { transform: scale(0.3); opacity: 0; }
    40% { transform: scale(1.15); }
    70% { transform: scale(0.98); }
    100% { transform: scale(1); opacity: 1; }
  }
</style>
<div id="alert">
  <div class="icon" id="ic">⚠️</div>
  <div class="label" id="lb">FELAKET</div>
  <div class="user" id="us">@user</div>
</div>
<script>
  const EL = document.getElementById('alert');
  const IC = document.getElementById('ic');
  const LB = document.getElementById('lb');
  const US = document.getElementById('us');
  const BIG_GIFTS = {
    'Galaxy':          { icon: '🌀', label: 'FELAKET GELDI' },
    'TikTok Universe': { icon: '💀', label: 'ARENA WIPE' },
    'Universe':        { icon: '💀', label: 'ARENA WIPE' },
    'Sports Car':      { icon: '🏎️', label: 'ARENA WIPE' },
    'Lion':            { icon: '🦁', label: 'NUKLEER' },
    'Train':           { icon: '🚂', label: 'METEOR' },
  };
  let hideT = null;
  function show(icon, label, user) {
    IC.textContent = icon;
    LB.textContent = label;
    US.textContent = '@' + (user || 'anonim');
    EL.classList.remove('show');
    void EL.offsetWidth;
    EL.classList.add('show');
    clearTimeout(hideT);
    hideT = setTimeout(() => EL.classList.remove('show'), 4200);
  }
  const es = new EventSource('/stream');
  es.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'big_gift') {
        const conf = BIG_GIFTS[ev.gift] || { icon: '🎁', label: ev.gift.toUpperCase() };
        show(conf.icon, conf.label, ev.user);
      } else if (ev.type === 'like_milestone' && ev.tnt >= 50) {
        show('❤️‍🔥', `${Math.round(ev.milestone/1000)}K BEGENI`, `${ev.tnt} TNT`);
      }
    } catch {}
  };
</script>
"""

GIFTERS_HTML = BASE_CSS + """
<style>
  body { padding: 16px; }
  .panel {
    background: rgba(10,10,20,0.85);
    border: 2px solid rgba(255,210,63,0.35);
    border-radius: 14px;
    padding: 12px 16px;
    backdrop-filter: blur(8px);
    width: 320px;
    box-shadow: 0 8px 32px rgba(0,0,0,0.4);
  }
  .title {
    font-size: 16px; font-weight: 800; letter-spacing: 1.5px;
    color: #ffd23f;
    text-shadow: 0 0 10px rgba(255,210,63,0.5);
    margin-bottom: 8px;
  }
  .row {
    display: grid; grid-template-columns: 28px 1fr auto;
    gap: 10px; align-items: center;
    padding: 6px 4px;
    font-size: 16px; font-weight: 600;
    border-bottom: 1px solid rgba(255,255,255,0.06);
  }
  .row:last-child { border-bottom: none; }
  .rank { font-weight: 900; color: #ff6ec7; text-align: center; }
  .rank.r1 { color: #ffd23f; font-size: 18px; }
  .rank.r2 { color: #e5e5e5; }
  .rank.r3 { color: #cd7f32; }
  .user { overflow: hidden; text-overflow: ellipsis; white-space: nowrap; }
  .coins { color: #4ade80; font-weight: 800; }
  .row.fresh { animation: flash 0.8s ease-out; }
  @keyframes flash {
    0% { background: rgba(255,210,63,0.4); }
    100% { background: transparent; }
  }
  .empty { opacity: 0.5; font-size: 14px; padding: 8px 4px; }
</style>
<div class="panel">
  <div class="title">🏆 TOP HEDIYE</div>
  <div id="list"></div>
</div>
<script>
  const LIST = document.getElementById('list');
  let lastSnapshot = {};

  function render(rows) {
    if (!rows || !rows.length) {
      LIST.innerHTML = '<div class="empty">Henuz hediye yok…</div>';
      return;
    }
    const prev = lastSnapshot;
    const next = {};
    LIST.innerHTML = '';
    rows.forEach((r, i) => {
      const rank = i + 1;
      const fresh = prev[r.user] !== undefined && prev[r.user] !== r.coins;
      const div = document.createElement('div');
      div.className = 'row' + (fresh ? ' fresh' : '');
      div.innerHTML = `
        <span class="rank r${rank}">${rank}</span>
        <span class="user">@${r.user}</span>
        <span class="coins">${r.coins.toLocaleString('tr-TR')}</span>
      `;
      LIST.appendChild(div);
      next[r.user] = r.coins;
    });
    lastSnapshot = next;
  }

  async function refresh() {
    try {
      const r = await fetch('/api/gifters', { cache: 'no-store' });
      const j = await r.json();
      render(j.gifters || []);
    } catch {}
  }
  refresh();
  setInterval(refresh, 4000);

  // Hediye eventi gelince hemen refresh
  const es = new EventSource('/stream');
  es.onmessage = (e) => {
    try {
      const ev = JSON.parse(e.data);
      if (ev.type === 'gift_raw' || ev.type === 'big_gift') {
        setTimeout(refresh, 500);
      }
    } catch {}
  };
</script>
"""

INDEX_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>TikTok Box — OBS Overlays</title>
<style>
  body { font-family: system-ui; background: #0b0b14; color: #eee; padding: 24px; }
  h1 { color: #ff6ec7; }
  .card { background: #17172a; border-radius: 12px; padding: 16px 20px; margin: 10px 0; }
  .card h3 { margin: 0 0 6px; color: #ffd23f; }
  code { background: #000; padding: 2px 8px; border-radius: 4px; color: #4ade80; }
  a { color: #3fc3ff; }
</style></head><body>
<h1>🎬 OBS Browser Source URL'leri</h1>
<p>OBS'de <b>Browser Source</b> ekle, URL olarak asagidakilerden birini yapistir. Arka plan otomatik seffaf.</p>
<div class="card"><h3>1. Son Aksiyon Feed (sol ust)</h3>
<code>http://127.0.0.1:{port}/feed</code> · 420×360 px onerilir</div>
<div class="card"><h3>2. Begeni Progress Bar (alt)</h3>
<code>http://127.0.0.1:{port}/likes</code> · 600×140 px onerilir</div>
<div class="card"><h3>3. Buyuk Hediye Alert (ekran ortasi)</h3>
<code>http://127.0.0.1:{port}/alerts</code> · 800×400 px, tam ekran olustur</div>
<div class="card"><h3>4. Top Hediye Liderlik Tablosu (sag alt)</h3>
<code>http://127.0.0.1:{port}/gifters</code> · 360×280 px onerilir</div>
<p style="opacity:0.6;margin-top:20px">Stream test: <a href="/stream">/stream</a> · State: <a href="/state">/state</a></p>
</body></html>"""


@app.route("/")
def index():
    return INDEX_HTML.replace("{port}", str(app.config.get("PORT", 5011)))


@app.route("/feed")
def feed_page():
    return render_template_string(FEED_HTML)


@app.route("/likes")
def likes_page():
    return render_template_string(LIKES_HTML)


@app.route("/alerts")
def alerts_page():
    return render_template_string(ALERT_HTML)


@app.route("/gifters")
def gifters_page():
    return render_template_string(GIFTERS_HTML)


def run(host: str = "127.0.0.1", port: int = 5011) -> None:
    app.config["PORT"] = port
    app.run(host=host, port=port, threaded=True, debug=False, use_reloader=False)


def start_in_thread(host: str = "127.0.0.1", port: int = 5011) -> threading.Thread:
    t = threading.Thread(target=run, args=(host, port), daemon=True, name="overlay-server")
    t.start()
    return t


if __name__ == "__main__":
    print("OBS Overlay server -> http://127.0.0.1:5011/")
    run()
