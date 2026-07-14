import React, { useState } from 'react';
import { ShieldAlert, Zap, Search, ToggleLeft, ToggleRight } from 'lucide-react';
import { StatusBadge } from '../components/StatusBadge';

const initialWatchlist = [
  { id: 'ent-881', name: 'Acme Holdings LLC', country: 'Cayman Islands', sector_risk: 'High', score: 85, watched: true },
  { id: 'ent-219', name: 'Globex Corp', country: 'Switzerland', sector_risk: 'Medium', score: 45, watched: true },
  { id: 'ent-332', name: 'Stark Industries', country: 'USA', sector_risk: 'Low', score: 20, watched: false },
  { id: 'ent-991', name: 'Wayne Enterprises', country: 'USA', sector_risk: 'Low', score: 15, watched: false },
];

export const AdminWatchlist = () => {
  const [entities, setEntities] = useState(initialWatchlist);
  const [injectingId, setInjectingId] = useState(null);

  const toggleWatch = (id) => {
    setEntities(entities.map(e => e.id === id ? { ...e, watched: !e.watched } : e));
  };

  const handleInject = (id) => {
    setInjectingId(id);
    setTimeout(() => {
      setInjectingId(null);
      // In Sprint 3, this will call POST /api/test/inject
    }, 1000);
  };

  return (
    <div className="flex flex-col h-full space-y-6 max-w-6xl mx-auto w-full">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold text-slate-100 flex items-center gap-2">
            <ShieldAlert className="w-6 h-6 text-brand-400" />
            Admin Watchlist & Testing
          </h1>
          <p className="text-sm text-slate-400 mt-1">Manage entity monitoring and trigger synthetic events for demo.</p>
        </div>
        
        <div className="relative">
          <Search className="w-4 h-4 text-slate-500 absolute left-3 top-1/2 -translate-y-1/2" />
          <input 
            type="text" 
            placeholder="Search entities..." 
            className="pl-9 pr-4 py-2 bg-slate-900 border border-slate-700 rounded-lg text-sm text-slate-200 focus:outline-none focus:border-brand-500 w-64"
          />
        </div>
      </div>

      <div className="bg-slate-900 border border-slate-800 rounded-xl flex-1 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm whitespace-nowrap">
            <thead className="bg-slate-800/50 text-slate-400 border-b border-slate-800">
              <tr>
                <th className="px-6 py-4 font-medium">Entity</th>
                <th className="px-6 py-4 font-medium">Jurisdiction</th>
                <th className="px-6 py-4 font-medium">Sector Risk</th>
                <th className="px-6 py-4 font-medium">Base Score</th>
                <th className="px-6 py-4 font-medium text-center">Watched</th>
                <th className="px-6 py-4 font-medium text-right">Actions</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-800/50">
              {entities.map(entity => (
                <tr key={entity.id} className="hover:bg-slate-800/30 transition-colors">
                  <td className="px-6 py-4">
                    <div className="font-medium text-slate-200">{entity.name}</div>
                    <div className="text-xs text-slate-500 font-mono mt-0.5">{entity.id}</div>
                  </td>
                  <td className="px-6 py-4 text-slate-300">{entity.country}</td>
                  <td className="px-6 py-4">
                    <StatusBadge 
                      band={entity.sector_risk === 'High' ? 'high' : entity.sector_risk === 'Medium' ? 'medium' : 'low'} 
                    />
                  </td>
                  <td className="px-6 py-4 font-mono text-slate-400">{entity.score}</td>
                  <td className="px-6 py-4 text-center">
                    <button 
                      onClick={() => toggleWatch(entity.id)}
                      className={`inline-flex items-center justify-center transition-colors ${entity.watched ? 'text-brand-400' : 'text-slate-600'}`}
                    >
                      {entity.watched ? <ToggleRight className="w-8 h-8" /> : <ToggleLeft className="w-8 h-8" />}
                    </button>
                  </td>
                  <td className="px-6 py-4 text-right">
                    <button 
                      onClick={() => handleInject(entity.id)}
                      disabled={injectingId === entity.id}
                      className="inline-flex items-center gap-1.5 px-3 py-1.5 bg-purple-500/10 text-purple-400 hover:bg-purple-500/20 border border-purple-500/20 rounded-md text-xs font-medium transition-colors"
                    >
                      <Zap className={`w-3.5 h-3.5 ${injectingId === entity.id ? 'animate-pulse' : ''}`} />
                      Inject Event
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
};
