import {useEffect, useState} from 'react';
import {api} from './api';

export function useDrivingRoute(start, end) {
  const [result, setResult] = useState(null);
  const identical = start.lat === end.lat && start.lng === end.lng;
  const query = new URLSearchParams({
    startLat:start.lat, startLng:start.lng, endLat:end.lat, endLng:end.lng,
  }).toString();

  useEffect(() => {
    if (identical) return;
    const controller = new AbortController();
    const timer = setTimeout(async () => {
      try {
        const route = await api(`/driving-route?${query}`, {signal:controller.signal});
        if (!controller.signal.aborted) setResult({query, route});
      } catch {
        if (!controller.signal.aborted) setResult({query, route:null});
      }
    }, 250);
    return () => {
      clearTimeout(timer);
      controller.abort();
    };
  }, [identical, query]);

  const current = result?.query === query ? result : null;
  return {route: current?.route, loading: !identical && !current};
}
