"""Download speed and time remaining, for the wizard's progress line."""

import time
from collections import deque
from collections.abc import Callable


class SpeedMeter:
    """Download speed over the last few seconds, and the time left at that speed."""

    def __init__(self, window: float = 5.0, clock: Callable[[], float] = time.monotonic) -> None:
        self._window = window
        self._clock = clock
        self._samples: deque[tuple[float, int]] = deque()

    def add(self, completed: int) -> None:
        now = self._clock()
        self._samples.append((now, completed))
        while len(self._samples) > 2 and now - self._samples[1][0] >= self._window:
            self._samples.popleft()

    def speed(self) -> float | None:
        """Bytes per second, 0 when nothing arrived for a whole window, None before two samples."""
        if len(self._samples) < 2:
            return None
        now = self._clock()
        (t0, c0), (t1, c1) = self._samples[0], self._samples[-1]
        if now - t1 >= self._window:
            return 0.0
        elapsed = t1 - t0
        return (c1 - c0) / elapsed if elapsed > 0 else None

    def eta(self, remaining: int) -> float | None:
        speed = self.speed()
        return remaining / speed if speed else None
