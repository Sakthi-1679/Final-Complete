import React, { useState, useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { buildApiUrl } from '../../constants';

interface EngagementMetrics {
  total_events: number;
  unique_users: number;
  total_watch_duration: number;
  engagement_rate: number;
  avg_rating: number;
  like_rate: number;
}

interface RecommendationQuality {
  total_recommendations: number;
  watched_rate: number;
  high_rating_rate: number;
  quality_score: number;
}

interface PipelineMetrics {
  engagement: EngagementMetrics;
  mood_patterns: Record<string, any>;
  recommendation_quality: RecommendationQuality;
}

interface PipelineStatus {
  is_running: boolean;
  last_retrain: string | null;
  retrain_count: number;
  check_interval_seconds: number;
}

const AIPipelineDashboard: React.FC = () => {
  const navigate = useNavigate();
  const [metrics, setMetrics] = useState<PipelineMetrics | null>(null);
  const [status, setStatus] = useState<PipelineStatus | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [autoRefresh, setAutoRefresh] = useState(false);

  const fetchMetrics = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildApiUrl('/pipeline/metrics'));
      const data = await response.json();
      if (data.status === 'success') {
        setMetrics(data.metrics);
      } else {
        setError(data.error || 'Failed to fetch metrics');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  };

  const fetchStatus = async () => {
    try {
      const response = await fetch(buildApiUrl('/pipeline/status'));
      const data = await response.json();
      if (data.status === 'success') {
        setStatus(data.pipeline);
      }
    } catch (err) {
      console.error('Failed to fetch status:', err);
    }
  };

  const triggerPipelineRun = async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(buildApiUrl('/pipeline/run'), {
        method: 'POST',
      });
      const data = await response.json();
      if (data.status === 'success') {
        // Refresh metrics after pipeline run
        await fetchMetrics();
        await fetchStatus();
      } else {
        setError(data.error || 'Failed to run pipeline');
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Network error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    fetchMetrics();
    fetchStatus();
  }, []);

  useEffect(() => {
    if (!autoRefresh) return;

    const interval = setInterval(() => {
      fetchMetrics();
      fetchStatus();
    }, 30000); // Refresh every 30 seconds

    return () => clearInterval(interval);
  }, [autoRefresh]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-black via-gray-900 to-black p-4 md:p-8">
      {/* Header */}
      <div className="mb-8">
        <button
          onClick={() => navigate('/admin/dashboard')}
          className="mb-4 flex items-center gap-2 px-4 py-2 bg-gray-800 hover:bg-gray-700 text-gray-300 hover:text-white rounded-lg transition-colors text-sm font-medium"
        >
          <i className="fas fa-arrow-left"></i>
          Back to Admin Dashboard
        </button>
        <h1 className="text-4xl font-bold text-white mb-2">🤖 AI Pipeline Dashboard</h1>
        <p className="text-gray-400">Production-Grade Continuous Learning & Monitoring</p>
      </div>

      {/* Error Message */}
      {error && (
        <div className="bg-red-500/20 border border-red-500 text-red-200 px-4 py-3 rounded-lg mb-6">
          <i className="fas fa-exclamation-circle mr-2"></i>
          {error}
        </div>
      )}

      {/* Controls */}
      <div className="flex gap-4 mb-8 flex-wrap">
        <button
          onClick={fetchMetrics}
          disabled={loading}
          className="px-6 py-2 bg-blue-600 hover:bg-blue-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50"
        >
          <i className="fas fa-sync mr-2"></i>
          {loading ? 'Loading...' : 'Refresh Metrics'}
        </button>
        <button
          onClick={triggerPipelineRun}
          disabled={loading}
          className="px-6 py-2 bg-green-600 hover:bg-green-700 text-white rounded-lg font-bold transition-colors disabled:opacity-50"
        >
          <i className="fas fa-play mr-2"></i>
          {loading ? 'Running...' : 'Run Pipeline'}
        </button>
        <label className="flex items-center gap-2 px-6 py-2 bg-purple-600 hover:bg-purple-700 text-white rounded-lg font-bold cursor-pointer transition-colors">
          <input
            type="checkbox"
            checked={autoRefresh}
            onChange={(e) => setAutoRefresh(e.target.checked)}
            className="w-4 h-4"
          />
          Auto Refresh (30s)
        </label>
      </div>

      {/* Pipeline Status Card */}
      {status && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6 mb-8">
          <h2 className="text-2xl font-bold text-white mb-4">
            <i className="fas fa-heartbeat text-green-400 mr-2"></i>Pipeline Status
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
            <div className="bg-gray-700/50 p-4 rounded">
              <p className="text-gray-400 text-sm">Status</p>
              <p className="text-2xl font-bold text-green-400">
                {status.is_running ? 'RUNNING' : 'IDLE'}
              </p>
            </div>
            <div className="bg-gray-700/50 p-4 rounded">
              <p className="text-gray-400 text-sm">Retrains Completed</p>
              <p className="text-2xl font-bold text-blue-400">{status.retrain_count}</p>
            </div>
            <div className="bg-gray-700/50 p-4 rounded">
              <p className="text-gray-400 text-sm">Last Retrain</p>
              <p className="text-sm text-gray-300 font-mono">
                {status.last_retrain ? new Date(status.last_retrain).toLocaleString() : 'Never'}
              </p>
            </div>
            <div className="bg-gray-700/50 p-4 rounded">
              <p className="text-gray-400 text-sm">Check Interval</p>
              <p className="text-xl font-bold text-yellow-400">{status.check_interval_seconds / 3600}h</p>
            </div>
          </div>
        </div>
      )}

      {/* Engagement Metrics */}
      {metrics && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
          {/* Engagement Card */}
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-white mb-4">
              <i className="fas fa-chart-line text-blue-400 mr-2"></i>Engagement Metrics
            </h2>
            <div className="space-y-4">
              <MetricRow
                label="Total Events"
                value={metrics.engagement.total_events}
                icon="fa-events"
              />
              <MetricRow
                label="Unique Users"
                value={metrics.engagement.unique_users}
                icon="fa-users"
              />
              <MetricRow
                label="Engagement Rate"
                value={`${(metrics.engagement.engagement_rate * 100).toFixed(1)}%`}
                icon="fa-percentage"
                color="text-green-400"
              />
              <MetricRow
                label="Avg Rating"
                value={`${metrics.engagement.avg_rating.toFixed(2)}/5`}
                icon="fa-star"
                color="text-yellow-400"
              />
              <MetricRow
                label="Like Rate"
                value={`${(metrics.engagement.like_rate * 100).toFixed(1)}%`}
                icon="fa-thumbs-up"
                color="text-red-400"
              />
            </div>
          </div>

          {/* Recommendation Quality Card */}
          <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
            <h2 className="text-2xl font-bold text-white mb-4">
              <i className="fas fa-brain text-purple-400 mr-2"></i>Recommendation Quality
            </h2>
            <div className="space-y-4">
              <MetricRow
                label="Total Recommendations"
                value={metrics.recommendation_quality.total_recommendations}
                icon="fa-film"
              />
              <MetricRow
                label="Watched Rate"
                value={`${(metrics.recommendation_quality.watched_rate * 100).toFixed(1)}%`}
                icon="fa-play-circle"
                color="text-blue-400"
              />
              <MetricRow
                label="High Rating Rate"
                value={`${(metrics.recommendation_quality.high_rating_rate * 100).toFixed(1)}%`}
                icon="fa-award"
                color="text-yellow-400"
              />
              <QualityScoreMeter
                score={metrics.recommendation_quality.quality_score}
              />
            </div>
          </div>
        </div>
      )}

      {/* Mood Patterns */}
      {metrics && Object.keys(metrics.mood_patterns).length > 0 && (
        <div className="bg-gray-800/50 border border-gray-700 rounded-lg p-6">
          <h2 className="text-2xl font-bold text-white mb-4">
            <i className="fas fa-smile text-pink-400 mr-2"></i>Mood Analysis
          </h2>
          <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-4">
            {Object.entries(metrics.mood_patterns).map(([mood, data]: [string, any]) => (
              <div key={mood} className="bg-gray-700/50 p-4 rounded">
                <p className="text-gray-400 text-sm capitalize mb-2">{mood}</p>
                <p className="text-2xl font-bold text-white mb-1">{data.count}</p>
                <p className="text-sm text-gray-300">Avg: {data.avg_rating.toFixed(2)}/5</p>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Loading State */}
      {loading && !metrics && (
        <div className="flex justify-center items-center py-12">
          <div className="animate-spin rounded-full h-12 w-12 border-t-2 border-b-2 border-blue-500"></div>
        </div>
      )}
    </div>
  );
};

interface MetricRowProps {
  label: string;
  value: string | number;
  icon?: string;
  color?: string;
}

const MetricRow: React.FC<MetricRowProps> = ({ label, value, icon, color = 'text-gray-300' }) => (
  <div className="flex justify-between items-center py-2 border-b border-gray-700/50">
    <p className="text-gray-400">{label}</p>
    <p className={`text-lg font-bold ${color}`}>{value}</p>
  </div>
);

interface QualityScoreMeterProps {
  score: number;
}

const QualityScoreMeter: React.FC<QualityScoreMeterProps> = ({ score }) => {
  const percentage = score * 100;
  const getColor = () => {
    if (percentage >= 70) return 'bg-green-500';
    if (percentage >= 50) return 'bg-yellow-500';
    return 'bg-red-500';
  };

  return (
    <div className="py-2">
      <div className="flex justify-between items-center mb-2">
        <p className="text-gray-400">Quality Score</p>
        <p className="font-bold text-lg">{percentage.toFixed(1)}%</p>
      </div>
      <div className="w-full bg-gray-700 rounded-full h-3 overflow-hidden">
        <div
          className={`h-full rounded-full transition-all ${getColor()}`}
          style={{ width: `${percentage}%` }}
        ></div>
      </div>
    </div>
  );
};

export default AIPipelineDashboard;
