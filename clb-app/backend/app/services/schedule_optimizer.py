from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.models import Event, OptimizationSuggestion, ScheduleChange, TimeSlot, WeekOptimizationProposal
from app.services.cognitive_calculator import (
    DAILY_BUDGET,
    calculate_event_cost,
    calculate_events_with_proximity,
)


def generate_suggestions(events: List[Event], debt_amount: int) -> List[OptimizationSuggestion]:
    """
    Generate optimization suggestions for movable events.
    Only considers is_flexible (True = movable, False = unmovable).
    """
    suggestions: List[OptimizationSuggestion] = []
    if debt_amount <= 0:
        return suggestions

    for event in events:
        # Only process movable events (is_flexible = True)
        if not event.is_flexible:
            continue
        
        # Skip recovery events (negative cost)
        if (event.calculated_cost or 0) <= 0:
            continue

        # Suggest moving to afternoon for cost reduction
        if event.start_time.hour < 14:
            new_time = event.start_time.replace(hour=15, minute=0)
            suggestions.append(
                OptimizationSuggestion(
                    suggestion_id=str(uuid4()),
                    event_id=event.id,
                    suggestion_type="postpone",
                    new_time=new_time,
                    debt_reduction=round((event.calculated_cost or 0) * 0.1),
                    reason="Moving to afternoon reduces cognitive cost by 10%.",
                )
            )

    # If we have movable long meetings, suggest shortening
    if not suggestions:
        for event in events:
            if event.is_flexible and event.event_type == "meeting" and event.duration_minutes > 30:
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
    """Find gaps between events where recovery activities could be scheduled."""
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


def _get_daily_costs(events: List[Event]) -> Dict[str, int]:
    """Calculate total cost per day."""
    daily_totals: Dict[str, int] = defaultdict(int)
    calculate_events_with_proximity(events)
    for event in events:
        day_key = event.start_time.strftime("%Y-%m-%d")
        daily_totals[day_key] += event.calculated_cost or 0
    return dict(daily_totals)


def _get_week_dates(events: List[Event]) -> List[datetime]:
    """Get list of weekday dates from the events."""
    if not events:
        return []
    
    min_date = min(e.start_time for e in events).date()
    # Get Monday of that week
    monday = min_date - timedelta(days=min_date.weekday())
    
    # Return Mon-Fri
    return [
        datetime.combine(monday + timedelta(days=i), datetime.min.time().replace(hour=9))
        for i in range(5)
    ]


def _find_earliest_slot(
    day_events: List[Event],
    duration_minutes: int,
    day_date: datetime,
    work_start: int = 9,
    work_end: int = 17,
) -> Optional[datetime]:
    """
    Find the earliest non-overlapping slot on a given day, packing events tightly.
    
    Args:
        day_events: Events already scheduled on this day
        duration_minutes: Duration of the event to place
        day_date: The date to schedule on
        work_start: Start of work day (hour)
        work_end: End of work day (hour)
    
    Returns:
        The earliest available start time, or None if no slot fits
    """
    sorted_events = sorted(day_events, key=lambda e: e.start_time)
    
    # Start cursor at beginning of work day
    cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
    
    for event in sorted_events:
        # Check if there's a gap before this event that fits our duration
        gap_before = (event.start_time - cursor).total_seconds() / 60
        
        if gap_before >= duration_minutes:
            # Found a slot - return it (pack early)
            return cursor
        
        # Move cursor to after this event
        cursor = max(cursor, event.end_time)
    
    # Check slot after all events
    end_of_day = day_date.replace(hour=work_end, minute=0, second=0, microsecond=0)
    remaining = (end_of_day - cursor).total_seconds() / 60
    
    if remaining >= duration_minutes:
        return cursor
    
    return None  # No slot found


def _score_day_for_event(
    day_events: List[Event],
    event: Event,
    day_date: datetime,
) -> Tuple[Tuple[float, float, float], Optional[datetime]]:
    """
    Score a day for placing an event. Lower score = better.
    Priority:
    1) Finish the day as early as possible
    2) Minimize mid-day gaps (gap_penalty = 2*hours - 1)
    3) Avoid exceeding DAILY_BUDGET when possible
    """
    slot = _find_earliest_slot(day_events, event.duration_minutes, day_date)
    if slot is None:
        return (float("inf"), float("inf"), float("inf")), None

    candidate = _clone_event(
        event,
        start_time=slot,
        end_time=slot + timedelta(minutes=event.duration_minutes),
    )
    simulated = [_clone_event(e) for e in day_events] + [candidate]
    calculate_events_with_proximity(simulated)

    finish_time = max(e.end_time for e in simulated)
    finish_score = finish_time.hour + finish_time.minute / 60.0
    gap_penalty = _calculate_gap_penalty(simulated, day_date)
    daily_cost = sum(e.calculated_cost or 0 for e in simulated)
    overflow = max(0, daily_cost - DAILY_BUDGET)

    return (finish_score, float(gap_penalty), float(overflow)), slot


def _clone_event(
    event: Event,
    start_time: Optional[datetime] = None,
    end_time: Optional[datetime] = None,
) -> Event:
    """Create a safe copy of an event for simulation."""
    data = event.model_dump()
    if start_time is not None:
        data["start_time"] = start_time
    if end_time is not None:
        data["end_time"] = end_time
        if start_time is not None:
            data["duration_minutes"] = int((end_time - start_time).total_seconds() / 60)
    return Event(**data)


def _calculate_gap_penalty(
    day_events: List[Event],
    day_date: datetime,
    work_start: int = 9,
) -> int:
    """
    Penalize mid-day gaps (free time between 9am and last event).
    gap_penalty = 2*hours - 1, where hours are consecutive free hours.
    """
    if not day_events:
        return 0

    sorted_events = sorted(day_events, key=lambda e: e.start_time)
    last_end = max(e.end_time for e in sorted_events)
    cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
    penalty = 0

    for event in sorted_events:
        if cursor >= last_end:
            break
        gap_end = min(event.start_time, last_end)
        if gap_end > cursor:
            gap_minutes = (gap_end - cursor).total_seconds() / 60
            hours = int((gap_minutes + 59) // 60)  # round up to full hours
            if hours > 0:
                penalty += 2 * hours - 1
        cursor = max(cursor, event.end_time)

    return penalty


def optimize_week(events: List[Event]) -> WeekOptimizationProposal:
    """
    Generate a proposal to redistribute movable events across the week.
    
    Goals (in order of priority):
    1. Pack events early in the day (finish ASAP, maximize free evening time)
    2. Avoid overlaps (proper slot-finding)
    3. Keep each day's total debt ≤ DAILY_BUDGET (20) if possible
    4. Minimize mid-day gaps (back-to-back is fine, accept proximity penalties)
    """
    proposal_id = str(uuid4())
    changes: List[ScheduleChange] = []
    
    # Separate movable and unmovable events
    # Movable: is_flexible=True AND positive cost (debt-adding)
    # Unmovable: is_flexible=False OR recovery events (negative/zero cost)
    movable = [e for e in events if e.is_flexible is True and (e.calculated_cost or 0) > 0]
    unmovable = [e for e in events if e.is_flexible is not True or (e.calculated_cost or 0) <= 0]
    
    if not movable:
        # Nothing to optimize
        daily_costs = _get_daily_costs(events)
        max_daily = max(daily_costs.values()) if daily_costs else 0
        return WeekOptimizationProposal(
            proposal_id=proposal_id,
            changes=[],
            current_max_daily_debt=max_daily,
            proposed_max_daily_debt=max_daily,
            total_debt_reduction=0,
        )
    
    # Calculate current daily costs
    current_daily = _get_daily_costs(events)
    current_max = max(current_daily.values()) if current_daily else 0
    
    # Get week dates
    week_dates = _get_week_dates(events)
    if not week_dates:
        return WeekOptimizationProposal(
            proposal_id=proposal_id,
            changes=[],
            current_max_daily_debt=current_max,
            proposed_max_daily_debt=current_max,
            total_debt_reduction=0,
        )
    
    # Build schedule per day with unmovable events (these are fixed)
    # We'll use a dict to track placed events per day for slot-finding
    day_schedules: Dict[str, List[Event]] = defaultdict(list)
    for event in unmovable:
        day_key = event.start_time.strftime("%Y-%m-%d")
        day_schedules[day_key].append(event)
    
    # Initialize all week days in the schedule
    for date in week_dates:
        day_key = date.strftime("%Y-%m-%d")
        if day_key not in day_schedules:
            day_schedules[day_key] = []
    
    # Sort movable events by duration (longest first) to place harder events first
    movable_sorted = sorted(movable, key=lambda e: e.duration_minutes, reverse=True)
    
    # Track which day each event gets assigned to and its new time
    event_placements: Dict[str, Tuple[str, datetime]] = {}  # event_id -> (day_key, new_start_time)
    
    for event in movable_sorted:
        duration = event.duration_minutes
        
        # Score each day and find the best one
        # Strategy: pick the day that results in the earliest finish time
        # This packs events early and keeps evenings free
        best_day_key: Optional[str] = None
        best_slot: Optional[datetime] = None
        best_score: Tuple[float, float, float] = (float("inf"), float("inf"), float("inf"))
        
        for date in week_dates:
            day_key = date.strftime("%Y-%m-%d")
            day_events = day_schedules[day_key]
            
            # Score this day (lower = better)
            score, slot = _score_day_for_event(day_events, event, date)
            
            if slot is not None and score < best_score:
                best_score = score
                best_day_key = day_key
                best_slot = slot
        
        if best_day_key is None or best_slot is None:
            # Couldn't find a slot within work hours - try to fit anywhere (up to 19:00)
            for date in week_dates:
                day_key = date.strftime("%Y-%m-%d")
                day_events = day_schedules[day_key]
                
                # Try to find a slot with extended hours (up to 19:00)
                slot = _find_earliest_slot(day_events, duration, date, work_end=19)
                if slot is not None:
                    candidate = _clone_event(
                        event,
                        start_time=slot,
                        end_time=slot + timedelta(minutes=duration),
                    )
                    simulated = [_clone_event(e) for e in day_events] + [candidate]
                    calculate_events_with_proximity(simulated)
                    finish_time = max(e.end_time for e in simulated)
                    finish_score = finish_time.hour + finish_time.minute / 60.0
                    gap_penalty = _calculate_gap_penalty(simulated, date)
                    daily_cost = sum(e.calculated_cost or 0 for e in simulated)
                    overflow = max(0, daily_cost - DAILY_BUDGET)
                    score = (finish_score, float(gap_penalty), float(overflow))

                    if score < best_score:
                        best_score = score
                        best_day_key = day_key
                        best_slot = slot
        
        if best_day_key is not None and best_slot is not None:
            # Place the event
            event_placements[event.id] = (best_day_key, best_slot)
            
            # Create a temporary event object to add to day_schedules
            # so subsequent events see this slot as occupied
            temp_event = Event(
                id=event.id,
                title=event.title,
                description=event.description,
                start_time=best_slot,
                end_time=best_slot + timedelta(minutes=duration),
                duration_minutes=duration,
                participants=event.participants,
                has_agenda=event.has_agenda,
                requires_tool_switch=event.requires_tool_switch,
                event_type=event.event_type,
                is_flexible=event.is_flexible,
            )
            day_schedules[best_day_key].append(temp_event)
    
    # Generate schedule changes
    for event in movable_sorted:
        if event.id not in event_placements:
            continue
        
        new_day_key, new_start = event_placements[event.id]
        original_day_key = event.start_time.strftime("%Y-%m-%d")
        
        # Only add change if day or time is different
        time_changed = (
            original_day_key != new_day_key or
            event.start_time.hour != new_start.hour or
            event.start_time.minute != new_start.minute
        )
        
        if time_changed:
            changes.append(
                ScheduleChange(
                    event_id=event.id,
                    event_title=event.title,
                    change_type="move",
                    original_time=event.start_time,
                    new_time=new_start,
                    applied=False,
                )
            )
    
    # Calculate proposed daily costs
    proposed_costs: Dict[str, int] = defaultdict(int)
    for day_key, day_events in day_schedules.items():
        calculate_events_with_proximity(day_events)
        proposed_costs[day_key] = sum(e.calculated_cost or 0 for e in day_events)
    
    proposed_max = max(proposed_costs.values()) if proposed_costs else 0
    total_reduction = max(0, current_max - proposed_max)
    
    return WeekOptimizationProposal(
        proposal_id=proposal_id,
        changes=changes,
        current_max_daily_debt=current_max,
        proposed_max_daily_debt=proposed_max,
        total_debt_reduction=total_reduction,
    )


def apply_week_optimization(events: List[Event], proposal: WeekOptimizationProposal) -> int:
    """
    Apply the proposed schedule changes to the events.
    Returns the number of changes applied.
    """
    applied_count = 0
    
    for change in proposal.changes:
        if change.applied:
            continue
        
        for event in events:
            if event.id == change.event_id and change.new_time:
                duration = event.end_time - event.start_time
                event.start_time = change.new_time
                event.end_time = change.new_time + duration
                change.applied = True
                applied_count += 1
                break
    
    # Recalculate all costs
    calculate_events_with_proximity(events)
    
    return applied_count
