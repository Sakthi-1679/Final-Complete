
import { Movie, MovieFormData, Recommendation } from '../types';

// Keys for LocalStorage (movies are NOT persisted here — they come from the backend API)
const HISTORY_KEY = 'streamflix_history';
const MY_LIST_KEY = 'streamflix_mylist';
const USER_ID_KEY = 'streamflix_user_id';

// ==================== BACKEND SYNC HELPERS ====================

const _getAuthHeaders = (): Record<string, string> => {
  const token = localStorage.getItem('authToken');
  return token ? { 'Authorization': `Bearer ${token}`, 'Content-Type': 'application/json' } : { 'Content-Type': 'application/json' };
};

/** Fire-and-forget backend sync — never throws, never blocks UI */
const _apiSync = (method: string, path: string, body?: unknown): void => {
  import('../constants').then(({ buildApiUrl }) => {
    fetch(buildApiUrl(path), {
      method,
      headers: _getAuthHeaders(),
      body: body !== undefined ? JSON.stringify(body) : undefined,
    }).catch(err => console.warn(`[Sync] ${method} ${path} failed:`, err));
  });
};

/** Awaitable backend request — resolves with parsed JSON or throws on failure */
const _apiRequest = async (method: string, path: string, body?: unknown): Promise<unknown> => {
  const { buildApiUrl } = await import('../constants');
  const res = await fetch(buildApiUrl(path), {
    method,
    headers: _getAuthHeaders(),
    body: body !== undefined ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) {
    const errText = await res.text().catch(() => res.statusText);
    throw new Error(`[API] ${method} ${path} → ${res.status}: ${errText}`);
  }
  return res.json().catch(() => ({}));
};

/**
 * Strip fields that should not be sent to MySQL:
 *  - data: base64 blobs (too large for TEXT columns)
 *  - IndexedDB reference keys (video_*, image_*)
 */
const _sanitizeForBackend = (data: Record<string, unknown>): Record<string, unknown> => {
  const out: Record<string, unknown> = {};
  for (const [k, v] of Object.entries(data)) {
    if (typeof v === 'string' && (v.startsWith('data:') || v.startsWith('video_') || v.startsWith('image_'))) {
      continue; // skip binary / IndexedDB blobs
    }
    out[k] = v;
  }
  return out;
};

// ==================== IN-MEMORY MOVIE CACHE ====================
// All movie data is loaded from MySQL via the backend REST API.
// Nothing is stored in localStorage for movies.

let _movieCache: Movie[] = [];

export const setMovieCache = (movies: Movie[]): void => {
  _movieCache = [...movies];
};

/** Fetch all movies from the backend and populate the in-memory cache. */
export const loadMoviesFromAPI = async (): Promise<Movie[]> => {
  try {
    const { buildApiUrl } = await import('../constants');
    const res = await fetch(buildApiUrl('/movies'));
    if (!res.ok) return _movieCache;
    const data = await res.json();
    _movieCache = (data.movies || []).map((m: Record<string, unknown>) => ({
      id: String(m.id ?? ''),
      title: String(m.title ?? ''),
      description: String(m.description ?? ''),
      genres: Array.isArray(m.genres) ? m.genres as string[] : [],
      year: Number(m.year ?? new Date().getFullYear()),
      duration: String(m.duration ?? ''),
      rating: String(m.rating ?? ''),
      poster: String(m.poster ?? ''),
      backdrop: String(m.backdrop ?? m.poster ?? ''),
      videoUrl: String(m.videoUrl ?? m.video_url ?? ''),
      trailerUrl: String(m.trailerUrl ?? m.trailer_url ?? ''),
      category: (m.category as 'trending' | 'top_rated' | 'new' | 'standard') ?? 'standard',
      views: Number(m.views ?? m.view_count ?? 0),
      createdAt: Number(m.createdAt ?? Date.now()),
    })) as Movie[];
    return _movieCache;
  } catch {
    return _movieCache;
  }
};

// IndexedDB for storing video files
const DB_NAME = 'streamflix_media_db';
const DB_VERSION = 1;
const VIDEO_STORE = 'videos';
const IMAGE_STORE = 'images';

// Initialize IndexedDB with retry logic
const openMediaDB = (): Promise<IDBDatabase> => {
  return new Promise((resolve, reject) => {
    const request = indexedDB.open(DB_NAME, DB_VERSION);
    
    request.onerror = () => {
      console.error('[Storage] IndexedDB open error:', request.error);
      reject(request.error);
    };
    
    request.onsuccess = () => {
      const db = request.result;
      console.log('[Storage] IndexedDB opened successfully');
      resolve(db);
    };
    
    request.onupgradeneeded = (event) => {
      console.log('[Storage] IndexedDB schema upgrade needed');
      const db = (event.target as IDBOpenDBRequest).result;
      if (!db.objectStoreNames.contains(VIDEO_STORE)) {
        db.createObjectStore(VIDEO_STORE, { keyPath: 'id' });
        console.log('[Storage] Created videos object store');
      }
      if (!db.objectStoreNames.contains(IMAGE_STORE)) {
        db.createObjectStore(IMAGE_STORE, { keyPath: 'id' });
        console.log('[Storage] Created images object store');
      }
    };
    
    request.onblocked = () => {
      console.warn('[Storage] IndexedDB open blocked - close other connections');
    };
  });
};

// Store a file in IndexedDB and return a unique ID
export const storeMediaFile = async (file: File, type: 'video' | 'image'): Promise<string> => {
  if (!file || file.size === 0) {
    throw new Error(`Invalid ${type} file: File is empty`);
  }
  
  const MAX_SIZE = 2 * 1024 * 1024 * 1024; // 2GB limit
  if (file.size > MAX_SIZE) {
    throw new Error(`${type} file is too large. Maximum size is 2GB. Current size: ${(file.size / (1024 * 1024 * 1024)).toFixed(2)}GB`);
  }
  
  console.log(`[Storage] Storing ${type} file:`, file.name, `Size: ${(file.size / (1024 * 1024)).toFixed(2)}MB`);
  
  try {
    const db = await openMediaDB();
    const id = `${type}_${Date.now()}_${Math.random().toString(36).substr(2, 9)}`;
    const storeName = type === 'video' ? VIDEO_STORE : IMAGE_STORE;
    
    return new Promise((resolve, reject) => {
      try {
        const transaction = db.transaction(storeName, 'readwrite');
        const store = transaction.objectStore(storeName);
        
        // Store the file directly as a Blob (more efficient for video playback)
        const data = {
          id,
          blob: file, // Store the File object directly (it's a Blob)
          name: file.name,
          type: file.type || (type === 'video' ? 'video/mp4' : 'image/jpeg'),
          size: file.size,
          createdAt: Date.now()
        };
        
        const request = store.put(data);
        
        request.onsuccess = () => {
          console.log(`[Storage] Successfully stored ${type} file with id: ${id}, size: ${(file.size / (1024 * 1024)).toFixed(2)} MB`);
          resolve(id);
        };
        
        request.onerror = () => {
          console.error('[Storage] Error storing file:', request.error);
          reject(new Error(`Failed to store ${type} file: ${request.error?.message || 'Unknown error'}`));
        };
        
        transaction.onerror = () => {
          console.error('[Storage] Transaction error:', transaction.error);
          reject(new Error(`Transaction failed: ${transaction.error?.message || 'Unknown error'}`));
        };
        
        transaction.oncomplete = () => {
          console.log('[Storage] Transaction completed successfully');
        };
        
        transaction.onabort = () => {
          console.error('[Storage] Transaction aborted');
          reject(new Error('Transaction was aborted'));
        };
      } catch (error) {
        console.error('[Storage] Exception while storing file:', error);
        reject(error);
      }
    });
  } catch (error) {
    console.error(`[Storage] Exception while opening database:`, error);
    throw new Error(`Could not store ${type} file: ${error instanceof Error ? error.message : 'Unknown error'}`);
  }
};

// Retrieve a file from IndexedDB and create a blob URL
export const getMediaFile = async (id: string): Promise<string | null> => {
  if (!id || (!id.startsWith('video_') && !id.startsWith('image_'))) {
    console.log('[Storage] Invalid media ID format:', id);
    return null;
  }
  
  console.log('[Storage] Retrieving media file with id:', id);
  
  try {
    const db = await openMediaDB();
    const type = id.startsWith('video_') ? 'video' : 'image';
    const storeName = type === 'video' ? VIDEO_STORE : IMAGE_STORE;
    
    return new Promise((resolve) => {
      const transaction = db.transaction(storeName, 'readonly');
      const store = transaction.objectStore(storeName);
      const request = store.get(id);
      
      request.onsuccess = () => {
        if (request.result) {
          console.log('[Storage] Found media file:', request.result.name, 'size:', request.result.size);
          
          // Handle both Blob and ArrayBuffer formats
          let blob: Blob;
          if (request.result.blob instanceof Blob) {
            blob = request.result.blob;
          } else if (request.result.blob instanceof ArrayBuffer) {
            // Legacy format - convert ArrayBuffer to Blob
            blob = new Blob([request.result.blob], { type: request.result.type || 'video/mp4' });
          } else {
            console.error('[Storage] Unknown blob format:', typeof request.result.blob);
            resolve(null);
            return;
          }
          
          try {
            const blobUrl = URL.createObjectURL(blob);
            console.log('[Storage] Created blob URL:', blobUrl.substring(0, 50) + '...');
            resolve(blobUrl);
          } catch (error) {
            console.error('[Storage] Failed to create blob URL:', error);
            resolve(null);
          }
        } else {
          console.error('[Storage] No media file found with id:', id);
          resolve(null);
        }
      };
      
      request.onerror = () => {
        console.error('[Storage] Error retrieving media file:', request.error);
        resolve(null);
      };
      
      transaction.onerror = () => {
        console.error('[Storage] Transaction error retrieving file:', transaction.error);
        resolve(null);
      };
      
      transaction.oncomplete = () => {
        console.log('[Storage] Transaction completed for file retrieval');
      };
    });
  } catch (error) {
    console.error('[Storage] Exception retrieving media file:', error);
    return null;
  }
};

// Delete a media file from IndexedDB
export const deleteMediaFile = async (id: string): Promise<void> => {
  if (!id || (!id.startsWith('video_') && !id.startsWith('image_'))) {
    console.log('[Storage] Skipping delete for invalid media ID:', id);
    return;
  }
  
  console.log('[Storage] Deleting media file with id:', id);
  
  try {
    const db = await openMediaDB();
    const type = id.startsWith('video_') ? 'video' : 'image';
    const storeName = type === 'video' ? VIDEO_STORE : IMAGE_STORE;
    
    return new Promise((resolve) => {
      const transaction = db.transaction(storeName, 'readwrite');
      const store = transaction.objectStore(storeName);
      const request = store.delete(id);
      
      request.onsuccess = () => {
        console.log('[Storage] Successfully deleted media file:', id);
        resolve();
      };
      
      request.onerror = () => {
        console.error('[Storage] Error deleting media file:', request.error);
        resolve(); // Don't reject, just log the error
      };
      
      transaction.oncomplete = () => {
        console.log('[Storage] Delete transaction completed');
      };
    });
  } catch (error) {
    console.error('[Storage] Exception deleting media file:', error);
    // Don't throw, just log
  }
};

// Get or create a unique user ID for tracking
const getUserId = (): string => {
  let userId = localStorage.getItem(USER_ID_KEY);
  if (!userId) {
    userId = 'user_' + Date.now().toString(36) + Math.random().toString(36).substr(2, 9);
    localStorage.setItem(USER_ID_KEY, userId);
  }
  return userId;
};

// Initialize user ID on load
getUserId();

// Movies are loaded from the backend API by calling loadMoviesFromAPI() at app startup.

export const fileToDataUrl = (file: File): Promise<string> => {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ''));
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });
};

const blobUrlToDataUrl = async (blobUrl: string): Promise<string | null> => {
  try {
    const res = await fetch(blobUrl);
    const blob = await res.blob();
    return await new Promise((resolve, reject) => {
      const reader = new FileReader();
      reader.onload = () => resolve(String(reader.result || ''));
      reader.onerror = () => reject(reader.error);
      reader.readAsDataURL(blob);
    });
  } catch {
    return null;
  }
};

// --- Movie Operations ---

export const getMovies = (): Movie[] => _movieCache;

export const getMovieById = (id: string): Movie | undefined => {
  const movies = getMovies();
  return movies.find((m) => m.id === id);
};

export const addMovie = async (data: MovieFormData): Promise<Movie> => {
  const movies = getMovies();
  
  // Store files in IndexedDB and get persistent IDs
  let videoUrl = data.videoUrl;
  let poster = data.poster;
  let backdrop = data.backdrop;
  
  if (data.videoFile) {
    videoUrl = await storeMediaFile(data.videoFile, 'video');
  }
  if (data.posterFile) {
    poster = await fileToDataUrl(data.posterFile);
  }
  if (data.backdropFile) {
    backdrop = await fileToDataUrl(data.backdropFile);
  }
  
  const newMovie: Movie = {
    ...data,
    id: Date.now().toString(),
    views: 0,
    createdAt: Date.now(),
    videoUrl,
    poster,
    backdrop,
  };

  _movieCache = [newMovie, ..._movieCache];

  // Await the backend POST so the record exists before navigation re-fetches.
  // Strip data: blobs / IndexedDB keys — MySQL TEXT columns can't hold them.
  const backendPayload = _sanitizeForBackend(newMovie as unknown as Record<string, unknown>);
  await _apiRequest('POST', '/admin/movies', backendPayload);

  return newMovie;
};

export const updateMovie = async (id: string, data: Partial<MovieFormData>): Promise<Movie | null> => {
  const movies = _movieCache;
  const index = movies.findIndex((m) => m.id === id);
  if (index === -1) return null;

  // Handle file uploads for updates
  const updateData: Partial<Movie> = { ...data };
  
  if (data.videoFile) {
    // Delete old video if it was stored in IndexedDB
    const oldVideoUrl = movies[index].videoUrl;
    if (oldVideoUrl && oldVideoUrl.startsWith('video_')) {
      await deleteMediaFile(oldVideoUrl);
    }
    updateData.videoUrl = await storeMediaFile(data.videoFile, 'video');
  }
  if (data.posterFile) {
    const oldPoster = movies[index].poster;
    if (oldPoster && oldPoster.startsWith('image_')) {
      await deleteMediaFile(oldPoster);
    }
    updateData.poster = await fileToDataUrl(data.posterFile);
  }
  if (data.backdropFile) {
    const oldBackdrop = movies[index].backdrop;
    if (oldBackdrop && oldBackdrop.startsWith('image_')) {
      await deleteMediaFile(oldBackdrop);
    }
    updateData.backdrop = await fileToDataUrl(data.backdropFile);
  }
  
  // Remove file objects from update data
  delete (updateData as any).videoFile;
  delete (updateData as any).posterFile;
  delete (updateData as any).backdropFile;

  // Update local in-memory cache immediately
  _movieCache = _movieCache.map(m => m.id === id ? { ...m, ...updateData } : m);

  // Await the backend PUT so navigation doesn't race ahead of the DB write.
  // Strip data: blobs / IndexedDB keys — MySQL TEXT columns can't hold them.
  const backendPayload = _sanitizeForBackend(updateData as Record<string, unknown>);
  await _apiRequest('PUT', `/admin/movies/${id}`, backendPayload);

  // Return the updated movie (not the stale pre-update snapshot)
  return _movieCache.find(m => m.id === id) ?? null;
};

export const deleteMovie = async (id: string): Promise<void> => {
  const movie = _movieCache.find(m => m.id === id);

  // Update cache and sync to backend immediately
  _movieCache = _movieCache.filter(m => m.id !== id);
  _apiSync('DELETE', `/admin/movies/${id}`);

  // Clean up any locally-stored IndexedDB files (fire and forget)
  if (movie) {
    if (movie.videoUrl?.startsWith('video_')) void deleteMediaFile(movie.videoUrl);
    if (movie.poster?.startsWith('image_')) void deleteMediaFile(movie.poster);
    if (movie.backdrop?.startsWith('image_')) void deleteMediaFile(movie.backdrop);
  }
};

export const deleteMultipleMovies = (ids: string[]): number => {
  const idSet = new Set(ids);
  const before = _movieCache.length;
  _movieCache = _movieCache.filter(m => !idSet.has(m.id));
  const deletedCount = before - _movieCache.length;

  // Sync bulk deletion to MySQL backend
  if (ids.length > 0) {
    _apiSync('POST', '/admin/movies/bulk-delete', { ids });
  }

  return deletedCount;
};

export const importMoviesFromCSV = (movies: Movie[]): number => {
  const existingIds = new Set(_movieCache.map(m => m.id));

  // Filter out duplicates
  const newMovies = movies.filter(m => !existingIds.has(m.id));

  const moviesWithIds = newMovies.map(movie => ({
    ...movie,
    id: movie.id || Date.now().toString() + Math.random().toString(36).substr(2, 9),
    views: movie.views || 0,
    createdAt: movie.createdAt || Date.now(),
  }));

  // Update in-memory cache
  _movieCache = [...moviesWithIds, ..._movieCache];

  // Persist every new movie to MySQL via the backend API
  moviesWithIds.forEach(movie => {
    _apiSync('POST', '/admin/movies', movie);
  });

  return moviesWithIds.length;
};

// --- User Interactions ---

export const addToHistory = (movieId: string) => {
  const history = getHistory();
  const newHistory = [movieId, ...history.filter(id => id !== movieId)].slice(0, 20);
  localStorage.setItem(HISTORY_KEY, JSON.stringify(newHistory));

  // Update view count in memory and sync to backend
  const movieIndex = _movieCache.findIndex(m => m.id === movieId);
  if (movieIndex >= 0) {
    const newViews = (_movieCache[movieIndex].views || 0) + 1;
    _movieCache = _movieCache.map((m, i) => i === movieIndex ? { ...m, views: newViews } : m);
    _apiSync('PUT', `/admin/movies/${movieId}`, { views: newViews });
  }
};

export const getHistory = (): string[] => {
  const data = localStorage.getItem(HISTORY_KEY);
  return data ? JSON.parse(data) : [];
};

export const toggleMyList = (movieId: string) => {
  const list = getMyList();
  if (list.includes(movieId)) {
    localStorage.setItem(MY_LIST_KEY, JSON.stringify(list.filter(id => id !== movieId)));
  } else {
    localStorage.setItem(MY_LIST_KEY, JSON.stringify([movieId, ...list]));
  }
};

export const getMyList = (): string[] => {
  const data = localStorage.getItem(MY_LIST_KEY);
  return data ? JSON.parse(data) : [];
};

// --- Mood-Based Logic ---

export const MOOD_GENRE_MAP: Record<string, string[]> = {
  'HAPPY': ['Comedy', 'Adventure', 'Animation', 'Musical', 'Feel-Good', 'Friendship'],
  'SAD': ['Comedy', 'Family', 'Friendship', 'Feel-Good', 'Motivational', 'Animation', 'Romance'],
  'BORED': ['Action', 'Sci-Fi', 'Thriller'],
  'EXCITED': ['Action', 'Adventure', 'Thriller', 'War', 'Crime'],
  'CALM': ['Documentary', 'Nature', 'History'],
  'MOTIVATED': ['Motivational', 'Sport', 'Biography']
};

export const getMoviesByMood = (mood: string): Movie[] => {
  const movies = getMovies();
  const upperMood = mood.toUpperCase();
  const targetGenres = MOOD_GENRE_MAP[upperMood] || [];
  
  if (targetGenres.length === 0) return [];

  return movies.filter(movie => 
    movie.genres.some(genre => targetGenres.includes(genre))
  ).sort((a, b) => b.views - a.views);
};

// --- Recommendation Engine ---

export const getRecommendations = (): Movie[] => {
  const movies = getMovies();
  const historyIds = getHistory();
  
  if (historyIds.length === 0) {
    return movies.filter(m => m.category === 'trending').slice(0, 5);
  }

  const watchedMovies = movies.filter(m => historyIds.includes(m.id));
  const genreCounts: Record<string, number> = {};
  
  watchedMovies.forEach(m => {
    m.genres.forEach(g => {
      genreCounts[g] = (genreCounts[g] || 0) + 1;
    });
  });

  const scoredMovies: Recommendation[] = movies
    .filter(m => !historyIds.includes(m.id))
    .map(m => {
      let score = 0;
      m.genres.forEach(g => {
        score += (genreCounts[g] || 0);
      });
      if (m.year >= 2023) score += 0.5;
      if (m.category === 'top_rated') score += 1;
      
      return { score, movie: m };
    });

  return scoredMovies
    .sort((a, b) => b.score - a.score)
    .map(item => item.movie)
    .slice(0, 10);
};

export const getContinueWatchingMovies = (): Movie[] => {
  const historyIds = getHistory();
  const movies = getMovies();
  return historyIds
    .map(id => movies.find(m => m.id === id))
    .filter((m): m is Movie => !!m);
};

// --- Feedback Storage ---
const FEEDBACK_KEY = 'streamflix_feedback';

export const saveFeedback = (data: { mood: string; recommendedMovies: Movie[]; feedback: 'positive' | 'negative' }): void => {
  const feedbackList = getFeedback();
  feedbackList.push({
    ...data,
    timestamp: Date.now(),
  });
  localStorage.setItem(FEEDBACK_KEY, JSON.stringify(feedbackList));
};

export const getFeedback = (): Array<{ mood: string; recommendedMovies: Movie[]; feedback: 'positive' | 'negative'; timestamp: number }> => {
  const data = localStorage.getItem(FEEDBACK_KEY);
  return data ? JSON.parse(data) : [];
};
