import React from "react";

const costColor = (cost) => {
  if (cost >= 7) return "border-debt text-debt";
  if (cost >= 4) return "border-warning text-warning";
  return "border-recovery text-recovery";
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
          </div>
        </div>
        <div className="text-xl font-semibold">{cost}</div>
      </div>
      {children && <div className="mt-3">{children}</div>}
    </div>
  );
};

export default EventCard;
