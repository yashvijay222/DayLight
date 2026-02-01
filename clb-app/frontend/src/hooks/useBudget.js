import { useEffect, useState } from "react";

import { getDailyBudget } from "../services/api";

export const useBudget = () => {
  const [budget, setBudget] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = async () => {
    setLoading(true);
    const { data, error: err } = await getDailyBudget();
    if (err) {
      setError(err);
    } else {
      setBudget(data);
    }
    setLoading(false);
  };

  useEffect(() => {
    load();
  }, []);

  return { budget, loading, error, reload: load };
};
