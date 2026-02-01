from datetime import datetime, timedelta

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
    
    # Recalculate all costs with proximity awareness (from main)
    calculate_events_with_proximity(events)
    
    now = datetime.utcnow()
    today = now.date()
    today_str = today.strftime("%Y-%m-%d")
    
    # Identify daily events
    daily_events = [e for e in events if e.start_time.date() == today]
    
    # Only count points for events that have already ended 
    # OR those that have an actual_cost from a completed Sage session
    completed_today = [e for e in daily_events if now >= e.end_time or e.actual_cost is not None]
    
    # Sum using actual_cost preference
    events_total = sum((e.actual_cost if e.actual_cost is not None else e.calculated_cost) or 0 for e in completed_today)
    
    # Add standalone session costs for today
    session_costs = sum(c["amount"] for c in request.app.state.daily_session_costs if c["date"] == today_str)
    
    total = int(events_total + session_costs)
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
    
    # Recalculate all costs with proximity awareness (from main)
    calculate_events_with_proximity(events)
    
    today = datetime.utcnow().date()
    
    # Determine the start of the week (Sunday) for the heatmap
    if events:
        first_date = min(e.start_time.date() for e in events)
        days_since_sunday = (first_date.weekday() + 1) % 7
        week_start = first_date - timedelta(days=days_since_sunday)
    else:
        days_since_sunday = (today.weekday() + 1) % 7
        week_start = today - timedelta(days=days_since_sunday)
        
    # Initialize all 7 days of the week for the heatmap
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    totals = {d.strftime("%Y-%m-%d"): 0 for d in week_dates}
    
    # Add event costs (preferring actual_cost from Sage Mode)
    for event in events:
        day_key = event.start_time.strftime("%Y-%m-%d")
        if day_key in totals:
            cost = (event.actual_cost if event.actual_cost is not None else event.calculated_cost) or 0
            totals[day_key] += int(cost)
            
    # Add standalone session costs
    for session in request.app.state.daily_session_costs:
        if session["date"] in totals:
            totals[session["date"]] += int(session["amount"])
    weekly_total = sum(totals.values())
    return {
        "daily_totals": totals,
        "weekly_total": weekly_total,
        "week_start": week_start.isoformat(),
    }
