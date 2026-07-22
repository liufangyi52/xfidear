import asyncio
import json
import threading
from collections import defaultdict

from fastapi import WebSocket

from backend.models import UserPublic


class NotificationHub:
    def __init__(self) -> None:
        self._connections: dict[int, set[WebSocket]] = defaultdict(set)
        self._lock = threading.Lock()
        self._loop: asyncio.AbstractEventLoop | None = None

    async def connect(self, user: UserPublic, websocket: WebSocket) -> None:
        await websocket.accept()
        loop = asyncio.get_running_loop()
        with self._lock:
            self._loop = loop
            self._connections[user.id].add(websocket)

    def disconnect(self, user: UserPublic, websocket: WebSocket) -> None:
        with self._lock:
            sockets = self._connections.get(user.id)
            if not sockets:
                return
            sockets.discard(websocket)
            if not sockets:
                self._connections.pop(user.id, None)

    def publish_message(self, user_ids: list[int], payload: dict) -> None:
        with self._lock:
            loop = self._loop
        if not loop or not user_ids:
            return
        future = asyncio.run_coroutine_threadsafe(self._broadcast(user_ids, payload), loop)
        future.add_done_callback(lambda _future: None)

    async def _broadcast(self, user_ids: list[int], payload: dict) -> None:
        text = json.dumps(payload, ensure_ascii=False)
        sockets: list[tuple[int, WebSocket]] = []
        with self._lock:
            for user_id in user_ids:
                for websocket in self._connections.get(user_id, set()):
                    sockets.append((user_id, websocket))

        stale: list[tuple[int, WebSocket]] = []
        for user_id, websocket in sockets:
            try:
                await websocket.send_text(text)
            except Exception:
                stale.append((user_id, websocket))

        if stale:
            with self._lock:
                for user_id, websocket in stale:
                    sockets_for_user = self._connections.get(user_id)
                    if not sockets_for_user:
                        continue
                    sockets_for_user.discard(websocket)
                    if not sockets_for_user:
                        self._connections.pop(user_id, None)


notification_hub = NotificationHub()
