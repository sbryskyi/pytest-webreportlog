"""Event broadcasting service for SSE updates."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class EventBroadcaster:
    """Simple SSE broadcaster for session updates."""

    def __init__(self):
        self.channels: dict[int, set[asyncio.Queue]] = {}

    def subscribe(self, session_id: int) -> asyncio.Queue:
        """Subscribe to updates for a session."""
        queue: asyncio.Queue = asyncio.Queue()
        if session_id not in self.channels:
            self.channels[session_id] = set()
        self.channels[session_id].add(queue)
        return queue

    def unsubscribe(self, session_id: int, queue: asyncio.Queue):
        """Unsubscribe from session updates."""
        if session_id in self.channels:
            self.channels[session_id].discard(queue)
            if not self.channels[session_id]:
                del self.channels[session_id]

    async def broadcast(self, session_id: int, message: dict):
        """Broadcast update to all subscribers of a session."""
        if session_id in self.channels:
            dead_queues = set()
            for queue in self.channels[session_id]:
                try:
                    await queue.put(message)
                except Exception as e:
                    # Queue is full or closed, mark for cleanup
                    logger.warning(f"Failed to broadcast to queue: {e}")
                    dead_queues.add(queue)

            # Clean up dead queues
            for queue in dead_queues:
                self.channels[session_id].discard(queue)


# Global broadcaster instance
broadcaster = EventBroadcaster()
