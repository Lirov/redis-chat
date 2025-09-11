import redis
from passlib.context import CryptContext
from .config import settings

pwd = CryptContext(schemes=["bcrypt"], deprecated="auto")
r = redis.Redis.from_url(str(settings.REDIS_URL), decode_responses=True)


def _k(u: str) -> str:
    return f"user:{u}"


def create_user(username: str, password: str) -> bool:
    if r.exists(_k(username)):
        return False
    r.hset(_k(username), mapping={"ph": pwd.hash(password)})
    return True


def verify_user(username: str, password: str) -> bool:
    if not r.exists(_k(username)):
        return False
    return pwd.verify(password, r.hget(_k(username), "ph"))
