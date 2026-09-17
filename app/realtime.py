import asyncio
import logging
import threading

logger = logging.getLogger("labmanager.realtime")

_loop: asyncio.AbstractEventLoop | None = None
_connections: set[asyncio.Queue] = set()
_lock = threading.Lock()


def set_loop(loop: asyncio.AbstractEventLoop | None):
    global _loop
    _loop = loop


def subscribe() -> asyncio.Queue:
    q: asyncio.Queue = asyncio.Queue(maxsize=256)
    with _lock:
        _connections.add(q)
    return q


def unsubscribe(q: asyncio.Queue):
    with _lock:
        _connections.discard(q)


def _put_event(q: asyncio.Queue, payload: dict):
    with _lock:
        active = q in _connections
    if not active:
        return
    try:
        q.put_nowait(payload)
    except asyncio.QueueFull:
        unsubscribe(q)


def publish(payload: dict):
    """Publish an event to every connected WebSocket client.

    Called from the MQTT ingestor thread; routes the payload onto the main
    event loop thread-safely.
    """
    loop = _loop
    if loop is None or loop.is_closed():
        return
    with _lock:
        targets = list(_connections)
    for q in targets:
        loop.call_soon_threadsafe(_put_event, q, payload)