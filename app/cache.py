import json
from redis import asyncio as aioredis
from app.config import settings

redis = None

async def get_redis():
    global redis
    if redis is None:
        redis = aioredis.from_url(settings.redis_url, decode_responses=True)
    return redis

async def get_cached_recommendations(user_id: str):
    r = await get_redis()
    key = f"reco:{user_id}"
    data = await r.get(key)
    if data:
        return json.loads(data)
    return None

async def set_cached_recommendations(user_id: str, recs, ttl=None):
    r = await get_redis()
    key = f"reco:{user_id}"
    await r.set(key, json.dumps(recs), ex=ttl or settings.cache_ttl_seconds)

async def invalidate_user_cache(user_id: str):
    r = await get_redis()
    await r.delete(f"reco:{user_id}")
