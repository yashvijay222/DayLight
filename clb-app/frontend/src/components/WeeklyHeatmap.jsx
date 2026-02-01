import React from "react";

const DAILY_BUDGET = 20;

const getHeatColor = (total) => {
  // Negative values (recovery/surplus) - show green
  if (total < 0) {
    if (total <= -10) return "bg-emerald-600/80"; // Very good recovery
    if (total <= -5) return "bg-emerald-500/60";  // Good recovery
    return "bg-emerald-400/40";                    // Light recovery
  }
  
  // Zero - neutral
  if (total === 0) return "bg-slate-800";
  
  // Positive values - scale from green to red based on budget ratio
  const ratio = total / DAILY_BUDGET;
  if (ratio <= 0.5) return "bg-recovery/30";
  if (ratio <= 0.8) return "bg-recovery/60";
  if (ratio <= 1.0) return "bg-warning/50";
  if (ratio <= 1.2) return "bg-debt/50";
  return "bg-debt/80";
};

const formatWeekLabel = (isoDate) => {
  if (!isoDate) return null;
  const d = new Date(isoDate + "T12:00:00");
  const day = d.toLocaleDateString("en-US", { weekday: "short" });
  const monthDay = d.toLocaleDateString("en-US", { month: "short", day: "numeric" });
  return `Week of ${day}, ${monthDay}`;
};

const WeeklyHeatmap = ({ dailyTotals = {}, weekStart = null }) => {
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
      <div className="flex flex-wrap items-center justify-between gap-2 mb-3">
        <div>
          <div className="text-lg font-semibold">Weekly Load Heatmap</div>
          {weekStart && (
            <div className="text-xs text-slate-400 mt-0.5">{formatWeekLabel(weekStart)}</div>
          )}
        </div>
        <div className={`text-sm font-semibold ${debt > 0 ? "text-debt" : "text-recovery"}`}>
          {debt > 0 ? `+${debt} debt` : `${Math.abs(debt)} surplus`}
        </div>
      </div>
      <div className="grid grid-cols-7 gap-2">
        {days.map(([day, total]) => {
          const dayName = new Date(day + "T12:00:00").toLocaleDateString("en-US", { weekday: "short" });
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
          <div className="w-3 h-3 rounded bg-emerald-500/60"></div>
          <span>Recovery</span>
        </div>
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
