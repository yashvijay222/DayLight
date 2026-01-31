"""
Event classifier service using Gemini API (google.genai) to determine event types.
"""
import os
from typing import List, Optional

from google import genai


VALID_EVENT_TYPES = ["meeting", "deep_work", "recovery", "admin"]


def classify_event(
    title: str,
    duration_minutes: int,
    description: Optional[str] = None
) -> str:
    """
    Use Gemini to classify an event into one of the valid event types.
    
    Args:
        title: The event title
        duration_minutes: Duration in minutes
        description: Optional event description
        
    Returns:
        One of: "meeting", "deep_work", "recovery", "admin"
    """
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        # Fallback to simple heuristics if no API key
        return _classify_fallback(title, duration_minutes, description)
    
    prompt = f"""Classify this calendar event into exactly one category.

Event Title: {title}
Duration: {duration_minutes} minutes
{f'Description: {description}' if description else ''}

Categories:
- "meeting": Meetings with others, calls, syncs, standups, 1:1s, reviews, interviews
- "deep_work": Focused solo work, coding, writing, design, research, study time
- "recovery": Breaks, lunch, walks, exercise, meditation, personal time, gym
- "admin": Administrative tasks, emails, scheduling, organizing, paperwork

Respond with ONLY the category name (meeting, deep_work, recovery, or admin), nothing else."""

    try:
        client = genai.Client(api_key=api_key)
        response = client.models.generate_content(
            model="gemini-2.5-flash",
            contents=prompt,
        )
        result = response.text.strip().lower()
        
        # Validate the response
        if result in VALID_EVENT_TYPES:
            return result
        
        # Try to extract a valid type from the response
        for event_type in VALID_EVENT_TYPES:
            if event_type in result:
                return event_type
        
        # Default to meeting if unclear
        return "meeting"
        
    except Exception as e:
        print(f"Gemini API error: {e}")
        return _classify_fallback(title, duration_minutes, description)


def _classify_fallback(
    title: str,
    duration_minutes: int,
    description: Optional[str] = None
) -> str:
    """Simple keyword-based fallback classification."""
    text = f"{title} {description or ''}".lower()
    
    # Recovery keywords
    recovery_keywords = [
        "break", "lunch", "walk", "exercise", "gym", "rest", "meditation",
        "yoga", "personal", "recovery", "relax", "nap"
    ]
    if any(kw in text for kw in recovery_keywords):
        return "recovery"
    
    # Deep work keywords
    deep_work_keywords = [
        "focus", "deep work", "coding", "writing", "design", "research",
        "study", "development", "implementation", "concentrate", "solo"
    ]
    if any(kw in text for kw in deep_work_keywords):
        return "deep_work"
    
    # Admin keywords
    admin_keywords = [
        "email", "admin", "organize", "paperwork", "schedule", "planning",
        "review docs", "cleanup", "filing", "expense"
    ]
    if any(kw in text for kw in admin_keywords):
        return "admin"
    
    # Meeting keywords (or default)
    meeting_keywords = [
        "meeting", "call", "sync", "standup", "1:1", "interview", "review",
        "discussion", "catchup", "chat", "team", "client"
    ]
    if any(kw in text for kw in meeting_keywords):
        return "meeting"
    
    # Default to meeting for unclassified events
    return "meeting"


async def classify_events_batch(events: List[dict]) -> List[str]:
    """
    Classify multiple events. For now, classifies sequentially.
    Could be optimized with batch API calls in the future.
    """
    results = []
    for event in events:
        event_type = classify_event(
            title=event.get("title", ""),
            duration_minutes=event.get("duration_minutes", 30),
            description=event.get("description")
        )
        results.append(event_type)
    return results
