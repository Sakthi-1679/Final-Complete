
import React from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import Layout from './components/Layout';
import Home from './pages/Home';
import MovieDetail from './pages/MovieDetail';
import Player from './pages/Player';
import Search from './pages/Search';
import Login from './pages/Login';
import Signup from './pages/Signup';
import Subscription from './pages/Subscription';
import AdminDashboard from './pages/admin/AdminDashboard';
import MovieEditor from './pages/admin/MovieEditor';
import AIPipelineDashboard from './pages/admin/AIPipelineDashboard';

// Error Boundary Component
class ErrorBoundary extends React.Component<
  { children: React.ReactNode },
  { hasError: boolean; error: Error | null }
> {
  declare state: { hasError: boolean; error: Error | null };
  declare props: { children: React.ReactNode };

  constructor(props: { children: React.ReactNode }) {
    super(props);
    this.state = { hasError: false, error: null };
  }

  static getDerivedStateFromError(error: Error) {
    return { hasError: true, error };
  }

  componentDidCatch(error: Error, errorInfo: React.ErrorInfo) {
    console.error('Error caught by boundary:', error, errorInfo);
  }

  render() {
    if (this.state.hasError) {
      return (
        <div style={{ padding: '20px', color: 'red', fontFamily: 'monospace' }}>
          <h1>🚨 Application Error</h1>
          <pre>{this.state.error?.toString()}</pre>
        </div>
      );
    }

    return this.props.children;
  }
}

// Protected Route Component — reads from reactive AuthContext (not raw localStorage)
interface ProtectedRouteProps {
  children: React.ReactNode;
  adminOnly?: boolean;
}

const ProtectedRoute: React.FC<ProtectedRouteProps> = ({ children, adminOnly = false }) => {
  const { isLoggedIn, currentUser } = useAuth();

  if (!isLoggedIn) {
    return <Navigate to="/login" replace />;
  }

  if (adminOnly && (!currentUser || (currentUser.role !== 'admin' && currentUser.role !== 'manager'))) {
    return <Navigate to="/" replace />;
  }

  return <>{children}</>;
};

// Inner component that consumes AuthContext and renders the reactive route tree
const AppRoutes: React.FC = () => {
  const { isLoggedIn, currentUser } = useAuth();
  const isAdminUser = isLoggedIn && currentUser &&
    (currentUser.role === 'admin' || currentUser.role === 'manager');

  return (
    <Routes>
      {/* Always-accessible auth routes */}
      <Route path="/login" element={<Login />} />
      <Route path="/signup" element={<Signup />} />

      {isLoggedIn ? (
        <>
          <Route path="/" element={<Layout />}>
            <Route index element={<Home />} />
            <Route path="movie/:id" element={<MovieDetail />} />
            <Route path="search" element={<Search />} />
          </Route>

          <Route path="/watch/:id" element={<Player />} />
          <Route path="/subscription" element={<Subscription />} />

          {/* Admin routes — only mounted when user has admin/manager role */}
          {isAdminUser && (
            <>
              <Route path="/admin/dashboard"
                element={<ProtectedRoute adminOnly><AdminDashboard /></ProtectedRoute>} />
              <Route path="/admin/movie-editor"
                element={<ProtectedRoute adminOnly><MovieEditor /></ProtectedRoute>} />
              <Route path="/admin/edit/:id"
                element={<ProtectedRoute adminOnly><MovieEditor /></ProtectedRoute>} />
              <Route path="/admin/pipeline"
                element={<ProtectedRoute adminOnly><AIPipelineDashboard /></ProtectedRoute>} />
            </>
          )}

          <Route path="*" element={<Navigate to="/" replace />} />
        </>
      ) : (
        <>
          <Route path="/" element={<Navigate to="/login" replace />} />
          <Route path="*" element={<Navigate to="/login" replace />} />
        </>
      )}
    </Routes>
  );
};

const App: React.FC = () => {
  return (
    <ErrorBoundary>
      <AuthProvider>
        <Router>
          <AppRoutes />
        </Router>
      </AuthProvider>
    </ErrorBoundary>
  );
};

export default App;
