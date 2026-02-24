
import React, { useRef, useState, useEffect } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { getMovieById, addToHistory, getMediaFile } from '../services/storage';
import { Movie } from '../types';
import { buildApiUrl } from '../constants';
import { logHybridInteraction } from '../services/logger';

const Player: React.FC = () => {
  const { id } = useParams<{ id: string }>();
  const navigate = useNavigate();
  const location = useLocation();
  const videoRef = useRef<HTMLVideoElement>(null);
  const cameraRef = useRef<HTMLVideoElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const playerContainerRef = useRef<HTMLDivElement>(null);
  const [movie, setMovie] = useState<Movie | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [progress, setProgress] = useState(0);
  const [showControls, setShowControls] = useState(true);
  const [isCameraActive, setIsCameraActive] = useState(false);
  const controlsTimeoutRef = useRef<number | null>(null);
  const watchStartTimeRef = useRef<number>(0);
  const [localVideoSrc, setLocalVideoSrc] = useState<string | null>(null);
  const [urlVideoSrc, setUrlVideoSrc] = useState<string | null>(null);
  const [showUrlInput, setShowUrlInput] = useState(false);
  const [urlInputValue, setUrlInputValue] = useState('');
  const [videoType, setVideoType] = useState<'youtube' | 'url' | 'local'>('url');
  const [videoError, setVideoError] = useState<string | null>(null);
  const [isResolvingStoredVideo, setIsResolvingStoredVideo] = useState(false);

  // ── User interaction state ──────────────────────────────────────
  // null = no action, true = liked, false = disliked
  const [userLiked, setUserLiked] = useState<boolean | null>(null);
  const [userRating, setUserRating] = useState<number>(0);   // 0 = not rated, 1-5
  const [hoverRating, setHoverRating] = useState<number>(0);
  const [showRatingPanel, setShowRatingPanel] = useState(false);
  const [feedbackToast, setFeedbackToast] = useState<string | null>(null);
  const feedbackTimerRef = useRef<number | null>(null);

  // Check if URL is a playable YouTube video (not search results)
  const isYouTubeUrl = (url: string): boolean => {
    if (!url) return false;
    // Include direct YouTube video URLs but exclude search result URLs
    const isYouTube = url.includes('youtube.com') || url.includes('youtu.be');
    const isSearch = url.includes('/results') || url.includes('search_query');
    return isYouTube && !isSearch;
  };

  // Extract YouTube video ID from various URL formats
  const getYouTubeVideoId = (url: string): string | null => {
    if (!url) return null;
    
    // Handle youtube.com/watch?v=VIDEO_ID
    const watchMatch = url.match(/[?&]v=([^&]+)/);
    if (watchMatch) return watchMatch[1];
    
    // Handle youtu.be/VIDEO_ID
    const shortMatch = url.match(/youtu\.be\/([^?]+)/);
    if (shortMatch) return shortMatch[1];
    
    // Handle youtube.com/embed/VIDEO_ID
    const embedMatch = url.match(/youtube\.com\/embed\/([^?]+)/);
    if (embedMatch) return embedMatch[1];
    
    return null;
  };

  // Convert YouTube URL to embed URL
  const getYouTubeEmbedUrl = (url: string): string => {
    const videoId = getYouTubeVideoId(url);
    if (videoId) {
      return `https://www.youtube.com/embed/${videoId}?autoplay=1&rel=0`;
    }
    return url;
  };

  // ── Interaction helpers ──────────────────────────────────────────
  const showToast = (msg: string) => {
    setFeedbackToast(msg);
    if (feedbackTimerRef.current) window.clearTimeout(feedbackTimerRef.current);
    feedbackTimerRef.current = window.setTimeout(() => setFeedbackToast(null), 3000);
  };

  const getWatchTimeSec = () => {
    if (videoRef.current && isFinite(videoRef.current.currentTime))
      return Math.round(videoRef.current.currentTime);
    return Math.round((Date.now() - watchStartTimeRef.current) / 1000);
  };

  const submitInteraction = (liked: boolean | null, rating: number) => {
    if (!movie) return;
    logHybridInteraction(movie.id, movie.title, {
      liked,
      rating,
      watchTime: getWatchTimeSec(),
      rank: movie._recommendedRank ?? null,
    });
  };

  const handleLike = () => {
    const newVal = userLiked === true ? null : true;
    setUserLiked(newVal);
    submitInteraction(newVal, userRating);
    showToast(newVal === true ? "\uD83D\uDC4D Liked! We'll find more like this." : 'Removed like');
  };

  const handleDislike = () => {
    const newVal = userLiked === false ? null : false;
    setUserLiked(newVal);
    submitInteraction(newVal, userRating);
    showToast(newVal === false ? "\uD83D\uDC4E Got it. We'll show less like this." : 'Removed dislike');
  };

  const handleRate = (star: number) => {
    setUserRating(star);
    setShowRatingPanel(false);
    submitInteraction(userLiked, star);
    showToast(`\u2B50 Rated ${star}/5 \u2014 Thanks for your feedback!`);
  };

  // Handle local file selection
  const handleLocalFile = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) {
      setVideoError(null);
      const objectUrl = URL.createObjectURL(file);
      if (localVideoSrc && localVideoSrc.startsWith('blob:')) {
        URL.revokeObjectURL(localVideoSrc);
      }
      setLocalVideoSrc(objectUrl);
      setUrlVideoSrc(null);
      setVideoType('local');
    }
  };

  const handleUrlSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (urlInputValue.trim()) {
      setVideoError(null);
      // Check if it's a YouTube URL
      if (isYouTubeUrl(urlInputValue)) {
        setVideoType('youtube');
        setMovie((prev) => (prev ? { ...prev, videoUrl: urlInputValue } : prev));
      } else {
        setUrlVideoSrc(urlInputValue.trim());
        setLocalVideoSrc(null);
        setVideoType('url');
      }
      setShowUrlInput(false);
      setUrlInputValue('');
    }
  };

  // Handle video load error
  const handleVideoError = (e: React.SyntheticEvent<HTMLVideoElement, Event>) => {
    const video = e.currentTarget;
    let errorMessage = 'Failed to load video. ';
    
    if (video.error) {
      switch (video.error.code) {
        case MediaError.MEDIA_ERR_ABORTED:
          errorMessage += 'Video playback was aborted.';
          break;
        case MediaError.MEDIA_ERR_NETWORK:
          errorMessage += 'A network error occurred while loading the video.';
          break;
        case MediaError.MEDIA_ERR_DECODE:
          errorMessage += 'Video decoding failed. The format may not be supported.';
          break;
        case MediaError.MEDIA_ERR_SRC_NOT_SUPPORTED:
          errorMessage += 'Video format not supported or source not found.';
          break;
        default:
          errorMessage += 'Unknown error occurred.';
      }
    }
    
    console.error('[Player] Video error:', video.error);
    setVideoError(errorMessage);
  };

  // Handle video loaded successfully
  const handleVideoLoaded = () => {
    console.log('[Player] Video loaded successfully');
    setVideoError(null);
  };
  
  // Handle when video can start playing
  const handleCanPlay = () => {
    console.log('[Player] Video can play');
    setVideoError(null);
  };

  // Open file picker
  const openFilePicker = () => {
    fileInputRef.current?.click();
  };

  // Check if URL is a direct video file (mp4, webm, etc.)
  const isDirectVideoUrl = (url: string): boolean => {
    if (!url) return false;
    const videoExtensions = ['.mp4', '.webm', '.ogg', '.mov', '.avi', '.mkv'];
    return videoExtensions.some(ext => url.toLowerCase().endsWith(ext)) || url.startsWith('blob:') || url.startsWith('data:video');
  };

  const isIndexedDbVideoId = (value?: string): boolean => {
    return Boolean(value && value.startsWith('video_'));
  };

  useEffect(() => {
    const loadMovie = async () => {
      if (id) {
        const found = getMovieById(id);
        if (found) {
          setMovie(found);
          addToHistory(found.id);
          watchStartTimeRef.current = Date.now();

          fetch(buildApiUrl('/log_event'), {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
              event_type: 'WATCH',
              user_id: localStorage.getItem('streamflix_user_id') || 'anonymous',
              movie_id: found.id,
              movie_title: found.title,
              detected_mood: localStorage.getItem('streamflix_last_mood') || '',
              genre: found.genres.join(' | '),
            }),
          }).catch(() => {});
          
          // Check if videoUrl is an IndexedDB reference (starts with 'video_')
          if (found.videoUrl && found.videoUrl.startsWith('video_')) {
            console.log('[Player] Loading video from IndexedDB:', found.videoUrl);
            setIsResolvingStoredVideo(true);
            setVideoError(null);
            
            try {
              const blobUrl = await getMediaFile(found.videoUrl);
              console.log('[Player] Got blob URL:', blobUrl);
              
              if (blobUrl) {
                setLocalVideoSrc(blobUrl);
                setVideoType('local');
                setVideoError(null);
              } else {
                console.error('[Player] Failed to get blob URL for video:', found.videoUrl);
                setLocalVideoSrc(null);
                setVideoType('local');
                setVideoError('Uploaded video could not be loaded. The video may have been deleted or corrupted. Please re-upload this video.');
              }
            } catch (error) {
              console.error('[Player] Error loading video from IndexedDB:', error);
              setLocalVideoSrc(null);
              setVideoType('local');
              setVideoError('Error loading video: ' + (error instanceof Error ? error.message : 'Unknown error'));
            }
            
            setIsResolvingStoredVideo(false);
          } else if (isYouTubeUrl(found.videoUrl)) {
            setVideoType('youtube');
          } else if (isDirectVideoUrl(found.videoUrl)) {
            setVideoType('url');
          } else {
            setVideoType('url'); // Default to URL type for any other direct link
          }
        } else {
          navigate('/');
        }
      }
    };
    
    loadMovie();
  }, [id, navigate]);

  // Log watch event when component unmounts or movie changes
  useEffect(() => {
    return () => {
      if (movie && watchStartTimeRef.current > 0) {
        const watchDuration = Math.round((Date.now() - watchStartTimeRef.current) / 1000);
        fetch(buildApiUrl('/log_event'), {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({
            event_type: 'WATCH_END',
            user_id: localStorage.getItem('streamflix_user_id') || 'anonymous',
            movie_id: movie.id,
            movie_title: movie.title,
            watch_duration: watchDuration,
            detected_mood: localStorage.getItem('streamflix_last_mood') || '',
            genre: movie.genres.join(' | '),
          }),
        }).catch(() => {});
      }
    };
  }, [movie]);

  useEffect(() => {
    return () => {
      if (localVideoSrc && localVideoSrc.startsWith('blob:')) {
        URL.revokeObjectURL(localVideoSrc);
      }
    };
  }, [localVideoSrc]);

  // Reaction Mode Logic
  useEffect(() => {
    let activeStream: MediaStream | null = null;
    let timerId: number | null = null;
    
    const startReactionCheck = async () => {
      if (!movie) return;
      
      if (typeof navigator !== 'undefined' && navigator.mediaDevices?.getUserMedia) {
        try {
          const stream = await navigator.mediaDevices.getUserMedia({ 
            video: { width: 320, height: 240 }, 
            audio: false
          });
          
          activeStream = stream;
          setIsCameraActive(true);

          if (cameraRef.current) {
            cameraRef.current.srcObject = stream;
          }

          timerId = window.setTimeout(() => {
            setIsCameraActive(false);
            if (activeStream) {
              activeStream.getTracks().forEach(track => track.stop());
            }
          }, 10000);
        } catch (err) {
          setIsCameraActive(false);
          console.log("Reaction Mode skipped due to restrictions.");
        }
      }
    };

    startReactionCheck();

    return () => {
      if (timerId) window.clearTimeout(timerId);
      if (activeStream) {
        activeStream.getTracks().forEach(track => track.stop());
      }
      setIsCameraActive(false);
    };
  }, [movie]);

  useEffect(() => {
    if (!movie) return;

    const lastMood = localStorage.getItem('streamflix_last_mood') || '';
    const suggestedMovies = localStorage.getItem('streamflix_last_suggested_movies') || '';

    fetch(buildApiUrl('/log_watch'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        watched_movie: movie.title,
        mood: lastMood,
        suggested_movies: suggestedMovies,
        watched_movie_genre: movie.genres.join(' | '),
      }),
    }).catch(() => {});
  }, [movie]);

  useEffect(() => {
    const video = videoRef.current;
    if (video && movie) {
      const playPromise = video.play();
      if (playPromise !== undefined) {
        playPromise.catch(() => {});
      }
    }
  }, [movie]);

  useEffect(() => {
    const video = videoRef.current;
    if (!video) return;

    const onPlay = () => setIsPlaying(true);
    const onPause = () => setIsPlaying(false);

    video.addEventListener('play', onPlay);
    video.addEventListener('pause', onPause);

    return () => {
      video.removeEventListener('play', onPlay);
      video.removeEventListener('pause', onPause);
    };
  }, [movie]);


  useEffect(() => {
    return () => {
      if (controlsTimeoutRef.current) {
        window.clearTimeout(controlsTimeoutRef.current);
      }
    };
  }, []);

  // Load previously saved like/rating from localStorage
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

  // Cleanup feedback timer on unmount
  useEffect(() => {
    return () => { if (feedbackTimerRef.current) window.clearTimeout(feedbackTimerRef.current); };
  }, []);

  const handleMouseMove = () => {
    setShowControls(true);
    if (controlsTimeoutRef.current) {
      window.clearTimeout(controlsTimeoutRef.current);
    }
    controlsTimeoutRef.current = window.setTimeout(() => {
      if (isPlaying) setShowControls(false);
    }, 3000);
  };

  const togglePlay = async (e?: React.MouseEvent) => {
    if (e) e.stopPropagation();
    const video = videoRef.current;
    if (video) {
      if (video.paused) {
        try {
          await video.play();
        } catch (error: any) {
          if (error.name !== 'AbortError') console.error("Playback failed", error);
        }
      } else {
        video.pause();
      }
    }
  };

  const handleTimeUpdate = () => {
    if (videoRef.current) {
      const current = videoRef.current.currentTime;
      const duration = videoRef.current.duration;
      if (duration > 0) {
        setProgress((current / duration) * 100);
      }
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (videoRef.current) {
      const time = (parseFloat(e.target.value) / 100) * videoRef.current.duration;
      videoRef.current.currentTime = time;
      setProgress(parseFloat(e.target.value));
    }
  };

  // Check if still loading
  if ((!movie && !localVideoSrc && !urlVideoSrc) || isResolvingStoredVideo) {
    return (
      <div className="bg-black text-white h-screen flex flex-col items-center justify-center">
        <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-netflix-red mb-4"></div>
        <div className="text-lg">Loading video...</div>
      </div>
    );
  }

  // Determine what video source to use
  const getVideoSource = () => {
    if (localVideoSrc) return localVideoSrc;
    if (urlVideoSrc) return urlVideoSrc;
    if (movie?.videoUrl && !isIndexedDbVideoId(movie.videoUrl)) return movie.videoUrl;
    return '';
  };

  const currentVideoSrc = getVideoSource();
  
  // Check if we should show native player
  const shouldShowNativePlayer = () => {
    // If local file
    if (videoType === 'local' && localVideoSrc) return true;
    // If URL type and has source
    if (videoType === 'url' && currentVideoSrc) return true;
    // If movie has videoUrl (not YouTube)
    if (movie?.videoUrl && !isIndexedDbVideoId(movie.videoUrl) && !isYouTubeUrl(movie.videoUrl)) return true;
    return false;
  };
  
  const showNativePlayer = shouldShowNativePlayer();
  
  // Check if it's YouTube
  const isYouTube = () => {
    if (videoType === 'youtube') return true;
    if (movie?.videoUrl && isYouTubeUrl(movie.videoUrl)) return true;
    return false;
  };

  return (
    <div 
      ref={playerContainerRef}
      className="relative w-full h-screen bg-black overflow-hidden group select-none cursor-pointer"
      onMouseMove={handleMouseMove}
      onClick={() => showNativePlayer && togglePlay()}
    >
      {/* Hidden file input for local video selection */}
      <input
        ref={fileInputRef}
        type="file"
        accept="video/*"
        onChange={handleLocalFile}
        className="hidden"
      />

      {/* Video Player or YouTube Embed */}
      {isYouTube() ? (
        <iframe
          src={getYouTubeEmbedUrl(movie?.videoUrl || '')}
          className="w-full h-full"
          frameBorder="0"
          allow="accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture"
          allowFullScreen
          title={movie?.title || 'Video'}
        />
      ) : showNativePlayer ? (
        <div className="w-full h-full relative">
          <video
            ref={videoRef}
            src={currentVideoSrc}
            className="w-full h-full object-contain"
            onTimeUpdate={handleTimeUpdate}
            onError={handleVideoError}
            onLoadedMetadata={handleVideoLoaded}
            onCanPlay={handleCanPlay}
            autoPlay
            controls
            playsInline
            preload="auto"
          />
          {videoError && (
            <div className="absolute inset-0 flex items-center justify-center bg-black/80">
              <div className="text-center text-white p-4">
                <i className="fas fa-exclamation-triangle text-4xl text-yellow-500 mb-2"></i>
                <p className="text-lg">{videoError}</p>
                <button
                  onClick={(e) => {
                    e.stopPropagation();
                    setVideoError(null);
                    // Re-fetch the video from IndexedDB if it's a stored video
                    if (movie?.videoUrl?.startsWith('video_')) {
                      setIsResolvingStoredVideo(true);
                      getMediaFile(movie.videoUrl).then((blobUrl) => {
                        if (blobUrl) {
                          setLocalVideoSrc(blobUrl);
                        }
                        setIsResolvingStoredVideo(false);
                      });
                    } else {
                      videoRef.current?.load();
                      videoRef.current?.play().catch(() => {});
                    }
                  }}
                  className="mt-4 px-4 py-2 bg-netflix-red rounded hover:bg-red-700 transition-colors"
                >
                  Retry
                </button>
              </div>
            </div>
          )}
        </div>
      ) : (
        <div className="w-full h-full flex flex-col items-center justify-center text-white">
          <div className="text-center space-y-4">
            <i className="fas fa-film text-6xl text-gray-600"></i>
            <p className="text-xl text-gray-400">No video source available</p>
            <button
              onClick={(e) => {
                e.stopPropagation();
                navigate('/');
              }}
              className="px-6 py-3 bg-netflix-red text-white rounded-lg hover:bg-red-700 transition-colors"
            >
              Back to Home
            </button>
          </div>
        </div>
      )}

      {/* Camera Preview Overlay */}
      {isCameraActive && (
        <div className="absolute top-8 right-8 w-40 h-28 md:w-48 md:h-32 rounded-lg overflow-hidden border-2 border-netflix-red shadow-2xl z-50 bg-black animate-zoom-in pointer-events-none">
           <video ref={cameraRef} autoPlay muted playsInline className="w-full h-full object-cover" style={{ transform: 'scaleX(-1)' }} />
           <div className="absolute bottom-1 right-1 flex items-center space-x-1 bg-black/60 px-1.5 py-0.5 rounded text-[8px] font-bold text-white">
              <span className="w-1.5 h-1.5 bg-red-500 rounded-full animate-pulse"></span>
              <span>REACTION MODE</span>
           </div>
        </div>
      )}

      {/* Controls Overlay - Hidden for YouTube */}
      {(!isYouTube()) && (
        <div className={`absolute inset-0 bg-gradient-to-t from-black/80 via-transparent to-transparent flex flex-col justify-end p-4 md:p-8 transition-opacity duration-300 pointer-events-none ${showControls ? 'opacity-100' : 'opacity-0'}`}>
          
          {/* Back Button */}
          <button 
            onClick={(e) => { e.stopPropagation(); navigate(-1); }}
            className="absolute top-4 left-4 md:top-8 md:left-8 text-white hover:text-gray-300 text-2xl md:text-3xl pointer-events-auto transition-transform hover:scale-110 z-50"
          >
            <i className="fas fa-arrow-left"></i>
          </button>

          {/* URL Input Overlay */}
          {showUrlInput && (
            <div className="absolute top-20 right-4 md:top-24 md:right-8 z-50 bg-black/90 p-3 rounded-lg" onClick={(e) => e.stopPropagation()}>
              <form onSubmit={handleUrlSubmit} className="flex flex-col gap-2">
                <input
                  type="text"
                  value={urlInputValue}
                  onChange={(e) => setUrlInputValue(e.target.value)}
                  placeholder="Enter video URL..."
                  className="px-3 py-2 bg-gray-800 text-white rounded border border-gray-600 focus:border-netflix-red focus:outline-none text-sm w-64"
                  autoFocus
                />
                <button 
                  type="submit"
                  className="px-4 py-2 bg-green-600 text-white rounded hover:bg-green-700 text-sm"
                >
                  Load URL
                </button>
              </form>
            </div>
          )}

          <div className="space-y-4 pointer-events-auto" onClick={(e) => e.stopPropagation()}>
            <div className="text-white text-lg md:text-xl font-bold drop-shadow-md">
              {movie?.title || 'Local Video'}
              {videoType === 'local' && <span className="ml-2 text-sm text-gray-400">(Local File)</span>}
            </div>
            
            <div className="relative group/progress">
              <input 
                type="range" 
                min="0" 
                max="100" 
                value={progress} 
                onChange={handleSeek}
                className="w-full h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer accent-netflix-red focus:outline-none focus:ring-2 focus:ring-netflix-red/50 transition-all hover:h-2"
              />
            </div>

            <div className="flex items-center justify-between">
              <div className="flex items-center space-x-4 md:space-x-6">
                <button onClick={(e) => togglePlay(e)} className="text-white text-2xl md:text-3xl hover:text-netflix-red transition-colors hover:scale-110 transform">
                  <i className={`fas ${isPlaying ? 'fa-pause' : 'fa-play'}`}></i>
                </button>
                <button onClick={() => videoRef.current && (videoRef.current.currentTime -= 10)} className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">
                  <i className="fas fa-undo-alt mr-1"></i> 10s
                </button>
                <button onClick={() => videoRef.current && (videoRef.current.currentTime += 10)} className="text-gray-300 hover:text-white transition-colors text-xs md:text-sm">
                   10s <i className="fas fa-redo-alt ml-1"></i>
                </button>
                <div className="text-gray-300 text-xs md:text-sm font-medium">
                   {videoRef.current ? Math.floor(videoRef.current.currentTime / 60) : 0}:{('0' + Math.floor(videoRef.current ? videoRef.current.currentTime % 60 : 0)).slice(-2)} / 
                   {videoRef.current ? Math.floor(videoRef.current.duration / 60) : 0}:{('0' + Math.floor(videoRef.current ? videoRef.current.duration % 60 : 0)).slice(-2)}
                </div>
              </div>

              <div className="flex items-center space-x-3 md:space-x-4">
                {/* Like */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleLike(); }}
                  title={userLiked === true ? 'Remove like' : 'Like this movie'}
                  className={`text-xl md:text-2xl transition-all hover:scale-110 ${
                    userLiked === true ? 'text-netflix-red drop-shadow-[0_0_6px_rgba(229,9,20,0.8)]' : 'text-white hover:text-netflix-red'
                  }`}
                >
                  <i className={`fa${userLiked === true ? 's' : 'r'} fa-thumbs-up`}></i>
                </button>
                {/* Dislike */}
                <button
                  onClick={(e) => { e.stopPropagation(); handleDislike(); }}
                  title={userLiked === false ? 'Remove dislike' : 'Not for me'}
                  className={`text-xl md:text-2xl transition-all hover:scale-110 ${
                    userLiked === false ? 'text-netflix-red drop-shadow-[0_0_6px_rgba(229,9,20,0.8)]' : 'text-white hover:text-white/70'
                  }`}
                >
                  <i className={`fa${userLiked === false ? 's' : 'r'} fa-thumbs-down`}></i>
                </button>
                {/* Star rating trigger */}
                <button
                  onClick={(e) => { e.stopPropagation(); setShowRatingPanel(p => !p); }}
                  title="Rate this movie"
                  className={`text-lg md:text-xl transition-all hover:scale-110 flex items-center gap-1 ${
                    userRating > 0 ? 'text-yellow-400' : 'text-white hover:text-yellow-300'
                  }`}
                >
                  <i className="fas fa-star"></i>
                  {userRating > 0 && <span className="text-xs font-bold">{userRating}/5</span>}
                </button>
                {/* Captions */}
                <button className="text-white hover:text-gray-300 transition-colors">
                  <i className="fas fa-closed-captioning text-lg md:text-xl"></i>
                </button>
              </div>
            </div>
          </div>

          {/* ── Star rating panel ──────────────────────────────────────── */}
          {showRatingPanel && (
            <div
              className="absolute bottom-24 right-4 md:right-8 bg-black/95 border border-white/20 rounded-2xl px-5 py-4 z-50 shadow-2xl pointer-events-auto"
              onClick={(e) => e.stopPropagation()}
            >
              <p className="text-white text-sm font-semibold mb-3 text-center">Rate this movie</p>
              <div className="flex items-center space-x-1">
                {[1, 2, 3, 4, 5].map(star => (
                  <button
                    key={star}
                    onMouseEnter={() => setHoverRating(star)}
                    onMouseLeave={() => setHoverRating(0)}
                    onClick={(e) => { e.stopPropagation(); handleRate(star); }}
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
                    onClick={(e) => { e.stopPropagation(); handleRate(0); setUserRating(0); setShowRatingPanel(false); }}
                    className="text-gray-400 hover:text-white text-xs underline"
                  >
                    Clear
                  </button>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* ── Feedback toast ─────────────────────────────────────────── */}
      {feedbackToast && (
        <div className="absolute bottom-28 left-1/2 -translate-x-1/2 bg-black/90 border border-white/20 text-white px-6 py-2.5 rounded-full text-sm font-medium z-[60] whitespace-nowrap shadow-2xl pointer-events-none">
          {feedbackToast}
        </div>
      )}
    </div>
  );
};

export default Player;
