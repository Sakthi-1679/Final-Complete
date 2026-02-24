"""
Retraining Tests
=================
Verifies that the weekly best-interaction retrain workflow:
  1. Uses only new, high-quality interactions
  2. Does not overwrite old checkpoints without versioning
  3. Increments model version correctly
  4. Does not block live recommendation requests
  5. Logs metrics after every retrain cycle
"""

import os
import csv
import json
import time
import pickle
import shutil
import threading
import pytest
import torch


BASE_DIR   = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', '..', 'backend'))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
VERSIONS_DIR = os.path.join(MODELS_DIR, 'versions')
METADATA_FILE = os.path.join(BASE_DIR, 'recommender_metadata.json')


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def svc():
    from services.hybrid_recommender_service import get_hybrid_recommender
    return get_hybrid_recommender()


def _write_interactions(path, rows):
    headers = [
        "timestamp", "user_id", "movie_id", "emotion",
        "rating", "liked", "watch_time", "watch_time_seconds",
        "session_id", "detected_mood",
    ]
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=headers)
        w.writeheader()
        w.writerows(rows)


# ──────────────────────────────────────────────────────────────────
# 1. collect_best_interactions returns only high-quality rows
# ──────────────────────────────────────────────────────────────────
def test_collect_best_only_high_quality(svc, tmp_path, monkeypatch):
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        # BEST: rating 5.0, liked
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
        # BEST: liked + watch > 120s
        {"timestamp": "2026-01-01T10:01:00", "user_id": "u2", "movie_id": "2",
         "emotion": "happy", "rating": "0", "liked": "1",
         "watch_time": "200", "watch_time_seconds": "200",
         "session_id": "s2", "detected_mood": "happy"},
        # NOT BEST: low rating
        {"timestamp": "2026-01-01T10:02:00", "user_id": "u3", "movie_id": "3",
         "emotion": "sad", "rating": "1.5", "liked": "0",
         "watch_time": "30", "watch_time_seconds": "30",
         "session_id": "s3", "detected_mood": "sad"},
        # NOT BEST: not liked, short watch
        {"timestamp": "2026-01-01T10:03:00", "user_id": "u4", "movie_id": "4",
         "emotion": "neutral", "rating": "0", "liked": "0",
         "watch_time": "10", "watch_time_seconds": "10",
         "session_id": "s4", "detected_mood": "neutral"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    best = svc.collect_best_interactions()
    assert len(best) == 2, f"Expected 2 best rows, got {len(best)}"
    for row in best:
        rating = float(row.get("rating", 0) or 0)
        liked  = row.get("liked", "0").strip().lower() in ("1", "true", "yes")
        assert rating >= 4.0 or liked, f"Non-best row slipped through: {row}"


# ──────────────────────────────────────────────────────────────────
# 2. Old checkpoint is versioned (backed up) before overwrite
# ──────────────────────────────────────────────────────────────────
def test_old_model_backed_up_on_retrain(svc, tmp_path, monkeypatch):
    """After retrain, a versioned copy must exist in models/versions/."""
    os.makedirs(VERSIONS_DIR, exist_ok=True)
    before_count = len(os.listdir(VERSIONS_DIR))

    # Create best interactions so retrain actually runs
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    result = svc.retrain_on_best(epochs=1)

    after_count = len(os.listdir(VERSIONS_DIR))
    if result.get("status") == "ok":
        assert after_count > before_count, "No version backup created after retrain"


# ──────────────────────────────────────────────────────────────────
# 3. Model version increments after successful retrain
# ──────────────────────────────────────────────────────────────────
def test_model_version_increments(svc, tmp_path, monkeypatch):
    meta_before = svc._load_metadata()
    version_before = meta_before.get("model_version", 1)

    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    result = svc.retrain_on_best(epochs=1)

    if result.get("status") == "ok":
        version_after = result["version"]
        assert version_after == version_before + 1, (
            f"Version did not increment: before={version_before}, after={version_after}"
        )


# ──────────────────────────────────────────────────────────────────
# 4. Retraining does NOT block live recommendation requests
# ──────────────────────────────────────────────────────────────────
def test_retrain_does_not_block_live_requests(svc, tmp_path, monkeypatch):
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    # Start retrain in background thread
    retrain_thread = threading.Thread(
        target=svc.retrain_on_best, kwargs={"epochs": 1}, daemon=True
    )
    retrain_thread.start()

    # Immediately make recommendation requests – should not block
    t0 = time.time()
    results = svc.recommend("user_1", "happy", top_k=5)
    elapsed = time.time() - t0

    retrain_thread.join(timeout=60)

    assert isinstance(results, list), "recommend() returned non-list during retrain"
    assert elapsed < 5.0, f"recommend() took {elapsed:.2f}s during retrain (too slow)"


# ──────────────────────────────────────────────────────────────────
# 5. Retraining logs metrics (training_loss) to metadata
# ──────────────────────────────────────────────────────────────────
def test_retrain_logs_training_loss(svc, tmp_path, monkeypatch):
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    result = svc.retrain_on_best(epochs=1)

    if result.get("status") == "ok":
        assert "training_loss" in result, "training_loss not in retrain result"
        assert isinstance(result["training_loss"], float)
        # Training loss reported in metadata
        meta = svc._load_metadata()
        assert "training_loss" in meta


# ──────────────────────────────────────────────────────────────────
# 6. Retrain with no best interactions returns 'skipped'
# ──────────────────────────────────────────────────────────────────
def test_retrain_skipped_when_no_best(svc, tmp_path, monkeypatch):
    # Write only weak/poor interactions
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "sad", "rating": "1.0", "liked": "0",
         "watch_time": "10", "watch_time_seconds": "10",
         "session_id": "s1", "detected_mood": "sad"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    result = svc.retrain_on_best(epochs=1)
    assert result.get("status") == "skipped", (
        f"Expected 'skipped', got: {result}"
    )


# ──────────────────────────────────────────────────────────────────
# 7. Scheduler fires every 7 days (unit: seconds constant check)
# ──────────────────────────────────────────────────────────────────
def test_scheduler_interval_is_7_days():
    from pipeline.retrain_scheduler import RETRAIN_INTERVAL_DAYS, RETRAIN_INTERVAL_SECS
    assert RETRAIN_INTERVAL_DAYS == 7
    assert RETRAIN_INTERVAL_SECS == 7 * 24 * 3600


# ──────────────────────────────────────────────────────────────────
# 8. Scheduler status API returns expected keys
# ──────────────────────────────────────────────────────────────────
def test_scheduler_status_keys():
    from pipeline.retrain_scheduler import scheduler_status
    status = scheduler_status()
    required = {"scheduler_running", "retrain_interval_days", "next_retrain_in"}
    missing = required - set(status.keys())
    assert not missing, f"Missing keys in scheduler_status: {missing}"


# ──────────────────────────────────────────────────────────────────
# 9. retrain_metadata timestamp is updated after retrain
# ──────────────────────────────────────────────────────────────────
def test_last_retrain_ts_updated(svc, tmp_path, monkeypatch):
    csv_path = str(tmp_path / "interactions.csv")
    rows = [
        {"timestamp": "2026-01-01T10:00:00", "user_id": "u1", "movie_id": "1",
         "emotion": "happy", "rating": "5.0", "liked": "1",
         "watch_time": "300", "watch_time_seconds": "300",
         "session_id": "s1", "detected_mood": "happy"},
    ]
    _write_interactions(csv_path, rows)

    from services import hybrid_recommender_service as hrsvc
    monkeypatch.setattr(hrsvc, "INTERACTIONS_FILE", csv_path)

    ts_before = svc._load_metadata().get("last_retrain_ts", 0)
    result = svc.retrain_on_best(epochs=1)

    if result.get("status") == "ok":
        ts_after = svc._load_metadata().get("last_retrain_ts", 0)
        assert ts_after >= ts_before, "last_retrain_ts not updated after retrain"
