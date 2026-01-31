import { useEffect, useState } from "react";

import { fetchEvents, updateFlexibility, deleteEvent as apiDeleteEvent } from "../services/api";

export const useEvents = () => {
  const [events, setEvents] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    const { data, error: err } = await fetchEvents();
    if (err) {
      setError(err);
    } else {
      setEvents(data || []);
    }
    setLoading(false);
  };

  const setFlexibility = async (eventId, payload) => {
    const { error: err } = await updateFlexibility(eventId, payload);
    if (err) {
      setError(err);
      return;
    }
    await load();
  };

  const deleteEvent = async (eventId) => {
    const { error: err } = await apiDeleteEvent(eventId);
    if (err) {
      setError(err);
      return;
    }
    await load();
  };

  useEffect(() => {
    load();
  }, []);

  return { events, loading, error, reload: load, setFlexibility, deleteEvent };
};
