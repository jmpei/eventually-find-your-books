import asyncio
from app import storage, recommender, cache

def _compute(user_id: str, ratings, limit: int = 10):
    return recommender.recommend_for_user(user_id, ratings, top_k=limit)

def compute_recommendations_for_user_sync(user_id: str, limit: int = 10):
    ratings = storage.fetch_all_ratings()
    return _compute(user_id, ratings, limit)

async def get_recommendations(user_id: str, limit: int = 10):
    # Try cache first
    cached = await cache.get_cached_recommendations(user_id)
    if cached:
        return cached[:limit]

    # Compute (run sync in threadpool)
    loop = asyncio.get_running_loop()
    recs = await loop.run_in_executor(None, compute_recommendations_for_user_sync, user_id, limit)
    await cache.set_cached_recommendations(user_id, recs)
    return recs

async def refresh_all_recommendations():
    # Compute and pre-warm cache for all users — fetch ratings ONCE and reuse
    loop = asyncio.get_running_loop()
    ratings = await loop.run_in_executor(None, storage.fetch_all_ratings)
    users = list({r['user_id'] for r in ratings})
    tasks = [loop.run_in_executor(None, _compute, u, ratings, 10) for u in users]
    results = await asyncio.gather(*tasks)
    for u, recs in zip(users, results):
        await cache.set_cached_recommendations(u, recs)
    return len(users)
