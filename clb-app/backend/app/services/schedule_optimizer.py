from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from app.models import Event, OptimizationSuggestion, TimeSlot


def generate_suggestions(events: List[Event], debt_amount: int) -> List[OptimizationSuggestion]:
    suggestions: List[OptimizationSuggestion] = []
    if debt_amount <= 0:
        return suggestions

    for event in events:
        if not event.is_flexible:
            continue

        if event.flexibility_reason == "skippable":
            suggestions.append(
                OptimizationSuggestion(
                    suggestion_id=str(uuid4()),
                    event_id=event.id,
                    suggestion_type="cancel",
                    debt_reduction=event.calculated_cost or 0,
                    reason="Skippable event provides immediate debt relief.",
                )
            )
        elif event.flexibility_reason == "moveable":
            new_time = event.start_time.replace(hour=15, minute=0)
            suggestions.append(
                OptimizationSuggestion(
                    suggestion_id=str(uuid4()),
                    event_id=event.id,
                    suggestion_type="postpone",
                    new_time=new_time,
                    debt_reduction=round((event.calculated_cost or 0) * 0.1),
                    reason="Afternoon scheduling reduces cognitive cost by 10%.",
                )
            )
        elif event.flexibility_reason == "required":
            continue

    if not suggestions:
        for event in events:
            if event.event_type == "meeting" and event.duration_minutes > 30:
                suggestions.append(
                    OptimizationSuggestion(
                        suggestion_id=str(uuid4()),
                        event_id=event.id,
                        suggestion_type="shorten",
                        debt_reduction=round((event.calculated_cost or 0) * 0.2),
                        reason="Shortening long meetings reduces fatigue.",
                    )
                )
                break

    return suggestions


def find_available_recovery_slots(events: List[Event], duration_minutes: int) -> List[TimeSlot]:
    if not events:
        return []

    sorted_events = sorted(events, key=lambda e: e.start_time)
    slots: List[TimeSlot] = []
    for i in range(len(sorted_events) - 1):
        current_end = sorted_events[i].end_time
        next_start = sorted_events[i + 1].start_time
        gap = (next_start - current_end).total_seconds() / 60
        if gap >= duration_minutes:
            slots.append(
                TimeSlot(
                    start_time=current_end,
                    end_time=current_end + timedelta(minutes=duration_minutes),
                    day=current_end.strftime("%A"),
                    available=True,
                )
            )
    return slots
