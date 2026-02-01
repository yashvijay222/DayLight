import React, { useState } from "react";
import { enrichEvent } from "../services/api";

const MeetingEnrichForm = ({ event, onEnrich }) => {
  const [participants, setParticipants] = useState(event.participants || 2);
  const [hasAgenda, setHasAgenda] = useState(event.has_agenda ?? true);
  const [requiresToolSwitch, setRequiresToolSwitch] = useState(
    event.requires_tool_switch ?? false
  );
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setLoading(true);
    
    const payload = {
      participants: parseInt(participants, 10),
      has_agenda: hasAgenda,
      requires_tool_switch: requiresToolSwitch,
    };
    
    await enrichEvent(event.id, payload);
    
    if (onEnrich) {
      await onEnrich(event.id, payload);
    }
    
    setLoading(false);
  };

  return (
    <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
      <div className="text-xs text-slate-400 mb-2">Meeting Details</div>
      <form onSubmit={handleSubmit} className="flex flex-wrap items-center gap-3">
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Participants:</label>
          <input
            type="number"
            min="1"
            max="100"
            value={participants}
            onChange={(e) => setParticipants(e.target.value)}
            className="w-16 px-2 py-1 text-xs rounded bg-slate-900 border border-slate-700 focus:border-neutral focus:outline-none"
          />
        </div>
        
        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Has Agenda:</label>
          <button
            type="button"
            onClick={() => setHasAgenda(!hasAgenda)}
            className={`px-2 py-1 text-xs rounded transition ${
              hasAgenda 
                ? "bg-recovery/30 text-recovery" 
                : "bg-debt/30 text-debt"
            }`}
          >
            {hasAgenda ? "Yes" : "No"}
          </button>
        </div>

        <div className="flex items-center gap-2">
          <label className="text-xs text-slate-500">Tool switching:</label>
          <button
            type="button"
            onClick={() => setRequiresToolSwitch(!requiresToolSwitch)}
            className={`px-2 py-1 text-xs rounded transition ${
              requiresToolSwitch
                ? "bg-warning/30 text-warning"
                : "bg-slate-700 text-slate-300"
            }`}
          >
            {requiresToolSwitch ? "Yes" : "No"}
          </button>
        </div>
        
        <button
          type="submit"
          disabled={loading}
          className="px-3 py-1 text-xs rounded bg-neutral hover:bg-blue-500 transition disabled:opacity-50"
        >
          {loading ? "Saving..." : "Save"}
        </button>
      </form>
    </div>
  );
};

export default MeetingEnrichForm;
