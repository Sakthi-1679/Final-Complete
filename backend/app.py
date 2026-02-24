import sys, io
# Force UTF-8 output on Windows (prevents charmap errors from Unicode in log msgs)
if sys.stdout and hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace', line_buffering=True)
if sys.stderr and hasattr(sys.stderr, 'buffer'):
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace', line_buffering=True)

from flask import Flask, request, jsonify
from flask_cors import CORS
import traceback
import csv
import io as _io
import json
import os
import time
from pathlib import Path
from functools import wraps
from datetime import datetime

from services.ai_engine import MultimodalEngine
from services.recommender import get_movies_by_mood
from services.recommender_engine import EmotionRecommenderEngine
from services.continuous_learning_pipeline import get_pipeline, run_pipeline_check, get_pipeline_status
# ── Hybrid recommender (industry-level) ──────────────────────────
from services.hybrid_recommender_service import get_hybrid_recommender
# ── Weekly best-interaction retrain scheduler ─────────────────────
from pipeline.retrain_scheduler import start_scheduler, scheduler_status, trigger_retrain_now
from utils.file_utils import save_input_files, cleanup
from utils.dataset_logger import initialize_log, log_prediction, log_watched_movie
from utils.database import (
    init_database, log_mood_detection, log_movie_interaction,
    log_hybrid_interaction, update_movie_stats, log_model_version,
    save_recommendations, get_mood_model_info, register_mood_model,
    get_all_movies_from_db, get_movie_by_id_from_db,
    add_movie_to_db, update_movie_in_db, delete_movie_from_db,
    delete_movies_bulk, get_movies_count_from_db, seed_movies_from_json
)
from auth import (
    register_user, login_user, verify_token, get_user_by_username,
    upgrade_subscription, get_user_stats, get_all_users_admin, delete_user,
    SUBSCRIPTION_PLANS
)
from services.realtime_recommender import get_realtime_recommender

app = Flask(__name__)
app.config['MAX_CONTENT_LENGTH'] = 500 * 1024 * 1024  # 500 MB

# Uploads folder — files uploaded from admin panel are stored here and served publicly
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

CORS(app, resources={r"/*": {"origins": "*"}})

# Serve uploaded files publicly
from flask import send_from_directory
@app.route('/uploads/<path:filename>')
def serve_upload(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

# Initialize database
print("\n[DB] Initializing MySQL Database...")
init_database()

# Auto-seed movies into MySQL if the table is empty or incomplete
_MOVIE_DB_JSON = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'movie_database.json')
_current_movie_count = get_movies_count_from_db()
try:
    import json as _json
    with open(_MOVIE_DB_JSON) as _f:
        _expected_count = len(_json.load(_f))
except Exception:
    _expected_count = 800

if _current_movie_count < _expected_count:
    print(f"[DB] Movies table has {_current_movie_count}/{_expected_count} — seeding from movie_database.json...")
    seeded = seed_movies_from_json(_MOVIE_DB_JSON)
    print(f"[DB] Seeded {seeded} movies into MySQL (total now {get_movies_count_from_db()})")
else:
    print(f"[DB] Movies table complete: {_current_movie_count} movies")

# Load AI mood detection engine with new model
print("\n[AI] Loading AI Mood Detection Engine...")
engine = MultimodalEngine()
recommender_engine = EmotionRecommenderEngine()
initialize_log()

# ── Hybrid recommender: load once at startup ──────────────────────
print("\n[Hybrid] Loading Hybrid Recommender (industry-level)...")
_hybrid_svc = get_hybrid_recommender()
# Inject the full movie catalogue so the recommender doesn't need to re-read the file
try:
    _all_movies_for_hybrid = get_all_movies_from_db()
    _hybrid_svc.set_movie_db(_all_movies_for_hybrid)
    print(f"[Hybrid] ✓ Movie catalogue injected ({len(_all_movies_for_hybrid)} movies)")
except Exception as _e:
    print(f"[Hybrid] Movie catalogue injection warning: {_e}")

# ── Start weekly weak-interaction retrain scheduler ───────────────
print("\n[Scheduler] Starting weekly retrain scheduler...")
start_scheduler()

# User Events CSV for comprehensive tracking
USER_EVENTS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'user_events.csv')

USER_EVENTS_HEADERS = [
    'timestamp',
    'event_type',
    'user_id',
    'movie_id',
    'movie_title',
    'search_query',
    'detected_mood',
    'watch_duration',
    'rating',
    'liked',
    'genre',
]

def _ensure_user_events_file():
    """Ensure user events CSV file exists with proper headers"""
    if os.path.exists(USER_EVENTS_FILE):
        return
    with open(USER_EVENTS_FILE, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(USER_EVENTS_HEADERS)

_ensure_user_events_file()


# ==================== AUTHENTICATION DECORATOR ====================

def token_required(f):
    """Decorator to protect routes with JWT authentication"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({"error": "Missing authorization token"}), 401
        
        try:
            token = token.replace('Bearer ', '')
            success, payload = verify_token(token)
            if not success:
                return jsonify({"error": "Invalid or expired token"}), 401
            
            request.user = payload
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": "Token verification failed"}), 401
    
    return decorated

def admin_required(f):
    """Decorator to protect admin routes"""
    @wraps(f)
    def decorated(*args, **kwargs):
        token = request.headers.get('Authorization')
        
        if not token:
            return jsonify({"error": "Missing authorization token"}), 401
        
        try:
            token = token.replace('Bearer ', '')
            success, payload = verify_token(token)
            if not success:
                return jsonify({"error": "Invalid or expired token"}), 401
            
            if payload.get('role') not in ['admin', 'manager']:
                return jsonify({"error": "Admin access required"}), 403
            
            request.user = payload
            return f(*args, **kwargs)
        except Exception as e:
            return jsonify({"error": "Token verification failed"}), 401
    
    return decorated


# ── Simple in-process rate limiter for /hybrid/recommend ─────────
import collections
_rate_store: dict = collections.defaultdict(list)
_RATE_LIMIT = 20       # max requests
_RATE_WINDOW = 60      # per 60 seconds

def _rate_limited():
    """Return True if the caller has exceeded the rate limit."""
    ip = request.remote_addr or 'unknown'
    now = time.time()
    hits = _rate_store[ip]
    # Purge old entries
    _rate_store[ip] = [t for t in hits if now - t < _RATE_WINDOW]
    if len(_rate_store[ip]) >= _RATE_LIMIT:
        return True
    _rate_store[ip].append(now)
    return False


# ==================== AUTHENTICATION ROUTES ====================

@app.route('/auth/register', methods=['POST'])
def register():
    """Register a new user"""
    try:
        data = request.get_json()
        
        username = data.get('username', '').strip()
        email = data.get('email', '').strip()
        password = data.get('password', '').strip()
        name = data.get('name', '').strip()
        
        if not all([username, email, password, name]):
            return jsonify({"error": "Missing required fields"}), 400
        
        if len(password) < 6:
            return jsonify({"error": "Password must be at least 6 characters"}), 400
        
        success, message = register_user(username, email, password, name)
        
        if success:
            return jsonify({"message": message, "success": True}), 201
        else:
            return jsonify({"error": message, "success": False}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auth/login', methods=['POST'])
def login():
    """Login user and return JWT token"""
    import sys
    with open('flask_debug.log', 'a') as f:
        f.write(f"[FLASK] /auth/login called at {datetime.now()}\n")
        f.flush()
    try:
        with open('flask_debug.log', 'a') as f:
            f.write("[FLASK] Getting JSON data...\n")
            f.flush()
        data = request.get_json()
        username = data.get('username', '').strip()
        password = data.get('password', '').strip()
        
        if not username or not password:
            return jsonify({"error": "Username and password required"}), 400
        
        with open('flask_debug.log', 'a') as f:
            f.write(f"[FLASK] Calling login_user({username})...\n")
            f.flush()
        success, message, user_data = login_user(username, password)
        with open('flask_debug.log', 'a') as f:
            f.write(f"[FLASK] login_user returned success={success}\n")
            f.flush()
        
        if success:
            return jsonify({
                "success": True,
                "token": user_data['token'],
                "user": user_data['user']
            }), 200
        else:
            return jsonify({"error": message, "success": False}), 401
    
    except Exception as e:
        import traceback
        with open('flask_debug.log', 'a') as f:
            f.write(f"[FLASK] ERROR: {e}\n")
            f.write(traceback.format_exc())
            f.flush()
        return jsonify({"error": str(e)}), 500

@app.route('/auth/profile', methods=['GET'])
@token_required
def get_profile():
    """Get current user profile"""
    try:
        username = request.user.get('username')
        user = get_user_by_username(username)
        
        if not user:
            return jsonify({"error": "User not found"}), 404
        
        return jsonify({
            "username": user.get("username"),
            "email": user.get("email"),
            "name": user.get("name"),
            "role": user.get("role"),
            "subscription": user.get("subscription"),
            "created_at": user.get("created_at"),
            "last_login": user.get("last_login")
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auth/upgrade', methods=['POST'])
@token_required
def upgrade():
    """Upgrade user subscription"""
    try:
        data = request.get_json()
        plan = data.get('plan', '').strip()
        username = request.user.get('username')
        
        if plan not in SUBSCRIPTION_PLANS:
            return jsonify({"error": "Invalid subscription plan"}), 400
        
        success, message = upgrade_subscription(username, plan)
        
        if success:
            return jsonify({"message": message, "success": True}), 200
        else:
            return jsonify({"error": message, "success": False}), 400
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/auth/subscription-plans', methods=['GET'])
def get_plans():
    """Get all subscription plans"""
    try:
        return jsonify(SUBSCRIPTION_PLANS), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== ADMIN ROUTES ====================

@app.route('/admin/stats', methods=['GET'])
@admin_required
def admin_stats():
    """Get admin dashboard statistics"""
    try:
        stats = get_user_stats()
        return jsonify(stats), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users', methods=['GET'])
@admin_required
def list_users():
    """Get all users for admin"""
    try:
        users = get_all_users_admin()
        return jsonify({"users": users}), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@app.route('/admin/users/<username>', methods=['DELETE'])
@admin_required
def delete_user_route(username):
    """Delete a user"""
    try:
        success, message = delete_user(username)
        if success:
            return jsonify({"message": message, "success": True}), 200
        else:
            return jsonify({"error": message, "success": False}), 400
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ==================== MOVIES API ====================

@app.route('/movies', methods=['GET'])
def list_movies():
    """Get all movies (public)"""
    try:
        movies = get_all_movies_from_db()
        return jsonify({"movies": movies, "count": len(movies)}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/movies/<movie_id>', methods=['GET'])
def get_movie(movie_id):
    """Get a single movie by ID (public)"""
    try:
        movie = get_movie_by_id_from_db(movie_id)
        if not movie:
            return jsonify({"error": "Movie not found"}), 404
        return jsonify(movie), 200
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/admin/movies', methods=['POST'])
@admin_required
def create_movie():
    """Add a new movie (admin only)"""
    try:
        data = request.get_json(silent=True) or {}
        if not data.get('id') or not data.get('title'):
            return jsonify({"error": "id and title are required"}), 400
        success = add_movie_to_db(data)
        if success:
            return jsonify({"message": "Movie added", "id": data['id']}), 201
        return jsonify({"error": "Failed to add movie"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/admin/movies/<movie_id>', methods=['PUT'])
@admin_required
def edit_movie(movie_id):
    """Update an existing movie (admin only)"""
    try:
        data = request.get_json(silent=True) or {}
        success = update_movie_in_db(movie_id, data)
        if success:
            return jsonify({"message": "Movie updated", "id": movie_id}), 200
        return jsonify({"error": "Failed to update movie"}), 500
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/admin/movies/<movie_id>', methods=['DELETE'])
@admin_required
def remove_movie(movie_id):
    """Delete a movie (admin only)"""
    try:
        success = delete_movie_from_db(movie_id)
        if success:
            return jsonify({"message": "Movie deleted", "id": movie_id}), 200
        return jsonify({"error": "Movie not found"}), 404
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/admin/movies/bulk-delete', methods=['POST'])
@admin_required
def bulk_delete_movies():
    """Delete multiple movies at once (admin only)"""
    try:
        data = request.get_json(silent=True) or {}
        ids = data.get('ids', [])
        if not ids:
            return jsonify({"error": "No movie IDs provided"}), 400
        deleted = delete_movies_bulk(ids)
        return jsonify({"message": f"Deleted {deleted} movies", "deleted": deleted}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


@app.route('/admin/upload', methods=['POST'])
@admin_required
def upload_media_file():
    """Upload an image or video file and return its public URL."""
    try:
        import uuid
        file = request.files.get('file')
        if not file or file.filename == '':
            return jsonify({'error': 'No file provided'}), 400

        # Safe filename: uuid + original extension
        original_name = file.filename or 'upload'
        ext = os.path.splitext(original_name)[1].lower() or ''
        safe_name = f"{uuid.uuid4().hex}{ext}"
        save_path = os.path.join(app.config['UPLOAD_FOLDER'], safe_name)
        file.save(save_path)

        # Build public URL
        host = request.host_url.rstrip('/')
        public_url = f"{host}/uploads/{safe_name}"
        return jsonify({'url': public_url, 'filename': safe_name}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500


@app.route('/admin/movies/import', methods=['POST'])
@admin_required
def import_movies_to_db():
    """Re-seed the movies table from movie_database.json (admin only)"""
    try:
        count = seed_movies_from_json(_MOVIE_DB_JSON)
        return jsonify({"message": f"Imported {count} movies", "count": count}), 200
    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500


def health_check():
    return jsonify({"status": "online"})


@app.route('/live_predict', methods=['POST'])
def live_predict():
    temp_files = []
    try:
        video = request.files.get('video_frame')
        audio = request.files.get('audio_sample')

        if not video or not audio:
            return jsonify({"error": "camera or microphone missing"}), 400

        img_path, audio_path = save_input_files(video, audio)
        temp_files = [img_path, audio_path]

        analysis = engine.analyze(img_path, audio_path)
        movies = get_movies_by_mood(analysis['mood'])
        log_prediction(analysis['mood'], analysis['confidence'], movies)

        return jsonify(
            {
                "mood": analysis['mood'],
                "confidence": analysis['confidence'],
                "reasoning": analysis['reasoning'],
                "movies": movies,
            }
        )

    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500
    finally:
        cleanup(temp_files)


@app.route('/log_watch', methods=['POST'])
def log_watch():
    try:
        payload = request.get_json(silent=True) or {}
        watched_movie = payload.get('watched_movie', '').strip()
        mood = payload.get('mood', '').strip()
        suggested_movies = payload.get('suggested_movies', '').strip()
        watched_movie_genre = payload.get('watched_movie_genre', '').strip()

        if not watched_movie:
            return jsonify({"error": "watched_movie is required"}), 400

        log_watched_movie(
            watched_movie=watched_movie,
            mood=mood,
            suggested_movies=suggested_movies,
            watched_movie_genre=watched_movie_genre,
        )
        return jsonify({"status": "logged"})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({"error": str(exc)}), 500


@app.route('/recommend', methods=['POST'])
def recommend_movies():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get('user_id', '')).strip()
        emotion = str(payload.get('emotion', '')).strip().lower()

        if not user_id:
            return jsonify({'error': 'user_id is required'}), 400
        if emotion not in {'sad', 'happy', 'calm', 'angry'}:
            return jsonify({'error': 'emotion must be one of: sad, happy, calm, angry'}), 400

        movies = recommender_engine.recommend(user_id=user_id, emotion=emotion, top_k=5)
        return jsonify({
            'user_id': user_id,
            'emotion': emotion,
            'recommendations': movies,
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/log_interaction', methods=['POST'])
def log_interaction():
    try:
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get('user_id', '')).strip()
        movie_id = str(payload.get('movie_id', '')).strip()
        movie_title = str(payload.get('movie_title', '')).strip()
        emotion = str(payload.get('emotion', '')).strip().lower()
        event_type = str(payload.get('event_type', 'watch')).strip().lower()
        rating = float(payload.get('rating', 0) or 0)
        liked = bool(payload.get('liked', False))

        if not user_id or not movie_id or not movie_title:
            return jsonify({'error': 'user_id, movie_id and movie_title are required'}), 400
        if emotion and emotion not in {'sad', 'happy', 'calm', 'angry'}:
            return jsonify({'error': 'emotion must be one of: sad, happy, calm, angry'}), 400
        if event_type not in {'watch', 'rating', 'like'}:
            return jsonify({'error': 'event_type must be one of: watch, rating, like'}), 400

        recommender_engine.log_interaction(
            user_id=user_id,
            movie_id=movie_id,
            movie_title=movie_title,
            emotion=emotion,
            event_type=event_type,
            rating=rating,
            liked=liked,
        )
        return jsonify({'status': 'logged'})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/retrain_recommender', methods=['POST'])
def retrain_recommender():
    try:
        payload = request.get_json(silent=True) or {}
        epochs = int(payload.get('epochs', 1))
        result = recommender_engine.retrain_incremental(epochs=max(1, epochs))
        return jsonify(result)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/mood/recommendations', methods=['POST'])
def mood_recommendations():
    """Get dynamic mood-based movie recommendations from trained model"""
    try:
        payload = request.get_json(silent=True) or {}
        user_id = str(payload.get('user_id', 'guest')).strip()
        mood = str(payload.get('mood', 'calm')).strip().lower()
        top_k = int(payload.get('top_k', 6))
        
        # Valid moods
        valid_moods = ['sad', 'happy', 'calm', 'angry', 'excited', 'stressed', 'neutral']
        if mood not in valid_moods:
            mood = 'calm'
        
        # Get recommendations from model
        movies = recommender_engine.recommend(user_id=user_id, emotion=mood, top_k=top_k)
        
        # Log the mood detection (CSV)
        log_prediction(
            mood=mood,
            confidence=0.95,
            suggested_movies=movies
        )
        
        # Log to MySQL database
        try:
            # Try to get numeric user_id if stored in DB
            numeric_user_id = 1  # Default to 1 for guest
            if user_id != 'guest':
                # In production, extract numeric ID from auth token or user table
                numeric_user_id = hash(user_id) % 999999 + 1
            
            log_mood_detection(numeric_user_id, mood, 0.95, recommender_engine._get_model_version())
            
            if movies:
                movie_ids = [str(m.get('id', f'movie_{i}')) for i, m in enumerate(movies)]
                save_recommendations(numeric_user_id, mood, movie_ids, recommender_engine._get_model_version())
        except Exception as db_err:
            print(f"Database logging warning: {db_err}")
            # Continue even if DB logging fails
        
        return jsonify({
            'user_id': user_id,
            'mood': mood,
            'recommendations': movies,
            'count': len(movies),
            'model_version': recommender_engine._get_model_version()
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/model/info', methods=['GET'])
def model_info():
    """Get current model information including version and stats"""
    try:
        info = recommender_engine.get_model_info()
        return jsonify(info)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/model/versions', methods=['GET'])
def model_versions():
    """Get list of all saved model versions"""
    try:
        import os
        versions_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
            'models',
            'versions'
        )
        
        versions = []
        if os.path.exists(versions_dir):
            for filename in sorted(os.listdir(versions_dir)):
                if filename.startswith('model_v') and filename.endswith('.pth'):
                    version_num = filename.replace('model_v', '').replace('.pth', '')
                    filepath = os.path.join(versions_dir, filename)
                    file_size = os.path.getsize(filepath)
                    file_time = os.path.getmtime(filepath)
                    
                    versions.append({
                        'version': int(version_num),
                        'filename': filename,
                        'size_kb': round(file_size / 1024, 2),
                        'timestamp': file_time
                    })
        
        return jsonify({
            'current_version': recommender_engine._get_model_version(),
            'versions': sorted(versions, key=lambda x: x['version'], reverse=True),
            'total_versions': len(versions)
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


# CSV Import helper functions
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


def parse_csv_movies(csv_content):
    """Parse CSV content and return movie data"""
    movies = []
    reader = csv.DictReader(io.StringIO(csv_content))
    
    for row in reader:
        movie_id = row.get('movie_id', '').strip() or str(len(movies) + 1)
        
        # Get video URL - prefer video_file_url, fallback to backup_url
        video_url = row.get('video_file_url', '').strip() or row.get('backup_url', '').strip()
        
        # If trailer_url is a YouTube search result, try to extract video ID or use as-is
        trailer_url = row.get('trailer_url', '').strip()
        
        # Use video_file_url or backup_url as the video URL
        # If they contain YouTube, use the trailer_url instead for embedding
        if not video_url or video_url == 'https://sample-videos.com/video123/mp4/720/big_buck_bunny_720p_1mb.mp4':
            # Use sample video if no valid URL, or try to use trailer
            if 'youtube.com' in trailer_url or 'youtu.be' in trailer_url:
                video_url = trailer_url
            else:
                video_url = video_url or 'https://cdn.coverr.co/videos/coverr-cinema-projector-5175/1080p.mp4'
        
        view_count = int(row.get('view_count', 0)) if row.get('view_count') else 0
        
        movie = {
            "id": movie_id,
            "title": row.get('title', f'Movie_{movie_id}').strip(),
            "description": f"{row.get('title', f'Movie_{movie_id}')} - {row.get('language', 'Tamil')} language",
            "genres": ['Drama'],  # Default genre for Tamil movies
            "year": int(row.get('year', 2025)),
            "duration": '2h 30m',  # Default duration
            "rating": '8.0',  # Default rating
            "poster": row.get('poster_url', '').strip() or generate_poster_url(movie_id),
            "backdrop": row.get('backdrop_url', '').strip() or generate_backdrop_url(movie_id),
            "videoUrl": video_url,
            "trailerUrl": trailer_url,
            "category": get_category_from_views(view_count),
            "views": view_count,
            "createdAt": 1705622400000,
        }
        movies.append(movie)
    
    return movies


@app.route('/import_movies_csv', methods=['POST'])
def import_movies_csv():
    """Import movies from CSV file and persist them to the database"""
    try:
        if 'file' not in request.files:
            return jsonify({'error': 'No file provided'}), 400
        
        file = request.files['file']
        if file.filename == '':
            return jsonify({'error': 'No file selected'}), 400
        
        if not file.filename.endswith('.csv'):
            return jsonify({'error': 'File must be a CSV file'}), 400
        
        csv_content = file.read().decode('utf-8')
        movies = parse_csv_movies(csv_content)
        
        if len(movies) == 0:
            return jsonify({'error': 'No valid movies found in CSV'}), 400
        
        # Persist each new movie to MySQL (skip if id already exists)
        saved = 0
        skipped = 0
        for movie in movies:
            try:
                result = add_movie_to_db(movie)
                if result:
                    saved += 1
                else:
                    skipped += 1
            except Exception:
                skipped += 1

        return jsonify({
            'status': 'ok',
            'movies': movies,
            'count': len(movies),
            'saved_to_db': saved,
            'skipped': skipped,
        })
    
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/log_event', methods=['POST'])
def log_event():
    """
    Log user events for model training.
    Accepts: event_type, user_id, movie_id, movie_title, search_query, 
             detected_mood, watch_duration, rating, liked, genre
    """
    try:
        payload = request.get_json(silent=True) or {}
        
        event_type = str(payload.get('event_type', 'unknown')).strip()
        user_id = str(payload.get('user_id', 'anonymous')).strip() or 'anonymous'
        movie_id = str(payload.get('movie_id', '')).strip()
        movie_title = str(payload.get('movie_title', '')).strip()
        search_query = str(payload.get('search_query', '')).strip()
        detected_mood = str(payload.get('detected_mood', '')).strip()
        watch_duration = float(payload.get('watch_duration', 0) or 0)
        rating = float(payload.get('rating', 0) or 0)
        liked = bool(payload.get('liked', False))
        genre = str(payload.get('genre', '')).strip()
        
        with open(USER_EVENTS_FILE, 'a', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow([
                int(time.time()),
                event_type,
                user_id,
                movie_id,
                movie_title,
                search_query,
                detected_mood,
                watch_duration,
                rating,
                int(liked) if liked else '',
                genre,
            ])
        
        return jsonify({'status': 'logged'})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


# ============================================================================
# PRODUCTION AI PIPELINE - Continuous Learning & Monitoring
# ============================================================================

@app.route('/pipeline/run', methods=['POST'])
def run_continuous_learning():
    """
    Trigger a continuous learning pipeline check
    Analyzes user data, monitors model performance, and triggers retraining if needed
    """
    try:
        result = run_pipeline_check()
        return jsonify({
            'status': 'success',
            'analysis': result['analysis'],
            'decision': result['decision'],
            'timestamp': result['timestamp']
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/pipeline/status', methods=['GET'])
def pipeline_status():
    """Get current status of the continuous learning pipeline"""
    try:
        status = get_pipeline_status()
        return jsonify({
            'status': 'success',
            'pipeline': status
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/pipeline/metrics', methods=['GET'])
def pipeline_metrics():
    """Get aggregated pipeline metrics"""
    try:
        pipeline = get_pipeline()
        analyzer = pipeline.analyzer
        
        engagement = analyzer.analyze_engagement()
        mood_patterns = analyzer.analyze_mood_patterns()
        recommendation_quality = analyzer.analyze_recommendation_quality()
        
        return jsonify({
            'status': 'success',
            'metrics': {
                'engagement': engagement,
                'mood_patterns': mood_patterns,
                'recommendation_quality': recommendation_quality
            },
            'timestamp': time.time()
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/pipeline/analysis', methods=['GET'])
def pipeline_analysis():
    """Get comprehensive pipeline analysis"""
    try:
        pipeline = get_pipeline()
        analyzer = pipeline.analyzer
        
        report = analyzer.generate_report()
        
        return jsonify({
            'status': 'success',
            'analysis': report,
            'timestamp': time.time()
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


# ==================== REAL-TIME EMOTION RECOMMENDATIONS ====================

@app.route('/realtime/emotion-record', methods=['POST'])
@token_required
def record_emotion():
    """Record user's current emotion and get real-time recommendations"""
    try:
        data = request.get_json()
        user_id = request.user.get('username')
        emotion = data.get('emotion', 'neutral').lower()
        confidence = float(data.get('confidence', 0.5))
        
        recommender = get_realtime_recommender()
        
        # Record the emotion
        result = recommender.record_emotion(user_id, emotion, confidence)
        
        return jsonify({
            "success": True,
            "emotion_recorded": result,
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/realtime/recommendations', methods=['POST'])
@token_required
def get_realtime_recommendations():
    """Get real-time movie recommendations based on user's current emotion"""
    try:
        data = request.get_json()
        user_id = request.user.get('username')
        current_emotion = data.get('emotion', 'neutral').lower()
        
        # Load available movies
        try:
            with open('movie_database.json', 'r') as f:
                available_movies = json.load(f)
        except:
            available_movies = []
        
        recommender = get_realtime_recommender()
        recommendations = recommender.get_real_time_recommendations(
            user_id, current_emotion, available_movies
        )
        
        return jsonify({
            "success": True,
            "emotion": current_emotion,
            "recommendations": recommendations,
            "count": len(recommendations),
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/realtime/emotion-patterns/<user_id>', methods=['GET'])
@token_required
def get_emotion_patterns(user_id):
    """Get emotion pattern analysis for a user"""
    try:
        # Check if user is requesting their own data or is admin
        current_user = request.user.get('username')
        if current_user != user_id and request.user.get('role') not in ['admin', 'manager']:
            return jsonify({"error": "Unauthorized"}), 403
        
        recommender = get_realtime_recommender()
        patterns = recommender.get_user_emotion_pattern(user_id)
        
        return jsonify({
            "success": True,
            "patterns": patterns,
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route('/realtime/emotion-trends', methods=['GET'])
@admin_required
def get_emotion_trends():
    """Get platform-wide emotion trends (admin only)"""
    try:
        recommender = get_realtime_recommender()
        trends = recommender.get_emotion_trends()
        
        return jsonify({
            "success": True,
            "trends": trends,
            "timestamp": datetime.now().isoformat()
        }), 200
    
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ============================================================================
# HYBRID RECOMMENDER ROUTES  (industry-level, replaces rule-based logic)
# ============================================================================

@app.route('/hybrid/recommend', methods=['POST'])
def hybrid_recommend():
    """
    Hybrid mood-based movie recommendation.
    Rate-limited: 20 requests / 60 s per IP.
    Input:  { user_id, mood, top_k (optional, default 6) }
    Output: { user_id, mood, recommendations, count, model_version, source }
    """
    if _rate_limited():
        return jsonify({'error': 'Too many requests. Please wait a moment.'}), 429

    try:
        payload  = request.get_json(silent=True) or {}
        user_id  = str(payload.get('user_id', 'guest')).strip() or 'guest'
        mood     = str(payload.get('mood', 'calm')).lower().strip()
        top_k    = min(int(payload.get('top_k', 6)), 20)  # cap at 20

        valid_moods = ['happy','sad','angry','calm','neutral','stressed','excited','bored','fear','disgust','surprise']
        if mood not in valid_moods:
            mood = 'calm'

        svc    = get_hybrid_recommender()
        movies = svc.recommend(user_id=user_id, mood=mood, top_k=top_k)

        # Save to DB (non-blocking, best-effort)
        try:
            numeric_uid = 1 if user_id == 'guest' else abs(hash(user_id)) % 999999 + 1
            movie_ids   = [str(m.get('id', '')) for m in movies]
            save_recommendations(numeric_uid, mood, movie_ids, f"hybrid_v{svc.get_version()}")
        except Exception:
            pass

        return jsonify({
            'user_id':       user_id,
            'mood':          mood,
            'recommendations': movies,
            'count':         len(movies),
            'model_version': svc.get_version(),
            'source':        'hybrid_recommender',
        })
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/hybrid/interact', methods=['POST'])
def hybrid_interact():
    """
    Log a user interaction (like / dislike / rating / watch_time).
    These are stored in interactions.csv AND MySQL, and used for weekly weak retraining.
    Input: {
        user_id, movie_id, movie_title,
        mood,  rating (1-5, optional),
        liked (bool), disliked (bool),
        watch_time (seconds),
        recommended_rank_position (int, optional)
    }
    """
    try:
        payload = request.get_json(silent=True) or {}

        user_id   = str(payload.get('user_id', 'guest')).strip() or 'guest'
        movie_id  = str(payload.get('movie_id', '')).strip()
        title     = str(payload.get('movie_title', '')).strip()
        mood      = str(payload.get('mood', '')).lower().strip()
        rating    = float(payload.get('rating', 0) or 0)
        liked     = bool(payload.get('liked', False))
        disliked  = bool(payload.get('disliked', False))
        watch_time= int(float(payload.get('watch_time', 0) or 0))
        rank_pos  = payload.get('recommended_rank_position')
        if rank_pos is not None:
            rank_pos = int(rank_pos)

        if not movie_id:
            return jsonify({'error': 'movie_id is required'}), 400

        # Write to interactions.csv for retraining pipeline
        import csv as _csv
        interactions_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'interactions.csv')
        file_exists = os.path.exists(interactions_path)
        with open(interactions_path, 'a', newline='', encoding='utf-8') as _f:
            writer = _csv.writer(_f)
            if not file_exists:
                writer.writerow(['timestamp','user_id','movie_id','movie_title',
                                 'emotion','event_type','rating','liked','watch_time',
                                 'recommended_rank_position'])
            event = 'like' if liked else ('dislike' if disliked else 'watch')
            writer.writerow([int(time.time()), user_id, movie_id, title,
                             mood, event, rating, int(liked), watch_time, rank_pos or ''])

        # Write to MySQL (best-effort)
        try:
            numeric_uid = 1 if user_id == 'guest' else abs(hash(user_id)) % 999999 + 1
            log_hybrid_interaction(
                user_id=numeric_uid, movie_id=movie_id, movie_title=title,
                mood=mood, rating=rating if rating else None,
                liked=liked, watch_time=watch_time,
                recommended_rank_position=rank_pos,
            )
            update_movie_stats(
                movie_id=movie_id,
                liked=True if liked else (False if disliked else None),
                rating=rating if rating else None,
                increment_views=(watch_time > 0),
            )
        except Exception as db_err:
            print(f"[interact] DB log warning: {db_err}")

        return jsonify({'status': 'logged', 'event': event})
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/hybrid/model-info', methods=['GET'])
def hybrid_model_info():
    """Get hybrid recommender model info and cache stats."""
    try:
        svc = get_hybrid_recommender()
        return jsonify(svc.get_model_info())
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


# ============================================================================
# RETRAIN SCHEDULER ROUTES
# ============================================================================

@app.route('/retrain/status', methods=['GET'])
def retrain_status():
    """Status of the weekly weak-interaction scheduler."""
    try:
        return jsonify(scheduler_status())
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


@app.route('/retrain/trigger', methods=['POST'])
@admin_required
def retrain_trigger():
    """Admin: manually trigger a weak-interaction retrain immediately."""
    try:
        result = trigger_retrain_now()
        return jsonify(result)
    except Exception as exc:
        traceback.print_exc()
        return jsonify({'error': str(exc)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False, threaded=True)