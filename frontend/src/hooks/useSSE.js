import { useState, useEffect, useRef } from 'react';

export const useSSE = (url = '/api/stream') => {
  const [connected, setConnected] = useState(false);
  const [lastEvent, setLastEvent] = useState(null);
  const [events, setEvents] = useState([]);
  const eventSourceRef = useRef(null);

  useEffect(() => {
    const sse = new EventSource(url);
    eventSourceRef.current = sse;

    sse.onopen = () => setConnected(true);
    
    sse.onerror = (err) => {
      console.error('SSE Error:', err);
      setConnected(false);
    };

    // Listen to specific named events according to our schema
    const handleEvent = (type) => (e) => {
      try {
        const data = JSON.parse(e.data);
        const eventObj = { type, data, timestamp: new Date() };
        setLastEvent(eventObj);
        setEvents((prev) => [eventObj, ...prev].slice(0, 100)); // Keep last 100
      } catch (err) {
        console.error('Failed to parse SSE message', err);
      }
    };

    sse.addEventListener('alert.new', handleEvent('alert.new'));
    sse.addEventListener('alert.updated', handleEvent('alert.updated'));
    sse.addEventListener('sar.ready', handleEvent('sar.ready'));

    // Optional: catch-all message handler for unstructured events
    sse.onmessage = (e) => {
      if (e.data === 'ping' || e.data.includes('heartbeat')) return;
      handleEvent('message')(e);
    };

    return () => {
      sse.close();
      eventSourceRef.current = null;
    };
  }, [url]);

  return { connected, lastEvent, events };
};
