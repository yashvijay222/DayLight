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
  const [selectedChanges, setSelectedChanges] = useState({}); // Track which changes are selected
  const navigate = useNavigate();

  // Check if all events have flexibility set
  const allClassified = events.length > 0 && events.every(e => e.is_flexible !== null);
  
  // Check if any meetings need enrichment
  const needsEnrichment = events.some(e => 
    (e.event_type === "meeting" || e.event_type === "admin") && 
    (e.participants === null || e.has_agenda === null)
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
    const proposal = data?.proposal || null;
    setWeekProposal(proposal);
    // Select all changes by default
    if (proposal?.changes) {
      const initialSelection = {};
      proposal.changes.forEach(change => {
        initialSelection[change.event_id] = true;
      });
      setSelectedChanges(initialSelection);
    } else {
      setSelectedChanges({});
    }
    setLoadingOptimize(false);
  };

  const handleToggleChange = (eventId) => {
    setSelectedChanges(prev => ({
      ...prev,
      [eventId]: !prev[eventId]
    }));
  };

  const handleSelectAll = () => {
    if (weekProposal?.changes) {
      const allSelected = {};
      weekProposal.changes.forEach(change => {
        allSelected[change.event_id] = true;
      });
      setSelectedChanges(allSelected);
    }
  };

  const handleDeselectAll = () => {
    setSelectedChanges({});
  };

  const getSelectedEventIds = () => {
    return Object.entries(selectedChanges)
      .filter(([_, isSelected]) => isSelected)
      .map(([eventId]) => eventId);
  };

  const handleApplyWeekOptimization = async () => {
    const selectedIds = getSelectedEventIds();
    if (selectedIds.length === 0) return;
    
    setApplyingOptimize(true);
    await applyWeekOptimization(selectedIds);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
    setWeekProposal(null);
    setSelectedChanges({});
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
                <div>
                  <div className="text-sm font-semibold">Proposed Changes</div>
                  <p className="text-xs text-slate-500">Select the changes you want to apply</p>
                </div>
                <div className="flex items-center gap-3">
                  <div className="text-xs text-slate-400">
                    Max daily: {weekProposal.current_max_daily_debt} → {weekProposal.proposed_max_daily_debt}
                  </div>
                  <div className="flex gap-2">
                    <button
                      onClick={handleSelectAll}
                      className="text-xs text-neutral hover:text-blue-400 transition"
                    >
                      Select All
                    </button>
                    <span className="text-slate-600">|</span>
                    <button
                      onClick={handleDeselectAll}
                      className="text-xs text-slate-400 hover:text-slate-300 transition"
                    >
                      Deselect All
                    </button>
                  </div>
                </div>
              </div>
              
              <div className="space-y-2 mb-4">
                {weekProposal.changes.map((change, idx) => {
                  const isSelected = selectedChanges[change.event_id] || false;
                  return (
                    <div 
                      key={idx} 
                      className={`flex items-center gap-3 text-sm rounded-lg p-3 cursor-pointer transition ${
                        isSelected 
                          ? "bg-recovery/10 border border-recovery/30" 
                          : "bg-slate-800/50 border border-transparent hover:bg-slate-800"
                      }`}
                      onClick={() => handleToggleChange(change.event_id)}
                    >
                      <input
                        type="checkbox"
                        checked={isSelected}
                        onChange={() => handleToggleChange(change.event_id)}
                        className="w-4 h-4 rounded border-slate-600 bg-slate-800 text-recovery focus:ring-recovery focus:ring-offset-0 cursor-pointer"
                      />
                      <div className="flex-1 flex items-center justify-between">
                        <span className={isSelected ? "text-slate-200" : "text-slate-400"}>
                          {change.event_title || "Event"}
                        </span>
                        <span className="text-xs text-slate-400">
                          {new Date(change.original_time).toLocaleDateString("en-US", { weekday: "short" })} 
                          {" → "}
                          {new Date(change.new_time).toLocaleDateString("en-US", { weekday: "short" })}
                          {" "}
                          {new Date(change.new_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                        </span>
                      </div>
                    </div>
                  );
                })}
              </div>
              
              <div className="flex items-center justify-between">
                <span className="text-xs text-slate-400">
                  {getSelectedEventIds().length} of {weekProposal.changes.length} changes selected
                </span>
                <button
                  onClick={handleApplyWeekOptimization}
                  disabled={applyingOptimize || getSelectedEventIds().length === 0}
                  className="px-6 py-2 rounded-xl bg-recovery text-slate-900 hover:bg-green-400 transition disabled:opacity-50 disabled:cursor-not-allowed"
                >
                  {applyingOptimize ? "Applying..." : `Apply ${getSelectedEventIds().length} Selected`}
                </button>
              </div>
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
