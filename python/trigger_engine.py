"""Maps chat keywords and TikTok gifts to arena actions with per-user/global cooldowns."""
import time
from collections import defaultdict

from overlay_bus import BUS

BIG_GIFT_NAMES = {"Galaxy", "TikTok Universe", "Universe", "Sports Car", "Lion", "Train"}


class TriggerEngine:
    def __init__(self, triggers_cfg: dict, tnt_actions, effect_actions=None, rcon=None):
        self.keywords = triggers_cfg.get("keywords", {})
        gifts_cfg = triggers_cfg.get("gifts", {})
        self.gifts_by_name = gifts_cfg.get("by_name", {})
        self.gift_diamond_rules = gifts_cfg.get("by_diamond_count", [])
        self.rate_limits = triggers_cfg.get("rate_limits", {})
        self.tnt = tnt_actions
        self.effects = effect_actions
        self.rcon = rcon
        self._user_cooldowns: dict[str, dict[str, float]] = defaultdict(dict)
        self._last_global: dict[str, float] = defaultdict(float)

    def _dispatch(self, rule: dict, username: str) -> None:
        action = rule.get("action")
        if action == "tnt":
            self.tnt.fire(rule["tier"], source=f"chat:{username}")
        elif action == "effect" and self.effects:
            self.effects.apply(rule["name"], source_user=username)

    def handle_comment(self, username: str, comment: str) -> None:
        text = (comment or "").strip().lower()
        rule = self.keywords.get(text)
        if rule is None:
            return
        now = time.time()
        action = rule.get("action", "default")
        per_user = float(rule.get("cooldown_per_user_sec", 3))
        global_cd = float(rule.get("global_cooldown_sec", 0.3))
        last = self._user_cooldowns[username].get(text, 0)
        if now - last < per_user:
            return
        if now - self._last_global[action] < global_cd:
            return
        self._user_cooldowns[username][text] = now
        self._last_global[action] = now
        self._dispatch(rule, username)
        print(f"[trigger] chat '{text}' -> {rule.get('action')}/{rule.get('tier') or rule.get('name')} (by {username})")

    def handle_gift(self, username: str, gift_name: str, diamonds: int, repeat_count: int) -> None:
        count = max(1, int(repeat_count or 1))
        total_coins = int(diamonds or 0) * count
        safe_user = (username or "anonim").replace(" ", "_")
        BUS.publish("gift_raw", user=safe_user, gift=gift_name,
                    diamonds=int(diamonds or 0), repeat=count, total_coins=total_coins)
        if gift_name in BIG_GIFT_NAMES or (diamonds or 0) >= 500:
            BUS.publish("big_gift", user=safe_user, gift=gift_name,
                        diamonds=int(diamonds or 0), repeat=count)
        if self.rcon and total_coins > 0:
            self.rcon.cmd(f'arena gift {safe_user} {total_coins}')
        # Her hediye yeni bir yardimci bot cagirir (gondericinin adiyla)
        if self.rcon:
            self.rcon.cmd(f'arena bot summon {safe_user}')

        rule = self.gifts_by_name.get(gift_name)
        if rule is None:
            for r in self.gift_diamond_rules:
                if r["min"] <= diamonds <= r["max"]:
                    rule = dict(r)
                    rule.setdefault("action", "tnt")
                    break
        if not rule:
            return
        action = rule.get("action")
        if action == "tnt":
            for _ in range(count):
                self.tnt.fire(rule["tier"], source=f"gift:{username}:{gift_name}")
        elif action == "effect" and self.effects:
            for _ in range(count):
                self.effects.apply(rule["name"], source_user=username)
        print(f"[trigger] gift '{gift_name}' x{count} ({total_coins} coin) -> {action}/{rule.get('tier') or rule.get('name')} (by {username})")
