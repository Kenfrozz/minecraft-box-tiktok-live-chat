"""TikTok Box dashboard — basit yerel yonetim panosu (http://127.0.0.1:5000)."""
import json
import re
import time
from pathlib import Path
from threading import Lock

import yaml
from flask import Flask, jsonify, request, render_template_string

from rcon_client import RconClient
from tnt_actions import TntActions
from effect_actions import EffectActions

ROOT = Path(__file__).parent
ARENA_CFG = json.loads((ROOT / "config" / "arena.json").read_text(encoding="utf-8"))
TRIGGERS_CFG = json.loads((ROOT / "config" / "triggers.json").read_text(encoding="utf-8"))
STATS_PATH = ROOT.parent / "server" / "plugins" / "TikTokBox" / "stats.yml"
STATE_PATH = ROOT / "state.json"

rcon_cfg = ARENA_CFG["rcon"]
rcon = RconClient(rcon_cfg["host"], int(rcon_cfg["port"]), rcon_cfg["password"])
tnt = TntActions(rcon, ARENA_CFG)
effects = EffectActions(rcon)

app = Flask(__name__)
_log: list[dict] = []
_log_lock = Lock()


def push_log(msg: str) -> None:
    with _log_lock:
        _log.append({"t": time.time(), "msg": msg})
        if len(_log) > 80:
            del _log[:-80]


def strip_color(s: str) -> str:
    return re.sub(r"§.", "", s or "")


def read_stats() -> dict:
    if not STATS_PATH.exists():
        return {"wins": 0, "gifters": []}
    try:
        data = yaml.safe_load(STATS_PATH.read_text(encoding="utf-8")) or {}
    except Exception:
        return {"wins": 0, "gifters": []}
    gifters = []
    for user, coins in (data.get("gifters") or {}).items():
        gifters.append({"user": str(user).replace("_DOT_", "."), "coins": int(coins)})
    gifters.sort(key=lambda g: -g["coins"])
    return {"wins": int(data.get("wins", 0)), "gifters": gifters[:10]}


def read_listener_state() -> dict | None:
    if not STATE_PATH.exists():
        return None
    try:
        s = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        s["stale"] = (time.time() - float(s.get("updated_at", 0))) > 10
        return s
    except Exception:
        return None


def query_arena() -> dict:
    out = strip_color(rcon.cmd("arena status") or "")
    m = re.search(
        r"Arena:\s*(\d+)/(\d+)\s*\((\d+)%\)(?:\s*Wins:\s*(\d+))?(?:\s*CD:\s*(\d+)s)?",
        out,
    )
    if not m:
        return {"filled": 0, "total": 0, "pct": 0, "wins": 0, "countdown": 0, "ok": False, "raw": out}
    return {
        "filled": int(m.group(1)),
        "total": int(m.group(2)),
        "pct": int(m.group(3)),
        "wins": int(m.group(4) or 0),
        "countdown": int(m.group(5) or 0),
        "ok": True,
        "raw": out.strip(),
    }


def query_players() -> dict:
    out = strip_color(rcon.cmd("list") or "")
    m = re.search(r"(\d+).*?(?:of\s*(?:a\s*max\s*of\s*)?)?(\d+)", out)
    if not m:
        return {"online": 0, "max": 0, "names": [], "raw": out}
    names_m = re.search(r":\s*(.+)$", out)
    names = [n.strip() for n in names_m.group(1).split(",")] if names_m and names_m.group(1).strip() else []
    return {"online": int(m.group(1)), "max": int(m.group(2)), "names": names, "raw": out.strip()}


HTML = r"""<!doctype html>
<html lang="tr">
<head>
<meta charset="utf-8">
<title>TikTok Box — Kontrol Paneli</title>
<meta name="viewport" content="width=device-width,initial-scale=1">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Press+Start+2P&family=Pixelify+Sans:wght@400;500;600;700&family=VT323&display=swap" rel="stylesheet">
<style>
:root {
  --mc-void: #08080b;
  --mc-bg: #151517;
  --mc-stone-darkest: #1e1e1e;
  --mc-stone-dark: #2a2a2a;
  --mc-stone: #4f4f4f;
  --mc-stone-light: #868686;
  --mc-oak-dark: #5a3d1f;
  --mc-oak: #8b5a2b;
  --mc-oak-light: #b47a3f;
  --mc-plank: #a47148;
  --mc-plank-dark: #6e4a2d;
  --mc-plank-light: #c89764;
  --mc-grass-dark: #3f6b1e;
  --mc-grass: #5a8a2d;
  --mc-grass-light: #7cb342;
  --mc-grass-top: #8fd445;
  --mc-dirt: #8b5a2b;
  --mc-dirt-dark: #5e3c1c;
  --mc-tnt: #e04141;
  --mc-tnt-dark: #8a1b1b;
  --mc-redstone: #c11414;
  --mc-redstone-glow: #ff3434;
  --mc-diamond: #4fcad7;
  --mc-diamond-dark: #2a7a85;
  --mc-gold: #fcd34d;
  --mc-gold-dark: #b8901e;
  --mc-emerald: #17dd62;
  --mc-emerald-dark: #0c7a35;
  --mc-iron: #d4d4d4;
  --mc-xp: #8cef16;
  --mc-xp-dark: #4d8a0a;
  --mc-amethyst: #b487e6;
  --mc-obsidian: #19122a;
  --mc-potion: #c455e8;
}

* { box-sizing: border-box; margin: 0; padding: 0; }

html {
  image-rendering: pixelated;
  image-rendering: -moz-crisp-edges;
  image-rendering: crisp-edges;
}

body {
  font-family: 'Pixelify Sans', 'VT323', monospace;
  background: #08080b;
  color: #e8e8e8;
  min-height: 100vh;
  font-size: 17px;
  font-weight: 500;
  line-height: 1.25;
  letter-spacing: 0.3px;
  overflow-x: hidden;
  position: relative;
}

/* Global stone texture — repeating pixel noise over a dark gradient */
body::before {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  background-image:
    radial-gradient(circle at 23% 47%, rgba(255,255,255,0.025) 1px, transparent 1.6px),
    radial-gradient(circle at 71% 82%, rgba(0,0,0,0.35) 1px, transparent 1.6px),
    radial-gradient(circle at 45% 15%, rgba(255,255,255,0.018) 1px, transparent 1.6px),
    radial-gradient(circle at 88% 35%, rgba(0,0,0,0.25) 1px, transparent 1.6px),
    repeating-linear-gradient(0deg, rgba(255,255,255,0.008) 0 1px, transparent 1px 4px),
    repeating-linear-gradient(90deg, rgba(0,0,0,0.03) 0 1px, transparent 1px 5px),
    linear-gradient(180deg, #1c1c1f 0%, #0a0a0d 100%);
  background-size: 70px 70px, 86px 86px, 94px 94px, 110px 110px, auto, auto, auto;
  pointer-events: none;
}

/* Faint ember particles */
body::after {
  content: '';
  position: fixed;
  inset: 0;
  z-index: 0;
  background-image:
    radial-gradient(circle, rgba(255,200,100,0.55) 0.6px, transparent 1px),
    radial-gradient(circle, rgba(255,200,100,0.35) 0.5px, transparent 1px);
  background-size: 170px 170px, 230px 230px;
  background-position: 0 0, 85px 120px;
  animation: drift 90s linear infinite;
  opacity: 0.35;
  pointer-events: none;
}
@keyframes drift {
  from { background-position: 0 0, 85px 120px; }
  to   { background-position: 170px 340px, -145px 460px; }
}

/* ---------- HEADER: GRASS BLOCK BANNER ---------- */
header {
  position: relative;
  z-index: 2;
  background:
    linear-gradient(180deg,
      var(--mc-grass-top)   0%,
      var(--mc-grass-top)   6%,
      var(--mc-grass-light) 6%,
      var(--mc-grass-light) 13%,
      var(--mc-grass-dark)  13%,
      var(--mc-grass-dark)  20%,
      var(--mc-dirt)        20%,
      var(--mc-dirt)        62%,
      var(--mc-dirt-dark)   62%,
      #452810 100%);
  border-bottom: 4px solid #000;
  box-shadow: 0 4px 0 rgba(0,0,0,0.55), 0 12px 24px rgba(0,0,0,0.7);
}
header::before {
  content: '';
  position: absolute;
  top: 0; left: 0; right: 0; height: 20%;
  background-image:
    linear-gradient(90deg,
      rgba(0,0,0,0.18) 0 2%, transparent 2% 6%,
      rgba(255,255,255,0.12) 6% 11%, transparent 11% 16%,
      rgba(0,0,0,0.24) 16% 22%, transparent 22% 28%,
      rgba(255,255,255,0.08) 28% 34%, transparent 34% 42%,
      rgba(0,0,0,0.2) 42% 48%, transparent 48% 56%,
      rgba(255,255,255,0.1) 56% 62%, transparent 62% 72%,
      rgba(0,0,0,0.22) 72% 78%, transparent 78% 85%,
      rgba(255,255,255,0.08) 85% 90%, transparent 90% 100%);
  background-size: 80px 100%;
  opacity: 0.9;
  pointer-events: none;
}
header::after {
  content: '';
  position: absolute;
  top: 20%; left: 0; right: 0; bottom: 0;
  background-image:
    radial-gradient(circle at 12% 40%, rgba(0,0,0,0.3) 2px, transparent 3px),
    radial-gradient(circle at 38% 70%, rgba(255,255,255,0.08) 1.5px, transparent 2.5px),
    radial-gradient(circle at 67% 25%, rgba(0,0,0,0.35) 2px, transparent 3px),
    radial-gradient(circle at 84% 68%, rgba(0,0,0,0.25) 2px, transparent 3px),
    radial-gradient(circle at 52% 50%, rgba(255,255,255,0.05) 1px, transparent 2px);
  background-size: 120px 120px, 90px 90px, 150px 150px, 100px 100px, 70px 70px;
  pointer-events: none;
}

.header-inner {
  max-width: 1420px;
  margin: 0 auto;
  padding: 26px 24px 22px;
  display: flex;
  justify-content: space-between;
  align-items: flex-end;
  gap: 22px;
  flex-wrap: wrap;
  position: relative;
  z-index: 3;
}
.title-block {
  display: flex;
  align-items: center;
  gap: 16px;
}
.tnt-icon {
  width: 62px;
  height: 62px;
  background: linear-gradient(180deg, #ef5050 0%, #d13232 44%, #a41b1b 46%, #7a0f0f 100%);
  border: 3px solid #000;
  box-shadow:
    inset 3px 3px 0 rgba(255,255,255,0.25),
    inset -3px -3px 0 rgba(0,0,0,0.35),
    4px 4px 0 rgba(0,0,0,0.5);
  position: relative;
  display: flex; align-items: center; justify-content: center;
  font-family: 'Press Start 2P', monospace;
  font-size: 11px;
  color: #fff;
  text-shadow: 2px 2px 0 #000;
  letter-spacing: 1px;
  flex-shrink: 0;
}
.tnt-icon::before {
  content: '';
  position: absolute;
  inset: 0;
  background-image:
    repeating-linear-gradient(0deg, transparent 0 8px, rgba(0,0,0,0.12) 8px 9px),
    repeating-linear-gradient(90deg, transparent 0 8px, rgba(255,255,255,0.06) 8px 9px);
  pointer-events: none;
}
.tnt-icon::after {
  content: '';
  position: absolute;
  top: -10px; left: 50%;
  width: 4px; height: 12px;
  background: #d4c48a;
  transform: translateX(-50%);
  box-shadow: 0 -2px 0 #8a7a45, inset 1px 0 0 rgba(255,255,255,0.25);
}
h1 {
  font-family: 'Press Start 2P', monospace;
  font-size: 24px;
  color: #fff;
  text-shadow: 3px 3px 0 #000, 4px 4px 0 rgba(0,0,0,0.5);
  letter-spacing: 1.5px;
  line-height: 1.15;
}
.subtitle {
  font-family: 'Pixelify Sans', monospace;
  font-size: 16px;
  color: #ffeab3;
  text-shadow: 2px 2px 0 rgba(0,0,0,0.8);
  margin-top: 6px;
  font-weight: 700;
  letter-spacing: 0.5px;
}

.hud {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}
.hud-pill {
  background: rgba(0,0,0,0.65);
  border: 2px solid #000;
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.12),
    inset -2px -2px 0 rgba(0,0,0,0.35),
    3px 3px 0 rgba(0,0,0,0.55);
  padding: 9px 13px;
  display: flex;
  align-items: center;
  gap: 9px;
  font-family: 'Pixelify Sans', monospace;
  font-size: 15px;
  color: #fff;
  font-weight: 700;
  text-shadow: 1px 1px 0 #000;
}
.hud-pill .dot {
  width: 12px; height: 12px;
  background: var(--mc-redstone);
  border: 2px solid #000;
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.35), 0 0 8px rgba(193,20,20,0.85);
  animation: pulseDot 1.6s ease-in-out infinite;
}
.hud-pill .dot.ok {
  background: var(--mc-emerald);
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.35), 0 0 10px rgba(23,221,98,0.9);
}
.hud-pill .dot.warn {
  background: var(--mc-gold);
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.35), 0 0 10px rgba(252,211,77,0.9);
}
@keyframes pulseDot { 0%,100% { opacity: 1; } 50% { opacity: 0.5; } }
.hud-pill .label {
  opacity: 0.7;
  text-transform: uppercase;
  font-family: 'Press Start 2P', monospace;
  font-size: 9px;
  letter-spacing: 1.4px;
  color: #cfcfcf;
}

/* ---------- LAYOUT ---------- */
main {
  position: relative;
  z-index: 1;
  display: grid;
  grid-template-columns: repeat(12, 1fr);
  gap: 14px;
  padding: 22px 20px 40px;
  max-width: 1420px;
  margin: 0 auto;
}
.span-3 { grid-column: span 3; }
.span-4 { grid-column: span 4; }
.span-6 { grid-column: span 6; }
.span-8 { grid-column: span 8; }
.span-12 { grid-column: span 12; }

@media (max-width: 1100px) {
  .span-3 { grid-column: span 6; }
  .span-4 { grid-column: span 6; }
  .span-8 { grid-column: span 12; }
}
@media (max-width: 680px) {
  .span-3, .span-4, .span-6, .span-8 { grid-column: span 12; }
}

/* ---------- PANEL (CHEST / INVENTORY STYLE) ---------- */
section.panel {
  position: relative;
  background:
    linear-gradient(180deg,
      #4c4c4c 0%, #3a3a3a 35%, #2a2a2a 100%);
  border: 3px solid #000;
  box-shadow:
    inset 0 0 0 2px #6c6c6c,
    inset 0 0 0 4px #2e2e2e,
    4px 4px 0 rgba(0,0,0,0.55);
  display: flex;
  flex-direction: column;
  min-height: 0;
}
section.panel > h2 {
  font-family: 'Press Start 2P', monospace;
  font-size: 11px;
  padding: 11px 14px 10px;
  color: #fff;
  text-shadow: 2px 2px 0 #000;
  letter-spacing: 0.5px;
  background: linear-gradient(180deg, #3f3f3f 0%, #252525 100%);
  border-bottom: 2px solid #000;
  text-transform: uppercase;
  display: flex;
  align-items: center;
  gap: 10px;
  font-weight: normal;
  line-height: 1.4;
}
section.panel > h2::before {
  content: '▣';
  color: var(--mc-gold);
  text-shadow: 1px 1px 0 #000;
  font-size: 15px;
}
.panel-body {
  padding: 14px;
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

/* ---------- VALUES / LABELS ---------- */
.big-value {
  font-family: 'Press Start 2P', monospace;
  font-size: 24px;
  color: var(--mc-gold);
  text-shadow: 3px 3px 0 #000, 0 0 12px rgba(252,211,77,0.35);
  line-height: 1.15;
}
.big-value.diamond {
  color: var(--mc-diamond);
  text-shadow: 3px 3px 0 #000, 0 0 12px rgba(79,202,215,0.45);
}
.big-value.tnt {
  color: #ff8a8a;
  text-shadow: 3px 3px 0 #000, 0 0 12px rgba(255,60,60,0.45);
}
.mini-label {
  font-family: 'Pixelify Sans', monospace;
  font-size: 13px;
  color: #a8a8a8;
  text-transform: uppercase;
  letter-spacing: 1.5px;
  font-weight: 700;
  text-shadow: 1px 1px 0 #000;
}
.value-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 10px;
  padding: 3px 0;
}
.value-row .val {
  font-family: 'Press Start 2P', monospace;
  font-size: 12px;
  color: #fff;
  text-shadow: 2px 2px 0 #000;
}

/* ---------- XP-BAR / HP-BAR PROGRESS ---------- */
.xp-bar {
  position: relative;
  height: 14px;
  background: #000;
  border: 2px solid #000;
  box-shadow: inset 0 0 0 1px #2a2a2a, 2px 2px 0 rgba(0,0,0,0.35);
  margin: 4px 0 6px;
}
.xp-bar .fill {
  height: 100%;
  background:
    linear-gradient(180deg,
      var(--mc-xp) 0%, var(--mc-xp) 45%,
      var(--mc-xp-dark) 46%, var(--mc-xp-dark) 100%);
  transition: width 0.4s step-start;
  position: relative;
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.45);
}
.xp-bar .fill::after {
  content: '';
  position: absolute; inset: 0;
  background-image: repeating-linear-gradient(
    90deg, transparent 0 9px, rgba(0,0,0,0.35) 9px 10px);
}
.xp-bar.hp .fill {
  background:
    linear-gradient(180deg,
      #ff5252 0%, #e01f1f 45%,
      #8a0b0b 46%, #7a0808 100%);
  box-shadow: inset 0 1px 0 rgba(255,255,255,0.35);
}
.xp-bar.gold .fill {
  background:
    linear-gradient(180deg,
      var(--mc-gold) 0%, var(--mc-gold) 45%,
      var(--mc-gold-dark) 46%, var(--mc-gold-dark) 100%);
}

/* ---------- MINECRAFT BUTTON ---------- */
.mc-btn {
  font-family: 'Pixelify Sans', monospace;
  font-weight: 700;
  font-size: 15px;
  letter-spacing: 0.5px;
  color: #ffffff;
  text-shadow: 2px 2px 0 #000;
  background: linear-gradient(180deg, #a6a6a6 0%, #858585 45%, #6c6c6c 46%, #525252 100%);
  border: 3px solid #000;
  padding: 10px 12px;
  cursor: pointer;
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.28),
    inset -2px -2px 0 rgba(0,0,0,0.4),
    3px 3px 0 rgba(0,0,0,0.55);
  transition: transform 0.07s, filter 0.12s, box-shadow 0.12s;
  position: relative;
  min-height: 44px;
  text-align: center;
  line-height: 1.15;
}
.mc-btn:hover {
  filter: brightness(1.18) saturate(1.08);
  transform: translate(-1px, -1px);
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.32),
    inset -2px -2px 0 rgba(0,0,0,0.4),
    5px 5px 0 rgba(0,0,0,0.55),
    0 0 14px rgba(255,255,255,0.1);
}
.mc-btn:active {
  transform: translate(2px, 2px);
  box-shadow:
    inset -2px -2px 0 rgba(255,255,255,0.18),
    inset 2px 2px 0 rgba(0,0,0,0.4),
    1px 1px 0 rgba(0,0,0,0.4);
  filter: brightness(0.9);
}

.mc-btn.tnt     { background: linear-gradient(180deg, #ef5050 0%, #cd2a2a 45%, #a01616 46%, #760a0a 100%); }
.mc-btn.mega    { background: linear-gradient(180deg, #ffa840 0%, #e68424 45%, #b8620f 46%, #8a4508 100%); }
.mc-btn.rain    { background: linear-gradient(180deg, #5fc8dc 0%, #3ba8be 45%, #2882a0 46%, #1a5e7a 100%); }
.mc-btn.creeper { background: linear-gradient(180deg, #7bc84a 0%, #55a42e 45%, #367c1a 46%, #24560f 100%); }
.mc-btn.nuke    { background: linear-gradient(180deg, #ff4040 0%, #dc1010 45%, #8e0a0a 46%, #5a0404 100%); }
.mc-btn.meteor  { background: linear-gradient(180deg, #b487e6 0%, #9060d0 45%, #6a3fa8 46%, #49247c 100%); }
.mc-btn.gold {
  background: linear-gradient(180deg, #ffe77a 0%, #f5c420 45%, #b8901e 46%, #8a6a10 100%);
  color: #2d1a00;
  text-shadow: 1px 1px 0 rgba(255,255,255,0.35);
}
.mc-btn.emerald { background: linear-gradient(180deg, #46f088 0%, #1cc85c 45%, #128a3c 46%, #0a5828 100%); }
.mc-btn.diamond { background: linear-gradient(180deg, #7ee8f0 0%, #3bc8d8 45%, #1e8aa0 46%, #106070 100%); }
.mc-btn.obsidian { background: linear-gradient(180deg, #4a3a6a 0%, #2e204a 45%, #1a1230 46%, #0d0820 100%); }
.mc-btn.potion   { background: linear-gradient(180deg, #e06cff 0%, #b040d8 45%, #7e24a2 46%, #50106a 100%); }
.mc-btn.redstone {
  background: linear-gradient(180deg, #ff4a4a 0%, #c81010 45%, #8a0808 46%, #560404 100%);
  animation: redstonePulse 2.4s ease-in-out infinite;
}
@keyframes redstonePulse {
  0%, 100% {
    box-shadow:
      inset 2px 2px 0 rgba(255,255,255,0.28),
      inset -2px -2px 0 rgba(0,0,0,0.4),
      3px 3px 0 rgba(0,0,0,0.55),
      0 0 6px rgba(255,40,40,0.35);
  }
  50% {
    box-shadow:
      inset 2px 2px 0 rgba(255,255,255,0.28),
      inset -2px -2px 0 rgba(0,0,0,0.4),
      3px 3px 0 rgba(0,0,0,0.55),
      0 0 18px rgba(255,60,60,0.85);
  }
}

.btn-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(108px, 1fr));
  gap: 8px;
}
.btn-grid.narrow {
  grid-template-columns: repeat(auto-fit, minmax(90px, 1fr));
}

.tooltip-label {
  font-family: 'Press Start 2P', monospace;
  font-size: 9px;
  color: var(--mc-gold);
  letter-spacing: 1.5px;
  text-transform: uppercase;
  padding: 6px 0 2px;
  text-shadow: 2px 2px 0 #000;
}

/* ---------- GIFTER LEADERBOARD ---------- */
.gifter-list {
  max-height: 280px;
  overflow-y: auto;
  padding-right: 2px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}
.gifter {
  display: flex;
  align-items: center;
  padding: 8px 10px;
  background: rgba(0,0,0,0.4);
  border: 2px solid #000;
  border-left: 4px solid var(--mc-stone-light);
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.05);
  font-family: 'Pixelify Sans', monospace;
}
.gifter:nth-child(1) {
  border-left-color: var(--mc-gold);
  background: linear-gradient(90deg, rgba(252,211,77,0.15) 0%, rgba(0,0,0,0.4) 70%);
}
.gifter:nth-child(2) { border-left-color: #d5d5d5; background: linear-gradient(90deg, rgba(200,200,200,0.12) 0%, rgba(0,0,0,0.4) 70%); }
.gifter:nth-child(3) { border-left-color: #cd7f32; background: linear-gradient(90deg, rgba(205,127,50,0.14) 0%, rgba(0,0,0,0.4) 70%); }
.gifter .rank {
  font-family: 'Press Start 2P', monospace;
  font-size: 10px;
  width: 26px;
  color: #888;
  text-shadow: 1px 1px 0 #000;
}
.gifter:nth-child(1) .rank { color: var(--mc-gold); }
.gifter:nth-child(2) .rank { color: #e6e6e6; }
.gifter:nth-child(3) .rank { color: #ff9f5c; }
.gifter .name {
  flex: 1;
  padding: 0 10px;
  color: #fff;
  font-size: 15px;
  font-weight: 700;
  text-shadow: 1px 1px 0 #000;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}
.gifter .coins {
  font-family: 'Press Start 2P', monospace;
  font-size: 10px;
  color: var(--mc-gold);
  text-shadow: 1px 1px 0 #000;
}
.gifter .coins::before { content: '◆ '; color: var(--mc-diamond); }

/* ---------- CHAT LOG ---------- */
.chat-log {
  font-family: 'Pixelify Sans', monospace;
  font-size: 14px;
  line-height: 1.55;
  color: #dadada;
  max-height: 260px;
  overflow-y: auto;
  background: linear-gradient(180deg, rgba(0,0,0,0.65) 0%, rgba(0,0,0,0.78) 100%);
  padding: 12px 14px;
  border: 2px solid #000;
  box-shadow: inset 2px 2px 0 rgba(255,255,255,0.04), inset 0 0 0 1px #2e2e2e;
  font-weight: 500;
}
.chat-log > div {
  padding: 2px 0;
  text-shadow: 1px 1px 0 #000;
}
.chat-log .ts {
  color: #7a7a7a;
  font-family: 'Press Start 2P', monospace;
  font-size: 9px;
  margin-right: 8px;
}
.chat-log .msg { color: #ffeab3; }

/* ---------- COMMAND BLOCK INPUT ---------- */
.cmd-block {
  display: flex;
  gap: 10px;
  align-items: stretch;
}
.cmd-input {
  flex: 1;
  font-family: 'Pixelify Sans', monospace;
  font-size: 16px;
  font-weight: 700;
  background:
    linear-gradient(180deg, #c85c3a 0%, #a03a24 48%, #7a2a18 49%, #5e1e10 100%);
  color: #fff;
  padding: 11px 14px;
  border: 3px solid #000;
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.22),
    inset -2px -2px 0 rgba(0,0,0,0.4),
    3px 3px 0 rgba(0,0,0,0.55);
  text-shadow: 1px 1px 0 #000;
  outline: none;
  letter-spacing: 0.5px;
}
.cmd-input::placeholder {
  color: rgba(255,255,255,0.55);
  font-style: italic;
}
.cmd-input:focus {
  background:
    linear-gradient(180deg, #d6694a 0%, #b44530 48%, #8a3222 49%, #6e2416 100%);
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.3),
    inset -2px -2px 0 rgba(0,0,0,0.4),
    3px 3px 0 rgba(0,0,0,0.55),
    0 0 16px rgba(220,120,60,0.5);
}
#out {
  padding: 10px 12px;
  font-family: 'Pixelify Sans', monospace;
  font-size: 14px;
  color: #ffeab3;
  background: rgba(0,0,0,0.55);
  border: 2px solid #000;
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.05);
  word-break: break-all;
  text-shadow: 1px 1px 0 #000;
  margin-top: 2px;
}
#out:empty { display: none; }

/* ---------- MOB SELECTOR ---------- */
.mob-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(82px, 1fr));
  gap: 6px;
  max-height: 360px;
  overflow-y: auto;
  padding: 12px;
  background:
    linear-gradient(180deg, #1b1b1b 0%, #0c0c0c 100%);
  border: 3px solid #000;
  box-shadow:
    inset 2px 2px 0 rgba(0,0,0,0.5),
    inset 0 0 0 2px #333;
}
.mob-category {
  grid-column: 1 / -1;
  font-family: 'Press Start 2P', monospace;
  font-size: 9px;
  color: var(--mc-gold);
  text-transform: uppercase;
  letter-spacing: 1.5px;
  padding: 10px 2px 4px;
  text-shadow: 2px 2px 0 #000;
  border-bottom: 1px dashed rgba(252,211,77,0.25);
  margin-bottom: 2px;
}
.mob-category:first-child { padding-top: 2px; }

.mob-card {
  background: linear-gradient(180deg, #5a5a5a 0%, #3c3c3c 45%, #2e2e2e 100%);
  border: 2px solid #000;
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.18),
    inset -2px -2px 0 rgba(0,0,0,0.4);
  padding: 8px 4px 6px;
  cursor: pointer;
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 4px;
  min-height: 80px;
  transition: transform 0.08s, filter 0.12s;
  font-family: 'Pixelify Sans', monospace;
  font-size: 11px;
  color: #fff;
  text-shadow: 1px 1px 0 #000;
  text-align: center;
}
.mob-card:hover {
  filter: brightness(1.25);
  transform: translate(-1px, -1px);
}
.mob-card.selected {
  background: linear-gradient(180deg, #e49a34 0%, #b87818 45%, #8a5812 46%, #5a3c0a 100%);
  border-color: var(--mc-gold);
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.3),
    inset -2px -2px 0 rgba(0,0,0,0.3),
    0 0 14px rgba(252,211,77,0.8);
}
.mob-card .thumb {
  width: 42px; height: 42px;
  background: rgba(0,0,0,0.45);
  border: 1px solid rgba(0,0,0,0.6);
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.06);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  image-rendering: pixelated;
}
.mob-card .thumb img {
  width: 36px; height: 36px;
  image-rendering: pixelated;
  display: block;
}
.mob-card .lbl {
  line-height: 1.2;
  font-weight: 700;
  word-break: break-word;
}

.bot-select-info {
  font-family: 'Pixelify Sans', monospace;
  font-size: 14px;
  color: #d8d8d8;
  padding: 10px 12px;
  background: rgba(0,0,0,0.5);
  border: 2px solid #000;
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.05);
  text-shadow: 1px 1px 0 #000;
  font-weight: 700;
}
#bot-selected {
  color: var(--mc-gold);
  font-family: 'Press Start 2P', monospace;
  font-size: 11px;
  margin-left: 8px;
  text-shadow: 2px 2px 0 #000;
}
#bot-status {
  font-family: 'Pixelify Sans', monospace;
  font-size: 14px;
  color: #bcbcbc;
  padding: 8px 12px;
  background: rgba(0,0,0,0.5);
  border: 2px solid #000;
  border-left: 4px solid var(--mc-emerald);
  box-shadow: inset 1px 1px 0 rgba(255,255,255,0.05);
  text-shadow: 1px 1px 0 #000;
  font-weight: 500;
}

/* Scrollbar */
::-webkit-scrollbar { width: 14px; height: 14px; }
::-webkit-scrollbar-track { background: #0d0d0d; border: 2px solid #000; }
::-webkit-scrollbar-thumb {
  background: linear-gradient(180deg, #6a6a6a 0%, #3a3a3a 100%);
  border: 2px solid #000;
  box-shadow:
    inset 2px 2px 0 rgba(255,255,255,0.2),
    inset -2px -2px 0 rgba(0,0,0,0.3);
}
::-webkit-scrollbar-thumb:hover { filter: brightness(1.2); }

/* ---------- RESPONSIVE ---------- */
@media (max-width: 900px) {
  main { padding: 14px 12px 30px; gap: 10px; }
  .header-inner { padding: 20px 16px; }
  h1 { font-size: 18px; }
  .big-value { font-size: 20px; }
  .tnt-icon { width: 50px; height: 50px; font-size: 9px; }
}
</style>
</head>
<body>

<header>
  <div class="header-inner">
    <div class="title-block">
      <div class="tnt-icon">TNT</div>
      <div>
        <h1>TIKTOK BOX</h1>
        <div class="subtitle">◆ KONTROL PANOSU ◆ @{{ tiktok_user }}</div>
      </div>
    </div>
    <div class="hud">
      <span class="hud-pill"><span class="dot" id="dot-srv"></span><span class="label">Sunucu</span><span id="srv-info">-</span></span>
      <span class="hud-pill"><span class="dot" id="dot-lis"></span><span class="label">Listener</span><span id="lis-info">-</span></span>
      <span class="hud-pill"><span class="dot" id="dot-live"></span><span class="label">Yayın</span><span id="live-info">-</span></span>
    </div>
  </div>
</header>

<main>

  <section class="panel span-4">
    <h2>Arena</h2>
    <div class="panel-body">
      <div class="value-row"><span class="mini-label">Doluluk</span><span class="big-value" id="a-pct">0%</span></div>
      <div class="xp-bar"><div class="fill" id="a-bar" style="width:0%"></div></div>
      <div class="value-row"><span class="mini-label">Blok</span><span class="val" id="a-blocks">0 / 0</span></div>
      <div class="value-row"><span class="mini-label">Zafer</span><span class="val" id="a-wins">0</span></div>
      <div class="value-row"><span class="mini-label">Countdown</span><span class="val" id="a-cd">-</span></div>
    </div>
  </section>

  <section class="panel span-4">
    <h2>Beğeniler</h2>
    <div class="panel-body">
      <div class="value-row"><span class="mini-label">Toplam ❤</span><span class="big-value tnt" id="l-total">-</span></div>
      <div class="xp-bar hp"><div class="fill" id="l-bar" style="width:0%"></div></div>
      <div class="value-row"><span class="mini-label">Sonraki</span><span class="val" id="l-next">-</span></div>
      <div class="mini-label" id="l-note" style="margin-top:4px; opacity:0.85;"></div>
    </div>
  </section>

  <section class="panel span-4">
    <h2>Top Hediye</h2>
    <div class="panel-body">
      <div class="gifter-list" id="gifters"><div class="mini-label" style="opacity:0.5; padding:8px 0;">Henüz hediye yok</div></div>
    </div>
  </section>

  <section class="panel span-4">
    <h2>TNT Tetikle</h2>
    <div class="panel-body">
      <div class="btn-grid narrow">
        <button class="mc-btn tnt"     onclick="act('tnt','normal')">Normal</button>
        <button class="mc-btn mega"    onclick="act('tnt','mega')">Mega</button>
        <button class="mc-btn rain"    onclick="act('tnt','rain')">Yağmur</button>
        <button class="mc-btn creeper" onclick="act('tnt','creeper')">Creeper</button>
        <button class="mc-btn nuke"    onclick="act('tnt','nuke')">Nuke</button>
        <button class="mc-btn meteor"  onclick="act('tnt','meteor')">Meteor</button>
      </div>
    </div>
  </section>

  <section class="panel span-4">
    <h2>Arena Kontrol</h2>
    <div class="panel-body">
      <div class="tooltip-label">Hızlı Fill</div>
      <div class="btn-grid narrow">
        <button class="mc-btn" onclick="fill(25)">25%</button>
        <button class="mc-btn" onclick="fill(50)">50%</button>
        <button class="mc-btn" onclick="fill(75)">75%</button>
        <button class="mc-btn gold" onclick="fill(100)">100%</button>
      </div>
      <div class="tooltip-label">Aksiyonlar</div>
      <div class="btn-grid narrow">
        <button class="mc-btn" onclick="simple('clear')">Temizle</button>
        <button class="mc-btn emerald" onclick="simple('win')">Zafer</button>
        <button class="mc-btn" onclick="simple('cleartnt')">TNT Sil</button>
        <button class="mc-btn" onclick="simple('cleargifters')">Top Sıfırla</button>
        <button class="mc-btn redstone" onclick="confirm('Arena tamamen silinsin mi?') && simple('wipe')">WIPE</button>
      </div>
    </div>
  </section>

  <section class="panel span-4">
    <h2>Efektler (Yayıncıya)</h2>
    <div class="panel-body">
      <div class="btn-grid narrow">
        <button class="mc-btn obsidian" onclick="effect('blindness')">Kör</button>
        <button class="mc-btn potion"   onclick="effect('nausea')">Bulantı</button>
        <button class="mc-btn diamond"  onclick="effect('slowness')">Yavaş</button>
        <button class="mc-btn rain"     onclick="effect('levitation')">Uçuş</button>
        <button class="mc-btn obsidian" onclick="effect('darkness')">Ters Dünya</button>
        <button class="mc-btn gold"     onclick="effect('speed')">Hız</button>
        <button class="mc-btn potion"   onclick="effect('mega_sabotaj')">Mega Sabotaj</button>
        <button class="mc-btn nuke"     onclick="effect('combo_nuke')">Felaket</button>
      </div>
    </div>
  </section>

  <section class="panel span-12">
    <h2>Cezalar</h2>
    <div class="panel-body">
      <div class="btn-grid">
        <button class="mc-btn redstone" onclick="penalty('prison')">🔒 Hapis (10s)</button>
        <button class="mc-btn redstone" onclick="penalty('gauntlet')">⚔ Canavarlara Yem (30s)</button>
        <button class="mc-btn emerald" onclick="penalty('end')">Serbest Bırak</button>
      </div>
    </div>
  </section>

  <section class="panel span-12">
    <h2>Yardımcı Bot</h2>
    <div class="panel-body">
      <div class="bot-select-info">Seçili karakter:<span id="bot-selected">Köylü</span></div>
      <div class="mob-grid" id="mob-grid"></div>
      <div class="tooltip-label">Başlat (blok/saniye)</div>
      <div class="btn-grid narrow">
        <button class="mc-btn" onclick="botStart(1)">1 bps</button>
        <button class="mc-btn" onclick="botStart(2)">2 bps</button>
        <button class="mc-btn" onclick="botStart(5)">5 bps</button>
        <button class="mc-btn gold" onclick="botStart(10)">10 bps</button>
        <button class="mc-btn redstone" onclick="bot('stop')">Durdur</button>
      </div>
      <div class="tooltip-label">Kamera</div>
      <div class="btn-grid narrow">
        <button class="mc-btn diamond" onclick="bot('watch')">👁 Bot POV</button>
        <button class="mc-btn" onclick="bot('unwatch')">POV Çıkış</button>
      </div>
      <div id="bot-status">-</div>
    </div>
  </section>

  <section class="panel span-12">
    <h2>Komut Bloğu</h2>
    <div class="panel-body">
      <div class="cmd-block">
        <input class="cmd-input" id="cmd" type="text" placeholder="/arena status   ya da   say merhaba" onkeydown="if(event.key==='Enter')runCmd()">
        <button class="mc-btn gold" onclick="runCmd()" style="min-width:140px;">⏎ Çalıştır</button>
      </div>
      <div id="out"></div>
    </div>
  </section>

  <section class="panel span-12">
    <h2>Son Aksiyonlar</h2>
    <div class="panel-body">
      <div class="chat-log" id="log"></div>
    </div>
  </section>

</main>

<script>
async function api(path, body) {
  const opts = { headers: {'Content-Type':'application/json'} };
  if (body) { opts.method='POST'; opts.body=JSON.stringify(body); }
  const r = await fetch(path, opts);
  return r.json();
}
async function act(action, tier) { await api('/api/action', {action, tier}); refresh(); }
async function effect(name) { await api('/api/action', {action:'effect', name}); refresh(); }
async function simple(a)    { await api('/api/action', {action:a}); refresh(); }
async function fill(pct)    { await api('/api/action', {action:'fill', pct}); refresh(); }
async function penalty(kind){ await api('/api/action', {action:'penalty', kind}); refresh(); }
async function bot(op, bps, type){
  const r = await api('/api/action', {action:'bot', op, bps, type});
  if (r.output) document.getElementById('bot-status').textContent = r.output;
  refresh();
}
let selectedMob = 'villager';
const MOBS = [
  {cat:'Varsayılan', items:[{t:'villager', l:'Köylü', e:'🧑'}]},
  {cat:'Evcil', items:[
    {t:'allay', l:'Allay', e:'✨'}, {t:'cat', l:'Kedi', e:'🐱'},
    {t:'ocelot', l:'Ocelot', e:'🐆'}, {t:'wolf', l:'Kurt', e:'🐺'},
    {t:'fox', l:'Tilki', e:'🦊'}, {t:'parrot', l:'Papağan', e:'🦜'},
    {t:'bee', l:'Arı', e:'🐝'}, {t:'axolotl', l:'Axolotl', e:'🦎'},
    {t:'frog', l:'Kurbağa', e:'🐸'}, {t:'turtle', l:'Kaplumbağa', e:'🐢'},
    {t:'sniffer', l:'Sniffer', e:'🔎'}, {t:'armadillo', l:'Armadillo', e:'🦡'},
    {t:'tadpole', l:'İribaş', e:'🐟'},
  ]},
  {cat:'Çiftlik', items:[
    {t:'cow', l:'İnek', e:'🐄'}, {t:'pig', l:'Domuz', e:'🐖'},
    {t:'sheep', l:'Koyun', e:'🐑'}, {t:'chicken', l:'Tavuk', e:'🐔'},
    {t:'rabbit', l:'Tavşan', e:'🐇'}, {t:'goat', l:'Keçi', e:'🐐'},
    {t:'mooshroom', l:'Mooshroom', e:'🍄'}, {t:'horse', l:'At', e:'🐎'},
    {t:'donkey', l:'Eşek', e:'🐴'}, {t:'mule', l:'Katır', e:'🫏'},
    {t:'llama', l:'Lama', e:'🦙'}, {t:'trader_llama', l:'Trader Lama', e:'🦙'},
    {t:'camel', l:'Deve', e:'🐫'},
  ]},
  {cat:'Köylü/İnsansı', items:[
    {t:'wandering_trader', l:'Gezgin Tüccar', e:'🧳'},
    {t:'zombie_villager', l:'Zombi Köylü', e:'🧟'},
    {t:'piglin', l:'Piglin', e:'🐷'},
    {t:'piglin_brute', l:'Piglin Brute', e:'⚔️'},
  ]},
  {cat:'Golem', items:[
    {t:'iron_golem', l:'Iron Golem', e:'🛡️'},
    {t:'snow_golem', l:'Kardan Adam', e:'⛄'},
  ]},
  {cat:'Yaban', items:[
    {t:'panda', l:'Panda', e:'🐼'},
    {t:'polar_bear', l:'Kutup Ayısı', e:'🐻‍❄️'},
    {t:'bat', l:'Yarasa', e:'🦇'},
  ]},
  {cat:'Su', items:[
    {t:'dolphin', l:'Yunus', e:'🐬'}, {t:'squid', l:'Ahtapot', e:'🦑'},
    {t:'glow_squid', l:'Parlak Ahtapot', e:'💡'},
    {t:'cod', l:'Morina', e:'🐟'}, {t:'salmon', l:'Somon', e:'🍣'},
    {t:'tropical_fish', l:'Tropik Balık', e:'🐠'},
    {t:'pufferfish', l:'Kirpi Balığı', e:'🐡'},
    {t:'guardian', l:'Guardian', e:'🔷'},
    {t:'elder_guardian', l:'Elder Guardian', e:'🔶'},
  ]},
  {cat:'Undead', items:[
    {t:'zombie', l:'Zombi', e:'🧟'}, {t:'husk', l:'Husk', e:'🏜️'},
    {t:'drowned', l:'Drowned', e:'🌊'},
    {t:'zombified_piglin', l:'Zombi Piglin', e:'💚'},
    {t:'skeleton', l:'İskelet', e:'💀'},
    {t:'wither_skeleton', l:'Wither İskelet', e:'☠️'},
    {t:'stray', l:'Stray', e:'🧊'}, {t:'bogged', l:'Bogged', e:'🟢'},
    {t:'phantom', l:'Phantom', e:'👁️'},
  ]},
  {cat:'Yaratık', items:[
    {t:'creeper', l:'Creeper', e:'💥'},
    {t:'spider', l:'Örümcek', e:'🕷️'},
    {t:'cave_spider', l:'Mağara Örümceği', e:'🕸️'},
    {t:'silverfish', l:'Silverfish', e:'🐛'},
    {t:'endermite', l:'Endermite', e:'🐜'},
    {t:'slime', l:'Slime', e:'🟩'},
    {t:'magma_cube', l:'Magma Cube', e:'🟥'},
  ]},
  {cat:'End/Nether', items:[
    {t:'enderman', l:'Enderman', e:'🌀'},
    {t:'blaze', l:'Blaze', e:'🔥'},
    {t:'ghast', l:'Ghast', e:'👻'},
    {t:'hoglin', l:'Hoglin', e:'🐗'},
    {t:'zoglin', l:'Zoglin', e:'🐷'},
    {t:'shulker', l:'Shulker', e:'📦'},
  ]},
  {cat:'İlluger', items:[
    {t:'vex', l:'Vex', e:'👻'}, {t:'witch', l:'Cadı', e:'🧙'},
    {t:'vindicator', l:'Vindicator', e:'🪓'},
    {t:'pillager', l:'Pillager', e:'🏹'},
    {t:'evoker', l:'Evoker', e:'🧙‍♂️'},
    {t:'ravager', l:'Ravager', e:'🐗'},
    {t:'illusioner', l:'Illusioner', e:'🎭'},
  ]},
  {cat:'Boss', items:[
    {t:'warden', l:'Warden', e:'🦇'},
    {t:'wither', l:'Wither', e:'💀'},
    {t:'ender_dragon', l:'Ender Dragon', e:'🐉'},
  ]},
];
const ICON_CDNS = [
  t => `https://raw.githubusercontent.com/PrismarineJS/minecraft-assets/master/data/1.20/items/${t}_spawn_egg.png`,
  t => `https://raw.githubusercontent.com/InventivetalentDev/minecraft-assets/1.21/assets/minecraft/textures/item/${t}_spawn_egg.png`,
];
function iconHtml(m) {
  const urls = ICON_CDNS.map(fn => fn(m.t));
  return `<img src="${urls[0]}" data-alt="${urls[1]}" data-emoji="${m.e}" alt="${m.l}" onerror="iconFail(this)">`;
}
function iconFail(img){
  const alt = img.getAttribute('data-alt');
  if (alt) { img.removeAttribute('data-alt'); img.src = alt; return; }
  const emoji = img.getAttribute('data-emoji') || '❓';
  const span = document.createElement('span');
  span.textContent = emoji;
  img.replaceWith(span);
}
function selectMob(t){
  selectedMob = t;
  document.querySelectorAll('.mob-card').forEach(c => c.classList.toggle('selected', c.dataset.t === t));
  const m = MOBS.flatMap(g => g.items).find(x => x.t === t);
  if (m) document.getElementById('bot-selected').textContent = m.l;
}
function renderMobGrid(){
  const el = document.getElementById('mob-grid');
  let html = '';
  for (const grp of MOBS) {
    html += `<div class="mob-category">${grp.cat}</div>`;
    for (const m of grp.items) {
      html += `<div class="mob-card${m.t===selectedMob?' selected':''}" data-t="${m.t}" onclick="selectMob('${m.t}')" title="${m.l}">
        <div class="thumb">${iconHtml(m)}</div>
        <div class="lbl">${m.l}</div>
      </div>`;
    }
  }
  el.innerHTML = html;
}
function botStart(bps){ return bot('start', bps, selectedMob); }
document.addEventListener('DOMContentLoaded', renderMobGrid);
async function runCmd() {
  const v = document.getElementById('cmd').value.trim();
  if (!v) return;
  const r = await api('/api/action', {action:'cmd', cmd: v});
  document.getElementById('out').textContent = r.output || '(boş)';
  refresh();
}

function pad(n) { return (n<10?'0':'')+n; }
function fmtTime(t) {
  const d = new Date(t*1000);
  return pad(d.getHours())+':'+pad(d.getMinutes())+':'+pad(d.getSeconds());
}
function setDot(id, ok, warn) {
  const el = document.getElementById(id);
  el.className = 'dot' + (ok?' ok':'') + (warn?' warn':'');
}

async function refresh() {
  try {
    const s = await api('/api/state');
    // Sunucu
    setDot('dot-srv', s.arena.ok);
    document.getElementById('srv-info').textContent =
      s.arena.ok ? `${s.players.online}/${s.players.max} oyuncu` : 'kapalı';
    // Listener
    const lis = s.listener;
    if (lis && !lis.stale) {
      setDot('dot-lis', true);
      document.getElementById('lis-info').textContent = '@'+(lis.tiktok_user||'-');
    } else if (lis && lis.stale) {
      setDot('dot-lis', false, true);
      document.getElementById('lis-info').textContent = 'kesildi';
    } else {
      setDot('dot-lis', false);
      document.getElementById('lis-info').textContent = 'kapalı';
    }
    // Yayın
    const live = lis && !lis.stale && lis.connected;
    setDot('dot-live', live);
    document.getElementById('live-info').textContent = live ? 'canlı' : 'kapalı';

    // Arena
    document.getElementById('a-pct').textContent = s.arena.pct + '%';
    document.getElementById('a-bar').style.width = s.arena.pct + '%';
    document.getElementById('a-blocks').textContent = s.arena.filled + ' / ' + s.arena.total;
    document.getElementById('a-wins').textContent = s.stats.wins;
    document.getElementById('a-cd').textContent = s.arena.countdown ? (s.arena.countdown + 's ⏱') : '-';

    // Likes
    if (lis && lis.likes_total !== undefined) {
      document.getElementById('l-total').textContent = lis.likes_total.toLocaleString('tr-TR');
      if (lis.next_threshold) {
        const pct = Math.min(100, Math.round(lis.likes_total / lis.next_threshold.at * 100));
        document.getElementById('l-bar').style.width = pct + '%';
        document.getElementById('l-next').textContent = lis.next_threshold.at.toLocaleString('tr-TR') + ' → ' + lis.next_threshold.tnt + ' TNT';
        document.getElementById('l-note').textContent = (lis.next_threshold.at - lis.likes_total) + ' beğeni kaldı';
      } else {
        document.getElementById('l-bar').style.width = '100%';
        document.getElementById('l-next').textContent = 'tüm eşikler tetiklendi';
        document.getElementById('l-note').textContent = '';
      }
    } else {
      document.getElementById('l-total').textContent = '-';
      document.getElementById('l-bar').style.width = '0%';
      document.getElementById('l-next').textContent = 'listener kapalı';
      document.getElementById('l-note').textContent = '';
    }

    // Gifters
    const g = s.stats.gifters || [];
    const gEl = document.getElementById('gifters');
    if (!g.length) {
      gEl.innerHTML = '<div class="mini-label" style="opacity:0.5; padding:8px 0;">Henüz hediye yok</div>';
    } else {
      gEl.innerHTML = g.map((x,i) => `<div class="gifter"><span class="rank">${String(i+1).padStart(2,'0')}.</span><span class="name">${x.user}</span><span class="coins">${x.coins.toLocaleString('tr-TR')}</span></div>`).join('');
    }

    // Bot status
    if (s.bot) {
      document.getElementById('bot-status').textContent = s.bot;
    }

    // Log
    const logEl = document.getElementById('log');
    if (!s.log.length) logEl.innerHTML = '<div style="color:#666;">(log boş)</div>';
    else logEl.innerHTML = s.log.map(l => `<div><span class="ts">[${fmtTime(l.t)}]</span><span class="msg">${l.msg}</span></div>`).join('');
  } catch (e) {
    console.error(e);
  }
}
refresh();
setInterval(refresh, 2000);
</script>
</body>
</html>
"""


@app.route("/")
def index():
    return render_template_string(HTML, tiktok_user=ARENA_CFG.get("tiktok", {}).get("username", "your_username"))


@app.route("/api/state")
def api_state():
    bot_status = strip_color(rcon.cmd("arena bot status") or "").strip() or "-"
    return jsonify({
        "arena": query_arena(),
        "players": query_players(),
        "stats": read_stats(),
        "listener": read_listener_state(),
        "bot": bot_status,
        "log": list(reversed(_log[-30:])),
        "server_time": time.time(),
    })


@app.route("/api/action", methods=["POST"])
def api_action():
    data = request.get_json(force=True, silent=True) or {}
    action = data.get("action", "")
    try:
        if action == "tnt":
            tier = str(data.get("tier", "normal")).lower()
            tnt.fire(tier, source=f"dashboard:admin:{tier}")
            push_log(f"TNT tetiklendi: {tier}")
        elif action == "effect":
            name = str(data.get("name", "")).lower()
            effects.apply(name, source_user="admin")
            push_log(f"Efekt: {name}")
        elif action == "fill":
            pct = int(data.get("pct", 100))
            rcon.cmd(f"arena fill {pct}")
            push_log(f"Fill %{pct}")
        elif action == "clear":
            rcon.cmd("arena clear")
            push_log("Arena clear")
        elif action == "win":
            rcon.cmd("arena win")
            push_log("Arena win (tam doldur)")
        elif action == "cleartnt":
            rcon.cmd("arena cleartnt")
            push_log("Aktif TNT silindi")
        elif action == "cleargifters":
            rcon.cmd("arena cleargifters")
            push_log("Top hediye listesi sıfırlandı")
        elif action == "wipe":
            effects.apply("wipe", source_user="admin")
            push_log("WIPE ceza manuel")
        elif action == "bot":
            op = str(data.get("op", "status")).lower()
            if op == "start":
                bps = int(data.get("bps", 2))
                bot_type = str(data.get("type", "villager")).lower()
                out = rcon.cmd(f"arena bot start {bps} {bot_type}") or ""
                push_log(f"Bot start {bot_type} @{bps}bps → {strip_color(out)[:60]}")
                return jsonify({"ok": True, "output": strip_color(out)})
            elif op == "stop":
                out = rcon.cmd("arena bot stop") or ""
                push_log("Bot stop")
                return jsonify({"ok": True, "output": strip_color(out)})
            elif op == "watch":
                out = rcon.cmd("arena bot watch") or ""
                push_log("Bot POV ON")
                return jsonify({"ok": True, "output": strip_color(out)})
            elif op == "unwatch":
                out = rcon.cmd("arena bot unwatch") or ""
                push_log("Bot POV OFF")
                return jsonify({"ok": True, "output": strip_color(out)})
            else:
                out = rcon.cmd("arena bot status") or ""
                return jsonify({"ok": True, "output": strip_color(out)})
        elif action == "penalty":
            kind = str(data.get("kind", "")).lower()
            if kind in ("prison", "jail", "hapis"):
                rcon.cmd("arena penalty prison")
                push_log("Hapis cezasi")
            elif kind in ("gauntlet", "yem", "canavar"):
                rcon.cmd("arena penalty gauntlet")
                push_log("Canavarlara yem cezasi")
            elif kind in ("end", "stop", "release"):
                rcon.cmd("arena penalty end")
                push_log("Ceza serbest birakildi")
            else:
                return jsonify({"ok": False, "error": "bilinmeyen ceza"}), 400
        elif action == "cmd":
            cmd = str(data.get("cmd", "")).lstrip("/").strip()
            if not cmd:
                return jsonify({"ok": False, "error": "bos komut"}), 400
            out = rcon.cmd(cmd) or ""
            push_log(f"CMD: /{cmd} → {strip_color(out)[:80]}")
            return jsonify({"ok": True, "output": strip_color(out)})
        else:
            return jsonify({"ok": False, "error": "bilinmeyen action"}), 400
    except Exception as e:
        push_log(f"HATA: {e}")
        return jsonify({"ok": False, "error": str(e)}), 500
    return jsonify({"ok": True})


if __name__ == "__main__":
    print("TikTok Box Dashboard → http://127.0.0.1:5010")
    app.run(host="127.0.0.1", port=5010, debug=False, use_reloader=False)
