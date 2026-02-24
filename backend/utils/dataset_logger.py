import csv
import os
import time

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
LOG_FILE = os.path.abspath(os.path.join(BASE_DIR, '..', 'mood_log.csv'))
EXPECTED_HEADERS = [
    'timestamp',
    'mood',
    'confidence',
    'suggested_movies',
    'watched_movie',
    'watched_movie_genre',
]


def _ensure_schema():
    os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)

    if not os.path.isfile(LOG_FILE):
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as file:
            csv.writer(file).writerow(EXPECTED_HEADERS)
        return

    with open(LOG_FILE, 'r', newline='', encoding='utf-8') as file:
        rows = list(csv.reader(file))

    if not rows:
        with open(LOG_FILE, 'w', newline='', encoding='utf-8') as file:
            csv.writer(file).writerow(EXPECTED_HEADERS)
        return

    current_header = rows[0]
    if current_header == EXPECTED_HEADERS:
        return

    migrated_rows = []
    for row in rows[1:]:
        mood = row[0] if len(row) > 0 else ''
        confidence = row[1] if len(row) > 1 else ''
        watched_movie = row[4] if len(row) > 4 else ''
        migrated_rows.append([
            '', mood, confidence, '', watched_movie, ''
        ])

    with open(LOG_FILE, 'w', newline='', encoding='utf-8') as file:
        writer = csv.writer(file)
        writer.writerow(EXPECTED_HEADERS)
        writer.writerows(migrated_rows)


def initialize_log():
    try:
        _ensure_schema()
    except Exception as exc:
        print('Log init error:', exc)


def append_log(mood='', confidence='', suggested_movies='', watched_movie='', watched_movie_genre=''):
    try:
        _ensure_schema()
        with open(LOG_FILE, 'a', newline='', encoding='utf-8') as file:
            writer = csv.writer(file)
            writer.writerow([
                int(time.time()),
                mood,
                confidence,
                suggested_movies,
                watched_movie,
                watched_movie_genre,
            ])
    except Exception as exc:
        print('Log write error:', exc)


def log_prediction(mood, confidence, suggested_movies):
    titles = []
    for movie in suggested_movies or []:
        if isinstance(movie, dict) and movie.get('title'):
            titles.append(movie['title'])
        elif isinstance(movie, str):
            titles.append(movie)
    append_log(
        mood=mood,
        confidence=confidence,
        suggested_movies=' | '.join(titles),
        watched_movie='',
        watched_movie_genre='',
    )


def log_watched_movie(watched_movie, mood='', suggested_movies='', watched_movie_genre=''):
    append_log(
        mood=mood,
        confidence='',
        suggested_movies=suggested_movies,
        watched_movie=watched_movie,
        watched_movie_genre=watched_movie_genre,
    )


def log_data(mood, confidence):
    """Backward-compatible alias for older imports/usages."""
    log_prediction(mood, confidence, suggested_movies=[])
