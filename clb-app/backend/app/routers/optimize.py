from datetime import timedelta
from typing import Optional

from fastapi import APIRouter, Request

from app.models import OptimizationSuggestion, WeekOptimizationProposal
from app.services.cognitive_calculator import (
    DAILY_BUDGET,
    calculate_events_with_proximity,
)
from app.services.schedule_optimizer import (
    apply_week_optimization,
    generate_suggestions,
    optimize_week,
)

router = APIRouter()


def _recalculate_costs(request: Request):
    """Recalculate all event costs with proximity awareness."""
    calculate_events_with_proximity(request.app.state.events)


def _get_weekly_debt(request: Request) -> int:
    """Calculate weekly debt with proximity-aware costs."""
    _recalculate_costs(request)
    total = sum(e.calculated_cost or 0 for e in request.app.state.events)
    return total - (DAILY_BUDGET * 7)


def _get_suggestions(request: Request):
    """Helper to get or generate suggestions."""
    suggestions = getattr(request.app.state, "last_suggestions", None)
    if not suggestions:
        weekly_debt = _get_weekly_debt(request)
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
                _recalculate_costs(request)
                return True
            elif suggestion.suggestion_type == "postpone" and suggestion.new_time:
                delta = event.end_time - event.start_time
                event.start_time = suggestion.new_time
                event.end_time = suggestion.new_time + delta
                _recalculate_costs(request)
                return True
            elif suggestion.suggestion_type == "shorten":
                original_minutes = event.duration_minutes
                new_minutes = max(15, round(original_minutes * 0.8))
                event.duration_minutes = new_minutes
                event.end_time = event.start_time + timedelta(minutes=new_minutes)
                _recalculate_costs(request)
                return True
    return False


@router.get("/optimize/suggestions")
def get_suggestions_endpoint(request: Request) -> dict:
    weekly_debt = _get_weekly_debt(request)
    suggestions = generate_suggestions(request.app.state.events, weekly_debt)
    request.app.state.last_suggestions = suggestions
    return {"weekly_debt": weekly_debt, "suggestions": suggestions}


@router.post("/optimize/apply")
def apply_suggestion_endpoint(request: Request, payload: dict) -> dict:
    suggestion_id = payload.get("suggestion_id")
    suggestions = _get_suggestions(request)
    
    for suggestion in suggestions:
        if suggestion.suggestion_id == suggestion_id:
            if _apply_single_suggestion(request, suggestion):
                # Clear cached data since events changed
                request.app.state.last_suggestions = None
                request.app.state.last_week_proposal = None
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

    # Clear cached data since events changed
    if applied:
        request.app.state.last_suggestions = None
        request.app.state.last_week_proposal = None
    
    return {"status": "ok", "applied": applied, "count": len(applied)}


@router.get("/optimize/week")
def get_week_optimization(request: Request) -> dict:
    """
    Generate a proposal to optimize the week's schedule.
    Redistributes movable events to keep daily debt ≤ 20 and maximize gaps.
    """
    _recalculate_costs(request)
    events = request.app.state.events
    
    # Check if all events have flexibility set
    all_classified = all(e.is_flexible is not None for e in events)
    
    proposal = optimize_week(events)
    request.app.state.last_week_proposal = proposal
    
    return {
        "all_classified": all_classified,
        "proposal": proposal,
        "daily_budget": DAILY_BUDGET,
    }


@router.post("/optimize/week/apply")
def apply_week_optimization_endpoint(request: Request) -> dict:
    """Apply the last generated week optimization proposal."""
    proposal = getattr(request.app.state, "last_week_proposal", None)
    
    if not proposal:
        return {"status": "error", "message": "No optimization proposal found. Generate one first."}
    
    applied_count = apply_week_optimization(request.app.state.events, proposal)
    
    # Clear cached data
    request.app.state.last_suggestions = None
    request.app.state.last_week_proposal = None
    
    return {
        "status": "applied",
        "changes_applied": applied_count,
    }
