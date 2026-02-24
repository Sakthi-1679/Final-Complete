/**
 * InsightsDashboard.tsx
 * ─────────────────────
 * Rich analytics panel for the Admin Dashboard.
 * Uses Recharts for all visualisations.
 *
 * Data sources
 *  • movies  – from backend API (views, genres, category, year)
 *  • users   – from backend API (subscription, role, created_at)
 *  • localStorage streamflix_system_logs  – event timeline
 *  • localStorage streamflix_feedback_*   – per-movie likes + star ratings
 */
import React, { useMemo, useState } from 'react';
import {
  BarChart, Bar, XAxis, YAxis, Tooltip, ResponsiveContainer, CartesianGrid,
  PieChart, Pie, Cell, Legend, AreaChart, Area, LineChart, Line, RadarChart,
  PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar,
} from 'recharts';
import { Movie } from '../../types';

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

interface Props {
  movies: Movie[];
  users: User[];
}

type FeedbackEntry = { liked: boolean | null; rating: number };

// ─── Colour palettes ─────────────────────────────────────────────────────────
const RED    = '#e50914';
const ACCENT = '#f59e0b';
const TEAL   = '#06b6d4';
const GREEN  = '#10b981';
const PURPLE = '#8b5cf6';
const PINK   = '#ec4899';
const INDIGO = '#6366f1';
const ORANGE = '#f97316';

const PIE_COLORS = [RED, ACCENT, TEAL, GREEN, PURPLE, PINK, INDIGO, ORANGE,
  '#84cc16','#14b8a6','#a855f7','#f43f5e'];

// ─── Helpers ─────────────────────────────────────────────────────────────────
const fmt = (n: number) =>
  n >= 1_000_000 ? (n / 1_000_000).toFixed(1) + 'M'
  : n >= 1_000   ? (n / 1_000).toFixed(1) + 'K'
  : String(n);

type ChartTooltipProps = { active?: boolean; payload?: any[]; label?: any };

const DarkTooltip: React.FC<ChartTooltipProps> = ({ active, payload, label }) => {
  if (!active || !payload?.length) return null;
  return (
    <div style={{
      background: '#18181b', border: '1px solid #3f3f46',
      borderRadius: 8, padding: '8px 12px', fontSize: 13,
    }}>
      {label !== undefined && <p style={{ color: '#a1a1aa', marginBottom: 4 }}>{label}</p>}
      {payload.map((p: any, i: number) => (
        <p key={i} style={{ color: p.color || '#fff', margin: 0 }}>
          {p.name}: <strong>{typeof p.value === 'number' ? fmt(p.value) : p.value}</strong>
        </p>
      ))}
    </div>
  );
};

// ─── KPI card ─────────────────────────────────────────────────────────────────
interface KPIProps {
  label: string; value: string | number; sub?: string;
  icon: string; color: string;
}
const KPI: React.FC<KPIProps> = ({ label, value, sub, icon, color }) => (
  <div style={{
    background: '#18181b', border: `1px solid ${color}44`,
    borderRadius: 12, padding: '18px 22px', minWidth: 150,
    display: 'flex', gap: 14, alignItems: 'center', flex: 1,
  }}>
    <span style={{
      fontSize: 28, background: `${color}22`,
      borderRadius: 10, width: 52, height: 52,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
    }}>{icon}</span>
    <div>
      <p style={{ color: '#a1a1aa', fontSize: 12, margin: 0, fontWeight: 600,
        textTransform: 'uppercase', letterSpacing: 1 }}>{label}</p>
      <p style={{ color: '#fff', fontSize: 22, fontWeight: 700, margin: '2px 0 0' }}>
        {typeof value === 'number' ? fmt(value) : value}
      </p>
      {sub && <p style={{ color: color, fontSize: 11, margin: 0 }}>{sub}</p>}
    </div>
  </div>
);

// ─── Section wrapper ──────────────────────────────────────────────────────────
interface SectionProps { title: string; sub?: string; children: React.ReactNode; span?: number; }
const Section: React.FC<SectionProps> = ({ title, sub, children, span = 1 }) => (
  <div style={{
    background: '#18181b', border: '1px solid #27272a', borderRadius: 14,
    padding: '22px 24px', gridColumn: `span ${span}`,
  }}>
    <div style={{ marginBottom: 16 }}>
      <h3 style={{ color: '#fff', margin: 0, fontSize: 15, fontWeight: 700 }}>{title}</h3>
      {sub && <p style={{ color: '#71717a', margin: '2px 0 0', fontSize: 12 }}>{sub}</p>}
    </div>
    {children}
  </div>
);

// ─── Main component ───────────────────────────────────────────────────────────
const InsightsDashboard: React.FC<Props> = ({ movies, users }) => {
  const [trendingLimit, setTrendingLimit] = useState(10);

  /* ── derive feedback from localStorage ──────────────────────── */
  const feedbackMap = useMemo<Record<string, FeedbackEntry>>(() => {
    const map: Record<string, FeedbackEntry> = {};
    for (let i = 0; i < localStorage.length; i++) {
      const key = localStorage.key(i);
      if (key?.startsWith('streamflix_feedback_')) {
        const id = key.replace('streamflix_feedback_', '');
        try {
          const parsed = JSON.parse(localStorage.getItem(key) || '{}') as { liked?: boolean | null; rating?: number };
          map[id] = { liked: parsed.liked ?? null, rating: parsed.rating ?? 0 };
        } catch {}
      }
    }
    return map;
  }, []);

  /* ── system event logs ───────────────────────────────────────── */
  const eventLogs: any[] = useMemo(() => {
    try { return JSON.parse(localStorage.getItem('streamflix_system_logs') || '[]'); }
    catch { return []; }
  }, []);

  // ── 1. Top Trending (by views) ────────────────────────────────
  const trendingData = useMemo(() =>
    [...movies]
      .sort((a, b) => (b.views || 0) - (a.views || 0))
      .slice(0, trendingLimit)
      .map(m => ({ name: m.title.length > 22 ? m.title.slice(0, 20) + '…' : m.title, views: m.views || 0 }))
  , [movies, trendingLimit]);

  // ── 2. Most Liked movies ──────────────────────────────────────
  const likedData = useMemo(() => {
    const result: { name: string; likes: number; dislikes: number }[] = [];
    movies.forEach(m => {
      const fb = feedbackMap[m.id];
      if (fb?.liked === true)  result.push({ name: m.title.slice(0, 20) + (m.title.length > 20 ? '…' : ''), likes: 1, dislikes: 0 });
      if (fb?.liked === false) result.push({ name: m.title.slice(0, 20) + (m.title.length > 20 ? '…' : ''), likes: 0, dislikes: 1 });
    });
    return result.slice(0, 10);
  }, [movies, feedbackMap]);

  // ── 3. Star Ratings distribution ─────────────────────────────
  const ratingDist = useMemo(() => {
    const counts = [0, 0, 0, 0, 0];
    (Object.values(feedbackMap) as FeedbackEntry[]).forEach(fb => {
      if (fb.rating >= 1 && fb.rating <= 5) counts[fb.rating - 1]++;
    });
    return [1,2,3,4,5].map((s, i) => ({ star: `${s}★`, count: counts[i] }));
  }, [feedbackMap]);

  // ── 4. Top Rated movies (avg star from feedback) ──────────────
  const topRatedMovies = useMemo(() =>
    movies
      .filter(m => feedbackMap[m.id]?.rating > 0)
      .map(m => ({ name: m.title.slice(0, 22) + (m.title.length > 22 ? '…' : ''), rating: feedbackMap[m.id].rating }))
      .sort((a, b) => b.rating - a.rating)
      .slice(0, 8)
  , [movies, feedbackMap]);

  // ── 5. Genre Distribution ─────────────────────────────────────
  const genreData = useMemo(() => {
    const map: Record<string, number> = {};
    movies.forEach(m => m.genres.forEach(g => { map[g] = (map[g] || 0) + 1; }));
    return Object.entries(map).sort(([, a], [, b]) => b - a).slice(0, 12)
      .map(([name, value]) => ({ name, value }));
  }, [movies]);

  // ── 6. Genre vs Views ────────────────────────────────────────
  const genreViewsData = useMemo(() => {
    const map: Record<string, number> = {};
    movies.forEach(m => m.genres.forEach(g => { map[g] = (map[g] || 0) + (m.views || 0); }));
    return Object.entries(map).sort(([, a], [, b]) => b - a).slice(0, 10)
      .map(([genre, views]) => ({ genre, views }));
  }, [movies]);

  // ── 7. Category Distribution ─────────────────────────────────
  const categoryData = useMemo(() => {
    const map: Record<string, number> = {};
    movies.forEach(m => { map[m.category] = (map[m.category] || 0) + 1; });
    return Object.entries(map).map(([name, value]) => ({ name: name.replace('_', ' '), value }));
  }, [movies]);

  // ── 8. Movies Added Per Year ─────────────────────────────────
  const moviesPerYear = useMemo(() => {
    const map: Record<number, number> = {};
    movies.forEach(m => { map[m.year] = (map[m.year] || 0) + 1; });
    return Object.entries(map).sort(([a], [b]) => Number(a) - Number(b))
      .map(([year, count]) => ({ year, count }));
  }, [movies]);

  // ── 9. User Subscription Breakdown ──────────────────────────
  const subscriptionData = useMemo(() => {
    const map: Record<string, number> = {};
    users.forEach(u => { map[u.subscription || 'free'] = (map[u.subscription || 'free'] || 0) + 1; });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [users]);

  // ── 10. User Roles ───────────────────────────────────────────
  const roleData = useMemo(() => {
    const map: Record<string, number> = {};
    users.forEach(u => { map[u.role || 'user'] = (map[u.role || 'user'] || 0) + 1; });
    return Object.entries(map).map(([name, value]) => ({ name, value }));
  }, [users]);

  // ── 11. User Signups Per Month ────────────────────────────────
  const signupsPerMonth = useMemo(() => {
    const map: Record<string, number> = {};
    users.forEach(u => {
      if (u.created_at) {
        const month = u.created_at.slice(0, 7); // "YYYY-MM"
        map[month] = (map[month] || 0) + 1;
      }
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b))
      .map(([month, count]) => ({ month, count }));
  }, [users]);

  // ── 12. Event log timeline (by day) ──────────────────────────
  const eventTimeline = useMemo(() => {
    const map: Record<string, number> = {};
    eventLogs.forEach((e: any) => {
      if (e.timestamp) {
        const day = String(e.timestamp).slice(0, 10);
        map[day] = (map[day] || 0) + 1;
      }
    });
    return Object.entries(map).sort(([a], [b]) => a.localeCompare(b)).slice(-30)
      .map(([date, events]) => ({ date: date.slice(5), events }));
  }, [eventLogs]);

  // ── 13. Mood distribution from logs ──────────────────────────
  const moodData = useMemo(() => {
    const map: Record<string, number> = {};
    eventLogs.forEach((e: any) => {
      const mood = e.detected_mood || e.mood;
      if (mood) { map[mood] = (map[mood] || 0) + 1; }
    });
    return Object.entries(map).sort(([, a], [, b]) => b - a)
      .map(([mood, count]) => ({ mood, count }));
  }, [eventLogs]);

  // ── 14. Top genres by interaction / likes ─────────────────────
  const genreLikesData = useMemo(() => {
    const map: Record<string, number> = {};
    movies.forEach(m => {
      const fb = feedbackMap[m.id];
      if (fb?.liked === true) {
        m.genres.forEach(g => { map[g] = (map[g] || 0) + 1; });
      }
    });
    return Object.entries(map).sort(([, a], [, b]) => b - a).slice(0, 8)
      .map(([genre, likes]) => ({ genre, likes }));
  }, [movies, feedbackMap]);

  // ── 15. Radar: genre profile ───────────────────────────────────
  const radarData = useMemo(() => {
    const top8 = genreData.slice(0, 8);
    const maxCount = Math.max(...top8.map(g => g.value), 1);
    return top8.map(g => ({
      genre: g.name,
      score: Math.round((g.value / maxCount) * 100),
    }));
  }, [genreData]);

  // ── derived KPIs ──────────────────────────────────────────────
  const totalViews = useMemo(() => movies.reduce((s, m) => s + (m.views || 0), 0), [movies]);
  const totalInteractions = useMemo(() => {
    // Count system log events + any feedback entries that haven't produced a log entry yet
    const logCount = eventLogs.length;
    const feedbackCount = Object.keys(feedbackMap).length;
    return logCount || feedbackCount; // prefer log events; fall back to feedback keys
  }, [eventLogs, feedbackMap]);
  const totalLikes = (Object.values(feedbackMap) as FeedbackEntry[]).filter(f => f.liked === true).length;
  const avgRating = useMemo(() => {
    const rated = (Object.values(feedbackMap) as FeedbackEntry[]).filter(f => f.rating > 0);
    if (!rated.length) return 0;
    return (rated.reduce((s, f) => s + f.rating, 0) / rated.length).toFixed(1);
  }, [feedbackMap]);

  const topGenre = genreData[0]?.name || '—';

  const chartH = 240;
  const gridStyle: React.CSSProperties = {
    display: 'grid',
    gap: 16,
    gridTemplateColumns: 'repeat(auto-fill, minmax(420px, 1fr))',
  };

  const TICK  = { fill: '#71717a', fontSize: 11 };
  const GRID  = { stroke: '#27272a' };

  return (
    <div style={{ padding: '8px 0', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── KPI row ──────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap' }}>
        <KPI label="Total Movies"  value={movies.length}        icon="🎬" color={RED}    sub={`${categoryData.find(c=>c.name==='trending')?.value ?? 0} trending`} />
        <KPI label="Total Users"   value={users.length}         icon="👥" color={TEAL}   sub={`${users.filter(u=>u.subscription==='premium').length} premium`} />
        <KPI label="Total Views"   value={totalViews}           icon="👁️" color={GREEN}  sub="across all titles" />
        <KPI label="Interactions"  value={totalInteractions}    icon="🖱️" color={PURPLE} sub="logged events" />
        <KPI label="Total Likes"   value={totalLikes}           icon="👍" color={ACCENT} sub={`${(Object.values(feedbackMap) as FeedbackEntry[]).filter(f=>f.liked===false).length} dislikes`} />
        <KPI label="Avg Rating"    value={avgRating || '—'}     icon="⭐" color={PINK}   sub={`${(Object.values(feedbackMap) as FeedbackEntry[]).filter(f=>f.rating>0).length} ratings`} />
        <KPI label="Top Genre"     value={topGenre}             icon="🏷️" color={INDIGO} sub={`${genreData[0]?.value ?? 0} movies`} />
      </div>

      {/* ── Row 1 ────────────────────────────────────────────── */}
      <div style={gridStyle}>

        {/* Trending Movies */}
        <Section
          title="🔥 Trending Movies"
          sub="Sorted by total view count"
          span={2}
        >
          <div style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: 8 }}>
            {[5,10,20].map(n => (
              <button
                key={n}
                onClick={() => setTrendingLimit(n)}
                style={{
                  marginLeft: 6, padding: '2px 10px', fontSize: 11, borderRadius: 6, cursor: 'pointer',
                  background: trendingLimit === n ? RED : '#27272a',
                  color: '#fff', border: 'none',
                }}
              >{n}</button>
            ))}
          </div>
          <ResponsiveContainer width="100%" height={chartH}>
            <BarChart data={trendingData} margin={{ left: 0, right: 8 }}>
              <CartesianGrid strokeDasharray="3 3" {...GRID} />
              <XAxis dataKey="name" tick={TICK} angle={-30} textAnchor="end" height={60} />
              <YAxis tick={TICK} tickFormatter={fmt} />
              <Tooltip content={<DarkTooltip />} />
              <Bar dataKey="views" name="Views" fill={RED} radius={[4,4,0,0]}>
                {trendingData.map((_, i) => <Cell key={i} fill={i === 0 ? ACCENT : RED} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Section>

        {/* Category Distribution */}
        <Section title="📂 Category Distribution" sub="Movies per category">
          <ResponsiveContainer width="100%" height={chartH}>
            <PieChart>
              <Pie data={categoryData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={90} innerRadius={45} paddingAngle={3}>
                {categoryData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ color: '#a1a1aa', fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Section>

      </div>

      {/* ── Row 2 ────────────────────────────────────────────── */}
      <div style={gridStyle}>

        {/* Genre Distribution donut */}
        <Section title="🎭 Genre Distribution" sub="Number of movies per genre">
          <ResponsiveContainer width="100%" height={chartH + 20}>
            <PieChart>
              <Pie data={genreData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={95} innerRadius={50} paddingAngle={2}
                label={({ name, percent }) => `${name} ${(percent*100).toFixed(0)}%`}
                labelLine={false}
              >
                {genreData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip content={<DarkTooltip />} />
            </PieChart>
          </ResponsiveContainer>
        </Section>

        {/* Genre vs Views */}
        <Section title="📊 Genre vs Total Views" sub="Which genres get watched the most">
          <ResponsiveContainer width="100%" height={chartH}>
            <BarChart data={genreViewsData} layout="vertical" margin={{ left: 4 }}>
              <CartesianGrid strokeDasharray="3 3" {...GRID} />
              <XAxis type="number" tick={TICK} tickFormatter={fmt} />
              <YAxis type="category" dataKey="genre" tick={TICK} width={72} />
              <Tooltip content={<DarkTooltip />} />
              <Bar dataKey="views" name="Views" fill={TEAL} radius={[0,4,4,0]}>
                {genreViewsData.map((_, i) => (
                  <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Section>

        {/* Genre radar */}
        <Section title="🕸️ Genre Content Radar" sub="Relative volume of each genre">
          <ResponsiveContainer width="100%" height={chartH}>
            <RadarChart data={radarData} cx="50%" cy="50%" outerRadius={90}>
              <PolarGrid stroke="#27272a" />
              <PolarAngleAxis dataKey="genre" tick={{ fill: '#a1a1aa', fontSize: 11 }} />
              <PolarRadiusAxis angle={30} tick={{ fill: '#52525b', fontSize: 9 }} domain={[0, 100]} />
              <Radar name="Score" dataKey="score" stroke={PURPLE} fill={PURPLE} fillOpacity={0.35} />
              <Tooltip content={<DarkTooltip />} />
            </RadarChart>
          </ResponsiveContainer>
        </Section>

      </div>

      {/* ── Row 3 — User insights ─────────────────────────────── */}
      <div style={gridStyle}>

        {/* Subscription breakdown */}
        <Section title="💳 Subscription Plans" sub="User breakdown by plan">
          <ResponsiveContainer width="100%" height={chartH}>
            <PieChart>
              <Pie data={subscriptionData} dataKey="value" nameKey="name"
                cx="50%" cy="50%" outerRadius={90} paddingAngle={4}
                label={({ name, value }) => `${name}: ${value}`}
              >
                {subscriptionData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Pie>
              <Tooltip content={<DarkTooltip />} />
              <Legend wrapperStyle={{ color: '#a1a1aa', fontSize: 12 }} />
            </PieChart>
          </ResponsiveContainer>
        </Section>

        {/* User roles */}
        <Section title="🛡️ User Roles" sub="Admins, managers, and regular users">
          <ResponsiveContainer width="100%" height={chartH}>
            <BarChart data={roleData}>
              <CartesianGrid strokeDasharray="3 3" {...GRID} />
              <XAxis dataKey="name" tick={TICK} />
              <YAxis tick={TICK} allowDecimals={false} />
              <Tooltip content={<DarkTooltip />} />
              <Bar dataKey="value" name="Users" radius={[6,6,0,0]}>
                {roleData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Section>

        {/* User signups per month */}
        <Section title="📈 User Growth" sub="New signups per month" span={2}>
          {signupsPerMonth.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <AreaChart data={signupsPerMonth}>
                <defs>
                  <linearGradient id="colGrowth" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={TEAL} stopOpacity={0.35} />
                    <stop offset="95%" stopColor={TEAL} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis dataKey="month" tick={TICK} />
                <YAxis tick={TICK} allowDecimals={false} />
                <Tooltip content={<DarkTooltip />} />
                <Area type="monotone" dataKey="count" name="New users"
                  stroke={TEAL} fill="url(#colGrowth)" strokeWidth={2} dot={{ r: 3, fill: TEAL }} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No signup data yet" />
          )}
        </Section>

      </div>

      {/* ── Row 4 — Interaction / feedback insights ───────────── */}
      <div style={gridStyle}>

        {/* Event timeline */}
        <Section title="🖱️ Activity Timeline" sub="Logged events (last 30 days)" span={2}>
          {eventTimeline.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <AreaChart data={eventTimeline}>
                <defs>
                  <linearGradient id="colEvent" x1="0" y1="0" x2="0" y2="1">
                    <stop offset="5%"  stopColor={PURPLE} stopOpacity={0.4} />
                    <stop offset="95%" stopColor={PURPLE} stopOpacity={0} />
                  </linearGradient>
                </defs>
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis dataKey="date" tick={TICK} />
                <YAxis tick={TICK} allowDecimals={false} />
                <Tooltip content={<DarkTooltip />} />
                <Area type="monotone" dataKey="events" name="Events"
                  stroke={PURPLE} fill="url(#colEvent)" strokeWidth={2} />
              </AreaChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No event logs yet — interaction data will appear here once users browse the platform." />
          )}
        </Section>

        {/* Mood distribution */}
        <Section title="😊 Mood Distribution" sub="Detected moods from watch sessions">
          {moodData.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <BarChart data={moodData}>
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis dataKey="mood" tick={TICK} />
                <YAxis tick={TICK} allowDecimals={false} />
                <Tooltip content={<DarkTooltip />} />
                <Bar dataKey="count" name="Count" radius={[4,4,0,0]}>
                  {moodData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No mood data logged yet." />
          )}
        </Section>

      </div>

      {/* ── Row 5 — Like / Rating insights ───────────────────── */}
      <div style={gridStyle}>

        {/* Most liked movies */}
        <Section title="👍 User Likes & Dislikes" sub="Movies users have reacted to">
          {likedData.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <BarChart data={likedData} margin={{ left: 0 }}>
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis dataKey="name" tick={TICK} angle={-25} textAnchor="end" height={55} />
                <YAxis tick={TICK} allowDecimals={false} />
                <Tooltip content={<DarkTooltip />} />
                <Legend wrapperStyle={{ color: '#a1a1aa', fontSize: 12 }} />
                <Bar dataKey="likes"    name="Likes"    fill={GREEN}  radius={[4,4,0,0]} />
                <Bar dataKey="dislikes" name="Dislikes" fill={RED}    radius={[4,4,0,0]} />
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No likes/dislikes recorded yet. Users can like movies from the Player or Movie Detail page." />
          )}
        </Section>

        {/* Rating distribution */}
        <Section title="⭐ Rating Distribution" sub="Star ratings given by users (1–5)">
          <ResponsiveContainer width="100%" height={chartH}>
            <BarChart data={ratingDist}>
              <CartesianGrid strokeDasharray="3 3" {...GRID} />
              <XAxis dataKey="star" tick={TICK} />
              <YAxis tick={TICK} allowDecimals={false} />
              <Tooltip content={<DarkTooltip />} />
              <Bar dataKey="count" name="Count" radius={[5,5,0,0]}>
                {ratingDist.map((d, i) => (
                  <Cell key={i}
                    fill={d.count === Math.max(...ratingDist.map(r => r.count)) ? ACCENT : `${ACCENT}66`} />
                ))}
              </Bar>
            </BarChart>
          </ResponsiveContainer>
        </Section>

        {/* Top rated movies */}
        <Section title="🏆 Top Rated by Users" sub="Movies with highest star ratings">
          {topRatedMovies.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <BarChart data={topRatedMovies} layout="vertical">
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis type="number" domain={[0, 5]} ticks={[1,2,3,4,5]} tick={TICK} />
                <YAxis type="category" dataKey="name" tick={TICK} width={110} />
                <Tooltip content={<DarkTooltip />} />
                <Bar dataKey="rating" name="Rating" radius={[0,5,5,0]}>
                  {topRatedMovies.map((_, i) => <Cell key={i} fill={i === 0 ? ACCENT : `${ACCENT}99`} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No star ratings yet. Users can rate movies during playback." />
          )}
        </Section>

      </div>

      {/* ── Row 6 — Genre likes + Movies per Year ─────────────── */}
      <div style={gridStyle}>

        {/* Genres liked */}
        <Section title="❤️ Most Liked Genres" sub="Genres users like the most">
          {genreLikesData.length > 0 ? (
            <ResponsiveContainer width="100%" height={chartH}>
              <BarChart data={genreLikesData}>
                <CartesianGrid strokeDasharray="3 3" {...GRID} />
                <XAxis dataKey="genre" tick={TICK} />
                <YAxis tick={TICK} allowDecimals={false} />
                <Tooltip content={<DarkTooltip />} />
                <Bar dataKey="likes" name="Likes" radius={[5,5,0,0]}>
                  {genreLikesData.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          ) : (
            <EmptyState msg="No genre preference data yet." />
          )}
        </Section>

        {/* Movies per year */}
        <Section title="📅 Library by Release Year" sub="How many movies per year in the catalogue">
          <ResponsiveContainer width="100%" height={chartH}>
            <LineChart data={moviesPerYear}>
              <CartesianGrid strokeDasharray="3 3" {...GRID} />
              <XAxis dataKey="year" tick={TICK} />
              <YAxis tick={TICK} allowDecimals={false} />
              <Tooltip content={<DarkTooltip />} />
              <Line type="monotone" dataKey="count" name="Movies"
                stroke={GREEN} strokeWidth={2} dot={{ r: 3, fill: GREEN }} />
            </LineChart>
          </ResponsiveContainer>
        </Section>

      </div>

      {/* ── Raw user table ────────────────────────────────────── */}
      <Section title="👥 All Users" sub={`${users.length} registered users`} span={3}>
        <div style={{ overflowX: 'auto' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
            <thead>
              <tr style={{ borderBottom: '1px solid #27272a', color: '#71717a', textAlign: 'left' }}>
                {['Username','Name','Email','Role','Plan','Verified','Joined'].map(h => (
                  <th key={h} style={{ padding: '8px 12px', fontWeight: 600 }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {users.slice(0, 20).map((u, i) => (
                <tr key={i} style={{ borderBottom: '1px solid #18181b', color: '#d4d4d8' }}
                  onMouseEnter={e => (e.currentTarget.style.background = '#27272a')}
                  onMouseLeave={e => (e.currentTarget.style.background = 'transparent')}>
                  <td style={{ padding: '8px 12px', fontWeight: 600 }}>{u.username}</td>
                  <td style={{ padding: '8px 12px' }}>{u.name || '—'}</td>
                  <td style={{ padding: '8px 12px', color: '#71717a' }}>{u.email}</td>
                  <td style={{ padding: '8px 12px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
                      background: u.role === 'admin' ? `${RED}33` : '#27272a',
                      color: u.role === 'admin' ? RED : '#a1a1aa',
                      textTransform: 'uppercase',
                    }}>{u.role}</span>
                  </td>
                  <td style={{ padding: '8px 12px' }}>
                    <span style={{
                      padding: '2px 8px', borderRadius: 99, fontSize: 10, fontWeight: 700,
                      background: u.subscription === 'premium' ? `${ACCENT}33` : '#27272a',
                      color: u.subscription === 'premium' ? ACCENT : '#a1a1aa',
                      textTransform: 'uppercase',
                    }}>{u.subscription || 'free'}</span>
                  </td>
                  <td style={{ padding: '8px 12px', textAlign: 'center' }}>
                    {u.verified ? '✅' : '❌'}
                  </td>
                  <td style={{ padding: '8px 12px', color: '#71717a' }}>
                    {u.created_at ? u.created_at.slice(0, 10) : '—'}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {users.length > 20 && (
            <p style={{ color: '#52525b', fontSize: 12, padding: '8px 12px', textAlign: 'center' }}>
              Showing 20 of {users.length} users
            </p>
          )}
        </div>
      </Section>

    </div>
  );
};

// ─── Small helper ─────────────────────────────────────────────────────────────
const EmptyState: React.FC<{ msg: string }> = ({ msg }) => (
  <div style={{
    height: 200, display: 'flex', flexDirection: 'column',
    alignItems: 'center', justifyContent: 'center', color: '#52525b', textAlign: 'center',
  }}>
    <span style={{ fontSize: 36, marginBottom: 10 }}>📭</span>
    <p style={{ fontSize: 13 }}>{msg}</p>
  </div>
);

export default InsightsDashboard;
