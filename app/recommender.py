from typing import Dict, List
import numpy as np
from collections import defaultdict

def build_matrix(ratings: List[Dict]):
    """
    Build user x item rating matrix and mappings.
    ratings: list of items with keys: user_id, book_id, rating
    """
    users = {}
    items = {}
    user_idx = 0
    item_idx = 0

    for r in ratings:
        u = r['user_id']
        i = r['book_id']
        if u not in users:
            users[u] = user_idx; user_idx += 1
        if i not in items:
            items[i] = item_idx; item_idx += 1

    mat = np.zeros((len(users), len(items)), dtype=float)
    for r in ratings:
        mat[users[r['user_id']], items[r['book_id']]] = float(r['rating'])
    return mat, users, items

def cosine_similarity_matrix(mat: np.ndarray):
    """Compute pairwise user-user cosine similarity."""
    norms = np.linalg.norm(mat, axis=1)
    # avoid div by zero:
    norms[norms == 0] = 1e-9
    sim = (mat @ mat.T) / (norms[:, None] * norms[None, :])
    return sim

def recommend_for_user(target_user: str, ratings: List[Dict], top_k=10) -> List[str]:
    """Return list of book_ids recommended for target_user."""
    if not ratings:
        return []

    mat, users_map, items_map = build_matrix(ratings)
    if target_user not in users_map:
        # cold user: fallback to most popular books
        return most_popular_items(ratings, top_k)

    sim = cosine_similarity_matrix(mat)
    u_idx = users_map[target_user]
    user_sims = sim[u_idx]

    # weighted sum of other users' ratings
    weighted = user_sims @ mat  # shape: (n_items,)
    # zero out items already rated by user
    user_rated = mat[u_idx] > 0
    weighted[user_rated] = -np.inf

    # get top indices
    top_indices = np.argsort(-weighted)[:top_k]
    # invert items_map to get book_ids
    inv_items = {v: k for k, v in items_map.items()}
    recs = []
    for idx in top_indices:
        if weighted[idx] == -np.inf:
            continue
        recs.append(inv_items[idx])
    return recs

def most_popular_items(ratings: List[Dict], top_k=10) -> List[str]:
    counts = {}
    sum_r = {}
    for r in ratings:
        w = r['book_id']
        counts[w] = counts.get(w, 0) + 1
        sum_r[w] = sum_r.get(w, 0) + float(r['rating'])
    # sort by count then avg rating
    items = sorted(counts.keys(), key=lambda w: (-counts[w], -sum_r[w]/counts[w]))
    return items[:top_k]
