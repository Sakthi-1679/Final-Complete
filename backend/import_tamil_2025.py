#!/usr/bin/env python3
"""
Import 50 Tamil 2025 movies from tamil_2025_50_movies_full.csv
into MySQL, movie_database.json, and generated_movies.ts
"""

import csv
import json
import os
import sys
import random

# Add backend directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, BASE_DIR)

CSV_FILE   = os.path.join(BASE_DIR, 'New folder', 'tamil_2025_50_movies_full.csv')
DB_JSON    = os.path.join(BASE_DIR, 'movie_database.json')
TS_FILE    = os.path.join(BASE_DIR, '..', 'frontend', 'generated_movies.ts')

SAMPLE_VIDEO = 'https://cdn.coverr.co/videos/coverr-cinema-projector-5175/1080p.mp4'

# Genre mapping by title keywords (best-effort for known Tamil films)
TITLE_GENRE_MAP = {
    'Coolie':           ['Action', 'Thriller'],
    'Mahavatar':        ['Action', 'Mythology'],
    'Good Bad Ugly':    ['Action', 'Comedy'],
    'Dragon':           ['Action', 'Adventure'],
    'Vidaamuyarchi':    ['Action', 'Thriller'],
    'Kuberaa':          ['Crime', 'Drama'],
    'Dude':             ['Comedy', 'Romance'],
    'Madharaasi':       ['Comedy', 'Drama'],
    'Thug Life':        ['Action', 'Crime'],
    'Tourist Family':   ['Comedy', 'Family'],
    'Lara':             ['Drama', 'Romance'],
    'Seesaw':           ['Drama', 'Thriller'],
    'Xtreme':           ['Action', 'Thriller'],
    'Vanangaan':        ['Action', 'Drama'],
    'Nesippaya':        ['Romance', 'Drama'],
    'Tharunam':         ['Drama'],
    'Kuzhanthaigal':    ['Family', 'Drama'],
    'Mr. Housekeeping': ['Comedy', 'Family'],
    'Vallan':           ['Action', 'Thriller'],
    'Ring Ring':        ['Comedy', 'Romance'],
    'Kaadhal':          ['Romance', 'Drama'],
    'Baby and Baby':    ['Comedy', 'Family'],
    'Dinasari':         ['Comedy', 'Drama'],
    'Fire':             ['Action', 'Drama'],
    'Kanneera':         ['Emotional', 'Drama'],
    'Otha Votu':        ['Comedy', 'Political'],
    'Nilavuku':         ['Romance', 'Drama'],
    'Piranthanaal':     ['Family', 'Comedy'],
    'Kooran':           ['Thriller', 'Horror'],
    'Sabdham':          ['Thriller', 'Horror'],
    'Gentlewoman':      ['Drama', 'Thriller'],
    'Kingston':         ['Action', 'Crime'],
    'Murmur':           ['Drama', 'Thriller'],
    'Niram Marum':      ['Drama', 'Romance'],
    'Yamakaathaghi':    ['Action', 'Drama'],
    'Konjam Kadhal':    ['Romance', 'Comedy'],
    'Maadan Kodai':     ['Family', 'Comedy'],
    'Perusu':           ['Drama', 'Comedy'],
    'Robber':           ['Action', 'Crime'],
    'Sweetheart':       ['Romance', 'Comedy'],
    'Varunan':          ['Action', 'Thriller'],
    'Pei Kottu':        ['Horror', 'Thriller'],
    'Trauma':           ['Thriller', 'Drama'],
    'The Door':         ['Thriller', 'Horror'],
    'Test':             ['Drama', 'Sport'],
    'Ten Hours':        ['Thriller', 'Action'],
    'Vallamai':         ['Action', 'Drama'],
    'En Kadhale':       ['Romance', 'Drama'],
    'Gajaana':          ['Comedy', 'Drama'],
}

MOOD_BY_GENRE = {
    'Action':     'angry',
    'Thriller':   'angry',
    'Horror':     'angry',
    'Crime':      'angry',
    'Drama':      'sad',
    'Emotional':  'sad',
    'Romance':    'happy',
    'Comedy':     'happy',
    'Family':     'happy',
    'Adventure':  'happy',
    'Sport':      'happy',
    'Political':  'calm',
    'Mythology':  'calm',
}

CATEGORY_BY_ID = {
    range(1001, 1006): 'trending',   # top blockbusters
    range(1006, 1016): 'new',
    range(1016, 1051): 'standard',
}

def get_genres(title: str):
    for keyword, genres in TITLE_GENRE_MAP.items():
        if keyword.lower() in title.lower():
            return genres
    return ['Drama']

def get_mood(genres):
    for g in genres:
        m = MOOD_BY_GENRE.get(g)
        if m:
            return m
    return 'happy'

def get_category(movie_id: int):
    if 1001 <= movie_id <= 1005:
        return 'trending'
    if 1006 <= movie_id <= 1015:
        return 'new'
    return 'standard'

def random_rating():
    return str(round(random.uniform(6.0, 9.2), 1))

def random_duration():
    h = random.randint(2, 2)
    m = random.randint(5, 55)
    return f"{h}h {m}m"

def random_views(category):
    if category == 'trending':
        return random.randint(600_000, 1_200_000)
    if category == 'new':
        return random.randint(150_000, 500_000)
    return random.randint(20_000, 149_000)

def load_existing_json(path):
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return []
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)

def read_csv():
    movies = []
    with open(CSV_FILE, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            mid   = row['movie_id'].strip()
            title = row['title'].strip()
            year  = int(row.get('year', 2025) or 2025)
            genres   = get_genres(title)
            mood     = get_mood(genres)
            category = get_category(int(mid))
            views    = random_views(category)
            rating   = random_rating()
            duration = random_duration()
            poster   = row.get('poster_url', '').strip()
            backdrop = row.get('backdrop_url', '').strip() or poster
            trailer  = row.get('trailer_url', '').strip()
            video    = row.get('video_file_url', '').strip() or SAMPLE_VIDEO

            movies.append({
                'id':          mid,
                'title':       title,
                'description': f"{title} - Tamil language {year} film",
                'genres':      genres,
                'year':        year,
                'duration':    duration,
                'rating':      rating,
                'poster':      poster,
                'backdrop':    backdrop,
                'videoUrl':    video,
                'trailerUrl':  trailer,
                'category':    category,
                'views':       views,
                'mood':        mood,
                'language':    'Tamil',
                'createdAt':   1737000000000,
            })
    return movies

def save_backend_json(new_movies):
    existing = load_existing_json(DB_JSON)
    existing_ids = {str(m.get('id')) for m in existing}
    to_add = [m for m in new_movies if str(m['id']) not in existing_ids]

    # Build backend-format (lighter, no videoUrl key rename)
    backend_new = []
    for m in to_add:
        backend_new.append({
            'id':          m['id'],
            'title':       m['title'],
            'description': m['description'],
            'genres':      m['genres'],
            'year':        m['year'],
            'duration':    m['duration'],
            'rating':      m['rating'],
            'poster':      m['poster'],
            'backdrop':    m['backdrop'],
            'video_url':   m['videoUrl'],
            'trailer_url': m.get('trailerUrl', ''),
            'category':    m['category'],
            'views':       m['views'],
            'mood':        m['mood'],
            'language':    m['language'],
        })

    combined = existing + backend_new
    with open(DB_JSON, 'w', encoding='utf-8') as f:
        json.dump(combined, f, indent=2, ensure_ascii=False)
    print(f"[JSON] {len(backend_new)} new movies appended → {len(combined)} total in movie_database.json")
    return len(backend_new)

def save_frontend_ts(new_movies):
    # Read existing TS and extract the JSON array
    existing_ts_movies = []
    if os.path.exists(TS_FILE):
        with open(TS_FILE, 'r', encoding='utf-8') as f:
            content = f.read()
        # Find the array that follows '= ' (the assignment), not the one in Movie[]
        assign_idx = content.find('= [')
        if assign_idx != -1:
            start = assign_idx + 2  # points to '['
            end   = content.rfind(']')
            if end > start:
                try:
                    existing_ts_movies = json.loads(content[start:end+1])
                except Exception as e:
                    print(f"[TS] Warning: could not parse existing TS array: {e}")

    existing_ids = {str(m.get('id')) for m in existing_ts_movies}
    to_add = [m for m in new_movies if str(m['id']) not in existing_ids]

    combined = to_add + existing_ts_movies   # new movies first
    with open(TS_FILE, 'w', encoding='utf-8') as f:
        f.write("import { Movie } from './types';\n\n")
        f.write("export const INITIAL_MOVIES: Movie[] = ")
        f.write(json.dumps(combined, indent=2, ensure_ascii=False))
        f.write(";\n")
    print(f"[TS]   {len(to_add)} new movies prepended → {len(combined)} total in generated_movies.ts")
    return len(to_add)

def seed_to_mysql(new_movies):
    try:
        from utils.database import add_movie_to_db, get_movie_by_id_from_db
        added = 0
        skipped = 0
        for m in new_movies:
            existing = get_movie_by_id_from_db(str(m['id']))
            if existing:
                skipped += 1
                continue
            if add_movie_to_db(m):
                added += 1
        print(f"[MySQL] {added} movies inserted, {skipped} already existed")
        return added
    except Exception as e:
        print(f"[MySQL] Warning – could not insert into MySQL: {e}")
        print("         (movie_database.json and generated_movies.ts were still updated)")
        return 0

def main():
    print("=" * 60)
    print("Importing 50 Tamil 2025 movies")
    print("=" * 60)

    if not os.path.exists(CSV_FILE):
        print(f"ERROR: CSV not found at {CSV_FILE}")
        sys.exit(1)

    movies = read_csv()
    print(f"Read {len(movies)} movies from CSV\n")

    json_count  = save_backend_json(movies)
    ts_count    = save_frontend_ts(movies)
    mysql_count = seed_to_mysql(movies)

    print("\n" + "=" * 60)
    print(f"Done!  JSON: +{json_count}  TS: +{ts_count}  MySQL: +{mysql_count}")
    print("=" * 60)

if __name__ == '__main__':
    main()
