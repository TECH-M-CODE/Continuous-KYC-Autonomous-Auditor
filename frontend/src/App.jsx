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
