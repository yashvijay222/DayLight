from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Request

from app.models import OptimizationSuggestion
from app.services.cognitive_calculator import DAILY_BUDGET, calculate_event_cost
from app.services.schedule_optimizer import generate_suggestions

router = APIRouter()


def _get_suggestions(request: Request):
    """Helper to get or generate suggestions."""
    suggestions = getattr(request.app.state, "last_suggestions", None)
    if not suggestions:
        total = sum(calculate_event_cost(e) for e in request.app.state.events)
        weekly_debt = total - (DAILY_BUDGET * 7)
        suggestions = generate_suggestions(request.app.state.events, weekly_debt)
        request.app.state.last_suggestions = suggestions
    return suggestions


def _apply_single_suggestion(request: Request, suggestion: OptimizationSuggestion) -> bool:
    """Apply a single suggestion. Returns True if applied."""
    for event in request.app.state.events:
        if event.id == suggestion.event_id:
            if suggestion.suggestion_type == "cancel":
                request.app.state.events = [
                    e for e in request.app.state.events if e.id != event.id
                ]
                return True
            elif suggestion.suggestion_type == "postpone" and suggestion.new_time:
                delta = event.end_time - event.start_time
                event.start_time = suggestion.new_time
                event.end_time = suggestion.new_time + delta
                event.calculated_cost = calculate_event_cost(event)
                return True
            elif suggestion.suggestion_type == "shorten":
                original_minutes = event.duration_minutes
                new_minutes = max(15, round(original_minutes * 0.8))
                event.duration_minutes = new_minutes
                event.end_time = event.start_time + timedelta(minutes=new_minutes)
                event.calculated_cost = calculate_event_cost(event)
                return True
    return False


@router.get("/optimize/suggestions")
def get_suggestions(request: Request) -> dict:
    events = request.app.state.events
    total = sum(calculate_event_cost(e) for e in events)
    weekly_debt = total - (DAILY_BUDGET * 7)
    suggestions = generate_suggestions(events, weekly_debt)
    request.app.state.last_suggestions = suggestions
    return {"weekly_debt": weekly_debt, "suggestions": suggestions}


@router.post("/optimize/apply")
def apply_suggestion_endpoint(request: Request, payload: dict) -> dict:
    suggestion_id = payload.get("suggestion_id")
    suggestions = _get_suggestions(request)
    
    for suggestion in suggestions:
        if suggestion.suggestion_id == suggestion_id:
            if _apply_single_suggestion(request, suggestion):
                # Clear cached suggestions since events changed
                request.app.state.last_suggestions = None
                return {"status": "applied", "suggestion": suggestion}
    return {"status": "not_found"}


@router.post("/optimize/apply-all")
def apply_all_suggestions(request: Request, payload: dict) -> dict:
    suggestion_ids = payload.get("ids", [])
    if not suggestion_ids:
        return {"status": "no_ids"}

    suggestions = _get_suggestions(request)
    applied = []
    
    for suggestion in suggestions:
        if suggestion.suggestion_id in suggestion_ids:
            if _apply_single_suggestion(request, suggestion):
                applied.append(suggestion.suggestion_id)

    # Clear cached suggestions since events changed
    if applied:
        request.app.state.last_suggestions = None
    
    return {"status": "ok", "applied": applied, "count": len(applied)}
