import { useState, useCallback } from "react";

import { getAuthUrl, handleCallback, syncCalendar } from "../services/api";

export const useGoogleCalendar = () => {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [connected, setConnected] = useState(false);

  const connect = useCallback(async () => {
    setLoading(true);
    const { data, error: err } = await getAuthUrl();
    if (err) {
      setError(err);
    } else {
      window.location.href = data.auth_url;
    }
    setLoading(false);
  }, []);

  const finish = useCallback(async (code) => {
    setLoading(true);
    const { error: err } = await handleCallback(code);
    if (err) {
      setError(err);
    } else {
      setConnected(true);
      await syncCalendar();
    }
    setLoading(false);
  }, []);

  return { connect, finish, loading, error, connected };
};
