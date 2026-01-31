from datetime import datetime
from typing import List
from uuid import uuid4

from fastapi import APIRouter, Request

from app.models import Event, EventCreate, FlexibilityClassification
from app.services.cognitive_calculator import calculate_event_cost

router = APIRouter()


@router.get("/events", response_model=List[Event])
def get_events(request: Request) -> List[Event]:
    events = request.app.state.events
    for event in events:
        event.calculated_cost = calculate_event_cost(event)
    # Sort by start_time for consistent ordering
    events.sort(key=lambda e: e.start_time)
    return events


@router.post("/events", response_model=Event)
def add_event(request: Request, payload: EventCreate) -> Event:
    event = Event(
        id=str(uuid4()),
        title=payload.title,
        start_time=payload.start_time,
        end_time=payload.end_time,
        duration_minutes=payload.duration_minutes,
        participants=payload.participants,
        has_agenda=payload.has_agenda,
        requires_tool_switch=payload.requires_tool_switch,
        event_type=payload.event_type,
    )
    event.calculated_cost = calculate_event_cost(event)
    request.app.state.events.append(event)
    return event


@router.get("/events/{event_id}")
def get_event(request: Request, event_id: str) -> dict:
    for event in request.app.state.events:
        if event.id == event_id:
            event.calculated_cost = calculate_event_cost(event)
            return {"status": "ok", "event": event}
    return {"status": "not_found"}


@router.delete("/events/{event_id}")
def delete_event(request: Request, event_id: str) -> dict:
    original_count = len(request.app.state.events)
    request.app.state.events = [e for e in request.app.state.events if e.id != event_id]
    if len(request.app.state.events) < original_count:
        # Clear cached suggestions since events changed
        request.app.state.last_suggestions = None
        return {"status": "deleted", "event_id": event_id}
    return {"status": "not_found"}


@router.get("/events/analyze")
def analyze_events(request: Request) -> dict:
    events = request.app.state.events
    for event in events:
        event.calculated_cost = calculate_event_cost(event)

    total_cost = sum(e.calculated_cost or 0 for e in events)
    return {
        "total_cost": total_cost,
        "event_count": len(events),
        "events": events,
    }


@router.patch("/events/{event_id}/flexibility")
def update_flexibility(request: Request, event_id: str, payload: FlexibilityClassification) -> dict:
    events = request.app.state.events
    for event in events:
        if event.id == event_id:
            event.is_flexible = payload.is_flexible
            event.flexibility_reason = payload.reason
            return {"status": "updated", "event": event}
    return {"status": "not_found"}
