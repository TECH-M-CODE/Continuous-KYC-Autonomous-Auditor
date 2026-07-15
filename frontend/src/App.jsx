import React from 'react';
import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { Layout } from './components/Layout';
import { Dashboard } from './pages/Dashboard';
import { AlertQueue } from './pages/AlertQueue';
import { EntityTimeline } from './pages/EntityTimeline';
import { SARReview } from './pages/SARReview';
import { AuditTrail } from './pages/AuditTrail';
import { AdminWatchlist } from './pages/AdminWatchlist';
import TraceView from './pages/TraceView';

function App() {
  return (
    <BrowserRouter>
      <Routes>
        <Route path="/" element={<Layout />}>
          <Route index element={<Dashboard />} />
          <Route path="alerts" element={<AlertQueue />} />
          <Route path="timeline/:entityId?" element={<EntityTimeline />} />
          <Route path="sar/:id?" element={<SARReview />} />
          <Route path="audit" element={<AuditTrail />} />
          <Route path="watchlist" element={<AdminWatchlist />} />
          <Route path="alerts/:id/trace" element={<TraceView />} />
        </Route>
      </Routes>
    </BrowserRouter>
  );
}

export default App;

