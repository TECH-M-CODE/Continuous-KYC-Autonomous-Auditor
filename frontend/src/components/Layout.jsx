import React, { useState } from 'react';
import { NavLink, Outlet, Link } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import { useSSE } from '../hooks/useSSE';
import {
  Bell, Activity, FileText, History, ShieldAlert,
  LayoutDashboard, ChevronRight, Zap, Shield, Sun, Moon
} from 'lucide-react';
import clsx from 'clsx';
import { apiClient } from '../api/client';
import { useTheme } from './ThemeContext';

export const Layout = () => {
  const { connected, connectionState, lastEvent } = useSSE();
  const { theme, toggleTheme } = useTheme();
  const [lastEventFlash, setLastEventFlash] = useState(false);

  const { data: alerts = [] } = useQuery({
    queryKey: ['alerts'],
    queryFn: apiClient.getAlerts,
    refetchInterval: 15_000,
  });

  const openAlerts = alerts.filter(a => a.status === 'OPEN').length;
  const criticalAlerts = alerts.filter(a => a.priority === 'CRITICAL' && a.status === 'OPEN').length;

  // Flash when new SSE event arrives
  React.useEffect(() => {
    if (!lastEvent) return;
    setLastEventFlash(true);
    const t = setTimeout(() => setLastEventFlash(false), 1000);
    return () => clearTimeout(t);
  }, [lastEvent]);

  const navItems = [
    { name: 'Dashboard',        path: '/',          icon: LayoutDashboard, exact: true },
    { name: 'Alert Queue',      path: '/alerts',    icon: Bell,            badge: openAlerts || null },
    { name: 'Entity Timeline',  path: '/timeline',  icon: Activity },
    { name: 'SAR Review',       path: '/sar',       icon: FileText },
    { name: 'Audit Trail',      path: '/audit',     icon: History },
    { name: 'Admin Watchlist',  path: '/watchlist', icon: ShieldAlert },
  ];

  return (
    <div className="flex h-screen text-slate-300 overflow-hidden" style={{ background: 'var(--app-bg)' }}>
      {/* ── Sidebar ─────────────────────────────── */}
      <aside className="w-60 flex-col hidden md:flex border-r" style={{ background: 'var(--app-surface)', borderColor: 'var(--app-border)' }}>
        {/* Logo */}
        <div className="p-4 border-b" style={{ borderColor: 'var(--app-border)' }}>
          <Link to="/" className="flex items-center gap-3 group">
            <div className="relative w-9 h-9 rounded-xl flex items-center justify-center shrink-0"
              style={{ background: 'linear-gradient(135deg, #0a7eff 0%, #7c3aed 100%)' }}>
              <Shield className="w-5 h-5 text-white" />
              {criticalAlerts > 0 && (
                <span className="absolute -top-1 -right-1 w-3 h-3 rounded-full bg-red-500 border-2 animate-pulse"
                  style={{ borderColor: 'var(--app-surface)' }} />
              )}
            </div>
            <div>
              <h1 className="text-sm font-bold text-white tracking-tight">SentinelAI</h1>
              <p className="text-[10px] text-slate-500">Continuous KYC Auditor</p>
            </div>
          </Link>
        </div>

        {/* Nav */}
        <nav className="flex-1 p-3 space-y-0.5 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              end={item.exact}
              className={({ isActive }) => clsx(
                'flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-medium transition-all group relative',
                isActive
                  ? 'text-white'
                  : 'text-slate-500 hover:text-slate-200 hover:bg-slate-800/50'
              )}
              style={({ isActive }) => isActive ? {
                background: 'linear-gradient(135deg, rgba(10,126,255,0.15) 0%, rgba(124,58,237,0.08) 100%)',
                borderLeft: '2px solid #0a7eff',
                paddingLeft: '10px',
              } : {}}
            >
              <item.icon className="w-4 h-4 shrink-0" />
              <span className="flex-1">{item.name}</span>
              {item.badge > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] font-bold bg-red-500 text-white min-w-[18px] text-center">
                  {item.badge > 99 ? '99+' : item.badge}
                </span>
              )}
            </NavLink>
          ))}
        </nav>

        {/* Bottom status */}
        <div className="p-3 border-t space-y-2" style={{ borderColor: 'var(--app-border)' }}>
          <div className={clsx(
            'flex items-center gap-2 px-3 py-2 rounded-xl border transition-all text-xs',
            connected
              ? 'bg-emerald-500/5 border-emerald-500/20 text-emerald-400'
              : 'bg-red-500/5 border-red-500/20 text-red-400',
            lastEventFlash && 'border-brand-500/50 bg-brand-500/5'
          )}>
            <span className={clsx(
              'w-1.5 h-1.5 rounded-full',
              connected ? 'bg-emerald-400 animate-ping' : 'bg-red-400'
            )} />
            <Zap className={clsx('w-3 h-3', lastEventFlash ? 'text-brand-400' : '')} />
            <span>{connected ? 'Pipeline Live' : 'Disconnected'}</span>
          </div>
        </div>
      </aside>

      {/* ── Main content ────────────────────────── */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Header */}
        <header className="h-12 flex items-center justify-between px-6 border-b shrink-0"
          style={{ background: 'var(--app-header-bg)', borderColor: 'var(--app-border)', backdropFilter: 'blur(12px)' }}>
          <div className="flex items-center gap-3">
            <ChevronRight className="w-3.5 h-3.5 text-slate-600" />
            <span className="text-xs text-slate-500">Hackathon Challenge 3</span>
          </div>
          <div className="flex items-center gap-3">
            {criticalAlerts > 0 && (
              <div className="flex items-center gap-1.5 px-2.5 py-1 rounded-lg bg-red-500/10 border border-red-500/20 text-red-400 text-xs font-medium animate-pulse">
                <ShieldAlert className="w-3 h-3" />
                {criticalAlerts} critical
              </div>
            )}
            <button
              onClick={toggleTheme}
              title={theme === 'dark' ? 'Switch to light theme' : 'Switch to dark theme'}
              aria-label="Toggle color theme"
              className="w-8 h-8 rounded-full flex items-center justify-center border border-slate-700 bg-slate-800/60 text-slate-300 hover:text-white hover:border-brand-500/50 transition-colors"
            >
              {theme === 'dark'
                ? <Sun className="w-4 h-4" />
                : <Moon className="w-4 h-4" />}
            </button>
          </div>
        </header>

        {/* Page */}
        <main className="flex-1 overflow-auto p-6 relative" style={{ background: 'var(--app-bg)' }}>
          <Outlet />
        </main>
      </div>
    </div>
  );
};
