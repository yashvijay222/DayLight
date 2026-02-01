import { useEffect, useState } from "react";

import { endSage, getSageReading, startSage } from "../services/api";

export const usePresage = () => {
  const [sessionId, setSessionId] = useState(null);
  const [reading, setReading] = useState(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);

  const start = async (eventId) => {
    const { data, error: err } = await startSage(eventId);
    if (err) {
      setError(err);
      return;
    }
    setSessionId(data.session_id);
    setActive(true);
  };

  const stop = async () => {
    if (!sessionId) return;
    const { data, error: err } = await endSage(sessionId);
    if (err) {
      setError(err);
      return;
    }
    setActive(false);
    return data;
  };

  useEffect(() => {
    if (!active || !sessionId) return;
    const timer = setInterval(async () => {
      const { data, error: err } = await getSageReading(sessionId);
      if (err) {
        setError(err);
      } else {
        setReading(data.reading);
      }
    }, 2000);
    return () => clearInterval(timer);
  }, [active, sessionId]);

  return { sessionId, reading, active, error, start, stop };
};
