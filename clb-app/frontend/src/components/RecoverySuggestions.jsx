import React, { useState } from "react";

const RecoverySuggestions = ({ activities = [], onSchedule }) => {
  const [scheduling, setScheduling] = useState(null);

  const handleSchedule = async (activity, slot) => {
    const key = `${activity.activity_type}-${slot.start_time}`;
    setScheduling(key);
    await onSchedule({
      title: activity.name,
      start_time: slot.start_time,
      end_time: slot.end_time,
      duration_minutes: activity.duration_minutes,
      participants: 1,
      has_agenda: true,
      requires_tool_switch: false,
      event_type: "recovery"
    });
    setScheduling(null);
  };

  if (activities.length === 0) {
    return (
      <div className="card">
        <div className="text-lg font-semibold mb-1">Recovery Activities</div>
        <p className="text-slate-400 text-sm">
          No recovery activities suggested. You're within your cognitive budget!
        </p>
      </div>
    );
  }

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-1">Recovery Activities</div>
      <p className="text-xs text-slate-400 mb-3">
        Schedule recovery activities to reduce your cognitive debt. Pick a time slot below.
      </p>
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        {activities.map((activity) => (
          <div 
            key={activity.activity_type} 
            className="bg-slate-950/40 rounded-xl p-3 border-l-4 border-recovery"
          >
            <div className="flex items-center justify-between">
              <div className="font-semibold">{activity.name}</div>
              <div className="text-recovery text-sm font-semibold">
                {activity.point_value} pts
              </div>
            </div>
            <div className="text-xs text-slate-400 mt-1">{activity.description}</div>
            <div className="text-xs text-slate-500 mt-1">
              Duration: {activity.duration_minutes} min
            </div>
            <div className="mt-3">
              <div className="text-xs text-slate-500 mb-1">Available slots:</div>
              <div className="flex flex-wrap gap-2">
                {(activity.suggested_slots || []).length === 0 ? (
                  <span className="text-xs text-slate-500">No gaps in schedule</span>
                ) : (
                  (activity.suggested_slots || []).slice(0, 4).map((slot, idx) => {
                    const key = `${activity.activity_type}-${slot.start_time}`;
                    return (
                      <button
                        key={idx}
                        onClick={() => handleSchedule(activity, slot)}
                        disabled={scheduling === key}
                        className="px-2 py-1 rounded-lg bg-recovery/20 hover:bg-recovery/40 text-xs disabled:opacity-50 border border-recovery/30"
                      >
                        {scheduling === key ? "..." : (
                          <>
                            {slot.day.slice(0, 3)} {new Date(slot.start_time).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                          </>
                        )}
                      </button>
                    );
                  })
                )}
              </div>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
};

export default RecoverySuggestions;
