import React, { useState, useEffect } from 'react';
import { useLocation } from 'react-router-dom';
import { loadMoviesFromAPI } from '../services/storage';
import { Movie } from '../types';
import { buildApiUrl } from '../constants';
import MovieCard from '../components/MovieCard';

const Search: React.FC = () => {
  const location = useLocation();
  const [movies, setMovies] = useState<Movie[]>([]);
  const [filteredMovies, setFilteredMovies] = useState<Movie[]>([]);
  const searchParams = new URLSearchParams(location.search);
  const query = searchParams.get('q') || '';
  const genre = searchParams.get('g') || '';

  useEffect(() => {
    loadMoviesFromAPI().then(setMovies);
  }, []);

  // Log search query to backend for model training
  useEffect(() => {
    if (query) {
      fetch(buildApiUrl('/log_event'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          event_type: 'SEARCH',
          user_id: localStorage.getItem('streamflix_user_id') || 'anonymous',
          search_query: query,
          detected_mood: localStorage.getItem('streamflix_last_mood') || '',
        }),
      }).catch(() => {});
    }
  }, [query]);

  useEffect(() => {
    let results = movies;

    if (query) {
      const lowerQ = query.toLowerCase();
      results = results.filter(m => 
        m.title.toLowerCase().includes(lowerQ) || 
        m.genres.some(g => g.toLowerCase().includes(lowerQ))
      );
    }

    if (genre) {
       results = results.filter(m => m.genres.includes(genre));
    }

    setFilteredMovies(results);
  }, [query, genre, movies]);

  return (
    <div className="pt-24 px-4 md:px-12 min-h-screen">
      <h1 className="text-2xl font-bold mb-6 text-gray-300">
        {query ? `Results for "${query}"` : genre ? `${genre} Movies` : 'Browse All'}
      </h1>
      
      {filteredMovies.length === 0 ? (
        <div className="text-center text-gray-500 mt-20">
          <p>No titles found matching your search.</p>
        </div>
      ) : (
        <div className="grid grid-cols-2 md:grid-cols-4 lg:grid-cols-6 gap-4">
          {filteredMovies.map(movie => (
            <MovieCard key={movie.id} movie={movie} />
          ))}
        </div>
      )}
    </div>
  );
};

export default Search;