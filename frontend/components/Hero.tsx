import React from 'react';
import { Link } from 'react-router-dom';
import { Movie } from '../types';

interface HeroProps {
  movie: Movie;
}

const Hero: React.FC<HeroProps> = ({ movie }) => {
  return (
    <div className="relative h-[85vh] w-full overflow-hidden">
      {/* Background Image with Zoom Effect */}
      <div className="absolute inset-0">
        <img 
          src={movie.backdrop} 
          alt={movie.title} 
          className="w-full h-full object-cover animate-fade-in"
        />
        {/* Advanced Gradient Overlay */}
        <div className="absolute inset-0 bg-gradient-to-r from-black/80 via-black/40 to-transparent"></div>
        <div className="absolute inset-0 bg-gradient-to-t from-[#141414] via-[#141414]/20 to-transparent"></div>
      </div>

      {/* Content */}
      <div className="absolute bottom-[25%] left-4 md:left-12 max-w-2xl px-4 animate-slide-up">
        <h1 className="text-4xl md:text-7xl font-extrabold mb-4 drop-shadow-2xl text-white tracking-tight">
          {movie.title}
        </h1>
        
        <div className="flex items-center space-x-4 mb-6 text-gray-200 text-sm md:text-base font-medium">
            <span className="text-green-400 font-bold">98% Match</span>
            <span>{movie.year}</span>
            <span className="border border-gray-400 px-2 py-0.5 rounded-sm bg-black/30 backdrop-blur-sm">{movie.rating}</span>
            <span>{movie.duration}</span>
            <span className="border border-gray-400 px-1 text-xs rounded-sm">HD</span>
        </div>
        
        <p className="text-base md:text-lg text-gray-300 mb-8 drop-shadow-md line-clamp-3 md:line-clamp-none max-w-xl leading-relaxed">
          {movie.description}
        </p>
        
        <div className="flex space-x-4">
          <Link 
            to={`/watch/${movie.id}`} state={{ autoFullscreen: true }}
            className="flex items-center px-8 py-3 bg-white text-black rounded font-bold hover:bg-gray-200 hover:scale-105 active:scale-95 transition-all duration-200 shadow-lg"
          >
            <i className="fas fa-play mr-2 text-xl"></i> <span className="text-lg">Play</span>
          </Link>
          <Link 
            to={`/movie/${movie.id}`}
            className="flex items-center px-8 py-3 bg-gray-500/60 text-white rounded font-bold hover:bg-gray-500/80 hover:scale-105 active:scale-95 transition-all duration-200 backdrop-blur-md shadow-lg"
          >
            <i className="fas fa-info-circle mr-2 text-xl"></i> <span className="text-lg">More Info</span>
          </Link>
        </div>
      </div>
    </div>
  );
};

export default Hero;