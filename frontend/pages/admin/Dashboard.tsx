import React, { useEffect, useState, useRef } from 'react';
import { Link } from 'react-router-dom';
import { loadMoviesFromAPI, deleteMovie, importMoviesFromCSV, deleteMultipleMovies } from '../../services/storage';
import { Movie } from '../../types';
import { buildApiUrl } from '../../constants';

const Dashboard: React.FC = () => {
  const [movies, setMovies] = useState<Movie[]>([]);
  const [isRetraining, setIsRetraining] = useState(false);
  const [retrainMessage, setRetrainMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const [selectedMovies, setSelectedMovies] = useState<Set<string>>(new Set());
  
  // CSV Import states
  const [showCSVModal, setShowCSVModal] = useState(false);
  const [csvFile, setCsvFile] = useState<File | null>(null);
  const [previewMovies, setPreviewMovies] = useState<Movie[]>([]);
  const [isUploading, setIsUploading] = useState(false);
  const [uploadMessage, setUploadMessage] = useState<{type: 'success' | 'error', text: string} | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const loadMovies = async () => {
    const movies = await loadMoviesFromAPI();
    setMovies(movies);
  };

  useEffect(() => {
    loadMovies();
  }, []);

  const handleDelete = (id: string) => {
    if (window.confirm('Are you sure you want to delete this movie?')) {
      deleteMovie(id);
      loadMovies();
    }
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

  const handleSelectAll = () => {
    if (selectedMovies.size === movies.length) {
      setSelectedMovies(new Set());
    } else {
      setSelectedMovies(new Set(movies.map(m => m.id)));
    }
  };

  const handleDeleteSelected = () => {
    if (selectedMovies.size === 0) return;
    
    if (window.confirm(`Are you sure you want to delete ${selectedMovies.size} movies?`)) {
      deleteMultipleMovies(Array.from(selectedMovies));
      setSelectedMovies(new Set());
      loadMovies();
    }
  };

  const handleRetrainModel = async () => {
    if (!window.confirm('Are you sure you want to retrain the recommendation model? This will train on new interaction data.')) {
      return;
    }

    setIsRetraining(true);
    setRetrainMessage(null);

    try {
      const response = await fetch(buildApiUrl('/retrain_recommender'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({ epochs: 1 }),
      });

      const result = await response.json();

      if (result.status === 'ok') {
        setRetrainMessage({ type: 'success', text: 'Model retrained successfully' });
      } else if (result.status === 'skipped') {
        setRetrainMessage({ type: 'success', text: result.message || 'No new data to train on' });
      } else {
        setRetrainMessage({ type: 'error', text: result.error || 'Failed to retrain model' });
      }
    } catch (error) {
      setRetrainMessage({ type: 'error', text: 'Failed to connect to server' });
    } finally {
      setIsRetraining(false);
    }
  };

  // CSV Import handlers
  const handleCSVFileSelect = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;

    setCsvFile(file);
    setUploadMessage(null);

    // Send to backend for parsing
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
    } catch (error) {
      setUploadMessage({ type: 'error', text: 'Failed to connect to server' });
      setPreviewMovies([]);
    } finally {
      setIsUploading(false);
    }
  };

  const handleImportMovies = () => {
    if (previewMovies.length === 0) return;

    const importedCount = importMoviesFromCSV(previewMovies);
    setUploadMessage({ type: 'success', text: `Successfully imported ${importedCount} movies!` });
    
    // Reset and close modal after short delay
    setTimeout(() => {
      setShowCSVModal(false);
      setCsvFile(null);
      setPreviewMovies([]);
      setUploadMessage(null);
      loadMovies();
    }, 1500);
  };

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

  return (
    <div className="pt-28 px-4 md:px-12 min-h-screen pb-12">
      <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-8 gap-4">
        <div>
            <h1 className="text-3xl font-bold text-white">Content Dashboard</h1>
            <p className="text-gray-400 text-sm mt-1">Manage your library, view stats, and update content.</p>
        </div>
        <div className="flex gap-3 flex-wrap">
          <Link 
            to="/admin/pipeline" 
            className="bg-purple-600 hover:bg-purple-700 text-white px-6 py-3 rounded-md font-bold transition-all shadow-lg flex items-center hover:scale-105 active:scale-95"
          >
            <i className="fas fa-chart-line mr-2"></i> AI Pipeline
          </Link>
          <button
            onClick={handleRetrainModel}
            disabled={isRetraining}
            className={`px-4 py-3 rounded-md font-bold transition-all shadow-lg flex items-center ${
              isRetraining 
                ? 'bg-gray-600 cursor-not-allowed' 
                : 'bg-green-600 hover:bg-green-700 hover:scale-105 active:scale-95'
            } text-white`}
          >
            <i className={`fas fa-brain mr-2 ${isRetraining ? 'animate-pulse' : ''}`}></i>
            {isRetraining ? 'Retraining...' : 'Retrain Model (Continuous Learning)'}
          </button>
          <button 
            onClick={openCSVModal}
            className="bg-blue-600 hover:bg-blue-700 text-white px-6 py-3 rounded-md font-bold transition-all shadow-lg flex items-center hover:scale-105 active:scale-95"
          >
            <i className="fas fa-file-csv mr-2"></i> Import CSV
          </button>
          {selectedMovies.size > 0 && (
            <button 
              onClick={handleDeleteSelected}
              className="bg-red-600 hover:bg-red-700 text-white px-6 py-3 rounded-md font-bold transition-all shadow-lg flex items-center hover:scale-105 active:scale-95"
            >
              <i className="fas fa-trash mr-2"></i> Delete Selected ({selectedMovies.size})
            </button>
          )}
          <Link 
            to="/admin/add" 
            className="bg-netflix-red hover:bg-red-700 text-white px-6 py-3 rounded-md font-bold transition-all shadow-lg flex items-center hover:scale-105 active:scale-95"
          >
            <i className="fas fa-plus mr-2"></i> Add New Title
          </Link>
        </div>
      </div>

      {/* Retrain Message */}
      {retrainMessage && (
        <div className={`mb-6 p-4 rounded-md ${
          retrainMessage.type === 'success' 
            ? 'bg-green-900/50 border border-green-500 text-green-400' 
            : 'bg-red-900/50 border border-red-500 text-red-400'
        }`}>
          {retrainMessage.text}
        </div>
      )}

      <div className="bg-[#181818] rounded-xl overflow-hidden shadow-2xl border border-gray-800">
        {/* Table Header */}
        <div className="grid grid-cols-13 gap-4 p-5 bg-black/40 font-bold text-gray-400 text-xs uppercase tracking-wider border-b border-gray-800">
          <div className="col-span-1 flex items-center">
            <input 
              type="checkbox" 
              checked={selectedMovies.size === movies.length && movies.length > 0}
              onChange={handleSelectAll}
              className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-netflix-red focus:ring-netflix-red"
            />
          </div>
          <div className="col-span-1">Preview</div>
          <div className="col-span-4">Title Info</div>
          <div className="col-span-2">Category</div>
          <div className="col-span-1">Year</div>
          <div className="col-span-2">Views</div>
          <div className="col-span-2 text-right">Actions</div>
        </div>
        
        {/* Table Body */}
        <div className="divide-y divide-gray-800">
          {movies.map(movie => (
            <div key={movie.id} className={`grid grid-cols-13 gap-4 p-4 items-center hover:bg-white/5 transition-colors group ${selectedMovies.has(movie.id) ? 'bg-netflix-red/10' : ''}`}>
              <div className="col-span-1 flex items-center">
                <input 
                  type="checkbox" 
                  checked={selectedMovies.has(movie.id)}
                  onChange={() => handleSelectMovie(movie.id)}
                  className="w-4 h-4 rounded border-gray-600 bg-gray-700 text-netflix-red focus:ring-netflix-red"
                />
              </div>
              <div className="col-span-1">
                <img src={movie.poster} alt="" className="h-16 w-12 object-cover rounded shadow-md group-hover:scale-105 transition-transform" />
              </div>
              <div className="col-span-4">
                  <div className="font-bold text-white text-base flex items-center gap-2">
                    {movie.title}
                    {movie.videoUrl ? (
                      <span className="text-[9px] bg-green-600/30 text-green-400 px-1.5 py-0.5 rounded border border-green-500/30" title="Video uploaded">
                        <i className="fas fa-video mr-1"></i>Video
                      </span>
                    ) : (
                      <span className="text-[9px] bg-red-600/30 text-red-400 px-1.5 py-0.5 rounded border border-red-500/30" title="No video uploaded">
                        <i className="fas fa-video-slash mr-1"></i>No Video
                      </span>
                    )}
                  </div>
                  <div className="text-xs text-gray-500 mt-1">{movie.duration} - {movie.rating}</div>
              </div>
              <div className="col-span-2">
                <span className={`text-[10px] uppercase font-bold px-2 py-1 rounded-sm tracking-wide ${
                  movie.category === 'trending' ? 'bg-red-500/20 text-red-400 border border-red-500/30' :
                  movie.category === 'new' ? 'bg-blue-500/20 text-blue-400 border border-blue-500/30' : 
                  movie.category === 'top_rated' ? 'bg-yellow-500/20 text-yellow-400 border border-yellow-500/30' :
                  'bg-gray-700 text-gray-300'
                }`}>
                  {movie.category.replace('_', ' ')}
                </span>
              </div>
              <div className="col-span-1 text-gray-400 font-mono text-sm">{movie.year}</div>
              <div className="col-span-2 text-gray-400 font-mono text-sm">
                  {movie.views.toLocaleString()} <span className="text-xs text-gray-600 ml-1">views</span>
              </div>
              <div className="col-span-2 flex justify-end space-x-4">
                <Link to={`/admin/edit/${movie.id}`} className="text-gray-400 hover:text-white transition-colors" title="Edit">
                  <i className="fas fa-pen"></i>
                </Link>
                <button onClick={() => handleDelete(movie.id)} className="text-gray-400 hover:text-red-500 transition-colors" title="Delete">
                  <i className="fas fa-trash"></i>
                </button>
              </div>
            </div>
          ))}
          
          {movies.length === 0 && (
            <div className="p-12 text-center flex flex-col items-center justify-center text-gray-500">
                <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mb-4">
                    <i className="fas fa-film text-2xl"></i>
                </div>
                <p className="text-lg font-medium text-gray-400">Your library is empty</p>
                <p className="text-sm">Start adding movies to populate your platform.</p>
            </div>
          )}
        </div>
      </div>

      {/* CSV Import Modal */}
      {showCSVModal && (
        <div className="fixed inset-0 bg-black/80 flex items-center justify-center z-50 p-4">
          <div className="bg-[#181818] rounded-xl shadow-2xl border border-gray-700 w-full max-w-3xl max-h-[90vh] overflow-hidden">
            <div className="p-6 border-b border-gray-700 flex justify-between items-center">
              <h2 className="text-2xl font-bold text-white">Import Movies from CSV</h2>
              <button onClick={closeCSVModal} className="text-gray-400 hover:text-white transition-colors">
                <i className="fas fa-times text-xl"></i>
              </button>
            </div>
            
            <div className="p-6 overflow-y-auto max-h-[60vh]">
              {/* File Upload Section */}
              <div className="mb-6">
                <label className="block text-gray-300 text-sm font-bold mb-3">Select CSV File</label>
                <div className="border-2 border-dashed border-gray-600 rounded-lg p-8 text-center hover:border-gray-400 transition-colors">
                  <input
                    ref={fileInputRef}
                    type="file"
                    accept=".csv"
                    onChange={handleCSVFileSelect}
                    className="hidden"
                  />
                  <div className="w-16 h-16 bg-gray-800 rounded-full flex items-center justify-center mx-auto mb-4">
                    <i className="fas fa-file-csv text-2xl text-gray-400"></i>
                  </div>
                  {csvFile ? (
                    <div className="text-white font-medium">
                      <p>{csvFile.name}</p>
                      <p className="text-gray-400 text-sm mt-1">{(csvFile.size / 1024).toFixed(2)} KB</p>
                    </div>
                  ) : (
                    <>
                      <p className="text-gray-400 mb-2">Drag and drop your CSV file here</p>
                      <button 
                        onClick={() => fileInputRef.current?.click()}
                        className="text-blue-400 hover:underline"
                      >
                        Browse Files
                      </button>
                    </>
                  )}
                </div>
              </div>

              {/* Upload Status Message */}
              {uploadMessage && (
                <div className={`mb-6 p-4 rounded-md ${
                  uploadMessage.type === 'success' 
                    ? 'bg-green-900/50 border border-green-500 text-green-400' 
                    : 'bg-red-900/50 border border-red-500 text-red-400'
                }`}>
                  {uploadMessage.text}
                </div>
              )}

              {/* Preview Movies */}
              {previewMovies.length > 0 && (
                <div>
                  <h3 className="text-lg font-bold text-white mb-3">Preview ({previewMovies.length} movies)</h3>
                  <div className="bg-[#222] rounded-lg border border-gray-700 max-h-64 overflow-y-auto">
                    <table className="w-full text-sm">
                      <thead className="bg-black/50 sticky top-0">
                        <tr className="text-gray-400">
                          <th className="text-left p-3">Title</th>
                          <th className="text-left p-3">Year</th>
                          <th className="text-left p-3">Genre</th>
                          <th className="text-left p-3">Category</th>
                        </tr>
                      </thead>
                      <tbody className="divide-y divide-gray-700">
                        {previewMovies.slice(0, 10).map((movie, idx) => (
                          <tr key={idx} className="text-gray-300 hover:bg-white/5">
                            <td className="p-3 font-medium">{movie.title}</td>
                            <td className="p-3">{movie.year}</td>
                            <td className="p-3">{movie.genres.join(', ')}</td>
                            <td className="p-3 capitalize">{movie.category.replace('_', ' ')}</td>
                          </tr>
                        ))}
                        {previewMovies.length > 10 && (
                          <tr>
                            <td colSpan={4} className="p-3 text-center text-gray-500">
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
              <div className="mt-6 p-4 bg-gray-900/50 rounded-lg border border-gray-700">
                <h4 className="text-white font-bold mb-2">Expected CSV Format</h4>
                <p className="text-gray-400 text-xs mb-2">Your CSV should include these columns:</p>
                <code className="text-green-400 text-xs block">movie_id, title, genres, year, runtime_min, rating, language, view_count, emotion_tags</code>
                <p className="text-gray-500 text-xs mt-2">Note: genres should be separated by | (pipe), e.g., "Action|Thriller|Sci-Fi"</p>
              </div>
            </div>

            {/* Modal Footer */}
            <div className="p-6 border-t border-gray-700 flex justify-end gap-4">
              <button 
                onClick={closeCSVModal}
                className="px-6 py-2 text-gray-400 hover:text-white font-bold transition-colors"
              >
                Cancel
              </button>
              <button 
                onClick={handleImportMovies}
                disabled={previewMovies.length === 0 || isUploading}
                className={`px-6 py-2 bg-netflix-red text-white font-bold rounded shadow-lg hover:bg-red-700 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center ${previewMovies.length === 0 ? 'opacity-50 cursor-not-allowed' : ''}`}
              >
                {isUploading && <i className="fas fa-circle-notch fa-spin mr-2"></i>}
                Import {previewMovies.length} Movies
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
