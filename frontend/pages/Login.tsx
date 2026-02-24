import React, { useState, useEffect } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import { buildApiUrl } from '../constants';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

interface LoginFormData {
  username: string;
  password: string;
}

interface LoginResponse {
  success: boolean;
  error?: string;
  token?: string;
  user?: {
    username: string;
    email: string;
    name: string;
    subscription: string;
    role: string;
  };
}

export const Login: React.FC = () => {
  const navigate = useNavigate();
  const { userLogin } = useAuth();
  const [searchParams] = useSearchParams();
  const [formData, setFormData] = useState<LoginFormData>({
    username: searchParams.get('user') || '',
    password: ''
  });
  const [error, setError] = useState('');
  const [successMessage, setSuccessMessage] = useState(searchParams.get('message') || '');
  const [loading, setLoading] = useState(false);
  const [rememberMe, setRememberMe] = useState(false);
  const [showPassword, setShowPassword] = useState(false);

  useEffect(() => {
    if (searchParams.get('message')) {
      setSuccessMessage(searchParams.get('message'));
      // Clear message after 5 seconds
      setTimeout(() => setSuccessMessage(''), 5000);
    }
  }, [searchParams]);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');
    setLoading(true);

    try {
      const response = await fetch(buildApiUrl('/auth/login'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify(formData)
      });

      const data: LoginResponse = await response.json();

      if (data.success) {
        // Update context (which also persists to localStorage) so App.tsx route tree
        // re-renders reactively without needing a hard page refresh
        userLogin(data.token!, data.user!);

        if (rememberMe) {
          localStorage.setItem('rememberMe', 'true');
        }

        // Redirect based on role
        if (data.user.role === 'admin' || data.user.role === 'manager') {
          navigate('/admin/dashboard');
        } else {
          navigate('/');
        }
      } else {
        setError(data.error || 'Login failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
      console.error('Login error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>🎬 MoviePulse</h1>
          <p>AI-Powered Movie Recommendations</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Enter your username"
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="password">Password</label>
            <div className="password-input-wrapper">
              <input
                type={showPassword ? "text" : "password"}
                id="password"
                name="password"
                value={formData.password}
                onChange={handleChange}
                placeholder="Enter your password"
                required
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => setShowPassword(!showPassword)}
                className="password-toggle"
                title={showPassword ? "Hide password" : "Show password"}
              >
                <i className={`fas fa-eye${showPassword ? '' : '-slash'}`}></i>
              </button>
            </div>
          </div>

          <div className="form-checkbox">
            <input
              type="checkbox"
              id="rememberMe"
              checked={rememberMe}
              onChange={(e) => setRememberMe(e.target.checked)}
            />
            <label htmlFor="rememberMe">Remember me</label>
          </div>

          {successMessage && <div className="success-message">{successMessage}</div>}
          {error && <div className="error-message">{error}</div>}

          <button 
            type="submit" 
            className="auth-button"
            disabled={loading}
          >
            {loading ? 'Logging in...' : 'Login'}
          </button>
        </form>

        <div className="auth-footer">
          <p>Don't have an account? <a href="/signup">Sign up here</a></p>
          <p className="demo-info">
            <strong>Demo Credentials:</strong><br/>
            Admin: admin / admin123<br/>
            Manager: manager / manager123
          </p>
        </div>
      </div>
    </div>
  );
};

export default Login;
