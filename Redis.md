## What is the Redis part here?

### At connection

- SADD rooms:set <room> — declare the room exists.

- SADD members:{room} <username> — mark presence.

- SUBSCRIBE room:{room} — open a Pub/Sub channel for this socket.

- LRANGE history:{room} — fetch recent messages to seed the client.

### When sending a message

- Client → server via WebSocket.

- Server PUBLISH room:{room} <json> — Redis fans this out immediately to all current subscribers (all app instances).

- Server LPUSH history:{room} <json> + LTRIM ... 0 N-1 — persist recent history.

- (optional) EXPIRE history:{room} <ttl> — age out old/inactive rooms.

### When switching rooms

- SREM members:{old} + PUBLISH a system leave.

- UNSUBSCRIBE room:{old}; SUBSCRIBE room:{new}.

- SADD members:{new} + PUBLISH a system join.

- LRANGE history:{new} — send recent history to the client.

### At disconnect

- SREM members:{room}; if empty, SREM rooms:set and DEL members:{room}.

- PUBLISH a system leave.

- UNSUBSCRIBE channel; close Pub/Sub.

### Key types in use

- Pub/Sub channels: room:{name} → real-time broadcast (ephemeral).

- List: history:{room} → short persisted buffer for context.

- Set: members:{room} → presence; rooms:set → all rooms.

### Why Pub/Sub + List together?
Pub/Sub gives instant fan-out but no storage; List gives a recent backlog for late joiners.