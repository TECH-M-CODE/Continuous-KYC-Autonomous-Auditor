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
  Menu,
  LayoutDashboard
} from 'lucide-react';
import clsx from 'clsx';

export const Layout = () => {
  const { connected, connectionState } = useSSE(); // Hook into SSE to show status dot

  const navItems = [
    { name: 'Dashboard', path: '/', icon: LayoutDashboard },
    { name: 'Alert Queue', path: '/alerts', icon: Bell },
    { name: 'Entity Timeline', path: '/timeline', icon: Activity },
    { name: 'SAR Review', path: '/sar', icon: FileText },
    { name: 'Audit Trail', path: '/audit', icon: History },
    { name: 'Admin Watchlist', path: '/watchlist', icon: ShieldAlert },
  ];

  return (
    <div className="flex h-screen bg-transparent text-slate-700 font-sans overflow-hidden">
      {/* Sidebar */}
      <aside className="w-64 glass-panel m-4 mr-0 flex flex-col hidden md:flex overflow-hidden">
        <div className="p-4 border-b border-white/40 flex items-center gap-3">
          <div className="w-8 h-8 rounded-xl bg-brand-500/20 flex items-center justify-center text-brand-600 font-bold shadow-inner border border-white/50">
            CX
          </div>
          <div>
            <h1 className="text-sm font-bold text-slate-800 tracking-wide">CXKYC Auditor</h1>
            <p className="text-xs text-slate-500 font-medium">Continuous KYC System</p>
          </div>
        </div>
        
        <nav className="flex-1 p-4 space-y-1 overflow-y-auto">
          {navItems.map((item) => (
            <NavLink
              key={item.path}
              to={item.path}
              className={({ isActive }) => clsx(
                "flex items-center gap-3 px-3 py-2.5 rounded-xl text-sm font-semibold transition-all duration-200",
                isActive 
                  ? "bg-brand-500/15 text-brand-700 shadow-sm border border-brand-500/10" 
                  : "text-slate-500 hover:bg-white/40 hover:text-slate-800 hover:shadow-sm"
              )}
            >
              <item.icon className="w-4 h-4" />
              {item.name}
            </NavLink>
          ))}
        </nav>
        
        <div className="p-4 border-t border-white/40">
          <button className="flex items-center gap-3 px-3 py-2 text-sm text-slate-500 hover:text-slate-800 transition-colors w-full font-medium">
            <Settings className="w-4 h-4" />
            System Config
          </button>
        </div>
      </aside>

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0">
        {/* Header */}
        <header className="h-16 mx-4 mt-4 glass-panel flex items-center justify-between px-6 z-10 shrink-0">
          <div className="flex items-center gap-4">
            <button className="md:hidden text-slate-500 hover:text-slate-800">
              <Menu className="w-5 h-5" />
            </button>
            <h2 className="text-sm font-bold text-slate-700">Hackathon Challenge 3</h2>
          </div>
          
          <div className="flex items-center gap-4">
            {/* System Status Dot */}
            <div className="flex items-center gap-2 px-3 py-1.5 rounded-full bg-white/40 border border-white/60 shadow-sm backdrop-blur-md">
              <span className="relative flex h-2.5 w-2.5">
                <span className={clsx(
                  "animate-ping absolute inline-flex h-full w-full rounded-full opacity-75",
                  connectionState === 'connected' ? "bg-emerald-400" : 
                  connectionState === 'connecting' ? "bg-amber-400" : "bg-red-400"
                )}></span>
                <span className={clsx(
                  "relative inline-flex rounded-full h-2.5 w-2.5",
                  connectionState === 'connected' ? "bg-emerald-500" : 
                  connectionState === 'connecting' ? "bg-amber-500" : "bg-red-500"
                )}></span>
              </span>
              <span className="text-xs font-semibold text-slate-600">
                {connectionState === 'connected' ? 'Live' : 
                 connectionState === 'connecting' ? 'Reconnecting...' : 'Disconnected'}
              </span>
            </div>
            
            <div className="w-9 h-9 rounded-full bg-brand-100 border border-brand-200 shadow-inner overflow-hidden flex items-center justify-center">
              <span className="text-xs font-bold text-brand-700">D5</span>
            </div>
          </div>
        </header>

        {/* Page Content */}
        <main className="flex-1 overflow-auto bg-transparent p-6 relative">
          <Outlet />
        </main>
      </div>
    </div>
  );
};

