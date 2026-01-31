from datetime import datetime, timedelta
from typing import List
from uuid import uuid4

from app.models import Event, TeamMetrics
from app.services.cognitive_calculator import calculate_event_cost


def _start_of_week(dt: datetime) -> datetime:
    start = dt - timedelta(days=dt.weekday())
    return start.replace(hour=9, minute=0, second=0, microsecond=0)


def generate_mock_week() -> List[Event]:
    base = _start_of_week(datetime.utcnow())
    events: List[Event] = []

    templates = [
        ("Product Sync", 60, 6, True, True, "meeting"),
        ("Deep Work Block", 90, 1, True, False, "deep_work"),
        ("1:1 Check-in", 30, 2, True, False, "meeting"),
        ("Design Review", 45, 5, False, True, "meeting"),
        ("Walk Break", 30, 1, True, False, "recovery"),
        ("Roadmap Planning", 60, 8, True, True, "meeting"),
        ("Focus Sprint", 120, 1, True, False, "deep_work"),
        ("Email Cleanup", 30, 1, True, True, "admin"),
        ("Team Retro", 60, 7, False, True, "meeting"),
        ("Micro Break", 15, 1, True, False, "recovery"),
    ]

    for i, tpl in enumerate(templates):
        day_offset = i % 5
        start_time = base + timedelta(days=day_offset, hours=i % 4)
        end_time = start_time + timedelta(minutes=tpl[1])
        event = Event(
            id=str(uuid4()),
            title=tpl[0],
            start_time=start_time,
            end_time=end_time,
            duration_minutes=tpl[1],
            participants=tpl[2],
            has_agenda=tpl[3],
            requires_tool_switch=tpl[4],
            event_type=tpl[5],
        )
        event.calculated_cost = calculate_event_cost(event)
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
