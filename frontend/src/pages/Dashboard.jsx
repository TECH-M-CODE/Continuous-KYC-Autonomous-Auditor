import React, { useState, useMemo } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import {
  ShieldCheck, ShieldAlert, Users, AlertTriangle,
  FileText, TrendingUp, Globe, ArrowUpRight, Activity
} from 'lucide-react';
import { apiClient } from '../api/client';
import { RiskGauge } from '../components/RiskGauge';
import { LiveFeed } from '../components/LiveFeed';
import { StatusBadge } from '../components/StatusBadge';

/* ── Helpers ── */
const timeAgo = (iso) => {
  const d = Math.floor((Date.now() - new Date(iso)) / 60000);
  if (d < 1)  return 'just now';
  if (d < 60) return `${d}m ago`;
  const h = Math.floor(d / 60);
  if (h < 24) return `${h}h ago`;
  return `${Math.floor(h / 24)}d ago`;
};

const RISK_BANDS = [
  { key: 'CRITICAL', label: 'Critical', bar: '#ef4444', text: 'text-red-400',     bg: 'bg-red-500/10 border-red-500/20' },
  { key: 'HIGH',     label: 'High',     bar: '#f97316', text: 'text-orange-400',  bg: 'bg-orange-500/10 border-orange-500/20' },
  { key: 'MEDIUM',   label: 'Medium',   bar: '#eab308', text: 'text-yellow-400',  bg: 'bg-yellow-500/10 border-yellow-500/20' },
  { key: 'LOW',      label: 'Low',      bar: '#22c55e', text: 'text-emerald-400', bg: 'bg-emerald-500/10 border-emerald-500/20' },
];

/* ── Stat Card ── */
const StatCard = ({ title, value, icon: Icon, gradient, sub, delay = 0 }) => (
  <div
    className="relative overflow-hidden rounded-2xl border p-5 flex flex-col gap-3 animate-slide-up glass-card"
    style={{ animationDelay: `${delay}ms`, borderColor: 'var(--app-border)' }}
  >
    <div className="flex items-start justify-between">
      <p className="text-xs font-semibold text-slate-500 uppercase tracking-wider">{title}</p>
      <div className="p-2 rounded-xl" style={{ background: gradient, opacity: 0.15 }}>
        <Icon className="w-4 h-4" style={{ color: 'white' }} />
      </div>
    </div>
    <div>
      <h3 className="text-3xl font-extrabold text-white animate-count-up" style={{ animationDelay: `${delay + 100}ms` }}>
        {value ?? '—'}
      </h3>
      {sub && <p className="text-xs text-slate-500 mt-1">{sub}</p>}
    </div>
    {/* Gradient accent line */}
    <div className="absolute bottom-0 left-0 right-0 h-0.5 rounded-full" style={{ background: gradient }} />
  </div>
);

/* ── Top Entity Row ── */
const EntityRow = ({ entity, rank }) => {
  const band = entity.risk_band || 'LOW';
  const barColor =
    band === 'CRITICAL' ? '#ef4444' :
    band === 'HIGH'     ? '#f97316' :
    band === 'MEDIUM'   ? '#eab308' : '#22c55e';

  return (
    <Link
      to={`/timeline/${entity.id}`}
      className="flex items-center gap-3 p-3 rounded-xl hover:bg-slate-800/40 transition-all group"
    >
      <span className="text-xs font-bold text-slate-600 w-5 text-right shrink-0">{rank}</span>
      <div className="flex-1 min-w-0">
        <p className="text-sm font-medium text-slate-200 group-hover:text-brand-300 transition-colors truncate">
          {entity.name}
        </p>
        <p className="text-xs text-slate-500">{entity.type} · {entity.jurisdiction || '—'}</p>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <div className="w-16 bg-slate-800 rounded-full h-1.5 overflow-hidden">
          <div className="h-1.5 rounded-full transition-all" style={{ width: `${entity.risk_score}%`, background: barColor }} />
        </div>
        <span className="text-xs font-bold w-8 text-right" style={{ color: barColor }}>
          {entity.risk_score}
        </span>
      </div>
      <ArrowUpRight className="w-3.5 h-3.5 text-slate-600 group-hover:text-brand-400 transition-colors" />
    </Link>
  );
};

/* ── Dashboard ── */
export const Dashboard = () => {
  const queryClient = useQueryClient();  const { data: alerts = [] }   = useQuery({ queryKey: ['dashboard-alerts'],   queryFn: () => apiClient.getAlerts({ limit: 100 }) });
  const { data: entities = [] } = useQuery({ queryKey: ['dashboard-entities'], queryFn: () => apiClient.getWatchlist({ limit: 100 }) });
  const { data: sars = [] }     = useQuery({ queryKey: ['dashboard-sars'],     queryFn: () => apiClient.getSARs({ limit: 100 }) });
  const { data: auditStatus }   = useQuery({ queryKey: ['dashboard-audit-verify'], queryFn: apiClient.verifyAuditChain });

  const activeAlerts  = alerts.filter(a => a.status === 'OPEN');
  const criticalCount = alerts.filter(a => a.priority === 'CRITICAL').length;
  const pendingSars   = sars.filter(s => s.status === 'DRAFT' || s.status === 'PENDING_APPROVAL');

  const avgRisk = useMemo(() => {
    if (!entities.length) return 0;
    return Math.round(entities.reduce((s, e) => s + (e.risk_score || 0), 0) / entities.length);
  }, [entities]);

  const riskCounts = RISK_BANDS.map(b => ({
    ...b, count: entities.filter(e => e.risk_band === b.key).length,
  }));

  const topEntities = useMemo(() =>
    [...entities].sort((a, b) => (b.risk_score || 0) - (a.risk_score || 0)).slice(0, 5),
    [entities]
  );

  // Country distribution for threat map
  const countryCounts = useMemo(() => {
    const map = {};
    entities.forEach(e => {
      const c = e.jurisdiction || 'Unknown';
      map[c] = (map[c] || 0) + 1;
    });
    return Object.entries(map).sort((a, b) => b[1] - a[1]).slice(0, 8);
  }, [entities]);

  return (
    <div className="flex flex-col space-y-6 max-w-7xl mx-auto w-full relative">
      {/* Page title */}
      <div className="flex items-center justify-between animate-slide-up">
        <div>
          <h1 className="text-2xl font-bold text-slate-100">System Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1">Real-time overview of your Continuous KYC autonomous auditing system.</p>
        </div>
      </div>


      {/* ── Stat Cards ── */}
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-4">
        <StatCard
          title="Active Alerts" value={activeAlerts.length}
          icon={AlertTriangle} delay={0}
          gradient="linear-gradient(135deg, #ef4444, #dc2626)"
          sub={`${criticalCount} critical`}
        />
        <StatCard
          title="Entities Monitored" value={entities.length}
          icon={Users} delay={80}
          gradient="linear-gradient(135deg, #0a7eff, #7c3aed)"
          sub="Under surveillance"
        />
        <StatCard
          title="Pending SARs" value={pendingSars.length}
          icon={FileText} delay={160}
          gradient="linear-gradient(135deg, #f97316, #ea580c)"
          sub="Awaiting review"
        />
        <StatCard
          title="Audit Chain"
          value={auditStatus ? (auditStatus.is_valid ? 'Valid' : 'Broken') : '—'}
          icon={auditStatus?.is_valid === false ? ShieldAlert : ShieldCheck}
          delay={240}
          gradient={auditStatus?.is_valid === false
            ? 'linear-gradient(135deg, #ef4444, #dc2626)'
            : 'linear-gradient(135deg, #22c55e, #16a34a)'}
          sub="Cryptographic integrity"
        />
      </div>

      {/* ── Middle row: Gauge + Risk Distribution + Live Feed ── */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4">

        {/* Average Risk Gauge */}
        <div className="glass-card rounded-2xl p-5 flex flex-col items-center justify-center gap-4 animate-slide-up delay-300">
          <h2 className="text-sm font-semibold text-slate-400 self-start flex items-center gap-2">
            <TrendingUp className="w-4 h-4 text-brand-400" />
            Average Portfolio Risk
          </h2>
          <RiskGauge score={avgRisk} size={160} label="Portfolio Risk Score" />
          <div className="grid grid-cols-2 gap-2 w-full">
            {riskCounts.slice(0, 4).map(b => (
              <div key={b.key} className={`flex items-center justify-between px-2.5 py-1.5 rounded-lg border text-xs ${b.bg}`}>
                <span className={b.text + ' font-medium'}>{b.label}</span>
                <span className="text-slate-300 font-bold">{b.count}</span>
              </div>
            ))}
          </div>
        </div>

        {/* Live Pipeline Feed */}
        <div className="lg:col-span-2 glass-card rounded-2xl p-5 animate-slide-up delay-400">
          <LiveFeed maxHeight={280} />
        </div>
      </div>

      {/* ── Bottom row: Top Entities + Threat Map ── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* Top 5 Riskiest */}
        <div className="glass-card rounded-2xl p-5 animate-slide-up" style={{ animationDelay: '500ms' }}>
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2">
              <ShieldAlert className="w-4 h-4 text-red-400" />
              Top Riskiest Entities
            </h2>
            <Link to="/watchlist" className="text-xs text-brand-400 hover:text-brand-300 transition-colors">View all →</Link>
          </div>
          <div className="space-y-1">
            {topEntities.map((e, i) => <EntityRow key={e.id} entity={e} rank={i + 1} />)}
            {topEntities.length === 0 && (
              <p className="text-xs text-slate-600 text-center py-6">No entities yet.</p>
            )}
          </div>
        </div>

        {/* Threat Map (country distribution) */}
        <div className="glass-card rounded-2xl p-5 animate-slide-up" style={{ animationDelay: '600ms' }}>
          <h2 className="text-sm font-semibold text-slate-300 flex items-center gap-2 mb-4">
            <Globe className="w-4 h-4 text-brand-400" />
            Geographic Exposure
          </h2>
          <div className="space-y-3">
            {countryCounts.map(([country, count]) => {
              const pct = Math.round((count / (entities.length || 1)) * 100);
              const isHighRisk = entities
                .filter(e => e.jurisdiction === country)
                .some(e => e.risk_band === 'CRITICAL' || e.risk_band === 'HIGH');
              return (
                <div key={country}>
                  <div className="flex justify-between text-xs mb-1">
                    <span className={isHighRisk ? 'text-orange-400 font-medium' : 'text-slate-400'}>
                      {country}
                      {isHighRisk && <span className="ml-1.5 text-[10px] text-red-400 font-semibold">HIGH RISK</span>}
                    </span>
                    <span className="text-slate-500">{count} entities · {pct}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-1.5 overflow-hidden">
                    <div
                      className="h-1.5 rounded-full transition-all"
                      style={{
                        width: `${pct}%`,
                        background: isHighRisk
                          ? 'linear-gradient(90deg, #f97316, #ef4444)'
                          : 'linear-gradient(90deg, #0a7eff, #7c3aed)',
                      }}
                    />
                  </div>
                </div>
              );
            })}
            {countryCounts.length === 0 && (
              <p className="text-xs text-slate-600 text-center py-6">No geographic data yet.</p>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
