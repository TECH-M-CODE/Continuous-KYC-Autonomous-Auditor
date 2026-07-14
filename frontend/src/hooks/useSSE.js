import { useState, useEffect, useRef } from 'react';
import { useQueryClient } from '@tanstack/react-query';

export const useSSE = (url = '/api/stream') => {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const [events, setEvents] = useState([]);
  const eventSourceRef = useRef(null);
  const queryClient = useQueryClient();

  useEffect(() => {
    const sse = new EventSource(url);
    eventSourceRef.current = sse;

    sse.onopen = () => setConnected(true);
    
    sse.onerror = (err) => {
      console.error('SSE Error:', err);
      setConnected(false);
    };

    const handleEvent = (type) => (e) => {
      try {
        const data = JSON.parse(e.data);
        const eventObj = { type, data, timestamp: new Date() };
        setLastEvent(eventObj);
        setEvents((prev) => [eventObj, ...prev].slice(0, 100)); // Keep last 100

        // Invalidate specific queries based on event type to trigger React Query refetch
        if (type === 'alert.new' || type === 'alert.updated') {
          queryClient.invalidateQueries({ queryKey: ['alerts'] });
        }
        if (type === 'entity.updated') {
          queryClient.invalidateQueries({ queryKey: ['entity'] });
        }
        if (type === 'sar.ready') {
          queryClient.invalidateQueries({ queryKey: ['sar'] });
        }
        
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    };

    sse.addEventListener('alert.new', handleEvent('alert.new'));
    sse.addEventListener('alert.updated', handleEvent('alert.updated'));
    sse.addEventListener('entity.updated', handleEvent('entity.updated'));
    sse.addEventListener('sar.ready', handleEvent('sar.ready'));

    sse.onmessage = (e) => {
      if (e.data === 'ping' || e.data.includes('heartbeat')) return;
      handleEvent('message')(e);
    };

    return () => {
      sse.close();
      eventSourceRef.current = null;
    };
  }, [url, queryClient]);

  return { connected, lastEvent, events };
};
