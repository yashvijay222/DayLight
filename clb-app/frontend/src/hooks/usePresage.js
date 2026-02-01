import { useState } from "react";

import { endSage, startSage } from "../services/api";

/**
 * usePresage hook - manages Sage session lifecycle via REST API.
 * 
 * Note: Real-time metrics streaming is now handled by WebSocket connections
 * directly in the SageMode component. This hook only manages session
 * start/stop via REST endpoints.
 */
export const usePresage = () => {
  const [sessionId, setSessionId] = useState(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState(null);

  /**
   * Start a new Sage session.
   * @param {string|null} eventId - Optional event ID to associate with the session
   * @returns {Promise<{session_id: string}|undefined>}
   */
  const start = async (eventId) => {
    try {
      setError(null);
      const { data, error: err } = await startSage(eventId);
      if (err) {
        setError(err);
        return;
      }
      setSessionId(data.session_id);
      setActive(true);
      return data;
    } catch (err) {
      setError(err.message || "Failed to start session");
      return;
    }
  };

  /**
   * Stop the current Sage session.
   * @returns {Promise<{session: object}|undefined>}
   */
  const stop = async () => {
    if (!sessionId) return;
    
    try {
      setError(null);
      const { data, error: err } = await endSage(sessionId);
      if (err) {
        setError(err);
        return;
      }
      setActive(false);
      setSessionId(null);
      return data;
    } catch (err) {
      setError(err.message || "Failed to end session");
      // Still mark as inactive even on error
      setActive(false);
      setSessionId(null);
      return;
    }
  };

  return { sessionId, active, error, start, stop };
};
