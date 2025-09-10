import os, httpx, asyncio, json, time

BASE = os.getenv("BASE_URL", "http://localhost:8000")

async def _post_msg(room: str, username: str, text: str):
    import websockets
    uri = f"ws://localhost:8000/ws/{room}?username={username}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"text": text}))
        # receive echo of our own message (published back)
        _ = await ws.recv()

def test_rooms_and_history_event_loop():
    # run an asyncio subtask inside sync pytest for simplicity
    asyncio.run(_post_msg("pytest", "alice", "hello-redis"))

    # history endpoint
    r = httpx.get(f"{BASE}/history/pytest?limit=5")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert data[-1]["text"].startswith("hello-redis")
