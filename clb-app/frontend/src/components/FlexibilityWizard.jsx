import React, { useState, useEffect } from "react";
import EventCard from "./EventCard";

const getButtonStyle = (event, isMovable, pendingFlexibility, isLoading) => {
  const base = "px-3 py-1.5 rounded-lg text-xs transition disabled:opacity-50";
  
  // Check pending changes first
  const currentFlexibility = pendingFlexibility !== undefined ? pendingFlexibility : event.is_flexible;
  const hasPendingChange = pendingFlexibility !== undefined && pendingFlexibility !== event.is_flexible;
  
  if (isMovable && currentFlexibility === true) {
    return `${base} bg-warning/30 ring-2 ring-warning ${hasPendingChange ? "animate-pulse" : ""}`;
  }
  if (!isMovable && currentFlexibility === false) {
    return `${base} bg-slate-600 ring-2 ring-slate-400 ${hasPendingChange ? "animate-pulse" : ""}`;
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
  const [saving, setSaving] = useState(false);
  
  // Track pending changes: { eventId: { flexibility: bool, enrichment: { participants, has_agenda } } }
  const [pendingChanges, setPendingChanges] = useState({});
  
  // Reset pending changes when events change (e.g., after save)
  useEffect(() => {
    setPendingChanges({});
  }, [events]);
  
  const hasPendingChanges = Object.keys(pendingChanges).length > 0;
  
  // Count events that need attention (considering pending changes)
  const getClassifiedCount = () => {
    return events.filter(e => {
      const pending = pendingChanges[e.id];
      const flexibility = pending?.flexibility ?? e.is_flexible;
      return flexibility !== null;
    }).length;
  };
  
  const getNeedsEnrichmentCount = () => {
    return events.filter(e => needsEnrichment(e, pendingChanges[e.id]?.enrichment)).length;
  };
  
  const classified = getClassifiedCount();
  const total = events.length;
  const needsEnrichmentCount = getNeedsEnrichmentCount();

  // Handle flexibility change (local only)
  const handleFlexibilityChange = (eventId, isFlexible) => {
    setPendingChanges(prev => ({
      ...prev,
      [eventId]: {
        ...prev[eventId],
        flexibility: isFlexible,
      }
    }));
  };
  
  // Handle enrichment change (local only)
  const handleEnrichmentChange = (eventId, field, value) => {
    setPendingChanges(prev => ({
      ...prev,
      [eventId]: {
        ...prev[eventId],
        enrichment: {
          ...prev[eventId]?.enrichment,
          [field]: value,
        }
      }
    }));
  };
  
  // Save all pending changes
  const handleSaveAll = async () => {
    setSaving(true);
    
    const promises = [];
    
    for (const [eventId, changes] of Object.entries(pendingChanges)) {
      // Save flexibility if changed
      if (changes.flexibility !== undefined) {
        promises.push(
          onClassify(eventId, { event_id: eventId, is_flexible: changes.flexibility })
        );
      }
      
      // Save enrichment if changed
      if (changes.enrichment && Object.keys(changes.enrichment).length > 0) {
        promises.push(
          onEnrich(eventId, changes.enrichment)
        );
      }
    }
    
    await Promise.all(promises);
    setPendingChanges({});
    setSaving(false);
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
        <div className="flex items-center gap-3">
          <div className="text-sm text-slate-400">
            {classified}/{total} classified
            {classified === total && needsEnrichmentCount === 0 && (
              <span className="text-recovery ml-2">✓</span>
            )}
          </div>
          {hasPendingChanges && (
            <button
              onClick={handleSaveAll}
              disabled={saving}
              className="px-4 py-1.5 rounded-lg bg-emerald-600 hover:bg-emerald-500 text-white text-sm font-medium transition disabled:opacity-50"
            >
              {saving ? "Saving..." : "Save All"}
            </button>
          )}
        </div>
      </div>
      
      {needsEnrichmentCount > 0 && (
        <div className="mb-4 p-3 bg-warning/10 border border-warning/30 rounded-lg text-sm text-warning">
          {needsEnrichmentCount} meeting(s) need additional details (participants, agenda)
        </div>
      )}
      
      {hasPendingChanges && (
        <div className="mb-4 p-3 bg-neutral/10 border border-neutral/30 rounded-lg text-sm text-neutral">
          You have unsaved changes. Click "Save All" to apply them.
        </div>
      )}
      
      <div className="space-y-3">
        {events.map((event) => {
          const pending = pendingChanges[event.id];
          const currentFlexibility = pending?.flexibility ?? event.is_flexible;
          const pendingEnrichment = pending?.enrichment || {};
          const currentParticipants = pendingEnrichment.participants ?? event.participants ?? 2;
          const currentHasAgenda = pendingEnrichment.has_agenda ?? event.has_agenda ?? true;
          const showEnrichment = needsEnrichment(event, pendingEnrichment);
          
          return (
            <EventCard key={event.id} event={event}>
              <div className="space-y-3">
                {/* Flexibility buttons */}
                <div className="flex gap-2 items-center flex-wrap">
                  <span className="text-xs text-slate-500 mr-2">Flexibility:</span>
                  <button
                    className={getButtonStyle(event, false, pending?.flexibility, saving)}
                    disabled={saving}
                    onClick={() => handleFlexibilityChange(event.id, false)}
                  >
                    Unmovable
                  </button>
                  <button
                    className={getButtonStyle(event, true, pending?.flexibility, saving)}
                    disabled={saving}
                    onClick={() => handleFlexibilityChange(event.id, true)}
                  >
                    Movable
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
                          value={currentParticipants}
                          onChange={(e) => handleEnrichmentChange(event.id, "participants", parseInt(e.target.value, 10))}
                          disabled={saving}
                          className="w-16 px-2 py-1 text-xs rounded bg-slate-900 border border-slate-700 focus:border-neutral focus:outline-none disabled:opacity-50"
                        />
                      </div>
                      
                      <div className="flex items-center gap-2">
                        <label className="text-xs text-slate-500">Has Agenda:</label>
                        <button
                          type="button"
                          disabled={saving}
                          onClick={() => handleEnrichmentChange(event.id, "has_agenda", !currentHasAgenda)}
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
