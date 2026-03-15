import time
from threading import Lock


class Metrics:
    def __init__(self):
        self.packets_count = 0
        self.bytes_count = 0
        self.last_reset = time.monotonic()
        self._lock = Lock()
        self._current_pps = 0
        self._current_bps = 0

    def add(self, num_bytes: int):
        with self._lock:
            # Check and reset window BEFORE adding new data
            self._update_if_needed()
            self.packets_count += 1
            self.bytes_count += num_bytes

    def _update_if_needed(self):
        # Assumes lock is held
        now = time.monotonic()
        dt = now - self.last_reset
        if dt >= 1.0:
            self._current_pps = int(self.packets_count / dt)
            self._current_bps = int(self.bytes_count / dt)
            self.packets_count = 0
            self.bytes_count = 0
            self.last_reset = now
            return True
        return False

    def get_current(self):
        with self._lock:
            self._update_if_needed()
            return self._current_pps, self._current_bps


metrics = Metrics()
