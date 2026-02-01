import React, { useState, useRef } from "react";
import CostBreakdownModal from "./CostBreakdownModal";

// 7-day week (your feature: includes Sat/Sun)
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAILY_BUDGET = 20;

// Scrollable layout constants (your feature)
const DAY_BLOCK_WIDTH = 291;
const DAY_BLOCK_HEIGHT = 196;
const GAP = 12;
const TOTAL_SCROLL_WIDTH = 7 * DAY_BLOCK_WIDTH + 6 * GAP;
const SCROLL_AMOUNT = Math.ceil(TOTAL_SCROLL_WIDTH / 2); // 2 clicks to reach the end

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
  // CostBreakdownModal state (from main)
  const [selectedEvent, setSelectedEvent] = useState(null);
  
  // Scroll functionality (your feature)
  const scrollRef = useRef(null);

  const scroll = (direction) => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({
      left: direction === "left" ? -SCROLL_AMOUNT : SCROLL_AMOUNT,
      behavior: "smooth",
    });
  };

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
      
      {/* Scrollable container with arrow buttons (your feature) */}
      <div className="flex items-stretch gap-2">
        <button
          type="button"
          onClick={() => scroll("left")}
          aria-label="Scroll week left"
          className="flex-shrink-0 self-center w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M15 19l-7-7 7-7" />
          </svg>
        </button>
        
        <div
          ref={scrollRef}
          className="week-view-scroll flex-1 overflow-x-auto overflow-y-visible pb-2 min-w-0"
        >
          <div className="flex flex-nowrap gap-3">
            {WEEKDAYS.map((day) => {
              const items = grouped[day] || [];
              const totalCost = items.reduce((sum, e) => sum + (e.calculated_cost || 0), 0);

              return (
                <div key={day} className="flex-shrink-0 w-[291px] min-w-[291px] h-[196px] bg-slate-950/40 rounded-xl p-3 flex flex-col">
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-medium text-slate-300">{day}</div>
                    {items.length > 0 && (
                      <div className={`text-xs font-semibold ${totalCost > DAILY_BUDGET ? "text-debt" : "text-slate-400"}`}>
                        {totalCost} pts
                      </div>
                    )}
                  </div>
                  <div className="space-y-1.5 min-h-0 flex-1 overflow-auto">
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
        </div>
        
        <button
          type="button"
          onClick={() => scroll("right")}
          aria-label="Scroll week right"
          className="flex-shrink-0 self-center w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden="true">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
      
      {/* CostBreakdownModal (from main) */}
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
