import React from "react";
import { useNavigate } from "react-router-dom";
import { useGoogleCalendar } from "../hooks/useGoogleCalendar";

const CalendarConnect = () => {
  const { connect, loading, error } = useGoogleCalendar();
  const navigate = useNavigate();

  const handleUseDemo = () => {
    // Skip sync - backend already has pre-loaded mock data from startup
    navigate("/dashboard");
  };

  return (
    <div className="card text-center">
      <h2 className="text-2xl font-semibold">Connect your Calendar</h2>
      <p className="text-slate-400 mt-2">
        Import your week and calculate your cognitive budget in seconds.
      </p>
      <div className="flex flex-col sm:flex-row gap-3 justify-center mt-4">
        <button
          onClick={connect}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-neutral hover:bg-blue-500 transition"
        >
          {loading ? "Connecting..." : "Connect Google Calendar"}
        </button>
        <button
          onClick={handleUseDemo}
          disabled={loading}
          className="px-4 py-2 rounded-xl bg-recovery text-slate-900 hover:bg-green-400 transition"
        >
          Use Demo Data
        </button>
      </div>
      {error && <div className="text-debt text-sm mt-2">{String(error)}</div>}
    </div>
  );
};

export default CalendarConnect;
