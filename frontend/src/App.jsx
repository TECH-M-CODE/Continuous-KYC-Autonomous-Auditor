<<<<<<< HEAD
import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { AlertQueue } from './pages/AlertQueue';
import { EntityTimeline } from './pages/EntityTimeline';
import { SARReview } from './pages/SARReview';
import { AuditTrail } from './pages/AuditTrail';
import { AdminWatchlist } from './pages/AdminWatchlist';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<AlertQueue />} />
          <Route path="timeline" element={<EntityTimeline />} />
          <Route path="sar" element={<SARReview />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="watchlist" element={<AdminWatchlist />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;
=======
import React, { useState, useEffect } from 'react'

function App() {
  const [stats, setStats] = useState({
    totalEntities: 100,
    watchedEntities: 70,
    activeAlerts: 12,
    sarsPending: 4,
    systemStatus: 'Optimal'
  })

  return (
    <div className="min-h-screen bg-slate-950 text-slate-100 font-sans flex flex-col selection:bg-indigo-500 selection:text-white">
      {/* Background decoration */}
      <div className="absolute top-0 left-1/4 w-96 h-96 bg-indigo-500/10 rounded-full blur-3xl pointer-events-none"></div>
      <div className="absolute bottom-0 right-1/4 w-96 h-96 bg-emerald-500/5 rounded-full blur-3xl pointer-events-none"></div>

      {/* Navigation Header */}
      <header className="sticky top-0 z-50 backdrop-blur-md bg-slate-950/80 border-b border-slate-800/80 px-6 py-4 flex items-center justify-between">
        <div className="flex items-center space-x-3">
          <div className="bg-gradient-to-tr from-indigo-500 to-purple-600 p-2.5 rounded-xl shadow-lg shadow-indigo-500/30">
            <svg className="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
              <path strokeLinecap="round" strokeLinejoin="round" strokeWidth="2.5" d="M9 12l2 2 4-4m5.618-4.016A11.955 11.955 0 0112 2.944a11.955 11.955 0 01-8.618 3.04A12.02 12.02 0 003 9c0 5.591 3.824 10.29 9 11.622 5.176-1.332 9-6.03 9-11.622 0-1.042-.133-2.052-.382-3.016z"></path>
            </svg>
          </div>
          <div>
            <h1 className="text-xl font-bold tracking-tight bg-gradient-to-r from-white via-slate-200 to-slate-400 bg-clip-text text-transparent">
              Sentinel<span className="text-indigo-400">AI</span>
            </h1>
            <p className="text-[10px] text-slate-500 uppercase tracking-widest font-semibold">Continuous KYC Auditor</p>
          </div>
        </div>
        
        <div className="flex items-center space-x-4">
          <div className="flex items-center space-x-2 bg-slate-900/90 border border-slate-800 px-3.5 py-1.5 rounded-full text-xs">
            <span className="w-2 h-2 rounded-full bg-emerald-400 animate-pulse"></span>
            <span className="text-slate-400 font-medium">System Status:</span>
            <span className="text-emerald-400 font-semibold">{stats.systemStatus}</span>
          </div>
          <button className="bg-slate-900 hover:bg-slate-850 border border-slate-800 hover:border-slate-700 transition-all text-xs font-semibold px-4 py-2 rounded-xl text-slate-300">
            L1 Analyst Panel
          </button>
        </div>
      </header>

      {/* Main Content Dashboard */}
      <main className="flex-1 max-w-7xl w-full mx-auto p-6 md:p-8 space-y-8 z-10">
        
        {/* Hero Section */}
        <section className="bg-gradient-to-br from-slate-900 to-slate-950 border border-slate-800/80 rounded-3xl p-6 md:p-8 relative overflow-hidden shadow-2xl">
          <div className="absolute -right-16 -top-16 w-64 h-64 bg-indigo-500/10 rounded-full blur-2xl"></div>
          <div className="relative z-10 max-w-2xl space-y-4">
            <div className="inline-flex items-center space-x-1.5 bg-indigo-500/10 text-indigo-400 border border-indigo-500/20 px-3 py-1 rounded-full text-xs font-medium">
              <span>🚀 Sprint 1 Active</span>
            </div>
            <h2 className="text-3xl md:text-4xl font-extrabold tracking-tight text-white leading-tight">
              Enterprise Risk Intelligence &amp; AML Monitoring
            </h2>
            <p className="text-slate-400 text-sm md:text-base leading-relaxed">
              Automated entity scoring, continuous regulatory watchlists mapping, and tamper-evident audit log ledger. Seeded and optimized for continuous operations.
            </p>
          </div>
        </section>

        {/* Stats Grid */}
        <section className="grid grid-cols-2 md:grid-cols-4 gap-4">
          {[
            { label: 'Seeded KYC Profiles', value: stats.totalEntities, icon: '🏢', color: 'from-blue-500/10 to-indigo-500/5', border: 'border-blue-500/20' },
            { label: 'Watched Entities', value: stats.watchedEntities, icon: '👁️', color: 'from-amber-500/10 to-orange-500/5', border: 'border-amber-500/20' },
            { label: 'Pending Alerts', value: stats.activeAlerts, icon: '⚠️', color: 'from-rose-500/10 to-pink-500/5', border: 'border-rose-500/20' },
            { label: 'Drafted SARs', value: stats.sarsPending, icon: '📝', color: 'from-violet-500/10 to-fuchsia-500/5', border: 'border-violet-500/20' }
          ].map((item, index) => (
            <div key={index} className={`bg-gradient-to-br ${item.color} border ${item.border} rounded-2xl p-5 flex flex-col justify-between shadow-lg relative overflow-hidden transition-all hover:scale-[1.02]`}>
              <div className="flex justify-between items-start">
                <span className="text-2xl">{item.icon}</span>
                <span className="text-[10px] uppercase font-bold text-slate-500 tracking-wider">Metric</span>
              </div>
              <div className="mt-4">
                <p className="text-3xl font-extrabold text-white">{item.value}</p>
                <p className="text-xs text-slate-400 mt-1">{item.label}</p>
              </div>
            </div>
          ))}
        </section>

        {/* Main Columns */}
        <section className="grid grid-cols-1 lg:grid-cols-3 gap-6">
          {/* Main Module Controls */}
          <div className="lg:col-span-2 space-y-6">
            <h3 className="text-lg font-bold text-white flex items-center space-x-2">
              <span>🎛️ Bounded Context Modules</span>
            </h3>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {[
                { title: 'Alert Queue', desc: 'Monitor and review suspicious risk events.', count: '12 active', active: true, tag: 'L1/L2' },
                { title: 'Audit Trail', desc: 'Cryptographically hashed immutable ledger.', count: 'Secured', active: false, tag: 'Tamper-Proof' },
                { title: 'SAR Review', desc: 'AI-drafted regulatory reports editor.', count: '4 drafts', active: false, tag: 'Reporter' },
                { title: 'Decision Graph', desc: 'Interactive React Flow entity risk maps.', count: 'Visual', active: false, tag: 'Explainable' }
              ].map((mod, index) => (
                <div key={index} className="bg-slate-900/90 border border-slate-800 hover:border-slate-700/80 transition-all rounded-2xl p-5 flex flex-col justify-between space-y-4 hover:shadow-xl hover:shadow-indigo-500/5">
                  <div className="space-y-1.5">
                    <div className="flex items-center justify-between">
                      <h4 className="font-bold text-slate-200">{mod.title}</h4>
                      <span className="text-[10px] bg-slate-800 border border-slate-700 text-slate-400 font-semibold px-2 py-0.5 rounded-md">{mod.tag}</span>
                    </div>
                    <p className="text-xs text-slate-400 leading-relaxed">{mod.desc}</p>
                  </div>
                  <div className="flex items-center justify-between pt-2">
                    <span className="text-[10px] text-slate-500 font-semibold uppercase">{mod.count}</span>
                    <button className="text-xs text-indigo-400 hover:text-indigo-300 font-bold transition-colors">Open Module &rarr;</button>
                  </div>
                </div>
              ))}
            </div>
          </div>

          {/* Activity / Seeding Log */}
          <div className="bg-slate-900/90 border border-slate-800 rounded-3xl p-5 flex flex-col space-y-4 h-[350px]">
            <h3 className="text-lg font-bold text-white flex items-center space-x-2">
              <span>📜 Seeding Logs &amp; Events</span>
            </h3>
            
            <div className="flex-1 overflow-y-auto space-y-3.5 pr-1 text-xs">
              {[
                { time: '14:29:20', text: 'Checked folder for kyc_profiles CSV data' },
                { time: '14:29:20', text: 'Kaggle keys not found; running fallback generator' },
                { time: '14:29:20', text: 'Generated 100 corporate profiles at data/kyc_profiles/' },
                { time: '14:29:20', text: 'Loaded risk configuration parameters from policy.yaml' },
                { time: '14:29:20', text: 'Calculated baseline risk scores using PEP/FATF/Sector mappings' },
                { time: '14:29:20', text: 'Determined watched list state for 70 high-risk profiles' },
                { time: '14:29:21', text: 'Successfully seeded 100 entities via UnitOfWork' },
                { time: '14:29:21', text: 'SQLite database connection successfully initialized (WAL Mode)' }
              ].map((log, index) => (
                <div key={index} className="flex space-x-3.5 items-start">
                  <span className="text-[10px] text-slate-500 font-mono pt-0.5">{log.time}</span>
                  <p className="text-slate-400 leading-relaxed">{log.text}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

      </main>

      {/* Footer */}
      <footer className="border-t border-slate-900 bg-slate-950/40 py-6 px-6 text-center text-xs text-slate-650">
        <p>&copy; 2026 SentinelAI. Built for Tech Mahindra CODE Hackathon.</p>
      </footer>
    </div>
  )
}

export default App
>>>>>>> 66632a0777426df4be40828afe8348ad78c2660d
