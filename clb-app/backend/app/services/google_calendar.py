import os
from datetime import datetime, timedelta
from typing import List, Optional
from uuid import uuid4

from app.models import Event


def get_auth_url() -> str:
    return "https://accounts.google.com/o/oauth2/auth?mock=true"


def handle_callback(code: str) -> dict:
    return {"access_token": f"mock-token-{code}", "expires_in": 3600}


def fetch_events(access_token: Optional[str], start_date: datetime, end_date: datetime) -> List[Event]:
    """
    Generate realistic mock events simulating Google Calendar import.
    
    Returns raw events with only basic calendar info (title, time, duration).
    event_type, participants, has_agenda, requires_tool_switch are NOT set -
    they will be classified by AI and enriched by the user.
    """
    import random
    
    # Templates: (title, duration_minutes, description)
    # Note: We don't include event_type or meeting fields - those come from AI + user
    templates = [
        ("Team Standup", 15, "Daily sync with the team"),
        ("Sprint Planning", 60, "Planning session for the upcoming sprint"),
        ("1:1 with Manager", 30, "Weekly check-in with direct manager"),
        ("Client Call", 45, "Call with external stakeholders"),
        ("Deep Work: Feature Dev", 120, "Focused development time"),
        ("Design Review", 45, "Review the latest design mockups"),
        ("Lunch Break", 30, "Midday break"),
        ("Code Review Session", 30, "Review pending pull requests"),
        ("Focus Time", 90, "Protected focus time block"),
        ("All Hands", 60, "Company-wide meeting"),
        ("Quick Sync", 15, "Brief alignment discussion"),
        ("Walking Meeting", 30, "Walk and talk session"),
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
                    description=tpl[2],
                    start_time=start_time,
                    end_time=end_time,
                    duration_minutes=duration,
                    # These fields are intentionally None - to be classified/enriched later
                    participants=None,
                    has_agenda=None,
                    event_type=None,
                    is_flexible=None,
                )
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
