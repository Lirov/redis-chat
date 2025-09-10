import json
import asyncio
import websockets

async def two_party_chat(room="pytest2"):
    uri_a = f"ws://localhost:8000/ws/{room}?username=alice"
    uri_b = f"ws://localhost:8000/ws/{room}?username=bob"
    async with websockets.connect(uri_a) as wa, websockets.connect(uri_b) as wb:
        await wa.send(json.dumps({"text": "hi from alice"}))
        # alice receives her own message too
        _ = await wa.recv()
        # bob should get it
        msg = await wb.recv()
        obj = json.loads(msg)
        assert obj["text"] == "hi from alice"
        assert obj["username"] == "alice"
        assert obj["room"] == room

def test_two_party_chat():
    asyncio.run(two_party_chat())
