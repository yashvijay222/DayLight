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
    daily_events = [e for e in events if e.start_time.date() == today]
    # Only count points for events that have already ended (your feature: real-time updates)
    completed_today = [e for e in daily_events if now >= e.end_time]
    total = sum(e.calculated_cost or 0 for e in completed_today)
    is_overdrafted, overdraft_amount, remaining = detect_overdraft(total, DAILY_BUDGET)
    weekly_total = sum(e.calculated_cost or 0 for e in events)
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
    # Use the week that contains our events so the heatmap shows real expenditure (your feature)
    if events:
        first_date = min(e.start_time.date() for e in events)
        days_since_sunday = (first_date.weekday() + 1) % 7
        week_start = first_date - timedelta(days=days_since_sunday)
    else:
        days_since_sunday = (today.weekday() + 1) % 7
        week_start = today - timedelta(days=days_since_sunday)
    # All 7 days: Sunday–Saturday (your feature: full week heatmap)
    week_dates = [week_start + timedelta(days=i) for i in range(7)]
    totals = {d.strftime("%Y-%m-%d"): 0 for d in week_dates}
    for event in events:
        day_key = event.start_time.strftime("%Y-%m-%d")
        if day_key in totals:
            totals[day_key] += event.calculated_cost or 0
    weekly_total = sum(totals.values())
    return {
        "daily_totals": totals,
        "weekly_total": weekly_total,
        "week_start": week_start.isoformat(),
    }
