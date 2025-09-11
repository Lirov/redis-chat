from prometheus_client import (
    Counter,
    Gauge,
    Histogram,
)

WS_CONNECTIONS = Gauge("chat_ws_connections", "Active WebSocket connections")
MSGS_PUBLISHED = Counter("chat_messages_published_total", "Messages published")
RATE_LIMIT_BLOCKS = Counter(
    "chat_rate_limit_blocked_total", "Messages blocked by rate limit"
)
PUBLISH_LATENCY = Histogram("chat_publish_latency_seconds", "Publish+persist latency")
