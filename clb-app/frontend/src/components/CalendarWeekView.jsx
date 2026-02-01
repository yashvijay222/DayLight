import React, { useState } from "react";
import CostBreakdownModal from "./CostBreakdownModal";

const WEEKDAYS = ["Mon", "Tue", "Wed", "Thu", "Fri"];
const DAILY_BUDGET = 20;

const getEventTypeColor = (type) => {
  switch (type) {
    case "recovery": return "border-l-2 border-recovery";
    case "deep_work": return "border-l-2 border-neutral";
    case "meeting": return "border-l-2 border-warning";
    case "admin": return "border-l-2 border-warning";
    default: return "border-l-2 border-slate-600";
  }
};

const CalendarWeekView = ({ events = [] }) => {
  const [selectedEvent, setSelectedEvent] = useState(null);
  
  // Group events by weekday
  const grouped = events.reduce((acc, event) => {
    const day = new Date(event.start_time).toLocaleDateString("en-US", {
      weekday: "short"
    });
    if (!acc[day]) acc[day] = [];
    acc[day].push(event);
    return acc;
  }, {});

  // Sort events within each day by start time
  Object.keys(grouped).forEach(day => {
    grouped[day].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  });

  if (events.length === 0) {
    return (
      <div className="card">
        <div className="text-lg font-semibold mb-4">Week View</div>
        <div className="text-slate-400 text-sm">No events scheduled this week.</div>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-4">Week View</div>
      <p className="text-xs text-slate-500 mb-3">Click on an event to see cost breakdown</p>
      <div className="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-5 gap-3">
        {WEEKDAYS.map((day) => {
          const items = grouped[day] || [];
          const totalCost = items.reduce((sum, e) => sum + (e.calculated_cost || 0), 0);
          
          return (
            <div key={day} className="bg-slate-950/40 rounded-xl p-3 min-h-[120px]">
              <div className="flex items-center justify-between mb-2">
                <div className="text-sm font-medium text-slate-300">{day}</div>
                {items.length > 0 && (
                  <div className={`text-xs font-semibold ${totalCost > DAILY_BUDGET ? "text-debt" : "text-slate-400"}`}>
                    {totalCost} pts
                  </div>
                )}
              </div>
              <div className="space-y-1.5">
                {items.length === 0 ? (
                  <div className="text-xs text-slate-600">No events</div>
                ) : (
                  items.map((event) => (
                    <div 
                      key={event.id} 
                      className={`text-xs rounded-lg bg-slate-900 p-2 cursor-pointer hover:bg-slate-800 transition ${getEventTypeColor(event.event_type)}`}
                      onClick={() => setSelectedEvent(event)}
                    >
                      <div className="font-medium truncate">{event.title}</div>
                      <div className="text-slate-500 flex justify-between mt-0.5">
                        <span>{new Date(event.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
                        <span>{event.calculated_cost || 0} pts</span>
                      </div>
                    </div>
                  ))
                )}
              </div>
            </div>
          );
        })}
      </div>
      
      {selectedEvent && (
        <CostBreakdownModal 
          event={selectedEvent} 
          onClose={() => setSelectedEvent(null)} 
        />
      )}
    </div>
  );
};

export default CalendarWeekView;
