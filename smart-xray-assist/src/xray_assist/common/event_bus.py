"""In-process pub/sub event bus for the Phase 1 MVP.

tech-stack §10 specifies ZeroMQ (with explicit HWM) + multiprocessing Queue for
the real pipeline; ZeroMQ PUB/SUB drops silently at HWM, so the production bus
must surface drops. For the single-process MVP this in-process bus carries
DepthSummary / RespirationState / ExposureRecommendation / system.error events
between services with the same publish/subscribe contract, so swapping in a
ZeroMQ/NNG transport later is a bus implementation change, not a service change.

Bounded per-subscriber queues make backpressure/drops explicit and counted —
mirroring the HWM monitoring the production transport requires."""

from __future__ import annotations

import queue
import threading
from collections import defaultdict
from typing import Any, Callable

Handler = Callable[[dict[str, Any]], None]


class EventBus:
    def __init__(self, max_queue: int = 256) -> None:
        self._subscribers: dict[str, list[tuple[Handler, queue.Queue]]] = defaultdict(list)
        self._lock = threading.Lock()
        self._max_queue = max_queue
        self.dropped: dict[str, int] = defaultdict(int)  # topic -> drop count (HWM analog)

    def subscribe(self, topic: str, handler: Handler) -> None:
        with self._lock:
            self._subscribers[topic].append((handler, queue.Queue(self._max_queue)))

    def publish(self, topic: str, message: dict[str, Any]) -> None:
        """Synchronous fan-out. On a full subscriber queue the message is dropped
        and counted (never blocks the real-time producer)."""
        with self._lock:
            subs = list(self._subscribers.get(topic, ()))
        for handler, q in subs:
            try:
                q.put_nowait(message)
            except queue.Full:
                self.dropped[topic] += 1
                continue
            try:
                handler(q.get_nowait())
            except Exception:  # noqa: BLE001 - a bad subscriber must not kill the bus
                pass

    def drop_count(self, topic: str | None = None) -> int:
        if topic is None:
            return sum(self.dropped.values())
        return self.dropped.get(topic, 0)
