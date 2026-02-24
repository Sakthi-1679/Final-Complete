import csv
import json
import os
from typing import Dict, List

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MOVIE_DB_FILE = os.path.join(BASE_DIR, 'movie_database.json')


def load_movie_database() -> List[Dict]:
    """Load movies from the movie database JSON file."""
    if not os.path.exists(MOVIE_DB_FILE):
        return []
    try:
        with open(MOVIE_DB_FILE, 'r', encoding='utf-8') as f:
            return json.load(f)
    except Exception:
        return []


# Load movies from database (empty list if not yet imported)
MOVIE_DB = load_movie_database()


def reload_movie_database():
    """Reload movie database from file."""
    global MOVIE_DB
    MOVIE_DB = load_movie_database()
    return MOVIE_DB


def get_all_movies() -> List[Dict]:
    """Get all movies from the database."""
    return MOVIE_DB


def get_movie_by_id(movie_id: str) -> Dict | None:
    """Get a specific movie by ID."""
    for movie in MOVIE_DB:
        if str(movie.get('id')) == str(movie_id):
            return movie
    return None


def get_movies_by_mood(mood: str) -> List[Dict]:
    """
    Get movies filtered by mood/emotion.
    Maps emotion tags to appropriate movies.
    """
    normalized = (mood or "").lower()
    mood_targets = {
        "sad": ["sad", "happy"],
        "happy": ["happy"],
        "angry": ["angry"],
        "calm": ["happy", "calm"],
        "stressed": ["happy", "calm"],
    }

    targets = mood_targets.get(normalized, ["happy"])
    recommendations = [movie for movie in MOVIE_DB if movie.get("mood") in targets]

    return recommendations[:6] if recommendations else MOVIE_DB[:6]
