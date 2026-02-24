"""
Unit Tests – Cold-Start Handling
=================================
A "cold-start" user has zero interaction history.
The recommender must still return valid, non-empty results
using the popularity/fallback path.
"""

import pytest


VALID_MOODS = ["happy", "sad", "angry", "calm", "neutral"]


@pytest.fixture(scope="module")
def svc():
    from services.hybrid_recommender_service import get_hybrid_recommender
    return get_hybrid_recommender()


# ──────────────────────────────────────────────────────────────────
# 1. Brand-new user ID not present in any mapping
# ──────────────────────────────────────────────────────────────────
def test_cold_start_user_non_empty(svc):
    results = svc.recommend("__cold_start_user__", "happy", top_k=5)
    assert len(results) >= 1, "Cold-start user returned 0 recommendations"


# ──────────────────────────────────────────────────────────────────
# 2. Cold-start results still have required fields
# ──────────────────────────────────────────────────────────────────
def test_cold_start_result_schema(svc):
    results = svc.recommend("__cold_start__", "happy", top_k=3)
    for r in results:
        assert "id" in r
        assert "title" in r


# ──────────────────────────────────────────────────────────────────
# 3. Cold-start across all moods – no crash
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mood", VALID_MOODS)
def test_cold_start_all_moods_no_crash(svc, mood):
    try:
        results = svc.recommend("__cs_user__", mood, top_k=5)
        assert isinstance(results, list)
    except Exception as exc:
        pytest.fail(f"Cold-start raised exception for mood '{mood}': {exc}")


# ──────────────────────────────────────────────────────────────────
# 4. Cold-start with top_k=10 – at most 10 returned
# ──────────────────────────────────────────────────────────────────
def test_cold_start_top_k_respected(svc):
    results = svc.recommend("__cold_10__", "neutral", top_k=10)
    assert len(results) <= 10


# ──────────────────────────────────────────────────────────────────
# 5. Empty user_id string – fallback, no crash
# ──────────────────────────────────────────────────────────────────
def test_empty_user_id_no_crash(svc):
    try:
        results = svc.recommend("", "happy", top_k=5)
        assert isinstance(results, list)
    except Exception as exc:
        pytest.fail(f"Empty user_id raised: {exc}")


# ──────────────────────────────────────────────────────────────────
# 6. Numeric user_id (as string) – cold-start path
# ──────────────────────────────────────────────────────────────────
def test_numeric_string_user_id(svc):
    results = svc.recommend("9999999", "calm", top_k=5)
    assert isinstance(results, list)
    assert len(results) >= 1


# ──────────────────────────────────────────────────────────────────
# 7. Very long user_id string – no crash (input length tolerance)
# ──────────────────────────────────────────────────────────────────
def test_long_user_id_no_crash(svc):
    long_id = "x" * 512
    results = svc.recommend(long_id, "happy", top_k=5)
    assert isinstance(results, list)
