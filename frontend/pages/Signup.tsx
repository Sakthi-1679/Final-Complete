import React, { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../constants';
import { useAuth } from '../context/AuthContext';
import './Auth.css';

interface SignupFormData {
  username: string;
  email: string;
  name: string;
  password: string;
  confirmPassword: string;
}

interface SignupResponse {
  success: boolean;
  message?: string;
  error?: string;
}

export const Signup: React.FC = () => {
  const navigate = useNavigate();
  const { userLogin } = useAuth();
  const [formData, setFormData] = useState<SignupFormData>({
    username: '',
    email: '',
    name: '',
    password: '',
    confirmPassword: ''
  });
  const [error, setError] = useState('');
  const [loading, setLoading] = useState(false);
  const [agreeTerms, setAgreeTerms] = useState(false);
  const [showPassword, setShowPassword] = useState(false);
  const [showConfirmPassword, setShowConfirmPassword] = useState(false);

  const handleChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const { name, value } = e.target;
    setFormData(prev => ({
      ...prev,
      [name]: value
    }));
  };

  const validateForm = (): boolean => {
    if (!formData.username || formData.username.length < 3) {
      setError('Username must be at least 3 characters');
      return false;
    }

    if (!formData.email || !formData.email.includes('@')) {
      setError('Please enter a valid email');
      return false;
    }

    if (!formData.name || formData.name.length < 2) {
      setError('Please enter your full name');
      return false;
    }

    if (!formData.password || formData.password.length < 6) {
      setError('Password must be at least 6 characters');
      return false;
    }

    if (formData.password !== formData.confirmPassword) {
      setError('Passwords do not match');
      return false;
    }

    if (!agreeTerms) {
      setError('You must agree to the terms and conditions');
      return false;
    }

    return true;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError('');

    if (!validateForm()) {
      return;
    }

    setLoading(true);

    try {
      const response = await fetch(buildApiUrl('/auth/register'), {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          username: formData.username,
          email: formData.email,
          name: formData.name,
          password: formData.password
        })
      });

      const data: SignupResponse = await response.json();

      if (data.success) {
        // Attempt automatic login after successful registration
        try {
          const loginResponse = await fetch(buildApiUrl('/auth/login'), {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify({
              username: formData.username,
              password: formData.password
            })
          });
          
          const loginData = await loginResponse.json();
          
          if (loginData.success && loginData.token) {
            // Auto-login successful — update context state so routes re-render reactively
            userLogin(loginData.token, loginData.user);
            navigate('/');
          } else {
            // Auto-login failed, redirect to manual login
            navigate(`/login?message=Account created successfully! Please log in.&user=${formData.username}`);
          }
        } catch (loginErr) {
          // If auto-login fails, redirect to login page
          navigate(`/login?message=Account created successfully! Please log in.&user=${formData.username}`);
          console.error('Auto-login error:', loginErr);
        }
      } else {
        setError(data.error || 'Signup failed');
      }
    } catch (err) {
      setError('Connection error. Please try again.');
      console.error('Signup error:', err);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="auth-container">
      <div className="auth-card">
        <div className="auth-header">
          <h1>🎬 MoviePulse</h1>
          <p>Join us for personalized movie recommendations</p>
        </div>

        <form onSubmit={handleSubmit}>
          <div className="form-group">
            <label htmlFor="name">Full Name</label>
            <input
              type="text"
              id="name"
              name="name"
              value={formData.name}
              onChange={handleChange}
              placeholder="John Doe"
              required
              disabled={loading}
              autoFocus
            />
          </div>

          <div className="form-group">
            <label htmlFor="email">Email</label>
            <input
              type="email"
              id="email"
              name="email"
              value={formData.email}
              onChange={handleChange}
              placeholder="your@email.com"
              required
              disabled={loading}
            />
          </div>

          <div className="form-group">
            <label htmlFor="username">Username</label>
            <input
              type="text"
              id="username"
              name="username"
              value={formData.username}
              onChange={handleChange}
              placeholder="Choose a username"
              required
              disabled={loading}
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
                placeholder="At least 6 characters"
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

          <div className="form-group">
            <label htmlFor="confirmPassword">Confirm Password</label>
            <div className="password-input-wrapper">
              <input
                type={showConfirmPassword ? "text" : "password"}
                id="confirmPassword"
                name="confirmPassword"
                value={formData.confirmPassword}
                onChange={handleChange}
                placeholder="Confirm your password"
                required
                disabled={loading}
              />
              <button
                type="button"
                onClick={() => setShowConfirmPassword(!showConfirmPassword)}
                className="password-toggle"
                title={showConfirmPassword ? "Hide password" : "Show password"}
              >
                <i className={`fas fa-eye${showConfirmPassword ? '' : '-slash'}`}></i>
              </button>
            </div>
          </div>

          <div className="form-checkbox">
            <input
              type="checkbox"
              id="agreeTerms"
              checked={agreeTerms}
              onChange={(e) => setAgreeTerms(e.target.checked)}
            />
            <label htmlFor="agreeTerms">
              I agree to the <a href="#terms">terms and conditions</a>
            </label>
          </div>

          {error && <div className="error-message">{error}</div>}

          <button 
            type="submit" 
            className="auth-button"
            disabled={loading}
          >
            {loading ? 'Creating Account...' : 'Sign Up'}
          </button>
        </form>

        <div className="auth-footer">
          <p>Already have an account? <a href="/login">Login here</a></p>
        </div>
      </div>
    </div>
  );
};

export default Signup;
