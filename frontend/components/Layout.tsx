import React, { useState, useEffect } from 'react';
import { Link, Outlet, useLocation, useNavigate } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const Layout: React.FC = () => {
  const [isScrolled, setIsScrolled] = useState(false);
  const { isAdmin, isLoggedIn, logout } = useAuth();
  const location = useLocation();
  const navigate = useNavigate();
  const [searchQuery, setSearchQuery] = useState('');

  const handleLogout = () => {
    logout();
    navigate('/login');
  };

  // Navbar background effect
  useEffect(() => {
    const handleScroll = () => {
      setIsScrolled(window.scrollY > 0);
    };
    window.addEventListener('scroll', handleScroll);
    return () => window.removeEventListener('scroll', handleScroll);
  }, []);

  const handleSearch = (e: React.FormEvent) => {
    e.preventDefault();
    if (searchQuery.trim()) {
      navigate(`/search?q=${encodeURIComponent(searchQuery)}`);
    }
  };

  const isPlayer = location.pathname.includes('/watch/');

  if (isPlayer) return <Outlet />;

  return (
    <div className="min-h-screen bg-netflix-dark text-white font-sans selection:bg-netflix-red selection:text-white">
      {/* Navbar */}
      <nav
        className={`fixed top-0 w-full z-[100] transition-all duration-500 px-4 md:px-12 py-4 flex items-center justify-between ${
          isScrolled ? 'glass-nav shadow-lg py-3' : 'bg-gradient-to-b from-black/90 via-black/60 to-transparent py-5'
        }`}
      >
        <div className="flex items-center space-x-8">
          <Link to="/" className="text-3xl md:text-4xl font-bold text-netflix-red tracking-tighter hover:scale-105 transition-transform">
            STREAMFLIX
          </Link>
          <div className="hidden md:flex space-x-6 text-sm font-medium text-gray-300">
            <NavLink to="/">Home</NavLink>
            <NavLink to="/search?g=TV Shows">TV Shows</NavLink>
            <NavLink to="/search?g=Movies">Movies</NavLink>
            <NavLink to="/search?category=new">New & Popular</NavLink>
          </div>
        </div>

        <div className="flex items-center space-x-6">
          <form onSubmit={handleSearch} className="hidden md:flex relative group">
            <input 
              type="text" 
              placeholder="Titles, people, genres" 
              className="bg-black/40 border border-gray-500/50 rounded-sm px-4 py-1.5 text-sm w-0 group-hover:w-64 focus:w-64 focus:border-white transition-all duration-300 focus:outline-none"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
            />
            <button type="submit" className="absolute right-2 top-1.5 text-gray-300 hover:text-white transition-colors">
              <i className="fas fa-search"></i>
            </button>
            {/* Fallback search icon if input is collapsed */}
            <div className="absolute right-0 top-0 h-full w-8 flex items-center justify-center cursor-pointer group-hover:hidden pointer-events-none">
               <i className="fas fa-search text-gray-300"></i>
            </div>
          </form>

          {isAdmin ? (
            <div className="flex items-center space-x-4">
              <Link to="/admin/dashboard" className="text-green-500 font-bold text-sm hover:text-green-400 transition-colors">
                ADMIN PANEL
              </Link>
              <button onClick={handleLogout} className="text-gray-300 hover:text-white transition-colors" title="Logout">
                <i className="fas fa-sign-out-alt text-lg"></i>
              </button>
            </div>
          ) : isLoggedIn ? (
            <button onClick={handleLogout} className="text-gray-400 hover:text-white transition-colors flex items-center gap-1 text-sm" title="Logout">
              <i className="fas fa-sign-out-alt"></i>
              <span className="hidden md:inline">Logout</span>
            </button>
          ) : (
            <Link to="/login" className="text-gray-400 hover:text-white text-xs transition-colors">Login</Link>
          )}
          
          <div className="w-8 h-8 rounded bg-blue-600 flex items-center justify-center cursor-pointer hover:ring-2 hover:ring-white transition-all">
             <i className="fas fa-user"></i>
          </div>
        </div>
      </nav>

      {/* Main Content */}
      <main className="min-h-screen">
        <Outlet />
      </main>

      {/* Footer */}
      <footer className="bg-black/60 py-16 px-4 md:px-12 text-gray-500 text-sm mt-12 border-t border-gray-900">
        <div className="max-w-6xl mx-auto">
          <div className="flex space-x-6 mb-8 text-2xl text-white">
            <i className="fab fa-facebook hover:text-netflix-red cursor-pointer transition-colors"></i>
            <i className="fab fa-instagram hover:text-netflix-red cursor-pointer transition-colors"></i>
            <i className="fab fa-twitter hover:text-netflix-red cursor-pointer transition-colors"></i>
            <i className="fab fa-youtube hover:text-netflix-red cursor-pointer transition-colors"></i>
          </div>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-8">
            <FooterLinkCol links={['Audio Description', 'Investor Relations', 'Legal Notices']} />
            <FooterLinkCol links={['Help Center', 'Jobs', 'Cookie Preferences']} />
            <FooterLinkCol links={['Gift Cards', 'Terms of Use', 'Corporate Information']} />
            <FooterLinkCol links={['Media Center', 'Privacy', 'Contact Us']} />
          </div>
          <div className="mt-8">
            <button className="border border-gray-500 px-4 py-1 hover:border-white hover:text-white transition-colors mb-4 text-xs">
              Service Code
            </button>
            <div className="text-xs text-gray-600">
              &copy; 2023 StreamFlix Pro. All rights reserved.
            </div>
          </div>
        </div>
      </footer>
    </div>
  );
};

// Helper Components for Cleaner Layout
const NavLink: React.FC<{ to: string; children: React.ReactNode }> = ({ to, children }) => {
  const location = useLocation();
  const isActive = location.pathname === to || (to !== '/' && location.pathname.includes(to));
  
  return (
    <Link 
      to={to} 
      className={`transition-colors duration-300 ${
        isActive ? 'text-white font-bold' : 'hover:text-gray-300'
      }`}
    >
      {children}
    </Link>
  );
};

const FooterLinkCol: React.FC<{ links: string[] }> = ({ links }) => (
  <div className="flex flex-col space-y-3">
    {links.map(link => (
      <span key={link} className="hover:underline cursor-pointer hover:text-gray-400 transition-colors">{link}</span>
    ))}
  </div>
);

export default Layout;