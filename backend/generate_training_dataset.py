"""
Training Dataset Generator - Creates 2000 mood-labeled movie interactions
Generates realistic training data for mood-based recommendation model
"""

import csv
import json
import os
import random
from datetime import datetime, timedelta
from typing import List, Dict

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Mood-to-genre mappings for training
MOOD_GENRE_MAPPING = {
    'happy': ['Comedy', 'Animation', 'Adventure', 'Family', 'Musical'],
    'sad': ['Drama', 'Romance', 'History', 'Documentary', 'Emotional'],
    'angry': ['Action', 'Thriller', 'Crime', 'War', 'Intense'],
    'calm': ['Documentary', 'Nature', 'Art', 'Mystery', 'Drama'],
    'stressed': ['Comedy', 'Animation', 'Feel-Good', 'Motivational', 'Adventure'],
    'excited': ['Action', 'Adventure', 'Sci-Fi', 'Thriller', 'Sports'],
    'neutral': ['All']
}

MOODS = list(MOOD_GENRE_MAPPING.keys())

# Realistic movie titles
MOVIE_TITLES = [
    'The Shawshank Redemption', 'The Godfather', 'The Dark Knight', 'Pulp Fiction',
    'Forrest Gump', 'Inception', 'The Matrix', 'Interstellar', 'Gladiator', 'Avatar',
    'The Avengers', 'Iron Man', 'Captain America', 'Thor', 'Black Panther',
    'Spider-Man: Homecoming', 'Deadpool', 'Logan', 'X-Men: Days of Future Past',
    'The Hunger Games', 'Divergent', 'The Maze Runner', 'Ready Player One',
    'Jurassic World', 'The Lion King', 'Frozen', 'Moana', 'Coco', 'Toy Story',
    'Finding Nemo', 'Inside Out', 'Up', 'Wall-E', 'Ratatouille',
    'The Notebook', 'Titanic', 'La La Land', 'The Fault in Our Stars', 'A Walk to Remember',
    'Casablanca', 'Roman Holiday', 'Breakfast at Tiffany\'s', 'Singin\' in the Rain',
    'The Pursuit of Happyness', 'Good Will Hunting', 'Rocky', 'The Karate Kid',
    'Whiplash', 'Black Swan', 'The Wolf of Wall Street', 'Scarface',
    'Se7en', 'The Silence of the Lambs', 'Zodiac', 'Gone Girl', 'Mindhunter',
    'The Conjuring', 'Insidious', 'The Ring', 'Sinister', 'Hereditary',
    'Jaws', 'The Blair Witch Project', 'A Quiet Place', 'Don\'t Breathe',
    'Parasite', 'Squid Game', 'Breakthrough', 'Hidden Figures', 'Why Did You Kill Me',
    'Planet Earth', 'Our Planet', 'The Great Barrier Reef', 'Frozen Planet',
    'Blue Planet', 'Life', 'March of the Penguins',
    'Inception', 'Memento', 'The Prestige', 'Ex Machina', 'Arrival',
    'Knives Out', 'Sherlock Holmes', 'Murder on the Orient Express', 'The Game',
    'The Sixth Sense', 'Fight Club', 'American Beauty', 'Requiem for a Dream',
    'Trainspotting', 'Slumdog Millionaire', 'Erin Brockovich', 'Social Network',
    'The Big Short', 'Moneyball', 'The Wolf of Wall Street', '127 Hours',
    'Cast Away', 'Into the Wild', 'The Revenant', 'Braveheart', 'Hacksaw Ridge',
    'Top Gun', 'Mission: Impossible', 'Fast & Furious', 'Mad Max: Fury Road',
    'John Wick', 'Atomic Blonde', 'Kingsman', 'Baby Driver', 'Drive',
    'The Nice Guys', 'Tropic Thunder', 'Central Intelligence', 'Jump Street',
    'Horrible Bosses', 'The Hangover', 'Bridesmaids', 'Superbad', 'Mean Girls',
]

def generate_user_id() -> str:
    """Generate realistic user IDs"""
    return f"user_{random.randint(1000, 9999)}"

def get_genre_for_mood(mood: str) -> str:
    """Get a random genre suitable for the mood"""
    genres = MOOD_GENRE_MAPPING.get(mood, ['All'])
    return random.choice(genres)

def generate_rating(mood: str) -> float:
    """Generate realistic ratings based on mood preference"""
    # Users give higher ratings for movies matching their mood
    base_rating = random.uniform(6.5, 9.5)
    # Add some variance
    variance = random.uniform(-1, 1)
    rating = base_rating + variance
    return round(min(10.0, max(1.0, rating)), 1)

def generate_watched_percentage() -> float:
    """Generate realistic watch completion percentage"""
    # Most users watch 60-100%, some drop off early
    if random.random() < 0.15:  # 15% chance of low engagement
        return random.uniform(0.1, 0.5)
    else:  # 85% complete or high engagement
        return random.uniform(0.6, 1.0)

def generate_training_data(num_records: int = 2000) -> List[Dict]:
    """
    Generate training dataset with mood-labeled movie interactions
    
    Args:
        num_records: Number of records to generate (default 2000)
    
    Returns:
        List of interaction records
    """
    records = []
    base_timestamp = datetime.now() - timedelta(days=90)  # Last 90 days of data
    
    for i in range(num_records):
        user_id = generate_user_id()
        mood = random.choice(MOODS)
        movie_title = random.choice(MOVIE_TITLES)
        genre = get_genre_for_mood(mood)
        rating = generate_rating(mood)
        watched_percent = generate_watched_percentage()
        timestamp = (base_timestamp + timedelta(hours=i * 2)).isoformat()
        confidence = round(random.uniform(0.65, 0.99), 2)
        liked = rating >= 7.0 and watched_percent >= 0.7
        
        records.append({
            'timestamp': timestamp,
            'user_id': user_id,
            'movie_id': f"movie_{i % 500}",
            'movie_title': movie_title,
            'mood': mood,
            'confidence': confidence,
            'genre': genre,
            'rating': rating,
            'watched_percentage': round(watched_percent, 2),
            'liked': liked,
            'event_type': 'watched' if watched_percent >= 0.5 else 'browsed',
            'duration_minutes': int(random.uniform(80, 180))
        })
    
    return records

def save_training_data(records: List[Dict], filepath: str = None):
    """Save training data to CSV file"""
    if filepath is None:
        filepath = os.path.join(BASE_DIR, 'training_dataset_2000.csv')
    
    if not records:
        print("No records to save")
        return
    
    try:
        fieldnames = list(records[0].keys())
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(records)
        
        print(f"✅ Training dataset saved: {filepath}")
        print(f"   Records: {len(records)}")
        print(f"   File size: {os.path.getsize(filepath) / 1024:.2f} KB")
        return filepath
    except Exception as e:
        print(f"❌ Error saving training data: {e}")
        return None

def save_training_interactions(records: List[Dict], filepath: str = None):
    """Save data in interactions.csv format for model training"""
    if filepath is None:
        filepath = os.path.join(BASE_DIR, 'interactions_training.csv')
    
    if not records:
        print("No records to save")
        return
    
    try:
        # Convert to interactions format that recommender_engine.py expects
        interactions = []
        for rec in records:
            interactions.append({
                'user_id': rec['user_id'],
                'movie_id': rec['movie_id'],
                'movie_title': rec['movie_title'],
                'emotion': rec['mood'],
                'event_type': rec['event_type'],
                'rating': rec['rating'],
                'liked': 1 if rec['liked'] else 0,
                'watched_duration_minutes': rec['duration_minutes']
            })
        
        fieldnames = list(interactions[0].keys())
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=fieldnames)
            writer.writeheader()
            writer.writerows(interactions)
        
        print(f"✅ Training interactions saved: {filepath}")
        print(f"   Records: {len(interactions)}")
        return filepath
    except Exception as e:
        print(f"❌ Error saving interactions: {e}")
        return None

def generate_mood_statistics(records: List[Dict]) -> Dict:
    """Generate statistics about the training data"""
    stats = {
        'total_records': len(records),
        'mood_distribution': {},
        'avg_rating_by_mood': {},
        'liked_percentage': {},
        'engagement_by_mood': {},
        'unique_users': set(),
        'unique_movies': set()
    }
    
    mood_ratings = {}
    mood_likes = {}
    mood_counts = {}
    
    for rec in records:
        mood = rec['mood']
        stats['unique_users'].add(rec['user_id'])
        stats['unique_movies'].add(rec['movie_id'])
        
        # Distribution
        stats['mood_distribution'][mood] = stats['mood_distribution'].get(mood, 0) + 1
        
        # Average rating
        if mood not in mood_ratings:
            mood_ratings[mood] = []
        mood_ratings[mood].append(rec['rating'])
        
        # Liked count
        if mood not in mood_likes:
            mood_likes[mood] = 0
        if rec['liked']:
            mood_likes[mood] += 1
        
        mood_counts[mood] = mood_counts.get(mood, 0) + 1
    
    # Calculate averages
    for mood in MOODS:
        if mood in mood_ratings:
            stats['avg_rating_by_mood'][mood] = round(sum(mood_ratings[mood]) / len(mood_ratings[mood]), 2)
            stats['liked_percentage'][mood] = round((mood_likes.get(mood, 0) / len(mood_ratings[mood])) * 100, 1)
            stats['engagement_by_mood'][mood] = mood_counts[mood]
    
    stats['unique_users'] = len(stats['unique_users'])
    stats['unique_movies'] = len(stats['unique_movies'])
    
    return stats

def print_statistics(stats: Dict):
    """Pretty print training data statistics"""
    print("\n" + "="*60)
    print("📊 TRAINING DATASET STATISTICS")
    print("="*60)
    print(f"✓ Total Records: {stats['total_records']}")
    print(f"✓ Unique Users: {stats['unique_users']}")
    print(f"✓ Unique Movies: {stats['unique_movies']}")
    
    print(f"\n🎭 Mood Distribution:")
    for mood in MOODS:
        count = stats['mood_distribution'].get(mood, 0)
        pct = (count / stats['total_records']) * 100
        print(f"   {mood.upper():12} → {count:4} records ({pct:5.1f}%)")
    
    print(f"\n⭐ Average Rating by Mood:")
    for mood in MOODS:
        avg_rating = stats['avg_rating_by_mood'].get(mood, 0)
        print(f"   {mood.upper():12} → {avg_rating:.2f}/10")
    
    print(f"\n👍 Like Percentage by Mood:")
    for mood in MOODS:
        like_pct = stats['liked_percentage'].get(mood, 0)
        print(f"   {mood.upper():12} → {like_pct:5.1f}%")
    
    print("\n" + "="*60)

if __name__ == '__main__':
    print("🔄 Generating training dataset with 2000 records...")
    
    # Generate data
    records = generate_training_data(num_records=2000)
    
    # Save in different formats
    save_training_data(records)
    save_training_interactions(records)
    
    # Generate and print statistics
    stats = generate_mood_statistics(records)
    print_statistics(stats)
    
    # Save statistics to JSON
    stats_file = os.path.join(BASE_DIR, 'training_dataset_stats.json')
    with open(stats_file, 'w') as f:
        json.dump({k: v for k, v in stats.items() if k not in ['unique_users', 'unique_movies']}, 
                  f, indent=2, default=str)
    print(f"\n✅ Statistics saved to: {stats_file}")
