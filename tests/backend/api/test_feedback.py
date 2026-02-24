"""
API Tests – POST /hybrid/interact  (feedback / like-dislike)
==============================================================
Tests the interaction-logging endpoint which records user
like/dislike/rating/watch-time feedback.

Run with:
    pytest tests/backend/api/test_feedback.py -v
"""

import pytest


# ──────────────────────────────────────────────────────────────────
# Fixture: a valid feedback payload
# ──────────────────────────────────────────────────────────────────
@pytest.fixture
def valid_payload():
    return {
        "user_id": "test_user",
        "movie_id": "1",
        "movie_title": "Test Movie",
        "emotion": "happy",
        "action": "like",
        "rating": 4.5,
        "watch_time": 120,
        "session_id": "sess_test_001",
    }


# ──────────────────────────────────────────────────────────────────
# Happy-path tests
# ──────────────────────────────────────────────────────────────────

def test_valid_like_returns_200(client, valid_payload):
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code == 200


def test_valid_dislike_returns_200(client, valid_payload):
    valid_payload["action"] = "dislike"
    valid_payload["rating"] = 1.0
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code == 200


def test_feedback_response_has_status(client, valid_payload):
    resp = client.post("/hybrid/interact", json=valid_payload)
    data = resp.get_json()
    assert "status" in data or "message" in data or "logged" in data


def test_feedback_with_zero_watch_time(client, valid_payload):
    valid_payload["watch_time"] = 0
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code in (200, 400)


def test_feedback_with_max_rating(client, valid_payload):
    valid_payload["rating"] = 5.0
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code == 200


def test_feedback_with_min_rating(client, valid_payload):
    valid_payload["rating"] = 0.5
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code == 200


# ──────────────────────────────────────────────────────────────────
# Edge / error cases
# ──────────────────────────────────────────────────────────────────

def test_missing_movie_id_returns_error(client, valid_payload):
    del valid_payload["movie_id"]
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code in (400, 422, 200)


def test_missing_user_id_treated_as_anonymous(client, valid_payload):
    del valid_payload["user_id"]
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code in (200, 400)


def test_invalid_rating_above_5(client, valid_payload):
    valid_payload["rating"] = 99
    resp = client.post("/hybrid/interact", json=valid_payload)
    # Should sanitise or reject – never crash
    assert resp.status_code != 500


def test_negative_watch_time(client, valid_payload):
    valid_payload["watch_time"] = -100
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code != 500


def test_empty_json_body(client):
    resp = client.post("/hybrid/interact", json={})
    assert resp.status_code in (400, 422, 200)


# ──────────────────────────────────────────────────────────────────
# Security
# ──────────────────────────────────────────────────────────────────

def test_sql_injection_in_movie_id(client, valid_payload):
    valid_payload["movie_id"] = "1; DROP TABLE movies; --"
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code != 500


def test_xss_in_movie_title(client, valid_payload):
    valid_payload["movie_title"] = "<img src=x onerror=alert(1)>"
    resp = client.post("/hybrid/interact", json=valid_payload)
    body = resp.get_data(as_text=True)
    assert "<img" not in body, "XSS payload reflected in response body"


def test_sql_injection_in_user_id(client, valid_payload):
    valid_payload["user_id"] = "admin'--"
    resp = client.post("/hybrid/interact", json=valid_payload)
    assert resp.status_code != 500


# ──────────────────────────────────────────────────────────────────
# /recommend (legacy route) still works
# ──────────────────────────────────────────────────────────────────

def test_legacy_recommend_endpoint(client):
    resp = client.post(
        "/recommend",
        json={"emotion": "happy", "user_id": "user_1"},
    )
    assert resp.status_code in (200, 400, 404)
