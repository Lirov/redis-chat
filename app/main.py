import asyncio
import json
import contextlib
from typing import List

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio.client import PubSub

from .config import settings
from .redis_conn import redis
from .schemas import ChatIn, ChatOut, HistoryItem

app = FastAPI(title="Redis Real-Time Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"], allow_credentials=True,
    allow_methods=["*"], allow_headers=["*"],
)

def room_channel(room: str) -> str:
    return f"room:{room}"

def history_key(room: str) -> str:
    return f"history:{room}"

def members_key(room: str) -> str:
    return f"members:{room}"

ROOMS_SET = "rooms:set"

# --- HTTP: get recent history ---
@app.get("/history/{room}", response_model=List[HistoryItem])
async def get_history(room: str, limit: int = Query(20, ge=1, le=200)):
    msgs = await redis.lrange(history_key(room), 0, limit - 1)  # latest first
    # stored as JSON lines
    result = [HistoryItem(**json.loads(m)) for m in msgs]
    return result[::-1]  # return oldest->newest for UI

# --- HTTP: list rooms ---
@app.get("/rooms")
async def get_rooms():
    rooms = await redis.smembers(ROOMS_SET)
    return {"rooms": sorted(list(rooms))}

# --- WS: real-time chat ---
@app.websocket("/ws/{room}")
async def websocket_endpoint(ws: WebSocket, room: str):
    # simple query param auth: ?username=alice
    username = ws.query_params.get("username")
    if not username or len(username) > 32:
        await ws.close(code=1008)  # policy violation
        return

    await ws.accept()

    # Mark presence & room
    await redis.sadd(ROOMS_SET, room)
    await redis.sadd(members_key(room), username)

    pubsub: PubSub = redis.pubsub()
    await pubsub.subscribe(room_channel(room))

    # Background task to fan-in messages from Redis to this WS
    async def reader():
        try:
            async for msg in pubsub.listen():
                if msg["type"] != "message":
                    continue
                payload = msg["data"]  # string (decode_responses=True)
                await ws.send_text(payload)
        except Exception:
            # ws closed or redis closed; reader exits
            pass

    reader_task = asyncio.create_task(reader())

    try:
        # send last history on connect (optional UX)
        hist = await redis.lrange(history_key(room), 0, min(20, settings.CHAT_HISTORY_LIMIT) - 1)
        for h in reversed(hist):
            await ws.send_text(h)

        # main loop: receive from WS, publish to Redis + persist
        while True:
            raw = await ws.receive_text()
            try:
                incoming = ChatIn.model_validate_json(raw) if raw.strip().startswith("{") else ChatIn(text=raw)
            except Exception:
                # normalize bad payloads to plain text
                incoming = ChatIn(text=raw)

            out = ChatOut(room=room, username=username, text=incoming.text)
            payload = out.model_dump_json()

            # 1) publish to channel
            await redis.publish(room_channel(room), payload)

            # 2) write to history (LPUSH newest first) + trim
            await redis.lpush(history_key(room), payload)
            await redis.ltrim(history_key(room), 0, settings.CHAT_HISTORY_LIMIT - 1)

    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(Exception):
            await redis.srem(members_key(room), username)
            # optional: cleanup empty rooms
            if not await redis.scard(members_key(room)):
                await redis.srem(ROOMS_SET, room)
                await redis.delete(members_key(room))
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(room_channel(room))
            await pubsub.close()
        reader_task.cancel()
        with contextlib.suppress(Exception):
            await reader_task
