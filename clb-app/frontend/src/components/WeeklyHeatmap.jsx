import React from "react";

const DAILY_BUDGET = 32;

const getHeatColor = (total) => {
  if (total <= 0) return "bg-slate-800";
  const ratio = total / DAILY_BUDGET;
  if (ratio <= 0.5) return "bg-recovery/30";
  if (ratio <= 0.8) return "bg-recovery/60";
  if (ratio <= 1.0) return "bg-warning/50";
  if (ratio <= 1.2) return "bg-debt/50";
  return "bg-debt/80";
};

const WeeklyHeatmap = ({ dailyTotals = {} }) => {
  const days = Object.entries(dailyTotals).sort((a, b) => a[0].localeCompare(b[0]));
  const totalWeek = days.reduce((sum, [, val]) => sum + val, 0);
  const weeklyBudget = DAILY_BUDGET * 7;
  const debt = totalWeek - weeklyBudget;

  if (days.length === 0) {
    return (
      <div className="card">
        <div className="text-lg font-semibold mb-3">Weekly Load Heatmap</div>
        <div className="text-slate-400 text-sm">No data available yet.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-lg font-semibold">Weekly Load Heatmap</div>
        <div className={`text-sm font-semibold ${debt > 0 ? "text-debt" : "text-recovery"}`}>
          {debt > 0 ? `+${debt} debt` : `${Math.abs(debt)} surplus`}
        </div>
      </div>
      <div className="grid grid-cols-7 gap-2">
        {days.map(([day, total]) => {
          const dayName = new Date(day).toLocaleDateString("en-US", { weekday: "short" });
          return (
            <div 
              key={day} 
              className={`rounded-lg p-3 text-center ${getHeatColor(total)}`}
            >
              <div className="text-xs text-slate-300 mb-1">{dayName}</div>
              <div className="text-lg font-semibold">{total}</div>
              <div className="text-xs text-slate-400">/{DAILY_BUDGET}</div>
            </div>
          );
        })}
      </div>
      <div className="mt-3 flex items-center justify-center gap-4 text-xs text-slate-400">
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-recovery/60"></div>
          <span>Good</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-warning/50"></div>
          <span>High</span>
        </div>
        <div className="flex items-center gap-1">
          <div className="w-3 h-3 rounded bg-debt/80"></div>
          <span>Overload</span>
        </div>
      </div>
    </div>
  );
};

export default WeeklyHeatmap;
