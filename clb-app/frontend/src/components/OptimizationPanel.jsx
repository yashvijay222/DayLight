import React, { useState } from "react";

const getSuggestionIcon = (type) => {
  switch (type) {
    case "cancel": return "×";
    case "postpone": return "→";
    case "shorten": return "↔";
    default: return "•";
  }
};

const getSuggestionColor = (type) => {
  switch (type) {
    case "cancel": return "bg-debt/20 border-debt";
    case "postpone": return "bg-warning/20 border-warning";
    case "shorten": return "bg-neutral/20 border-neutral";
    default: return "bg-slate-800 border-slate-700";
  }
};

const OptimizationPanel = ({ suggestions = [], weeklyDebt = 0, onApply, onApplyAll }) => {
  const [applying, setApplying] = useState(null);
  
  const potentialReduction = suggestions.reduce((sum, s) => sum + s.debt_reduction, 0);

  const handleApply = async (id) => {
    setApplying(id);
    await onApply(id);
    setApplying(null);
  };

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-1">
        <div className="text-lg font-semibold">Optimization Suggestions</div>
        <div className="text-sm text-debt font-semibold">Debt: {weeklyDebt}</div>
      </div>
      <div className="flex items-center justify-between mb-3">
        <p className="text-xs text-slate-400">
          Apply these suggestions to reduce your cognitive debt. Potential reduction: {potentialReduction} points.
        </p>
        {onApplyAll && suggestions.length > 1 && (
          <button
            className="text-xs px-3 py-1 rounded-lg bg-recovery text-slate-900 hover:bg-green-400 ml-2 whitespace-nowrap"
            onClick={() => onApplyAll(suggestions.map((s) => s.suggestion_id))}
          >
            Apply All
          </button>
        )}
      </div>
      <div className="space-y-2">
        {suggestions.length === 0 && (
          <div className="text-slate-400 text-sm">
            Mark events as "moveable" or "skippable" to get suggestions.
          </div>
        )}
        {suggestions.map((suggestion) => (
          <div 
            key={suggestion.suggestion_id} 
            className={`p-3 rounded-xl border-l-4 ${getSuggestionColor(suggestion.suggestion_type)}`}
          >
            <div className="flex items-center justify-between">
              <div>
                <div className="flex items-center gap-2">
                  <span className="text-lg">{getSuggestionIcon(suggestion.suggestion_type)}</span>
                  <span className="text-sm font-semibold uppercase">
                    {suggestion.suggestion_type}
                  </span>
                </div>
                <div className="text-xs text-slate-400 mt-1">{suggestion.reason}</div>
              </div>
              <div className="text-right">
                <div className="text-xs text-recovery font-semibold">
                  -{suggestion.debt_reduction} pts
                </div>
                <button
                  className="mt-1 px-3 py-1 rounded-lg bg-recovery text-slate-900 text-xs hover:bg-green-400 disabled:opacity-50"
                  onClick={() => handleApply(suggestion.suggestion_id)}
                  disabled={applying === suggestion.suggestion_id}
                >
                  {applying === suggestion.suggestion_id ? "..." : "Apply"}
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default OptimizationPanel;
