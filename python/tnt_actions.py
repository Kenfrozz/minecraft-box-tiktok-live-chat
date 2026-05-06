"""TNT spawn actions for each tier."""
import random
import threading
import time

from overlay_bus import BUS


class TntActions:
    def __init__(self, rcon, arena_cfg: dict):
        self.rcon = rcon
        self.arena = arena_cfg["arena"]

    def _bounds(self) -> tuple[int, int, int, int, int, int]:
        a = self.arena["inner_min"]
        b = self.arena["inner_max"]
        return a["x"], a["y"], a["z"], b["x"], b["y"], b["z"]

    def _rand_xz(self, margin: int = 1) -> tuple[int, int]:
        x0, _, z0, x1, _, z1 = self._bounds()
        x = random.randint(x0 + margin, x1 - margin)
        z = random.randint(z0 + margin, z1 - margin)
        return x, z

    def _drop_y(self) -> int:
        _, _, _, _, y1, _ = self._bounds()
        return y1 + 5

    def fire(self, tier: str, source: str = "") -> None:
        tier = (tier or "normal").lower()
        user = self._extract_user(source)
        if tier != "rain_single":
            src_kind = source.split(":", 1)[0] if source else ""
            extra = {}
            if src_kind == "gift":
                parts = source.split(":", 2)
                if len(parts) >= 3:
                    extra["gift"] = parts[2]
            elif src_kind == "likes":
                parts = source.split(":", 2)
                if len(parts) >= 2:
                    extra["milestone"] = parts[1]
            BUS.publish("action", category="tnt", key=tier, user=user,
                        source=src_kind or "chat", **extra)
        if tier == "normal":
            self._announce(tier, user)
            self._drop(tier, user, fuse=40)
        elif tier == "mega":
            self._announce(tier, user)
            self._drop(tier, user, fuse=40)
        elif tier == "rain":
            self._announce(tier, user)
            threading.Thread(target=self._rain, args=(user,), daemon=True, name="tnt-rain").start()
        elif tier == "nuke":
            self._announce(tier, user)
            threading.Thread(target=self._nuke, args=(user,), daemon=True, name="tnt-nuke").start()
        elif tier == "creeper":
            self._announce(tier, user)
            self._drop("creeper", user, fuse=40)
        elif tier == "meteor":
            self._announce(tier, user)
            threading.Thread(target=self._meteor, args=(user,), daemon=True, name="tnt-meteor").start()
        elif tier == "rain_single":
            self._drop_rain_single(user)
        else:
            print(f"[tnt] bilinmeyen tier: {tier}")

    def _extract_user(self, source: str) -> str:
        if not source:
            return "anonim"
        parts = source.split(":", 2)
        if len(parts) >= 2:
            return parts[1] or "anonim"
        return source

    def _announce(self, tier: str, user: str) -> None:
        labels = {
            "normal":  ("TNT",            "yellow"),
            "mega":    ("MEGA TNT",       "gold"),
            "rain":    ("TNT YAGMURU",    "aqua"),
            "nuke":    ("NUKLEER",        "red"),
            "creeper": ("CREEPER ORDUSU", "green"),
            "meteor":  ("METEOR YAGMURU", "dark_red"),
        }
        label, color = labels.get(tier, (tier.upper(), "white"))
        safe_user = self._safe_name(user)
        msg = (
            '["",'
            '{"text":"[","color":"dark_gray"},'
            f'{{"text":"{safe_user}","color":"light_purple","bold":true}},'
            '{"text":"] ","color":"dark_gray"},'
            f'{{"text":"{label}","color":"{color}","bold":true}},'
            '{"text":" gonderdi","color":"gray"}'
            ']'
        )
        self.rcon.cmd(f'tellraw @a {msg}')

    @staticmethod
    def _safe_name(user: str) -> str:
        if not user:
            return "anonim"
        safe = user.replace("\\", "").replace('"', "'")
        return safe[:32] if len(safe) > 32 else safe

    def _name_nbt(self, user: str, color: str = "aqua") -> str:
        """Return ',CustomName:...,CustomNameVisible:1b' NBT snippet.

        1.21.5+ SNBT text-component formatini kullanir (JSON string degil).
        """
        safe = self._safe_name(user)
        return (
            f',CustomName:{{text:"{safe}",color:"{color}",bold:1b}},'
            f'CustomNameVisible:1b'
        )

    def _tag_for(self, tier: str) -> str:
        if tier == "normal":
            return ""
        return f',Tags:["box_{tier}"]'

    def _drop_rain_single(self, user: str) -> None:
        _, _, _, _, y1, _ = self._bounds()
        x, z = self._rand_xz(margin=0)
        y = y1 + 22 + random.randint(0, 6)
        fuse = random.randint(80, 100)
        nbt = f'{{Fuse:{fuse},Tags:["box_rain"]{self._name_nbt(user, "aqua")}}}'
        self.rcon.cmd(f'summon tnt {x} {y} {z} {nbt}')

    def _drop(self, tier: str, user: str, fuse: int = 40) -> None:
        x, z = self._rand_xz()
        y = self._drop_y()
        color = {
            "normal":  "yellow",
            "mega":    "gold",
            "rain":    "aqua",
            "nuke":    "red",
            "creeper": "green",
        }.get(tier, "white")
        nbt = f'{{Fuse:{fuse}{self._tag_for(tier)}{self._name_nbt(user, color)}}}'
        self.rcon.cmd(f'summon tnt {x} {y} {z} {nbt}')

    def _rain(self, user: str) -> None:
        _, _, _, _, y1, _ = self._bounds()
        cx = (self.arena["inner_min"]["x"] + self.arena["inner_max"]["x"]) // 2
        cz = (self.arena["inner_min"]["z"] + self.arena["inner_max"]["z"]) // 2
        self.rcon.cmd('title @a title {"text":"TNT YAGMURU","color":"gold"}')
        self.rcon.cmd(f'playsound minecraft:entity.lightning_bolt.thunder master @a {cx} {y1} {cz} 2 1')
        positions = self._spread_positions(20, min_gap=2)
        random.shuffle(positions)
        for (x, z) in positions:
            y = y1 + 22 + random.randint(0, 6)
            fuse = random.randint(80, 100)
            nbt = f'{{Fuse:{fuse},Tags:["box_rain"]{self._name_nbt(user, "aqua")}}}'
            self.rcon.cmd(f'summon tnt {x} {y} {z} {nbt}')
            time.sleep(0.12)

    def _spread_positions(self, count: int, min_gap: int = 2) -> list[tuple[int, int]]:
        """Poisson-disk benzeri dagilim: her yeni nokta mevcutlardan en az min_gap uzakta."""
        x0, _, z0, x1, _, z1 = self._bounds()
        chosen: list[tuple[int, int]] = []
        min2 = min_gap * min_gap
        attempts = 0
        limit = count * 30
        while len(chosen) < count and attempts < limit:
            attempts += 1
            x = random.randint(x0, x1)
            z = random.randint(z0, z1)
            ok = True
            for (cx, cz) in chosen:
                if (x - cx) ** 2 + (z - cz) ** 2 < min2:
                    ok = False
                    break
            if ok:
                chosen.append((x, z))
        while len(chosen) < count:
            chosen.append((random.randint(x0, x1), random.randint(z0, z1)))
        return chosen

    def _nuke(self, user: str) -> None:
        x0, y0, z0, x1, y1, z1 = self._bounds()
        cx = (x0 + x1) // 2
        cz = (z0 + z1) // 2
        drop_y = y1 + 15
        self.rcon.cmd('title @a title {"text":"NUKLEER","color":"red"}')
        self.rcon.cmd('title @a subtitle {"text":"kacis yok","color":"dark_red"}')
        self.rcon.cmd(f'playsound minecraft:entity.wither.spawn master @a {cx} {drop_y} {cz} 2 0.8')
        self.rcon.cmd(f'particle minecraft:explosion_emitter {cx} {drop_y} {cz} 3 3 3 0.5 25')
        time.sleep(1.0)
        nbt = f'{{Fuse:60,Tags:["box_nuke"]{self._name_nbt(user, "red")}}}'
        self.rcon.cmd(f'summon tnt {cx} {drop_y} {cz} {nbt}')

    def _meteor(self, user: str) -> None:
        x0, y0, z0, x1, y1, z1 = self._bounds()
        cx = (x0 + x1) // 2
        cz = (z0 + z1) // 2
        drop_y = y1 + 25
        self.rcon.cmd('title @a title {"text":"METEOR","color":"dark_red"}')
        self.rcon.cmd('title @a subtitle {"text":"gokyuzu yaniyor","color":"red"}')
        self.rcon.cmd(f'playsound minecraft:entity.ender_dragon.growl master @a {cx} {drop_y} {cz} 2 0.7')
        safe = self._safe_name(user)
        name_nbt = (
            f',CustomName:{{text:"{safe}",color:"dark_red",bold:1b}},'
            f'CustomNameVisible:1b'
        )
        for i in range(50):
            x, z = self._rand_xz(margin=0)
            y = drop_y + random.randint(0, 10)
            nbt = (
                '{ExplosionPower:2,'
                f'Motion:[0.0,-1.2,0.0],Tags:["box_meteor"]'
                f'{name_nbt}}}'
            )
            self.rcon.cmd(f'summon fireball {x} {y} {z} {nbt}')
            time.sleep(0.08)
