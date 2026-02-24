"""
Unit Tests – Recommender Logic
================================
Tests the HybridRecommenderService recommend() method in isolation:
mood filtering, top-k limiting, cold-start users, popularity fallback,
and output schema validation.
"""

import pytest
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────────────────────────
# Helpers
# ──────────────────────────────────────────────────────────────────
FAKE_MOVIES = [
    {
        "id": str(i),
        "title": f"Movie {i}",
        "genres": ["Comedy"] if i % 2 == 0 else ["Action"],
        "mood": "happy" if i % 2 == 0 else "angry",
        "rating": str(round(3 + (i % 30) / 10, 1)),
        "year": 2020 + (i % 5),
        "views": 1000 * i,
        "description": f"Desc {i}",
        "poster": f"https://example.com/{i}.jpg",
        "posterUrl": f"https://example.com/{i}.jpg",
        "backdropUrl": "",
        "trailerUrl": "",
        "videoUrl": "",
        "duration": "2h",
        "language": "English",
        "category": "popular",
    }
    for i in range(1, 51)
]


@pytest.fixture
def svc(fake_mappings):
    """Set up a real HybridRecommenderService with mocked movie catalogue."""
    from services.hybrid_recommender_service import get_hybrid_recommender
    s = get_hybrid_recommender()
    s.set_movie_db(FAKE_MOVIES)
    return s


# ──────────────────────────────────────────────────────────────────
# 1. Returns exactly top_k results
# ──────────────────────────────────────────────────────────────────
def test_recommend_returns_top_k(svc):
    results = svc.recommend("user_1", "happy", top_k=5)
    assert len(results) == 5, f"Expected 5, got {len(results)}"


# ──────────────────────────────────────────────────────────────────
# 2. Every result has required fields
# ──────────────────────────────────────────────────────────────────
REQUIRED_FIELDS = {"id", "title", "genres", "_recommended_rank"}

def test_recommend_result_schema(svc):
    results = svc.recommend("user_1", "happy", top_k=3)
    for r in results:
        missing = REQUIRED_FIELDS - set(r.keys())
        assert not missing, f"Missing fields: {missing}"


# ──────────────────────────────────────────────────────────────────
# 3. Ranks are sequential starting at 1
# ──────────────────────────────────────────────────────────────────
def test_recommend_ranks_sequential(svc):
    results = svc.recommend("user_1", "happy", top_k=5)
    ranks = [r.get("_recommended_rank") for r in results]
    assert ranks == list(range(1, 6)), f"Ranks wrong: {ranks}"


# ──────────────────────────────────────────────────────────────────
# 4. Cold-start user (not in mappings) still gets results
# ──────────────────────────────────────────────────────────────────
def test_cold_start_user_gets_results(svc):
    results = svc.recommend("brand_new_user_xyz", "happy", top_k=5)
    assert len(results) > 0, "Cold-start user got no recommendations"


# ──────────────────────────────────────────────────────────────────
# 5. Unknown mood falls back to popularity-sorted results
# ──────────────────────────────────────────────────────────────────
def test_unknown_mood_returns_results(svc):
    results = svc.recommend("user_1", "totally_invalid_mood", top_k=5)
    assert len(results) > 0, "Unknown mood produced no results"


# ──────────────────────────────────────────────────────────────────
# 6. top_k=1 returns exactly 1 movie
# ──────────────────────────────────────────────────────────────────
def test_top_k_one(svc):
    results = svc.recommend("user_1", "calm", top_k=1)
    assert len(results) == 1


# ──────────────────────────────────────────────────────────────────
# 7. Happy mood returns mostly Comedy/Family films (genre filter test)
# ──────────────────────────────────────────────────────────────────
def test_happy_mood_comedy_bias(svc):
    results = svc.recommend("user_1", "happy", top_k=10)
    comedy_count = sum(
        1 for r in results if "Comedy" in r.get("genres", [])
    )
    # At least half the results should be Comedy when mood is happy
    assert comedy_count >= len(results) // 2, (
        f"Expected Comedy bias for 'happy' mood, got {comedy_count}/{len(results)}"
    )


# ──────────────────────────────────────────────────────────────────
# 8. LRU cache: second identical call returns same results
# ──────────────────────────────────────────────────────────────────
def test_lru_cache_returns_same_results(svc):
    r1 = svc.recommend("user_cache_test", "happy", top_k=5)
    r2 = svc.recommend("user_cache_test", "happy", top_k=5)
    ids1 = [m["id"] for m in r1]
    ids2 = [m["id"] for m in r2]
    assert ids1 == ids2, "Cache returned different results for identical call"


# ──────────────────────────────────────────────────────────────────
# 9. Different moods can return different results
# ──────────────────────────────────────────────────────────────────
def test_different_moods_return_different_results(svc):
    happy_ids = {m["id"] for m in svc.recommend("user_1", "happy", top_k=10)}
    angry_ids = {m["id"] for m in svc.recommend("user_1", "angry", top_k=10)}
    # At least one result should differ (unless catalogue is tiny)
    assert happy_ids != angry_ids, (
        "Happy and Angry moods returned identical results"
    )


# ──────────────────────────────────────────────────────────────────
# 10. Concurrent calls don't raise exceptions (thread-safety smoke test)
# ──────────────────────────────────────────────────────────────────
def test_concurrent_recommend_threadsafe(svc):
    import threading
    errors = []

    def call():
        try:
            svc.recommend("user_1", "happy", top_k=5)
        except Exception as e:
            errors.append(str(e))

    threads = [threading.Thread(target=call) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=10)

    assert not errors, f"Thread-safety failures: {errors}"
