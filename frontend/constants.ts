import { Movie } from './types';

export const ADMIN_KEY = "admin123";

const DEFAULT_VIDEO_URL = 'https://cdn.coverr.co/videos/coverr-cinema-projector-5175/1080p.mp4';

// Movies will be imported from backend CSV via import_movies.py
// Movies are stored in and served from the MySQL backend database.

export const INITIAL_MOVIES: Movie[] = [];

export const API_BASE_URL = (import.meta.env.VITE_API_BASE_URL || 'http://localhost:5000').replace(/\/$/, '');

export const buildApiUrl = (path: string): string => `${API_BASE_URL}${path.startsWith('/') ? path : `/${path}`}`;
