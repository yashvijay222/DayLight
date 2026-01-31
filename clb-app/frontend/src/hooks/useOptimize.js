import { useEffect, useState } from "react";

import { applyAllSuggestions, applySuggestion, getOptimizationSuggestions } from "../services/api";

export const useOptimize = () => {
  const [suggestions, setSuggestions] = useState([]);
  const [weeklyDebt, setWeeklyDebt] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    const { data, error: err } = await getOptimizationSuggestions();
    if (err) {
      setError(err);
    } else {
      setSuggestions(data.suggestions || []);
      setWeeklyDebt(data.weekly_debt || 0);
    }
    setLoading(false);
  };

  const apply = async (id) => {
    const { error: err } = await applySuggestion(id);
    if (err) {
      setError(err);
      return;
    }
    await load();
  };

  const applyAll = async (ids) => {
    const { error: err } = await applyAllSuggestions(ids);
    if (err) {
      setError(err);
      return;
    }
    await load();
  };

  useEffect(() => {
    load();
  }, []);

  return { suggestions, weeklyDebt, loading, error, reload: load, apply, applyAll };
};
