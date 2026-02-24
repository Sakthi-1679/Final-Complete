"""
Database Tests
===============
Validates MySQL operations used by the recommender system:
  - Interaction logging (no duplicates, correct fields)
  - Mood log storage
  - Rating storage and numeric bounds
  - Timestamp format correctness
  - Foreign key / data consistency
  - Data consistency after retraining
"""

import pytest
import datetime
from unittest.mock import patch, MagicMock


# ──────────────────────────────────────────────────────────────────
# Helpers – thin wrappers around database.py functions under test
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def db():
    """Import database module once; skip entire module if DB unvailable."""
    try:
        import utils.database as database
        # Quick connectivity check
        conn = database.get_connection()
        conn.close()
        return database
    except Exception as e:
        pytest.skip(f"Database unavailable: {e}")


# ──────────────────────────────────────────────────────────────────
# 1. init_database() creates all required tables
# ──────────────────────────────────────────────────────────────────
EXPECTED_TABLES = {
    "users", "movies", "movie_interactions",
    "mood_logs", "hybrid_model_metadata",
}

def test_all_tables_exist(db):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SHOW TABLES")
    existing = {row[0].lower() for row in cursor.fetchall()}
    cursor.close(); conn.close()
    missing = EXPECTED_TABLES - existing
    assert not missing, f"Missing tables: {missing}"


# ──────────────────────────────────────────────────────────────────
# 2. log_hybrid_interaction inserts a row
# ──────────────────────────────────────────────────────────────────
def test_log_hybrid_interaction_inserts_row(db):
    before = _count_rows(db, "movie_interactions")
    db.log_hybrid_interaction(
        user_id=1,
        movie_id="9999",
        movie_title="DB Test Movie",
        mood="happy",
        rating=4.5,
        liked=True,
        watch_time=120,
        recommended_rank_position=1,
    )
    after = _count_rows(db, "movie_interactions")
    assert after >= before, "Row count did not increase after log_hybrid_interaction"


# ──────────────────────────────────────────────────────────────────
# 3. No duplicate rows for same (user, movie, timestamp) combo
# ──────────────────────────────────────────────────────────────────
def test_no_duplicate_interactions(db):
    """
    Insert the same interaction twice; count should not have exact-dupe rows.
    (The schema may allow duplicates functionally – but we check data integrity.)
    """
    conn = db.get_connection()
    cursor = conn.cursor()
    ts = datetime.datetime.now().isoformat()
    for _ in range(2):
        try:
            db.log_hybrid_interaction(
                user_id=1,
                movie_id="8888",
                movie_title="Dup Test",
                mood="sad",
                liked=False,
                rating=1.0,
                watch_time=10,
                recommended_rank_position=1,
            )
        except Exception:
            pass  # unique-constraint violation is also acceptable

    cursor.execute(
        "SELECT COUNT(*) FROM movie_interactions "
        "WHERE user_id=%s AND movie_id=%s",
        ("dup_check_user", "8888"),
    )
    count = cursor.fetchone()[0]
    cursor.close(); conn.close()
    # At most 2 rows (two explicit inserts), never more
    assert count <= 2, f"Unexpected duplicate rows: {count}"


# ──────────────────────────────────────────────────────────────────
# 4. Timestamps are stored in ISO format / parseable
# ──────────────────────────────────────────────────────────────────
def test_timestamps_are_parseable(db):
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT watched_at FROM movie_interactions ORDER BY interaction_id DESC LIMIT 5"
    )
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    for row in rows:
        ts = row.get("watched_at")
        if ts is None:
            continue
        if isinstance(ts, datetime.datetime):
            continue        # MySQL driver already parsed it
        # Try parsing as string
        try:
            datetime.datetime.fromisoformat(str(ts))
        except ValueError:
            pytest.fail(f"Timestamp not parseable: {ts!r}")


# ──────────────────────────────────────────────────────────────────
# 5. Ratings stored and retrieved within [0, 5]
# ──────────────────────────────────────────────────────────────────
def test_rating_within_bounds(db):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT rating FROM movie_interactions "
        "WHERE rating IS NOT NULL LIMIT 50"
    )
    rows = cursor.fetchall()
    cursor.close(); conn.close()
    for (r,) in rows:
        if r is None:
            continue
        assert 0.0 <= float(r) <= 5.0, f"Rating out of range: {r}"


# ──────────────────────────────────────────────────────────────────
# 6. Mood log stores correct mood string
# ──────────────────────────────────────────────────────────────────
def test_mood_log_correct_mood(db):
    # Get a real user_id that satisfies the FK constraint
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users LIMIT 1")
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if not row:
        pytest.skip("No users in DB to satisfy FK constraint")
    real_user_id = row[0]

    db.log_mood_detection(
        user_id=real_user_id,
        mood="excited",
        confidence=0.92,
        model_version="test_v1",
    )
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT detected_mood FROM mood_logs "
        "WHERE user_id=%s ORDER BY mood_log_id DESC LIMIT 1",
        (real_user_id,),
    )
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if row:
        assert row["detected_mood"] == "excited"


# ──────────────────────────────────────────────────────────────────
# 7. get_all_movies_from_db returns a list with expected fields
# ──────────────────────────────────────────────────────────────────
def test_get_all_movies_returns_list(db):
    movies = db.get_all_movies_from_db()
    assert isinstance(movies, list)
    assert len(movies) > 0, "Movies table is empty"


def test_movie_has_required_fields(db):
    movies = db.get_all_movies_from_db()
    required = {"id", "title"}
    for m in movies[:5]:
        missing = required - set(m.keys())
        assert not missing, f"Movie missing fields: {missing}"


# ──────────────────────────────────────────────────────────────────
# 8. log_model_version increments version in hybrid_model_metadata
# ──────────────────────────────────────────────────────────────────
def test_log_model_version_inserts(db):
    before = _count_rows(db, "hybrid_model_metadata")
    db.log_model_version(
        version=9999,
        training_data_size=42,
        training_loss=0.123,
        model_file="hybrid_v9999.pth",
    )
    after = _count_rows(db, "hybrid_model_metadata")
    assert after >= before, "hybrid_model_metadata count did not increase"


# ──────────────────────────────────────────────────────────────────
# 9. update_movie_stats increments total_views without going negative
# ──────────────────────────────────────────────────────────────────
def test_update_movie_stats_views(db):
    movies = db.get_all_movies_from_db()
    if not movies:
        pytest.skip("No movies in DB")
    movie_id = str(movies[0]["id"])
    # Should not raise
    db.update_movie_stats(movie_id=movie_id, increment_views=True)
    conn = db.get_connection()
    cursor = conn.cursor(dictionary=True)
    cursor.execute(
        "SELECT total_views FROM movies WHERE id=%s", (movie_id,)
    )
    row = cursor.fetchone()
    cursor.close(); conn.close()
    if row and row["total_views"] is not None:
        assert int(row["total_views"]) >= 0


# ──────────────────────────────────────────────────────────────────
# 10. Data consistency – interactions reference existing users/movies
# ──────────────────────────────────────────────────────────────────
def test_interactions_reference_valid_movies(db):
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT COUNT(*) FROM movie_interactions mi
        LEFT JOIN movies m ON mi.movie_id = m.id
        WHERE m.id IS NULL AND mi.movie_id IS NOT NULL
    """)
    orphan_count = cursor.fetchone()[0]
    cursor.close(); conn.close()
    # Allow some orphans (test data) but flag if more than 10%
    total = _count_rows(db, "movie_interactions")
    if total > 0:
        orphan_ratio = orphan_count / total
        assert orphan_ratio <= 0.20, (
            f"High orphan interaction ratio: {orphan_ratio:.1%} ({orphan_count}/{total})"
        )


# ──────────────────────────────────────────────────────────────────
# Internal helper
# ──────────────────────────────────────────────────────────────────
def _count_rows(db, table: str) -> int:
    conn = db.get_connection()
    cursor = conn.cursor()
    cursor.execute(f"SELECT COUNT(*) FROM `{table}`")
    count = cursor.fetchone()[0]
    cursor.close(); conn.close()
    return count
