import React from 'react';
import { ShieldCheck, Users, AlertTriangle, FileText, Activity, TrendingUp } from 'lucide-react';

const StatCard = ({ title, value, icon: Icon, trend, colorClass }) => (
  <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex items-center justify-between">
    <div>
      <p className="text-sm font-medium text-slate-400 mb-1">{title}</p>
      <div className="flex items-baseline gap-2">
        <h3 className="text-3xl font-bold text-slate-100">{value}</h3>
        {trend && (
          <span className="text-xs font-medium text-emerald-400 flex items-center gap-1">
            <TrendingUp className="w-3 h-3" /> {trend}
          </span>
        )}
      </div>
    </div>
    <div className={`p-4 rounded-xl ${colorClass}`}>
      <Icon className="w-6 h-6" />
    </div>
  </div>
);

export const Dashboard = () => {
  return (
    <div className="flex flex-col space-y-8 max-w-7xl mx-auto w-full">
      <div>
        <h1 className="text-2xl font-semibold text-slate-100">System Dashboard</h1>
        <p className="text-sm text-slate-400 mt-1">Overview of your Continuous KYC autonomous auditing system.</p>
      </div>

      {/* Top Stats */}
      <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-6">
        <StatCard 
          title="Active Alerts" 
          value="24" 
          trend="+3 today"
          icon={AlertTriangle}
          colorClass="bg-red-500/10 text-red-400 border border-red-500/20"
        />
        <StatCard 
          title="Entities Monitored" 
          value="1,248" 
          trend="+12 this week"
          icon={Users}
          colorClass="bg-brand-500/10 text-brand-400 border border-brand-500/20"
        />
        <StatCard 
          title="Pending SARs" 
          value="5" 
          icon={FileText}
          colorClass="bg-orange-500/10 text-orange-400 border border-orange-500/20"
        />
        <StatCard 
          title="System Health" 
          value="99.9%" 
          icon={ShieldCheck}
          colorClass="bg-emerald-500/10 text-emerald-400 border border-emerald-500/20"
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
            {[
              { time: '10 mins ago', title: 'New alert generated for Acme Holdings LLC', type: 'alert' },
              { time: '1 hour ago', title: 'SAR draft completed for Globex Corp', type: 'sar' },
              { time: '2 hours ago', title: 'Automated review cleared 15 low-risk entities', type: 'system' },
              { time: '5 hours ago', title: 'Daily sanctions list synchronized successfully', type: 'system' },
            ].map((activity, i) => (
              <div key={i} className="flex items-start gap-4 p-4 rounded-lg bg-slate-800/50 border border-slate-700/50">
                <div className={`mt-0.5 w-2 h-2 rounded-full ${
                  activity.type === 'alert' ? 'bg-red-400 shadow-[0_0_8px_rgba(248,113,113,0.6)]' :
                  activity.type === 'sar' ? 'bg-orange-400' : 'bg-brand-400'
                }`} />
                <div>
                  <p className="text-sm font-medium text-slate-200">{activity.title}</p>
                  <p className="text-xs text-slate-500 mt-1">{activity.time}</p>
                </div>
              </div>
            ))}
          </div>
        </div>

        {/* Risk Distribution */}
        <div className="bg-slate-900 border border-slate-800 rounded-xl p-6 flex flex-col">
          <h2 className="text-lg font-semibold text-slate-100 mb-6">Risk Distribution</h2>
          
          <div className="flex-1 flex flex-col justify-center space-y-6">
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-red-400 font-medium">Critical Risk</span>
                <span className="text-slate-400">8%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-red-500 h-2 rounded-full" style={{ width: '8%' }}></div>
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-orange-400 font-medium">High Risk</span>
                <span className="text-slate-400">15%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-orange-500 h-2 rounded-full" style={{ width: '15%' }}></div>
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-yellow-400 font-medium">Medium Risk</span>
                <span className="text-slate-400">32%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-yellow-500 h-2 rounded-full" style={{ width: '32%' }}></div>
              </div>
            </div>
            
            <div>
              <div className="flex justify-between text-sm mb-2">
                <span className="text-emerald-400 font-medium">Low Risk</span>
                <span className="text-slate-400">45%</span>
              </div>
              <div className="w-full bg-slate-800 rounded-full h-2 overflow-hidden">
                <div className="bg-emerald-500 h-2 rounded-full" style={{ width: '45%' }}></div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
