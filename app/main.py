import asyncio
import json
import contextlib
from typing import List
from fastapi.responses import HTMLResponse
import time

from .security import create_access_token, decode_token
from .users import create_user, verify_user


from fastapi import (
    FastAPI,
    WebSocket,
    WebSocketDisconnect,
    Query,
    HTTPException,
)
from fastapi.middleware.cors import CORSMiddleware
from redis.asyncio.client import PubSub

from .config import settings
from .redis_conn import redis
from .schemas import ChatOut, HistoryItem
from .rate_limit import allow_message
from pydantic import BaseModel

app = FastAPI(title="Redis Real-Time Chat")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class Register(BaseModel):
    username: str
    password: str


class Login(BaseModel):
    username: str
    password: str


@app.post("/auth/register")
async def auth_register(b: Register):
    if not create_user(b.username, b.password):
        raise HTTPException(400, "username exists")
    return {"ok": True}


@app.post("/auth/login")
async def auth_login(b: Login):
    if not verify_user(b.username, b.password):
        raise HTTPException(401, "invalid creds")
    return {"access_token": create_access_token(b.username), "token_type": "bearer"}


# -- Helpers --
async def _join_room(username: str, room: str):
    await redis.sadd(ROOMS_SET, room)
    await redis.sadd(members_key(room), username)
    # broadcast join (not persisted in history)
    await redis.publish(
        room_channel(room),
        json.dumps(
            {
                "type": "system",
                "room": room,
                "username": username,
                "event": "join",
                "ts": int(time.time()),
            }
        ),
    )


async def _leave_room(username: str, room: str):
    await redis.srem(members_key(room), username)
    if not await redis.scard(members_key(room)):
        await redis.srem(ROOMS_SET, room)
        await redis.delete(members_key(room))
    await redis.publish(
        room_channel(room),
        json.dumps(
            {
                "type": "system",
                "room": room,
                "username": username,
                "event": "leave",
                "ts": int(time.time()),
            }
        ),
    )


async def _maybe_bump_history_ttl(room: str):
    if settings.HISTORY_TTL_SECONDS > 0:
        await redis.expire(history_key(room), settings.HISTORY_TTL_SECONDS)


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
    token = ws.query_params.get("token")
    username = None
    if token:
        try:
            username = decode_token(token)
        except ValueError:
            await ws.close(code=1008)  # policy violation
            return
    elif settings.ALLOW_ANON_WS:
        username = ws.query_params.get("username") or "anon"
    else:
        await ws.close(code=1008)
        return
    await ws.accept()

    current_room = room
    await _join_room(username, current_room)

    pubsub: PubSub = redis.pubsub()
    await pubsub.subscribe(room_channel(current_room))

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
            history_key(current_room), 0, min(20, settings.CHAT_HISTORY_LIMIT) - 1
        )
        for h in reversed(hist):
            await ws.send_text(h)

        # main loop: receive from WS, publish to Redis + persist
        while True:
            raw = await ws.receive_text()
            # normalize payload
            try:
                obj = json.loads(raw)
            except Exception:
                obj = {"type": "message", "text": raw}

            msg_type = obj.get("type", "message")

            if msg_type == "switch":
                new_room = obj.get("room", "").strip()
                if not new_room:
                    continue  # ignore bad payload
                if new_room == current_room:
                    continue

                # leave old room
                await _leave_room(username, current_room)
                await pubsub.unsubscribe(room_channel(current_room))

                # join new room
                current_room = new_room
                await _join_room(username, current_room)
                await pubsub.subscribe(room_channel(current_room))

                # send recent history for the new room
                hist = await redis.lrange(
                    history_key(current_room),
                    0,
                    min(20, settings.CHAT_HISTORY_LIMIT) - 1,
                )
                for h in reversed(hist):
                    await ws.send_text(h)
                continue

            # default path: message
            text = obj.get("text", "")
            if not text:
                continue
            out = ChatOut(room=current_room, username=username, text=text)
            payload = out.model_dump_json()

            if msg_type == "message":
                # rate limit
                ok, rem = await allow_message(username, current_room)
                if not ok:
                    # inform only the sender; do not persist
                    await ws.send_text(
                        json.dumps(
                            {
                                "type": "rate_limit",
                                "room": current_room,
                                "username": username,
                                "msg": "Too many messages, slow down.",
                                "ts": int(time.time()),
                            }
                        )
                    )
                    continue

            await redis.publish(room_channel(current_room), payload)
            await redis.lpush(history_key(current_room), payload)
            await redis.ltrim(
                history_key(current_room), 0, settings.CHAT_HISTORY_LIMIT - 1
            )
            await _maybe_bump_history_ttl(current_room)

    except WebSocketDisconnect:
        pass
    finally:
        with contextlib.suppress(Exception):
            await _leave_room(username, current_room)
        with contextlib.suppress(Exception):
            await pubsub.unsubscribe(room_channel(current_room))
            await pubsub.close()
        reader_task.cancel()
        with contextlib.suppress(Exception):
            await reader_task
