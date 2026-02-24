import React, { useState, useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../../constants';
import { useAuth } from '../../context/AuthContext';
import { loadMoviesFromAPI, deleteMovie, importMoviesFromCSV, deleteMultipleMovies } from '../../services/storage';
import { Movie } from '../../types';
import InsightsDashboard from './InsightsDashboard';
import './AdminDashboard.css';

interface StatCard {
  title: string;
  value: number;
  icon: string;
  color: string;
  suffix?: string;
}

interface User {
  username: string;
  email: string;
  name: string;
  role: string;
  subscription: string;
  created_at: string;
  last_login: string | null;
  verified: boolean;
}

interface DashboardStats {
  total_users: number;
  admin_users: number;
  premium_users: number;
  enterprise_users: number;
  free_users: number;
  monthly_revenue: number;
  timestamp: string;
}

export const AdminDashboard: React.FC = () => {
  const navigate = useNavigate();
  const { logout } = useAuth();
  const [stats, setStats] = useState<DashboardStats | null>(null);
  const [users, setUsers] = useState<User[]>([]);
  const [movies, setMovies] = useState<Movie[]>([]);
  const [loading, setLoading] = useState(true);
  const [activeTab, setActiveTab] = useState('overview');
  const [selectedUser, setSelectedUser] = useState<User | null>(null);
  const [searchQuery, setSearchQuery] = useState('');
  const [selectedMovies, setSelectedMovies] = useState<Set<string>>(new Set());

  // CSV Import states
  const [showCSVModal, setShowCSVModal] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [previewMovies, setPreviewMovies] = useState<Movie[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const token = localStorage.getItem('authToken');
  const user = localStorage.getItem('user') ? JSON.parse(localStorage.getItem('user') || '{}') : null;

  useEffect(() => {
    if (!token || !user || (user.role !== 'admin' && user.role !== 'manager')) {
      navigate('/login');
      return;
    }

    fetchData();
    const interval = setInterval(fetchData, 30000);

    return () => clearInterval(interval);
  }, []);

  const fetchData = async () => {
    try {
      const headers = { 'Authorization': `Bearer ${token}` };

      const [statsRes, usersRes] = await Promise.all([
        fetch(buildApiUrl('/admin/stats'), { headers }),
        fetch(buildApiUrl('/admin/users'), { headers })
      ]);

      if (statsRes.ok) {
        const statsData = await statsRes.json();
        setStats(statsData);
      }

      if (usersRes.ok) {
        const usersData = await usersRes.json();
        setUsers(usersData.users || []);
      }

      // Load movies from backend API
      const loadedMovies = await loadMoviesFromAPI();
      setMovies(loadedMovies);
    } catch (error) {
      console.error('Error fetching dashboard data:', error);
    } finally {
      setLoading(false);
    }
  };

  const handleLogout = () => {
    logout();          // clears authToken, user, admin_auth from localStorage + resets context state
    navigate('/login');
  };

  const handleDeleteUser = async (username: string) => {
    if (!window.confirm(`Are you sure you want to delete user: ${username}?`)) return;

    try {
      const response = await fetch(buildApiUrl(`/admin/users/${username}`), {
        method: 'DELETE',
        headers: { 'Authorization': `Bearer ${token}` }
      });

      if (response.ok) {
        setUsers(users.filter(u => u.username !== username));
        alert('User deleted successfully');
      }
    } catch (error) {
      console.error('Error deleting user:', error);
    }
  };

  const handleDeleteMovie = (id: string) => {
    if (window.confirm('Are you sure you want to delete this movie?')) {
      deleteMovie(id);
      setMovies(movies.filter(m => m.id !== id));
      setSelectedMovies(prev => {
        const newSet = new Set(prev);
        newSet.delete(id);
        return newSet;
      });
    }
  };

  const handleDeleteSelectedMovies = () => {
    if (selectedMovies.size === 0) return;
    if (!window.confirm(`Are you sure you want to delete ${selectedMovies.size} selected movie(s)? This cannot be undone.`)) return;
    selectedMovies.forEach(id => deleteMovie(id));
    setMovies(movies.filter(m => !selectedMovies.has(m.id)));
    setSelectedMovies(new Set());
  };

  const handleSelectMovie = (id: string) => {
    const newSelection = new Set(selectedMovies);
    if (newSelection.has(id)) {
      newSelection.delete(id);
    } else {
      newSelection.add(id);
    }
    setSelectedMovies(newSelection);
  };

  const handleSelectAllMovies = () => {
    if (selectedMovies.size === movies.length) {
      setSelectedMovies(new Set());
    } else {
      setSelectedMovies(new Set(movies.map(m => m.id)));
    }
  };

  // CSV Import handlers
  const openCSVModal = () => {
    setShowCSVModal(true);
    setCsvFile(null);
    setPreviewMovies([]);
    setUploadMessage(null);
  };

  const closeCSVModal = () => {
    setShowCSVModal(false);
    setCsvFile(null);
    setPreviewMovies([]);
    setUploadMessage(null);
  };

  const handleCSVFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCsvFile(file);
    setUploadMessage(null);
    setIsUploading(true);

    try {
      const formData = new FormData();
      formData.append('file', file);

      const response = await fetch(buildApiUrl('/import_movies_csv'), {
        method: 'POST',
        body: formData,
      });

      const result = await response.json();

      if (result.status === 'ok') {
        setPreviewMovies(result.movies);
        setUploadMessage({ type: 'success', text: `Found ${result.count} movies in CSV` });
      } else {
        setUploadMessage({ type: 'error', text: result.error || 'Failed to parse CSV' });
        setPreviewMovies([]);
      }
    } catch {
      setUploadMessage({ type: 'error', text: 'Failed to connect to server' });
      setPreviewMovies([]);
    } finally {
      setIsUploading(false);
    }
  };

  const handleImportMovies = async () => {
    if (previewMovies.length === 0) return;

    const importedCount = importMoviesFromCSV(previewMovies);
    setUploadMessage({ type: 'success', text: `Successfully imported ${importedCount} movies!` });

    setTimeout(async () => {
      closeCSVModal();
      await fetchData();
    }, 1500);
  };

  const filteredUsers = users.filter(u =>
    u.username.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.email.toLowerCase().includes(searchQuery.toLowerCase()) ||
    u.name.toLowerCase().includes(searchQuery.toLowerCase())
  );

  const statCards: StatCard[] = stats ? [
    { title: 'Total Users', value: stats.total_users, icon: '👥', color: '#e50914', suffix: '' },
    { title: 'Premium Users', value: stats.premium_users, icon: '⭐', color: '#f59e0b', suffix: '' },
    { title: 'Movies', value: movies.length, icon: '🎬', color: '#06b6d4', suffix: '' },
    { title: 'Total Views', value: movies.reduce((sum, m) => sum + (m.views || 0), 0), icon: '👁️', color: '#10b981', suffix: '' }
  ] : [];

  return (
    <div className="netflix-admin-container">
      {/* Header */}
      <header className="netflix-admin-header">
        <div className="header-left">
          <h1 className="admin-title">🎬 StreamFlix Admin</h1>
          <p className="admin-subtitle">Content & User Management</p>
        </div>
        <div className="header-right">
          <div className="user-info">
            <span className="user-name">{user?.name}</span>
            <span className="role-badge">{user?.role.toUpperCase()}</span>
          </div>
          <button className="logout-btn" onClick={handleLogout}>
            <i className="fas fa-sign-out-alt"></i> Logout
          </button>
        </div>
      </header>

      {/* Navigation Tabs */}
      <nav className="netflix-admin-nav">
        <button
          className={`nav-tab ${activeTab === 'overview' ? 'active' : ''}`}
          onClick={() => setActiveTab('overview')}
        >
          <i className="fas fa-chart-pie"></i> Overview
        </button>
        <button
          className={`nav-tab ${activeTab === 'movies' ? 'active' : ''}`}
          onClick={() => setActiveTab('movies')}
        >
          <i className="fas fa-film"></i> Movies ({movies.length})
        </button>
        <button
          className={`nav-tab ${activeTab === 'users' ? 'active' : ''}`}
          onClick={() => setActiveTab('users')}
        >
          <i className="fas fa-users"></i> Users ({users.length})
        </button>
        <button
          className={`nav-tab ${activeTab === 'insights' ? 'active' : ''}`}
          onClick={() => setActiveTab('insights')}
        >
          <i className="fas fa-chart-bar"></i> Insights
        </button>
      </nav>

      {/* Main Content */}
      <main className="netflix-admin-content">
        {/* Overview Tab */}
        {activeTab === 'overview' && (
          <div className="overview-section">
            <div className="section-header">
              <h2>Dashboard Overview</h2>
              <p>Platform statistics and analytics</p>
            </div>

            {/* Stats Grid */}
            <div className="stats-grid">
              {statCards.map((card, idx) => (
                <div key={idx} className="stat-card" style={{ '--accent-color': card.color } as React.CSSProperties}>
                  <div className="stat-icon">{card.icon}</div>
                  <div className="stat-content">
                    <h3>{card.title}</h3>
                    <p className="stat-value">{card.suffix}{card.value.toLocaleString()}</p>
                  </div>
                </div>
              ))}
            </div>

            {/* Quick Actions */}
            <div className="quick-actions">
              <h3>Quick Actions</h3>
              <div className="actions-grid">
                <button
                  onClick={() => setActiveTab('movies')}
                  className="action-btn action-upload"
                >
                  <i className="fas fa-plus"></i> Upload Movie
                </button>
                <button
                  onClick={() => navigate('/admin/movie-editor')}
                  className="action-btn action-edit"
                >
                  <i className="fas fa-pen"></i> Edit Movies
                </button>
                <button
                  onClick={() => navigate('/admin/pipeline')}
                  className="action-btn action-ai"
                >
                  <i className="fas fa-brain"></i> AI Pipeline
                </button>
              </div>
            </div>
          </div>
        )}

        {/* Movies Tab */}
        {activeTab === 'movies' && (
          <div className="movies-section">
            <div className="section-header">
              <h2>Content Library</h2>
              <div style={{ display: 'flex', gap: '10px', alignItems: 'center', flexWrap: 'wrap' }}>
                {selectedMovies.size > 0 && (
                  <button
                    onClick={handleDeleteSelectedMovies}
                    className="upload-btn"
                    style={{ background: '#e50914', borderColor: '#e50914' }}
                  >
                    <i className="fas fa-trash"></i> Delete Selected ({selectedMovies.size})
                  </button>
                )}
                <button
                  onClick={openCSVModal}
                  className="upload-btn"
                  style={{ background: '#2563eb', borderColor: '#2563eb' }}
                >
                  <i className="fas fa-file-csv"></i> Import CSV
                </button>
                <button
                  onClick={() => navigate('/admin/movie-editor')}
                  className="upload-btn"
                >
                  <i className="fas fa-plus"></i> Upload New Movie
                </button>
              </div>
            </div>

            {movies.length > 0 ? (
              <div className="movies-container">
                {/* Bulk select toolbar */}
                <div style={{ display: 'flex', alignItems: 'center', gap: '10px', marginBottom: '12px', padding: '8px 12px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px' }}>
                  <label style={{ display: 'flex', alignItems: 'center', gap: '8px', cursor: 'pointer', color: '#ccc', fontSize: '14px', userSelect: 'none' }}>
                    <input
                      type="checkbox"
                      checked={selectedMovies.size === movies.length && movies.length > 0}
                      onChange={handleSelectAllMovies}
                      style={{ width: '16px', height: '16px', cursor: 'pointer', accentColor: '#e50914' }}
                    />
                    {selectedMovies.size === movies.length && movies.length > 0 ? 'Deselect All' : 'Select All'}
                  </label>
                  {selectedMovies.size > 0 && (
                    <span style={{ color: '#e50914', fontSize: '13px', fontWeight: 600 }}>
                      {selectedMovies.size} of {movies.length} selected
                    </span>
                  )}
                </div>

                {/* Movie Grid */}
                <div className="movies-grid">
                  {movies.map(movie => (
                    <div
                      key={movie.id}
                      className="movie-card"
                      style={selectedMovies.has(movie.id) ? { outline: '2px solid #e50914', borderRadius: '8px' } : {}}
                    >
                      {/* Checkbox */}
                      <div style={{ position: 'absolute', top: '8px', left: '8px', zIndex: 10 }}>
                        <input
                          type="checkbox"
                          checked={selectedMovies.has(movie.id)}
                          onChange={() => handleSelectMovie(movie.id)}
                          onClick={e => e.stopPropagation()}
                          style={{ width: '18px', height: '18px', cursor: 'pointer', accentColor: '#e50914' }}
                        />
                      </div>
                      <div className="movie-poster-container">
                        <img src={movie.poster} alt={movie.title} className="movie-poster" />
                        <div className="movie-overlay">
                          <button
                            onClick={() => navigate(`/admin/edit/${movie.id}`)}
                            className="overlay-btn edit-btn"
                            title="Edit"
                          >
                            <i className="fas fa-pen"></i>
                          </button>
                          <button
                            onClick={() => handleDeleteMovie(movie.id)}
                            className="overlay-btn delete-btn"
                            title="Delete"
                          >
                            <i className="fas fa-trash"></i>
                          </button>
                        </div>
                        <div className="movie-badge">{movie.category}</div>
                      </div>
                      <div className="movie-info">
                        <h4 className="movie-title">{movie.title}</h4>
                        <p className="movie-meta">{movie.year} • {movie.duration}</p>
                        <div className="movie-stats">
                          <span><i className="fas fa-eye"></i> {movie.views}</span>
                          <span><i className="fas fa-star"></i> {movie.rating}</span>
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            ) : (
              <div className="empty-state">
                <i className="fas fa-film"></i>
                <h3>No Movies Yet</h3>
                <p>Start by uploading your first movie</p>
                <button onClick={() => navigate('/admin/movie-editor')} className="upload-btn">
                  <i className="fas fa-plus"></i> Upload Now
                </button>
              </div>
            )}
          </div>
        )}

        {/* Users Tab */}
        {activeTab === 'users' && (
          <div className="users-section">
            <div className="section-header">
              <h2>User Management</h2>
              <div className="search-box">
                <i className="fas fa-search"></i>
                <input
                  type="text"
                  placeholder="Search users..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                />
              </div>
            </div>

            <div className="users-table-container">
              <div className="users-table">
                <div className="table-row table-header">
                  <div className="table-cell">Username</div>
                  <div className="table-cell">Name</div>
                  <div className="table-cell">Email</div>
                  <div className="table-cell">Subscription</div>
                  <div className="table-cell">Role</div>
                  <div className="table-cell">Joined</div>
                  <div className="table-cell">Actions</div>
                </div>

                {filteredUsers.length > 0 ? (
                  filteredUsers.map(u => (
                    <div key={u.username} className="table-row">
                      <div className="table-cell">{u.username}</div>
                      <div className="table-cell">{u.name}</div>
                      <div className="table-cell">{u.email}</div>
                      <div className="table-cell">
                        <span className={`badge badge-${u.subscription}`}>
                          {u.subscription.toUpperCase()}
                        </span>
                      </div>
                      <div className="table-cell">
                        <span className={`badge badge-${u.role}`}>
                          {u.role.toUpperCase()}
                        </span>
                      </div>
                      <div className="table-cell">{new Date(u.created_at).toLocaleDateString()}</div>
                      <div className="table-cell">
                        {u.role !== 'admin' && (
                          <button
                            className="delete-action"
                            onClick={() => handleDeleteUser(u.username)}
                            title="Delete user"
                          >
                            <i className="fas fa-trash"></i> Delete
                          </button>
                        )}
                      </div>
                    </div>
                  ))
                ) : (
                  <div className="table-empty">No users found</div>
                )}
              </div>
            </div>
          </div>
        )}

        {/* Insights Tab */}
        {activeTab === 'insights' && (
          <div style={{ padding: '8px 0' }}>
            <div className="section-header">
              <h2>Platform Insights</h2>
              <p>Analytics, trends and visualizations across movies and users</p>
            </div>
            <InsightsDashboard movies={movies} users={users} />
          </div>
        )}
      </main>

      {/* CSV Import Modal */}
      {showCSVModal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.85)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000, padding: '16px' }}>
          <div style={{ background: '#181818', borderRadius: '12px', boxShadow: '0 25px 50px rgba(0,0,0,0.8)', border: '1px solid #374151', width: '100%', maxWidth: '760px', maxHeight: '90vh', overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>
            {/* Modal Header */}
            <div style={{ padding: '24px', borderBottom: '1px solid #374151', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <h2 style={{ color: '#fff', fontSize: '22px', fontWeight: 700, margin: 0 }}>
                <i className="fas fa-file-csv" style={{ marginRight: '10px', color: '#2563eb' }}></i>
                Import Movies from CSV
              </h2>
              <button onClick={closeCSVModal} style={{ background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontSize: '20px' }}>
                <i className="fas fa-times"></i>
              </button>
            </div>

            {/* Modal Body */}
            <div style={{ padding: '24px', overflowY: 'auto', flex: 1 }}>
              {/* File Upload Zone */}
              <div style={{ marginBottom: '24px' }}>
                <label style={{ display: 'block', color: '#d1d5db', fontSize: '14px', fontWeight: 700, marginBottom: '12px' }}>Select CSV File</label>
                <div
                  style={{ border: '2px dashed #4b5563', borderRadius: '10px', padding: '40px', textAlign: 'center', cursor: 'pointer' }}
                  onClick={() => fileInputRef.current?.click()}
                >
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleCSVFileSelect}
                    style={{ display: 'none' }}
                  />
                  <div style={{ width: '64px', height: '64px', background: '#1f2937', borderRadius: '50%', display: 'flex', alignItems: 'center', justifyContent: 'center', margin: '0 auto 16px' }}>
                    <i className="fas fa-file-csv" style={{ fontSize: '24px', color: '#9ca3af' }}></i>
                  </div>
                  {csvFile ? (
                    <div style={{ color: '#fff' }}>
                      <p style={{ fontWeight: 600, margin: '0 0 4px' }}>{csvFile.name}</p>
                      <p style={{ color: '#9ca3af', fontSize: '13px', margin: 0 }}>{(csvFile.size / 1024).toFixed(2)} KB</p>
                    </div>
                  ) : (
                    <>
                      <p style={{ color: '#9ca3af', margin: '0 0 8px' }}>Drag & drop your CSV file here or</p>
                      <span style={{ color: '#2563eb', fontSize: '14px' }}>Browse Files</span>
                    </>
                  )}
                  {isUploading && (
                    <p style={{ color: '#9ca3af', marginTop: '12px', fontSize: '13px' }}>
                      <i className="fas fa-circle-notch fa-spin" style={{ marginRight: '6px' }}></i>Parsing CSV...
                    </p>
                  )}
                </div>
              </div>

              {/* Status Message */}
              {uploadMessage && (
                <div style={{
                  marginBottom: '20px', padding: '12px 16px', borderRadius: '8px',
                  background: uploadMessage.type === 'success' ? 'rgba(6,78,59,0.5)' : 'rgba(127,29,29,0.5)',
                  border: `1px solid ${uploadMessage.type === 'success' ? '#10b981' : '#ef4444'}`,
                  color: uploadMessage.type === 'success' ? '#34d399' : '#f87171',
                  fontSize: '14px'
                }}>
                  <i className={`fas ${uploadMessage.type === 'success' ? 'fa-check-circle' : 'fa-exclamation-circle'}`} style={{ marginRight: '8px' }}></i>
                  {uploadMessage.text}
                </div>
              )}

              {/* Preview Table */}
              {previewMovies.length > 0 && (
                <div>
                  <h3 style={{ color: '#fff', fontSize: '16px', fontWeight: 700, marginBottom: '12px' }}>
                    Preview ({previewMovies.length} movies)
                  </h3>
                  <div style={{ background: '#111827', borderRadius: '8px', border: '1px solid #374151', maxHeight: '260px', overflowY: 'auto' }}>
                    <table style={{ width: '100%', fontSize: '13px', borderCollapse: 'collapse' }}>
                      <thead style={{ background: 'rgba(0,0,0,0.5)', position: 'sticky', top: 0 }}>
                        <tr>
                          {['Title', 'Year', 'Genre', 'Category'].map(h => (
                            <th key={h} style={{ textAlign: 'left', padding: '10px 12px', color: '#9ca3af', fontWeight: 600 }}>{h}</th>
                          ))}
                        </tr>
                      </thead>
                      <tbody>
                        {previewMovies.slice(0, 10).map((movie, idx) => (
                          <tr key={idx} style={{ borderTop: '1px solid #374151' }}>
                            <td style={{ padding: '10px 12px', color: '#f3f4f6', fontWeight: 500 }}>{movie.title}</td>
                            <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{movie.year}</td>
                            <td style={{ padding: '10px 12px', color: '#9ca3af' }}>{movie.genres?.join(', ')}</td>
                            <td style={{ padding: '10px 12px', color: '#9ca3af', textTransform: 'capitalize' }}>{movie.category?.replace('_', ' ')}</td>
                          </tr>
                        ))}
                        {previewMovies.length > 10 && (
                          <tr style={{ borderTop: '1px solid #374151' }}>
                            <td colSpan={4} style={{ padding: '10px 12px', color: '#6b7280', textAlign: 'center' }}>
                              ...and {previewMovies.length - 10} more movies
                            </td>
                          </tr>
                        )}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}

              {/* CSV Format Help */}
              <div style={{ marginTop: '20px', padding: '14px', background: 'rgba(17,24,39,0.7)', borderRadius: '8px', border: '1px solid #374151' }}>
                <h4 style={{ color: '#fff', fontWeight: 700, margin: '0 0 8px', fontSize: '14px' }}>Expected CSV Format</h4>
                <p style={{ color: '#9ca3af', fontSize: '12px', margin: '0 0 6px' }}>Your CSV should include these columns:</p>
                <code style={{ color: '#34d399', fontSize: '12px', display: 'block', wordBreak: 'break-all' }}>movie_id, title, genres, year, runtime_min, rating, language, view_count, emotion_tags</code>
                <p style={{ color: '#6b7280', fontSize: '11px', margin: '6px 0 0' }}>Tip: genres should be separated by | (pipe), e.g. "Action|Thriller|Sci-Fi"</p>
              </div>
            </div>

            {/* Modal Footer */}
            <div style={{ padding: '20px 24px', borderTop: '1px solid #374151', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
              <button
                onClick={closeCSVModal}
                style={{ padding: '10px 20px', background: 'none', border: 'none', color: '#9ca3af', cursor: 'pointer', fontWeight: 700, fontSize: '14px' }}
              >
                Cancel
              </button>
              <button
                onClick={handleImportMovies}
                disabled={previewMovies.length === 0 || isUploading}
                style={{
                  padding: '10px 24px', background: previewMovies.length === 0 ? '#374151' : '#e50914',
                  border: 'none', color: '#fff', fontWeight: 700, borderRadius: '6px',
                  cursor: previewMovies.length === 0 ? 'not-allowed' : 'pointer',
                  fontSize: '14px', display: 'flex', alignItems: 'center', gap: '8px'
                }}
              >
                {isUploading && <i className="fas fa-circle-notch fa-spin"></i>}
                Import {previewMovies.length > 0 ? previewMovies.length : ''} Movies
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Loading Indicator */}
      {loading && (
        <div className="loading-overlay">
          <div className="loading-spinner"></div>
          <p>Loading...</p>
        </div>
      )}
    </div>
  );
};

export default AdminDashboard;

