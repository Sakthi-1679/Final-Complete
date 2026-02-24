import React, { createContext, useContext, useState, useEffect } from 'react';
import { ADMIN_KEY } from '../constants';

interface UserInfo {
  username: string;
  email: string;
  name: string;
  subscription: string;
  role: string;
}

interface AuthContextType {
  isAdmin: boolean;
  isLoggedIn: boolean;
  currentUser: UserInfo | null;
  login: (key: string) => boolean;               // admin-panel key login
  userLogin: (token: string, user: UserInfo) => void; // regular JWT login
  logout: () => void;                            // clears everything
}

const AuthContext = createContext<AuthContextType | null>(null);

export const AuthProvider: React.FC<{ children: React.ReactNode }> = ({ children }) => {
  const [isAdmin, setIsAdmin] = useState(false);
  const [isLoggedIn, setIsLoggedIn] = useState(() => !!localStorage.getItem('authToken'));
  const [currentUser, setCurrentUser] = useState<UserInfo | null>(() => {
    try {
      const raw = localStorage.getItem('user');
      return raw ? JSON.parse(raw) : null;
    } catch { return null; }
  });

  useEffect(() => {
    if (localStorage.getItem('admin_auth') === 'true') setIsAdmin(true);
  }, []);

  /** Log in via admin-panel secret key */
  const login = (key: string) => {
    if (key === ADMIN_KEY) {
      setIsAdmin(true);
      localStorage.setItem('admin_auth', 'true');
      return true;
    }
    return false;
  };

  /** Log in a regular user with a JWT + user data returned from the backend */
  const userLogin = (token: string, user: UserInfo) => {
    localStorage.setItem('authToken', token);
    localStorage.setItem('user', JSON.stringify(user));
    setCurrentUser(user);
    setIsLoggedIn(true);
    if (user.role === 'admin' || user.role === 'manager') {
      setIsAdmin(true);
      localStorage.setItem('admin_auth', 'true');
    }
  };

  /** Full logout — clears JWT, user data, and admin flag */
  const logout = () => {
    setIsAdmin(false);
    setIsLoggedIn(false);
    setCurrentUser(null);
    localStorage.removeItem('admin_auth');
    localStorage.removeItem('authToken');
    localStorage.removeItem('user');
  };

  return (
    <AuthContext.Provider value={{ isAdmin, isLoggedIn, currentUser, login, userLogin, logout }}>
      {children}
    </AuthContext.Provider>
  );
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) throw new Error('useAuth must be used within AuthProvider');
  return context;
};