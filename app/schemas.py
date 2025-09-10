from pydantic import BaseModel, Field
from typing import Literal
import time


class ChatIn(BaseModel):
    text: str = Field(min_length=1, max_length=2000)


class ChatOut(BaseModel):
    type: Literal["message"] = "message"
    room: str
    username: str
    text: str
    ts: int = Field(default_factory=lambda: int(time.time()))


class HistoryItem(BaseModel):
    username: str
    text: str
    ts: int
