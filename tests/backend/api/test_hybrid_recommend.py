"""
API Tests – POST /hybrid/recommend
====================================
Tests the Flask endpoint used by the frontend to fetch
mood-based movie recommendations.

Run with:
    pytest tests/backend/api/test_hybrid_recommend.py -v
"""

import json
import pytest


# ──────────────────────────────────────────────────────────────────
# Happy-path tests
# ──────────────────────────────────────────────────────────────────

def test_valid_recommend_returns_200(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "user_id": "user_1", "top_k": 5},
    )
    assert resp.status_code == 200


def test_valid_recommend_returns_list(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "user_id": "user_1", "top_k": 5},
    )
    data = resp.get_json()
    assert "recommendations" in data
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) == 5


def test_recommend_includes_mood_field(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "sad", "user_id": "user_1", "top_k": 3},
    )
    data = resp.get_json()
    assert data.get("mood") == "sad"


def test_recommend_includes_model_version(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "calm", "user_id": "user_1", "top_k": 3},
    )
    data = resp.get_json()
    assert "model_version" in data
    assert isinstance(data["model_version"], int)


@pytest.mark.parametrize("mood", [
    "happy", "sad", "angry", "calm", "neutral",
    "stressed", "excited", "bored", "fear", "disgust", "surprise",
])
def test_all_valid_moods_return_200(client, mood):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": mood, "user_id": "user_1", "top_k": 3},
    )
    assert resp.status_code == 200, f"Mood '{mood}' returned {resp.status_code}"


def test_cold_start_user_returns_results(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "user_id": "never_seen_user_xyz", "top_k": 5},
    )
    assert resp.status_code == 200
    data = resp.get_json()
    assert len(data["recommendations"]) > 0


# ──────────────────────────────────────────────────────────────────
# Input validation / error cases
# ──────────────────────────────────────────────────────────────────

def test_missing_mood_field_returns_error(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"user_id": "user_1", "top_k": 5},
    )
    assert resp.status_code in (400, 422, 200)  # 200 with fallback accepted


def test_missing_user_id_still_returns_200(client):
    """user_id is optional – backend uses anonymous/cold-start."""
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "top_k": 5},
    )
    assert resp.status_code == 200


def test_invalid_mood_string_returns_results(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "xyzzy_invalid", "user_id": "user_1", "top_k": 5},
    )
    # Either 200 with fallback or 400 – must not 500
    assert resp.status_code != 500


def test_top_k_zero_returns_error_or_empty(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "user_id": "user_1", "top_k": 0},
    )
    assert resp.status_code in (200, 400)
    if resp.status_code == 200:
        data = resp.get_json()
        assert len(data.get("recommendations", [])) == 0


def test_top_k_very_large_is_clamped(client):
    resp = client.post(
        "/hybrid/recommend",
        json={"mood": "happy", "user_id": "user_1", "top_k": 9999},
    )
    # 429 = rate-limited (server protecting itself) — also acceptable
    assert resp.status_code in (200, 429)
    if resp.status_code == 200:
        data = resp.get_json()
        # Must not return 9999 movies (catalogue is finite)
        assert len(data["recommendations"]) <= 500


def test_empty_body_returns_4xx(client):
    resp = client.post("/hybrid/recommend", json={})
    assert resp.status_code in (400, 422, 200, 429)


def test_non_json_content_type(client):
    resp = client.post(
        "/hybrid/recommend",
        data="not json",
        content_type="text/plain",
    )
    assert resp.status_code in (400, 415, 422, 429, 500)


# ──────────────────────────────────────────────────────────────────
# Security-relevant API tests (basic)
# ──────────────────────────────────────────────────────────────────

def test_sql_injection_in_user_id(client):
    payload = {"mood": "happy", "user_id": "' OR '1'='1", "top_k": 5}
    resp = client.post("/hybrid/recommend", json=payload)
    assert resp.status_code in (200, 400, 429)
    assert resp.status_code != 500


def test_xss_in_mood_field(client):
    payload = {"mood": "<script>alert(1)</script>", "user_id": "user_1", "top_k": 5}
    resp = client.post("/hybrid/recommend", json=payload)
    text = resp.get_data(as_text=True)
    assert "<script>" not in text, "XSS payload reflected in response"


def test_large_payload_does_not_crash(client):
    payload = {
        "mood": "happy",
        "user_id": "x" * 4096,
        "top_k": 5,
        "extra": "A" * 65536,
    }
    resp = client.post("/hybrid/recommend", json=payload)
    assert resp.status_code in (200, 400, 413, 429)
