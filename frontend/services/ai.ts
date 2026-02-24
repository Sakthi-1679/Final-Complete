
import { GoogleGenAI, Type } from "@google/genai";
import { MoodType, Movie } from "../types";
import { getMovies } from "./storage";

let ai: GoogleGenAI | null = null;

try {
  const apiKey = import.meta.env.VITE_API_KEY;
  if (apiKey && apiKey.trim()) {
    ai = new GoogleGenAI({ apiKey });
  }
} catch (error) {
  console.warn('[AI] Failed to initialize Gemini API:', error);
  ai = null;
}

interface MoodAnalysisResponse {
  mood: MoodType;
  confidence: number;
  reasoning: string;
}

export const analyzeMood = async (text: string): Promise<MoodAnalysisResponse | null> => {
  try {
    if (!ai) {
      console.warn('[AI] Gemini API not initialized, using fallback');
      return null;
    }
    
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: `Analyze the following user input and determine their current mood. 
      Input: "${text}"`,
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            mood: {
              type: Type.STRING,
              description: "The detected mood: happy, sad, angry, calm, or stressed.",
              enum: ["happy", "sad", "angry", "calm", "stressed"]
            },
            confidence: {
              type: Type.NUMBER,
              description: "Confidence score between 0 and 1."
            },
            reasoning: {
              type: Type.STRING,
              description: "Short explanation for the detected mood."
            }
          },
          required: ["mood", "confidence", "reasoning"]
        },
        systemInstruction: "You are an expert psychological classifier. Categorize text into 5 mood buckets: happy, sad, angry, calm, stressed."
      }
    });

    const json = JSON.parse(response.text || '{}');
    return json as MoodAnalysisResponse;
  } catch (error) {
    console.error("AI Mood Analysis Error:", error);
    return null;
  }
};

export const detectLiveMood = async (imageB64: string, audioB64: string): Promise<MoodAnalysisResponse | null> => {
  try {
    if (!ai) {
      console.warn('[AI] Gemini API not initialized, using fallback');
      return null;
    }
    
    const response = await ai.models.generateContent({
      model: "gemini-3-flash-preview",
      contents: {
        parts: [
          {
            inlineData: {
              mimeType: "image/jpeg",
              data: imageB64
            }
          },
          {
            inlineData: {
              mimeType: "audio/webm",
              data: audioB64
            }
          },
          {
            text: "Analyze the user's expression and tone of voice from the provided image and audio clip. Detect their current mood: happy, sad, angry, calm, or stressed."
          }
        ]
      },
      config: {
        responseMimeType: "application/json",
        responseSchema: {
          type: Type.OBJECT,
          properties: {
            mood: {
              type: Type.STRING,
              enum: ["happy", "sad", "angry", "calm", "stressed"]
            },
            confidence: {
              type: Type.NUMBER
            },
            reasoning: {
              type: Type.STRING
            }
          },
          required: ["mood", "confidence", "reasoning"]
        }
      }
    });

    const json = JSON.parse(response.text || '{}');
    return json as MoodAnalysisResponse;
  } catch (error) {
    console.error("Multimodal AI Analysis Error:", error);
    return null;
  }
};

export const getMoodBasedMovies = (mood: MoodType): Movie[] => {
  const allMovies = getMovies();
  
  const mapping: Record<MoodType, string[]> = {
    HAPPY: ['Comedy', 'Adventure', 'Animation', 'Musical', 'Feel-Good'],
    SAD: ['Comedy', 'Family', 'Feel-Good', 'Motivational', 'Romance'],
    BORED: ['Thriller', 'Crime', 'Action', 'Intense'],
    EXCITED: ['Action', 'Adventure', 'Thriller', 'Sci-Fi'],
    CALM: ['Documentary', 'Nature', 'Drama'],
    MOTIVATED: ['Motivational', 'Sport', 'Biography']
  };

  const targetGenres = mapping[mood];
  
  return allMovies
    .filter(movie => movie.genres.some(g => targetGenres.includes(g)))
    .sort((a, b) => b.views - a.views)
    .slice(0, 6);
};
/**
 * Get dynamic mood-based recommendations from trained backend model
 * Makes API call to get personalized recommendations based on mood
 */
export const getDynamicMoodRecommendations = async (
  mood: string,
  userId: string = 'guest',
  topK: number = 6
): Promise<Movie[]> => {
  try {
    const { buildApiUrl } = await import('../constants');
    
    const response = await fetch(buildApiUrl('/mood/recommendations'), {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        user_id: userId,
        mood: mood.toLowerCase(),
        top_k: topK
      })
    });

    if (!response.ok) {
      console.warn('Failed to get dynamic recommendations, falling back to static');
      return getMoodBasedMovies(mood as MoodType);
    }

    const data = await response.json();
    
    if (data.recommendations && Array.isArray(data.recommendations)) {
      // ONLY return movies that already exist in the local DB (localStorage).
      // Movies not found locally are silently dropped — we never suggest
      // content that isn't in our database.
      const localMovies = getMovies();
      const localById = new Map(localMovies.map(m => [m.id, m]));

      const dbOnly = data.recommendations
        .map((rec: Record<string, unknown>) => localById.get(String(rec.id ?? '')))
        .filter((m): m is import('../types').Movie => m !== undefined);

      // If none of the backend IDs matched our local DB, fall back to
      // genre/mood-based filtering from localStorage instead.
      if (dbOnly.length === 0) {
        return getMoodBasedMovies(mood as MoodType);
      }

      return dbOnly;
    }
    
    return getMoodBasedMovies(mood as MoodType);
  } catch (error) {
    console.warn('Dynamic mood recommendation error, using fallback:', error);
    return getMoodBasedMovies(mood as MoodType);
  }
};

/**
 * ── HYBRID RECOMMENDER  ──────────────────────────────────────────
 * Calls /hybrid/recommend — the new industry-level neural model.
 * Falls back to getDynamicMoodRecommendations if unavailable.
 */
export const getHybridRecommendations = async (
  mood: string,
  userId: string = 'guest',
  topK: number = 6
): Promise<{ movies: Movie[]; source: string; version: number }> => {
  try {
    const { buildApiUrl } = await import('../constants');
    const res = await fetch(buildApiUrl('/hybrid/recommend'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ user_id: userId, mood: mood.toLowerCase(), top_k: topK }),
    });

    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    const data = await res.json();

    const localMovies = getMovies();
    const localById = new Map(localMovies.map(m => [m.id, m]));

    // Merge backend metadata (rank, mood) into local movie objects
    const merged: Movie[] = [];
    for (const rec of (data.recommendations ?? [])) {
      const local = localById.get(String(rec.id ?? ''));
      if (local) merged.push({ ...local, _recommendedRank: rec._recommended_rank });
    }

    // If no overlap with local DB, fall back fully
    if (merged.length === 0) {
      const fallback = await getDynamicMoodRecommendations(mood, userId, topK);
      return { movies: fallback, source: 'fallback', version: 0 };
    }

    return {
      movies: merged,
      source: data.source ?? 'hybrid_recommender',
      version: data.model_version ?? 0,
    };
  } catch (err) {
    console.warn('[Hybrid] Falling back to legacy recommender:', err);
    const fallback = await getDynamicMoodRecommendations(mood, userId, topK);
    return { movies: fallback, source: 'fallback', version: 0 };
  }
};

/**
 * Log a like / dislike / watch interaction for the hybrid retraining pipeline.
 */
export const logHybridInteraction = async (params: {
  userId: string;
  movieId: string;
  movieTitle: string;
  mood: string;
  liked?: boolean;
  disliked?: boolean;
  rating?: number;
  watchTime?: number;
  recommendedRankPosition?: number;
}): Promise<void> => {
  try {
    const { buildApiUrl } = await import('../constants');
    await fetch(buildApiUrl('/hybrid/interact'), {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        user_id: params.userId,
        movie_id: params.movieId,
        movie_title: params.movieTitle,
        mood: params.mood,
        liked: params.liked ?? false,
        disliked: params.disliked ?? false,
        rating: params.rating ?? 0,
        watch_time: params.watchTime ?? 0,
        recommended_rank_position: params.recommendedRankPosition ?? null,
      }),
    });
  } catch (err) {
    console.warn('[HybridInteraction] Log failed (non-critical):', err);
  }
};

/**
 * Get model information including current version
 */
export const getModelInfo = async () => {
  try {
    const { buildApiUrl } = await import('../constants');
    
    const response = await fetch(buildApiUrl('/model/info'));
    if (!response.ok) throw new Error('Failed to fetch model info');
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching model info:', error);
    return null;
  }
};

/**
 * Get all available model versions
 */
export const getModelVersions = async () => {
  try {
    const { buildApiUrl } = await import('../constants');
    
    const response = await fetch(buildApiUrl('/model/versions'));
    if (!response.ok) throw new Error('Failed to fetch model versions');
    
    return await response.json();
  } catch (error) {
    console.error('Error fetching model versions:', error);
    return null;
  }
};