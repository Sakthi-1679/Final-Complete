# StreamFlix MySQL Setup & Mood Detection Model

## Overview
This guide explains how to set up MySQL database integration and use the new `mood_model_3datasets.pth` mood detection model.

## Prerequisites
- MySQL Server 5.7 or higher
- Python 3.8+
- Virtual environment with dependencies installed

## Installation Steps

### 1. Install MySQL Server
- **Windows**: Download from [mysql.com](https://dev.mysql.com/downloads/mysql/)
- **Mac**: `brew install mysql`
- **Linux**: `sudo apt-get install mysql-server`

### 2. Install Python Dependencies
```bash
cd backend
pip install -r requirements.txt
```

This includes:
- `mysql-connector-python` - MySQL database driver
- `python-dotenv` - Environment variable management

### 3. Configure Database Connection

Copy `.env.example` to `.env`:
```bash
cp .env.example .env
```

Edit `.env` with your MySQL credentials:
```env
DB_HOST=localhost
DB_USER=root
DB_PASSWORD=your_password
DB_NAME=streamflix_db
DB_PORT=3306
FLASK_ENV=development
MODEL_VERSION=v3_3datasets
```

### 4. Initialize Database and Models

Run the setup script:
```bash
python setup_database.py
```

This will:
- Create MySQL database and tables
- Register mood detection models
- Set up mood logs, movie interactions, and recommendations tables

### 5. Start the Backend

```bash
python app.py
```

You should see:
```
📊 Initializing MySQL Database...
✅ Database tables initialized successfully
🤖 Loading AI Mood Detection Engine...
✅ Mood model loaded successfully! Version: v3_3datasets
```

## Database Schema

### Tables Created

#### `users`
- Stores user account information
- Fields: user_id, username, email, password_hash, name, subscription, role, timestamps

#### `mood_logs`
- Records every mood detection
- Fields: mood_log_id, user_id, detected_mood, confidence, model_version, timestamp

#### `movie_interactions`
- Tracks user-movie interactions
- Fields: interaction_id, user_id, movie_id, title, mood, rating, liked, watch_duration, timestamp

#### `recommendations`
- Stores recommendation history
- Fields: recommendation_id, user_id, mood, recommended_movies, model_version, timestamp

#### `mood_model_metadata`
- Model version information
- Fields: model_id, model_version, model_name, model_path, accuracy, trained_samples, training_date

## Mood Detection Model

### Model File
- **Location**: `backend/models/mood_model_3datasets.pth`
- **Type**: PyTorch neural network
- **Version**: v3_3datasets
- **Input**: 512-dimensional feature vector
- **Output**: 7 mood classes (happy, sad, angry, calm, stressed, excited, neutral)
- **Accuracy**: 87% (trained on 3 datasets)

### Mood Classes
1. **happy** - Positive, cheerful mood
2. **sad** - Low energy, melancholic mood
3. **angry** - Frustrated, aggressive mood
4. **calm** - Relaxed, peaceful mood
5. **stressed** - Anxious, tense mood
6. **excited** - Energetic, enthusiastic mood
7. **neutral** - Indifferent, baseline mood

### How It Works

1. **Feature Extraction** (ai_engine.py)
   - Extracts features from user input (image/audio)
   - Creates 512-dimensional feature vector

2. **Mood Prediction**
   - Passes features through neural network
   - Returns mood class and confidence score

3. **Database Logging**
   - Stores detected mood in `mood_logs` table
   - Links to user and timestamp
   - Tracks model version used

### API Endpoints

#### Get Mood-Based Recommendations
```
POST /mood/recommendations
Content-Type: application/json

{
  "user_id": "user_123",
  "mood": "happy",
  "top_k": 6
}

Response:
{
  "user_id": "user_123",
  "mood": "happy",
  "recommendations": [...],
  "count": 6,
  "model_version": "v3_3datasets"
}
```

#### Get Model Information
```
GET /model/info

Response:
{
  "version": 2,
  "model_loaded": true,
  "model_path": "...",
  "trained_rows": 2000,
  "last_retrain_timestamp": 1771733729,
  "last_retrain_date": "2026-02-22T09:45:29"
}
```

#### Get Model Versions
```
GET /model/versions

Response:
{
  "versions": [
    {"model": "model_v2.pth", "size": 198.18, "date": "2026-02-22T09:45:29"}
  ]
}
```

## Troubleshooting

### Database Connection Error
```
Error: "Access denied for user 'root'@'localhost'"
```
**Solution**: Check MySQL credentials in `.env` file

### Model Not Loading
```
Error: "Model file not found at ..."
```
**Solution**: Ensure `mood_model_3datasets.pth` exists in `backend/models/`

### MySQL Table Already Exists
This is normal - the setup script creates tables only if they don't exist

### Port Already in Use
If port 3306 is busy:
1. Change `DB_PORT` in `.env`
2. Ensure only one MySQL instance is running

## Data Persistence

All user interactions are now stored in MySQL:
- ✅ Mood detections
- ✅ Movie recommendations
- ✅ Watch history
- ✅ Ratings and likes
- ✅ Model versions

This enables:
- User profile building
- Personalized recommendations over time
- Model performance tracking
- User analytics

## Next Steps

1. Test the API endpoints using curl or Postman
2. Train the model with fresh data if needed
3. Monitor mood detection accuracy
4. Use analytics queries on the stored data

## Example SQL Queries

```sql
-- Get user's mood distribution
SELECT detected_mood, COUNT(*) as count 
FROM mood_logs 
WHERE user_id = 1 
GROUP BY detected_mood;

-- Get top recommended movies
SELECT movie_title, COUNT(*) as recommendations 
FROM recommendations 
JOIN movie_interactions 
GROUP BY movie_title 
LIMIT 10;

-- Model accuracy trend
SELECT model_version, AVG(confidence) as avg_confidence
FROM mood_logs
GROUP BY model_version;
```

## Performance Tips

1. **Index frequently queried columns**:
   ```sql
   CREATE INDEX idx_user_mood ON mood_logs(user_id, detected_at);
   CREATE INDEX idx_movie_interaction ON movie_interactions(user_id, watched_at);
   ```

2. **Archive old data** periodically to maintain performance

3. **Monitor disk space** as movie interactions grow

## Security Notes

- Store database passwords securely (use environment variables)
- Never commit `.env` file to version control
- Use strong passwords for MySQL user
- Restrict database access to local network only
- Implement rate limiting on API endpoints

---

**For questions or issues, refer to the main README.md**
