import React, { useEffect, useState } from "react";
import { getCostBreakdown } from "../services/api";

const CostBreakdownModal = ({ event, onClose }) => {
  const [breakdown, setBreakdown] = useState(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const load = async () => {
      setLoading(true);
      const { data } = await getCostBreakdown(event.id);
      setBreakdown(data);
      setLoading(false);
    };
    load();
  }, [event.id]);

  const formatValue = (value) => {
    if (value === 0) return "0";
    if (value > 0) return `+${value}`;
    return `${value}`;
  };

  return (
    <div className="fixed inset-0 bg-black/60 flex items-center justify-center z-50" onClick={onClose}>
      <div 
        className="bg-slate-900 rounded-xl p-6 max-w-md w-full mx-4 shadow-xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold">{event.title}</h3>
          <button 
            onClick={onClose}
            className="text-slate-400 hover:text-white text-xl"
          >
            &times;
          </button>
        </div>
        
        <div className="text-xs text-slate-400 mb-4">
          {new Date(event.start_time).toLocaleString()} • {event.duration_minutes} min
          {event.event_type && <span className="ml-2 px-2 py-0.5 bg-slate-800 rounded">{event.event_type}</span>}
        </div>

        {loading ? (
          <div className="text-slate-400 text-center py-4">Loading breakdown...</div>
        ) : breakdown ? (
          <div className="space-y-2">
            <div className="text-sm font-semibold text-slate-300 mb-3">Cost Breakdown</div>
            
            <div className="space-y-1.5 text-sm">
              {breakdown.duration_component !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Duration ({event.duration_minutes}min)</span>
                  <span>{formatValue(breakdown.duration_component)}</span>
                </div>
              )}
              
              {breakdown.base !== 0 && breakdown.event_type === "recovery" && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Recovery benefit</span>
                  <span className="text-recovery">{formatValue(breakdown.base)}</span>
                </div>
              )}
              
              {breakdown.tool_switch !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Tool switching</span>
                  <span className="text-warning">{formatValue(breakdown.tool_switch)}</span>
                </div>
              )}
              
              {breakdown.participants !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Participants</span>
                  <span className="text-warning">{formatValue(breakdown.participants)}</span>
                </div>
              )}
              
              {breakdown.no_agenda !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">No agenda</span>
                  <span className="text-debt">{formatValue(breakdown.no_agenda)}</span>
                </div>
              )}
              
              {breakdown.afternoon_discount !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Afternoon discount</span>
                  <span className="text-recovery">{formatValue(breakdown.afternoon_discount)}</span>
                </div>
              )}
              
              {breakdown.proximity_increment !== 0 && (
                <div className="flex justify-between">
                  <span className="text-slate-400">Back-to-back penalty</span>
                  <span className="text-debt">{formatValue(breakdown.proximity_increment)}</span>
                </div>
              )}
            </div>
            
            <div className="border-t border-slate-700 pt-2 mt-3">
              <div className="flex justify-between text-lg font-semibold">
                <span>Total</span>
                <span className={breakdown.total > 0 ? "text-warning" : "text-recovery"}>
                  {breakdown.total} pts
                </span>
              </div>
            </div>
          </div>
        ) : (
          <div className="text-slate-400 text-center py-4">Could not load breakdown</div>
        )}
        
        <button
          onClick={onClose}
          className="mt-4 w-full px-4 py-2 rounded-lg bg-slate-800 hover:bg-slate-700 transition"
        >
          Close
        </button>
      </div>
    </div>
  );
};

export default CostBreakdownModal;
