import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useAuth } from '../../context/AuthContext';

const AdminLogin: React.FC = () => {
  const [key, setKey] = useState('');
  const [error, setError] = useState('');
  const { login } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (login(key)) {
      navigate('/admin/dashboard');
    } else {
      setError('Invalid Access Key');
    }
  };

  return (
    <div className="min-h-screen bg-black flex flex-col items-center justify-center p-4">
      <div className="w-full max-w-md bg-netflix-dark p-12 rounded shadow-2xl border border-gray-800">
        <h1 className="text-3xl font-bold mb-8 text-white">Admin Access</h1>
        {error && <div className="bg-orange-500 p-3 rounded mb-4 text-white text-sm">{error}</div>}
        <form onSubmit={handleSubmit} className="space-y-6">
          <div>
            <label className="block text-gray-400 text-sm mb-2">Access Key</label>
            <input
              type="password"
              value={key}
              onChange={(e) => setKey(e.target.value)}
              className="w-full bg-gray-700 rounded px-4 py-3 text-white focus:outline-none focus:bg-gray-600"
              placeholder="Enter admin key (admin123)"
            />
          </div>
          <button 
            type="submit"
            className="w-full bg-netflix-red text-white font-bold py-3 rounded hover:bg-red-700 transition"
          >
            Enter Dashboard
          </button>
        </form>
        <div className="mt-6 text-center">
            <button onClick={() => navigate('/')} className="text-gray-500 hover:text-white text-sm">
                Return to Home
            </button>
        </div>
      </div>
    </div>
  );
};

export default AdminLogin;