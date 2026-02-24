"""
Industry-Level Hybrid Recommender Service
==========================================
Loads hybrid_model.pth ONCE at startup.
Combines: Neural CF + Mood encoding + Popularity fallback.

RETRAINING: Only on WEAK interactions (low rating / not liked / short watch time).
No blocking of live requests during retraining.
"""

import os
import json
import pickle
import time
import hashlib
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple
from collections import OrderedDict

# ──────────────────────────────────────────────────────────────────
# Paths
# ──────────────────────────────────────────────────────────────────
BASE_DIR    = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR  = os.path.join(BASE_DIR, 'models')
HYBRID_MODEL_PATH   = os.path.join(MODELS_DIR, 'hybrid_model.pth')
FALLBACK_MODEL_PATH = os.path.join(MODELS_DIR, 'model.pth')
MAPPINGS_PATH       = os.path.join(MODELS_DIR, 'hybrid_mappings.pkl')
LEGACY_MAPPINGS     = os.path.join(MODELS_DIR, 'mappings.pkl')
VERSIONS_DIR        = os.path.join(MODELS_DIR, 'versions')
INTERACTIONS_FILE   = os.path.join(BASE_DIR, 'interactions.csv')
METADATA_FILE       = os.path.join(BASE_DIR, 'recommender_metadata.json')

os.makedirs(VERSIONS_DIR, exist_ok=True)

# ──────────────────────────────────────────────────────────────────
# Mood encoder  (mood name → integer id for embedding lookup)
# ──────────────────────────────────────────────────────────────────
MOOD_TO_ID: Dict[str, int] = {
    "happy":    0,
    "sad":      1,
    "angry":    2,
    "calm":     3,
    "neutral":  4,
    "stressed": 5,
    "excited":  6,
    "bored":    7,
    "fear":     8,
    "disgust":  9,
    "surprise": 10,
}
NUM_MOODS = len(MOOD_TO_ID)

# ──────────────────────────────────────────────────────────────────
# Weak-interaction thresholds  (only these are used for retraining)
# ──────────────────────────────────────────────────────────────────
WEAK_RATING_MAX  = 2.5   # rating ≤ this is "weak"
WEAK_WATCH_MAX   = 60    # watch_time_seconds ≤ this is "weak"

# ──────────────────────────────────────────────────────────────────
# Simple LRU cache for top recommendations
# ──────────────────────────────────────────────────────────────────
class _LRUCache:
    def __init__(self, maxsize: int = 256, ttl: int = 300):
        self._cache: OrderedDict = OrderedDict()
        self.maxsize = maxsize
        self.ttl = ttl          # seconds

    def _key(self, user_id: str, mood: str, top_k: int) -> str:
        raw = f"{user_id}:{mood}:{top_k}"
        return hashlib.md5(raw.encode()).hexdigest()

    def get(self, user_id: str, mood: str, top_k: int):
        k = self._key(user_id, mood, top_k)
        if k not in self._cache:
            return None
        val, ts = self._cache[k]
        if time.time() - ts > self.ttl:
            del self._cache[k]
            return None
        self._cache.move_to_end(k)
        return val

    def set(self, user_id: str, mood: str, top_k: int, movies: list):
        k = self._key(user_id, mood, top_k)
        self._cache[k] = (movies, time.time())
        self._cache.move_to_end(k)
        if len(self._cache) > self.maxsize:
            self._cache.popitem(last=False)

    def invalidate(self):
        self._cache.clear()


# ──────────────────────────────────────────────────────────────────
# Model architectures
# ──────────────────────────────────────────────────────────────────
def _build_model(num_users: int, num_movies: int, embedding_dim: int = 32,
                 include_mood: bool = False):
    """Build model dynamically based on whether mood embedding is available."""
    try:
        import torch.nn as nn
        if include_mood:
            class HybridMoodModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.user_emb  = nn.Embedding(num_users,  embedding_dim)
                    self.movie_emb = nn.Embedding(num_movies, embedding_dim)
                    self.mood_emb  = nn.Embedding(NUM_MOODS,  8)
                    in_dim = embedding_dim * 2 + 8
                    self.fc = nn.Sequential(
                        nn.Linear(in_dim, 128), nn.ReLU(),
                        nn.Dropout(0.2),
                        nn.Linear(128, 64),  nn.ReLU(),
                        nn.Linear(64, 1),
                    )
                def forward(self, user_ids, movie_ids, mood_ids=None):
                    u = self.user_emb(user_ids)
                    m = self.movie_emb(movie_ids)
                    if mood_ids is not None:
                        mood = self.mood_emb(mood_ids)
                        x = __import__('torch').cat([u, m, mood], dim=1)
                    else:
                        import torch
                        mood_zero = torch.zeros(u.shape[0], 8, device=u.device)
                        x = torch.cat([u, m, mood_zero], dim=1)
                    return self.fc(x)
            return HybridMoodModel()
        else:
            class BasicNCF(nn.Module):
                def __init__(self):
                    super().__init__()
                    self.user_emb  = nn.Embedding(num_users,  embedding_dim)
                    self.movie_emb = nn.Embedding(num_movies, embedding_dim)
                    self.fc = nn.Sequential(
                        nn.Linear(embedding_dim * 2, 128), nn.ReLU(),
                        nn.Linear(128, 1),
                    )
                def forward(self, user_ids, movie_ids, mood_ids=None):
                    u = self.user_emb(user_ids)
                    m = self.movie_emb(movie_ids)
                    return self.fc(__import__('torch').cat([u, m], dim=1))
            return BasicNCF()
    except ImportError:
        return None


# ──────────────────────────────────────────────────────────────────
# Main service class
# ──────────────────────────────────────────────────────────────────
class HybridRecommenderService:
    """
    Loaded once at server startup.
    Thread-safe: a RLock guards model swap during hot-reload after retraining.
    """

    # Capacity caps (keep consistent with legacy model.pth)
    MAX_USERS  = 500
    MAX_MOVIES = 800

    def __init__(self):
        self._lock        = threading.RLock()
        self.model        = None
        self.has_mood_emb = False
        self._emb_prefix  = 'embed'   # 'embed' or 'embedding' — set by _load_model
        self._mood_dim    = 8
        self.mappings: Dict = {
            'user_id_to_idx':  {},
            'movie_id_to_idx': {},
            'idx_to_movie_id': {},
        }
        self._cache = _LRUCache(maxsize=512, ttl=300)
        self._movie_db: List[Dict] = []

        self._load_model()
        self._load_mappings()
        print("[HybridRecommender] ✓ Service ready")

    # ── model loading ──────────────────────────────────────────────

    def _load_model(self):
        """Load hybrid_model.pth or fall back to model.pth.
        Inspects state-dict keys to determine architecture automatically."""
        path = HYBRID_MODEL_PATH if os.path.exists(HYBRID_MODEL_PATH) else FALLBACK_MODEL_PATH
        if not os.path.exists(path):
            print(f"[HybridRecommender] No model file found. Fallback scoring will be used.")
            return

        try:
            import torch
            import torch.nn as nn
            state = torch.load(path, map_location='cpu')

            # ── Detect key naming convention ─────────────────────────
            # hybrid_model.pth uses: user_embed / movie_embed / mood_embed
            # legacy model.pth uses: user_embedding / movie_embedding
            key_names = list(state.keys())
            if any('user_embed.' in k for k in key_names):
                prefix = 'embed'    # → user_embed, movie_embed, mood_embed
            else:
                prefix = 'embedding'  # → user_embedding, movie_embedding

            user_key  = f'user_{prefix}.weight'
            movie_key = f'movie_{prefix}.weight'
            mood_key  = f'mood_{prefix}.weight' if f'mood_{prefix}.weight' in state else None

            user_weight  = state.get(user_key)
            movie_weight = state.get(movie_key)
            mood_weight  = state.get(mood_key) if mood_key else None

            num_users  = user_weight.shape[0]  if user_weight  is not None else self.MAX_USERS
            num_movies = movie_weight.shape[0] if movie_weight is not None else self.MAX_MOVIES
            emb_dim    = user_weight.shape[1]  if user_weight  is not None else 32
            mood_dim   = mood_weight.shape[1]  if mood_weight  is not None else 8
            # Use ACTUAL mood-vocab size from checkpoint (may differ from NUM_MOODS)
            num_moods  = mood_weight.shape[0]  if mood_weight  is not None else NUM_MOODS
            has_mood   = mood_weight is not None

            # ── Infer fc layer sizes from state dict ─────────────────
            # Find all fc linear weight keys in order
            fc_weights = sorted(
                [(k, v) for k, v in state.items() if 'fc' in k and 'weight' in k],
                key=lambda x: x[0]
            )
            fc_dims = [v.shape for _, v in fc_weights]

            # Build model matching the actual checkpoint exactly
            # fc_dims[0][1] is the TRUE input dim (e.g. 98) from the checkpoint;
            # may be larger than emb_dim*2+mood_dim due to extra engineered features.
            fc_in_dim = fc_dims[0][1] if fc_dims else (emb_dim * 2 + (mood_dim if has_mood else 0))

            class DynamicHybridModel(nn.Module):
                def __init__(self):
                    super().__init__()
                    if prefix == 'embed':
                        self.user_embed  = nn.Embedding(num_users,  emb_dim)
                        self.movie_embed = nn.Embedding(num_movies, emb_dim)
                        if has_mood:
                            self.mood_embed = nn.Embedding(num_moods, mood_dim)
                    else:
                        self.user_embedding  = nn.Embedding(num_users,  emb_dim)
                        self.movie_embedding = nn.Embedding(num_movies, emb_dim)

                    # Build fc layers using EXACT in/out dims from the checkpoint weights
                    layers = []
                    for i, shape in enumerate(fc_dims):
                        out_f, in_f = shape[0], shape[1]
                        layers.append(nn.Linear(in_f, out_f))
                        if i < len(fc_dims) - 1:   # no ReLU after final layer
                            layers.append(nn.ReLU())
                    self.fc = nn.Sequential(*layers)

                def forward(self, user_ids, movie_ids, mood_ids=None):
                    import torch as _t
                    if prefix == 'embed':
                        u = self.user_embed(user_ids)
                        m = self.movie_embed(movie_ids)
                    else:
                        u = self.user_embedding(user_ids)
                        m = self.movie_embedding(movie_ids)

                    parts = [u, m]
                    if has_mood and mood_ids is not None and hasattr(self, 'mood_embed'):
                        parts.append(self.mood_embed(mood_ids))
                    elif has_mood and hasattr(self, 'mood_embed'):
                        parts.append(_t.zeros(u.shape[0], mood_dim, device=u.device))

                    x = _t.cat(parts, dim=1)
                    # Pad with zeros if checkpoint fc layer expects more features
                    # (e.g. original model used extra engineered features we don't have)
                    if x.shape[1] < fc_in_dim:
                        pad = _t.zeros(x.shape[0], fc_in_dim - x.shape[1], device=x.device)
                        x = _t.cat([x, pad], dim=1)
                    return self.fc(x)

            model = DynamicHybridModel()
            model.load_state_dict(state)
            model.eval()

            with self._lock:
                self.model        = model
                self.has_mood_emb = has_mood
                self._emb_prefix  = prefix
                self._mood_dim    = mood_dim

            print(f"[HybridRecommender] ✓ Loaded {'hybrid (mood-aware)' if has_mood else 'basic NCF'} model from {os.path.basename(path)}")
            print(f"[HybridRecommender]   users={num_users}, movies={num_movies}, emb_dim={emb_dim}, mood_dim={mood_dim if has_mood else 'N/A'}")
        except Exception as e:
            print(f"[HybridRecommender] Model load error: {e}. Fallback scoring active.")
            self.model = None

    def _load_mappings(self):
        """Load ID→index mappings; try hybrid first, then legacy."""
        for path in (MAPPINGS_PATH, LEGACY_MAPPINGS):
            if os.path.exists(path):
                try:
                    with open(path, 'rb') as f:
                        data = pickle.load(f)
                    with self._lock:
                        self.mappings = data
                    print(f"[HybridRecommender] ✓ Mappings loaded from {os.path.basename(path)} "
                          f"({len(data.get('user_id_to_idx', {}))} users, "
                          f"{len(data.get('movie_id_to_idx', {}))} movies)")
                    return
                except Exception as e:
                    print(f"[HybridRecommender] Mappings load warning: {e}")
        print("[HybridRecommender] No mappings found – will build on first retrain.")

    def reload_model(self):
        """Hot-reload: called by retrain scheduler after saving a new checkpoint."""
        self._cache.invalidate()
        self._load_model()
        self._load_mappings()

    # ── movie database ────────────────────────────────────────────

    def set_movie_db(self, movies: List[Dict]):
        """Inject movie catalogue (called by app.py after DB load)."""
        self._movie_db = movies

    def _get_movies(self) -> List[Dict]:
        if self._movie_db:
            return self._movie_db
        # Lazy fallback: read from JSON file
        json_path = os.path.join(BASE_DIR, 'movie_database.json')
        if os.path.exists(json_path):
            try:
                with open(json_path, 'r', encoding='utf-8') as f:
                    self._movie_db = json.load(f)
                return self._movie_db
            except Exception:
                pass
        return []

    # ── mood → genre filtering ────────────────────────────────────

    MOOD_GENRES = {
        "happy":    ["Comedy", "Animation", "Adventure", "Family", "Musical"],
        "sad":      ["Drama", "Romance", "History", "Documentary"],
        "angry":    ["Action", "Thriller", "Crime", "War"],
        "calm":     ["Drama", "Documentary", "Mystery", "Art"],
        "neutral":  [],   # no filter – use all
        "stressed": ["Comedy", "Animation", "Family"],
        "excited":  ["Action", "Adventure", "Science Fiction", "Thriller"],
        "bored":    ["Comedy", "Adventure", "Animation"],
        "fear":     ["Horror", "Thriller", "Suspense"],
        "disgust":  ["Documentary", "Crime", "Drama"],
        "surprise": ["Thriller", "Mystery", "Science Fiction"],
    }

    MOOD_TAGS = {
        "happy":  ["happy"],
        "sad":    ["sad"],
        "angry":  ["angry"],
        "calm":   ["calm", "happy"],
        "neutral":["happy", "calm", "sad"],
        "stressed":["happy"],
    }

    def _filter_by_mood(self, movies: List[Dict], mood: str) -> List[Dict]:
        mood = mood.lower()
        # First: try mood tag field
        tags = self.MOOD_TAGS.get(mood, [mood])
        tagged = [m for m in movies if m.get('mood', '').lower() in tags]
        if tagged:
            return tagged

        # Second: try genre overlap
        target_genres = self.MOOD_GENRES.get(mood, [])
        if target_genres:
            genre_filtered = []
            for m in movies:
                mg = m.get('genres', [])
                if isinstance(mg, str):
                    try:
                        mg = json.loads(mg)
                    except Exception:
                        mg = [mg]
                if any(g in target_genres for g in mg):
                    genre_filtered.append(m)
            if genre_filtered:
                return genre_filtered

        # Fallback: return all
        return movies

    # ── neural scoring ────────────────────────────────────────────

    def _neural_score(self, user_id: str, mood: str,
                      movies: List[Dict]) -> List[Tuple[float, Dict]]:
        """Score movies using the loaded model. Returns (score, movie) pairs."""
        with self._lock:
            model = self.model
            mappings = self.mappings
            has_mood = self.has_mood_emb

        if model is None:
            return []

        try:
            import torch
            uid = mappings['user_id_to_idx'].get(user_id, 0)
            mid_map = mappings.get('movie_id_to_idx', {})
            mood_id = MOOD_TO_ID.get(mood.lower(), 4)   # default: neutral

            results = []
            for movie in movies:
                movie_key = str(movie.get('id', ''))
                midx = mid_map.get(movie_key, 0)

                u_t = torch.tensor([uid  if uid  > 0 else 0], dtype=torch.long)
                m_t = torch.tensor([midx if midx > 0 else 0], dtype=torch.long)

                with torch.no_grad():
                    if has_mood:
                        mood_t = torch.tensor([mood_id], dtype=torch.long)
                        score = float(model(u_t, m_t, mood_t).item())
                    else:
                        score = float(model(u_t, m_t).item())

                # Boost popularity for cold-start users (uid==0)
                if uid == 0:
                    pop = float(movie.get('views', 0) or movie.get('popularity', 0) or 0)
                    score += pop / max(1, 100_000) * 0.5

                results.append((score, movie))
            return results
        except Exception as e:
            print(f"[HybridRecommender] Neural scoring error: {e}")
            return []

    def _popularity_score(self, movies: List[Dict]) -> List[Tuple[float, Dict]]:
        """Fallback: rank by views / popularity / average_rating."""
        results = []
        for m in movies:
            pop   = float(m.get('views', 0) or m.get('popularity', 0) or 0)
            avg_r = float(m.get('average_rating', 0) or m.get('rating', 3) or 3)
            score = pop / max(1, 100_000) + avg_r / 5.0
            results.append((score, m))
        return results

    # ── public API ────────────────────────────────────────────────

    def recommend(self, user_id: str, mood: str, top_k: int = 6) -> List[Dict]:
        """
        Returns top_k movie recommendations for user+mood.
        Uses in-memory LRU cache. Falls back gracefully if model unavailable.

        Cold-start handling:
          - New user  → popularity + mood filter
          - New movie → content/genre similarity already covered by mood filter
        """
        # Normalise
        user_id = str(user_id or 'guest').strip()
        mood    = str(mood or 'calm').lower().strip()
        if mood not in MOOD_TO_ID:
            mood = 'calm'

        # Cache hit?
        cached = self._cache.get(user_id, mood, top_k)
        if cached is not None:
            return cached

        movies = self._get_movies()
        if not movies:
            return []

        # Mood-filtered candidate set
        candidates = self._filter_by_mood(movies, mood)
        if not candidates:
            candidates = movies

        # Score
        scored = self._neural_score(user_id, mood, candidates)
        if not scored:
            scored = self._popularity_score(candidates)

        scored.sort(key=lambda x: x[0], reverse=True)
        results = [m for _, m in scored[:top_k]]

        # Add rank positions for interaction logging
        for rank, movie in enumerate(results, start=1):
            movie['_recommended_rank'] = rank

        self._cache.set(user_id, mood, top_k, results)
        return results

    def get_model_info(self) -> Dict:
        meta = self._load_metadata()
        with self._lock:
            loaded = self.model is not None
            has_mood = self.has_mood_emb
        return {
            'model_file':    os.path.basename(HYBRID_MODEL_PATH) if os.path.exists(HYBRID_MODEL_PATH) else 'model.pth (fallback)',
            'model_loaded':  loaded,
            'mood_aware':    has_mood,
            'version':       meta.get('model_version', 1),
            'last_retrain':  meta.get('last_retrain_date', 'Never'),
            'weak_samples_used': meta.get('weak_samples_trained', 0),
            'cache_size':    len(self._cache._cache),
        }

    # ── metadata helpers ──────────────────────────────────────────

    def _load_metadata(self) -> Dict:
        if not os.path.exists(METADATA_FILE):
            return {}
        try:
            with open(METADATA_FILE, 'r') as f:
                return json.load(f)
        except Exception:
            return {}

    def _save_metadata(self, data: Dict):
        try:
            with open(METADATA_FILE, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            print(f"[HybridRecommender] Metadata save error: {e}")

    def get_version(self) -> int:
        return self._load_metadata().get('model_version', 1)

    # ── weak-interaction retraining ───────────────────────────────

    def collect_weak_interactions(self) -> List[Dict]:
        """
        Read interactions.csv and return ONLY weak records:
          - rated ≤ WEAK_RATING_MAX
          - OR liked == False
          - OR watch_time ≤ WEAK_WATCH_MAX seconds
        These are the samples the model got wrong → retrain on them.
        """
        import csv
        weak = []
        if not os.path.exists(INTERACTIONS_FILE):
            return weak
        try:
            with open(INTERACTIONS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rating     = float(row.get('rating', 0) or 0)
                        liked_raw  = str(row.get('liked', '0')).strip().lower()
                        liked      = liked_raw in ('1', 'true', 'yes')
                        watch_time = float(row.get('watch_time', 0) or row.get('watch_time_seconds', 0) or 0)
                        is_weak    = (
                            (rating > 0 and rating <= WEAK_RATING_MAX) or
                            (not liked and rating == 0 and watch_time <= WEAK_WATCH_MAX)
                        )
                        if is_weak:
                            weak.append(row)
                    except Exception:
                        continue
        except Exception as e:
            print(f"[HybridRecommender] Error reading interactions: {e}")
        return weak

    def retrain_on_weak(self, epochs: int = 2) -> Dict:
        """
        Retrain the model using ONLY weak interactions.
        Called by the background scheduler — never blocks live requests.
        """
        with self._lock:
            model = self.model

        if model is None:
            return {'status': 'skipped', 'reason': 'model_not_loaded'}

        weak_rows = self.collect_weak_interactions()
        if not weak_rows:
            return {'status': 'skipped', 'reason': 'no_weak_interactions',
                    'message': 'No weak interactions found – model is performing well.'}

        print(f"[HybridRecommender] Retraining on {len(weak_rows)} weak interactions …")

        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            mappings = self.mappings
            user_map  = mappings.get('user_id_to_idx', {})
            movie_map = mappings.get('movie_id_to_idx', {})

            # Build training tensors
            x_user, x_movie, x_mood, y = [], [], [], []
            for row in weak_rows:
                uid   = user_map.get(str(row.get('user_id', '')), 0)
                mid   = movie_map.get(str(row.get('movie_id', '')), 0)
                if uid == 0 or mid == 0:
                    continue

                mood_raw = str(row.get('emotion', row.get('detected_mood', 'calm'))).lower()
                moodid   = MOOD_TO_ID.get(mood_raw, 4)

                rating   = float(row.get('rating', 0) or 0)
                liked    = str(row.get('liked', '0')).strip().lower() in ('1', 'true', 'yes')
                # Target: push weak samples toward a slightly better score
                target   = min(rating + 0.5, 3.0) if rating > 0 else (0.5 if liked else 0.1)

                x_user.append(uid);  x_movie.append(mid)
                x_mood.append(moodid); y.append(target)

            if not x_user:
                return {'status': 'skipped', 'reason': 'no_valid_weak_data'}

            x_user  = torch.tensor(x_user,  dtype=torch.long)
            x_movie = torch.tensor(x_movie, dtype=torch.long)
            x_mood  = torch.tensor(x_mood,  dtype=torch.long)
            y_t     = torch.tensor(y,        dtype=torch.float32)

            dataset    = TensorDataset(x_user, x_movie, x_mood, y_t)
            dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

            optimizer = torch.optim.Adam(model.parameters(), lr=5e-4)
            criterion = nn.MSELoss()

            model.train()
            for epoch in range(epochs):
                epoch_loss = 0.0
                for bu, bm, bmood, by in dataloader:
                    optimizer.zero_grad()
                    if self.has_mood_emb:
                        pred = model(bu, bm, bmood).squeeze()
                    else:
                        pred = model(bu, bm).squeeze()
                    loss = criterion(pred, by)
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                print(f"  Epoch {epoch+1}/{epochs} — loss: {epoch_loss:.4f}")
            model.eval()

            # Save checkpoint and update service
            active_path = HYBRID_MODEL_PATH if os.path.exists(HYBRID_MODEL_PATH) else FALLBACK_MODEL_PATH
            torch.save(model.state_dict(), active_path)

            meta = self._load_metadata()
            version = meta.get('model_version', 1) + 1
            meta['model_version']        = version
            meta['last_retrain_date']    = datetime.now().isoformat()
            meta['last_retrain_ts']      = int(time.time())
            meta['weak_samples_trained'] = meta.get('weak_samples_trained', 0) + len(weak_rows)
            meta['training_loss']        = round(epoch_loss, 4)
            self._save_metadata(meta)

            # Version backup
            backup = os.path.join(VERSIONS_DIR, f"hybrid_v{version}.pth")
            import shutil
            shutil.copy2(active_path, backup)

            # Hot-reload into service without stopping server
            self.reload_model()
            self._cache.invalidate()

            print(f"[HybridRecommender] ✓ Weak retrain done → version v{version}")
            return {
                'status':              'ok',
                'version':             version,
                'weak_samples_used':   len(weak_rows),
                'epochs':              epochs,
                'training_loss':       round(epoch_loss, 4),
                'model_file':          os.path.basename(active_path),
                'timestamp':           datetime.now().isoformat(),
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}

    # ── Best-Interaction Retraining (scheduled weekly) ────────────

    BEST_RATING_MIN  = 4.0   # rating must be ≥ this to count as "best"
    BEST_WATCH_MIN   = 120   # seconds of watch time required if no explicit rating

    def collect_best_interactions(self) -> List[Dict]:
        """
        Return ONLY the best interactions from interactions.csv:
          - rated ≥ BEST_RATING_MIN  (user genuinely liked it)
          - OR liked == True AND watch_time ≥ BEST_WATCH_MIN seconds
        These are strong positive signals to reinforce in the model.
        """
        import csv
        best = []
        if not os.path.exists(INTERACTIONS_FILE):
            return best
        try:
            with open(INTERACTIONS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try:
                        rating     = float(row.get('rating', 0) or 0)
                        liked_raw  = str(row.get('liked', '0')).strip().lower()
                        liked      = liked_raw in ('1', 'true', 'yes')
                        watch_time = float(row.get('watch_time', 0) or row.get('watch_time_seconds', 0) or 0)
                        is_best    = (
                            rating >= self.BEST_RATING_MIN or
                            (liked and watch_time >= self.BEST_WATCH_MIN)
                        )
                        if is_best:
                            best.append(row)
                    except Exception:
                        continue
        except Exception as e:
            print(f"[HybridRecommender] Error reading interactions: {e}")
        return best

    def retrain_on_best(self, epochs: int = 2) -> Dict:
        """
        Weekly retrain using ONLY best interactions.
        Reinforces high-quality positive signals so the model learns to
        score highly-rated / well-watched movies even higher.
        Called by the background weekly scheduler.
        """
        with self._lock:
            model = self.model

        if model is None:
            return {'status': 'skipped', 'reason': 'model_not_loaded'}

        best_rows = self.collect_best_interactions()
        if not best_rows:
            return {'status': 'skipped', 'reason': 'no_best_interactions',
                    'message': 'No best interactions found yet — keep watching!'}

        print(f"[HybridRecommender] Retraining on {len(best_rows)} best interactions …")

        try:
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            mappings  = self.mappings
            user_map  = mappings.get('user_id_to_idx', {})
            movie_map = mappings.get('movie_id_to_idx', {})

            x_user, x_movie, x_mood, y = [], [], [], []
            for row in best_rows:
                uid = user_map.get(str(row.get('user_id', '')), 0)
                mid = movie_map.get(str(row.get('movie_id', '')), 0)
                if uid == 0 or mid == 0:
                    continue

                mood_raw = str(row.get('emotion', row.get('detected_mood', 'calm'))).lower()
                moodid   = MOOD_TO_ID.get(mood_raw, 4)

                rating   = float(row.get('rating', 0) or 0)
                liked    = str(row.get('liked', '0')).strip().lower() in ('1', 'true', 'yes')
                # Target: use actual rating; floor at 4.0 so we only push scores up
                target   = max(rating, 4.0) if rating > 0 else (5.0 if liked else 4.0)
                target   = min(target, 5.0)

                x_user.append(uid);  x_movie.append(mid)
                x_mood.append(moodid); y.append(target / 5.0)   # normalise to [0,1]

            if not x_user:
                return {'status': 'skipped', 'reason': 'no_valid_best_data'}

            x_user  = torch.tensor(x_user,  dtype=torch.long)
            x_movie = torch.tensor(x_movie, dtype=torch.long)
            x_mood  = torch.tensor(x_mood,  dtype=torch.long)
            y_t     = torch.tensor(y,        dtype=torch.float32)

            dataset    = TensorDataset(x_user, x_movie, x_mood, y_t)
            dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

            optimizer = torch.optim.Adam(model.parameters(), lr=2e-4)   # lower LR for fine-tuning
            criterion = nn.MSELoss()

            model.train()
            epoch_loss = 0.0
            for epoch in range(epochs):
                epoch_loss = 0.0
                for bu, bm, bmood, by in dataloader:
                    optimizer.zero_grad()
                    pred = model(bu, bm, bmood).squeeze() if self.has_mood_emb else model(bu, bm).squeeze()
                    loss = criterion(pred, by)
                    loss.backward()
                    optimizer.step()
                    epoch_loss += loss.item()
                print(f"  Epoch {epoch+1}/{epochs} — loss: {epoch_loss:.4f}")
            model.eval()

            # Save checkpoint and hot-reload
            active_path = HYBRID_MODEL_PATH if os.path.exists(HYBRID_MODEL_PATH) else FALLBACK_MODEL_PATH
            torch.save(model.state_dict(), active_path)

            meta    = self._load_metadata()
            version = meta.get('model_version', 1) + 1
            meta['model_version']         = version
            meta['last_retrain_date']     = datetime.now().isoformat()
            meta['last_retrain_ts']       = int(time.time())
            meta['best_samples_trained']  = meta.get('best_samples_trained', 0) + len(best_rows)
            meta['training_loss']         = round(epoch_loss, 4)
            self._save_metadata(meta)

            backup = os.path.join(VERSIONS_DIR, f"hybrid_v{version}.pth")
            import shutil
            shutil.copy2(active_path, backup)

            self.reload_model()
            self._cache.invalidate()

            print(f"[HybridRecommender] ✓ Best-interaction retrain done → version v{version}")
            return {
                'status':              'ok',
                'version':             version,
                'best_samples_used':   len(best_rows),
                'epochs':              epochs,
                'training_loss':       round(epoch_loss, 4),
                'model_file':          os.path.basename(active_path),
                'timestamp':           datetime.now().isoformat(),
            }

        except Exception as e:
            import traceback
            traceback.print_exc()
            return {'status': 'error', 'error': str(e)}


# ──────────────────────────────────────────────────────────────────
# Singleton – loaded once at import time
# ──────────────────────────────────────────────────────────────────
_service_instance: Optional[HybridRecommenderService] = None
_init_lock = threading.Lock()

def get_hybrid_recommender() -> HybridRecommenderService:
    global _service_instance
    if _service_instance is None:
        with _init_lock:
            if _service_instance is None:
                _service_instance = HybridRecommenderService()
    return _service_instance
