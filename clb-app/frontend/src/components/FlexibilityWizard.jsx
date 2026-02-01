import React, { useState } from "react";
import EventCard from "./EventCard";

const getButtonStyle = (event, isMovable, isLoading) => {
  const base = "px-3 py-1.5 rounded-lg text-xs transition disabled:opacity-50";
  
  if (isLoading) {
    return `${base} bg-slate-800 opacity-50`;
  }
  
  if (isMovable && event.is_flexible === true) {
    return `${base} bg-warning/30 ring-2 ring-warning`;
  }
  if (!isMovable && event.is_flexible === false) {
    return `${base} bg-slate-600 ring-2 ring-slate-400`;
  }
  
  return `${base} bg-slate-800 hover:bg-slate-700`;
};

const needsEnrichment = (event, pendingEnrichment) => {
  // Only meeting/admin events need enrichment
  if (event.event_type !== "meeting" && event.event_type !== "admin") {
    return false;
  }
  // Check pending enrichment first, then actual event
  const participants = pendingEnrichment?.participants ?? event.participants;
  const hasAgenda = pendingEnrichment?.has_agenda ?? event.has_agenda;
  
  return participants === null || hasAgenda === null;
};

const FlexibilityWizard = ({ events = [], onClassify, onEnrich }) => {
  // Track which events are currently being saved
  const [savingEvents, setSavingEvents] = useState({});
  
  // Count events that need attention
  const getClassifiedCount = () => {
    return events.filter(e => e.is_flexible !== null).length;
  };
  
  const getNeedsEnrichmentCount = () => {
    return events.filter(e => needsEnrichment(e, {})).length;
  };
  
  const classified = getClassifiedCount();
  const total = events.length;
  const needsEnrichmentCount = getNeedsEnrichmentCount();

  // Handle flexibility change - save immediately
  const handleFlexibilityChange = async (eventId, isFlexible) => {
    setSavingEvents(prev => ({ ...prev, [eventId]: true }));
    try {
      await onClassify(eventId, { event_id: eventId, is_flexible: isFlexible });
    } finally {
      setSavingEvents(prev => ({ ...prev, [eventId]: false }));
    }
  };
  
  // Handle enrichment change - save immediately
  const handleEnrichmentChange = async (eventId, field, value, currentEnrichment) => {
    setSavingEvents(prev => ({ ...prev, [eventId]: true }));
    try {
      await onEnrich(eventId, { ...currentEnrichment, [field]: value });
    } finally {
      setSavingEvents(prev => ({ ...prev, [eventId]: false }));
    }
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
          <p className="text-xs text-slate-500">Mark events as movable or unmovable, and complete meeting details. Changes save automatically.</p>
        </div>
        <div className="flex items-center gap-3">
          <div className="text-sm text-slate-400">
            {classified}/{total} classified
            {classified === total && needsEnrichmentCount === 0 && (
              <span className="text-recovery ml-2">✓</span>
            )}
          </div>
        </div>
      </div>
      
      {needsEnrichmentCount > 0 && (
        <div className="mb-4 p-3 bg-warning/10 border border-warning/30 rounded-lg text-sm text-warning">
          {needsEnrichmentCount} meeting(s) need additional details (participants, agenda)
        </div>
      )}
      
      <div className="space-y-3">
        {events.map((event) => {
          const isSaving = savingEvents[event.id];
          const currentParticipants = event.participants ?? 2;
          const currentHasAgenda = event.has_agenda ?? true;
          
          return (
            <EventCard key={event.id} event={event}>
              <div className="space-y-3">
                {/* Flexibility buttons */}
                <div className="flex gap-2 items-center flex-wrap">
                  <span className="text-xs text-slate-500 mr-2">Flexibility:</span>
                  <button
                    className={getButtonStyle(event, false, isSaving)}
                    disabled={isSaving}
                    onClick={() => handleFlexibilityChange(event.id, false)}
                  >
                    {isSaving ? "Saving..." : "Unmovable"}
                  </button>
                  <button
                    className={getButtonStyle(event, true, isSaving)}
                    disabled={isSaving}
                    onClick={() => handleFlexibilityChange(event.id, true)}
                  >
                    {isSaving ? "Saving..." : "Movable"}
                  </button>
                </div>
                
                {/* Meeting enrichment form (inline) */}
                {(event.event_type === "meeting" || event.event_type === "admin") && (
                  <div className="bg-slate-800/50 rounded-lg p-3 border border-slate-700">
                    <div className="text-xs text-slate-400 mb-2">Meeting Details</div>
                    <div className="flex flex-wrap items-center gap-3">
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-slate-500">Participants:</label>
                        <input
                          type="number"
                          min="1"
                          max="100"
                          key={`${event.id}-${event.participants}`}
                          defaultValue={currentParticipants}
                          onBlur={(e) => {
                            const newValue = parseInt(e.target.value, 10);
                            if (newValue !== event.participants && !isNaN(newValue)) {
                              handleEnrichmentChange(event.id, "participants", newValue, { has_agenda: currentHasAgenda });
                            }
                          }}
                          disabled={isSaving}
                          className="w-16 px-2 py-1 text-xs rounded bg-slate-900 border border-slate-700 focus:border-neutral focus:outline-none disabled:opacity-50"
                        />
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-slate-500">Has Agenda:</label>
                        <button
                          type="button"
                          disabled={isSaving}
                          onClick={() => handleEnrichmentChange(event.id, "has_agenda", !currentHasAgenda, { participants: currentParticipants })}
                          className={`px-2 py-1 text-xs rounded transition disabled:opacity-50 ${
                            currentHasAgenda 
                              ? "bg-recovery/30 text-recovery" 
                              : "bg-debt/30 text-debt"
                          }`}
                        >
                          {currentHasAgenda ? "Yes" : "No"}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            </EventCard>
          );
        })}
      </div>
    </div>
  );
};

export default FlexibilityWizard;
