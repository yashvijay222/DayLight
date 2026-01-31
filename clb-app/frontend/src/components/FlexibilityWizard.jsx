import React, { useState } from "react";

import EventCard from "./EventCard";

const getButtonStyle = (event, reason, isLoading) => {
  const isActive = event.flexibility_reason === reason;
  const base = "px-2 py-1 rounded-lg text-xs transition disabled:opacity-50";
  if (isActive) {
    if (reason === "required") return `${base} bg-slate-600 ring-2 ring-slate-400`;
    if (reason === "moveable") return `${base} bg-warning/30 ring-2 ring-warning`;
    if (reason === "skippable") return `${base} bg-recovery/30 ring-2 ring-recovery`;
  }
  return `${base} bg-slate-800 hover:bg-slate-700`;
};

const FlexibilityWizard = ({ events = [], onClassify }) => {
  const [loading, setLoading] = useState(null);
  const classified = events.filter(e => e.flexibility_reason).length;
  const total = events.length;

  const handleClassify = async (eventId, payload) => {
    setLoading(`${eventId}-${payload.reason}`);
    await onClassify(eventId, payload);
    setLoading(null);
  };

  if (events.length === 0) {
    return (
      <div className="card">
        <div className="text-lg font-semibold mb-2">Flexibility Check</div>
        <div className="text-slate-400 text-sm">No events to classify. Sync your calendar first.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div className="text-lg font-semibold">Flexibility Check</div>
        <div className="text-sm text-slate-400">
          {classified}/{total} classified
          {classified === total && <span className="text-recovery ml-2">✓</span>}
        </div>
      </div>
      <div className="space-y-3">
        {events.map((event) => (
          <EventCard key={event.id} event={event}>
            <div className="flex gap-2 items-center flex-wrap">
              <button
                className={getButtonStyle(event, "required", loading)}
                disabled={loading !== null}
                onClick={() =>
                  handleClassify(event.id, { event_id: event.id, is_flexible: false, reason: "required" })
                }
              >
                {loading === `${event.id}-required` ? "..." : "Required"}
              </button>
              <button
                className={getButtonStyle(event, "moveable", loading)}
                disabled={loading !== null}
                onClick={() =>
                  handleClassify(event.id, { event_id: event.id, is_flexible: true, reason: "moveable" })
                }
              >
                {loading === `${event.id}-moveable` ? "..." : "Moveable"}
              </button>
              <button
                className={getButtonStyle(event, "skippable", loading)}
                disabled={loading !== null}
                onClick={() =>
                  handleClassify(event.id, { event_id: event.id, is_flexible: true, reason: "skippable" })
                }
              >
                {loading === `${event.id}-skippable` ? "..." : "Skippable"}
              </button>
            </div>
          </EventCard>
        ))}
      </div>
    </div>
  );
};

export default FlexibilityWizard;
