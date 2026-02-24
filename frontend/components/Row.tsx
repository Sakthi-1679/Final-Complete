
import React, { useRef, useState } from 'react';
import { Link } from 'react-router-dom';
import { Movie } from '../types';
import MovieCard from './MovieCard';

interface RowProps {
  title: string;
  movies: Movie[];
  isLarge?: boolean;
}

const Row: React.FC<RowProps> = ({ title, movies, isLarge }) => {
  const rowRef = useRef<HTMLDivElement>(null);
  const [isMoved, setIsMoved] = useState(false);

  const handleClick = (direction: 'left' | 'right') => {
    setIsMoved(true);
    if (rowRef.current) {
      const { scrollLeft, clientWidth } = rowRef.current;
      const scrollTo = direction === 'left' 
        ? scrollLeft - clientWidth / 2 
        : scrollLeft + clientWidth / 2;

      rowRef.current.scrollTo({ left: scrollTo, behavior: 'smooth' });
    }
  };

  if (!movies.length) return null;

  return (
    <div className="mb-4 md:mb-8 space-y-2 group relative px-4 md:px-12 z-20">
      <div className="flex justify-between items-end px-1">
          <h2 className="text-lg md:text-2xl font-bold text-gray-100 hover:text-white transition-colors cursor-pointer">
            {title} <i className="fas fa-chevron-right text-xs ml-2 opacity-0 group-hover:opacity-100 transition-opacity text-cyan-500"></i>
          </h2>
      </div>
      
      <div className="relative group/row">
        {/* Left Arrow */}
        <div 
          className={`absolute top-0 bottom-0 left-0 bg-black/60 w-10 md:w-12 z-[60] flex items-center justify-center cursor-pointer opacity-0 group-hover/row:opacity-100 transition-all duration-300 hover:bg-black/80 ${!isMoved && 'hidden'}`}
          onClick={() => handleClick('left')}
        >
          <i className="fas fa-chevron-left text-white text-xl md:text-2xl transform transition hover:scale-125"></i>
        </div>

        {/* Scroll Container with vertical padding to accommodate hover scaling */}
        <div 
          ref={rowRef}
          className="flex items-center space-x-2 md:space-x-4 overflow-x-scroll no-scrollbar py-8 md:py-10 scroll-smooth"
        >
          {movies.map(movie => (
            <div key={movie.id} className={`relative transition-all duration-300 hover:z-50 ${isLarge ? 'min-w-[140px] md:min-w-[200px] h-[220px] md:h-[350px]' : 'min-w-[160px] md:min-w-[280px]'}`}>
                {/* Custom Card Logic for Large Rows (Top Rated) */}
                {isLarge ? (
                    <Link to={`/movie/${movie.id}`} className="relative block h-full w-full rounded-md overflow-hidden transition-transform duration-300 hover:scale-110 shadow-lg hover:shadow-2xl">
                         <img src={movie.poster} alt={movie.title} className="w-full h-full object-cover" />
                         <div className="absolute inset-0 bg-gradient-to-t from-black/60 to-transparent opacity-0 hover:opacity-100 transition-opacity"></div>
                    </Link>
                ) : (
                    <MovieCard movie={movie} className="w-full" />
                )}
            </div>
          ))}
        </div>

        {/* Right Arrow */}
        <div 
          className="absolute top-0 bottom-0 right-0 bg-black/60 w-10 md:w-12 z-[60] flex items-center justify-center cursor-pointer opacity-0 group-hover/row:opacity-100 transition-all duration-300 hover:bg-black/80"
          onClick={() => handleClick('right')}
        >
          <i className="fas fa-chevron-right text-white text-xl md:text-2xl transform transition hover:scale-125"></i>
        </div>
      </div>
    </div>
  );
};

export default Row;
