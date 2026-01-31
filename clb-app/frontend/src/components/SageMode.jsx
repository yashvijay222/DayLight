import React, { useState } from "react";

import { usePresage } from "../hooks/usePresage";

const getStressColor = (stress) => {
  if (stress >= 70) return "text-debt";
  if (stress >= 40) return "text-warning";
  return "text-recovery";
};

const SageMode = ({ events = [], onSessionEnd }) => {
  const { reading, active, start, stop } = usePresage();
  const [lastResult, setLastResult] = useState(null);

  const handleStop = async () => {
    const result = await stop();
    if (result?.session) {
      setLastResult(result.session);
      if (onSessionEnd) onSessionEnd();
    }
  };

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-2">Sage Mode</div>
      <p className="text-xs text-slate-400 mb-3">
        Monitor your cognitive load in real-time during work sessions.
      </p>
      
      {!active && (
        <div className="flex flex-wrap gap-2">
          {events.slice(0, 4).map((event) => (
            <button
              key={event.id}
              className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm"
              onClick={() => {
                setLastResult(null);
                start(event.id);
              }}
            >
              {event.title}
            </button>
          ))}
          <button
            className="px-3 py-1 rounded-lg bg-neutral hover:bg-blue-500 text-sm"
            onClick={() => {
              setLastResult(null);
              start(null);
            }}
          >
            General Work
          </button>
        </div>
      )}

      {active && (
        <>
          <div className="flex items-center gap-2 mb-3">
            <span className="animate-pulse w-3 h-3 rounded-full bg-recovery"></span>
            <span className="text-sm text-recovery">Session Active</span>
          </div>
          <button
            className="px-4 py-2 rounded-lg bg-debt hover:bg-red-500"
            onClick={handleStop}
          >
            End Session
          </button>
        </>
      )}

      {reading && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">HRV</div>
            <div className="text-xl font-semibold">{reading.hrv}</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Breathing</div>
            <div className="text-xl font-semibold">{reading.breathing_rate}/min</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Focus</div>
            <div className="text-xl font-semibold">{reading.focus_score}%</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Stress</div>
            <div className={`text-xl font-semibold ${getStressColor(reading.stress_level)}`}>
              {reading.stress_level}
            </div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2 col-span-2">
            <div className="text-slate-400 text-xs">Cognitive Cost Ticker</div>
            <div className={`text-xl font-semibold ${reading.cognitive_cost_delta > 0 ? "text-debt" : "text-recovery"}`}>
              {reading.cognitive_cost_delta > 0 ? "+" : ""}{reading.cognitive_cost_delta} pts
            </div>
          </div>
        </div>
      )}

      {lastResult && !active && (
        <div className="mt-4 p-3 bg-slate-950/40 rounded-lg">
          <div className="text-sm font-semibold">Session Complete</div>
          <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
            <div>Estimated Cost: {lastResult.estimated_cost}</div>
            <div>Actual Cost: {lastResult.actual_cost}</div>
            <div className={lastResult.debt_adjustment > 0 ? "text-debt" : "text-recovery"}>
              Adjustment: {lastResult.debt_adjustment > 0 ? "+" : ""}{lastResult.debt_adjustment}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SageMode;
