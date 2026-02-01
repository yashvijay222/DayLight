from datetime import datetime, timedelta
from typing import List

from fastapi import APIRouter, Request

from app.models import Event
from app.services.google_calendar import (
    create_event,
    fetch_events,
    get_auth_url,
    handle_callback,
    update_event,
    use_mock_data,
)
from app.services.cognitive_calculator import calculate_events_with_proximity
from app.services.event_classifier import classify_event

router = APIRouter()


def _classify_and_prepare_events(events_list: List[Event]) -> List[Event]:
    """Classify events using AI and calculate initial costs."""
    for event in events_list:
        if event.event_type is None:
            # Classify using AI (or fallback heuristics)
            event.event_type = classify_event(
                title=event.title,
                duration_minutes=event.duration_minutes,
                description=event.description,
            )
            
            # For non-meeting types, set default values for meeting-specific fields
            if event.event_type in ("recovery", "deep_work"):
                if event.participants is None:
                    event.participants = 1
                if event.has_agenda is None:
                    event.has_agenda = True
                if event.requires_tool_switch is None:
                    event.requires_tool_switch = False
    
    # Calculate costs with proximity awareness
    calculate_events_with_proximity(events_list)
    return events_list


@router.get("/calendar/auth-url")
def auth_url() -> dict:
    return {"auth_url": get_auth_url(), "mock": use_mock_data()}


@router.post("/calendar/callback")
def calendar_callback(request: Request, payload: dict) -> dict:
    code = payload.get("code", "demo")
    token_data = handle_callback(code)
    request.app.state.oauth_tokens["google"] = token_data
    return {"status": "ok", "token": token_data}


@router.post("/calendar/sync", response_model=List[Event])
def sync_calendar(request: Request) -> List[Event]:
    """
    Sync events from Google Calendar.
    Events are classified by AI and costs are calculated with proximity awareness.
    Meeting events will need user enrichment (participants, has_agenda).
    """
    token = request.app.state.oauth_tokens.get("google", {}).get("access_token")
    start = datetime.utcnow()
    end = start + timedelta(days=7)
    
    # Fetch raw events
    events = fetch_events(token, start, end)
    
    # Clear meeting-specific fields so they need to be enriched
    for event in events:
        event.participants = None
        event.has_agenda = None
        event.requires_tool_switch = None
        event.event_type = None
        event.is_flexible = None
    
    # Classify and prepare events
    events = _classify_and_prepare_events(events)
    
    # Clear cached optimization data
    request.app.state.last_suggestions = None
    request.app.state.last_week_proposal = None
    
    request.app.state.events = events
    return events


@router.post("/calendar/push")
def push_calendar(request: Request) -> dict:
    token = request.app.state.oauth_tokens.get("google", {}).get("access_token")
    updates = []
    for event in request.app.state.events:
        if event.google_id:
            updates.append(update_event(token, event.google_id, event.model_dump()))
        else:
            updates.append(create_event(token, event))
    return {"status": "ok", "updates": updates}
