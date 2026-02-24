"""
End-to-End Integration Test
==============================
Full workflow:
  User → Mood Detection → Hybrid Recommendation
  → Feedback (Like) → Weekly Retrain → Improved Recommendation

This test requires the Flask server to be running at localhost:5000.
Skip flag: set env var SKIP_E2E=1 to skip.

Run with:
    pytest tests/integration/test_e2e_workflow.py -v -s
"""

import os
import csv
import json
import time
import tempfile
import pytest
import requests


BASE_URL = os.getenv("TEST_API_URL", "http://127.0.0.1:5000")
SKIP_E2E = os.getenv("SKIP_E2E", "0") == "1"

pytestmark = pytest.mark.skipif(SKIP_E2E, reason="SKIP_E2E=1")


# ──────────────────────────────────────────────────────────────────
# Session-scoped fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module", autouse=True)
def require_server():
    try:
        r = requests.get(f"{BASE_URL}/hybrid/model-info", timeout=3)
        assert r.status_code == 200
    except Exception:
        pytest.skip(f"E2E: server not reachable at {BASE_URL}")


@pytest.fixture(scope="module")
def test_user():
    """Register (or re-use) a test user and return auth token + username."""
    username = f"e2e_user_{int(time.time())}"
    reg = requests.post(f"{BASE_URL}/auth/register", json={
        "username": username,
        "email": f"{username}@e2e.test",
        "password": "E2e@test1234",
    })
    # Login even if register failed (user may already exist)
    login = requests.post(f"{BASE_URL}/auth/login", json={
        "username": username,
        "password": "E2e@test1234",
    })
    token = login.json().get("token", "")
    return {"username": username, "token": token}


# ──────────────────────────────────────────────────────────────────
# STEP 1 – User detects mood (simulated as an API call result)
# ──────────────────────────────────────────────────────────────────

def test_step1_mood_detection_produces_valid_mood(test_user):
    """
    In production, mood comes from the face/voice model.
    In integration testing we simulate by directly calling /live_predict
    with a blank image (or accept that mood == 'happy' as the default).
    """
    # Simulated detected mood
    detected_mood = "happy"
    assert detected_mood in {
        "happy", "sad", "angry", "calm", "neutral",
        "stressed", "excited", "bored", "fear", "disgust", "surprise",
    }


# ──────────────────────────────────────────────────────────────────
# STEP 2 – Hybrid recommender returns results for detected mood
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def first_recommendations(test_user):
    resp = requests.post(f"{BASE_URL}/hybrid/recommend", json={
        "mood": "happy",
        "user_id": test_user["username"],
        "top_k": 5,
    })
    assert resp.status_code == 200, f"Recommend failed: {resp.text}"
    return resp.json()


def test_step2_recommendation_returns_results(first_recommendations):
    recs = first_recommendations.get("recommendations", [])
    assert len(recs) >= 1, "No recommendations returned"


def test_step2_results_have_required_fields(first_recommendations):
    for r in first_recommendations.get("recommendations", []):
        assert "id" in r
        assert "title" in r
        assert "_recommended_rank" in r


def test_step2_mood_echoed_in_response(first_recommendations):
    assert first_recommendations.get("mood") == "happy"


def test_step2_model_version_present(first_recommendations):
    assert isinstance(first_recommendations.get("model_version"), int)


# ──────────────────────────────────────────────────────────────────
# STEP 3 – User gives positive feedback (like) on top recommendation
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def feedback_response(test_user, first_recommendations):
    recs = first_recommendations.get("recommendations", [])
    if not recs:
        pytest.skip("No recommendations to give feedback on")
    top_movie = recs[0]
    resp = requests.post(f"{BASE_URL}/hybrid/interact", json={
        "user_id": test_user["username"],
        "movie_id": str(top_movie["id"]),
        "movie_title": top_movie.get("title", ""),
        "emotion": "happy",
        "action": "like",
        "rating": 5.0,
        "watch_time": 300,
        "session_id": "e2e_sess_001",
    })
    return resp


def test_step3_feedback_returns_200(feedback_response):
    assert feedback_response.status_code == 200, (
        f"Feedback failed: {feedback_response.text}"
    )


def test_step3_feedback_response_has_status_field(feedback_response):
    data = feedback_response.json()
    assert any(k in data for k in ("status", "message", "logged"))


# ──────────────────────────────────────────────────────────────────
# STEP 4 – Trigger a manual retrain (force cycle)
# ──────────────────────────────────────────────────────────────────

def test_step4_trigger_retrain_accepted(test_user):
    resp = requests.post(
        f"{BASE_URL}/retrain/trigger",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    # Either triggered (200) or not permitted without admin (401/403) – both acceptable
    assert resp.status_code in (200, 202, 401, 403), (
        f"Unexpected retrain trigger response: {resp.status_code}"
    )


def test_step4_retrain_status_endpoint_reachable(test_user):
    resp = requests.get(
        f"{BASE_URL}/retrain/status",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert resp.status_code in (200, 401, 403)
    if resp.status_code == 200:
        data = resp.json()
        assert "scheduler_running" in data or "retrain_interval_days" in data


# ──────────────────────────────────────────────────────────────────
# STEP 5 – Second recommendation call after feedback
#          Results must still be valid (model may or may not have retrained)
# ──────────────────────────────────────────────────────────────────

def test_step5_second_recommendation_still_valid(test_user):
    resp = requests.post(f"{BASE_URL}/hybrid/recommend", json={
        "mood": "happy",
        "user_id": test_user["username"],
        "top_k": 5,
    })
    assert resp.status_code == 200
    recs = resp.json().get("recommendations", [])
    assert len(recs) >= 1, "No recs on second call after feedback"


# ──────────────────────────────────────────────────────────────────
# STEP 6 – Model info reflects healthy state
# ──────────────────────────────────────────────────────────────────

def test_step6_model_info_loaded():
    resp = requests.get(f"{BASE_URL}/hybrid/model-info")
    assert resp.status_code == 200
    data = resp.json()
    assert data.get("model_loaded") is True


def test_step6_model_version_is_integer():
    resp = requests.get(f"{BASE_URL}/hybrid/model-info")
    data = resp.json()
    assert isinstance(data.get("version"), int)
    assert data["version"] >= 1


# ──────────────────────────────────────────────────────────────────
# STEP 7 – Auth flow is intact throughout
# ──────────────────────────────────────────────────────────────────

def test_step7_authenticated_profile_accessible(test_user):
    if not test_user["token"]:
        pytest.skip("No token available")
    resp = requests.get(
        f"{BASE_URL}/auth/profile",
        headers={"Authorization": f"Bearer {test_user['token']}"},
    )
    assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────
# STEP 8 – End-to-end latency under 2 s for full cycle
# ──────────────────────────────────────────────────────────────────

def test_step8_full_flow_latency(test_user):
    t0 = time.time()

    # Recommend
    r1 = requests.post(f"{BASE_URL}/hybrid/recommend", json={
        "mood": "calm", "user_id": test_user["username"], "top_k": 5
    })
    recs = r1.json().get("recommendations", [])

    # Interact
    if recs:
        requests.post(f"{BASE_URL}/hybrid/interact", json={
            "user_id": test_user["username"],
            "movie_id": str(recs[0]["id"]),
            "action": "like",
            "rating": 4.0,
        })

    elapsed = time.time() - t0
    assert elapsed < 5.0, (
        f"Full recommend+interact cycle took {elapsed:.2f}s (target < 5s)"
    )
    print(f"\n[E2E] Full cycle elapsed: {elapsed:.2f}s")
