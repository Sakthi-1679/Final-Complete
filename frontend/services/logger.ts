import { buildApiUrl } from '../constants';

/**
 * Submit a like / dislike / star-rating interaction to the hybrid recommender backend.
 * Persists the feedback in localStorage so it survives page reloads.
 */
export const logHybridInteraction = (
  movieId: string,
  movieTitle: string,
  opts: {
    liked?: boolean | null;   // true = like, false = dislike, null = remove
    rating?: number;          // 1-5 star rating (0 = not rated)
    watchTime?: number;       // seconds watched so far
    rank?: number | null;     // _recommendedRank from hybrid recommender
  } = {}
): void => {
  const userId = localStorage.getItem('streamflix_user_id') || 'guest';
  const mood   = localStorage.getItem('streamflix_last_mood') || 'calm';
  const { liked = null, rating = 0, watchTime = 0, rank = null } = opts;

  // Persist locally so the UI can reload state on revisit
  const key = `streamflix_feedback_${movieId}`;
  const prev = (() => { try { return JSON.parse(localStorage.getItem(key) || '{}'); } catch { return {}; } })();
  localStorage.setItem(key, JSON.stringify({ ...prev, liked, rating }));

  // Also write an entry to streamflix_system_logs so the Insights dashboard can count interactions
  try {
    const logEntry = {
      event_type: 'interaction',
      timestamp: new Date().toISOString(),
      user_id: userId,
      movie_id: movieId,
      movie_title: movieTitle,
      detected_mood: mood,
      liked,
      rating,
      watch_time: watchTime,
    };
    const existing = JSON.parse(localStorage.getItem('streamflix_system_logs') || '[]');
    localStorage.setItem('streamflix_system_logs', JSON.stringify([logEntry, ...existing].slice(0, 200)));
  } catch { /* silent */ }

  // Fire-and-forget to backend
  fetch(buildApiUrl('/hybrid/interact'), {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      user_id: userId,
      movie_id: movieId,
      movie_title: movieTitle,
      mood,
      liked: liked === true,
      disliked: liked === false,
      rating: rating || 0,
      watch_time: watchTime,
      recommended_rank_position: rank,
    }),
  }).catch(() => {});
};

export const logUserEvent = async (eventType: string, details: any) => {
  const payload = {
    event_type: eventType,
    timestamp: new Date().toISOString(),
    ...details
  };

  // 1. Persist to local storage for Admin Dashboard visibility (Mocking a real database)
  try {
    const existingLogs = JSON.parse(localStorage.getItem('streamflix_system_logs') || '[]');
    const updatedLogs = [payload, ...existingLogs].slice(0, 100); // Keep last 100
    localStorage.setItem('streamflix_system_logs', JSON.stringify(updatedLogs));
  } catch (e) {
    console.error('Local logging failed', e);
  }

  // 2. Send to backend endpoint
  try {
    const response = await fetch(buildApiUrl('/log_event'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(payload),
    });

    if (!response.ok) {
      console.warn(`Logger: Remote endpoint returned ${response.status}`);
    }
  } catch (error) {
    // Graceful degradation: failing to reach the mock backend doesn't break the app
    console.debug('Logger: Could not reach backend logging endpoint. Events are stored locally.');
  }
};
