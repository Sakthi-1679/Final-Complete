#!/usr/bin/env python3
"""
Import movies from full_movies_2025_2026.csv and generate movie database files
for both backend and frontend with proper movie_id preservation.
"""

import csv
import json
import os
from pathlib import Path

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
CSV_FILE = os.path.join(BASE_DIR, 'models', 'full_movies_2025_2026.csv')
BACKEND_OUTPUT = os.path.join(BASE_DIR, 'movie_database.json')
FRONTEND_OUTPUT = os.path.join(BASE_DIR, '..', 'frontend', 'generated_movies.ts')

# Emotion to mood mapping
EMOTION_TO_MOOD = {
    'sad': 'sad',
    'happy': 'happy',
    'warm': 'happy',
    'joyful': 'happy',
    'uplifting': 'happy',
    'tense': 'angry',
    'angry': 'angry',
    'intense': 'angry',
    'thrilling': 'angry',
    'calm': 'calm',
    'peaceful': 'calm',
    'relaxing': 'calm',
    'soothing': 'calm',
}


def convert_runtime_to_duration(minutes):
    """Convert runtime in minutes to duration string like '1h 33m'"""
    if not minutes:
        return '1h 30m'
    try:
        mins = int(minutes)
        hours = mins // 60
        remaining = mins % 60
        if hours == 0:
            return f"{remaining}m"
        elif remaining == 0:
            return f"{hours}h"
        else:
            return f"{hours}h {remaining}m"
    except (ValueError, TypeError):
        return '1h 30m'


def get_category_from_views(view_count):
    """Assign category based on view count"""
    try:
        views = int(view_count)
        if views > 500000:
            return 'trending'
        elif views > 200000:
            return 'top_rated'
        elif views > 100000:
            return 'new'
        else:
            return 'standard'
    except (ValueError, TypeError):
        return 'standard'


def emotion_to_mood(emotion_tag):
    """Convert emotion tag to mood"""
    if not emotion_tag:
        return 'happy'
    emotion_tag = str(emotion_tag).lower().strip()
    return EMOTION_TO_MOOD.get(emotion_tag, 'happy')


def generate_poster_url(movie_id):
    """Generate a unique poster URL using picsum.photos"""
    return f"https://picsum.photos/seed/movie{movie_id}/300/450?random={movie_id}"


def generate_backdrop_url(movie_id):
    """Generate a unique backdrop URL using picsum.photos"""
    return f"https://picsum.photos/seed/backdrop{movie_id}/1920/1080?random={movie_id}"


def create_backend_movie(row):
    """Create a backend movie format from CSV row (fully compatible with frontend Movie type)"""
    movie_id = row.get('movie_id', '').strip()
    view_count = int(row.get('view_count', 0))

    return {
        "id": movie_id,
        "title": row.get('title', f'Movie_{movie_id}').strip(),
        "description": f"{row.get('title', f'Movie_{movie_id}')} - {row.get('language', 'Unknown')} language",
        "mood": emotion_to_mood(row.get('emotion_tags')),
        "genres": [g.strip() for g in str(row.get('genres', '')).split('|') if g.strip()],
        "poster": generate_poster_url(movie_id),
        "backdrop": generate_backdrop_url(movie_id),
        "videoUrl": "https://cdn.coverr.co/videos/coverr-cinema-projector-5175/1080p.mp4",
        "rating": str(row.get('rating', '5.0')).strip(),
        "year": int(row.get('year', 2025)),
        "duration": convert_runtime_to_duration(row.get('runtime_min')),
        "category": get_category_from_views(view_count),
        "views": view_count,
        "createdAt": 1705622400000,
        "language": row.get('language', 'Unknown').strip(),
    }


def create_frontend_movie(row):
    """Create a frontend movie format from CSV row"""
    movie_id = row.get('movie_id', '').strip()
    view_count = int(row.get('view_count', 0))
    
    return {
        "id": movie_id,
        "title": row.get('title', f'Movie_{movie_id}').strip(),
        "description": f"{row.get('title', f'Movie_{movie_id}')} - {row.get('language', 'Unknown')} language",
        "genres": [g.strip() for g in str(row.get('genres', '')).split('|') if g.strip()],
        "year": int(row.get('year', 2025)),
        "duration": convert_runtime_to_duration(row.get('runtime_min')),
        "rating": str(row.get('rating', '5.0')).strip(),
        "poster": generate_poster_url(movie_id),
        "backdrop": generate_backdrop_url(movie_id),
        "videoUrl": "https://cdn.coverr.co/videos/coverr-cinema-projector-5175/1080p.mp4",
        "category": get_category_from_views(view_count),
        "views": view_count,
        "createdAt": 1705622400000,  # Fixed timestamp for reproducibility
    }


def main():
    """Main import function"""
    if not os.path.exists(CSV_FILE):
        print(f"Error: CSV file not found at {CSV_FILE}")
        return False

    print(f"Reading movies from {CSV_FILE}...")
    
    backend_movies = []
    frontend_movies = []
    
    try:
        with open(CSV_FILE, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get('movie_id'):
                    continue
                
                backend_movie = create_backend_movie(row)
                frontend_movie = create_frontend_movie(row)
                
                backend_movies.append(backend_movie)
                frontend_movies.append(frontend_movie)
    
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False

    print(f"Loaded {len(backend_movies)} movies from CSV")

    # Write backend database
    try:
        with open(BACKEND_OUTPUT, 'w', encoding='utf-8') as f:
            json.dump(backend_movies, f, indent=2, ensure_ascii=False)
        print(f"Backend movie database written to {BACKEND_OUTPUT}")
    except Exception as e:
        print(f"Error writing backend database: {e}")
        return False

    # Write frontend TypeScript file
    try:
        os.makedirs(os.path.dirname(FRONTEND_OUTPUT), exist_ok=True)
        with open(FRONTEND_OUTPUT, 'w', encoding='utf-8') as f:
            f.write("import { Movie } from './types';\n\n")
            f.write("export const INITIAL_MOVIES: Movie[] = ")
            # Format JSON with proper indentation
            json_str = json.dumps(frontend_movies, indent=2, ensure_ascii=False)
            f.write(json_str)
            f.write(";\n")
        print(f"Frontend movie database written to {FRONTEND_OUTPUT}")
    except Exception as e:
        print(f"Error writing frontend database: {e}")
        return False

    print(f"\nSuccessfully imported {len(frontend_movies)} movies!")
    print(f"  - Backend: {BACKEND_OUTPUT}")
    print(f"  - Frontend: {FRONTEND_OUTPUT}")
    
    return True


if __name__ == '__main__':
    success = main()
    exit(0 if success else 1)
