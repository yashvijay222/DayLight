import React, { useEffect, useState, useCallback } from "react";

import BudgetGauge from "./BudgetGauge";
import CalendarWeekView from "./CalendarWeekView";
import OptimizationPanel from "./OptimizationPanel";
import RecoverySuggestions from "./RecoverySuggestions";
import SageMode from "./SageMode";
import WeeklyHeatmap from "./WeeklyHeatmap";
import { useBudget } from "../hooks/useBudget";
import { useEvents } from "../hooks/useEvents";
import { useOptimize } from "../hooks/useOptimize";
import { getRecoverySuggestions, getWeeklyBudget, scheduleRecovery } from "../services/api";

const Dashboard = () => {
  const { events, loading: eventsLoading, reload: reloadEvents } = useEvents();
  const { budget, loading: budgetLoading, reload: reloadBudget } = useBudget();
  const { suggestions, weeklyDebt, apply, applyAll, reload: reloadOptimize } = useOptimize();
  const [recovery, setRecovery] = useState([]);
  const [weeklyTotals, setWeeklyTotals] = useState({});
  const [weekStart, setWeekStart] = useState(null);

  const loadRecovery = useCallback(async () => {
    const { data } = await getRecoverySuggestions();
    setRecovery(data?.activities || []);
  }, []);

  const loadWeekly = useCallback(async () => {
    const { data } = await getWeeklyBudget();
    setWeeklyTotals(data?.daily_totals || {});
    setWeekStart(data?.week_start || null);
  }, []);

  useEffect(() => {
    loadRecovery();
    loadWeekly();
  }, [loadRecovery, loadWeekly]);

  const handleScheduleRecovery = async (payload) => {
    await scheduleRecovery(payload);
    await reloadEvents();
    await reloadBudget();
    await reloadOptimize();
    await loadRecovery();
    await loadWeekly();
  };

  const handleApplyOptimization = async (id) => {
    await apply(id);
    await reloadEvents();
    await reloadBudget();
    await loadRecovery();
    await loadWeekly();
  };

  const handleApplyAll = async (ids) => {
    await applyAll(ids);
    await reloadEvents();
    await reloadBudget();
    await loadRecovery();
    await loadWeekly();
  };

  const handleSessionEnd = async () => {
    await reloadEvents();
    await reloadBudget();
    await reloadOptimize();
    await loadRecovery();
    await loadWeekly();
  };

  return (
    <div className="space-y-6">
      <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
        <BudgetGauge 
          spent={budget?.spent || 0} 
          budget={budget?.daily_budget || 20}
          weeklyDebt={budget?.weekly_debt || weeklyDebt}
          weeklyTotal={budget?.weekly_total || 0}
        />
        <SageMode events={events} onSessionEnd={handleSessionEnd} />
      </div>

      <CalendarWeekView events={events} />

      {weeklyDebt > 0 && (
        <OptimizationPanel
          suggestions={suggestions}
          weeklyDebt={weeklyDebt}
          onApply={handleApplyOptimization}
          onApplyAll={handleApplyAll}
        />
      )}

      {weeklyDebt > 0 && (
        <RecoverySuggestions activities={recovery} onSchedule={handleScheduleRecovery} />
      )}

      <WeeklyHeatmap dailyTotals={weeklyTotals} weekStart={weekStart} />

      {(eventsLoading || budgetLoading) && (
        <div className="text-slate-400 text-sm">Loading data...</div>
      )}
    </div>
  );
};

export default Dashboard;
