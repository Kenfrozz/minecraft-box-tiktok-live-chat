"""Hizli test CLI.

Ornekler:
  python test.py tnt normal
  python test.py tnt mega
  python test.py tnt rain
  python test.py tnt nuke
  python test.py spam tnt 20           # 20 adet normal TNT art arda
  python test.py gift Rose 1 10        # kullanici Rose x10 atti
  python test.py gift Galaxy 1000 1    # 1000 coin Galaxy
  python test.py chat kenfroz tnt      # chat simulasyon: kenfroz 'tnt' yazdi
  python test.py fill 80               # arenayi %80 doldur
  python test.py fill iron             # sadece demir tier'i doldur
  python test.py win                   # arenayi tam doldur (geri sayim baslatir)
  python test.py clear                 # arenayi tamamen temizle
  python test.py reset                 # arena + plugin state sifirla
  python test.py inv                   # envanteri yenile
  python test.py tp                    # arenaya tp ol
"""
import json
import random
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from rcon_client import RconClient
from tnt_actions import TntActions
from effect_actions import EffectActions
from trigger_engine import TriggerEngine

ROOT = Path(__file__).parent
ARENA = json.loads((ROOT / "config" / "arena.json").read_text(encoding="utf-8"))
TRIGGERS = json.loads((ROOT / "config" / "triggers.json").read_text(encoding="utf-8"))

PLAYER = "kenfroz"


def make():
    rcon = RconClient(**ARENA["rcon"])
    tnt = TntActions(rcon, ARENA)
    effects = EffectActions(rcon)
    engine = TriggerEngine(TRIGGERS, tnt, effect_actions=effects, rcon=rcon)
    return rcon, tnt, engine, effects


def cmd_tnt(tier: str) -> None:
    _, tnt, _, _ = make()
    tnt.fire(tier, source="cli")
    print(f"TNT: {tier} -> tetiklendi")


def cmd_effect(name: str) -> None:
    _, _, _, effects = make()
    effects.apply(name, source_user="cli")
    print(f"Effect: {name} uygulandi")


def cmd_spam(what: str, count: int) -> None:
    _, tnt, _, _ = make()
    for i in range(count):
        tnt.fire(what, source=f"cli-spam-{i}")
        time.sleep(0.2)
    print(f"Spam: {count}x {what}")


def cmd_gift(gift_name: str, diamonds: int, repeat: int) -> None:
    _, _, engine, _ = make()
    engine.handle_gift(f"testuser_{random.randint(1000,9999)}", gift_name, diamonds, repeat)


def cmd_chat(username: str, text: str) -> None:
    _, _, engine, _ = make()
    engine.handle_comment(username, text)


def cmd_clear() -> None:
    rcon, _, _, _ = make()
    print(rcon.cmd("arena clear"))
    rcon.close()


def cmd_reset() -> None:
    rcon, _, _, _ = make()
    print(rcon.cmd("arena reset"))
    rcon.close()


def cmd_win() -> None:
    rcon, _, _, _ = make()
    print(rcon.cmd("arena fill"))
    rcon.close()


def cmd_fill(arg: str) -> None:
    rcon, _, _, _ = make()
    arena = ARENA["arena"]
    a = arena["inner_min"]; b = arena["inner_max"]
    if arg.isdigit():
        pct = max(0, min(100, int(arg)))
        rcon.cmd("arena clear")
        time.sleep(0.3)
        tiers = arena["tiers"]
        total_cap = (b["x"]-a["x"]+1) * (b["z"]-a["z"]+1) * (b["y"]-a["y"]+1)
        target = int(total_cap * pct / 100)
        placed = 0
        for t in tiers:
            for y in range(t["y_min"], t["y_max"]+1):
                if placed >= target: break
                for x in range(a["x"], b["x"]+1):
                    if placed >= target: break
                    remaining = target - placed
                    z_width = b["z"] - a["z"] + 1
                    to_place = min(z_width, remaining)
                    z_end = a["z"] + to_place - 1
                    rcon.cmd(f'fill {x} {y} {a["z"]} {x} {y} {z_end} {t["block"]}')
                    placed += to_place
        print(f"Fill %{pct}: {placed} blok yerlestirildi")
    else:
        for t in arena["tiers"]:
            if t["name"].lower() == arg.lower():
                rcon.cmd(f'fill {a["x"]} {t["y_min"]} {a["z"]} {b["x"]} {t["y_max"]} {b["z"]} {t["block"]}')
                print(f"Tier '{arg}' dolduruldu")
                rcon.close()
                return
        print(f"Bilinmeyen tier: {arg}")
    rcon.close()


def cmd_inv() -> None:
    rcon, _, _, _ = make()
    rcon.cmd(f"clear {PLAYER}")
    for mat in ("iron_block", "gold_block", "diamond_block", "stone_bricks", "tnt"):
        rcon.cmd(f"give {PLAYER} {mat} 64")
    print(f"{PLAYER} envanteri yenilendi")
    rcon.close()


def cmd_tp() -> None:
    rcon, _, _, _ = make()
    rcon.cmd(f"tp {PLAYER} 10 54 -8 0 15")
    print(f"{PLAYER} arenaya TP")
    rcon.close()


def cmd_say(text: str) -> None:
    rcon, _, _, _ = make()
    rcon.cmd(f"say {text}")
    rcon.close()


def cmd_help() -> None:
    print(__doc__)


def main() -> int:
    if len(sys.argv) < 2:
        cmd_help(); return 0
    op = sys.argv[1].lower()
    args = sys.argv[2:]
    try:
        if   op == "tnt":    cmd_tnt(args[0] if args else "normal")
        elif op == "effect": cmd_effect(args[0] if args else "blindness")
        elif op == "spam":   cmd_spam(args[0], int(args[1]) if len(args) > 1 else 10)
        elif op == "gift":   cmd_gift(args[0], int(args[1]), int(args[2]) if len(args) > 2 else 1)
        elif op == "chat":   cmd_chat(args[0], args[1])
        elif op == "fill":   cmd_fill(args[0] if args else "100")
        elif op == "win":    cmd_win()
        elif op == "clear":  cmd_clear()
        elif op == "reset":  cmd_reset()
        elif op == "inv":    cmd_inv()
        elif op == "tp":     cmd_tp()
        elif op == "say":    cmd_say(" ".join(args))
        elif op in ("help", "-h", "--help"): cmd_help()
        else:
            print(f"Bilinmeyen komut: {op}")
            cmd_help()
            return 1
    except IndexError:
        print("Eksik argüman")
        cmd_help()
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
