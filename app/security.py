from datetime import datetime, timedelta, timezone
import jwt
from .config import settings

ALGO = "HS256"


def create_access_token(sub: str, minutes: int | None = None) -> str:
    exp = datetime.now(timezone.utc) + timedelta(
        minutes=minutes or settings.JWT_EXPIRES_MINUTES
    )
    return jwt.encode({"sub": sub, "exp": exp}, settings.JWT_SECRET, algorithm=ALGO)


def decode_token(token: str) -> str:
    try:
        payload = jwt.decode(token, settings.JWT_SECRET, algorithms=[ALGO])
        return payload["sub"]
    except jwt.ExpiredSignatureError as e:
        raise ValueError("expired") from e
    except jwt.InvalidTokenError as e:
        raise ValueError("invalid") from e
