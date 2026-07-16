import { useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { useToast } from '../components/ToastContext';

export const useSSE = (url = '/api/v1/stream') => {
  const [connectionState, setConnectionState] = useState('disconnected'); // 'connected', 'connecting', 'disconnected'
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
          // Reconnect: refresh the live data views specifically. A blanket
          // invalidateQueries() here refetches *everything* including the
          // currently-mounted page, which caused a visible blank flash.
          queryClient.invalidateQueries({ queryKey: ['alerts'] });
          queryClient.invalidateQueries({ queryKey: ['sars'] });
        }
        return 'connected';
      });
    };
    
    sse.onerror = (err) => {
      console.error('SSE Error:', err);
      // EventSource tries to reconnect automatically
      setConnectionState('connecting');
    };

    const handleEvent = (type) => (e) => {
      try {
        const data = JSON.parse(e.data);
        const eventObj = { id: Date.now() + Math.random(), type, data, timestamp: new Date() };
        setLastEvent(eventObj);
        setEvents((prev) => {
          // StrictMode protection: deduplicate identical payloads occurring extremely close in time
          if (prev.length > 0) {
            const last = prev[0];
            if (last.type === type && JSON.stringify(last.data) === JSON.stringify(data)) {
              if (new Date().getTime() - last.timestamp.getTime() < 1000) {
                return prev;
              }
            }
          }
          return [eventObj, ...prev].slice(0, 100);
        }); // Keep last 100

        // Invalidate specific queries based on event type to trigger React Query refetch
        if (type === 'alert.new' || type === 'alert.updated') {
          queryClient.invalidateQueries({ queryKey: ['alerts'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-alerts'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-audit-verify'] });
        }
        if (type === 'entity.updated') {
          queryClient.invalidateQueries({ queryKey: ['entity'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-entities'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-audit-verify'] });
        }
        if (type === 'sar.ready') {
          queryClient.invalidateQueries({ queryKey: ['sar'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-sars'] });
          queryClient.invalidateQueries({ queryKey: ['dashboard-audit-verify'] });
          addToast({
            type: 'sar',
            title: 'SAR Draft Ready',
            message: `A new SAR draft is ready for review.`,
            actionText: 'Review now',
            actionLink: '/sar', // Assuming there's only one page for now, or route to specific SAR
            duration: 10000
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
    // Per-agent pipeline progress — purely informational (drives the live
    // inject stepper); does not invalidate any query.
    sse.addEventListener('pipeline.progress', handleEvent('pipeline.progress'));

    sse.onmessage = (e) => {
      if (e.data === 'ping' || e.data.includes('heartbeat')) return;
      handleEvent('message')(e);
    };

    return () => {
      sse.close();
      eventSourceRef.current = null;
      setConnectionState('disconnected');
    };
  }, [url, queryClient, addToast]);

  return { connectionState, connected: connectionState === 'connected', lastEvent, events };
};

