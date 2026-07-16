import React, { createContext, useContext, useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useToast } from '../components/ToastContext';

/**
 * ONE EventSource for the whole app.
 *
 * Previously every component that called useSSE() opened its own EventSource
 * (Layout + LiveFeed + AlertQueue + PipelineProgress = 4 persistent streams).
 * Browsers cap concurrent HTTP/1.1 connections per host at ~6, so those
 * long-lived streams starved the pool: subsequent /api refetches queued forever,
 * the UI hung with stale/blank panels, and the connection badge flapped to
 * "Disconnected". Sharing a single stream via context fixes that at the source
 * and also stops N-fold re-renders on every event.
 */
const SSEContext = createContext({
  connectionState: 'disconnected',
  connected: false,
  lastEvent: null,
  events: [],
});

export const SSEProvider = ({ children, url = '/api/v1/stream' }) => {
  const [connectionState, setConnectionState] = useState('disconnected');
  const [lastEvent, setLastEvent] = useState(null);
  const [events, setEvents] = useState([]);
  const eventSourceRef = useRef(null);
  const queryClient = useQueryClient();
  const { addToast } = useToast();

  useEffect(() => {
    setConnectionState('connecting');
    const sse = new EventSource(url);
    eventSourceRef.current = sse;

    sse.onopen = () => {
      setConnectionState((prev) => {
        if (prev === 'connecting' || prev === 'disconnected') {
          // Refresh the live views specifically. A blanket invalidateQueries()
          // here refetches everything at once and visibly blanks the page.
          queryClient.invalidateQueries({ queryKey: ['alerts'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
        }
        return 'connected';
      });
    };

    sse.onerror = () => {
      // EventSource reconnects on its own.
      setConnectionState('connecting');
    };

    const handleEvent = (type) => (e) => {
      try {
        const data = JSON.parse(e.data);
        const eventObj = { id: `${Date.now()}-${Math.random()}`, type, data, timestamp: new Date() };
        setLastEvent(eventObj);
        setEvents((prev) => {
          // StrictMode protection: drop identical payloads arriving back-to-back.
          if (prev.length > 0) {
            const last = prev[0];
            if (last.type === type && JSON.stringify(last.data) === JSON.stringify(data)) {
              if (new Date().getTime() - last.timestamp.getTime() < 1000) return prev;
            }
          }
          return [eventObj, ...prev].slice(0, 100);
        });

        if (type === 'alert.new' || type === 'alert.updated') {
          queryClient.invalidateQueries({ queryKey: ['alerts'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-audit-verify'] });
        }
        if (type === 'entity.updated') {
          queryClient.invalidateQueries({ queryKey: ['entity'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-entities'] });
          queryClient.invalidateQueries({ queryKey: ['watchlist'] });
        }
        if (type === 'sar.ready') {
          queryClient.invalidateQueries({ queryKey: ['sars'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-sars'] });
          addToast({
            type: 'sar',
            title: 'SAR Draft Ready',
            message: 'A new SAR draft is ready for review.',
            actionText: 'Review now',
            actionLink: '/sar',
            duration: 10000,
          });
        }
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    };

    sse.addEventListener('alert.new', handleEvent('alert.new'));
    sse.addEventListener('alert.updated', handleEvent('alert.updated'));
    sse.addEventListener('entity.updated', handleEvent('entity.updated'));
    sse.addEventListener('sar.ready', handleEvent('sar.ready'));
    // Per-agent pipeline progress — informational only, no query invalidation.
    sse.addEventListener('pipeline.progress', handleEvent('pipeline.progress'));

    return () => {
      sse.close();
      eventSourceRef.current = null;
      setConnectionState('disconnected');
    };
  }, [url, queryClient, addToast]);

  const value = {
    connectionState,
    connected: connectionState === 'connected',
    lastEvent,
    events,
  };

  return <SSEContext.Provider value={value}>{children}</SSEContext.Provider>;
};

// Consumers keep the exact same API — they just share one stream now.
export const useSSE = () => useContext(SSEContext);
