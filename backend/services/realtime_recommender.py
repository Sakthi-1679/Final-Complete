"""
Real-time Emotion-Based Recommendation Engine
Provides personalized recommendations based on detected emotions
"""

import json
import os
from datetime import datetime
from typing import Dict, List, Tuple, Any
from collections import defaultdict

USER_MOOD_HISTORY = "user_mood_history.json"

EMOTION_TO_GENRES = {
    "happy": ["Comedy", "Animation", "Adventure", "Family"],
    "sad": ["Drama", "Romance", "History", "Documentary"],
    "angry": ["Action", "Thriller", "Crime", "War"],
    "calm": ["Drama", "Documentary", "Art", "Mystery"],
    "neutral": ["All"],
    "surprised": ["Thriller", "Mystery", "Science Fiction"],
    "fear": ["Horror", "Thriller", "Suspense"],
    "disgust": ["Documentary", "Crime", "Drama"]
}

class RealTimeRecommender:
    """Real-time emotion-based movie recommendation engine"""

    def __init__(self):
        self.mood_history = self.load_mood_history()
        self.user_preferences = defaultdict(lambda: defaultdict(int))
        self.load_user_preferences()

    def load_mood_history(self) -> Dict:
        """Load user mood history from persistent storage"""
        if os.path.exists(USER_MOOD_HISTORY):
            try:
                with open(USER_MOOD_HISTORY, 'r') as f:
                    return json.load(f)
            except:
                return {}
        return {}

    def save_mood_history(self):
        """Save mood history to persistent storage"""
        with open(USER_MOOD_HISTORY, 'w') as f:
            json.dump(self.mood_history, f, indent=2)

    def load_user_preferences(self):
        """Load user preferences based on their mood history"""
        for user_id, moods in self.mood_history.items():
            for mood_entry in moods:
                emotion = mood_entry.get('emotion', 'neutral')
                genre = mood_entry.get('recommended_genre', 'All')
                self.user_preferences[user_id][genre] += 1

    def get_emotion_based_genres(self, emotion: str) -> List[str]:
        """Get recommended genres for a specific emotion"""
        emotion_lower = emotion.lower()
        return EMOTION_TO_GENRES.get(emotion_lower, EMOTION_TO_GENRES['neutral'])

    def record_emotion(self, user_id: str, emotion: str, confidence: float,
                      movie_recommendation: str = None) -> Dict[str, Any]:
        """Record user's emotion and generate recommendations"""
        if user_id not in self.mood_history:
            self.mood_history[user_id] = []

        genres = self.get_emotion_based_genres(emotion)
        
        mood_entry = {
            "timestamp": datetime.now().isoformat(),
            "emotion": emotion,
            "confidence": confidence,
            "recommended_genres": genres,
            "recommended_movie": movie_recommendation
        }

        self.mood_history[user_id].append(mood_entry)
        self.save_mood_history()

        # Update user preferences
        for genre in genres:
            self.user_preferences[user_id][genre] += 1

        return {
            "status": "recorded",
            "emotion": emotion,
            "confidence": confidence,
            "genres": genres
        }

    def get_real_time_recommendations(self, user_id: str, current_emotion: str,
                                     available_movies: List[Dict]) -> List[Dict]:
        """Get real-time recommendations based on current emotion"""
        genres = self.get_emotion_based_genres(current_emotion)

        # Filter movies by recommended genres
        recommended = []
        for movie in available_movies:
            movie_genre = movie.get('genre', 'Unknown').lower()
            for genre in genres:
                if genre.lower() in movie_genre.lower():
                    score = self.calculate_recommendation_score(
                        user_id, movie, current_emotion
                    )
                    movie_with_score = {**movie, "recommendation_score": score}
                    recommended.append(movie_with_score)
                    break

        # Sort by recommendation score
        recommended.sort(key=lambda x: x['recommendation_score'], reverse=True)
        return recommended[:5]  # Top 5 recommendations

    def calculate_recommendation_score(self, user_id: str, movie: Dict,
                                      current_emotion: str) -> float:
        """
        Calculate recommendation score based on:
        1. Genre match with emotion (weight: 40%)
        2. User's past preference for genre (weight: 30%)
        3. Movie rating (weight: 20%)
        4. Emotion confidence (weight: 10%)
        """
        genres = self.get_emotion_based_genres(current_emotion)
        movie_genre = movie.get('genre', 'Unknown').lower()

        # Genre match score
        genre_match = 0
        for genre in genres:
            if genre.lower() in movie_genre.lower():
                genre_match = 1.0
                break
        genre_score = genre_match * 0.4

        # User preference score
        user_genre_history = self.user_preferences.get(user_id, {})
        user_preference_score = (
            user_genre_history.get(movie.get('genre', 'Unknown'), 0) / max(
                sum(user_genre_history.values()), 1
            )
        ) * 0.3

        # Movie rating score
        try:
            rating = float(movie.get('rating', 0)) / 10.0
        except (ValueError, TypeError):
            rating = 0
        rating_score = rating * 0.2

        # Emotion confidence score
        emotion_confidence = 0.5  # Default, would be from emotion detection
        confidence_score = emotion_confidence * 0.1

        total_score = genre_score + user_preference_score + rating_score + confidence_score
        return min(total_score, 1.0)  # Cap at 1.0

    def get_user_emotion_pattern(self, user_id: str) -> Dict[str, Any]:
        """Analyze user's emotion pattern over time"""
        if user_id not in self.mood_history:
            return {"error": "No history for this user"}

        moods = self.mood_history[user_id]
        emotion_counts = defaultdict(int)
        average_confidence = defaultdict(list)
        preferred_genres = defaultdict(int)

        for mood in moods:
            emotion = mood.get('emotion', 'neutral')
            emotion_counts[emotion] += 1
            average_confidence[emotion].append(mood.get('confidence', 0))
            for genre in mood.get('recommended_genres', []):
                preferred_genres[genre] += 1

        # Calculate averages
        avg_confidence = {
            emotion: sum(scores) / len(scores)
            for emotion, scores in average_confidence.items()
        }

        dominant_emotion = max(emotion_counts.items(), key=lambda x: x[1])[0] if emotion_counts else 'neutral'

        return {
            "user_id": user_id,
            "total_sessions": len(moods),
            "emotion_distribution": dict(emotion_counts),
            "average_confidence": avg_confidence,
            "dominant_emotion": dominant_emotion,
            "preferred_genres": dict(sorted(
                preferred_genres.items(),
                key=lambda x: x[1],
                reverse=True
            )[:5]),
            "recommendations_summary": {
                "for_" + emotion: self.get_emotion_based_genres(emotion)
                for emotion in emotion_counts.keys()
            }
        }

    def get_emotion_trends(self) -> Dict[str, Any]:
        """Get overall emotion trends across all users"""
        global_emotion_counts = defaultdict(int)
        total_sessions = 0

        for user_id, moods in self.mood_history.items():
            total_sessions += len(moods)
            for mood in moods:
                emotion = mood.get('emotion', 'neutral')
                global_emotion_counts[emotion] += 1

        total = sum(global_emotion_counts.values()) or 1
        emotion_percentages = {
            emotion: (count / total) * 100
            for emotion, count in global_emotion_counts.items()
        }

        return {
            "timestamp": datetime.now().isoformat(),
            "total_sessions": total_sessions,
            "emotion_distribution": dict(global_emotion_counts),
            "emotion_percentages": emotion_percentages,
            "most_common_emotion": max(
                global_emotion_counts.items(),
                key=lambda x: x[1]
            )[0] if global_emotion_counts else 'neutral'
        }

# Global instance
realtime_recommender = RealTimeRecommender()

def get_realtime_recommender() -> RealTimeRecommender:
    """Get the global recommender instance"""
    return realtime_recommender
