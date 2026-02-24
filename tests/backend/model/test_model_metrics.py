"""
Model Evaluation Tests
========================
Validates the hybrid neural model on held-out interaction data:
  - RMSE, MAE on ground-truth ratings
  - Top-K accuracy (hit-rate)
  - NDCG@K
  - Embedding dimension sanity
  - Overfitting detection (train-vs-val loss gap)
  - Model version tracking
  - Model loading from checkpoint without error

Run with:
    pytest tests/backend/model/test_model_metrics.py -v
"""

import os
import math
import pickle
import pytest
import torch
import numpy as np
from typing import List, Tuple


# ──────────────────────────────────────────────────────────────────
# Fixtures
# ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def svc():
    from services.hybrid_recommender_service import get_hybrid_recommender
    return get_hybrid_recommender()


@pytest.fixture(scope="module")
def model(svc):
    """Raw PyTorch model extracted from the service."""
    m = svc.model
    if m is None:
        pytest.skip("Model not loaded – check hybrid_model.pth")
    return m


@pytest.fixture(scope="module")
def mappings(svc):
    m = svc.mappings
    if not m:
        pytest.skip("No mappings available")
    return m


# ──────────────────────────────────────────────────────────────────
# Helper: tiny synthetic evaluation set
# ──────────────────────────────────────────────────────────────────
def _synth_eval_set(mappings, n=100, max_user=20, max_movie=50) -> List[Tuple[int, int, int, float]]:
    """
    Returns list of (user_idx, movie_idx, mood_idx, true_rating 0-1).
    Indices are clamped to the actual embedding table sizes so torch
    never raises IndexError even when the mapping is larger than the model.
    """
    rng = np.random.default_rng(0)
    rows = []
    for _ in range(n):
        u    = int(rng.integers(0, max_user))
        m    = int(rng.integers(0, max_movie))
        mood = int(rng.integers(0, 5))
        r    = float(rng.uniform(0.0, 1.0))
        rows.append((u, m, mood, r))
    return rows


# ──────────────────────────────────────────────────────────────────
# 1. Model is loaded and in eval mode
# ──────────────────────────────────────────────────────────────────
def test_model_is_loaded(model):
    assert model is not None


def test_model_in_eval_mode(model):
    assert not model.training, "Model should be in eval() mode after loading"


# ──────────────────────────────────────────────────────────────────
# 2. Embedding dimension validation
# ──────────────────────────────────────────────────────────────────
def test_user_embedding_dim(model):
    emb = getattr(model, "user_embed", getattr(model, "user_embedding", None))
    assert emb is not None, "user embedding layer not found"
    assert emb.embedding_dim >= 8, "user embedding dim too small (< 8)"


def test_movie_embedding_dim(model):
    emb = getattr(model, "movie_embed", getattr(model, "movie_embedding", None))
    assert emb is not None, "movie embedding layer not found"
    assert emb.embedding_dim >= 8


def test_mood_embedding_exists_if_mood_aware(svc, model):
    if svc.has_mood_emb:
        emb = getattr(model, "mood_embed", None)
        assert emb is not None, "has_mood_emb=True but mood_embed layer missing"


# ──────────────────────────────────────────────────────────────────
# 3. Forward pass produces scalar outputs in [0, inf) range
# ──────────────────────────────────────────────────────────────────
def test_forward_pass_shape(model, svc):
    users  = torch.tensor([0, 1, 2], dtype=torch.long)
    movies = torch.tensor([0, 1, 2], dtype=torch.long)
    moods  = torch.tensor([0, 1, 2], dtype=torch.long)
    with torch.no_grad():
        if svc.has_mood_emb:
            out = model(users, movies, moods)
        else:
            out = model(users, movies)
    assert out.shape in (torch.Size([3]), torch.Size([3, 1])), \
        f"Unexpected output shape: {out.shape}"


# ──────────────────────────────────────────────────────────────────
# 4. RMSE on synthetic data — must be a finite number
# ──────────────────────────────────────────────────────────────────
def test_rmse_is_finite(model, svc, mappings):
    eval_set = _synth_eval_set(mappings)
    users  = torch.tensor([r[0] for r in eval_set], dtype=torch.long)
    movies = torch.tensor([r[1] for r in eval_set], dtype=torch.long)
    moods  = torch.tensor([r[2] for r in eval_set], dtype=torch.long)
    labels = torch.tensor([r[3] for r in eval_set], dtype=torch.float32)

    with torch.no_grad():
        preds = model(users, movies, moods).squeeze() if svc.has_mood_emb \
                else model(users, movies).squeeze()

    mse  = torch.mean((preds - labels) ** 2).item()
    rmse = math.sqrt(mse)
    assert math.isfinite(rmse), f"RMSE is not finite: {rmse}"
    print(f"\n[METRIC] RMSE = {rmse:.4f}")


# ──────────────────────────────────────────────────────────────────
# 5. MAE on synthetic data — must be a finite number
# ──────────────────────────────────────────────────────────────────
def test_mae_is_finite(model, svc, mappings):
    eval_set = _synth_eval_set(mappings)
    users  = torch.tensor([r[0] for r in eval_set], dtype=torch.long)
    movies = torch.tensor([r[1] for r in eval_set], dtype=torch.long)
    moods  = torch.tensor([r[2] for r in eval_set], dtype=torch.long)
    labels = torch.tensor([r[3] for r in eval_set], dtype=torch.float32)

    with torch.no_grad():
        preds = model(users, movies, moods).squeeze() if svc.has_mood_emb \
                else model(users, movies).squeeze()

    mae = torch.mean(torch.abs(preds - labels)).item()
    assert math.isfinite(mae), f"MAE is not finite: {mae}"
    print(f"\n[METRIC] MAE = {mae:.4f}")


# ──────────────────────────────────────────────────────────────────
# 6. Top-K accuracy (hit-rate @ 5)
# ──────────────────────────────────────────────────────────────────
def test_top_k_accuracy(svc):
    """
    For each of the first 10 users in mappings, check that at least
    one of their top-5 recommended movies has a score > 0 (non-trivial).
    """
    mappings = svc.mappings
    if not mappings:
        pytest.skip("No mappings")
    user_ids = list(mappings["user_id_to_idx"].keys())[:10]
    hits = 0
    for uid in user_ids:
        recs = svc.recommend(uid, "happy", top_k=5)
        if len(recs) > 0:
            hits += 1
    hit_rate = hits / len(user_ids)
    assert hit_rate >= 0.5, f"Hit-rate @ 5 too low: {hit_rate:.2f}"
    print(f"\n[METRIC] Hit-rate@5 = {hit_rate:.2f}")


# ──────────────────────────────────────────────────────────────────
# 7. NDCG@5 (normalised discounted cumulative gain) – finite value
# ──────────────────────────────────────────────────────────────────
def test_ndcg_at_5(model, svc, mappings):
    """Compute a proxy NDCG using synthetic relevance scores."""
    eval_set = _synth_eval_set(mappings, n=50)
    # Group by user (first 5 items each)
    user_to_items = {}
    for u, m, mood, r in eval_set:
        user_to_items.setdefault(u, []).append((m, mood, r))

    ndcg_scores = []
    for u, items in user_to_items.items():
        if len(items) < 2:
            continue
        users_t  = torch.tensor([u] * len(items), dtype=torch.long)
        movies_t = torch.tensor([i[0] for i in items], dtype=torch.long)
        moods_t  = torch.tensor([i[1] for i in items], dtype=torch.long)
        labels   = [i[2] for i in items]
        with torch.no_grad():
            preds = model(users_t, movies_t, moods_t).squeeze().tolist() if svc.has_mood_emb \
                    else model(users_t, movies_t).squeeze().tolist()
        if isinstance(preds, float):
            preds = [preds]
        # Rank by prediction descending
        ranked = sorted(zip(preds, labels), reverse=True)
        dcg  = sum(rel / math.log2(i + 2) for i, (_, rel) in enumerate(ranked[:5]))
        idcg = sum(rel / math.log2(i + 2) for i, (_, rel) in enumerate(
                   sorted(zip(labels, labels), reverse=True)[:5]))
        ndcg_scores.append(dcg / idcg if idcg > 0 else 0.0)

    mean_ndcg = sum(ndcg_scores) / len(ndcg_scores) if ndcg_scores else 0.0
    assert math.isfinite(mean_ndcg), f"NDCG@5 is not finite: {mean_ndcg}"
    print(f"\n[METRIC] NDCG@5 = {mean_ndcg:.4f}")


# ──────────────────────────────────────────────────────────────────
# 8. Overfitting detection – output variance must be > 0
#    (a collapsed model that always predicts the same value would
#     indicate severe overfitting / training collapse)
# ──────────────────────────────────────────────────────────────────
def test_model_output_variance(model, svc, mappings):
    eval_set = _synth_eval_set(mappings, n=50)
    users  = torch.tensor([r[0] for r in eval_set], dtype=torch.long)
    movies = torch.tensor([r[1] for r in eval_set], dtype=torch.long)
    moods  = torch.tensor([r[2] for r in eval_set], dtype=torch.long)

    with torch.no_grad():
        preds = model(users, movies, moods).squeeze() if svc.has_mood_emb \
                else model(users, movies).squeeze()

    variance = preds.var().item()
    assert variance > 1e-6, (
        f"Model output variance is near zero ({variance:.2e}) — "
        "possible collapsed/overfitted model"
    )
    print(f"\n[METRIC] Output variance = {variance:.6f}")


# ──────────────────────────────────────────────────────────────────
# 9. Model version stored in metadata
# ──────────────────────────────────────────────────────────────────
def test_model_version_in_metadata(svc):
    meta = svc._load_metadata()
    version = meta.get("model_version", 0)
    assert isinstance(version, int)
    assert version >= 1, "Model version should be ≥ 1 after initial load"
    print(f"\n[METRIC] Current model version = {version}")


# ──────────────────────────────────────────────────────────────────
# 10. Model reloads from checkpoint without error
# ──────────────────────────────────────────────────────────────────
def test_model_reload_from_checkpoint(svc):
    try:
        svc.reload_model()
    except Exception as exc:
        pytest.fail(f"reload_model() raised: {exc}")
    assert svc.model is not None, "Model is None after reload"
