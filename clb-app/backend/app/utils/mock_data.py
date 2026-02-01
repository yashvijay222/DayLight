from datetime import datetime, timedelta, timezone
from typing import List
from uuid import uuid4

from app.models import Event, TeamMetrics

# EST timezone (UTC-5)
EST = timezone(timedelta(hours=-5))


def _now_est() -> datetime:
    """Get current time in EST as naive datetime."""
    return datetime.now(EST).replace(tzinfo=None)


def _start_of_week(dt: datetime) -> datetime:
    """Get Sunday 9am of the current week (Sun-Sat week for your 7-day view)."""
    days_since_sunday = (dt.weekday() + 1) % 7
    start = dt - timedelta(days=days_since_sunday)
    return start.replace(hour=9, minute=0, second=0, microsecond=0)


def generate_mock_week() -> List[Event]:
    """
    Generate a fixed set of 5 raw events for testing.
    
    These events only have title, duration, and description.
    event_type is None (to be classified by AI).
    participants/has_agenda are None (to be enriched by user for meetings).
    """
    base = _start_of_week(_now_est())
    events: List[Event] = []

    # Fixed 5 events: (title, duration_minutes, description, day_offset, start_hour)
    # day_offset: 0=Sun, 1=Mon, 2=Tue, 3=Wed, 4=Thu, 5=Fri, 6=Sat
    templates = [
        (
            "Weekly Team Standup",
            30,
            "Regular team sync to discuss blockers and progress",
            1,  # Monday
            9,
        ),
        (
            "Deep Focus: Feature Development",
            120,
            "Uninterrupted coding time for the new dashboard feature",
            1,  # Monday
            14,
        ),
        (
            "Client Strategy Call",
            60,
            "Quarterly review call with the client stakeholders",
            2,  # Tuesday
            10,
        ),
        (
            "Lunch Walk",
            30,
            "Quick walk around the block to recharge",
            3,  # Wednesday
            12,
        ),
        (
            "Sprint Planning",
            90,
            "Planning session for the upcoming two-week sprint",
            4,  # Thursday
            9,
        ),
    ]

    for title, duration, description, day_offset, start_hour in templates:
        start_time = base + timedelta(days=day_offset, hours=start_hour - 9)
        end_time = start_time + timedelta(minutes=duration)
        event = Event(
            id=str(uuid4()),
            title=title,
            description=description,
            start_time=start_time,
            end_time=end_time,
            duration_minutes=duration,
            # These fields are None - to be classified/enriched later
            participants=None,
            has_agenda=None,
            event_type=None,  # AI will classify this
            calculated_cost=None,
            is_flexible=None,
        )
        events.append(event)

    return events


def generate_team_metrics() -> TeamMetrics:
    return TeamMetrics(
        health_score=72,
        high_risk_percentage=18,
        avg_context_switches=5.4,
        insights=[
            "Meeting density is highest on Tuesday and Thursday.",
            "Teams with fewer context switches show lower debt.",
            "Afternoon meetings tend to have lower cognitive cost.",
        ],
    )
