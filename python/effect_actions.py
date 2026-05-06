"""Status effect actions (buyuler) - chat keyword veya hediye ile tetiklenir.

Efektler @a (tum oyuncular) uzerinde uygulanir - pratikte yayinci etkilenir.
Sureler kisa tutulmustur ki akis kesilmesin.
"""
from typing import Dict, List, Tuple

from overlay_bus import BUS


class EffectActions:
    # {keyword: [(effect_id, seconds, amplifier)], announce_text}
    PRESETS: Dict[str, Tuple[List[Tuple[str, int, int]], str, str]] = {
        "blindness":  ([("blindness", 4, 0)],                              "KOR",        "dark_purple"),
        "nausea":     ([("nausea", 6, 0)],                                 "SARHOS",     "dark_green"),
        "slowness":   ([("slowness", 6, 4)],                               "YAVAS",      "blue"),
        "levitation": ([("levitation", 3, 0)],                             "UCUS",       "aqua"),
        "darkness":   ([("darkness", 5, 0), ("glowing", 5, 0)],            "TERS DUNYA", "black"),
        "speed":      ([("speed", 5, 1)],                                  "HIZ",        "green"),
        # Hediye komboları
        "mega_sabotaj": ([("blindness", 6, 0), ("slowness", 6, 2), ("nausea", 6, 0)], "MEGA SABOTAJ", "red"),
        "combo_nuke":   ([("blindness", 10, 0), ("slowness", 10, 4), ("nausea", 10, 0), ("levitation", 3, 0)], "FELAKET", "dark_red"),
    }

    def __init__(self, rcon, target: str = "@a"):
        self.rcon = rcon
        self.target = target

    def apply(self, name: str, source_user: str = "") -> None:
        key = (name or "").lower()
        BUS.publish("action", category="effect", key=key,
                    user=source_user or "anonim", source="chat")
        if key == "wipe":
            self._wipe(source_user)
            return
        if key == "jail":
            self._jail(source_user)
            return
        if key == "gauntlet":
            self._gauntlet(source_user)
            return
        preset = self.PRESETS.get(key)
        if not preset:
            print(f"[effect] bilinmeyen: {name}")
            return
        effects, label, color = preset
        for effect, seconds, amplifier in effects:
            self.rcon.cmd(f'effect give {self.target} minecraft:{effect} {seconds} {amplifier} true')
        self._announce(label, color, source_user)
        print(f"[effect] {name} -> {label} (by {source_user})")

    def _wipe(self, source_user: str) -> None:
        self.rcon.cmd('title @a title {"text":"ARENA SIFIRLANDI","color":"dark_red"}')
        self.rcon.cmd('title @a subtitle {"text":"tum bloklar silindi","color":"red"}')
        self.rcon.cmd('playsound minecraft:entity.wither.death master @a ~ ~ ~ 2 0.6')
        self.rcon.cmd('arena clear')
        self._announce("ARENA SIFIRLANDI", "dark_red", source_user)
        print(f"[effect] wipe -> ARENA CLEARED (by {source_user})")

    def _jail(self, source_user: str) -> None:
        self.rcon.cmd('playsound minecraft:block.iron_door.close master @a ~ ~ ~ 2 0.7')
        self.rcon.cmd('arena penalty prison')
        self._announce("HAPIS CEZASI", "dark_purple", source_user)
        print(f"[effect] jail -> PRISON (by {source_user})")

    def _gauntlet(self, source_user: str) -> None:
        self.rcon.cmd('playsound minecraft:entity.ender_dragon.growl master @a ~ ~ ~ 2 0.6')
        self.rcon.cmd('arena penalty gauntlet')
        self._announce("CANAVARLARA YEM", "dark_red", source_user)
        print(f"[effect] gauntlet -> MOB ARENA (by {source_user})")

    def _announce(self, label: str, color: str, user: str) -> None:
        safe = (user or "anonim").replace('"', "'")
        msg = (
            '["",'
            '{"text":"[","color":"dark_gray"},'
            f'{{"text":"{safe}","color":"light_purple","bold":true}},'
            '{"text":"] ","color":"dark_gray"},'
            f'{{"text":"{label}","color":"{color}","bold":true}},'
            '{"text":" buyusu yolladi","color":"gray"}'
            ']'
        )
        self.rcon.cmd(f'tellraw @a {msg}')
