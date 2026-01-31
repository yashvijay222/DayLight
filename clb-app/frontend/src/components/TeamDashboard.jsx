import React, { useEffect, useState } from "react";

import { getTeamMetrics } from "../services/api";

const TeamDashboard = () => {
  const [metrics, setMetrics] = useState(null);

  useEffect(() => {
    const load = async () => {
      const { data } = await getTeamMetrics();
      setMetrics(data);
    };
    load();
  }, []);

  if (!metrics) {
    return (
      <div className="card">
        <div className="text-slate-400 text-sm">Loading team metrics...</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-2">Team Health</div>
      <div className="grid grid-cols-2 gap-4 text-sm">
        <div>
          <div className="text-slate-400">Health Score</div>
          <div className="text-2xl font-semibold">{metrics.health_score}</div>
        </div>
        <div>
          <div className="text-slate-400">High Risk %</div>
          <div className="text-2xl font-semibold">{metrics.high_risk_percentage}%</div>
        </div>
        <div>
          <div className="text-slate-400">Avg Context Switches</div>
          <div className="text-xl font-semibold">{metrics.avg_context_switches}</div>
        </div>
      </div>
      <div className="mt-3 text-xs text-slate-400 space-y-1">
        {metrics.insights?.map((insight, idx) => (
          <div key={idx}>• {insight}</div>
        ))}
      </div>
    </div>
  );
};

export default TeamDashboard;
