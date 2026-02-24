#!/usr/bin/env python3
"""Generate test interaction data for AI pipeline testing"""

import csv
import random
from datetime import datetime, timedelta
import os

# Configuration
NUM_USERS = 10
NUM_MOVIES = 20
NUM_INTERACTIONS = 100

def generate_interactions():
    """Generate test interaction data"""
    interactions_file = 'interactions.csv'
    
    # Create headers
    data = [['user_id', 'movie_id', 'rating', 'timestamp']]
    
    # Generate random interactions
    for _ in range(NUM_INTERACTIONS):
        user_id = f"user_{random.randint(1, NUM_USERS)}"
        movie_id = f"movie_{random.randint(1, NUM_MOVIES)}"
        rating = round(random.uniform(1.0, 5.0), 1)
        timestamp = (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
        
        data.append([user_id, movie_id, rating, timestamp])
    
    # Write to CSV
    with open(interactions_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    
    print(f"✅ Generated {interactions_file} with {NUM_INTERACTIONS} interactions")
    return len(data) - 1

def generate_user_events():
    """Generate test user event data"""
    events_file = 'user_events.csv'
    
    # Create headers
    data = [['user_id', 'movie_id', 'event_type', 'timestamp']]
    
    # Generate events (watch, like, rate)
    for _ in range(NUM_INTERACTIONS * 2):
        user_id = f"user_{random.randint(1, NUM_USERS)}"
        movie_id = f"movie_{random.randint(1, NUM_MOVIES)}"
        event_type = random.choice(['watched', 'liked', 'rated', 'completed'])
        timestamp = (datetime.now() - timedelta(days=random.randint(0, 30))).isoformat()
        
        data.append([user_id, movie_id, event_type, timestamp])
    
    # Write to CSV
    with open(events_file, 'w', newline='') as f:
        writer = csv.writer(f)
        writer.writerows(data)
    
    print(f"✅ Generated {events_file} with {len(data) - 1} events")
    return len(data) - 1

def main():
    print("🔧 Generating test data for AI pipeline...")
    print()
    
    interactions = generate_interactions()
    events = generate_user_events()
    
    print()
    print("=" * 50)
    print("✅ TEST DATA GENERATION COMPLETE")
    print("=" * 50)
    print(f"Generated {interactions} interactions")
    print(f"Generated {events} events")
    print()
    print("Now you can:")
    print("1. Restart the backend: python app.py")
    print("2. Visit: http://localhost:3001/admin/pipeline")
    print("3. Click 'Trigger Pipeline Run' button")
    print("4. Watch metrics populate!")

if __name__ == "__main__":
    main()
