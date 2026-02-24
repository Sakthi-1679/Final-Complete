export interface Movie {
  id: string;
  title: string;
  description: string;
  genres: string[];
  year: number;
  duration: string; // e.g., "2h 15m"
  rating: string; // e.g., "PG-13", "R"
  poster: string;
  backdrop: string;
  videoUrl: string;
  trailerUrl?: string;
  category: 'trending' | 'top_rated' | 'new' | 'standard';
  views: number;
  createdAt: number;
  mood?: string;
  language?: string;
  /** Rank position assigned by hybrid recommender (1-based) */
  _recommendedRank?: number;
}

export type MovieFormData = Omit<Movie, 'id' | 'views' | 'createdAt'> & {
  videoFile?: File | null;
  posterFile?: File | null;
  backdropFile?: File | null;
};

export interface Recommendation {
  score: number;
  movie: Movie;
}

export type MoodType = 'HAPPY' | 'SAD' | 'BORED' | 'EXCITED' | 'CALM' | 'MOTIVATED';

export interface FeedbackData {
  mood: MoodType;
  recommendedMovies: Movie[];
  feedback: 'positive' | 'negative';
  timestamp: number;
}
