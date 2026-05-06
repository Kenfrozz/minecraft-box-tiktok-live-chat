"""Paylasimli event bus - action/like/gift eventlerini OBS overlay server'a yayinlar."""
import queue
import threading
import time
from collections import deque


class OverlayBus:
    def __init__(self, history_size: int = 30) -> None:
        self._subscribers: list[queue.Queue] = []
        self._lock = threading.Lock()
        self._history: deque = deque(maxlen=history_size)
        self._state: dict = {
            "likes_total": 0,
            "next_threshold": None,
            "last_action": None,
        }

    def publish(self, event_type: str, **data) -> None:
        payload = {"type": event_type, "ts": time.time(), **data}
        with self._lock:
            self._history.append(payload)
            if event_type == "action":
                self._state["last_action"] = payload
            elif event_type == "likes":
                self._state["likes_total"] = payload.get("total", 0)
                self._state["next_threshold"] = payload.get("next_threshold")
            subs = list(self._subscribers)
        for q in subs:
            try:
                q.put_nowait(payload)
            except queue.Full:
                pass

    def subscribe(self) -> queue.Queue:
        q: queue.Queue = queue.Queue(maxsize=200)
        with self._lock:
            self._subscribers.append(q)
            snapshot = list(self._history)
        for ev in snapshot[-10:]:
            try:
                q.put_nowait(ev)
            except queue.Full:
                break
        return q

    def unsubscribe(self, q: queue.Queue) -> None:
        with self._lock:
            try:
                self._subscribers.remove(q)
            except ValueError:
                pass

    def state(self) -> dict:
        with self._lock:
            return dict(self._state)


BUS = OverlayBus()
