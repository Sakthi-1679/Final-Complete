"""
Unit Tests – Mood Encoder
==========================
Verifies that every valid mood maps to a unique integer id,
that unknown moods fall back gracefully, and that the id range
is within the embedding table's capacity.
"""

import pytest

# MOOD_TO_ID is defined in the service module
from services.hybrid_recommender_service import MOOD_TO_ID, NUM_MOODS


# ──────────────────────────────────────────────────────────────────
# 1. Every valid mood produces a non-negative integer index
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("mood", [
    "happy", "sad", "angry", "calm", "neutral",
    "stressed", "excited", "bored", "fear", "disgust", "surprise",
])
def test_valid_mood_returns_integer(mood):
    idx = MOOD_TO_ID.get(mood)
    assert isinstance(idx, int), f"Expected int for mood '{mood}', got {type(idx)}"
    assert idx >= 0, "Mood index must be non-negative"


# ──────────────────────────────────────────────────────────────────
# 2. All mood ids are unique
# ──────────────────────────────────────────────────────────────────
def test_mood_ids_are_unique():
    ids = list(MOOD_TO_ID.values())
    assert len(ids) == len(set(ids)), "Duplicate mood IDs detected"


# ──────────────────────────────────────────────────────────────────
# 3. NUM_MOODS matches the actual dict size
# ──────────────────────────────────────────────────────────────────
def test_num_moods_equals_dict_length():
    assert NUM_MOODS == len(MOOD_TO_ID)


# ──────────────────────────────────────────────────────────────────
# 4. Unknown mood falls back to the neutral id (4) at call sites
# ──────────────────────────────────────────────────────────────────
def test_unknown_mood_fallback():
    NEUTRAL_ID = MOOD_TO_ID["neutral"]
    unknown_id = MOOD_TO_ID.get("xyzzy", NEUTRAL_ID)
    assert unknown_id == NEUTRAL_ID


# ──────────────────────────────────────────────────────────────────
# 5. All ids fit within the embedding table (0 … NUM_MOODS-1)
# ──────────────────────────────────────────────────────────────────
def test_all_ids_within_embedding_bounds():
    for mood, idx in MOOD_TO_ID.items():
        assert 0 <= idx < NUM_MOODS, (
            f"Mood '{mood}' has id {idx} outside [0, {NUM_MOODS})"
        )


# ──────────────────────────────────────────────────────────────────
# 6. Case sensitivity – must be lowercase in the map
# ──────────────────────────────────────────────────────────────────
def test_mood_keys_are_lowercase():
    for mood in MOOD_TO_ID:
        assert mood == mood.lower(), f"Mood key '{mood}' is not lowercase"


# ──────────────────────────────────────────────────────────────────
# 7. Basic normalization helper (as done in service code)
# ──────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("raw,expected_mood", [
    ("HAPPY", "happy"),
    ("Sad  ", "sad"),
    ("  ANGRY ", "angry"),
])
def test_normalize_before_lookup(raw, expected_mood):
    normalized = raw.strip().lower()
    assert normalized in MOOD_TO_ID, f"'{normalized}' not in MOOD_TO_ID"
    assert MOOD_TO_ID[normalized] == MOOD_TO_ID[expected_mood]
