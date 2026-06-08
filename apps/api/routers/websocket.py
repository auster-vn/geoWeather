import asyncio
import json
import logging
import h3
from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..core.redis import get_redis
from ..core.telemetry import active_websocket_connections

logger = logging.getLogger(__name__)
router = APIRouter()

class ConnectionManager:
    def __init__(self):
        # Maps h3_index -> set of WebSocket connections
        self.subscriptions: dict[str, set[WebSocket]] = {}

    async def subscribe(self, ws: WebSocket, h3_cells: list[str]):
        for cell in h3_cells:
            self.subscriptions.setdefault(cell, set()).add(ws)
        active_websocket_connections.set(sum(len(s) for s in self.subscriptions.values()))

    def unsubscribe(self, ws: WebSocket, h3_cells: list[str]):
        for cell in h3_cells:
            if cell in self.subscriptions:
                self.subscriptions[cell].discard(ws)
                if not self.subscriptions[cell]:
                    del self.subscriptions[cell]
        active_websocket_connections.set(sum(len(s) for s in self.subscriptions.values()))

    async def broadcast_update(self, h3_index: str, data: dict):
        if h3_index not in self.subscriptions:
            return
            
        dead = set()
        for ws in self.subscriptions[h3_index]:
            try:
                await ws.send_json(data)
            except Exception:
                dead.add(ws)
                
        if dead:
            for ws in dead:
                self.unsubscribe(ws, [h3_index])

manager = ConnectionManager()

@router.websocket("/weather/{h3_index}")
async def weather_stream(websocket: WebSocket, h3_index: str):
    """
    Subscribes the websocket client to real-time aggregates for a specific H3 cell
    and its parents (for zoomed-out views).
    """
    await websocket.accept()
    
    # Calculate parent cells for zoom-out support
    parent_cells = []
    try:
        # Resolve parents up to resolution 2
        for r in [4, 3, 2]:
            try:
                parent = h3.cell_to_parent(h3_index, r)
                parent_cells.append(parent)
            except Exception:
                pass
    except Exception as e:
        logger.warning(f"Error resolving parent cells for {h3_index}: {e}")

    all_cells = [h3_index, "global"] + parent_cells
    await manager.subscribe(websocket, all_cells)
    logger.info(f"WebSocket client connected to H3: {h3_index} (listening on cells: {all_cells})")

    try:
        while True:
            # Maintain connection and listen for pings from the browser
            data = await websocket.receive_text()
            if data == "ping":
                await websocket.send_text("pong")
    except WebSocketDisconnect:
        logger.info(f"WebSocket client disconnected from H3: {h3_index}")
    finally:
        manager.unsubscribe(websocket, all_cells)

async def redis_listener():
    """
    Background listener task:
    Subscribes to Redis channels and broadcasts incoming aggregates to WebSockets.
    Uses a single persistent connection with socket_timeout to avoid "Too many connections".
    """
    await asyncio.sleep(5)  # Wait for Redis to initialize
    while True:
        pubsub = None
        try:
            redis = await get_redis()
            pubsub = redis.pubsub()
            await pubsub.psubscribe("weather:h3:*")
            logger.info("Subscribed to Redis pub/sub: weather:h3:*")

            while True:
                # get_message with timeout avoids blocking forever and avoids
                # creating a new connection on every keep-alive cycle.
                message = await pubsub.get_message(
                    ignore_subscribe_messages=True, timeout=10.0
                )
                if message and message["type"] == "pmessage":
                    try:
                        channel_parts = message["channel"].split(":")
                        h3_cell = channel_parts[-1]
                        data = json.loads(message["data"])
                        await manager.broadcast_update(h3_cell, data)
                        await manager.broadcast_update("global", data)
                    except Exception as e:
                        logger.error(f"Error broadcasting WebSocket message: {e}")
                # Yield control to the event loop between polls
                await asyncio.sleep(0)

        except asyncio.CancelledError:
            logger.info("Redis pub/sub listener cancelled.")
            break
        except Exception as e:
            logger.error(f"Redis Pub/Sub listener encountered error: {e}. Reconnecting in 5s...")
            await asyncio.sleep(5)
        finally:
            if pubsub:
                try:
                    await pubsub.punsubscribe("weather:h3:*")
                    await pubsub.aclose()
                except Exception:
                    pass
