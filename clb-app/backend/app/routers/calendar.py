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
from app.services.cognitive_calculator import calculate_event_cost

router = APIRouter()


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
    token = request.app.state.oauth_tokens.get("google", {}).get("access_token")
    start = datetime.utcnow()
    end = start + timedelta(days=7)
    events = fetch_events(token, start, end)
    for event in events:
        event.calculated_cost = calculate_event_cost(event)
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
