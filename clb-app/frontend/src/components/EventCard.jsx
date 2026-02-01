import React from "react";

const costColor = (cost) => {
  if (cost < 0) return "border-recovery text-recovery"; // Recovery events
  if (cost >= 7) return "border-debt text-debt";
  if (cost >= 4) return "border-warning text-warning";
  return "border-recovery text-recovery";
};

const getEventTypeLabel = (type) => {
  switch (type) {
    case "meeting": return "Meeting";
    case "deep_work": return "Deep Work";
    case "recovery": return "Recovery";
    case "admin": return "Admin";
    default: return type || "Unknown";
  }
};

const EventCard = ({ event, children }) => {
  const cost = event.calculated_cost ?? 0;
  return (
    <div className={`card border-l-4 ${costColor(cost)}`}>
      <div className="flex items-center justify-between">
        <div>
          <div className="text-lg font-semibold">{event.title}</div>
          <div className="text-xs text-slate-400">
            {new Date(event.start_time).toLocaleString()} • {event.duration_minutes} min
            {event.event_type && (
              <span className="ml-2 px-1.5 py-0.5 bg-slate-800 rounded text-slate-300">
                {getEventTypeLabel(event.event_type)}
              </span>
            )}
          </div>
        </div>
        <div className={`text-xl font-semibold ${cost < 0 ? "text-recovery" : ""}`}>
          {cost > 0 ? cost : cost} pts
        </div>
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
};

export default EventCard;
