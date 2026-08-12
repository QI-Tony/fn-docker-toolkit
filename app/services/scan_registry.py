from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from threading import Lock
from typing import Generic, TypeVar
from uuid import uuid4


T = TypeVar("T")


@dataclass
class _Entry(Generic[T]):
    value: T
    expires_at: datetime


class ScanRegistry(Generic[T]):
    """Small in-memory store that binds confirmation requests to scan results."""

    def __init__(self, ttl_minutes: int = 30) -> None:
        self._items: dict[str, _Entry[T]] = {}
        self._ttl = timedelta(minutes=ttl_minutes)
        self._lock = Lock()

    def put(self, value: T) -> str:
        now = datetime.now(timezone.utc)
        token = uuid4().hex
        with self._lock:
            self._purge(now)
            self._items[token] = _Entry(value, now + self._ttl)
        return token

    def take(self, token: str) -> T | None:
        now = datetime.now(timezone.utc)
        with self._lock:
            self._purge(now)
            entry = self._items.pop(token, None)
        return entry.value if entry else None

    def _purge(self, now: datetime) -> None:
        expired = [key for key, entry in self._items.items() if entry.expires_at <= now]
        for key in expired:
            del self._items[key]

