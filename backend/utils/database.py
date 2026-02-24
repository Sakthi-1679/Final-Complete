"""MySQL Database utilities for StreamFlix"""
import mysql.connector
import os
from datetime import datetime
from typing import List, Dict, Optional, Tuple

# Load environment variables from .env file FIRST before anything else
try:
    from dotenv import load_dotenv
    # Explicitly load .env from backend directory
    env_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
    if os.path.exists(env_path):
        load_dotenv(env_path, override=True)
        print(f"[INFO] Loaded environment from: {env_path}")
    else:
        print(f"[INFO] .env file not found at {env_path}, using system environment")
except ImportError:
    print("[WARN] python-dotenv not installed, using system environment variables")

# Database configuration with environment variables
DB_CONFIG = {
    'host': os.getenv('DB_HOST', 'localhost'),
    'user': os.getenv('DB_USER', 'root'),
    'password': os.getenv('DB_PASSWORD', ''),
    'database': os.getenv('DB_NAME', 'hybrid_recommender_db'),
    'port': int(os.getenv('DB_PORT', '3306')),
    'autocommit': True
}

# Debug: Show connection config (without password)
print(f"[DB Config] Host: {DB_CONFIG['host']}, User: {DB_CONFIG['user']}, DB: {DB_CONFIG['database']}")

# Track if database is available
_db_available = None

def check_db_connection() -> bool:
    """Check if database is available"""
    global _db_available
    
    if _db_available is not None:
        return _db_available
    
    try:
        print(f"[DB] Attempting connection to {DB_CONFIG['host']}:{DB_CONFIG['port']} as {DB_CONFIG['user']}")
        # Try to connect without database first to check MySQL server
        db_config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
        conn = mysql.connector.connect(**db_config_no_db)
        conn.close()
        _db_available = True
        print("[SUCCESS] MySQL server connection successful")
        return True
    except Exception as e:
        _db_available = False
        print(f"[WARN] MySQL database not available: {e}")
        print("   Continuing without database. Install and run MySQL to enable full functionality.")
        return False

def get_connection():
    """Get MySQL database connection"""
    try:
        conn = mysql.connector.connect(**DB_CONFIG)
        return conn
    except mysql.connector.Error as err:
        print(f"Database connection error: {err}")
        return None

def init_database():
    """Initialize database tables"""
    if not check_db_connection():
        print("[SKIP] Database initialization skipped (MySQL not available)")
        return False
    
    # First, create database if it doesn't exist
    try:
        db_config_no_db = {k: v for k, v in DB_CONFIG.items() if k != 'database'}
        conn = mysql.connector.connect(**db_config_no_db)
        cursor = conn.cursor()
        
        db_name = DB_CONFIG['database']
        print(f"[DB] Creating database '{db_name}' if not exists...")
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db_name}")
        print(f"[SUCCESS] Database '{db_name}' ready")
        
        cursor.close()
        conn.close()
    except Exception as e:
        print(f"[ERROR] Error creating database: {e}")
        return False
    
    # Now connect to the database and create tables
    conn = get_connection()
    if not conn:
        print("Failed to connect to database")
        return False
    
    cursor = conn.cursor()
    
    try:
        # Users table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS users (
                user_id INT AUTO_INCREMENT PRIMARY KEY,
                username VARCHAR(255) UNIQUE NOT NULL,
                email VARCHAR(255) UNIQUE NOT NULL,
                password_hash VARCHAR(255) NOT NULL,
                name VARCHAR(255),
                subscription VARCHAR(50) DEFAULT 'free',
                role VARCHAR(50) DEFAULT 'user',
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)
        
        # Mood detection logs
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mood_logs (
                mood_log_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                detected_mood VARCHAR(50) NOT NULL,
                confidence FLOAT,
                model_version VARCHAR(50),
                detected_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Movie interactions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movie_interactions (
                interaction_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                movie_id VARCHAR(255) NOT NULL,
                movie_title VARCHAR(500),
                mood_when_watched VARCHAR(50),
                rating FLOAT,
                liked BOOLEAN DEFAULT FALSE,
                watch_duration INT,
                watched_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # Recommendations history
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS recommendations (
                recommendation_id INT AUTO_INCREMENT PRIMARY KEY,
                user_id INT NOT NULL,
                mood VARCHAR(50) NOT NULL,
                recommended_movies JSON,
                model_version VARCHAR(50),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (user_id) REFERENCES users(user_id) ON DELETE CASCADE
            )
        """)
        
        # AI Mood Model metadata
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS mood_model_metadata (
                model_id INT AUTO_INCREMENT PRIMARY KEY,
                model_version VARCHAR(50) UNIQUE NOT NULL,
                model_name VARCHAR(255),
                model_path VARCHAR(500),
                accuracy FLOAT,
                trained_on_samples INT,
                training_date TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Movies catalogue
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS movies (
                id VARCHAR(255) PRIMARY KEY,
                title VARCHAR(500) NOT NULL,
                description TEXT,
                genres JSON,
                year INT,
                duration VARCHAR(50),
                rating VARCHAR(50),
                poster MEDIUMTEXT,
                backdrop MEDIUMTEXT,
                video_url MEDIUMTEXT,
                trailer_url MEDIUMTEXT,
                poster_file VARCHAR(500) DEFAULT '',
                backdrop_file VARCHAR(500) DEFAULT '',
                video_file_path VARCHAR(500) DEFAULT '',
                category VARCHAR(50) DEFAULT 'standard',
                views INT DEFAULT 0,
                mood VARCHAR(50),
                language VARCHAR(100),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
            )
        """)

        print("[SUCCESS] Database tables initialized successfully")

        # Migrate existing column types to MEDIUMTEXT (safe to run multiple times)
        for col in ('poster', 'backdrop', 'video_url', 'trailer_url'):
            try:
                cursor.execute(f"ALTER TABLE movies MODIFY COLUMN {col} MEDIUMTEXT")
            except Exception:
                pass  # column may already be MEDIUMTEXT

        # Add new file-path columns if they don't exist yet
        for col_def in (
            "poster_file VARCHAR(500) NOT NULL DEFAULT ''",
            "backdrop_file VARCHAR(500) NOT NULL DEFAULT ''",
            "video_file_path VARCHAR(500) NOT NULL DEFAULT ''",
        ):
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE movies ADD COLUMN {col_def}")
                print(f"[DB] Added column: {col_name}")
            except Exception:
                pass  # column already exists

        # ── STEP 2: Hybrid recommender schema additions ───────────────

        # interactions table: add columns needed for hybrid retraining
        interactions_additions = [
            "mood VARCHAR(50) DEFAULT NULL",
            "rating FLOAT DEFAULT NULL",
            "liked TINYINT(1) DEFAULT 0",
            "watch_time INT DEFAULT 0",
            "recommended_rank_position INT DEFAULT NULL",
        ]
        for col_def in interactions_additions:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE movie_interactions ADD COLUMN {col_def}")
                print(f"[DB] movie_interactions: added column '{col_name}'")
            except Exception:
                pass  # already exists

        # movies table: popularity & stats columns
        movies_additions = [
            "popularity_score FLOAT DEFAULT 0",
            "average_rating FLOAT DEFAULT 0",
            "total_views INT DEFAULT 0",
            "total_likes INT DEFAULT 0",
            "total_dislikes INT DEFAULT 0",
        ]
        for col_def in movies_additions:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE movies ADD COLUMN {col_def}")
                print(f"[DB] movies: added column '{col_name}'")
            except Exception:
                pass

        # users table: activity & preference columns
        users_additions = [
            "last_active_at TIMESTAMP NULL DEFAULT NULL",
            "total_watch_time INT DEFAULT 0",
            "average_rating_given FLOAT DEFAULT 0",
            "preferred_genre_distribution JSON DEFAULT NULL",
        ]
        for col_def in users_additions:
            col_name = col_def.split()[0]
            try:
                cursor.execute(f"ALTER TABLE users ADD COLUMN {col_def}")
                print(f"[DB] users: added column '{col_name}'")
            except Exception:
                pass

        # mood_logs table: detection_source column
        try:
            cursor.execute("ALTER TABLE mood_logs ADD COLUMN detection_source VARCHAR(20) DEFAULT 'face'")
            print("[DB] mood_logs: added column 'detection_source'")
        except Exception:
            pass

        # model_metadata table for hybrid model versions
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS hybrid_model_metadata (
                id INT AUTO_INCREMENT PRIMARY KEY,
                model_version INT NOT NULL DEFAULT 1,
                training_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                training_data_size INT DEFAULT 0,
                weak_samples_used INT DEFAULT 0,
                training_loss FLOAT DEFAULT NULL,
                validation_loss FLOAT DEFAULT NULL,
                active_model TINYINT(1) DEFAULT 1,
                model_file VARCHAR(255) DEFAULT 'hybrid_model.pth',
                notes TEXT DEFAULT NULL
            )
        """)

        print("[DB] ✓ Hybrid recommender schema additions complete")
        return True
        
    except Exception as e:
        print(f"[ERROR] Error initializing database: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def add_user(username: str, email: str, password_hash: str, name: str = None) -> Optional[int]:
    """Add new user to database"""
    conn = get_connection()
    if not conn:
        return None
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO users (username, email, password_hash, name) VALUES (%s, %s, %s, %s)",
            (username, email, password_hash, name or username)
        )
        user_id = cursor.lastrowid
        conn.commit()
        print(f"[SUCCESS] User '{username}' created with ID: {user_id}")
        return user_id
    except Exception as e:
        print(f"Error adding user: {e}")
        return None
    finally:
        cursor.close()
        conn.close()

def log_mood_detection(user_id: int, mood: str, confidence: float, model_version: str = "v3"):
    """Log mood detection to database"""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            "INSERT INTO mood_logs (user_id, detected_mood, confidence, model_version) VALUES (%s, %s, %s, %s)",
            (user_id, mood, confidence, model_version)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error logging mood: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def log_movie_interaction(user_id: int, movie_id: str, movie_title: str, mood: str, 
                          rating: float = None, liked: bool = False, watch_duration: int = 0):
    """Log movie interaction to database"""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO movie_interactions 
               (user_id, movie_id, movie_title, mood_when_watched, rating, liked, watch_duration) 
               VALUES (%s, %s, %s, %s, %s, %s, %s)""",
            (user_id, movie_id, movie_title, mood, rating, liked, watch_duration)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error logging movie interaction: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def log_hybrid_interaction(user_id: int, movie_id: str, movie_title: str,
                           mood: str = None, rating: float = None,
                           liked: bool = False, watch_time: int = 0,
                           recommended_rank_position: int = None,
                           mood_confidence: float = None,
                           detection_source: str = 'face'):
    """
    Log a rich hybrid interaction used for retraining.
    Writes to movie_interactions with all new hybrid columns.
    """
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO movie_interactions
               (user_id, movie_id, movie_title, mood_when_watched,
                rating, liked, watch_duration,
                mood, watch_time, recommended_rank_position)
               VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)""",
            (user_id, movie_id, movie_title, mood,
             rating, int(bool(liked)), watch_time,
             mood, watch_time, recommended_rank_position)
        )
        conn.commit()
        # Update user last_active_at
        try:
            cursor.execute(
                "UPDATE users SET last_active_at = NOW() WHERE user_id = %s",
                (user_id,)
            )
            conn.commit()
        except Exception:
            pass
        return True
    except Exception as e:
        print(f"Error logging hybrid interaction: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_movie_stats(movie_id: str, liked: bool = None, rating: float = None,
                       increment_views: bool = False):
    """Update denormalised stats columns on the movies table."""
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        if increment_views:
            cursor.execute(
                "UPDATE movies SET views = views + 1, total_views = total_views + 1 WHERE id = %s",
                (movie_id,)
            )
        if liked is True:
            cursor.execute(
                "UPDATE movies SET total_likes = total_likes + 1 WHERE id = %s", (movie_id,)
            )
        elif liked is False:
            cursor.execute(
                "UPDATE movies SET total_dislikes = total_dislikes + 1 WHERE id = %s", (movie_id,)
            )
        if rating is not None:
            # Rolling average update (simplified)
            cursor.execute(
                """UPDATE movies SET
                   average_rating = (average_rating * total_views + %s) / (total_views + 1),
                   popularity_score = (total_likes - total_dislikes) / GREATEST(total_views, 1)
                   WHERE id = %s""",
                (rating, movie_id)
            )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating movie stats: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def log_model_version(version: int, training_data_size: int = 0,
                      weak_samples: int = 0, training_loss: float = None,
                      model_file: str = 'hybrid_model.pth'):
    """Record a new hybrid model version in hybrid_model_metadata."""
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        # Deactivate previous versions
        cursor.execute("UPDATE hybrid_model_metadata SET active_model = 0")
        cursor.execute(
            """INSERT INTO hybrid_model_metadata
               (model_version, training_data_size, weak_samples_used,
                training_loss, active_model, model_file)
               VALUES (%s, %s, %s, %s, 1, %s)""",
            (version, training_data_size, weak_samples, training_loss, model_file)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error logging model version: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def save_recommendations(user_id: int, mood: str, movie_ids: List[str], model_version: str = "v3"):
    """Save recommendations history to database"""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO recommendations 
               (user_id, mood, recommended_movies, model_version) 
               VALUES (%s, %s, %s, %s)""",
            (user_id, mood, str(movie_ids), model_version)
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error saving recommendations: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_user_mood_history(user_id: int, limit: int = 10) -> List[Dict]:
    """Get recent mood detections for a user"""
    conn = get_connection()
    if not conn:
        return []
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT detected_mood, confidence, detected_at 
               FROM mood_logs 
               WHERE user_id = %s 
               ORDER BY detected_at DESC 
               LIMIT %s""",
            (user_id, limit)
        )
        results = cursor.fetchall()
        return results or []
    except Exception as e:
        print(f"Error fetching mood history: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def get_user_movie_preferences(user_id: int) -> Dict:
    """Get user's movie preferences based on interactions"""
    conn = get_connection()
    if not conn:
        return {}
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            """SELECT movie_title, COUNT(*) as view_count, AVG(rating) as avg_rating
               FROM movie_interactions 
               WHERE user_id = %s 
               GROUP BY movie_title 
               ORDER BY view_count DESC""",
            (user_id,)
        )
        results = cursor.fetchall()
        return results or []
    except Exception as e:
        print(f"Error fetching user preferences: {e}")
        return []
    finally:
        cursor.close()
        conn.close()

def register_mood_model(model_version: str, model_name: str, model_path: str, 
                       accuracy: float = None, trained_samples: int = 0):
    """Register a mood detection model in database"""
    conn = get_connection()
    if not conn:
        return False
    
    cursor = conn.cursor()
    try:
        cursor.execute(
            """INSERT INTO mood_model_metadata 
               (model_version, model_name, model_path, accuracy, trained_on_samples, training_date) 
               VALUES (%s, %s, %s, %s, %s, %s)""",
            (model_version, model_name, model_path, accuracy, trained_samples, datetime.now())
        )
        conn.commit()
        print(f"[SUCCESS] Mood model '{model_version}' registered")
        return True
    except Exception as e:
        print(f"Error registering model: {e}")
        return False
    finally:
        cursor.close()
        conn.close()

def get_mood_model_info(model_version: str = "v3") -> Optional[Dict]:
    """Get mood model metadata"""
    conn = get_connection()
    if not conn:
        return None
    
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute(
            "SELECT * FROM mood_model_metadata WHERE model_version = %s",
            (model_version,)
        )
        result = cursor.fetchone()
        return result
    except Exception as e:
        print(f"Error fetching model info: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


# ==================== MOVIE CRUD ====================

def _movie_row_to_dict(row: Dict) -> Dict:
    """Normalise a DB row into a frontend-compatible Movie dict."""
    genres = row.get('genres')
    if isinstance(genres, str):
        try:
            import json as _json
            genres = _json.loads(genres)
        except Exception:
            genres = [genres]
    return {
        'id': str(row['id']),
        'title': row.get('title', ''),
        'description': row.get('description', ''),
        'genres': genres or [],
        'year': row.get('year', 2025),
        'duration': row.get('duration', ''),
        'rating': str(row.get('rating', '')),
        # Resolve effective URLs: local file path wins over external URL
        'poster':   row.get('poster_file') or row.get('poster', ''),
        'backdrop': row.get('backdrop_file') or row.get('backdrop', ''),
        'videoUrl': row.get('video_file_path') or row.get('video_url', ''),
        # Expose raw columns so the editor can repopulate both fields
        'posterUrl':       row.get('poster', ''),
        'posterFilePath':  row.get('poster_file', ''),
        'backdropUrl':     row.get('backdrop', ''),
        'backdropFilePath':row.get('backdrop_file', ''),
        'videoUrlRaw':     row.get('video_url', ''),
        'videoFilePath':   row.get('video_file_path', ''),
        'trailerUrl': row.get('trailer_url', ''),
        'category': row.get('category', 'standard'),
        'views': row.get('views', 0),
        'mood': row.get('mood', 'happy'),
        'language': row.get('language', ''),
        'createdAt': int(row['created_at'].timestamp() * 1000) if row.get('created_at') else 0,
    }


def get_all_movies_from_db() -> List[Dict]:
    """Return all movies from the movies table."""
    conn = get_connection()
    if not conn:
        return []
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM movies ORDER BY created_at DESC")
        rows = cursor.fetchall()
        return [_movie_row_to_dict(r) for r in rows]
    except Exception as e:
        print(f"Error fetching movies: {e}")
        return []
    finally:
        cursor.close()
        conn.close()


def get_movie_by_id_from_db(movie_id: str) -> Optional[Dict]:
    """Return a single movie by ID."""
    conn = get_connection()
    if not conn:
        return None
    cursor = conn.cursor(dictionary=True)
    try:
        cursor.execute("SELECT * FROM movies WHERE id = %s", (movie_id,))
        row = cursor.fetchone()
        return _movie_row_to_dict(row) if row else None
    except Exception as e:
        print(f"Error fetching movie {movie_id}: {e}")
        return None
    finally:
        cursor.close()
        conn.close()


def add_movie_to_db(movie: Dict) -> bool:
    """Insert or replace a movie record."""
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        import json as _json
        genres_json = _json.dumps(movie.get('genres', []))
        cursor.execute(
            """INSERT INTO movies
               (id, title, description, genres, year, duration, rating,
                poster, backdrop, video_url, trailer_url, category, views, mood, language,
                poster_file, backdrop_file, video_file_path)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
               ON DUPLICATE KEY UPDATE
                 title=VALUES(title), description=VALUES(description),
                 genres=VALUES(genres), year=VALUES(year), duration=VALUES(duration),
                 rating=VALUES(rating), poster=VALUES(poster), backdrop=VALUES(backdrop),
                 video_url=VALUES(video_url), trailer_url=VALUES(trailer_url),
                 category=VALUES(category), views=VALUES(views),
                 mood=VALUES(mood), language=VALUES(language),
                 poster_file=VALUES(poster_file), backdrop_file=VALUES(backdrop_file),
                 video_file_path=VALUES(video_file_path)""",
            (
                str(movie.get('id', '')),
                movie.get('title', ''),
                movie.get('description', ''),
                genres_json,
                movie.get('year', 2025),
                movie.get('duration', ''),
                str(movie.get('rating', '')),
                movie.get('poster', ''),
                movie.get('backdrop', ''),
                movie.get('videoUrl', movie.get('video_url', '')),
                movie.get('trailerUrl', movie.get('trailer_url', '')),
                movie.get('category', 'standard'),
                int(movie.get('views', 0)),
                movie.get('mood', 'happy'),
                movie.get('language', ''),
                movie.get('posterFile', movie.get('poster_file', '')),
                movie.get('backdropFile', movie.get('backdrop_file', '')),
                movie.get('videoFilePath', movie.get('video_file_path', '')),
            )
        )
        conn.commit()
        return True
    except Exception as e:
        print(f"Error adding movie: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def update_movie_in_db(movie_id: str, data: Dict) -> bool:
    """Update fields of an existing movie."""
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        import json as _json
        fields = []
        values = []
        # Standard scalar columns
        mapping = {
            'title': 'title', 'description': 'description', 'year': 'year',
            'duration': 'duration', 'rating': 'rating', 'trailerUrl': 'trailer_url',
            'category': 'category', 'views': 'views', 'mood': 'mood', 'language': 'language',
        }
        for key, col in mapping.items():
            if key in data:
                fields.append(f"{col} = %s")
                values.append(data[key])
        if 'genres' in data:
            fields.append("genres = %s")
            values.append(_json.dumps(data['genres']))

        # ── URL vs File mutual exclusivity ───────────────────────────────────
        # Poster
        if 'posterFile' in data:          # local file uploaded
            fields += ["poster_file = %s", "poster = %s"]
            values += [data['posterFile'], '']          # store file path, clear URL
        elif 'poster' in data:            # external URL provided
            fields += ["poster = %s", "poster_file = %s"]
            values += [data['poster'], '']              # store URL, clear file path

        # Backdrop
        if 'backdropFile' in data:        # local file uploaded
            fields += ["backdrop_file = %s", "backdrop = %s"]
            values += [data['backdropFile'], '']        # store file path, clear URL
        elif 'backdrop' in data:          # external URL provided
            fields += ["backdrop = %s", "backdrop_file = %s"]
            values += [data['backdrop'], '']            # store URL, clear file path

        # Video
        if 'videoFilePath' in data:       # local file uploaded
            fields += ["video_file_path = %s", "video_url = %s"]
            values += [data['videoFilePath'], '']       # store file path, clear URL
        elif 'videoUrl' in data:          # external URL provided
            fields += ["video_url = %s", "video_file_path = %s"]
            values += [data['videoUrl'], '']            # store URL, clear file path

        if not fields:
            return True
        values.append(movie_id)
        cursor.execute(f"UPDATE movies SET {', '.join(fields)} WHERE id = %s", values)
        conn.commit()
        return cursor.rowcount > 0 or True
    except Exception as e:
        print(f"Error updating movie {movie_id}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_movie_from_db(movie_id: str) -> bool:
    """Delete a single movie by ID."""
    conn = get_connection()
    if not conn:
        return False
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM movies WHERE id = %s", (movie_id,))
        conn.commit()
        return cursor.rowcount > 0
    except Exception as e:
        print(f"Error deleting movie {movie_id}: {e}")
        return False
    finally:
        cursor.close()
        conn.close()


def delete_movies_bulk(movie_ids: List[str]) -> int:
    """Delete multiple movies by IDs. Returns number deleted."""
    if not movie_ids:
        return 0
    conn = get_connection()
    if not conn:
        return 0
    cursor = conn.cursor()
    try:
        placeholders = ','.join(['%s'] * len(movie_ids))
        cursor.execute(f"DELETE FROM movies WHERE id IN ({placeholders})", movie_ids)
        conn.commit()
        return cursor.rowcount
    except Exception as e:
        print(f"Error bulk deleting movies: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def get_movies_count_from_db() -> int:
    """Return total number of movies stored in DB."""
    conn = get_connection()
    if not conn:
        return 0
    cursor = conn.cursor()
    try:
        cursor.execute("SELECT COUNT(*) FROM movies")
        result = cursor.fetchone()
        return result[0] if result else 0
    except Exception as e:
        print(f"Error counting movies: {e}")
        return 0
    finally:
        cursor.close()
        conn.close()


def seed_movies_from_json(json_path: str) -> int:
    """Bulk-insert movies from a JSON file (movie_database.json). Returns count inserted."""
    import json as _json
    if not os.path.exists(json_path):
        print(f"[SEED] JSON file not found: {json_path}")
        return 0
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            movies = _json.load(f)
        if not movies:
            return 0
        count = 0
        for m in movies:
            if add_movie_to_db(m):
                count += 1
        print(f"[SEED] Seeded {count}/{len(movies)} movies into MySQL")
        return count
    except Exception as e:
        print(f"[SEED] Error seeding movies: {e}")
        return 0
