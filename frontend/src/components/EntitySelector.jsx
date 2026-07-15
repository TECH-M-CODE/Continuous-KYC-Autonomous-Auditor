import React, { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { Link } from 'react-router-dom';
import { apiClient } from '../api/client';
import { Search, Building2, User, Loader2 } from 'lucide-react';
import clsx from 'clsx';

const BAND_DOT = {
  CRITICAL: 'bg-red-400',
  HIGH:     'bg-orange-400',
  MEDIUM:   'bg-yellow-400',
  LOW:      'bg-emerald-400',
};

/**
 * Searchable entity list sidebar.
 * `basePath` — prefix for navigation links e.g. "/timeline" or "/audit"
 * `selectedId` — currently selected entity id (highlights the row)
 */
export const EntitySelector = ({ basePath = '/timeline', selectedId = null }) => {
  const [search, setSearch] = useState('');

  const { data: entities = [], isLoading } = useQuery({
    queryKey: ['watchlist'],
    queryFn: apiClient.getWatchlist,
    staleTime: 30_000,
  });

  const filtered = useMemo(() => {
    if (!search.trim()) return entities;
    const q = search.toLowerCase();
    return entities.filter(e =>
      e.name?.toLowerCase().includes(q) ||
      e.id?.toLowerCase().includes(q) ||
      e.type?.toLowerCase().includes(q)
    );
  }, [entities, search]);

  return (
    <div className="flex flex-col h-full w-full">
      {/* Search */}
      <div className="relative mb-3">
        <Search className="absolute left-2.5 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-slate-500" />
        <input
          type="text"
          placeholder="Search entities…"
          value={search}
          onChange={e => setSearch(e.target.value)}
          className="w-full pl-8 pr-3 py-2 bg-slate-800/60 border border-slate-700/60 rounded-lg text-xs text-slate-200 placeholder-slate-500 focus:outline-none focus:border-brand-500/60"
        />
      </div>

      {/* Count */}
      <p className="text-xs text-slate-500 mb-2 px-0.5">
        {isLoading ? 'Loading…' : `${filtered.length} entities`}
      </p>

      {/* List */}
      <div className="flex-1 overflow-y-auto space-y-1">
        {isLoading && (
          <div className="flex justify-center py-8">
            <Loader2 className="w-5 h-5 text-brand-400 animate-spin" />
          </div>
        )}
        {filtered.map(entity => {
          const isSelected = entity.id === selectedId;
          const band = entity.risk_band || 'LOW';
          const dot  = BAND_DOT[band] || 'bg-slate-500';
          const Icon = entity.type === 'Person' ? User : Building2;

          return (
            <Link
              key={entity.id}
              to={`${basePath}/${entity.id}`}
              className={clsx(
                'flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-xs transition-all group',
                isSelected
                  ? 'bg-brand-500/15 border border-brand-500/30 text-brand-300'
                  : 'text-slate-400 hover:bg-slate-800/60 hover:text-slate-200 border border-transparent'
              )}
            >
              <div className={clsx('w-1.5 h-1.5 rounded-full shrink-0', dot)} />
              <Icon className={clsx('w-3.5 h-3.5 shrink-0', isSelected ? 'text-brand-400' : 'text-slate-600 group-hover:text-slate-400')} />
              <div className="flex-1 min-w-0">
                <p className="truncate font-medium">{entity.name}</p>
                <p className="text-slate-600 font-mono text-[10px] truncate">{entity.id}</p>
              </div>
              <span className={clsx(
                'text-[10px] font-semibold px-1.5 py-0.5 rounded shrink-0',
                band === 'CRITICAL' ? 'text-red-400 bg-red-500/10' :
                band === 'HIGH'     ? 'text-orange-400 bg-orange-500/10' :
                band === 'MEDIUM'   ? 'text-yellow-400 bg-yellow-500/10' :
                                      'text-emerald-400 bg-emerald-500/10'
              )}>
                {entity.risk_score ?? '—'}
              </span>
            </Link>
          );
        })}
        {!isLoading && filtered.length === 0 && (
          <p className="text-xs text-slate-600 text-center py-8">No entities match "{search}"</p>
        )}
      </div>
    </div>
  );
};

export default EntitySelector;
