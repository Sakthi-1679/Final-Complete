import React from 'react';
import { Link } from 'react-router-dom';
import { Movie } from '../types';

interface MovieCardProps {
  movie: Movie;
  className?: string; // Allow parent to control width/styling
}

const MovieCard: React.FC<MovieCardProps> = ({ movie, className }) => {
  return (
    <Link 
      to={`/movie/${movie.id}`} 
      className={`block relative group bg-netflix-card rounded-md overflow-hidden transition-all duration-300 focus:outline-none focus:ring-2 focus:ring-white ${className || 'min-w-[160px] md:min-w-[240px]'}`}
    >
      <div className="aspect-video relative overflow-hidden rounded-md">
        <img 
          src={movie.backdrop || movie.poster} 
          alt={movie.title} 
          className="w-full h-full object-cover transition-transform duration-500 group-hover:scale-110"
          loading="lazy"
        />
        
        {/* Dark overlay that appears on hover */}
        <div className="absolute inset-0 bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity duration-300"></div>

        {/* Content Overlay */}
        <div className="absolute inset-0 flex flex-col justify-end p-4 opacity-0 group-hover:opacity-100 transition-opacity duration-300 delay-100 bg-gradient-to-t from-black via-black/60 to-transparent">
          <h3 className="text-white font-bold text-sm md:text-base mb-2 truncate">{movie.title}</h3>
          
          <div className="flex items-center space-x-2 mb-3">
            <button className="bg-white text-black rounded-full w-8 h-8 flex items-center justify-center hover:bg-gray-200 transition-colors shadow-md">
              <i className="fas fa-play text-xs pl-0.5"></i>
            </button>
            <button className="border-2 border-gray-400 text-white rounded-full w-8 h-8 flex items-center justify-center hover:border-white hover:bg-white/10 transition-colors">
              <i className="fas fa-plus text-xs"></i>
            </button>
            <button className="border-2 border-gray-400 text-white rounded-full w-8 h-8 flex items-center justify-center ml-auto hover:border-white hover:bg-white/10 transition-colors">
              <i className="fas fa-chevron-down text-xs"></i>
            </button>
          </div>

          <div className="flex items-center space-x-2 text-[10px] md:text-xs font-semibold text-gray-300">
            <span className="text-green-400">95% Match</span>
            <span className="border border-gray-500 px-1 rounded-sm uppercase">{movie.rating}</span>
            <span>{movie.duration}</span>
          </div>
          
          <div className="flex flex-wrap gap-1.5 mt-2">
            {movie.genres.slice(0, 3).map((g, i) => (
              <span key={g} className="text-[10px] text-gray-400 flex items-center">
                {i > 0 && <span className="text-gray-600 mr-1.5">•</span>}
                {g}
              </span>
            ))}
          </div>
        </div>
      </div>
    </Link>
  );
};

export default MovieCard;