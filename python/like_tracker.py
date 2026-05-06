"""Kumulatif begeni takibi - esik gecildiginde TNT yagmuru tetikler.

Esikler (begeni: tnt sayisi):
  1000  -> 10
  5000  -> 20
  10000 -> 50
  20000 -> 100
  20000 sonrasi her +50k -> 100 (donguye girer)
"""
import threading
import time
import random

from overlay_bus import BUS


class LikeTracker:
    def __init__(self, tnt_actions, rcon, thresholds: list[tuple[int, int]],
                 post_interval: int = 50000, post_count: int = 100):
        self.tnt = tnt_actions
        self.rcon = rcon
        # (likes_milestone, tnt_count) sorted ascending
        self.thresholds = sorted(thresholds, key=lambda p: p[0])
        self.post_interval = max(1000, int(post_interval))
        self.post_count = int(post_count)
        self._total = 0
        self._fired_milestones: set[int] = set()
        self._lock = threading.Lock()

    def add(self, new_total: int) -> None:
        """new_total = cumulative likes reported by TikTok."""
        with self._lock:
            if new_total <= self._total:
                return
            self._total = int(new_total)
            to_fire = self._collect_milestones()
        self._publish_state()
        for count, milestone in to_fire:
            self._fire(count, milestone)

    def _publish_state(self) -> None:
        nxt = None
        for (at, tnt_count) in self.thresholds:
            if at not in self._fired_milestones and self._total < at:
                nxt = {"at": at, "tnt": tnt_count}
                break
        if nxt is None and self.thresholds:
            last = self.thresholds[-1][0]
            n = ((self._total - last) // self.post_interval) + 1
            if n >= 1:
                next_at = last + n * self.post_interval
                if next_at not in self._fired_milestones:
                    nxt = {"at": next_at, "tnt": self.post_count}
        BUS.publish("likes", total=self._total, next_threshold=nxt)

    def _collect_milestones(self) -> list[tuple[int, int]]:
        """Return list of (tnt_count, milestone_value) to fire now."""
        out: list[tuple[int, int]] = []
        for milestone, tnt_count in self.thresholds:
            if self._total >= milestone and milestone not in self._fired_milestones:
                self._fired_milestones.add(milestone)
                out.append((tnt_count, milestone))
        if self.thresholds:
            last_defined = self.thresholds[-1][0]
            if self._total > last_defined:
                steps_passed = (self._total - last_defined) // self.post_interval
                for i in range(1, int(steps_passed) + 1):
                    ms = last_defined + i * self.post_interval
                    if ms not in self._fired_milestones and self._total >= ms:
                        self._fired_milestones.add(ms)
                        out.append((self.post_count, ms))
        return out

    def _fire(self, count: int, milestone: int) -> None:
        threading.Thread(
            target=self._fire_worker, args=(count, milestone),
            daemon=True, name=f"like-rain-{milestone}"
        ).start()

    def _fire_worker(self, count: int, milestone: int) -> None:
        BUS.publish("like_milestone", milestone=milestone, tnt=count)
        human = f"{milestone // 1000}k" if milestone >= 1000 else str(milestone)
        msg = (
            '["",'
            '{"text":"[","color":"dark_gray"},'
            f'{{"text":"{human} BEGENI","color":"red","bold":true}},'
            '{"text":"] ","color":"dark_gray"},'
            f'{{"text":"{count} TNT yagiyor","color":"gold","bold":true}}'
            ']'
        )
        self.rcon.cmd(f'tellraw @a {msg}')
        self.rcon.cmd(
            f'title @a title {{"text":"{human} BEGENI","color":"red"}}'
        )
        self.rcon.cmd(
            f'title @a subtitle {{"text":"{count} TNT yagmuru","color":"gold"}}'
        )
        for _ in range(count):
            self.tnt.fire("rain_single", source=f"likes:{human}:")
            time.sleep(0.08 + random.random() * 0.12)

    @property
    def total(self) -> int:
        return self._total
