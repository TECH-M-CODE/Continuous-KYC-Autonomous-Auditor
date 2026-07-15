import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert, Users, AlertTriangle, FileText, Activity } from 'lucide-react';
import { apiClient } from '../api/client';

const StatCard = ({ title, value, icon: Icon, colorClass }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex items-center justify-between">
    <div>
      <p className="text-sm font-medium text-slate-400 mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-slate-100">{value}</h3>
    </div>
    <div className={`p-4 rounded-xl ${colorClass}`}>
      <Icon className="w-6 h-6" />
    </div>
  </div>
);

const RISK_BANDS = [
  { key: 'CRITICAL', label: 'Critical Risk', barClass: 'bg-red-500', textClass: 'text-red-400' },
  { key: 'HIGH', label: 'High Risk', barClass: 'bg-orange-500', textClass: 'text-orange-400' },
  { key: 'MEDIUM', label: 'Medium Risk', barClass: 'bg-yellow-500', textClass: 'text-yellow-400' },
  { key: 'LOW', label: 'Low Risk', barClass: 'bg-emerald-500', textClass: 'text-emerald-400' },
];

const timeAgo = (isoDate) => {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return 'just now';
  if (minutes < 60) return `${minutes} min${minutes === 1 ? '' : 's'} ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} hour${hours === 1 ? '' : 's'} ago`;
  const days = Math.floor(hours / 24);
  return `${days} day${days === 1 ? '' : 's'} ago`;
};

export const Dashboard = () => {
  const queryClient = useQueryClient();
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [formData, setFormData] = useState({ name: '', jurisdiction: '', sector: '' });

  const addCustomerMutation = useMutation({
    mutationFn: apiClient.addCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries(['dashboard-entities']);
      setIsModalOpen(false);
      setFormData({ name: '', jurisdiction: '', sector: '' });
    },
  });
  const { data: alerts = [] } = useQuery({
    queryKey: ['dashboard-alerts'],
    queryFn: () => apiClient.getAlerts({ limit: 100 }),
  });

  const { data: entities = [] } = useQuery({
    queryKey: ['dashboard-entities'],
    queryFn: () => apiClient.getWatchlist({ limit: 100 }),
  });

  const { data: sars = [] } = useQuery({
    queryKey: ['dashboard-sars'],
    queryFn: () => apiClient.getSARs({ limit: 100 }),
  });

  const { data: auditStatus } = useQuery({
    queryKey: ['dashboard-audit-verify'],
    queryFn: apiClient.verifyAuditChain,
  });

  const activeAlerts = alerts.filter((a) => a.status === 'OPEN');
  const pendingSars = sars.filter((s) => s.status === 'DRAFT' || s.status === 'PENDING_APPROVAL');
  const totalEntities = entities.length;

  const riskCounts = RISK_BANDS.map((band) => ({
    ...band,
    count: entities.filter((e) => e.risk_band === band.key).length,
  }));

  const recentActivity = [...alerts]
    .sort((a, b) => new Date(b.created_at) - new Date(a.created_at))
    .slice(0, 4);

  return (
    <div className="flex flex-col space-y-8 max-w-7xl mx-auto w-full relative">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100">System Dashboard</h1>
          <p className="text-sm text-slate-400 mt-1">Overview of your Continuous KYC autonomous auditing system.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-4 py-2 bg-brand-600 hover:bg-brand-500 text-white font-medium rounded-lg transition-colors shadow-lg"
        >
          Add Customer
        </button>
      </div>

      {isModalOpen && (
        <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50">
          <div className="bg-slate-900 border border-slate-700 rounded-xl w-full max-w-md p-6 shadow-2xl">
            <h2 className="text-xl font-bold text-slate-100 mb-4">Add New Customer</h2>
            <div className="space-y-4">
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Entity Name</label>
                <input
                  type="text"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                  value={formData.name}
                  onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                  placeholder="e.g. Acme Corp"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Jurisdiction</label>
                <input
                  type="text"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                  value={formData.jurisdiction}
                  onChange={(e) => setFormData({ ...formData, jurisdiction: e.target.value })}
                  placeholder="e.g. US"
                />
              </div>
              <div>
                <label className="block text-sm font-medium text-slate-400 mb-1">Sector</label>
                <input
                  type="text"
                  className="w-full bg-slate-800 border border-slate-700 rounded-lg px-3 py-2 text-slate-100 focus:outline-none focus:border-brand-500"
                  value={formData.sector}
                  onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
                  placeholder="e.g. Finance"
                />
              </div>
            </div>
            <div className="mt-6 flex justify-end gap-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-4 py-2 text-slate-300 hover:text-white transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => addCustomerMutation.mutate(formData)}
                disabled={addCustomerMutation.isPending || !formData.name}
                className="px-4 py-2 bg-brand-600 hover:bg-brand-500 disabled:opacity-50 text-white font-medium rounded-lg transition-colors"
              >
                {addCustomerMutation.isPending ? 'Adding...' : 'Add Customer'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard
          title="Active Alerts"
          value={activeAlerts.length}
          icon={AlertTriangle}
          colorClass="bg-red-500/10 text-red-400 border border-red-500/20"
        />
        <StatCard
          title="Entities Monitored"
          value={totalEntities}
          icon={Users}
          colorClass="bg-brand-500/10 text-brand-400 border border-brand-500/20"
        />
        <StatCard
          title="Pending SARs"
          value={pendingSars.length}
          icon={FileText}
          colorClass="bg-orange-500/10 text-orange-400 border border-orange-500/20"
        />
        <StatCard
          title="Audit Chain"
          value={auditStatus ? (auditStatus.is_valid ? 'Verified' : 'Broken') : '—'}
          icon={auditStatus?.is_valid === false ? ShieldAlert : ShieldCheck}
          colorClass={
            auditStatus?.is_valid === false
              ? 'bg-red-500/10 text-red-400 border border-red-500/20'
              : 'bg-emerald-500/10 text-emerald-400 border border-emerald-500/20'
          }
        />
      </div>

      {/* Lower Section */}
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-6">

        {/* Recent Activity */}
        <div className="lg:col-span-2 bg-slate-900 border border-slate-800 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-slate-100 mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-slate-400" />
            Recent System Activity
          </h2>

          <div className="space-y-4">
            {recentActivity.map((alert) => (
              <div key={alert.id} className="flex items-start gap-4 p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <div className={`mt-0.5 w-2 h-2 rounded-full ${
                  alert.priority === 'CRITICAL' || alert.priority === 'HIGH'
                    ? 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]'
                    : 'bg-brand-400'
                }`} />
                <div>
                  <p className="text-sm font-medium text-slate-200">
                    {alert.priority} alert for {alert.entity_name} — {alert.status}
                  </p>
                  <p className="text-xs text-slate-500 mt-1">{timeAgo(alert.created_at)}</p>
                </div>
              </div>
            ))}

            {recentActivity.length === 0 && (
              <div className="text-center text-slate-500 py-8">No recent alerts.</div>
            )}
          </div>
        </div>

        {/* Risk Distribution */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col">
          <h2 className="text-lg font-semibold text-slate-100 mb-6">Risk Distribution</h2>

          <div className="flex-1 flex flex-col justify-center space-y-6">
            {riskCounts.map((band) => {
              const pct = totalEntities > 0 ? Math.round((band.count / totalEntities) * 100) : 0;
              return (
                <div key={band.key}>
                  <div className="flex justify-between text-sm mb-2">
                    <span className={`${band.textClass} font-medium`}>{band.label}</span>
                    <span className="text-slate-400">{pct}%</span>
                  </div>
                  <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                    <div className={`${band.barClass} h-2 rounded-full`} style={{ width: `${pct}%` }}></div>
                  </div>
                </div>
              );
            })}
          </div>
        </div>
      </div>
    </div>
  );
};
