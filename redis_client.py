import os
import json
import asyncio
from datetime import datetime, timedelta, timezone
from dotenv import load_dotenv

load_dotenv()

REDIS_HOST = os.getenv("REDIS_HOST", "localhost")
REDIS_PORT = int(os.getenv("REDIS_PORT", 6379))
REDIS_PASSWORD = os.getenv("REDIS_PASSWORD", "")

class InMemoryRedis:
    """A thread-safe, async-compatible in-memory key-value emulator that mimics basic Redis behavior."""
    def __init__(self):
        self._store = {}
        self._lock = asyncio.Lock()
        print("💡 [REDIS FALLBACK] Initialized local In-Memory Redis Emulator.")

    def _prune_expired(self):
        now = datetime.now(timezone.utc)
        expired_keys = []
        for key, data in self._store.items():
            if data["expires_at"] and now > data["expires_at"]:
                expired_keys.append(key)
        for key in expired_keys:
            del self._store[key]

    async def ping(self):
        return True

    async def get(self, key: str):
        async with self._lock:
            self._prune_expired()
            item = self._store.get(key)
            if item:
                return item["value"]
            return None

    async def set(self, key: str, value: str, ex: int = None):
        async with self._lock:
            self._prune_expired()
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=ex) if ex else None
            self._store[key] = {
                "value": str(value),
                "expires_at": expires_at
            }
            return True

    async def delete(self, *keys):
        async with self._lock:
            count = 0
            for key in keys:
                if key in self._store:
                    del self._store[key]
                    count += 1
            return count

    async def keys(self, pattern: str = "*"):
        async with self._lock:
            self._prune_expired()
            # Simple conversion of redis style pattern '*' to python prefix checks
            prefix = pattern.replace("*", "")
            if not prefix:
                return list(self._store.keys())
            return [k for k in self._store.keys() if k.startswith(prefix)]

    async def exists(self, key: str):
        async with self._lock:
            self._prune_expired()
            return 1 if key in self._store else 0

# Client Singleton Setup
redis_client = None
is_mock_redis = True

async def init_redis():
    global redis_client, is_mock_redis
    try:
        import redis.asyncio as aioredis
        print(f"Connecting to Redis at {REDIS_HOST}:{REDIS_PORT}...")
        client = aioredis.Redis(
            host=REDIS_HOST,
            port=REDIS_PORT,
            password=REDIS_PASSWORD if REDIS_PASSWORD else None,
            decode_responses=True,
            socket_timeout=2.0
        )
        # Test connection
        await client.ping()
        redis_client = client
        is_mock_redis = False
        print("✅ Connected to local Redis server successfully.")
    except Exception as e:
        print(f"⚠️ Redis Connection failed ({e}). Reverting to In-Memory Redis Emulator.")
        redis_client = InMemoryRedis()
        is_mock_redis = True

# Helper functions to interface with the active client
async def get_redis():
    if redis_client is None:
        await init_redis()
    return redis_client
