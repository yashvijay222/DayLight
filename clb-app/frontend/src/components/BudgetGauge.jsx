import React from "react";

const getStatusColor = (spent, budget) => {
  if (spent > budget) return "text-debt";
  if (spent > budget * 0.8) return "text-warning";
  return "text-recovery";
};

const BudgetGauge = ({ spent = 0, budget = 32, weeklyDebt = 0, weeklyTotal = 0 }) => {
  const pct = Math.min(100, Math.max(0, Math.round((spent / budget) * 100)));
  const strokeDasharray = `${pct} ${100 - pct}`;
  const colorClass = getStatusColor(spent, budget);

  return (
    <div className="card">
      <div className="flex items-center gap-4">
        <div className="relative">
          <svg viewBox="0 0 36 36" className="w-24 h-24">
            <path
              className="text-slate-800"
              stroke="currentColor"
              strokeWidth="3"
              fill="none"
              d="M18 2a16 16 0 1 1 0 32a16 16 0 1 1 0-32"
            />
            <path
              className={colorClass}
              stroke="currentColor"
              strokeWidth="3"
              strokeLinecap="round"
              fill="none"
              strokeDasharray={strokeDasharray}
              d="M18 2a16 16 0 1 1 0 32a16 16 0 1 1 0-32"
            />
          </svg>
          <div className="absolute inset-0 flex items-center justify-center text-lg font-semibold">
            {pct}%
          </div>
        </div>
        <div>
          <div className="text-sm text-slate-400">Daily Budget</div>
          <div className="text-2xl font-semibold">{spent} / {budget}</div>
          <div className={`text-sm ${colorClass}`}>{spent > budget ? "Overdrafted" : "On Track"}</div>
        </div>
      </div>
      
      <div className="mt-4 pt-4 border-t border-slate-800">
        <div className="flex justify-between text-sm">
          <span className="text-slate-400">Weekly Total</span>
          <span className="font-semibold">{weeklyTotal}</span>
        </div>
        <div className="flex justify-between text-sm mt-1">
          <span className="text-slate-400">Weekly Debt</span>
          <span className={`font-semibold ${weeklyDebt > 0 ? "text-debt" : "text-recovery"}`}>
            {weeklyDebt > 0 ? `+${weeklyDebt}` : weeklyDebt}
          </span>
        </div>
      </div>
    </div>
  );
};

export default BudgetGauge;
