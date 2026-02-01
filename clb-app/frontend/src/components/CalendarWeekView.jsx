import React, { useState, useRef, useEffect } from "react";
import CostBreakdownModal from "./CostBreakdownModal";
import { updateEvent, addEvent, deleteEvent } from "../services/api";

// 7-day week (includes Sat/Sun)
const WEEKDAYS = ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"];
const DAILY_BUDGET = 20;

// Format time in EST
const formatTimeEST = (isoString) => {
  if (!isoString) return "";
  return new Date(isoString).toLocaleTimeString("en-US", {
    hour: "2-digit",
    minute: "2-digit",
    timeZone: "America/New_York",
  });
};

// Get weekday in EST
const getWeekdayEST = (isoString) => {
  if (!isoString) return "";
  return new Date(isoString).toLocaleDateString("en-US", {
    weekday: "short",
    timeZone: "America/New_York",
  });
};

// Get current time in EST
const nowEST = () => {
  return new Date(new Date().toLocaleString("en-US", { timeZone: "America/New_York" }));
};

// Scrollable layout constants
const DAY_BLOCK_WIDTH = 291;
const GAP = 12;
const TOTAL_SCROLL_WIDTH = 7 * DAY_BLOCK_WIDTH + 6 * GAP;
const SCROLL_AMOUNT = Math.ceil(TOTAL_SCROLL_WIDTH / 2);

// Calculate event card height based on duration (min 40px, scales with duration)
const getEventHeight = (durationMinutes) => {
  const minHeight = 48; // Minimum height for very short events
  const pixelsPerMinute = 1.2; // Scale factor
  const calculated = Math.max(minHeight, durationMinutes * pixelsPerMinute);
  return Math.min(calculated, 150); // Cap at 150px to prevent huge cards
};

const getEventTypeColor = (type, isCompleted) => {
  if (isCompleted) return "border-l-2 border-slate-600 opacity-60";
  switch (type) {
    case "recovery": return "border-l-2 border-recovery";
    case "deep_work": return "border-l-2 border-neutral";
    case "meeting": return "border-l-2 border-warning";
    case "admin": return "border-l-2 border-warning";
    default: return "border-l-2 border-slate-600";
  }
};

// Check if event's end time has passed (in EST)
const isEventPastEndTime = (event) => {
  const now = nowEST();
  const endTime = new Date(new Date(event.end_time).toLocaleString("en-US", { timeZone: "America/New_York" }));
  return now >= endTime;
};

// Get effective cost (prorated if completed early, full if auto-completed)
const getEffectiveCost = (event) => {
  const isPast = isEventPastEndTime(event);
  
  if (event.is_completed && event.prorated_cost !== null && event.prorated_cost !== undefined) {
    // Manually completed early - use prorated cost
    return event.prorated_cost;
  } else if (event.is_completed || isPast) {
    // Auto-completed or manually completed without proration
    return event.calculated_cost || 0;
  }
  // Not yet completed
  return 0;
};

const CalendarWeekView = ({ events = [], onEventsChange }) => {
  const [selectedEvent, setSelectedEvent] = useState(null);
  const [editingEvent, setEditingEvent] = useState(null);
  const [editForm, setEditForm] = useState(null);
  const [isEditingOpen, setIsEditingOpen] = useState(false);
  const [returnToEditOnClose, setReturnToEditOnClose] = useState(false);
  const [collisionWarning, setCollisionWarning] = useState(null); // { newEvent, collidingEvents }
  const [isCreatingNew, setIsCreatingNew] = useState(false); // true when adding new event
  const [newEventTargetDate, setNewEventTargetDate] = useState(null); // target date for new event
  const [draggedEvent, setDraggedEvent] = useState(null); // event being dragged
  const [dragOverDay, setDragOverDay] = useState(null); // day being hovered during drag
  const [deleteConfirm, setDeleteConfirm] = useState(null); // event to delete (for confirmation modal)
  const scrollRef = useRef(null);

  // Check if two events overlap in time
  const eventsOverlap = (event1, event2) => {
    const start1 = new Date(event1.start_time);
    const end1 = new Date(event1.end_time);
    const start2 = new Date(event2.start_time);
    const end2 = new Date(event2.end_time);
    return start1 < end2 && start2 < end1;
  };

  // Find events that collide with a given event (using time objects for pending events)
  const findCollidingEvents = (eventData, existingEvents, excludeId = null) => {
    return existingEvents.filter((e) => {
      if (excludeId && e.id === excludeId) return false;
      return eventsOverlap(eventData, e);
    });
  };

  // Extract time (HH:MM) in EST from ISO string
  const toTimeInput = (isoString) => {
    if (!isoString) return "";
    return new Date(isoString).toLocaleTimeString("en-US", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "America/New_York",
    });
  };

  const openEditModal = (event) => {
    setEditingEvent(event);
    setEditForm({
      title: event.title || "",
      description: event.description || "",
      start_time: toTimeInput(event.start_time),
      end_time: toTimeInput(event.end_time),
      event_type: event.event_type || "",
    });
    setIsCreatingNew(false);
    setNewEventTargetDate(null);
    setIsEditingOpen(true);
  };

  // Open modal for creating a new event (no API call yet)
  const openNewEventModal = (targetDate) => {
    const startTime = new Date(targetDate);
    startTime.setHours(9, 0, 0, 0);
    const endTime = new Date(startTime);
    endTime.setMinutes(endTime.getMinutes() + 30);
    
    setEditingEvent({
      id: null, // null indicates new event
      title: "",
      description: "",
      start_time: startTime.toISOString(),
      end_time: endTime.toISOString(),
      duration_minutes: 30,
      event_type: "meeting",
    });
    setEditForm({
      title: "",
      description: "",
      start_time: "09:00",
      end_time: "09:30",
      event_type: "meeting",
    });
    setIsCreatingNew(true);
    setNewEventTargetDate(targetDate);
    setIsEditingOpen(true);
  };

  const closeEditModal = () => {
    setEditingEvent(null);
    setEditForm(null);
    setIsEditingOpen(false);
    setReturnToEditOnClose(false);
    setIsCreatingNew(false);
    setNewEventTargetDate(null);
  };

  const hideEditModal = () => {
    setIsEditingOpen(false);
  };

  const scroll = (direction) => {
    if (!scrollRef.current) return;
    scrollRef.current.scrollBy({
      left: direction === "left" ? -SCROLL_AMOUNT : SCROLL_AMOUNT,
      behavior: "smooth",
    });
  };

  // Handle checkbox toggle
  const handleToggleComplete = async (e, event) => {
    e.stopPropagation();
    const newCompleted = !event.is_completed;
    await updateEvent(event.id, { is_completed: newCompleted });
    if (onEventsChange) onEventsChange();
  };

  // Handle delete event - show confirmation modal
  const handleDeleteClick = (e, event) => {
    e.stopPropagation();
    setDeleteConfirm(event);
  };

  // Confirm delete
  const handleConfirmDelete = async () => {
    if (deleteConfirm) {
      await deleteEvent(deleteConfirm.id);
      if (onEventsChange) onEventsChange();
    }
    setDeleteConfirm(null);
  };

  // Cancel delete
  const handleCancelDelete = () => {
    setDeleteConfirm(null);
  };

  // Handle add new event - just opens the modal, event created on save
  const handleAddEvent = (dayName) => {
    // Find the date for this day in the current week (using EST)
    const now = nowEST();
    const dayIndex = WEEKDAYS.indexOf(dayName);
    const currentDayIndex = now.getDay();
    
    // Calculate diff - handle week wrap correctly
    const diff = dayIndex - currentDayIndex;
    
    // Get the target date for this weekday
    const targetDate = new Date(now);
    targetDate.setDate(now.getDate() + diff);
    
    openNewEventModal(targetDate);
  };

  // Handle collision warning response - keep the event anyway
  const handleKeepAnyway = async () => {
    if (collisionWarning?.pendingEventData) {
      await performSave(
        collisionWarning.pendingEventData,
        collisionWarning.isNew,
        collisionWarning.existingEventId
      );
    }
    setCollisionWarning(null);
  };

  // Handle collision warning response - cancel the save
  const handleCancelSave = () => {
    setCollisionWarning(null);
    // Keep the edit modal open so user can change the time
  };

  const handleSaveEdit = async () => {
    if (!editForm) return;
    
    // Build the event times from form
    let baseDate;
    if (isCreatingNew && newEventTargetDate) {
      baseDate = new Date(newEventTargetDate);
    } else if (editingEvent) {
      baseDate = new Date(editingEvent.start_time);
    } else {
      return;
    }
    
    let startDate = new Date(baseDate);
    let endDate = new Date(baseDate);
    
    if (editForm.start_time) {
      const [hours, minutes] = editForm.start_time.split(":").map(Number);
      startDate.setHours(hours, minutes, 0, 0);
    }
    
    if (editForm.end_time) {
      const [hours, minutes] = editForm.end_time.split(":").map(Number);
      endDate.setHours(hours, minutes, 0, 0);
      // Handle case where end time is before start (crosses midnight - add a day)
      if (endDate <= startDate) {
        endDate.setDate(endDate.getDate() + 1);
      }
    }
    
    const durationMinutes = Math.max(1, Math.round((endDate - startDate) / 60000));
    
    const eventData = {
      title: editForm.title || "Untitled Event",
      description: editForm.description,
      event_type: editForm.event_type || null,
      start_time: startDate.toISOString(),
      end_time: endDate.toISOString(),
      duration_minutes: durationMinutes,
    };
    
    // Check for collisions before saving
    const pendingEvent = { start_time: eventData.start_time, end_time: eventData.end_time };
    const collisions = findCollidingEvents(
      pendingEvent, 
      events, 
      isCreatingNew ? null : editingEvent?.id
    );
    
    if (collisions.length > 0) {
      // Show collision warning - store the pending save data
      setCollisionWarning({
        pendingEventData: eventData,
        collidingEvents: collisions,
        isNew: isCreatingNew,
        existingEventId: isCreatingNew ? null : editingEvent?.id,
      });
      return; // Don't save yet
    }
    
    // No collisions, proceed with save
    await performSave(eventData, isCreatingNew, editingEvent?.id);
  };

  // Actually perform the save (after collision check passes or user confirms)
  const performSave = async (eventData, isNew, existingId) => {
    if (isNew) {
      await addEvent(eventData);
    } else {
      await updateEvent(existingId, eventData);
    }
    if (onEventsChange) onEventsChange();
    closeEditModal();
  };

  // ===== DRAG AND DROP HANDLERS =====
  
  // Handle drag start
  const handleDragStart = (e, event) => {
    setDraggedEvent(event);
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData("text/plain", event.id);
    // Add a slight delay to allow the drag image to be captured
    setTimeout(() => {
      e.target.style.opacity = "0.5";
    }, 0);
  };

  // Handle drag end
  const handleDragEnd = (e) => {
    e.target.style.opacity = "1";
    setDraggedEvent(null);
    setDragOverDay(null);
  };

  // Handle drag over a day column
  const handleDragOver = (e, day) => {
    e.preventDefault();
    e.dataTransfer.dropEffect = "move";
    if (dragOverDay !== day) {
      setDragOverDay(day);
    }
  };

  // Handle drag leave
  const handleDragLeave = (e) => {
    // Only clear if leaving the day container (not entering a child)
    if (!e.currentTarget.contains(e.relatedTarget)) {
      setDragOverDay(null);
    }
  };

  // Handle drop on a day
  const handleDrop = async (e, targetDay) => {
    e.preventDefault();
    setDragOverDay(null);
    
    if (!draggedEvent) return;
    
    const eventCurrentDay = getWeekdayEST(draggedEvent.start_time);
    
    // If dropping on same day, do nothing
    if (eventCurrentDay === targetDay) {
      setDraggedEvent(null);
      return;
    }
    
    // Calculate the new date for the event
    const now = nowEST();
    const targetDayIndex = WEEKDAYS.indexOf(targetDay);
    const currentDayIndex = now.getDay();
    const diff = targetDayIndex - currentDayIndex;
    
    const targetDate = new Date(now);
    targetDate.setDate(now.getDate() + diff);
    
    // Get the original event's time (just time portion)
    const originalStart = new Date(draggedEvent.start_time);
    const originalEnd = new Date(draggedEvent.end_time);
    
    // Create new dates preserving the time
    const newStartDate = new Date(targetDate);
    newStartDate.setHours(originalStart.getHours(), originalStart.getMinutes(), 0, 0);
    
    const newEndDate = new Date(targetDate);
    newEndDate.setHours(originalEnd.getHours(), originalEnd.getMinutes(), 0, 0);
    
    // If the event crossed midnight originally, adjust end date
    if (originalEnd.getDate() !== originalStart.getDate()) {
      newEndDate.setDate(newEndDate.getDate() + 1);
    }
    
    const durationMinutes = Math.max(1, Math.round((newEndDate - newStartDate) / 60000));
    
    const eventData = {
      start_time: newStartDate.toISOString(),
      end_time: newEndDate.toISOString(),
      duration_minutes: durationMinutes,
    };
    
    // Check for collisions on the target day
    const pendingEvent = { start_time: eventData.start_time, end_time: eventData.end_time };
    const collisions = findCollidingEvents(pendingEvent, events, draggedEvent.id);
    
    if (collisions.length > 0) {
      // Show collision warning
      setCollisionWarning({
        pendingEventData: eventData,
        collidingEvents: collisions,
        isNew: false,
        existingEventId: draggedEvent.id,
      });
      setDraggedEvent(null);
      return;
    }
    
    // No collisions, update the event
    await updateEvent(draggedEvent.id, eventData);
    if (onEventsChange) onEventsChange();
    setDraggedEvent(null);
  };

  // Group events by weekday (in EST)
  const grouped = events.reduce((acc, event) => {
    const day = getWeekdayEST(event.start_time);
    if (!acc[day]) acc[day] = [];
    acc[day].push(event);
    return acc;
  }, {});

  // Sort events within each day by start time
  Object.keys(grouped).forEach(day => {
    grouped[day].sort((a, b) => new Date(a.start_time) - new Date(b.start_time));
  });

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-4">Week View</div>
      <p className="text-xs text-slate-500 mb-3">
        Drag events to move between days • Click to edit • Check box to mark complete
      </p>
      
      <div className="flex items-stretch gap-2">
        <button
          type="button"
          onClick={() => scroll("left")}
          aria-label="Scroll week left"
          className="flex-shrink-0 self-center w-8 h-8 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
        >
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
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
              // Use effective cost (prorated for early completions)
              const totalCost = items.reduce((sum, e) => sum + getEffectiveCost(e), 0);
              const scheduledCost = items.reduce((sum, e) => sum + (e.calculated_cost || 0), 0);

              return (
                <div 
                  key={day} 
                  className={`flex-shrink-0 w-[291px] min-w-[291px] h-[360px] bg-slate-950/40 rounded-xl p-3 flex flex-col transition-all ${
                    dragOverDay === day ? "ring-2 ring-neutral bg-slate-900/60" : ""
                  }`}
                  onDragOver={(e) => handleDragOver(e, day)}
                  onDragLeave={handleDragLeave}
                  onDrop={(e) => handleDrop(e, day)}
                >
                  <div className="flex items-center justify-between mb-2">
                    <div className="text-sm font-medium text-slate-300">{day}</div>
                    <div className="flex items-center gap-2">
                      {items.length > 0 && (
                        <div className={`text-xs font-semibold ${totalCost > DAILY_BUDGET ? "text-debt" : "text-slate-400"}`}>
                          {totalCost !== scheduledCost ? (
                            <span title={`Scheduled: ${scheduledCost} pts`}>
                              {totalCost}/{scheduledCost} pts
                            </span>
                          ) : (
                            <span>{scheduledCost} pts</span>
                          )}
                        </div>
                      )}
                      <button
                        onClick={() => handleAddEvent(day)}
                        className="w-5 h-5 rounded bg-slate-700 hover:bg-slate-600 text-slate-300 hover:text-white flex items-center justify-center transition-colors"
                        title="Add event"
                      >
                        <svg className="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 4v16m8-8H4" />
                        </svg>
                      </button>
                    </div>
                  </div>
                  <div className="space-y-1.5 min-h-0 flex-1 overflow-auto">
                    {items.length === 0 ? (
                      <div className="text-xs text-slate-600">No events</div>
                    ) : (
                      items.map((event) => {
                        const isPast = isEventPastEndTime(event);
                        const isChecked = event.is_completed || isPast;
                        const effectiveCost = getEffectiveCost(event);
                        const scheduledEventCost = event.calculated_cost || 0;
                        const hasProration = event.is_completed && event.prorated_cost !== null && event.prorated_cost !== undefined && event.prorated_cost < scheduledEventCost;
                        const eventHeight = getEventHeight(event.duration_minutes || 30);
                        
                        return (
                          <div
                            key={event.id}
                            draggable
                            onDragStart={(e) => handleDragStart(e, event)}
                            onDragEnd={handleDragEnd}
                            style={{ minHeight: `${eventHeight}px` }}
                            className={`text-xs rounded-lg bg-slate-900 p-2 cursor-grab hover:bg-slate-800 transition flex flex-col ${getEventTypeColor(event.event_type, isChecked)} ${
                              draggedEvent?.id === event.id ? "opacity-50" : ""
                            }`}
                            onClick={() => openEditModal(event)}
                          >
                            {/* Top row: Start time, title, checkbox, delete */}
                            <div className="flex items-start gap-2">
                              {/* Start time on the left */}
                              <div className="text-slate-500 text-[10px] w-12 flex-shrink-0 pt-0.5">
                                {formatTimeEST(event.start_time)}
                              </div>
                              
                              {/* Checkbox */}
                              <input
                                type="checkbox"
                                checked={isChecked}
                                onChange={(e) => handleToggleComplete(e, event)}
                                onClick={(e) => e.stopPropagation()}
                                className="event-checkbox mt-0.5"
                                title={isPast ? "Auto-completed (time passed)" : "Mark as complete"}
                              />
                              
                              {/* Title and points */}
                              <div className="flex-1 min-w-0">
                                <div className={`font-medium truncate ${isChecked ? "line-through text-slate-500" : ""}`}>
                                  {event.title}
                                </div>
                              </div>
                              
                              {/* Points */}
                              <div className="flex-shrink-0 text-right">
                                {hasProration ? (
                                  <span className="text-recovery" title={`Saved ${scheduledEventCost - effectiveCost} pts by finishing early`}>
                                    {effectiveCost}/{scheduledEventCost}
                                  </span>
                                ) : (
                                  <span className="text-slate-500">{scheduledEventCost} pts</span>
                                )}
                              </div>
                              
                              {/* Delete button */}
                              <button
                                onClick={(e) => handleDeleteClick(e, event)}
                                className="text-slate-600 hover:text-debt transition-colors flex-shrink-0"
                                title="Delete event"
                              >
                                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M6 18L18 6M6 6l12 12" />
                                </svg>
                              </button>
                            </div>
                            
                            {/* Spacer to push end time to bottom */}
                            <div className="flex-1"></div>
                            
                            {/* Bottom row: End time */}
                            <div className="text-slate-500 text-[10px] mt-1">
                              {formatTimeEST(event.end_time)}
                            </div>
                          </div>
                        );
                      })
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
          <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 5l7 7-7 7" />
          </svg>
        </button>
      </div>
      
      {/* CostBreakdownModal */}
      {selectedEvent && (
        <CostBreakdownModal 
          event={selectedEvent} 
          onClose={() => {
            setSelectedEvent(null);
            if (returnToEditOnClose && editingEvent && editForm) {
              setIsEditingOpen(true);
            }
            setReturnToEditOnClose(false);
          }} 
        />
      )}

      {/* Edit Event Modal */}
      {editingEvent && editForm && isEditingOpen && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-lg rounded-2xl bg-slate-900 border border-slate-800 p-5 shadow-xl">
            <div className="flex items-center justify-between mb-4">
              <div className="text-lg font-semibold">{isCreatingNew ? "New Event" : "Edit Event"}</div>
              <button
                type="button"
                onClick={closeEditModal}
                className="text-slate-400 hover:text-slate-200"
                aria-label="Close edit modal"
              >
                ✕
              </button>
            </div>

            <div className="space-y-3">
              <div>
                <label className="text-xs text-slate-400">Title</label>
                <input
                  type="text"
                  value={editForm.title}
                  onChange={(e) => setEditForm({ ...editForm, title: e.target.value })}
                  className="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-600"
                />
              </div>

              <div>
                <label className="text-xs text-slate-400">Description</label>
                <textarea
                  value={editForm.description}
                  onChange={(e) => setEditForm({ ...editForm, description: e.target.value })}
                  rows={3}
                  className="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-600"
                />
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                <div>
                  <label className="text-xs text-slate-400">Start time</label>
                  <input
                    type="time"
                    value={editForm.start_time}
                    onChange={(e) => setEditForm({ ...editForm, start_time: e.target.value })}
                    className="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-600"
                  />
                </div>
                <div>
                  <label className="text-xs text-slate-400">End time</label>
                  <input
                    type="time"
                    value={editForm.end_time}
                    onChange={(e) => setEditForm({ ...editForm, end_time: e.target.value })}
                    className="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-600"
                  />
                </div>
              </div>

              <div>
                <label className="text-xs text-slate-400">Event type</label>
                <select
                  value={editForm.event_type || ""}
                  onChange={(e) => setEditForm({ ...editForm, event_type: e.target.value })}
                  className="mt-1 w-full rounded-lg bg-slate-800 border border-slate-700 px-3 py-2 text-sm text-slate-100 focus:outline-none focus:ring-2 focus:ring-slate-600"
                >
                  <option value="">Unspecified</option>
                  <option value="meeting">Meeting</option>
                  <option value="deep_work">Deep Work</option>
                  <option value="admin">Admin</option>
                  <option value="recovery">Recovery</option>
                </select>
              </div>
            </div>

            <div className="mt-5 flex flex-wrap items-center justify-between gap-2">
              {!isCreatingNew && editingEvent?.id ? (
                <button
                  type="button"
                  onClick={() => {
                    hideEditModal();
                    setReturnToEditOnClose(true);
                    setSelectedEvent(editingEvent);
                  }}
                  className="text-xs text-slate-400 hover:text-slate-200"
                >
                  View cost breakdown
                </button>
              ) : (
                <div></div>
              )}
              <div className="flex gap-2">
                <button
                  type="button"
                  onClick={closeEditModal}
                  className="px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm hover:bg-slate-700"
                >
                  Cancel
                </button>
                <button
                  type="button"
                  onClick={handleSaveEdit}
                  className="px-4 py-2 rounded-lg bg-emerald-600 text-white text-sm hover:bg-emerald-500"
                >
                  Save
                </button>
              </div>
            </div>
          </div>
        </div>
      )}

      {/* Collision Warning Modal */}
      {collisionWarning && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-md rounded-2xl bg-slate-900 border border-slate-800 p-5 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-warning/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-warning" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-3L13.732 4c-.77-1.333-2.694-1.333-3.464 0L3.34 16c-.77 1.333.192 3 1.732 3z" />
                </svg>
              </div>
              <div className="text-lg font-semibold">Time Conflict</div>
            </div>

            <p className="text-sm text-slate-300 mb-4">
              This event overlaps with {collisionWarning.collidingEvents.length === 1 ? "an existing event" : `${collisionWarning.collidingEvents.length} existing events`}:
            </p>

            <div className="space-y-2 mb-5 max-h-40 overflow-auto">
              {collisionWarning.collidingEvents.map((event) => (
                <div key={event.id} className="text-sm bg-slate-800 rounded-lg p-3">
                  <div className="font-medium">{event.title}</div>
                  <div className="text-xs text-slate-400 mt-1">
                    {formatTimeEST(event.start_time)} – {formatTimeEST(event.end_time)}
                  </div>
                </div>
              ))}
            </div>

            <p className="text-sm text-slate-400 mb-4">
              Do you want to save anyway or go back to edit the time?
            </p>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleCancelSave}
                className="flex-1 px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm hover:bg-slate-700"
              >
                Edit Time
              </button>
              <button
                type="button"
                onClick={handleKeepAnyway}
                className="flex-1 px-4 py-2 rounded-lg bg-warning text-slate-900 text-sm font-medium hover:bg-warning/90"
              >
                Save Anyway
              </button>
            </div>
          </div>
        </div>
      )}

      {/* Delete Confirmation Modal */}
      {deleteConfirm && (
        <div className="fixed inset-0 z-[60] flex items-center justify-center bg-black/60 p-4">
          <div className="w-full max-w-sm rounded-2xl bg-slate-900 border border-slate-800 p-5 shadow-xl">
            <div className="flex items-center gap-3 mb-4">
              <div className="w-10 h-10 rounded-full bg-debt/20 flex items-center justify-center">
                <svg className="w-5 h-5 text-debt" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 7l-.867 12.142A2 2 0 0116.138 21H7.862a2 2 0 01-1.995-1.858L5 7m5 4v6m4-6v6m1-10V4a1 1 0 00-1-1h-4a1 1 0 00-1 1v3M4 7h16" />
                </svg>
              </div>
              <div className="text-lg font-semibold">Delete Event</div>
            </div>

            <p className="text-sm text-slate-300 mb-2">
              Are you sure you want to delete this event?
            </p>

            <div className="bg-slate-800 rounded-lg p-3 mb-5">
              <div className="font-medium text-sm">{deleteConfirm.title}</div>
              <div className="text-xs text-slate-400 mt-1">
                {formatTimeEST(deleteConfirm.start_time)} – {formatTimeEST(deleteConfirm.end_time)}
              </div>
              {deleteConfirm.calculated_cost && (
                <div className="text-xs text-slate-500 mt-1">
                  {deleteConfirm.calculated_cost} pts
                </div>
              )}
            </div>

            <div className="flex gap-3">
              <button
                type="button"
                onClick={handleCancelDelete}
                className="flex-1 px-4 py-2 rounded-lg bg-slate-800 text-slate-200 text-sm hover:bg-slate-700"
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleConfirmDelete}
                className="flex-1 px-4 py-2 rounded-lg bg-debt text-white text-sm font-medium hover:bg-debt/90"
              >
                Delete
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default CalendarWeekView;
