import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from app.models import Event
from app.services.cognitive_calculator import calculate_event_cost


def get_auth_url() -> str:
    return "https://accounts.google.com/o/oauth2/auth?mock=true"


def handle_callback(code: str) -> dict:
    return {"access_token": f"mock-token-{code}", "expires_in": 3600}


def fetch_events(access_token: Optional[str], start_date: datetime, end_date: datetime) -> List[Event]:
    """Generate realistic mock events simulating Google Calendar import."""
    import random
    
    templates = [
        ("Team Standup", 15, 5, True, False, "meeting"),
        ("Sprint Planning", 60, 8, True, True, "meeting"),
        ("1:1 with Manager", 30, 2, True, False, "meeting"),
        ("Client Call", 45, 4, False, True, "meeting"),
        ("Deep Work: Feature Dev", 120, 1, True, False, "deep_work"),
        ("Design Review", 45, 6, True, True, "meeting"),
        ("Lunch Break", 30, 1, True, False, "recovery"),
        ("Code Review Session", 30, 3, True, True, "meeting"),
        ("Focus Time", 90, 1, True, False, "deep_work"),
        ("All Hands", 60, 20, False, True, "meeting"),
        ("Quick Sync", 15, 3, True, False, "meeting"),
        ("Walking Meeting", 30, 2, True, False, "recovery"),
    ]
    
    events: List[Event] = []
    cursor = start_date.replace(hour=9, minute=0, second=0, microsecond=0)
    
    day_count = 0
    while cursor < end_date and day_count < 7:
        # Skip weekends
        if cursor.weekday() < 5:
            # Add 2-4 events per day
            daily_events = random.sample(templates, min(random.randint(2, 4), len(templates)))
            hour = 9
            
            for tpl in daily_events:
                if hour >= 17:
                    break
                    
                start_time = cursor.replace(hour=hour, minute=0)
                duration = tpl[1]
                end_time = start_time + timedelta(minutes=duration)
                
                event = Event(
                    id=str(uuid4()),
                    google_id=str(uuid4()),
                    title=tpl[0],
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=duration,
                    participants=tpl[2],
                    has_agenda=tpl[3],
                    requires_tool_switch=tpl[4],
                    event_type=tpl[5],
                )
                event.calculated_cost = calculate_event_cost(event)
                events.append(event)
                
                # Next event starts after this one plus a gap
                hour += (duration // 60) + 1
        
        cursor += timedelta(days=1)
        day_count += 1
    
    return events


def create_event(access_token: Optional[str], event: Event) -> dict:
    return {"status": "created", "google_id": event.google_id or str(uuid4())}


def update_event(access_token: Optional[str], event_id: str, changes: dict) -> dict:
    return {"status": "updated", "event_id": event_id, "changes": changes}


def delete_event(access_token: Optional[str], event_id: str) -> dict:
    return {"status": "deleted", "event_id": event_id}


def use_mock_data() -> bool:
    return os.getenv("USE_MOCK_DATA", "true").lower() == "true"
