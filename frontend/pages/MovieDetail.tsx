import React, { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { loadMoviesFromAPI, toggleMyList, getMyList } from '../services/storage';
import { Movie } from '../types';
import MovieCard from '../components/MovieCard';
import { logHybridInteraction } from '../services/logger';

// Convert YouTube watch URL to embed URL
const getYouTubeEmbedUrl = (url: string): string | null => {
  if (!url) return null;
  
  // Check if it's a YouTube URL
  if (!url.includes('youtube.com') && !url.includes('youtu.be')) {
    return null;
  }
  
  // Handle youtube.com/watch?v=VIDEO_ID
  const watchMatch = url.match(/[?&]v=([^&]+)/);
  if (watchMatch) {
    return `https://www.youtube.com/embed/${watchMatch[1]}`;
  }
  
  // Handle youtu.be/VIDEO_ID
  const shortMatch = url.match(/youtu\.be\/([^?]+)/);
  if (shortMatch) {
    return `https://www.youtube.com/embed/${shortMatch[1]}`;
  }
  
  return null;
};

const MovieDetail: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const [movie, setMovie] = useState<Movie | null>(null);
  const [similar, setSimilar] = useState<Movie[]>([]);
  const [inList, setInList] = useState(false);
  // ── Like / Dislike / Rating state ──────────────────────────────
  const [userLiked, setUserLiked] = useState<boolean | null>(null);
  const [userRating, setUserRating] = useState<number>(0);
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [showRatingPanel, setShowRatingPanel] = useState(false);
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);

  useEffect(() => {
    window.scrollTo(0, 0);
    if (id) {
      loadMoviesFromAPI().then(allMovies => {
        const found = allMovies.find(m => m.id === id);
        setMovie(found || null);
        setInList(getMyList().includes(id));
        if (found) {
          const related = allMovies.filter(m => m.id !== id && m.genres.some(g => found.genres.includes(g)));
          setSimilar(related);
        }
      });
    }
  }, [id]);

  const handleListToggle = () => {
    if (movie) {
      toggleMyList(movie.id);
      setInList(!inList);
    }
  };

  // Load saved feedback from localStorage when movie is ready
  useEffect(() => {
    if (!movie) return;
    const saved = localStorage.getItem(`streamflix_feedback_${movie.id}`);
    if (saved) {
      try {
        const data = JSON.parse(saved);
        if (data.liked !== undefined) setUserLiked(data.liked);
        if (data.rating)             setUserRating(data.rating);
      } catch {}
    }
  }, [movie?.id]);

  const showDetailToast = (msg: string) => {
    setFeedbackToast(msg);
    setTimeout(() => setFeedbackToast(null), 3500);
  };

  const handleLike = () => {
    if (!movie) return;
    const newVal = userLiked === true ? null : true;
    setUserLiked(newVal);
    logHybridInteraction(movie.id, movie.title, { liked: newVal, rating: userRating });
    showDetailToast(newVal === true ? "\uD83D\uDC4D Liked! We'll recommend more like this." : 'Removed like');
  };

  const handleDislike = () => {
    if (!movie) return;
    const newVal = userLiked === false ? null : false;
    setUserLiked(newVal);
    logHybridInteraction(movie.id, movie.title, { liked: newVal, rating: userRating });
    showDetailToast(newVal === false ? "\uD83D\uDC4E Got it. We'll show less like this." : 'Removed dislike');
  };

  const handleDetailRate = (star: number) => {
    if (!movie) return;
    const newRating = userRating === star ? 0 : star; // clicking same star clears
    setUserRating(newRating);
    setShowRatingPanel(false);
    logHybridInteraction(movie.id, movie.title, { liked: userLiked, rating: newRating });
    if (newRating > 0) showDetailToast(`\u2B50 Rated ${newRating}/5 \u2014 Thanks for your feedback!`);
    else showDetailToast('Rating removed');
  };

  if (!movie) return <div className="min-h-screen bg-netflix-dark flex items-center justify-center">Movie not found</div>;

  const embedUrl = getYouTubeEmbedUrl(movie.trailerUrl || '');

  return (
    <div className="pb-20 bg-[#141414] min-h-screen">
      {/* Banner */}
      <div className="relative h-[70vh] w-full">
        <div className="absolute inset-0">
             <img src={movie.backdrop} alt={movie.title} className="w-full h-full object-cover animate-fade-in" />
             {/* Gradient overlay for text readability */}
             <div className="absolute inset-0 bg-gradient-to-r from-[#141414] via-[#141414]/50 to-transparent"></div>
             {/* Bottom fade into content */}
             <div className="absolute bottom-0 left-0 right-0 h-48 bg-gradient-to-t from-[#141414] to-transparent"></div>
        </div>
        
        <div className="absolute bottom-12 left-4 md:left-12 max-w-3xl pr-4 animate-slide-up">
          <h1 className="text-4xl md:text-6xl font-extrabold mb-4 text-white drop-shadow-xl">{movie.title}</h1>
          
          <div className="flex items-center space-x-4 text-gray-300 mb-8 text-sm md:text-base">
            <span className="text-green-500 font-bold">98% Match</span>
            <span>{movie.year}</span>
            <span className="border border-gray-400 px-2 rounded text-xs bg-black/20">{movie.rating}</span>
            <span>{movie.duration}</span>
            <span className="border border-gray-400 px-1 text-xs rounded">HD</span>
          </div>

          {/* ── Action buttons row ─────────────────────────────────────── */}
          <div className="flex flex-wrap items-center gap-3 mb-6">
            <Link to={`/watch/${movie.id}`} state={{ autoFullscreen: true }} className="bg-white text-black px-8 py-3 rounded font-bold hover:bg-gray-200 hover:scale-105 transition-all flex items-center shadow-lg">
              <i className="fas fa-play mr-3"></i> Play
            </Link>
            <button
              onClick={handleListToggle}
              className={`px-6 py-3 rounded font-bold transition-all flex items-center shadow-lg border-2 ${
                inList ? 'border-green-500 text-green-500 bg-black/50' : 'bg-gray-500/50 text-white border-transparent hover:bg-gray-500/70'
              }`}
            >
              <i className={`fas ${inList ? 'fa-check' : 'fa-plus'} mr-2`}></i>
              {inList ? 'In My List' : 'My List'}
            </button>

            {/* Like button */}
            <button
              onClick={handleLike}
              title={userLiked === true ? 'Remove like' : 'Like this movie'}
              className={`px-5 py-3 rounded font-bold transition-all flex items-center gap-2 border-2 shadow-lg ${
                userLiked === true
                  ? 'border-netflix-red bg-netflix-red/20 text-netflix-red'
                  : 'border-white/30 text-white hover:border-white hover:bg-white/10'
              }`}
            >
              <i className={`fa${userLiked === true ? 's' : 'r'} fa-thumbs-up text-lg`}></i>
              <span className="hidden sm:inline">{userLiked === true ? 'Liked' : 'Like'}</span>
            </button>

            {/* Dislike button */}
            <button
              onClick={handleDislike}
              title={userLiked === false ? 'Remove dislike' : 'Not for me'}
              className={`px-5 py-3 rounded font-bold transition-all flex items-center gap-2 border-2 shadow-lg ${
                userLiked === false
                  ? 'border-gray-400 bg-gray-600/30 text-gray-300'
                  : 'border-white/30 text-white hover:border-white hover:bg-white/10'
              }`}
            >
              <i className={`fa${userLiked === false ? 's' : 'r'} fa-thumbs-down text-lg`}></i>
              <span className="hidden sm:inline">{userLiked === false ? 'Disliked' : 'Dislike'}</span>
            </button>

            {/* Star rating */}
            <div className="relative">
              <button
                onClick={() => setShowRatingPanel(p => !p)}
                title="Rate this movie"
                className={`px-5 py-3 rounded font-bold transition-all flex items-center gap-2 border-2 shadow-lg ${
                  userRating > 0
                    ? 'border-yellow-400 bg-yellow-400/10 text-yellow-400'
                    : 'border-white/30 text-white hover:border-yellow-400 hover:text-yellow-300 hover:bg-yellow-400/10'
                }`}
              >
                <i className="fas fa-star text-lg"></i>
                <span>{userRating > 0 ? `${userRating}/5` : 'Rate'}</span>
              </button>

              {showRatingPanel && (
                <div className="absolute left-0 top-full mt-2 bg-[#1a1a1a] border border-white/20 rounded-2xl px-5 py-4 z-50 shadow-2xl min-w-[220px]">
                  <p className="text-white text-sm font-semibold mb-3 text-center">Rate this movie</p>
                  <div className="flex items-center justify-center space-x-1">
                    {[1, 2, 3, 4, 5].map(star => (
                      <button
                        key={star}
                        onMouseEnter={() => setHoverRating(star)}
                        onMouseLeave={() => setHoverRating(0)}
                        onClick={() => handleDetailRate(star)}
                        className="transition-transform hover:scale-125 p-1"
                      >
                        <i className={`fas fa-star text-2xl ${
                          star <= (hoverRating || userRating) ? 'text-yellow-400' : 'text-gray-600'
                        }`}></i>
                      </button>
                    ))}
                  </div>
                  {userRating > 0 && (
                    <div className="flex items-center justify-between mt-3">
                      <p className="text-yellow-400 text-xs">Your rating: {userRating}/5</p>
                      <button
                        onClick={() => handleDetailRate(userRating)}
                        className="text-gray-400 hover:text-white text-xs underline"
                      >
                        Clear
                      </button>
                    </div>
                  )}
                </div>
              )}
            </div>
          </div>

          {/* Feedback toast */}
          {feedbackToast && (
            <div className="inline-flex items-center gap-2 bg-black/80 border border-white/20 text-white px-5 py-2.5 rounded-full text-sm font-medium mb-4 shadow-lg">
              {feedbackToast}
            </div>
          )}

          <div className="grid grid-cols-1 md:grid-cols-3 gap-8 text-sm text-gray-300">
             <div className="md:col-span-2">
                 <p className="text-base md:text-lg leading-relaxed text-white mb-4">{movie.description}</p>
             </div>
             <div className="space-y-2 text-xs md:text-sm">
                 <div className="flex flex-wrap gap-1">
                    <span className="text-gray-500">Genres:</span>
                    {movie.genres.map((g, i) => (
                        <span key={g} className="text-white hover:underline cursor-pointer">
                            {g}{i < movie.genres.length - 1 ? ',' : ''}
                        </span>
                    ))}
                 </div>
                 <div><span className="text-gray-500">Maturity Rating:</span> <span className="border border-gray-600 px-1 text-[10px]">{movie.rating}</span></div>
             </div>
          </div>
        </div>
      </div>

      {/* Similar Content */}
      <div className="px-4 md:px-12 mt-4 space-y-6">
        <h2 className="text-2xl font-bold text-white border-l-4 border-netflix-red pl-3">More Like This</h2>
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-5 xl:grid-cols-6 gap-4">
          {similar.length > 0 ? (
            similar.slice(0, 12).map(m => (
              <MovieCard key={m.id} movie={m} className="w-full" />
            ))
          ) : (
            <p className="text-gray-500 italic">No similar movies found.</p>
          )}
        </div>
      </div>

      {/* Trailer Section */}
      <div className="px-4 md:px-12 mt-8">
        <h2 className="text-2xl font-bold text-white border-l-4 border-netflix-red pl-3 mb-4">Trailer</h2>
        {embedUrl ? (
          <div className="relative w-full max-w-4xl mx-auto" style={{ paddingBottom: '56.25%' }}>
            <iframe
              src={embedUrl}
              className="absolute top-0 left-0 w-full h-full rounded-lg shadow-xl"
              title={`${movie.title} Trailer`}
              frameBorder="0"
              allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
              allowFullScreen
            />
          </div>
        ) : (
          <div className="bg-gray-800 rounded-lg p-8 text-center max-w-4xl mx-auto">
            <p className="text-gray-400 text-lg">Trailer not available.</p>
          </div>
        )}
      </div>
    </div>
  );
};

export default MovieDetail;