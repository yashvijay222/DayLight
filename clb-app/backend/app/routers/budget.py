from collections import defaultdict
from datetime import datetime

from fastapi import APIRouter, Request

from app.models import BudgetStatus
from app.services.cognitive_calculator import (
    DAILY_BUDGET,
    calculate_events_with_proximity,
    detect_overdraft,
)

router = APIRouter()


@router.get("/budget/daily", response_model=BudgetStatus)
def get_daily_budget(request: Request) -> BudgetStatus:
    events = request.app.state.events
    
    # Recalculate all costs with proximity awareness
    calculate_events_with_proximity(events)
    
    today = datetime.utcnow().date()
    today_str = today.strftime("%Y-%m-%d")
    
    # Calculate daily total: use actual_cost if present, else calculated_cost
    daily_events = [e for e in events if e.start_time.date() == today]
    events_total = sum((e.actual_cost if e.actual_cost is not None else e.calculated_cost) or 0 for e in daily_events)
    
    # Add standalone session costs for today
    session_costs = sum(c["amount"] for c in request.app.state.daily_session_costs if c["date"] == today_str)
    
    total = events_total + session_costs
    
    is_overdrafted, overdraft_amount, remaining = detect_overdraft(total, DAILY_BUDGET)
    
    # Weekly total also needs updated logic
    weekly_events_total = sum((e.actual_cost if e.actual_cost is not None else e.calculated_cost) or 0 for e in events)
    weekly_sessions_total = sum(c["amount"] for c in request.app.state.daily_session_costs)
    
    weekly_total = weekly_events_total + weekly_sessions_total
    weekly_debt = weekly_total - (DAILY_BUDGET * 7)
    
    return BudgetStatus(
        daily_budget=DAILY_BUDGET,
        spent=total,
        remaining=remaining,
        is_overdrafted=is_overdrafted,
        overdraft_amount=overdraft_amount,
        weekly_total=weekly_total,
        weekly_debt=weekly_debt,
    )


@router.get("/budget/weekly")
def get_weekly_budget(request: Request) -> dict:
    events = request.app.state.events
    
    # Recalculate all costs with proximity awareness
    calculate_events_with_proximity(events)
    
    totals = defaultdict(float)
    for event in events:
        day_key = event.start_time.strftime("%Y-%m-%d")
        cost = (event.actual_cost if event.actual_cost is not None else event.calculated_cost) or 0
        totals[day_key] += cost
        
    for session in request.app.state.daily_session_costs:
        totals[session["date"]] += session["amount"]
        
    weekly_total = sum(totals.values())
    return {"daily_totals": dict(totals), "weekly_total": weekly_total}
