from __future__ import annotations

import asyncio
import json
from typing import Any


class EventBroadcaster:
    """Manajer Server-Sent Events (SSE) untuk broadcast sinyal realtime ke Web Dashboard."""

    def __init__(self) -> None:
        self._subscribers: set[tuple[asyncio.AbstractEventLoop, asyncio.Queue[str]]] = set()

    async def subscribe(self) -> asyncio.Queue[str]:
        loop = asyncio.get_running_loop()
        queue: asyncio.Queue[str] = asyncio.Queue(maxsize=100)
        self._subscribers.add((loop, queue))
        return queue

    def unsubscribe(self, queue: asyncio.Queue[str]) -> None:
        self._subscribers = {pair for pair in self._subscribers if pair[1] is not queue}

    def broadcast(self, event_type: str, data: dict[str, Any] | None = None) -> None:
        """Kirim event ke seluruh klien browser yang terhubung secara thread-safe."""
        if not self._subscribers:
            return

        payload = json.dumps({"type": event_type, "data": data or {}})
        for loop, q in list(self._subscribers):
            try:
                if loop.is_closed():
                    continue
                loop.call_soon_threadsafe(q.put_nowait, payload)
            except Exception:
                pass


broadcaster = EventBroadcaster()
