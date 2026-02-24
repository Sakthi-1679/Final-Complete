import React, { useEffect, useState, useCallback } from 'react';
import Hero from '../components/Hero';
import Row from '../components/Row';
import MoodDetector from '../components/MoodDetector';
import { loadMoviesFromAPI, getContinueWatchingMovies, getRecommendations, getMoviesByMood } from '../services/storage';
import { getDynamicMoodRecommendations, getHybridRecommendations, logHybridInteraction } from '../services/ai';
import { Movie } from '../types';

// Get persistent anonymous user-id from localStorage (set by storage.ts)
const _getUserId = (): string => {
  try {
    const token = localStorage.getItem('authToken');
    if (token) {
      // Extract username from JWT payload (base64 middle part)
      const payload = JSON.parse(atob(token.split('.')[1] ?? '{}'));
      if (payload.username) return String(payload.username);
    }
    let uid = localStorage.getItem('streamflix_user_id');
    if (!uid) { uid = 'user_' + Date.now().toString(36); localStorage.setItem('streamflix_user_id', uid); }
    return uid;
  } catch { return 'guest'; }
};

const Home: React.FC = () => {
  const userId = _getUserId();

  const [movies, setMovies] = useState<Movie[]>([]);
  const [featured, setFeatured] = useState<Movie | null>(null);
  const [continueWatching, setContinueWatching] = useState<Movie[]>([]);
  const [recommendations, setRecommendations] = useState<Movie[]>([]);
  const [moodMovies, setMoodMovies] = useState<Movie[]>([]);
  const [currentMood, setCurrentMood] = useState<string | null>(null);
  const [moodLoading, setMoodLoading] = useState(false);
  const [moodSource, setMoodSource] = useState<string>('');
  const [modelVersion, setModelVersion] = useState<number>(0);
  const [feedbackMap, setFeedbackMap] = useState<Record<string, 'liked' | 'disliked'>>({});

  useEffect(() => {
    loadMoviesFromAPI().then(allMovies => {
      setMovies(allMovies);
      const trending = allMovies.filter(m => m.category === 'trending');
      setFeatured(trending[Math.floor(Math.random() * trending.length)] || allMovies[0]);
      setContinueWatching(getContinueWatchingMovies());
      setRecommendations(getRecommendations());
    });
  }, []);

  const fetchMoodMovies = useCallback(async (mood: string) => {
    setMoodLoading(true);
    setMoodMovies([]);
    setFeedbackMap({});
    try {
      const { movies: hybridMovies, source, version } = await getHybridRecommendations(mood, userId, 6);
      setMoodMovies(hybridMovies);
      setMoodSource(source);
      setModelVersion(version);
    } catch {
      try {
        const fallback = await getDynamicMoodRecommendations(mood, userId, 6);
        setMoodMovies(fallback);
        setMoodSource('fallback');
      } catch {
        const local = getMoviesByMood(mood);
        setMoodMovies(local);
        setMoodSource('local');
      }
    } finally {
      setMoodLoading(false);
    }
  }, [userId]);

  const handleMoodDetected = async (mood: string, suggestedMovies: string[] = []) => {
    setCurrentMood(mood);
    await fetchMoodMovies(mood);
    try {
      localStorage.setItem('streamflix_last_mood', mood);
      localStorage.setItem('streamflix_last_suggested_movies', suggestedMovies.join(' | '));
    } catch { /* ignore */ }
    setTimeout(() => {
      const moodRow = document.getElementById('mood-row');
      if (moodRow) moodRow.scrollIntoView({ behavior: 'smooth', block: 'center' });
    }, 500);
  };

  const handleRefresh = () => {
    if (currentMood) fetchMoodMovies(currentMood);
  };

  const handleLike = (movie: Movie, rank: number) => {
    setFeedbackMap(prev => ({ ...prev, [movie.id]: 'liked' }));
    logHybridInteraction({
      userId, movieId: movie.id, movieTitle: movie.title,
      mood: currentMood ?? '', liked: true, recommendedRankPosition: rank,
    });
  };

  const handleDislike = (movie: Movie, rank: number) => {
    setFeedbackMap(prev => ({ ...prev, [movie.id]: 'disliked' }));
    logHybridInteraction({
      userId, movieId: movie.id, movieTitle: movie.title,
      mood: currentMood ?? '', disliked: true, recommendedRankPosition: rank,
    });
  };

  if (!featured) return (
    <div className="h-screen w-full bg-netflix-dark flex flex-col items-center justify-center space-y-4">
      <div className="w-12 h-12 border-4 border-netflix-red border-t-transparent rounded-full animate-spin"></div>
      <p className="text-gray-400 animate-pulse">Loading StreamFlix...</p>
    </div>
  );

  return (
    <div className="pb-20 overflow-x-hidden">
      <Hero movie={featured} />

      {/* Dynamic Controls Bar */}
      <div className="relative z-30 px-4 md:px-12 flex items-center justify-end -mt-12 mb-4">
        <MoodDetector onMoodDetected={handleMoodDetected} />
      </div>

      <div className="relative z-20 -mt-16 md:-mt-24 space-y-4 md:space-y-8">

        {/* ── Mood Recommendations Row ─────────────────────────── */}
        {(moodLoading || moodMovies.length > 0) && (
          <div id="mood-row" className="animate-fade-in px-4 md:px-12">

            {/* Row header with badge + refresh */}
            <div className="flex flex-wrap items-center gap-3 mb-3">
              <h2 className="text-white font-bold text-lg md:text-xl">
                {currentMood
                  ? `${currentMood.charAt(0).toUpperCase() + currentMood.slice(1)} Mix`
                  : 'Mood Picks'}
              </h2>

              {/* "Recommended based on your mood" badge */}
              <span className="flex items-center gap-1.5 bg-netflix-red/20 border border-netflix-red/50 text-netflix-red text-xs font-semibold px-2.5 py-1 rounded-full">
                <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                  <path d="M9.049 2.927c.3-.921 1.603-.921 1.902 0l1.07 3.292a1 1 0 00.95.69h3.462c.969 0 1.371 1.24.588 1.81l-2.8 2.034a1 1 0 00-.364 1.118l1.07 3.292c.3.921-.755 1.688-1.54 1.118l-2.8-2.034a1 1 0 00-1.175 0l-2.8 2.034c-.784.57-1.838-.197-1.539-1.118l1.07-3.292a1 1 0 00-.364-1.118L2.98 8.72c-.783-.57-.38-1.81.588-1.81h3.461a1 1 0 00.951-.69l1.07-3.292z"/>
                </svg>
                Recommended based on your mood
                {modelVersion > 0 && (
                  <span className="opacity-60 ml-1">· v{modelVersion}</span>
                )}
              </span>

              {/* Refresh button */}
              <button
                onClick={handleRefresh}
                disabled={moodLoading}
                className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-white border border-gray-600 hover:border-gray-400 px-2.5 py-1 rounded-full transition-colors disabled:opacity-40"
                title="Refresh recommendations"
              >
                <svg className={`w-3 h-3 ${moodLoading ? 'animate-spin' : ''}`} fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15"/>
                </svg>
                Refresh
              </button>
            </div>

            {/* Loading skeleton */}
            {moodLoading && (
              <div className="flex gap-3 overflow-hidden">
                {[...Array(6)].map((_, i) => (
                  <div key={i} className="min-w-[160px] md:min-w-[220px] aspect-video bg-gray-800 rounded-md animate-pulse flex-shrink-0"/>
                ))}
              </div>
            )}

            {/* Movie cards with Like / Dislike */}
            {!moodLoading && moodMovies.length > 0 && (
              <div className="flex gap-3 overflow-x-auto pb-2 scrollbar-hide">
                {moodMovies.map((movie, idx) => {
                  const fb = feedbackMap[movie.id];
                  return (
                    <div key={movie.id} className="relative flex-shrink-0 min-w-[160px] md:min-w-[220px] group">
                      {/* reuse existing MovieCard via a manual structure to avoid prop mismatch */}
                      <a href={`/movie/${movie.id}`} className="block">
                        <div className="aspect-video relative overflow-hidden rounded-md bg-gray-900">
                          <img
                            src={movie.backdrop || movie.poster}
                            alt={movie.title}
                            loading="lazy"
                            className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
                          />
                          <div className="absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent opacity-0 group-hover:opacity-100 transition-opacity duration-300"/>
                          <div className="absolute bottom-2 left-2 right-2 opacity-0 group-hover:opacity-100 transition-opacity duration-300">
                            <p className="text-white text-xs font-semibold truncate">{movie.title}</p>
                          </div>
                        </div>
                      </a>

                      {/* Like / Dislike buttons */}
                      <div className="flex items-center justify-center gap-2 mt-1.5">
                        <button
                          onClick={() => handleLike(movie, idx + 1)}
                          className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors ${
                            fb === 'liked'
                              ? 'bg-green-600 border-green-600 text-white'
                              : 'border-gray-600 text-gray-400 hover:border-green-500 hover:text-green-400'
                          }`}
                          title="Like this recommendation"
                        >
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M2 10.5a1.5 1.5 0 113 0v6a1.5 1.5 0 01-3 0v-6zM6 10.333v5.43a2 2 0 001.106 1.79l.05.025A4 4 0 008.943 18h5.416a2 2 0 001.962-1.608l1.2-6A2 2 0 0015.56 8H12V4a2 2 0 00-2-2 1 1 0 00-1 1v.667a4 4 0 01-.8 2.4L6.8 7.933a4 4 0 00-.8 2.4z"/>
                          </svg>
                          Like
                        </button>
                        <button
                          onClick={() => handleDislike(movie, idx + 1)}
                          className={`flex items-center gap-1 text-xs px-2 py-0.5 rounded-full border transition-colors ${
                            fb === 'disliked'
                              ? 'bg-red-700 border-red-700 text-white'
                              : 'border-gray-600 text-gray-400 hover:border-red-500 hover:text-red-400'
                          }`}
                          title="Dislike this recommendation"
                        >
                          <svg className="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M18 9.5a1.5 1.5 0 11-3 0v-6a1.5 1.5 0 013 0v6zM14 9.667v-5.43a2 2 0 00-1.105-1.79l-.05-.025A4 4 0 0011.055 2H5.64a2 2 0 00-1.962 1.608l-1.2 6A2 2 0 004.44 12H8v4a2 2 0 002 2 1 1 0 001-1v-.667a4 4 0 01.8-2.4l1.4-1.866a4 4 0 00.8-2.4z"/>
                          </svg>
                          Dislike
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>
        )}

        {continueWatching.length > 0 && (
          <Row title="Continue Watching" movies={continueWatching} />
        )}

        <Row title="Recommended For You" movies={recommendations} />
        <Row title="Trending Now" movies={movies.filter(m => m.category === 'trending')} />
        <Row title="New Releases" movies={movies.filter(m => m.category === 'new')} />
        <Row title="Top Rated" movies={movies.filter(m => m.category === 'top_rated')} isLarge />

        <Row title="Action & Adventure" movies={movies.filter(m => m.genres.includes('Action') || m.genres.includes('Adventure'))} />
        <Row title="Sci-Fi Movies" movies={movies.filter(m => m.genres.includes('Sci-Fi'))} />
        <Row title="Emotional & Moving" movies={movies.filter(m => m.genres.includes('Emotional'))} />
        <Row title="Laughter & Comedy" movies={movies.filter(m => m.genres.includes('Comedy'))} />
        <Row title="Motivational & Inspiring" movies={movies.filter(m => m.genres.includes('Motivational'))} />
      </div>
    </div>
  );
};

export default Home;
