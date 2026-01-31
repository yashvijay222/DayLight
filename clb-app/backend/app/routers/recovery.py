from uuid import uuid4

from fastapi import APIRouter, Request

from app.models import Event, EventCreate
from app.services.cognitive_calculator import (
    DAILY_BUDGET,
    calculate_events_with_proximity,
    suggest_recovery_activities,
)
from app.services.schedule_optimizer import find_available_recovery_slots

router = APIRouter()


@router.get("/recovery/suggestions")
def get_recovery_suggestions(request: Request) -> dict:
    events = request.app.state.events
    
    # Recalculate all costs with proximity awareness
    calculate_events_with_proximity(events)
    
    total = sum(e.calculated_cost or 0 for e in events)
    weekly_debt = total - (DAILY_BUDGET * 7)
    activities = suggest_recovery_activities(weekly_debt)
    for activity in activities:
        activity.suggested_slots = find_available_recovery_slots(
            events, activity.duration_minutes
        )
    return {"weekly_debt": weekly_debt, "activities": activities}


@router.post("/recovery/schedule")
def schedule_recovery(request: Request, payload: dict) -> dict:
    if "activity" in payload and "slot" in payload:
        activity = payload.get("activity", {})
        slot = payload.get("slot", {})
        event_payload = {
            "title": activity.get("name", "Recovery Activity"),
            "start_time": slot.get("start_time"),
            "end_time": slot.get("end_time"),
            "duration_minutes": activity.get("duration_minutes", 30),
            "participants": 1,
            "has_agenda": True,
            "requires_tool_switch": False,
            "event_type": "recovery",
        }
    else:
        event_payload = payload

    data = EventCreate.model_validate(event_payload)
    event = Event(
        id=str(uuid4()),
        title=data.title,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
        participants=data.participants if data.participants is not None else 1,
        has_agenda=data.has_agenda if data.has_agenda is not None else True,
        requires_tool_switch=data.requires_tool_switch if data.requires_tool_switch is not None else False,
        event_type=data.event_type if data.event_type else "recovery",
    )
    request.app.state.events.append(event)
    
    # Recalculate all costs with proximity awareness
    calculate_events_with_proximity(request.app.state.events)
    
    return {"status": "scheduled", "event": event}
