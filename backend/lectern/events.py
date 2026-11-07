"""In-memory publish/subscribe for Server-Sent Events, one channel per lesson."""

from __future__ import annotations

import asyncio
from collections import defaultdict


class EventBroker:
    def __init__(self) -> None:
        self._subscribers: dict[str, set[asyncio.Queue]] = defaultdict(set)

    def subscribe(self, lesson_id: str) -> asyncio.Queue:
        queue: asyncio.Queue = asyncio.Queue(maxsize=500)
        self._subscribers[lesson_id].add(queue)
        return queue

    def unsubscribe(self, lesson_id: str, queue: asyncio.Queue) -> None:
        self._subscribers[lesson_id].discard(queue)
        if not self._subscribers[lesson_id]:
            self._subscribers.pop(lesson_id, None)

    def publish(self, lesson_id: str, event: str, data: dict) -> None:
        for queue in list(self._subscribers.get(lesson_id, ())):
            try:
                queue.put_nowait({"event": event, "data": data})
            except asyncio.QueueFull:  # a stalled browser tab must not block the pipeline
                pass
