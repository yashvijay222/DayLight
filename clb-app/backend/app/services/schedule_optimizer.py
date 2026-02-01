from collections import defaultdict
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from uuid import uuid4

from app.models import Event, OptimizationSuggestion, ScheduleChange, TimeSlot, WeekOptimizationProposal
from app.services.cognitive_calculator import (
    DAILY_BUDGET,
    PROXIMITY_THRESHOLD_MINUTES,
    calculate_event_base_cost,
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


def find_available_recovery_slots(
    events: List[Event], 
    duration_minutes: int,
    prioritize_overloaded: bool = True,
) -> List[TimeSlot]:
    """
    Find gaps where recovery activities could be scheduled.
    
    Looks for:
    1. Gaps between events during the day
    2. Slots at the end of the day (after last event, before 19:00)
    3. Prioritizes days that are over budget (if prioritize_overloaded=True)
    """
    if not events:
        return []

    # Group events by day and calculate daily costs
    day_events: Dict[str, List[Event]] = defaultdict(list)
    for event in events:
        day_key = event.start_time.strftime("%Y-%m-%d")
        day_events[day_key].append(event)
    
    # Calculate daily costs
    daily_costs: Dict[str, int] = {}
    for day_key, day_evts in day_events.items():
        calculate_events_with_proximity(day_evts)
        daily_costs[day_key] = sum(e.calculated_cost or 0 for e in day_evts)
    
    slots: List[TimeSlot] = []
    
    for day_key, day_evts in day_events.items():
        sorted_day = sorted(day_evts, key=lambda e: e.start_time)
        day_date = sorted_day[0].start_time.date()
        day_cost = daily_costs.get(day_key, 0)
        is_overloaded = day_cost > DAILY_BUDGET
        
        # Find gaps between events
        for i in range(len(sorted_day) - 1):
            current_end = sorted_day[i].end_time
            next_start = sorted_day[i + 1].start_time
            gap = (next_start - current_end).total_seconds() / 60
            if gap >= duration_minutes:
                slots.append(
                    TimeSlot(
                        start_time=current_end,
                        end_time=current_end + timedelta(minutes=duration_minutes),
                        day=current_end.strftime("%A"),
                        available=True,
                        priority="high" if is_overloaded else "normal",
                    )
                )
        
        # Find slot at end of day (after last event, before 19:00)
        last_end = max(e.end_time for e in sorted_day)
        end_of_day = datetime.combine(day_date, datetime.min.time().replace(hour=19))
        remaining = (end_of_day - last_end).total_seconds() / 60
        if remaining >= duration_minutes:
            slots.append(
                TimeSlot(
                    start_time=last_end,
                    end_time=last_end + timedelta(minutes=duration_minutes),
                    day=last_end.strftime("%A"),
                    available=True,
                    priority="high" if is_overloaded else "normal",
                )
            )
    
    # Sort: prioritize overloaded days first, then by time
    if prioritize_overloaded:
        slots.sort(key=lambda s: (0 if s.priority == "high" else 1, s.start_time))
    else:
        slots.sort(key=lambda s: s.start_time)
    
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
    prefer_gap: bool = True,
) -> Optional[datetime]:
    """
    Find the earliest non-overlapping slot on a given day.
    
    Args:
        day_events: Events already scheduled on this day
        duration_minutes: Duration of the event to place
        day_date: The date to schedule on
        work_start: Start of work day (hour)
        work_end: End of work day (hour)
        prefer_gap: If True, prefer slots with 1-hour gap from previous event
    
    Returns:
        The earliest available start time, or None if no slot fits
    """
    sorted_events = sorted(day_events, key=lambda e: e.start_time)
    end_of_day = day_date.replace(hour=work_end, minute=0, second=0, microsecond=0)
    
    # Required gap to avoid proximity penalty (1 hour + 1 minute buffer)
    preferred_gap = PROXIMITY_THRESHOLD_MINUTES + 1 if prefer_gap else 0
    
    # PASS 1: Try to find a slot with preferred gap (1 hour after previous event)
    if prefer_gap and sorted_events:
        cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
        
        for i, event in enumerate(sorted_events):
            # Calculate when we can start (with gap from previous event)
            if i > 0:
                # Need 1-hour gap from previous event's end
                earliest_with_gap = sorted_events[i-1].end_time + timedelta(minutes=preferred_gap)
                cursor = max(cursor, earliest_with_gap)
            
            # Check if there's room before this event (with gap before it too)
            latest_start = event.start_time - timedelta(minutes=preferred_gap + duration_minutes)
            
            if cursor <= latest_start:
                # Found a slot with proper gaps on both sides
                return cursor
            
            # Move cursor to after this event (with gap)
            cursor = event.end_time + timedelta(minutes=preferred_gap)
        
        # Check slot after all events (with gap from last event)
        if sorted_events:
            cursor = sorted_events[-1].end_time + timedelta(minutes=preferred_gap)
        else:
            cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
        
        remaining = (end_of_day - cursor).total_seconds() / 60
        if remaining >= duration_minutes:
            return cursor
    
    # PASS 2: Fall back to tight packing (no gap requirement)
    cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
    
    for event in sorted_events:
        gap_before = (event.start_time - cursor).total_seconds() / 60
        
        if gap_before >= duration_minutes:
            return cursor
        
        cursor = max(cursor, event.end_time)
    
    remaining = (end_of_day - cursor).total_seconds() / 60
    if remaining >= duration_minutes:
        return cursor
    
    return None  # No slot found


def _score_day_for_event(
    day_events: List[Event],
    event: Event,
    day_date: datetime,
) -> Tuple[Tuple[int, float, float, str], Optional[datetime]]:
    """
    Score a day for placing an event. Lower score = better.
    
    Priority (in order):
    1) NEVER exceed DAILY_BUDGET (20) - days that would exceed get score (1, ...)
       Days that stay under budget get score (0, ...)
    2) BALANCE loads - prefer days with lower current cost (spread events evenly)
    3) PACK EARLY - among equal loads, prefer earlier finish time
    4) DAY ORDER - tiebreaker: prefer earlier days in the week (deterministic)
    
    Returns: ((exceeds_budget_flag, daily_cost, finish_score, day_key), slot)
    """
    slot = _find_earliest_slot(day_events, event.duration_minutes, day_date)
    day_key = day_date.strftime("%Y-%m-%d")
    
    if slot is None:
        return (2, float("inf"), float("inf"), day_key), None  # No slot available

    candidate = _clone_event(
        event,
        start_time=slot,
        end_time=slot + timedelta(minutes=event.duration_minutes),
    )
    simulated = [_clone_event(e) for e in day_events] + [candidate]
    calculate_events_with_proximity(simulated)

    daily_cost = sum(e.calculated_cost or 0 for e in simulated)
    
    # Primary: Does this day exceed budget?
    # 0 = under/at budget (preferred), 1 = over budget
    exceeds_budget = 1 if daily_cost > DAILY_BUDGET else 0
    
    # Secondary: Current daily cost (lower = more capacity = preferred)
    # This ensures we balance across days
    
    # Tertiary: Finish time (earlier = better, pack events early)
    finish_time = max(e.end_time for e in simulated)
    finish_score = finish_time.hour + finish_time.minute / 60.0
    
    # Quaternary: Day key for deterministic tiebreaking (earlier day wins)

    return (exceeds_budget, float(daily_cost), finish_score, day_key), slot


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


def optimize_week(events: List[Event]) -> WeekOptimizationProposal:
    """
    Generate a proposal to redistribute movable events across the week.
    
    Goals (in order of priority):
    1. NEVER exceed DAILY_BUDGET (20) per day if possible
    2. BALANCE loads across days (spread events evenly)
    3. Pack events early in the day (finish ASAP, free evenings)
    4. Avoid time overlaps (proper slot-finding)
    """
    proposal_id = str(uuid4())
    changes: List[ScheduleChange] = []
    
    # Separate movable and unmovable events
    # Movable: is_flexible=True AND positive base cost (debt-adding)
    # Unmovable: is_flexible=False OR recovery events (negative/zero base cost)
    movable = [e for e in events if e.is_flexible is True and calculate_event_base_cost(e) > 0]
    unmovable = [e for e in events if e.is_flexible is not True or calculate_event_base_cost(e) <= 0]
    
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
    
    # Sort movable events by BASE cost (highest first), then by ID for stable ordering
    # Using base cost (not calculated_cost) ensures deterministic results regardless of position
    # because base cost doesn't change with proximity - same input always produces same output
    movable_sorted = sorted(
        movable, 
        key=lambda e: (-calculate_event_base_cost(e), e.id)  # negative for descending, ID for tiebreaker
    )
    
    # Track which day each event gets assigned to and its new time
    event_placements: Dict[str, Tuple[str, datetime]] = {}  # event_id -> (day_key, new_start_time)
    
    for event in movable_sorted:
        duration = event.duration_minutes
        
        # Score each day and find the best one
        # Strategy: pick day under budget with lowest load, then pack early
        best_day_key: Optional[str] = None
        best_slot: Optional[datetime] = None
        # Score tuple: (exceeds_budget, daily_cost, finish_score, day_key) - lower is better
        best_score: Tuple[int, float, float, str] = (2, float("inf"), float("inf"), "9999-99-99")
        
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
            # Couldn't find a slot within work hours - try extended hours (up to 19:00)
            # Still prefer 1-hour gaps first
            for date in week_dates:
                day_key = date.strftime("%Y-%m-%d")
                day_events = day_schedules[day_key]
                
                # Try extended hours with gap preference (internal fallback to tight packing)
                slot = _find_earliest_slot(day_events, duration, date, work_end=19, prefer_gap=True)
                if slot is not None:
                    candidate = _clone_event(
                        event,
                        start_time=slot,
                        end_time=slot + timedelta(minutes=duration),
                    )
                    simulated = [_clone_event(e) for e in day_events] + [candidate]
                    calculate_events_with_proximity(simulated)
                    
                    daily_cost = sum(e.calculated_cost or 0 for e in simulated)
                    exceeds_budget = 1 if daily_cost > DAILY_BUDGET else 0
                    finish_time = max(e.end_time for e in simulated)
                    finish_score = finish_time.hour + finish_time.minute / 60.0
                    score = (exceeds_budget, float(daily_cost), finish_score, day_key)

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


def apply_week_optimization(
    events: List[Event], 
    proposal: WeekOptimizationProposal,
    selected_event_ids: Optional[List[str]] = None
) -> int:
    """
    Apply the proposed schedule changes to the events.
    If selected_event_ids is provided, only apply changes for those events.
    Returns the number of changes applied.
    """
    applied_count = 0
    
    for change in proposal.changes:
        if change.applied:
            continue
        
        # Skip if we have a selection and this event is not selected
        if selected_event_ids is not None and change.event_id not in selected_event_ids:
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
