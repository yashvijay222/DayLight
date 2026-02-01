from datetime import datetime, timezone, timedelta
from math import ceil
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, HTTPException, Request

from app.models import CostBreakdown, Event, EventCreate, EventEnrich, EventUpdate, FlexibilityClassification
from app.services.cognitive_calculator import (
    calculate_cost_breakdown,
    calculate_event_cost,
    calculate_events_with_proximity,
)

router = APIRouter()

# EST timezone (UTC-5)
EST = timezone(timedelta(hours=-5))


def _now_est() -> datetime:
    """Get current time in EST as naive datetime."""
    return datetime.now(EST).replace(tzinfo=None)


def _recalculate_all_costs(events: List[Event]) -> None:
    """Recalculate costs for all events with proximity awareness."""
    for event in events:
        event.start_time = _normalize_datetime(event.start_time)
        event.end_time = _normalize_datetime(event.end_time)
    calculate_events_with_proximity(events)


def _normalize_datetime(value: datetime) -> datetime:
    """Normalize datetimes to naive EST for consistent comparisons."""
    if value.tzinfo is None:
        return value
    return value.astimezone(EST).replace(tzinfo=None)


def _calculate_prorated_cost(event: Event, completed_at: datetime) -> int:
    """
    Calculate prorated cost based on actual time spent.
    
    Divides the event into intervals based on total points, then calculates
    how many intervals were actually used (rounded up).
    
    Example: 60-min meeting worth 4 points = 15-min intervals
    If completed at 20 min: ceil(20/15) = 2 intervals = 2 points
    """
    total_cost = event.calculated_cost or 0
    if total_cost <= 0:
        return 0
    
    # Calculate total scheduled duration in minutes
    total_duration = (event.end_time - event.start_time).total_seconds() / 60
    if total_duration <= 0:
        return total_cost
    
    # Calculate actual time spent in minutes
    actual_time = (completed_at - event.start_time).total_seconds() / 60
    if actual_time <= 0:
        return 0  # Completed before it even started
    if actual_time >= total_duration:
        return total_cost  # Completed at or after scheduled end
    
    # Calculate interval duration (divide total time by total points)
    interval_duration = total_duration / total_cost
    
    # Calculate intervals used (round up)
    intervals_used = ceil(actual_time / interval_duration)
    
    # Return prorated cost (capped at total cost)
    return min(intervals_used, total_cost)


@router.get("/events", response_model=List[Event])
def get_events(request: Request) -> List[Event]:
    events = request.app.state.events
    _recalculate_all_costs(events)
    # Sort by start_time for consistent ordering
    events.sort(key=lambda e: e.start_time)
    return events


@router.post("/events", response_model=Event)
def add_event(request: Request, payload: EventCreate) -> Event:
    event = Event(
        id=str(uuid4()),
        title=payload.title,
        description=payload.description,
        start_time=_normalize_datetime(payload.start_time),
        end_time=_normalize_datetime(payload.end_time),
        duration_minutes=payload.duration_minutes,
        participants=payload.participants,
        has_agenda=payload.has_agenda,
        event_type=payload.event_type,
    )
    request.app.state.events.append(event)
    # Recalculate all costs with new event
    _recalculate_all_costs(request.app.state.events)
    return event


@router.get("/events/{event_id}")
def get_event(request: Request, event_id: str) -> dict:
    _recalculate_all_costs(request.app.state.events)
    for event in request.app.state.events:
        if event.id == event_id:
            return {"status": "ok", "event": event}
    return {"status": "not_found"}


@router.delete("/events/{event_id}")
def delete_event(request: Request, event_id: str) -> dict:
    original_count = len(request.app.state.events)
    request.app.state.events = [e for e in request.app.state.events if e.id != event_id]
    if len(request.app.state.events) < original_count:
        # Clear cached suggestions since events changed
        request.app.state.last_suggestions = None
        request.app.state.last_week_proposal = None
        _recalculate_all_costs(request.app.state.events)
        return {"status": "deleted", "event_id": event_id}
    return {"status": "not_found"}


@router.patch("/events/{event_id}")
def update_event(request: Request, event_id: str, payload: EventUpdate) -> dict:
    """Update event details including marking as complete."""
    events = request.app.state.events
    for event in events:
        if event.id == event_id:
            if payload.title is not None:
                event.title = payload.title
            if payload.description is not None:
                event.description = payload.description
            if payload.start_time is not None:
                event.start_time = _normalize_datetime(payload.start_time)
            if payload.end_time is not None:
                event.end_time = _normalize_datetime(payload.end_time)
            if payload.duration_minutes is not None:
                event.duration_minutes = payload.duration_minutes
            if payload.participants is not None:
                event.participants = payload.participants
            if payload.has_agenda is not None:
                event.has_agenda = payload.has_agenda
            if payload.event_type is not None:
                event.event_type = payload.event_type
            if payload.is_completed is not None:
                event.is_completed = payload.is_completed
                
                # Calculate prorated cost when marking complete
                if payload.is_completed:
                    now = _now_est()
                    event.completed_at = now
                    
                    # Make sure we have the latest calculated_cost
                    _recalculate_all_costs(events)
                    
                    # Calculate prorated cost based on actual time spent
                    event.prorated_cost = _calculate_prorated_cost(event, now)
                else:
                    # Unchecking - clear completion data
                    event.completed_at = None
                    event.prorated_cost = None
            
            # Clear cached suggestions since event changed
            request.app.state.last_suggestions = None
            request.app.state.last_week_proposal = None
            _recalculate_all_costs(events)
            return {"status": "updated", "event": event}
    return {"status": "not_found"}


@router.get("/events/analyze")
def analyze_events(request: Request) -> dict:
    events = request.app.state.events
    _recalculate_all_costs(events)
    total_cost = sum(e.calculated_cost or 0 for e in events)
    return {
        "total_cost": total_cost,
        "event_count": len(events),
        "events": events,
    }


@router.patch("/events/{event_id}/flexibility")
def update_flexibility(request: Request, event_id: str, payload: FlexibilityClassification) -> dict:
    """Update event flexibility: True = movable, False = unmovable."""
    events = request.app.state.events
    for event in events:
        if event.id == event_id:
            event.is_flexible = payload.is_flexible
            # Clear cached optimization since flexibility changed
            request.app.state.last_suggestions = None
            request.app.state.last_week_proposal = None
            return {"status": "updated", "event": event}
    return {"status": "not_found"}


@router.patch("/events/{event_id}/enrich")
def enrich_event(request: Request, event_id: str, payload: EventEnrich) -> dict:
    """
    Enrich meeting-specific fields (participants, has_agenda).
    Only applies to meeting or admin event types.
    """
    events = request.app.state.events
    for event in events:
        if event.id == event_id:
            # Only allow enriching meeting/admin events
            if event.event_type not in ("meeting", "admin", None):
                return {
                    "status": "error",
                    "message": f"Cannot enrich {event.event_type} events. Only meeting/admin events need enrichment."
                }
            
            if payload.participants is not None:
                event.participants = payload.participants
            if payload.has_agenda is not None:
                event.has_agenda = payload.has_agenda
            
            # Recalculate costs after enrichment
            _recalculate_all_costs(events)
            return {"status": "updated", "event": event}
    return {"status": "not_found"}


@router.get("/events/{event_id}/cost-breakdown", response_model=CostBreakdown)
def get_cost_breakdown(request: Request, event_id: str) -> CostBreakdown:
    """Get a detailed breakdown of how an event's cost is calculated."""
    events = request.app.state.events
    sorted_events = sorted(events, key=lambda e: e.start_time)
    
    previous_end: Optional[datetime] = None
    for event in sorted_events:
        if event.id == event_id:
            breakdown = calculate_cost_breakdown(event, previous_end)
            return breakdown
        # Track previous end for proximity calculation regardless of cost type
        previous_end = event.end_time
    
    raise HTTPException(status_code=404, detail="Event not found")
