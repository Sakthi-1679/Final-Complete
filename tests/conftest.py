"""
conftest.py – Shared pytest fixtures for the entire test suite.
All tests import from here via pytest's auto-discovery.
"""

import os
import sys
import csv
import json
import pickle
import tempfile
import threading
import pytest

# ── Put the backend on the PYTHONPATH so imports resolve ──────────
BACKEND_DIR = os.path.join(os.path.dirname(__file__), '..', 'backend')
sys.path.insert(0, os.path.abspath(BACKEND_DIR))

# ─────────────────────────────────────────────────────────────────
# Flask app (test client)
# ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def app():
    """Create the Flask app in testing mode once for the whole test session."""
    os.environ.setdefault("TESTING", "1")
    os.environ.setdefault("DB_HOST", "localhost")
    os.environ.setdefault("DB_USER", "streamflix_user")
    os.environ.setdefault("DB_PASSWORD", "streamflix_password")
    os.environ.setdefault("DB_NAME", "hybrid_recommender_db")

    from app import app as flask_app
    flask_app.config["TESTING"] = True
    flask_app.config["WTF_CSRF_ENABLED"] = False
    return flask_app


@pytest.fixture(scope="session")
def client(app):
    """A Flask test client that can make HTTP requests without a running server."""
    with app.test_client() as c:
        yield c


# ─────────────────────────────────────────────────────────────────
# Hybrid recommender service (singleton)
# ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def hybrid_svc():
    from services.hybrid_recommender_service import get_hybrid_recommender
    svc = get_hybrid_recommender()
    return svc


# ─────────────────────────────────────────────────────────────────
# Minimal fake movie catalogue
# ─────────────────────────────────────────────────────────────────
FAKE_MOVIES = [
    {
        "id": str(i),
        "title": f"Movie {i}",
        "genres": ["Comedy"] if i % 2 == 0 else ["Action"],
        "mood": "happy" if i % 2 == 0 else "angry",
        "rating": str(round(3 + (i % 30) / 10, 1)),
        "year": 2020 + (i % 5),
        "views": 1000 * i,
        "description": f"Description for Movie {i}",
        "poster": f"https://example.com/poster{i}.jpg",
        "posterUrl": f"https://example.com/poster{i}.jpg",
        "backdropUrl": f"https://example.com/backdrop{i}.jpg",
        "trailerUrl": "",
        "videoUrl": "",
        "duration": "2h 0m",
        "language": "English",
        "category": "popular",
    }
    for i in range(1, 51)
]


@pytest.fixture
def movie_catalogue():
    return list(FAKE_MOVIES)


# ─────────────────────────────────────────────────────────────────
# Temp interactions CSV (writable copy)
# ─────────────────────────────────────────────────────────────────
INTERACTIONS_HEADERS = [
    "timestamp", "user_id", "movie_id", "emotion",
    "rating", "liked", "watch_time", "watch_time_seconds",
    "session_id", "detected_mood",
]


@pytest.fixture
def tmp_interactions_csv(tmp_path):
    """Creates a temporary interactions.csv with 10 sample rows."""
    fpath = tmp_path / "interactions.csv"
    rows = [
        {
            "timestamp": "2026-01-01T10:00:00",
            "user_id": f"user_{i}",
            "movie_id": str(i + 1),
            "emotion": "happy",
            "rating": "4.5",
            "liked": "1",
            "watch_time": "180",
            "watch_time_seconds": "180",
            "session_id": f"sess_{i}",
            "detected_mood": "happy",
        }
        for i in range(1, 6)
    ] + [
        {
            "timestamp": "2026-01-02T10:00:00",
            "user_id": f"user_{i}",
            "movie_id": str(i + 1),
            "emotion": "sad",
            "rating": "1.5",
            "liked": "0",
            "watch_time": "30",
            "watch_time_seconds": "30",
            "session_id": f"sess_{i}",
            "detected_mood": "sad",
        }
        for i in range(6, 11)
    ]
    with open(fpath, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=INTERACTIONS_HEADERS)
        writer.writeheader()
        writer.writerows(rows)
    return str(fpath)


# ─────────────────────────────────────────────────────────────────
# Fake ID mappings (pickle)
# ─────────────────────────────────────────────────────────────────
@pytest.fixture
def fake_mappings(tmp_path):
    mappings = {
        "user_id_to_idx": {f"user_{i}": i for i in range(1, 21)},
        "movie_id_to_idx": {str(i): i - 1 for i in range(1, 51)},
        "idx_to_movie_id": {i - 1: str(i) for i in range(1, 51)},
    }
    fpath = tmp_path / "mappings.pkl"
    with open(fpath, "wb") as f:
        pickle.dump(mappings, f)
    return mappings, str(fpath)


# ─────────────────────────────────────────────────────────────────
# Auth helpers
# ─────────────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def auth_token(client):
    """Register then log in a test user; return the JWT string."""
    client.post(
        "/auth/register",
        json={"username": "testuser_ci", "email": "ci@test.com", "password": "Test@1234"},
    )
    resp = client.post(
        "/auth/login",
        json={"username": "testuser_ci", "password": "Test@1234"},
    )
    data = resp.get_json() or {}
    return data.get("token", "")
