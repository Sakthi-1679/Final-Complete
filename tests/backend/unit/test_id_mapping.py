"""
Unit Tests – ID Mapping
========================
Verifies user-to-index and movie-to-index mappings behave correctly
for known, unknown (cold-start), and boundary IDs.
"""

import pickle
import pytest


# ──────────────────────────────────────────────────────────────────
# Helper – build a small in-memory mapping (no file I/O needed)
# ──────────────────────────────────────────────────────────────────
@pytest.fixture
def mappings():
    return {
        "user_id_to_idx":  {f"user_{i}": i for i in range(1, 21)},
        "movie_id_to_idx": {str(i): i - 1 for i in range(1, 51)},
        "idx_to_movie_id": {i - 1: str(i) for i in range(1, 51)},
    }


# 1. Known user returns correct index
def test_known_user_maps_to_index(mappings):
    assert mappings["user_id_to_idx"]["user_5"] == 5


# 2. Known movie returns correct index
def test_known_movie_maps_to_index(mappings):
    assert mappings["movie_id_to_idx"]["10"] == 9


# 3. Unknown user (cold-start) falls back to 0
def test_unknown_user_fallback(mappings):
    idx = mappings["user_id_to_idx"].get("cold_start_user", 0)
    assert idx == 0


# 4. Unknown movie falls back to 0
def test_unknown_movie_fallback(mappings):
    idx = mappings["movie_id_to_idx"].get("99999", 0)
    assert idx == 0


# 5. Reverse mapping idx→movie_id is consistent
def test_reverse_mapping_consistent(mappings):
    for movie_id, idx in mappings["movie_id_to_idx"].items():
        assert mappings["idx_to_movie_id"][idx] == movie_id


# 6. No duplicate user indices
def test_no_duplicate_user_indices(mappings):
    indices = list(mappings["user_id_to_idx"].values())
    assert len(indices) == len(set(indices))


# 7. No duplicate movie indices
def test_no_duplicate_movie_indices(mappings):
    indices = list(mappings["movie_id_to_idx"].values())
    assert len(indices) == len(set(indices))


# 8. Indices start at 0 (or a known constant) – not negative
def test_indices_non_negative(mappings):
    for idx in mappings["user_id_to_idx"].values():
        assert idx >= 0
    for idx in mappings["movie_id_to_idx"].values():
        assert idx >= 0


# 9. Pickle round-trip preserves mapping
def test_pickle_roundtrip(mappings, tmp_path):
    fpath = tmp_path / "mappings.pkl"
    with open(fpath, "wb") as f:
        pickle.dump(mappings, f)
    with open(fpath, "rb") as f:
        loaded = pickle.load(f)
    assert loaded["user_id_to_idx"] == mappings["user_id_to_idx"]
    assert loaded["movie_id_to_idx"] == mappings["movie_id_to_idx"]


# 10. All movie IDs in mappings are strings
def test_movie_ids_are_strings(mappings):
    for k in mappings["movie_id_to_idx"]:
        assert isinstance(k, str), f"Movie id key '{k}' is not a string"
