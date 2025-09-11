import asyncio
import json
import contextlib
from typing import List
from fastapi.responses import HTMLResponse
import time

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio.client import PubSub

from .config import settings
from .redis_conn import redis
from .schemas import ChatIn, ChatOut, HistoryItem

app = FastAPI(title="Redis Real-Time Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def room_channel(room: str) -> str:
    return f"room:{room}"


def history_key(room: str) -> str:
    return f"history:{room}"


def members_key(room: str) -> str:
    return f"members:{room}"


ROOMS_SET = "rooms:set"

@app.get("/", response_class=HTMLResponse)
async def index():
    return """
<!doctype html>
<html>
<head>
  <meta charset="utf-8"/>
  <title>Redis Chat</title>
  <style>
    body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 20px; }
    #log { border: 1px solid #ddd; padding: 10px; height: 300px; overflow: auto; }
    input, button { font-size: 14px; padding: 6px 8px; }
    .sys { color: #666; }
    .msg { margin: 2px 0; }
  </style>
</head>
<body>
  <h2>Redis Chat</h2>
  <div>
    <label>Room <input id="room" value="lobby"></label>
    <label>Username <input id="user" value="alice"></label>
    <button id="connect">Connect</button>
    <button id="disconnect" disabled>Disconnect</button>
  </div>
  <p>
    <button id="refreshRooms">List rooms</button>
    <button id="refreshPresence">Who’s here?</button>
  </p>
  <pre id="meta"></pre>
  <div id="log"></div>
  <p>
    <input id="text" placeholder="Type message…" size="60">
    <button id="send" disabled>Send</button>
  </p>

<script>
let ws;

function line(html, cls="msg") {
  const div = document.createElement("div");
  div.className = cls;
  div.innerHTML = html;
  document.getElementById("log").appendChild(div);
  document.getElementById("log").scrollTop = 999999;
}

function enableConnected(state) {
  document.getElementById("send").disabled = !state;
  document.getElementById("disconnect").disabled = !state;
  document.getElementById("connect").disabled = state;
}

document.getElementById("connect").onclick = async () => {
  const room = document.getElementById("room").value.trim();
  const user = document.getElementById("user").value.trim();
  if (!room || !user) return alert("room + username required");
  ws = new WebSocket(`ws://${location.host}/ws/${encodeURIComponent(room)}?username=${encodeURIComponent(user)}`);
  ws.addEventListener("open", () => {
    line(`<em>connected as <b>${user}</b> in <b>${room}</b></em>`, "sys");
    enableConnected(true);
  });
  ws.addEventListener("close", () => {
    line(`<em>disconnected</em>`, "sys");
    enableConnected(false);
  });
  ws.addEventListener("message", (e) => {
    const obj = JSON.parse(e.data);
    if (obj.type === "system") {
      line(`<em>${obj.username} ${obj.event}s</em>`, "sys");
    } else {
      const t = new Date(obj.ts * 1000).toLocaleTimeString();
      line(`[${t}] <b>${obj.username}</b>: ${obj.text}`);
    }
  });
};

document.getElementById("disconnect").onclick = () => {
  if (ws && ws.readyState <= 1) ws.close();
};

document.getElementById("send").onclick = () => {
  if (!ws || ws.readyState !== WebSocket.OPEN) return;
  const text = document.getElementById("text").value;
  if (text.trim()) ws.send(JSON.stringify({ text }));
  document.getElementById("text").value = "";
};

document.getElementById("text").addEventListener("keydown", (e) => {
  if (e.key === "Enter") document.getElementById("send").click();
});

document.getElementById("refreshRooms").onclick = async () => {
  const r = await fetch("/rooms").then(r => r.json());
  document.getElementById("meta").textContent = "rooms: " + JSON.stringify(r.rooms);
};

document.getElementById("refreshPresence").onclick = async () => {
  const room = document.getElementById("room").value.trim();
  if (!room) return;
  const r = await fetch(`/presence/${encodeURIComponent(room)}`).then(r => r.json());
  document.getElementById("meta").textContent = `presence(${room}): ` + JSON.stringify(r);
};
</script>
</body>
</html>
    """


# --- HTTP: get recent history ---


@app.get("/history/{room}", response_model=List[HistoryItem])
async def get_history(room: str, limit: int = Query(20, ge=1, le=200)):
    msgs = await redis.lrange(history_key(room), 0, limit - 1)  # latest first
    # stored as JSON lines

    result = [HistoryItem(**json.loads(m)) for m in msgs]
    return result[::-1]  # return oldest->newest for UI


# --- HTTP: list rooms ---

@app.get("/presence/{room}")
async def presence(room: str):
    members = await redis.smembers(members_key(room))
    return {"room": room, "count": len(members), "members": sorted(members)}


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

    await redis.publish(
    room_channel(room),
    json.dumps({
        "type": "system", "room": room, "username": username,
        "event": "join", "ts": int(time.time())
    })
)

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

        hist = await redis.lrange(
            history_key(room), 0, min(20, settings.CHAT_HISTORY_LIMIT) - 1
        )
        for h in reversed(hist):
            await ws.send_text(h)
        # main loop: receive from WS, publish to Redis + persist

        while True:
            raw = await ws.receive_text()
            try:
                incoming = (
                    ChatIn.model_validate_json(raw)
                    if raw.strip().startswith("{")
                    else ChatIn(text=raw)
                )
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
            await redis.publish(
                room_channel(room),
                json.dumps({
                    "type": "system", "room": room, "username": username,
                    "event": "leave", "ts": int(time.time())
                })
            )
            await pubsub.unsubscribe(room_channel(room))
            await pubsub.close()
        reader_task.cancel()
        with contextlib.suppress(Exception):
            await reader_task
