"""TikTok Box - listens to TikTok Live chat+gifts and fires Minecraft TNT actions via RCON."""
import asyncio
import json
import sys
import threading
import time
from pathlib import Path

from TikTokLive import TikTokLiveClient
from TikTokLive.events import (
    ConnectEvent,
    DisconnectEvent,
    CommentEvent,
    GiftEvent,
    LikeEvent,
)

from rcon_client import RconClient
from tnt_actions import TntActions
from effect_actions import EffectActions
from trigger_engine import TriggerEngine
from like_tracker import LikeTracker
import overlay_server

ROOT = Path(__file__).parent
ARENA_CFG = json.loads((ROOT / "config" / "arena.json").read_text(encoding="utf-8"))
TRIGGERS_CFG = json.loads((ROOT / "config" / "triggers.json").read_text(encoding="utf-8"))

rcon_cfg = ARENA_CFG["rcon"]
rcon = RconClient(host=rcon_cfg["host"], port=int(rcon_cfg["port"]), password=rcon_cfg["password"])
tnt = TntActions(rcon, ARENA_CFG)
effects = EffectActions(rcon)
engine = TriggerEngine(TRIGGERS_CFG, tnt, effect_actions=effects, rcon=rcon)

_likes_cfg = ARENA_CFG.get("likes", {})
_thresholds = [(int(p["at"]), int(p["tnt"])) for p in _likes_cfg.get("thresholds", [])]
likes = LikeTracker(
    tnt_actions=tnt,
    rcon=rcon,
    thresholds=_thresholds or [(1000, 10), (5000, 20), (10000, 50), (20000, 100)],
    post_interval=int(_likes_cfg.get("post_interval", 50000)),
    post_count=int(_likes_cfg.get("post_count", 100)),
)

TT_USER = ARENA_CFG["tiktok"]["username"]
client = TikTokLiveClient(unique_id=f"@{TT_USER}")

STATE_PATH = ROOT / "state.json"
_connected = False


def _state_writer() -> None:
    while True:
        try:
            next_th = None
            for (at, tnt_count) in likes.thresholds:
                if at not in likes._fired_milestones and likes.total < at:
                    next_th = {"at": at, "tnt": tnt_count}
                    break
            if next_th is None and likes.thresholds:
                last = likes.thresholds[-1][0]
                n = ((likes.total - last) // likes.post_interval) + 1
                if n >= 1:
                    next_at = last + n * likes.post_interval
                    if next_at not in likes._fired_milestones:
                        next_th = {"at": next_at, "tnt": likes.post_count}
            STATE_PATH.write_text(json.dumps({
                "listener_alive": True,
                "connected": _connected,
                "tiktok_user": TT_USER,
                "likes_total": likes.total,
                "next_threshold": next_th,
                "updated_at": time.time(),
            }), encoding="utf-8")
        except Exception as e:
            print(f"[state] yazma hatasi: {e}")
        time.sleep(2)


threading.Thread(target=_state_writer, daemon=True, name="state-writer").start()

OVERLAY_PORT = int(ARENA_CFG.get("overlay", {}).get("port", 5011))
overlay_server.start_in_thread(port=OVERLAY_PORT)
print(f"[overlay] OBS browser source hub -> http://127.0.0.1:{OVERLAY_PORT}/")


@client.on(ConnectEvent)
async def on_connect(event: ConnectEvent) -> None:
    global _connected
    _connected = True
    rcon.cmd(f'say TikTok bagli: @{TT_USER}')
    print(f"[+] TikTok Live baglandi: @{event.unique_id}")


@client.on(DisconnectEvent)
async def on_disconnect(event: DisconnectEvent) -> None:
    global _connected
    _connected = False
    print("[!] TikTok baglantisi koptu")


@client.on(CommentEvent)
async def on_comment(event: CommentEvent) -> None:
    try:
        user = event.user.unique_id
        text = event.comment
        print(f"[CHAT] {user}: {text}")
        engine.handle_comment(user, text)
    except Exception as e:
        print(f"[err] comment: {e}")


@client.on(LikeEvent)
async def on_like(event: LikeEvent) -> None:
    try:
        total = int(getattr(event, "total", 0) or 0)
        if total <= 0:
            return
        likes.add(total)
    except Exception as e:
        print(f"[err] like: {e}")


@client.on(GiftEvent)
async def on_gift(event: GiftEvent) -> None:
    try:
        gift = event.gift
        if gift.streakable and event.streaking:
            return
        user = event.user.unique_id
        repeat = int(event.repeat_count or 1)
        diamonds = int(gift.diamond_count or 0) * repeat
        print(f"[GIFT] {user}: {gift.name} x{repeat} ({diamonds} coin, id={gift.id})")
        engine.handle_gift(user, gift.name, gift.diamond_count, repeat)
    except Exception as e:
        print(f"[err] gift: {e}")


def main() -> int:
    import time as _time
    print(f"TikTok Box listener — @{TT_USER}")
    print(f"RCON: {rcon_cfg['host']}:{rcon_cfg['port']}")
    print("Yayin acik degilse 30sn'de bir yeniden deneyecek. Ctrl+C ile cik.")
    retry_sec = 30
    try:
        while True:
            try:
                client.run()
                # Clean dönüş = disconnect. Tekrar bağlanmayı dene.
                print(f"[bilgi] Yayin kapandi/baglanti dustu. {retry_sec} sn sonra yeniden denenecek...")
            except KeyboardInterrupt:
                raise
            except Exception as e:
                msg = str(e)
                if "offline" in msg.lower() or "not live" in msg.lower():
                    print(f"[bekle] @{TT_USER} canlida degil. {retry_sec} sn sonra tekrar denenecek...")
                else:
                    print(f"[hata] {e.__class__.__name__}: {e}")
            try:
                _time.sleep(retry_sec)
            except KeyboardInterrupt:
                raise
    except KeyboardInterrupt:
        print("\nKapatiliyor...")
    finally:
        rcon.close()
    return 0


if __name__ == "__main__":
    sys.exit(main())
