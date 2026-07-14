import React from 'react';
import { NavLink, Outlet } from 'react-router-dom';
import { useSSE } from '../hooks/useSSE';
import { 
  Bell, 
  Activity, 
  FileText, 
  History, 
  ShieldAlert, 
  Settings,
  Menu
} from 'lucide-react';
import clsx from 'clsx';

export const Layout = () => {
  const { connected } = useSSE(); // Hook into SSE to show status dot

  const navItems = [
    { name: 'Alert Queue', path: '/', icon: Bell },
    { name: 'Entity Timeline', path: '/timeline', icon: Activity },
    { name: 'SAR Review', path: '/sar', icon: FileText },
    { name: 'Audit Trail', path: '/audit', icon: History },
    { name: 'Admin Watchlist', path: '/watchlist', icon: ShieldAlert },
  ];

  return (
    <div className="flex h-screen bg-slate-950 text-slate-300 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 bg-slate-900 border-r border-slate-800 flex flex-col hidden md:flex">
        <div className="p-4 border-b border-slate-800 flex items-center gap-3">
          <div className="w-8 h-8 rounded bg-brand-600 flex items-center justify-center text-white font-bold">
            CX
          </div>
          <div>
            <h1 className="text-sm font-semibold text-slate-100 tracking-wide">CXKYC Auditor</h1>
            <p className="text-xs text-slate-500">Continuous KYC System</p>
          </div>
        </div>
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-lg text-sm font-medium transition-colors",
                isActive 
                  ? "bg-brand-500/10 text-brand-400" 
                  : "text-slate-400 hover:bg-slate-800 hover:text-slate-200"
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
        
        <div className="p-4 border-t border-slate-800">
          <button className="flex items-center gap-3 px-3 py-2 text-sm text-slate-400 hover:text-slate-200 transition-colors w-full">
            <Settings className="w-4 h-4" />
            System Config
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-14 bg-slate-900/50 border-b border-slate-800 flex items-center justify-between px-6 backdrop-blur-sm z-10">
          <div className="flex items-center gap-4">
            <button className="md:hidden text-slate-400 hover:text-slate-200">
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-sm font-medium text-slate-200">Hackathon Challenge 3</h2>
          </div>
          
          <div className="flex items-center gap-4">
            {/* System Status Dot */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-slate-800/50 border border-slate-700/50">
              <span className="relative flex h-2.5 w-2.5">
                <span className={clsx(
                  "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                  connected ? "bg-green-400" : "bg-red-400"
                )}></span>
                <span className={clsx(
                  "relative inline-flex rounded-full h-2.5 w-2.5",
                  connected ? "bg-green-500" : "bg-red-500"
                )}></span>
              </span>
              <span className="text-xs font-medium text-slate-300">
                {connected ? 'Live' : 'Disconnected'}
              </span>
            </div>
            
            <div className="w-8 h-8 rounded-full bg-slate-800 border border-slate-700 overflow-hidden flex items-center justify-center">
              <span className="text-xs font-medium text-slate-400">D5</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-slate-950 p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};
