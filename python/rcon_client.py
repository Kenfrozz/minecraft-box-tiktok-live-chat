"""Thread-safe RCON wrapper with auto-reconnect."""
import threading
import time
from mcrcon import MCRcon


class RconClient:
    def __init__(self, host: str, port: int, password: str):
        self.host = host
        self.port = port
        self.password = password
        self._lock = threading.Lock()
        self._mc: MCRcon | None = None
        self._connect()

    def _connect(self) -> None:
        self._mc = MCRcon(self.host, self.password, self.port)
        self._mc.connect()

    def cmd(self, command: str) -> str | None:
        with self._lock:
            for attempt in range(2):
                try:
                    return self._mc.command(command)
                except Exception as e:
                    print(f"[rcon] retry ({attempt+1}/2): {e}")
                    try:
                        self._mc.disconnect()
                    except Exception:
                        pass
                    time.sleep(0.3)
                    try:
                        self._connect()
                    except Exception as e2:
                        print(f"[rcon] reconnect failed: {e2}")
            return None

    def close(self) -> None:
        with self._lock:
            try:
                if self._mc:
                    self._mc.disconnect()
            except Exception:
                pass
