import React, { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";

import FlexibilityWizard from "../components/FlexibilityWizard";
import OptimizationPanel from "../components/OptimizationPanel";
import RecoverySuggestions from "../components/RecoverySuggestions";
import { useEvents } from "../hooks/useEvents";
import { useOptimize } from "../hooks/useOptimize";
import { getRecoverySuggestions, scheduleRecovery } from "../services/api";

const Analysis = () => {
  const { events, setFlexibility, reload: reloadEvents } = useEvents();
  const { suggestions, weeklyDebt, apply, applyAll, reload: reloadOptimize } = useOptimize();
  const [recovery, setRecovery] = useState([]);
  const navigate = useNavigate();

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
  };

  const handleApply = async (id) => {
    await apply(id);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
  };

  const handleApplyAll = async (ids) => {
    await applyAll(ids);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
  };

  const handleScheduleRecovery = async (payload) => {
    await scheduleRecovery(payload);
    await reloadEvents();
    await reloadOptimize();
    await loadRecovery();
  };

  return (
    <div className="min-h-screen p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">Schedule Analysis</h1>
          <p className="text-slate-400 text-sm">
            Mark which events are flexible so we can reduce debt.
          </p>
          {weeklyDebt > 0 ? (
            <p className="text-debt text-sm mt-1">Weekly debt: {weeklyDebt} points</p>
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

      <FlexibilityWizard events={events} onClassify={handleClassify} />

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
