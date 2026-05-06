"""Tek komutla tum TikTok Box stack'ini baslatir:
  1) Paper Minecraft server       (ayri pencerede)
  2) TikTok listener + overlay    (ayri pencerede, main.py)
  3) Dashboard                     (ayri pencerede, dashboard.py)

Sira: server once kalkar (RCON dinleyene kadar beklenir), sonra listener+dashboard.
Ctrl+C ile hepsini duzgun kapatir (server'a RCON uzerinden 'stop' gonderir).
"""
from __future__ import annotations

import json
import os
import signal
import socket
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent
PROJECT = ROOT.parent
SERVER_DIR = PROJECT / "server"
SERVER_BAT = SERVER_DIR / "start.bat"
VENV_PY = ROOT / "venv" / "Scripts" / "python.exe"

ARENA_CFG = json.loads((ROOT / "config" / "arena.json").read_text(encoding="utf-8"))
RCON_CFG = ARENA_CFG["rcon"]
RCON_HOST = RCON_CFG["host"]
RCON_PORT = int(RCON_CFG["port"])
RCON_PASS = RCON_CFG["password"]

CREATE_NEW_CONSOLE = 0x00000010  # Windows-only flag

procs: list[tuple[str, subprocess.Popen]] = []


def log(msg: str) -> None:
    print(f"[launch] {msg}", flush=True)


def _port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def _rcon_ready() -> bool:
    """RCON login+ping ile hazir mi test et."""
    if not _port_open(RCON_HOST, RCON_PORT, timeout=0.5):
        return False
    try:
        from mcrcon import MCRcon  # type: ignore
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as r:
            r.command("list")
        return True
    except Exception:
        return False


def spawn(title: str, args: list[str], cwd: Path) -> subprocess.Popen:
    log(f"baslatiliyor: {title}  ({' '.join(str(a) for a in args)})")
    # Windows'ta yeni konsol penceresi ac
    creationflags = CREATE_NEW_CONSOLE if os.name == "nt" else 0
    p = subprocess.Popen(
        args,
        cwd=str(cwd),
        creationflags=creationflags,
        shell=False,
    )
    procs.append((title, p))
    return p


def wait_rcon(timeout_sec: int = 180) -> bool:
    log(f"RCON bekleniyor {RCON_HOST}:{RCON_PORT} ... (max {timeout_sec}sn)")
    start = time.time()
    while time.time() - start < timeout_sec:
        if _rcon_ready():
            log("RCON hazir ✓")
            return True
        time.sleep(2)
    log("RCON zaman asimi ✗")
    return False


def shutdown_server() -> None:
    """Paper sunucuya RCON uzerinden 'stop' gonder - dunya duzgun kaydedilsin."""
    if not _port_open(RCON_HOST, RCON_PORT, timeout=0.5):
        return
    try:
        from mcrcon import MCRcon  # type: ignore
        with MCRcon(RCON_HOST, RCON_PASS, port=RCON_PORT) as r:
            r.command("say [Sistem] launch.py kapatiliyor...")
            r.command("stop")
        log("Server'a 'stop' gonderildi, dunya kaydediliyor.")
    except Exception as e:
        log(f"stop komutu gonderilemedi: {e}")


def stop_all() -> None:
    log("Kapatma baslatildi...")
    shutdown_server()
    # Listener ve dashboard'a terminate
    for title, p in procs:
        if p.poll() is None:
            try:
                if title == "server":
                    # Zaten stop komutu gonderildi, 20sn bekle
                    try:
                        p.wait(timeout=20)
                        continue
                    except subprocess.TimeoutExpired:
                        log("server timeout, force kill")
                log(f"terminate: {title}")
                p.terminate()
            except Exception as e:
                log(f"terminate hata ({title}): {e}")
    time.sleep(2)
    for title, p in procs:
        if p.poll() is None:
            try:
                log(f"kill: {title}")
                p.kill()
            except Exception:
                pass


def main() -> int:
    # Sanity checks
    if not SERVER_BAT.exists():
        log(f"HATA: server/start.bat bulunamadi: {SERVER_BAT}")
        return 1
    if not VENV_PY.exists():
        log(f"HATA: venv python yok: {VENV_PY}  (once: python -m venv venv && venv\\Scripts\\pip install -r requirements.txt)")
        return 1

    # Zaten acik RCON varsa uyari
    if _port_open(RCON_HOST, RCON_PORT, timeout=0.3):
        log(f"UYARI: {RCON_HOST}:{RCON_PORT} zaten dolu - sunucu zaten calisiyor olabilir. Yeni sunucu baslatilmayacak.")
        server_running_elsewhere = True
    else:
        server_running_elsewhere = False

    try:
        # 1) Minecraft server
        if not server_running_elsewhere:
            spawn("server", ["cmd.exe", "/k", str(SERVER_BAT)], cwd=SERVER_DIR)
            if not wait_rcon(timeout_sec=180):
                log("Server ayaga kalkmadi, diger bilesenler baslatilmiyor.")
                stop_all()
                return 2
        else:
            if not wait_rcon(timeout_sec=30):
                log("Mevcut sunucuda RCON acik degil veya sifre yanlis. Yine de devam?")
                # devam et
        time.sleep(2)

        # 2) TikTok listener (overlay server dahil)
        spawn(
            "listener",
            ["cmd.exe", "/k", str(VENV_PY), str(ROOT / "main.py")],
            cwd=ROOT,
        )
        time.sleep(1.5)

        # 3) Dashboard
        spawn(
            "dashboard",
            ["cmd.exe", "/k", str(VENV_PY), str(ROOT / "dashboard.py")],
            cwd=ROOT,
        )

        log("=" * 60)
        log("Tum bilesenler baslatildi.")
        log("  - Minecraft:  localhost:25565")
        log("  - Dashboard:  http://127.0.0.1:5010")
        log("  - Overlays:   http://127.0.0.1:5011")
        log("Cikmak icin bu pencerede Ctrl+C. Dunya otomatik kaydedilir.")
        log("=" * 60)

        # Herhangi bir process olur olmez rapor et, ana dongu
        while True:
            time.sleep(3)
            dead = [(t, p) for (t, p) in procs if p.poll() is not None]
            for t, p in dead:
                log(f"UYARI: '{t}' cikti (exit={p.returncode}).")
            # Hepsi oldu ise cik
            alive = [(t, p) for (t, p) in procs if p.poll() is None]
            if not alive:
                log("Tum surecler kapandi, cikiliyor.")
                return 0
            # server olduyse listener/dashboard'i da kapat
            if dead and any(t == "server" for t, _ in dead):
                log("Server kapandi, digerleri de kapatiliyor.")
                stop_all()
                return 0
            procs[:] = alive + dead  # tut (zaten var)
    except KeyboardInterrupt:
        log("Ctrl+C alindi.")
        stop_all()
        return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log(f"Beklenmeyen hata: {e}")
        stop_all()
        sys.exit(3)
