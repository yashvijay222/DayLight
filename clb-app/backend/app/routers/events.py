from datetime import datetime
from typing import List, Optional
from uuid import uuid4

from fastapi import APIRouter, Request

from app.models import CostBreakdown, Event, EventCreate, EventEnrich, FlexibilityClassification
from app.services.cognitive_calculator import (
    calculate_cost_breakdown,
    calculate_event_cost,
    calculate_events_with_proximity,
)

router = APIRouter()


def _recalculate_all_costs(events: List[Event]) -> None:
    """Recalculate costs for all events with proximity awareness."""
    calculate_events_with_proximity(events)


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
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        participants=payload.participants,
        has_agenda=payload.has_agenda,
        requires_tool_switch=payload.requires_tool_switch,
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
    Enrich meeting-specific fields (participants, has_agenda, requires_tool_switch).
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
            if payload.requires_tool_switch is not None:
                event.requires_tool_switch = payload.requires_tool_switch
            
            # Recalculate costs after enrichment
            _recalculate_all_costs(events)
            return {"status": "updated", "event": event}
    return {"status": "not_found"}


@router.get("/events/{event_id}/cost-breakdown", response_model=CostBreakdown)
def get_cost_breakdown(request: Request, event_id: str) -> dict:
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
    
    return {"status": "not_found"}
