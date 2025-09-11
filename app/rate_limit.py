import time
from .config import settings
from .redis_conn import redis

# returns (allowed:int, tokens_remaining:float)
LUA_BUCKET = """
local key=KEYS[1]
local capacity=tonumber(ARGV[1])
local refill=tonumber(ARGV[2])   -- tokens per second
local now=tonumber(ARGV[3])      -- ms
local tokens=0
local ts=now
local last_ts=redis.call('HGET', key, 'ts')
if last_ts then
  ts=tonumber(last_ts)
  local last_tokens=tonumber(redis.call('HGET', key, 'tokens'))
  local delta=(now - ts)/1000.0
  tokens=math.min(capacity, last_tokens + delta*refill)
else
  tokens=capacity
end
local allowed=0
if tokens >= 1 then
  tokens=tokens-1
  allowed=1
end
redis.call('HSET', key, 'ts', now, 'tokens', tokens)
redis.call('PEXPIRE', key, math.max(1000, math.floor((capacity/refill)*1000))) -- gc
return {allowed, tokens}
"""


async def allow_message(username: str, room: str) -> tuple[bool, float]:
    key = f"rl:{room}:{username}"
    now_ms = int(time.time() * 1000)
    cap = settings.RATE_LIMIT_BURST
    refill = settings.RATE_LIMIT_TOKENS_PER_SEC
    allowed, rem = await redis.eval(LUA_BUCKET, 1, key, cap, refill, now_ms)
    return (allowed == 1), float(rem)
