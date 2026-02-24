import os

# Define the base directory
BASE_DIR = "backend"

# Define the file structure and content
files = {
    f"{BASE_DIR}/requirements.txt": """flask
flask-cors
numpy
opencv-python-headless
librosa
tensorflow
""",

    f"{BASE_DIR}/app.py": """from flask import Flask, request, jsonify
from flask_cors import CORS
from services.ai_engine import MultimodalEngine
from services.recommender import get_movies_by_mood
from utils.file_utils import save_input_files, cleanup
import traceback
import os

app = Flask(__name__)
CORS(app)

# Initialize AI Engine
try:
    engine = MultimodalEngine()
except Exception as e:
    print(f"Warning: AI Engine failed to load. {e}")
    engine = None

@app.route('/health', methods=['GET'])
def health_check():
    return jsonify({"status": "online", "model": "v1.0"})

@app.route('/live_predict', methods=['POST'])
def live_predict():
    temp_files = []
    try:
        if 'video_frame' not in request.files or 'audio_sample' not in request.files:
            return jsonify({"error": "Missing media files"}), 400

        video = request.files['video_frame']
        audio = request.files['audio_sample']

        # Save temporarily
        img_path, audio_path = save_input_files(video, audio)
        temp_files = [img_path, audio_path]

        # AI Analysis
        if engine:
            analysis = engine.analyze(img_path, audio_path)
        else:
            # Fallback if engine fails
            analysis = {"mood": "neutral", "confidence": 0.0, "reasoning": "AI Engine offline"}

        # Get Recommendations
        movies = get_movies_by_mood(analysis['mood'])

        return jsonify({
            "mood": analysis['mood'],
            "confidence": analysis['confidence'],
            "reasoning": analysis['reasoning'],
            "movies": movies
        })

    except Exception as e:
        traceback.print_exc()
        return jsonify({"error": str(e)}), 500
    finally:
        cleanup(temp_files)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True, threaded=True)
""",

    f"{BASE_DIR}/utils/__init__.py": "",
    
    f"{BASE_DIR}/utils/file_utils.py": """import os
import uuid

UPLOAD_DIR = "temp_uploads"
if not os.path.exists(UPLOAD_DIR):
    os.makedirs(UPLOAD_DIR)

def save_input_files(video_file, audio_file):
    session_id = str(uuid.uuid4())
    img_path = os.path.join(UPLOAD_DIR, f"{session_id}_face.jpg")
    audio_path = os.path.join(UPLOAD_DIR, f"{session_id}_voice.webm")
    
    video_file.save(img_path)
    audio_file.save(audio_path)
    return img_path, audio_path

def cleanup(paths):
    for path in paths:
        if os.path.exists(path):
            try:
                os.remove(path)
            except:
                pass
""",

    f"{BASE_DIR}/services/__init__.py": "",

    f"{BASE_DIR}/services/recommender.py": """# Mock Database matching frontend types
MOVIE_DB = [
    {"id": "1", "title": "Interstellar Odyssey", "mood": "calm", "genres": ["Sci-Fi", "Adventure"], 
     "poster": "https://picsum.photos/seed/inter/300/450", "rating": "PG-13", "year": 2023, "duration": "2h 49m", "description": "Space exploration."},
    {"id": "2", "title": "Cyberpunk City", "mood": "angry", "genres": ["Action", "Sci-Fi"], 
     "poster": "https://picsum.photos/seed/cyber/300/450", "rating": "R", "year": 2077, "duration": "2h 10m", "description": "Future dystopian action."},
    {"id": "3", "title": "The Silent Forest", "mood": "sad", "genres": ["Horror", "Drama"], 
     "poster": "https://picsum.photos/seed/silent/300/450", "rating": "PG-13", "year": 2022, "duration": "1h 30m", "description": "Quiet horror."},
    {"id": "4", "title": "Sunnyside Up", "mood": "happy", "genres": ["Comedy", "Animation"], 
     "poster": "https://picsum.photos/seed/sunny/300/450", "rating": "G", "year": 2024, "duration": "1h 25m", "description": "Happy eggs."},
    {"id": "7", "title": "Final Reckoning", "mood": "stressed", "genres": ["Thriller", "Intense"], 
     "poster": "https://picsum.photos/seed/dark/300/450", "rating": "R", "year": 2023, "duration": "2h 05m", "description": "Intense detective story."}
]

def get_movies_by_mood(mood):
    mood = mood.lower()
    # Simple filter
    recs = [m for m in MOVIE_DB if m['mood'] == mood]
    
    # Fallback logic
    if not recs:
        # Return generic recommendations if no direct match
        return MOVIE_DB[:4]
        
    return recs
""",

    f"{BASE_DIR}/services/ai_engine.py": """import random

class MultimodalEngine:
    def __init__(self):
        print("Initializing AI Engine... (Loading Mock Models)")
        # In production, load your .h5 or .pt models here
        # self.face_model = load_model(...)
        # self.voice_model = load_model(...)

    def analyze(self, img_path, audio_path):
        # 1. Mock Prediction (Replace with actual inference)
        face_mood = self._predict_face(img_path)
        voice_mood = self._predict_voice(audio_path)
        
        # 2. Fusion
        final_mood = self._fuse(face_mood, voice_mood)
        
        return {
            "mood": final_mood,
            "confidence": round(random.uniform(0.7, 0.99), 2),
            "reasoning": f"Face showed {face_mood} and voice sounded {voice_mood}."
        }

    def _predict_face(self, img_path):
        # Logic: cv2.imread(img_path) -> model.predict()
        return random.choice(['happy', 'sad', 'angry', 'neutral', 'calm'])

    def _predict_voice(self, audio_path):
        # Logic: librosa.load(audio_path) -> model.predict()
        return random.choice(['happy', 'sad', 'angry', 'neutral', 'stressed'])

    def _fuse(self, face, voice):
        # Priority Logic
        if face == 'sad' or voice == 'sad': return 'sad'
        if face == 'angry' and voice == 'angry': return 'angry'
        if face == 'happy' and voice == 'happy': return 'happy'
        if voice == 'stressed': return 'stressed'
        
        return face if face != 'neutral' else 'calm'
"""
}

def create_structure():
    # Create main folders
    folders = [
        BASE_DIR,
        os.path.join(BASE_DIR, "models"),
        os.path.join(BASE_DIR, "services"),
        os.path.join(BASE_DIR, "utils"),
        os.path.join(BASE_DIR, "temp_uploads")
    ]

    for folder in folders:
        os.makedirs(folder, exist_ok=True)
        print(f"Created directory: {folder}")

    # Create files
    for filepath, content in files.items():
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(content)
        print(f"Created file: {filepath}")

    print("\n✅ Backend generation complete!")
    print(f"1. cd {BASE_DIR}")
    print("2. pip install -r requirements.txt")
    print("3. python app.py")

if __name__ == "__main__":
    create_structure()
