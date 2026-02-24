import csv
import json
import os
import pickle
import time
from datetime import datetime
from typing import Dict, List, Tuple

from services.recommender import get_all_movies, reload_movie_database

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MODELS_DIR = os.path.join(BASE_DIR, 'models')
INTERACTIONS_FILE = os.path.join(BASE_DIR, 'interactions.csv')
USER_EVENTS_FILE = os.path.join(BASE_DIR, 'user_events.csv')
METADATA_FILE = os.path.join(BASE_DIR, 'recommender_metadata.json')
MODEL_VERSIONS_DIR = os.path.join(MODELS_DIR, 'versions')

# Model files - use model.pth as specified in requirements
MODEL_PATH = os.path.join(MODELS_DIR, 'model.pth')
MAPPINGS_PATH = os.path.join(MODELS_DIR, 'mappings.pkl')

# Create versions directory if it doesn't exist
os.makedirs(MODEL_VERSIONS_DIR, exist_ok=True)


class EmotionRecommenderEngine:
    """Pluggable real-time recommender with manual incremental retraining using neural network."""

    def __init__(self):
        self.model = None
        self.mappings = None
        self.movie_database = []
        self._load_model()
        self._load_mappings()
        self._ensure_interactions_file()

    def _load_model(self):
        """Load the PyTorch neural network model."""
        if not os.path.exists(MODEL_PATH):
            print(f"Model file not found: {MODEL_PATH}")
            self.model = None
            return
        try:
            import torch
            import torch.nn as nn
            
            # Define the same model architecture used during training
            # Checkpoint was saved with: num_users=500, num_movies=800, embedding_dim=32
            # Network structure: embeddings -> concat -> Linear(64, 128) -> ReLU -> Linear(128, 1)
            class MovieRecommenderNN(nn.Module):
                def __init__(self, num_users, num_movies, embedding_dim=32):
                    super().__init__()
                    self.user_embedding = nn.Embedding(num_users, embedding_dim)
                    self.movie_embedding = nn.Embedding(num_movies, embedding_dim)
                    
                    # Simple two-layer network: 64 -> 128 -> 1
                    self.fc = nn.Sequential(
                        nn.Linear(embedding_dim * 2, 128),
                        nn.ReLU(),
                        nn.Linear(128, 1)
                    )
                
                def forward(self, user_ids, movie_ids):
                    user_emb = self.user_embedding(user_ids)
                    movie_emb = self.movie_embedding(movie_ids)
                    x = torch.cat([user_emb, movie_emb], dim=1)
                    return self.fc(x)
            
            # Load the model state dict - match checkpoint architecture
            self.model = MovieRecommenderNN(num_users=500, num_movies=800)
            self.model.load_state_dict(torch.load(MODEL_PATH, map_location='cpu'))
            self.model.eval()
            print(f"Model loaded successfully from {MODEL_PATH}")
        except Exception as e:
            print(f"Error loading model: {e}")
            self.model = None

    def _load_mappings(self):
        """Load user and movie ID mappings."""
        if not os.path.exists(MAPPINGS_PATH):
            print(f"Mappings file not found: {MAPPINGS_PATH}")
            self.mappings = {'user_id_to_idx': {}, 'movie_id_to_idx': {}, 'idx_to_movie_id': {}}
            return
        try:
            with open(MAPPINGS_PATH, 'rb') as f:
                self.mappings = pickle.load(f)
            print(f"Mappings loaded successfully from {MAPPINGS_PATH}")
        except Exception as e:
            print(f"Error loading mappings: {e}")
            self.mappings = {'user_id_to_idx': {}, 'movie_id_to_idx': {}, 'idx_to_movie_id': {}}

    def _ensure_interactions_file(self):
        if os.path.exists(INTERACTIONS_FILE):
            return
        with open(INTERACTIONS_FILE, 'w', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                'timestamp',
                'user_id',
                'movie_id',
                'movie_title',
                'emotion',
                'event_type',
                'rating',
                'liked',
            ])

    def _get_model_version(self) -> int:
        """Get current model version from metadata"""
        metadata = self._load_metadata()
        return metadata.get('model_version', 1)
    
    def _increment_model_version(self, metadata: Dict) -> int:
        """Increment and return the new model version"""
        new_version = metadata.get('model_version', 1) + 1
        metadata['model_version'] = new_version
        return new_version
    
    def _save_model_version(self, version: int):
        """Create a versioned backup of the current model"""
        if not os.path.exists(MODEL_PATH):
            return None
        
        try:
            version_name = f"model_v{version}.pth"
            version_path = os.path.join(MODEL_VERSIONS_DIR, version_name)
            
            import shutil
            shutil.copy2(MODEL_PATH, version_path)
            
            # Also save mappings version
            if os.path.exists(MAPPINGS_PATH):
                mappings_version_name = f"mappings_v{version}.pkl"
                mappings_version_path = os.path.join(MODEL_VERSIONS_DIR, mappings_version_name)
                shutil.copy2(MAPPINGS_PATH, mappings_version_path)
            
            print(f"✓ Model version {version} saved to {version_path}")
            return version_path
        except Exception as e:
            print(f"Error saving model version: {e}")
            return None
    
    def get_model_info(self) -> Dict:
        """Get current model information including version and stats"""
        metadata = self._load_metadata()
        version = metadata.get('model_version', 1)
        
        return {
            'version': version,
            'model_path': MODEL_PATH,
            'last_retrain_timestamp': metadata.get('last_retrain_timestamp', 0),
            'last_retrain_date': datetime.fromtimestamp(metadata.get('last_retrain_timestamp', 0)).isoformat() if metadata.get('last_retrain_timestamp') else 'Never',
            'trained_rows': metadata.get('last_processed_row', 0),
            'model_loaded': self.model is not None,
        }

    def _load_user_events(self) -> List[Dict]:
        """Load user events from user_events.csv"""
        if not os.path.exists(USER_EVENTS_FILE):
            return []
        
        events = []
        try:
            with open(USER_EVENTS_FILE, 'r', newline='', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    events.append(row)
        except Exception as e:
            print(f"Error loading user events: {e}")
        
        return events

    def _convert_user_events_to_interactions(self, user_events: List[Dict]) -> List[Dict]:
        """Convert user events to interaction format for training"""
        interactions = []

        def _to_bool(value) -> bool:
            if value is None:
                return False
            if isinstance(value, bool):
                return value
            if isinstance(value, (int, float)):
                return value != 0
            normalized = str(value).strip().lower()
            return normalized in {'1', 'true', 'yes', 'y'}
        
        for event in user_events:
            event_type = event.get('event_type', '')
            
            # Only process watch and rating events
            if event_type in ['WATCH', 'WATCH_END', 'RATING', 'LIKE']:
                interaction = {
                    'timestamp': event.get('timestamp', ''),
                    'user_id': event.get('user_id', 'anonymous'),
                    'movie_id': event.get('movie_id', ''),
                    'movie_title': event.get('movie_title', ''),
                    'emotion': event.get('detected_mood', ''),
                    'event_type': 'watch' if event_type in ['WATCH', 'WATCH_END'] else event_type.lower(),
                    'rating': float(event.get('rating') or 0),
                    'liked': _to_bool(event.get('liked')),
                }
                
                # Add watch duration as additional signal
                watch_duration = float(event.get('watch_duration') or 0)
                if watch_duration > 0:
                    # Longer watch = more engagement
                    interaction['rating'] = min(5.0, watch_duration / 60.0)  # Convert seconds to a rating-like score
                
                if interaction['movie_id']:
                    interactions.append(interaction)
        
        return interactions

    def _load_metadata(self) -> Dict:
        if not os.path.exists(METADATA_FILE):
            return {'last_retrain_timestamp': 0, 'last_processed_row': 0}
        try:
            with open(METADATA_FILE, 'r', encoding='utf-8') as file:
                return json.load(file)
        except Exception:
            return {'last_retrain_timestamp': 0, 'last_processed_row': 0}

    def _save_metadata(self, metadata: Dict):
        with open(METADATA_FILE, 'w', encoding='utf-8') as file:
            json.dump(metadata, file, indent=2)

    def log_interaction(
        self,
        user_id: str,
        movie_id: str,
        movie_title: str,
        emotion: str,
        event_type: str,
        rating: float = 0.0,
        liked: bool = False,
    ):
        self._ensure_interactions_file()
        with open(INTERACTIONS_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                int(time.time()),
                user_id,
                movie_id,
                movie_title,
                emotion,
                event_type,
                rating,
                int(liked),
            ])

    def _filter_movies_by_emotion(self, emotion: str) -> List[Dict]:
        """Filter movies based on emotion."""
        # Reload movie database to get latest movies
        self.movie_database = reload_movie_database()
        
        # If movie database is empty, return fallback mood-based recommendations
        if not self.movie_database:
            print(f"Movie database empty, returning fallback recommendations for {emotion}")
            return self._get_fallback_movies_by_emotion(emotion)
        
        emotion = (emotion or '').lower()
        emotion_map = {
            'sad': ['sad', 'happy'],
            'happy': ['happy'],
            'calm': ['happy', 'calm'],
            'angry': ['angry'],
        }
        targets = emotion_map.get(emotion, ['happy'])
        
        # Filter movies by mood tag
        filtered = [movie for movie in self.movie_database if movie.get('mood') in targets]
        
        # If no movies match mood tags, return all movies
        if not filtered:
            print(f"No movies with mood tags for {emotion}, returning all movies")
            return self.movie_database[:20]  # Return first 20 for performance
        
        return filtered
    
    def _get_fallback_movies_by_emotion(self, emotion: str) -> List[Dict]:
        """Get fallback movie recommendations when database is empty"""
        # Mock movie objects for demonstration
        emotion = (emotion or '').lower()
        
        genre_map = {
            'happy': 'Comedy',
            'sad': 'Drama',
            'calm': 'Documentary',
            'angry': 'Action',
            'stressed': 'Comedy',
            'excited': 'Action',
        }
        
        genre = genre_map.get(emotion, 'Drama')
        
        # Return mock movies
        movies = [
            {'id': f'movie_{i}', 'title': f'Sample {genre} Movie {i}', 'genres': [genre], 'mood': emotion}
            for i in range(6)
        ]
        return movies

    def _build_ids(self, movies: List[Dict]) -> Tuple[Dict[str, int], Dict[str, int]]:
        """Build user and movie ID mappings from interactions and movies."""
        # Use mappings from file or build from scratch
        # Clamp to model capacity: 500 users, 800 movies
        MAX_USERS = 500
        MAX_MOVIES = 800
        
        movie_idx = {}
        for i, movie in enumerate(movies):
            if i + 1 >= MAX_MOVIES:
                break  # Exceeds model capacity
            mid = str(movie.get('id', ''))
            movie_idx[mid] = i + 1  # Reserve 0 for unseen

        users = set()
        if os.path.exists(INTERACTIONS_FILE):
            with open(INTERACTIONS_FILE, 'r', newline='', encoding='utf-8') as file:
                reader = csv.DictReader(file)
                for row in reader:
                    if row.get('user_id'):
                        users.add(row['user_id'])
        
        # Sort and limit users to model capacity
        sorted_users = sorted(users)[:MAX_USERS - 1]
        user_idx = {user: i + 1 for i, user in enumerate(sorted_users)}  # reserve 0 for unseen
        return user_idx, movie_idx

    def _fallback_scores(self, user_id: str, movies: List[Dict]) -> List[Tuple[float, Dict]]:
        """Fallback scoring when model is not available."""
        popularity = {movie['id']: 0.0 for movie in movies}
        user_bias = {movie['id']: 0.0 for movie in movies}

        with open(INTERACTIONS_FILE, 'r', newline='', encoding='utf-8') as file:
            reader = csv.DictReader(file)
            for row in reader:
                mid = row.get('movie_id')
                if mid not in popularity:
                    continue
                rating = float(row.get('rating') or 0)
                liked = float(row.get('liked') or 0)
                event_type = row.get('event_type') or ''
                base = 1.0 if event_type == 'watch' else 0.5
                popularity[mid] += base + rating + liked
                if row.get('user_id') == user_id:
                    user_bias[mid] += 1.5 + rating + liked

        scored = []
        for movie in movies:
            score = popularity.get(movie['id'], 0.0) + user_bias.get(movie['id'], 0.0)
            scored.append((score, movie))
        return scored

    def recommend(self, user_id: str, emotion: str, top_k: int = 5) -> List[Dict]:
        """Get movie recommendations based on user and emotion."""
        movies = self._filter_movies_by_emotion(emotion)
        if not movies:
            return []

        # If model is not loaded, use fallback
        if self.model is None:
            scored = self._fallback_scores(user_id, movies)
            scored.sort(key=lambda item: item[0], reverse=True)
            return [movie for _, movie in scored[:top_k]]

        # Use neural network model for predictions
        try:
            user_idx, movie_idx = self._build_ids(movies)
            uid = user_idx.get(user_id, 0)
            
            # Get all movie indices that exist in our database
            preds = []
            for movie in movies:
                mid = str(movie.get('id', ''))
                movie_index = movie_idx.get(mid, 0)
                
                if movie_index > 0 and uid > 0:
                    try:
                        import torch
                        user_tensor = torch.tensor([uid], dtype=torch.long)
                        movie_tensor = torch.tensor([movie_index], dtype=torch.long)
                        
                        with torch.no_grad():
                            score = float(self.model(user_tensor, movie_tensor).item())
                    except Exception:
                        score = 0.0
                else:
                    score = 0.0
                
                preds.append((score, movie))
            
            preds.sort(key=lambda item: item[0], reverse=True)
            return [movie for _, movie in preds[:top_k]]
            
        except Exception as e:
            print(f"Error in neural prediction: {e}")
            scored = self._fallback_scores(user_id, movies)
            scored.sort(key=lambda item: item[0], reverse=True)
            return [movie for _, movie in scored[:top_k]]

    def retrain_incremental(self, epochs: int = 1) -> Dict:
        """
        Retrain the model incrementally on new interaction data.
        This includes both interactions.csv and user_events.csv data.
        """
        if self.model is None:
            self._load_model()
        if self.model is None:
            return {
                'status': 'skipped',
                'reason': 'model_not_loaded',
                'message': f'No model loaded from {MODEL_PATH}',
            }

        metadata = self._load_metadata()
        last_processed = int(metadata.get('last_processed_row', 0))

        # Load interactions from both files
        all_interactions = []
        
        # Load from interactions.csv
        with open(INTERACTIONS_FILE, 'r', newline='', encoding='utf-8') as file:
            rows = list(csv.DictReader(file))
            all_interactions.extend(rows)
        
        # Load and convert user_events.csv
        user_events = self._load_user_events()
        converted_events = self._convert_user_events_to_interactions(user_events)
        all_interactions.extend(converted_events)

        new_rows = all_interactions[last_processed:]
        if not new_rows:
            return {
                'status': 'skipped',
                'reason': 'no_new_data',
                'last_processed_row': last_processed,
                'message': 'No new interactions to train on',
            }

        try:
            import numpy as np
            import torch
            import torch.nn as nn
            from torch.utils.data import DataLoader, TensorDataset

            # Reload movie database
            self.movie_database = reload_movie_database()
            
            # Build mappings from current movies - with model capacity limits
            MAX_USERS = 500
            MAX_MOVIES = 800
            
            all_movie_ids = [str(m.get('id', '')) for m in self.movie_database][:MAX_MOVIES - 1]
            movie_id_to_idx = {mid: i + 1 for i, mid in enumerate(all_movie_ids)}
            
            # Get all unique users from interactions
            all_users = set()
            all_movie_ids = set()
            
            for row in all_interactions:
                if row.get('user_id'):
                    all_users.add(row['user_id'])
                if row.get('movie_id'):
                    all_movie_ids.add(row['movie_id'])
            
            # Limit to model capacity
            sorted_users = sorted(all_users)[:MAX_USERS - 1]
            sorted_movies = sorted(all_movie_ids)[:MAX_MOVIES - 1]
            
            user_id_to_idx = {uid: i + 1 for i, uid in enumerate(sorted_users)}
            movie_id_to_idx = {mid: i + 1 for i, mid in enumerate(sorted_movies)}
            
            x_user, x_movie, y = [], [], []
            for row in new_rows:
                uid = user_id_to_idx.get(row.get('user_id', ''), 0)
                mid = movie_id_to_idx.get(row.get('movie_id', ''), 0)
                
                if uid == 0 or mid == 0:
                    continue
                    
                event_type = row.get('event_type') or ''
                rating = float(row.get('rating') or 0)
                liked = float(row.get('liked') or 0)
                target = (1.0 if event_type == 'watch' else 0.5) + rating + liked
                
                x_user.append(uid)
                x_movie.append(mid)
                y.append(target)

            if len(x_user) == 0:
                return {
                    'status': 'skipped',
                    'reason': 'no_valid_data',
                    'message': 'No valid interaction data for training',
                }

            # Create tensors and dataloader
            x_user = torch.tensor(x_user, dtype=torch.long)
            x_movie = torch.tensor(x_movie, dtype=torch.long)
            y = torch.tensor(y, dtype=torch.float32)

            dataset = TensorDataset(x_user, x_movie, y)
            dataloader = DataLoader(dataset, batch_size=32, shuffle=True)

            # Define optimizer and loss
            optimizer = torch.optim.Adam(self.model.parameters(), lr=0.001)
            criterion = nn.MSELoss()

            # Train
            self.model.train()
            for epoch in range(epochs):
                for batch_user, batch_movie, batch_y in dataloader:
                    optimizer.zero_grad()
                    predictions = self.model(batch_user, batch_movie).squeeze()
                    loss = criterion(predictions, batch_y)
                    loss.backward()
                    optimizer.step()

            # Save the updated model - overwrites model.pth as required
            torch.save(self.model.state_dict(), MODEL_PATH)
            print(f"Model retrained and saved to {MODEL_PATH}")

            # Update mappings
            with open(MAPPINGS_PATH, 'wb') as f:
                pickle.dump({
                    'user_id_to_idx': user_id_to_idx,
                    'movie_id_to_idx': movie_id_to_idx,
                    'idx_to_movie_id': {v: k for k, v in movie_id_to_idx.items()}
                }, f)

            # Update metadata with versioning
            metadata['last_retrain_timestamp'] = int(time.time())
            metadata['last_processed_row'] = len(rows)
            
            # Increment model version and save backup
            new_version = self._increment_model_version(metadata)
            self._save_metadata(metadata)
            self._save_model_version(new_version)
            
            print(f"✓ Model version incremented to v{new_version}")

            return {
                'status': 'ok',
                'message': f'Model retrained successfully (v{new_version})',
                'trained_on_rows': len(new_rows),
                'last_processed_row': len(rows),
                'model_version': new_version,
                'model_path': MODEL_PATH,
            }
        except Exception as exc:
            return {
                'status': 'error',
                'error': str(exc),
            }
