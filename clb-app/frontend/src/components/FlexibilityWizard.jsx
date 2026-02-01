import React, { useState } from "react";

import EventCard from "./EventCard";
import MeetingEnrichForm from "./MeetingEnrichForm";

const getButtonStyle = (event, isMovable, isLoading) => {
  const base = "px-3 py-1.5 rounded-lg text-xs transition disabled:opacity-50";
  
  if (isMovable && event.is_flexible === true) {
    return `${base} bg-warning/30 ring-2 ring-warning`;
  }
  if (!isMovable && event.is_flexible === false) {
    return `${base} bg-slate-600 ring-2 ring-slate-400`;
  }
  
  return `${base} bg-slate-800 hover:bg-slate-700`;
};

const needsEnrichment = (event) => {
  // Only meeting/admin events need enrichment
  if (event.event_type !== "meeting" && event.event_type !== "admin") {
    return false;
  }
  // Check if any meeting-specific field is missing
  return (
    event.participants === null ||
    event.has_agenda === null ||
    event.requires_tool_switch === null
  );
};

const FlexibilityWizard = ({ events = [], onClassify, onEnrich }) => {
  const [loading, setLoading] = useState(null);
  const classified = events.filter(e => e.is_flexible !== null).length;
  const total = events.length;
  const needsEnrichmentCount = events.filter(needsEnrichment).length;

  const handleClassify = async (eventId, isFlexible) => {
    setLoading(`${eventId}-${isFlexible ? 'movable' : 'unmovable'}`);
    await onClassify(eventId, { event_id: eventId, is_flexible: isFlexible });
    setLoading(null);
  };

  if (events.length === 0) {
    return (
      <div className="card">
        <div className="text-lg font-semibold mb-2">Event Setup</div>
        <div className="text-slate-400 text-sm">No events to configure. Sync your calendar first.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="flex items-center justify-between mb-3">
        <div>
          <div className="text-lg font-semibold">Event Setup</div>
          <p className="text-xs text-slate-500">Mark events as movable or unmovable, and complete meeting details</p>
        </div>
        <div className="text-sm text-slate-400">
          {classified}/{total} classified
          {classified === total && needsEnrichmentCount === 0 && (
            <span className="text-recovery ml-2">✓</span>
          )}
        </div>
      </div>
      
      {needsEnrichmentCount > 0 && (
        <div className="mb-4 p-3 bg-warning/10 border border-warning/30 rounded-lg text-sm text-warning">
          {needsEnrichmentCount} meeting(s) need additional details (participants, agenda, tool switching)
        </div>
      )}
      
      <div className="space-y-3">
        {events.map((event) => (
          <EventCard key={event.id} event={event}>
            <div className="space-y-3">
              {/* Flexibility buttons */}
              <div className="flex gap-2 items-center flex-wrap">
                <span className="text-xs text-slate-500 mr-2">Flexibility:</span>
                <button
                  className={getButtonStyle(event, false, loading)}
                  disabled={loading !== null}
                  onClick={() => handleClassify(event.id, false)}
                >
                  {loading === `${event.id}-unmovable` ? "..." : "Unmovable"}
                </button>
                <button
                  className={getButtonStyle(event, true, loading)}
                  disabled={loading !== null}
                  onClick={() => handleClassify(event.id, true)}
                >
                  {loading === `${event.id}-movable` ? "..." : "Movable"}
                </button>
              </div>
              
              {/* Meeting enrichment form */}
              {needsEnrichment(event) && (
                <MeetingEnrichForm event={event} onEnrich={onEnrich} />
              )}
            </div>
          </EventCard>
        ))}
      </div>
    </div>
  );
};

export default FlexibilityWizard;
