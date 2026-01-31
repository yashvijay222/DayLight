import React, { useState } from "react";
import { Link } from "react-router-dom";

import Dashboard from "../components/Dashboard";
import { pushToCalendar, syncCalendar } from "../services/api";

const Home = () => {
  const [syncing, setSyncing] = useState(false);
  const [pushing, setPushing] = useState(false);
  const [status, setStatus] = useState("");
  const [refreshKey, setRefreshKey] = useState(0);

  const handleSync = async () => {
    setSyncing(true);
    setStatus("");
    const { error } = await syncCalendar();
    if (error) {
      setStatus("Sync failed");
    } else {
      setStatus("Calendar synced successfully");
      setRefreshKey((k) => k + 1); // Force Dashboard to remount and reload data
    }
    setSyncing(false);
  };

  const handlePush = async () => {
    setPushing(true);
    setStatus("");
    const { error } = await pushToCalendar();
    if (error) {
      setStatus("Push failed");
    } else {
      setStatus("Changes pushed to calendar");
    }
    setPushing(false);
  };

  return (
    <div className="min-h-screen p-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-6">
        <div>
          <h1 className="text-2xl font-semibold">Dashboard</h1>
          {status && (
            <div className={`text-xs mt-1 ${status.includes("failed") ? "text-debt" : "text-recovery"}`}>
              {status}
            </div>
          )}
        </div>
        <div className="flex flex-wrap gap-3">
          <button
            onClick={handleSync}
            className="px-3 py-1 rounded-lg bg-neutral hover:bg-blue-500 text-sm"
            disabled={syncing || pushing}
          >
            {syncing ? "Syncing..." : "Sync Calendar"}
          </button>
          <button
            onClick={handlePush}
            className="px-3 py-1 rounded-lg bg-recovery text-slate-900 hover:bg-green-400 text-sm"
            disabled={syncing || pushing}
          >
            {pushing ? "Pushing..." : "Push Changes"}
          </button>
          <Link
            to="/analysis"
            className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm"
          >
            Edit Flexibility
          </Link>
          <Link
            to="/onboarding"
            className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm"
          >
            Reconnect
          </Link>
        </div>
      </div>
      <Dashboard key={refreshKey} />
    </div>
  );
};

export default Home;
