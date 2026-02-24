
import React, { useState, useEffect } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { getMovieById, loadMoviesFromAPI } from '../../services/storage';
import { buildApiUrl } from '../../constants';
import { MovieFormData } from '../../types';

const MovieEditor: React.FC = () => {
  const navigate = useNavigate();
  const { id } = useParams<{ id: string }>();
  
  const [formData, setFormData] = useState<MovieFormData>({
    title: '',
    description: '',
    genres: [],
    year: new Date().getFullYear(),
    duration: '',
    rating: 'PG-13',
    poster: '',
    backdrop: '',
    videoUrl: '',
    category: 'standard',
  });

  const [genreInput, setGenreInput] = useState('');
  const [loading, setLoading] = useState(false);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);
  const [uploadProgress, setUploadProgress] = useState<string | null>(null);

  const suggestedGenres = ['Emotional', 'Comedy', 'Motivational', 'Action', 'Sci-Fi', 'Horror', 'Documentary'];

  useEffect(() => {
    if (id) {
      // Try in-memory cache first; if empty (direct URL access), load from API
      const movie = getMovieById(id);
      if (movie) {
        // eslint-disable-next-line @typescript-eslint/no-unused-vars
        const { id: _, views, createdAt, ...rest } = movie;
        setFormData(rest);
      } else {
        // Cache is empty — page was accessed directly; fetch fresh from API
        loadMoviesFromAPI().then(() => {
          const freshMovie = getMovieById(id);
          if (freshMovie) {
            // eslint-disable-next-line @typescript-eslint/no-unused-vars
            const { id: _, views, createdAt, ...rest } = freshMovie;
            setFormData(rest);
          }
        });
      }
    }
  }, [id]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement | HTMLSelectElement>) => {
    const { name, value } = e.target;
    if (name === 'year') {
      setFormData(prev => ({ ...prev, [name]: parseInt(value) || new Date().getFullYear() }));
    } else if (name === 'poster') {
      // URL typed → clear any selected poster file
      setFormData(prev => ({ ...prev, poster: value, posterFile: null }));
    } else if (name === 'backdrop') {
      // URL typed → clear any selected backdrop file
      setFormData(prev => ({ ...prev, backdrop: value, backdropFile: null }));
    } else if (name === 'videoUrl') {
      // URL typed → clear any selected video file
      setFormData(prev => ({ ...prev, videoUrl: value, videoFile: null }));
    } else {
      setFormData(prev => ({ ...prev, [name]: value }));
    }
  };

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>, field: 'videoFile' | 'posterFile' | 'backdropFile') => {
    if (e.target.files && e.target.files[0]) {
      const file = e.target.files[0];
      // File chosen → clear the corresponding URL field
      if (field === 'videoFile')
        setFormData(prev => ({ ...prev, videoFile: file, videoUrl: '' }));
      else if (field === 'posterFile')
        setFormData(prev => ({ ...prev, posterFile: file, poster: '' }));
      else if (field === 'backdropFile')
        setFormData(prev => ({ ...prev, backdropFile: file, backdrop: '' }));
    }
  };

  const addGenre = (genre: string) => {
    const trimmed = genre.trim();
    if (trimmed && !formData.genres.includes(trimmed)) {
      setFormData(prev => ({ ...prev, genres: [...prev.genres, trimmed] }));
    }
    setGenreInput('');
  };

  const handleGenreAdd = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && genreInput.trim()) {
      e.preventDefault();
      addGenre(genreInput);
    }
  };

  const removeGenre = (genre: string) => {
    setFormData(prev => ({ ...prev, genres: prev.genres.filter(g => g !== genre) }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setLoading(true);
    setErrorMessage(null);
    setUploadProgress(null);

    if (!formData.videoUrl && !formData.videoFile) {
      setErrorMessage('Please upload a video file or provide a video URL before saving.');
      setLoading(false);
      return;
    }

    try {
      const token = localStorage.getItem('authToken');

      /** Upload a local file to the backend and return its public URL */
      const uploadToServer = async (file: File, label: string): Promise<string> => {
        const mb = (file.size / 1024 / 1024).toFixed(2);
        setUploadProgress(`Uploading ${label} (${mb} MB)…`);
        const fd = new FormData();
        fd.append('file', file);
        const res = await fetch(buildApiUrl('/admin/upload'), {
          method: 'POST',
          headers: token ? { Authorization: `Bearer ${token}` } : {},
          body: fd,
        });
        if (!res.ok) {
          const e = await res.json().catch(() => ({ error: res.statusText }));
          throw new Error(`Upload failed for ${label}: ${e.error}`);
        }
        const { url } = await res.json();
        return url as string;
      };

      // ── Step 1: Upload any local files and get server paths ───────────────
      // posterFile/backdropFile/videoFile → upload → store server path in payload
      // poster/backdrop/videoUrl (strings) → external URLs, send as-is
      let videoUrl      = formData.videoUrl   || '';
      let poster        = formData.poster      || '';
      let backdrop      = formData.backdrop    || '';
      let videoFilePath = '';   // server-relative path for uploaded video
      let posterFilePath= '';   // server-relative path for uploaded poster
      let backdropFilePath = ''; // server-relative path for uploaded backdrop

      if (formData.videoFile) {
        const serverUrl   = await uploadToServer(formData.videoFile,   'video');
        videoFilePath     = serverUrl;  // full URL like http://localhost:5000/uploads/xxx.mp4
        videoUrl          = '';         // clear URL — file takes over
      }
      if (formData.posterFile) {
        const serverUrl   = await uploadToServer(formData.posterFile,  'poster image');
        posterFilePath    = serverUrl;
        poster            = '';
      }
      if (formData.backdropFile) {
        const serverUrl   = await uploadToServer(formData.backdropFile, 'backdrop image');
        backdropFilePath  = serverUrl;
        backdrop          = '';
      }

      // ── Step 2: Build backend payload with split columns ────────────────────
      // DB: videoUrl goes to video_url, videoFilePath goes to video_file_path, etc.
      const payload: Record<string, unknown> = {
        title:       formData.title,
        description: formData.description,
        genres:      formData.genres,
        year:        formData.year,
        duration:    formData.duration,
        rating:      formData.rating,
        category:    formData.category,
        trailerUrl:  formData.trailerUrl || '',
        mood:        (formData as any).mood     || 'happy',
        language:    (formData as any).language || '',
        // URL columns (external links)
        poster,
        backdrop,
        videoUrl,
        // File-path columns (server-hosted uploads)
        posterFile:   posterFilePath,
        backdropFile: backdropFilePath,
        videoFilePath: videoFilePath,
      };

      // ── Step 3: Save to MySQL via backend ───────────────────────────────────
      const headers: Record<string, string> = {
        'Content-Type': 'application/json',
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      };

      setUploadProgress('Saving to database…');

      let res: Response;
      if (id) {
        res = await fetch(buildApiUrl(`/admin/movies/${id}`), {
          method: 'PUT',
          headers,
          body: JSON.stringify(payload),
        });
      } else {
        const newId = Date.now().toString();
        res = await fetch(buildApiUrl('/admin/movies'), {
          method: 'POST',
          headers,
          body: JSON.stringify({ id: newId, ...payload }),
        });
      }

      if (!res.ok) {
        let errMsg = `Server returned ${res.status}`;
        try { const d = await res.json(); errMsg = d.error || d.message || errMsg; } catch { /* ignore */ }
        throw new Error(errMsg);
      }

      // ── Step 4: Refresh cache and navigate ─────────────────────────────────
      setUploadProgress('Refreshing movie list…');
      await loadMoviesFromAPI();
      navigate('/admin/dashboard');

    } catch (error) {
      console.error('[MovieEditor] Save error:', error);
      setErrorMessage(
        '❌ Save failed: ' + (error instanceof Error ? error.message : String(error))
      );
    } finally {
      setLoading(false);
      setUploadProgress(null);
    }
  };

  const inputClass = "w-full bg-[#333] border border-transparent focus:border-gray-400 rounded px-4 py-3 text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-netflix-red/50 transition-all";
  const labelClass = "block text-gray-300 text-xs font-bold mb-2 uppercase tracking-wide";

  return (
    <div className="pt-28 px-4 md:px-12 pb-12 max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-8">
          <h1 className="text-3xl font-bold text-white">{id ? 'Edit Movie Details' : 'Upload New Movie'}</h1>
          <button onClick={() => navigate('/admin/dashboard')} className="text-gray-400 hover:text-white transition">
              <i className="fas fa-times text-xl"></i>
          </button>
      </div>
      
      <form onSubmit={handleSubmit} className="space-y-8">
        {errorMessage && (
          <div className="bg-red-900/40 border border-red-500 text-red-200 px-4 py-3 rounded-lg text-sm">
            <i className="fas fa-exclamation-circle mr-2"></i>
            {errorMessage}
          </div>
        )}
        
        {uploadProgress && (
          <div className="bg-blue-900/40 border border-blue-500 text-blue-200 px-4 py-3 rounded-lg text-sm">
            <i className="fas fa-spinner fa-spin mr-2"></i>
            {uploadProgress}
          </div>
        )}
        
        {/* Main Section */}
        <div className="bg-[#181818] p-8 rounded-xl shadow-lg border border-gray-800">
            <h3 className="text-xl font-bold text-white mb-6 border-b border-gray-700 pb-2">Basic Information</h3>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6">
            <div>
                <label className={labelClass}>Title</label>
                <input name="title" value={formData.title} onChange={handleChange} className={inputClass} placeholder="Movie Title" required />
            </div>
            <div>
                <label className={labelClass}>Category</label>
                <div className="relative">
                    <select name="category" value={formData.category} onChange={handleChange} className={`${inputClass} appearance-none cursor-pointer`}>
                    <option value="standard">Standard Library</option>
                    <option value="trending">Trending Now</option>
                    <option value="top_rated">Top Rated</option>
                    <option value="new">New Release</option>
                    </select>
                    <div className="absolute right-4 top-4 text-gray-400 pointer-events-none">
                        <i className="fas fa-chevron-down"></i>
                    </div>
                </div>
            </div>
            <div className="md:col-span-2">
                <label className={labelClass}>Description</label>
                <textarea name="description" value={formData.description} onChange={handleChange} rows={4} className={inputClass} placeholder="Synopsis..." required />
            </div>
            </div>
        </div>

        {/* Metadata Section */}
        <div className="bg-[#181818] p-8 rounded-xl shadow-lg border border-gray-800">
             <h3 className="text-xl font-bold text-white mb-6 border-b border-gray-700 pb-2">Metadata</h3>
             <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
                <div>
                    <label className={labelClass}>Year</label>
                    <input type="number" name="year" value={formData.year} onChange={handleChange} className={inputClass} />
                </div>
                <div>
                    <label className={labelClass}>Duration</label>
                    <input name="duration" value={formData.duration} onChange={handleChange} placeholder="2h 15m" className={inputClass} />
                </div>
                <div>
                    <label className={labelClass}>Rating</label>
                    <input name="rating" value={formData.rating} onChange={handleChange} className={inputClass} placeholder="PG-13" />
                </div>
                <div>
                    <label className={labelClass}>Trailer URL</label>
                    <input name="trailerUrl" value={formData.trailerUrl || ''} onChange={handleChange} className={inputClass} placeholder="https://..." />
                </div>
            </div>
            <div className="mt-6">
                <label className={labelClass}>Genres</label>
                <div className="flex flex-wrap gap-2 mb-3 min-h-[40px] p-2 bg-[#222] rounded border border-gray-700">
                    {formData.genres.map(g => (
                    <span key={g} className="bg-netflix-red text-white px-3 py-1 rounded-full text-sm flex items-center shadow-sm">
                        {g} <button type="button" onClick={() => removeGenre(g)} className="ml-2 hover:text-black transition-colors"><i className="fas fa-times"></i></button>
                    </span>
                    ))}
                    {formData.genres.length === 0 && <span className="text-gray-500 text-sm italic">No genres added yet</span>}
                </div>
                <div className="flex flex-wrap gap-2 mb-3">
                  {suggestedGenres.map(g => (
                    <button 
                      key={g} 
                      type="button" 
                      onClick={() => addGenre(g)}
                      className="text-[10px] bg-gray-800 hover:bg-gray-700 text-gray-400 hover:text-white px-2 py-1 rounded border border-gray-700 transition-colors"
                    >
                      + {g}
                    </button>
                  ))}
                </div>
                <input value={genreInput} onChange={(e) => setGenreInput(e.target.value)} onKeyDown={handleGenreAdd} className={inputClass} placeholder="Type genre and press Enter..." />
            </div>
        </div>

        {/* Media Upload Section */}
        <div className="bg-[#181818] p-8 rounded-xl shadow-lg border border-gray-800">
          <h3 className="text-xl font-bold text-white mb-6 border-b border-gray-700 pb-2">Media Assets</h3>
          <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
            <UploadBox icon="image" label="Poster Image" name="poster" value={formData.poster} onChange={handleChange} onFileChange={(e) => handleFileChange(e, 'posterFile')} file={formData.posterFile} />
            <UploadBox icon="image" label="Backdrop Image" name="backdrop" value={formData.backdrop} onChange={handleChange} onFileChange={(e) => handleFileChange(e, 'backdropFile')} file={formData.backdropFile} />
            <UploadBox icon="video" label="Video File" name="videoUrl" value={formData.videoUrl} onChange={handleChange} onFileChange={(e) => handleFileChange(e, 'videoFile')} accept="video/*" file={formData.videoFile} />
          </div>
        </div>

        <div className="flex justify-end pt-4 gap-4">
          <button type="button" onClick={() => navigate('/admin/dashboard')} className="px-6 py-3 text-gray-400 hover:text-white font-bold transition-colors">
            Discard
          </button>
          <button type="submit" disabled={loading} className="px-10 py-3 bg-netflix-red text-white font-bold rounded shadow-lg hover:bg-red-700 hover:scale-105 active:scale-95 transition-all disabled:opacity-50 disabled:cursor-not-allowed flex items-center">
            {loading && <i className="fas fa-circle-notch fa-spin mr-2"></i>}
            {id ? 'Save Changes' : 'Publish Movie'}
          </button>
        </div>
      </form>
    </div>
  );
};

interface UploadBoxProps {
  icon: string;
  label: string;
  name: string;
  value: string;
  onChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  onFileChange: (e: React.ChangeEvent<HTMLInputElement>) => void;
  accept?: string;
  file?: File | null;
}

const UploadBox: React.FC<UploadBoxProps> = ({ icon, label, name, value, onChange, onFileChange, accept = "image/*", file }) => {
  const hasFile = file !== null && file !== undefined;
  const hasUrl  = !hasFile && value.trim().length > 0;
  const source  = hasFile ? 'file' : hasUrl ? 'url' : 'none';

  return (
    <div className={`group relative border-2 border-dashed rounded-lg p-6 text-center transition-all duration-300 ${
      source === 'file' ? 'border-green-600 bg-green-900/10' :
      source === 'url'  ? 'border-blue-600 bg-blue-900/10'  :
      'border-gray-700 hover:border-white hover:bg-[#222]'
    }`}>
        {/* Source badge */}
        {source !== 'none' && (
          <span className={`absolute top-2 right-2 text-[9px] font-bold px-2 py-0.5 rounded-full uppercase ${
            source === 'file' ? 'bg-green-700 text-green-200' : 'bg-blue-700 text-blue-200'
          }`}>
            {source === 'file' ? '📁 Local file' : '🔗 External URL'}
          </span>
        )}

        <div className={`w-12 h-12 rounded-full flex items-center justify-center mx-auto mb-3 transition-colors ${
          source === 'file' ? 'bg-green-800' : source === 'url' ? 'bg-blue-800' : 'bg-gray-800 group-hover:bg-gray-700'
        }`}>
            <i className={`fas fa-${
              source === 'file' ? 'check' : source === 'url' ? 'link' : icon
            } text-xl ${
              source === 'file' ? 'text-green-400' : source === 'url' ? 'text-blue-400' : 'text-gray-400 group-hover:text-white'
            }`}></i>
        </div>
        <p className="text-sm font-bold text-gray-300 mb-2 group-hover:text-white">{label}</p>

        {/* File picker */}
        <div className="relative">
            <input type="file" accept={accept} onChange={onFileChange} className="absolute inset-0 w-full h-full opacity-0 cursor-pointer z-10" />
            {hasFile ? (
                <div className="text-xs text-green-400">
                    <i className="fas fa-file mr-1"></i>
                    {file!.name.length > 20 ? file!.name.substring(0, 20) + '...' : file!.name}
                    <div className="text-[10px] text-gray-500 mt-1">{(file!.size / (1024 * 1024)).toFixed(2)} MB — will upload to server</div>
                </div>
            ) : (
                <div className="text-xs text-blue-400 hover:underline cursor-pointer">Choose file</div>
            )}
        </div>

        {/* URL input */}
        <div className="mt-4 pt-4 border-t border-gray-700">
            <p className="text-[10px] text-gray-500 mb-1 text-left uppercase font-bold">Or External URL</p>
            <input
              name={name}
              value={value}
              onChange={onChange}
              placeholder="https://…"
              className={`w-full bg-[#111] text-xs p-2 rounded border focus:outline-none ${
                hasUrl ? 'border-blue-500 text-blue-300' : 'border-gray-700 focus:border-gray-500'
              } ${hasFile ? 'opacity-40 cursor-not-allowed' : ''}`}
              disabled={hasFile}
              title={hasFile ? 'Remove the selected file first to use a URL' : ''}
            />
            {hasFile && (
              <p className="text-[9px] text-yellow-500 mt-1 text-left">
                URL disabled — file is selected (typing a URL will clear the file)
              </p>
            )}
        </div>
    </div>
  );
};

export default MovieEditor;
