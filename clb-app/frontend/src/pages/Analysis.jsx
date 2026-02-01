import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

import FlexibilityWizard from "../components/FlexibilityWizard";
import OptimizationPanel from "../components/OptimizationPanel";
import RecoverySuggestions from "../components/RecoverySuggestions";
import { useEvents } from "../hooks/useEvents";
import { useOptimize } from "../hooks/useOptimize";
import { 
  getRecoverySuggestions, 
  scheduleRecovery, 
  getWeekOptimization, 
  applyWeekOptimization 
} from "../services/api";

const Analysis = () => {
  const { events, setFlexibility, reload: reloadEvents } = useEvents();
  const { suggestions, weeklyDebt, apply, applyAll, reload: reloadOptimize } = useOptimize();
  const [recovery, setRecovery] = useState([]);
  const [weekProposal, setWeekProposal] = useState(null);
  const [loadingOptimize, setLoadingOptimize] = useState(false);
  const [applyingOptimize, setApplyingOptimize] = useState(false);
  const navigate = useNavigate();

  // Check if all events have flexibility set
  const allClassified = events.length > 0 && events.every(e => e.is_flexible !== null);
  
  // Check if any meetings need enrichment
  const needsEnrichment = events.some(e => 
    (e.event_type === "meeting" || e.event_type === "admin") && 
    (e.participants === null || e.has_agenda === null || e.requires_tool_switch === null)
  );

  const loadRecovery = useCallback(async () => {
    const { data } = await getRecoverySuggestions();
    setRecovery(data?.activities || []);
  }, []);

  useEffect(() => {
    loadRecovery();
  }, [loadRecovery]);

  const handleClassify = async (eventId, payload) => {
    await setFlexibility(eventId, payload);
    await reloadOptimize();
    setWeekProposal(null); // Clear proposal when flexibility changes
  };

  const handleEnrich = async () => {
    await reloadEvents();
    await reloadOptimize();
  };

  const handleApply = async (id) => {
    await apply(id);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
    setWeekProposal(null);
  };

  const handleApplyAll = async (ids) => {
    await applyAll(ids);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
    setWeekProposal(null);
  };

  const handleScheduleRecovery = async (payload) => {
    await scheduleRecovery(payload);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
  };

  const handleOptimizeWeek = async () => {
    setLoadingOptimize(true);
    const { data } = await getWeekOptimization();
    setWeekProposal(data?.proposal || null);
    setLoadingOptimize(false);
  };

  const handleApplyWeekOptimization = async () => {
    setApplyingOptimize(true);
    await applyWeekOptimization();
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
    setWeekProposal(null);
    setApplyingOptimize(false);
  };

  return (
    <div className="min-h-screen p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Schedule Analysis</h1>
          <p className="text-slate-400 text-sm">
            Configure event flexibility and complete meeting details to optimize your week.
          </p>
          {weeklyDebt > 0 ? (
            <p className="text-debt text-sm mt-1">Weekly debt: {weeklyDebt} points (max 20/day)</p>
          ) : (
            <p className="text-recovery text-sm mt-1">No debt - you're on track!</p>
          )}
        </div>
        <button
          className="px-4 py-2 rounded-xl bg-recovery text-slate-900 hover:bg-green-400"
          onClick={() => navigate("/dashboard")}
        >
          Go to Dashboard
        </button>
      </div>

      <FlexibilityWizard 
        events={events} 
        onClassify={handleClassify} 
        onEnrich={handleEnrich}
      />

      {/* Optimize Week Button - shown when all events are classified and enriched */}
      {allClassified && !needsEnrichment && (
        <div className="card">
          <div className="flex items-center justify-between">
            <div>
              <div className="text-lg font-semibold">Week Optimization</div>
              <p className="text-xs text-slate-400">
                All events are configured. Optimize your week to reduce debt and spread events evenly.
              </p>
            </div>
            <button
              onClick={handleOptimizeWeek}
              disabled={loadingOptimize}
              className="px-4 py-2 rounded-xl bg-neutral hover:bg-blue-500 transition disabled:opacity-50"
            >
              {loadingOptimize ? "Generating..." : "Optimize My Calendar"}
            </button>
          </div>
          
          {/* Week Optimization Proposal */}
          {weekProposal && weekProposal.changes && weekProposal.changes.length > 0 && (
            <div className="mt-4 pt-4 border-t border-slate-800">
              <div className="flex items-center justify-between mb-3">
                <div className="text-sm font-semibold">Proposed Changes</div>
                <div className="text-xs text-slate-400">
                  Max daily: {weekProposal.current_max_daily_debt} → {weekProposal.proposed_max_daily_debt}
                </div>
              </div>
              
              <div className="space-y-2 mb-4">
                {weekProposal.changes.map((change, idx) => (
                  <div key={idx} className="flex items-center justify-between text-sm bg-slate-800/50 rounded-lg p-2">
                    <span className="text-slate-300">{change.event_title || "Event"}</span>
                    <span className="text-xs text-slate-400">
                      {new Date(change.original_time).toLocaleDateString("en-US", { weekday: "short" })} 
                      {" → "}
                      {new Date(change.new_time).toLocaleDateString("en-US", { weekday: "short" })}
                      {" "}
                      {new Date(change.new_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                    </span>
                  </div>
                ))}
              </div>
              
              <button
                onClick={handleApplyWeekOptimization}
                disabled={applyingOptimize}
                className="w-full px-4 py-2 rounded-xl bg-recovery text-slate-900 hover:bg-green-400 transition disabled:opacity-50"
              >
                {applyingOptimize ? "Applying..." : "Apply Optimization"}
              </button>
            </div>
          )}
          
          {weekProposal && (!weekProposal.changes || weekProposal.changes.length === 0) && (
            <div className="mt-4 pt-4 border-t border-slate-800">
              <p className="text-sm text-slate-400">
                No changes needed - your schedule is already optimized or no movable events can be redistributed.
              </p>
            </div>
          )}
        </div>
      )}

      {weeklyDebt > 0 && suggestions.length > 0 && (
        <OptimizationPanel
          suggestions={suggestions}
          weeklyDebt={weeklyDebt}
          onApply={handleApply}
          onApplyAll={handleApplyAll}
        />
      )}

      {weeklyDebt > 0 && (
        <RecoverySuggestions activities={recovery} onSchedule={handleScheduleRecovery} />
      )}
    </div>
  );
};

export default Analysis;
