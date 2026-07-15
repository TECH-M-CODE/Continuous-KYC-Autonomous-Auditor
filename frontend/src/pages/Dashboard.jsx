import React, { useState } from 'react';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import { ShieldCheck, ShieldAlert, Users, AlertTriangle, FileText, Activity } from 'lucide-react';
import { apiClient } from '../api/client';

const StatCard = ({ title, value, icon: Icon, colorClass }) => (
  <div className="glass-panel p-6 flex items-center justify-between glass-panel-hover cursor-default">
    <div>
      <p className="text-sm font-semibold text-slate-500 mb-1">{title}</p>
      <h3 className="text-3xl font-bold text-slate-800">{value}</h3>
    </div>
    <div className={`p-4 rounded-2xl shadow-sm border border-white/50 ${colorClass}`}>
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
  
  const [duplicateMatches, setDuplicateMatches] = useState([]);
  const [showDuplicateModal, setShowDuplicateModal] = useState(false);
  const [isChecking, setIsChecking] = useState(false);
  const [verificationResult, setVerificationResult] = useState(null);

  const addCustomerMutation = useMutation({
    mutationFn: apiClient.addCustomer,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['dashboard-entities'] });
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
          <h1 className="text-2xl font-bold text-slate-800 drop-shadow-sm">System Dashboard</h1>
          <p className="text-sm text-slate-500 mt-1 font-medium">Overview of your Continuous KYC autonomous auditing system.</p>
        </div>
        <button
          onClick={() => setIsModalOpen(true)}
          className="px-5 py-2.5 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 text-white font-semibold rounded-xl shadow-lg shadow-brand-500/30 transition-all hover:-translate-y-0.5"
        >
          Add Customer
        </button>
      </div>

      {/* Verification Result Popup */}
      {verificationResult && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-[70]" onClick={() => setVerificationResult(null)}>
          <div className="glass-panel bg-white/70 w-full max-w-sm p-8 text-center transform scale-100 transition-transform">
            {verificationResult.status === 'SAFE' ? (
              <div className="mx-auto w-20 h-20 bg-emerald-50 border border-emerald-200 rounded-full flex items-center justify-center mb-6 shadow-inner">
                <ShieldCheck className="w-10 h-10 text-emerald-500" />
              </div>
            ) : (
              <div className="mx-auto w-20 h-20 bg-red-50 border border-red-200 rounded-full flex items-center justify-center mb-6 shadow-inner">
                <ShieldAlert className="w-10 h-10 text-red-500" />
              </div>
            )}
            
            <h2 className={`text-2xl font-bold mb-2 ${verificationResult.status === 'SAFE' ? 'text-emerald-600' : 'text-red-600'}`}>
              {verificationResult.status === 'SAFE' ? 'Customer is Safe' : 'Customer At Risk'}
            </h2>
            
            <p className="text-slate-600 mb-8 font-medium">
              Existing risk profile is <strong className="text-slate-800">{verificationResult.band}</strong>. No new profile was created.
            </p>
            
            <button
              onClick={() => setVerificationResult(null)}
              className="w-full py-3 bg-white hover:bg-slate-50 text-slate-800 font-bold border border-slate-200 rounded-xl transition-all shadow-sm"
            >
              Close
            </button>
          </div>
        </div>
      )}

      {/* Duplicate Check Modal */}
      {showDuplicateModal && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-[60]">
          <div className="glass-panel bg-white/70 w-full max-w-lg p-6 shadow-2xl">
            <div className="flex items-center gap-3 mb-4 text-orange-500">
              <AlertTriangle className="w-6 h-6" />
              <h2 className="text-xl font-bold">Potential Duplicate Detected</h2>
            </div>
            <p className="text-slate-600 mb-6 font-medium">
              We found existing records matching this name. Is this the same person/entity?
            </p>
            
            <div className="space-y-3 mb-6 max-h-60 overflow-y-auto pr-2">
              {duplicateMatches.map(match => (
                <div key={match.id} className="bg-white/50 p-4 rounded-xl border border-white/60 shadow-sm flex justify-between items-center hover:bg-white/80 transition-colors">
                  <div>
                    <p className="font-bold text-slate-800">{match.name}</p>
                    <p className="text-sm font-medium text-slate-500">{match.role}</p>
                  </div>
                  <button
                    onClick={() => {
                      const isSafe = ['LOW', 'MEDIUM'].includes(match.risk_band);
                      setVerificationResult({ status: isSafe ? 'SAFE' : 'AT_RISK', band: match.risk_band });
                      setShowDuplicateModal(false);
                      setIsModalOpen(false);
                    }}
                    className="px-4 py-2 bg-brand-500 hover:bg-brand-600 text-white text-sm font-semibold rounded-lg shadow-sm transition-colors"
                  >
                    Yes, this is them
                  </button>
                </div>
              ))}
            </div>

            <div className="flex justify-end gap-3 pt-4 border-t border-white/40">
              <button
                onClick={() => setShowDuplicateModal(false)}
                className="px-4 py-2 text-slate-500 font-semibold hover:text-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={() => {
                  const finalName = formData.type === 'PERSON' 
                    ? `${formData.firstName || ''} ${formData.lastName || ''}`.trim() 
                    : formData.name;
                  setShowDuplicateModal(false);
                  addCustomerMutation.mutate({ ...formData, name: finalName });
                }}
                className="px-4 py-2 bg-slate-200 hover:bg-slate-300 text-slate-800 font-bold rounded-xl shadow-sm transition-colors"
              >
                No, create new customer
              </button>
            </div>
          </div>
        </div>
      )}

      {isModalOpen && (
        <div className="fixed inset-0 bg-slate-900/40 backdrop-blur-sm flex items-center justify-center z-50">
          <div className="glass-panel bg-white/70 w-full max-w-md p-6 shadow-2xl">
            <h2 className="text-xl font-bold text-slate-800 mb-4">Add New Customer</h2>
            
            <div className="flex gap-4 mb-6">
              <label className="flex items-center gap-2 text-slate-600 font-semibold">
                <input 
                  type="radio" 
                  name="customerType" 
                  checked={formData.type === 'PERSON'} 
                  onChange={() => setFormData({ ...formData, type: 'PERSON', name: '', firstName: '', lastName: '' })}
                  className="text-brand-500 focus:ring-brand-500 border-slate-300"
                />
                Person
              </label>
              <label className="flex items-center gap-2 text-slate-600 font-semibold">
                <input 
                  type="radio" 
                  name="customerType" 
                  checked={formData.type !== 'PERSON'} 
                  onChange={() => setFormData({ ...formData, type: 'COMPANY', name: '', firstName: '', lastName: '' })}
                  className="text-brand-500 focus:ring-brand-500 border-slate-300"
                />
                Company
              </label>
            </div>

            <div className="space-y-4">
              {formData.type === 'PERSON' ? (
                <>
                  <div className="flex gap-4">
                    <div className="flex-1">
                      <label className="block text-sm font-semibold text-slate-600 mb-1">First Name</label>
                      <input
                        type="text"
                        className="glass-input w-full px-4 py-2.5 text-slate-800"
                        value={formData.firstName || ''}
                        onChange={(e) => setFormData({ ...formData, firstName: e.target.value })}
                        placeholder="e.g. Khushi"
                      />
                    </div>
                    <div className="flex-1">
                      <label className="block text-sm font-semibold text-slate-600 mb-1">Last Name</label>
                      <input
                        type="text"
                        className="glass-input w-full px-4 py-2.5 text-slate-800"
                        value={formData.lastName || ''}
                        onChange={(e) => setFormData({ ...formData, lastName: e.target.value })}
                        placeholder="e.g. Katiyar"
                      />
                    </div>
                  </div>
                </>
              ) : (
                <div>
                  <label className="block text-sm font-semibold text-slate-600 mb-1">Company Name</label>
                  <input
                    type="text"
                    className="glass-input w-full px-4 py-2.5 text-slate-800"
                    value={formData.name || ''}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    placeholder="e.g. Acme Corp"
                  />
                </div>
              )}
              
              <div>
                <label className="block text-sm font-semibold text-slate-600 mb-1">Jurisdiction / Country</label>
                <input
                  type="text"
                  className="glass-input w-full px-4 py-2.5 text-slate-800"
                  value={formData.jurisdiction}
                  onChange={(e) => setFormData({ ...formData, jurisdiction: e.target.value })}
                  placeholder="e.g. US, UK, India"
                />
              </div>
              <div>
                <label className="block text-sm font-semibold text-slate-600 mb-1">Sector / Industry</label>
                <input
                  type="text"
                  className="glass-input w-full px-4 py-2.5 text-slate-800"
                  value={formData.sector}
                  onChange={(e) => setFormData({ ...formData, sector: e.target.value })}
                  placeholder="e.g. Finance, Technology"
                />
              </div>
            </div>
            <div className="mt-8 flex justify-end gap-3">
              <button
                onClick={() => setIsModalOpen(false)}
                className="px-5 py-2.5 text-slate-500 font-semibold hover:text-slate-800 transition-colors"
              >
                Cancel
              </button>
              <button
                onClick={async () => {
                  const finalName = formData.type === 'PERSON' 
                    ? `${formData.firstName || ''} ${formData.lastName || ''}`.trim() 
                    : formData.name;
                  
                  setIsChecking(true);
                  try {
                    const matches = await apiClient.checkDuplicate(finalName);
                    if (matches && matches.length > 0) {
                      setDuplicateMatches(matches);
                      setShowDuplicateModal(true);
                    } else {
                      addCustomerMutation.mutate({ ...formData, name: finalName });
                    }
                  } catch(e) {
                    addCustomerMutation.mutate({ ...formData, name: finalName });
                  } finally {
                    setIsChecking(false);
                  }
                }}
                disabled={addCustomerMutation.isPending || isChecking || (formData.type === 'PERSON' ? (!formData.firstName && !formData.lastName) : !formData.name)}
                className="px-5 py-2.5 bg-gradient-to-r from-brand-500 to-brand-600 hover:from-brand-600 hover:to-brand-700 disabled:opacity-50 text-white font-bold rounded-xl shadow-md transition-all hover:shadow-lg"
              >
                {addCustomerMutation.isPending || isChecking ? 'Adding...' : 'Add Customer'}
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
        <div className="lg:col-span-2 glass-panel p-6">
          <h2 className="text-lg font-bold text-slate-800 mb-6 flex items-center gap-2">
            <Activity className="w-5 h-5 text-brand-500" />
            Recent System Activity
          </h2>

          <div className="space-y-4">
            {recentActivity.map((alert) => (
              <div key={alert.id} className="flex items-start gap-4 p-4 rounded-2xl bg-white/40 border border-white/60 shadow-sm hover:bg-white/60 transition-colors">
                <div className={`mt-0.5 w-2 h-2 rounded-full ${
                  alert.priority === 'CRITICAL' || alert.priority === 'HIGH'
                    ? 'bg-red-500 shadow-[0_0_8px_rgba(239,68,68,0.6)]'
                    : 'bg-brand-500'
                }`} />
                <div>
                  <p className="text-sm font-semibold text-slate-700">
                    {alert.priority} alert for {alert.entity_name} — {alert.status}
                  </p>
                  <p className="text-xs font-medium text-slate-500 mt-1">{timeAgo(alert.created_at)}</p>
                </div>
              </div>
            ))}

            {recentActivity.length === 0 && (
              <div className="text-center text-slate-500 py-8 font-medium">No recent alerts.</div>
            )}
          </div>
        </div>

        {/* Risk Distribution */}
        <div className="glass-panel p-6 flex flex-col">
          <h2 className="text-lg font-bold text-slate-800 mb-6">Risk Distribution</h2>

          <div className="flex-1 flex flex-col justify-center space-y-6">
            {riskCounts.map((band) => {
              const pct = totalEntities > 0 ? Math.round((band.count / totalEntities) * 100) : 0;
              return (
                <div key={band.key}>
                  <div className="flex justify-between text-sm mb-2">
                    <span className={`${band.textClass} font-bold`}>{band.label}</span>
                    <span className="text-slate-500 font-semibold">{pct}%</span>
                  </div>
                  <div className="w-full bg-slate-200/50 rounded-full h-2 overflow-hidden shadow-inner border border-white/30">
                    <div className={`${band.barClass} h-2 rounded-full shadow-sm`} style={{ width: `${pct}%` }}></div>
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
