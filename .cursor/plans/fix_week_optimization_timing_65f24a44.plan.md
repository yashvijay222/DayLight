---
name: Fix week optimization timing
overview: Fix the week optimization algorithm to properly schedule events without overlaps, pack events early in the day to maximize free evening time, and treat mid-day gaps as costly. Switch from OpenAI to Gemini API.
todos:
  - id: fix-optimizer
    content: Rewrite optimize_week() with proper slot-finding that packs events early, avoids overlaps, and minimizes mid-day gaps
    status: completed
  - id: switch-to-gemini
    content: Replace OpenAI API with Gemini API in event_classifier.py and update requirements.txt
    status: completed
isProject: false
---

# Fix Week Optimization Timing Bugs

## Problem 1: Events can overlap after optimization

The current `optimize_week()` function in `[schedule_optimizer.py](clb-app/backend/app/services/schedule_optimizer.py)` uses a simple list of start hours `[9, 10, 11, 14, 15, 16]` and cycles through them without checking:

- Event durations
- Existing unmovable events on the target day
- Other movable events already assigned to that day

This causes events to potentially start before previous events end.

## Problem 2: Optimization goal - "Finish your day ASAP"

The algorithm should follow this mantra: **finish your day as soon as possible**.

- **Gaps during the day are bad** - Any unplanned time between events is treated as negative debt that increases linearly for consecutive free hours
- **Evening free time is good** - The goal is to pack events early so the user has the evening free
- **Accept proximity penalties** - Back-to-back events are fine (the +2 proximity penalty is worth it to finish earlier)

### Scoring model for gaps

For mid-day gaps (free time between 9am and last event):

- 1 hour gap = 1 penalty
- 2 consecutive hours = 3 penalty
- 3 consecutive hours = 5 penalty
- Formula: `gap_penalty = 2*hours - 1`

Free time AFTER the last event (evening) = no penalty (this is the goal)

## Fix: Rewrite `optimize_week()` with "pack early" strategy

### Changes to `schedule_optimizer.py`

Replace the naive slot assignment with a proper scheduling algorithm:

1. **Build occupied ranges per day** - For each day, track time ranges occupied by unmovable events
2. **Find EARLIEST available slot** - New helper function `_find_earliest_slot(day_events, event_duration, day_date, work_start=9, work_end=17)`:
  - Sort existing events by start time
  - Find the FIRST gap that fits the event duration
  - Pack events as early as possible (right after the previous event ends)
  - No preference for gaps - we WANT events back-to-back
3. **Assign movable events greedily** - For each movable event:
  - Try each day in order of remaining capacity
  - Use `_find_earliest_slot()` to get the earliest non-overlapping time
  - Pack immediately after the last event on that day
  - Update the day's occupied ranges
4. **Score days by "finish time"** - When choosing which day to assign an event to:
  - Prefer days where adding this event results in the earliest finish time across all days
  - Balance: don't overload one day while others are empty

### Pseudocode for new slot-finding

```python
def _find_earliest_slot(day_events: List[Event], duration_minutes: int, day_date: datetime) -> Optional[datetime]:
    """Find the earliest non-overlapping slot, packing events tightly."""
    work_start = 9   # 9am
    work_end = 17    # 5pm
    
    sorted_events = sorted(day_events, key=lambda e: e.start_time)
    
    # Start cursor at beginning of work day
    cursor = day_date.replace(hour=work_start, minute=0, second=0, microsecond=0)
    
    for event in sorted_events:
        # Check if there's a gap before this event that fits our duration
        gap_before = (event.start_time - cursor).total_seconds() / 60
        
        if gap_before >= duration_minutes:
            # Found a slot - return it (pack early)
            return cursor
        
        # Move cursor to after this event
        cursor = max(cursor, event.end_time)
    
    # Check slot after all events
    end_of_day = day_date.replace(hour=work_end, minute=0)
    remaining = (end_of_day - cursor).total_seconds() / 60
    
    if remaining >= duration_minutes:
        return cursor
    
    return None  # No slot found
```

### Day selection scoring

When deciding which day to place a movable event:

```python
def _score_day_for_event(day_events: List[Event], new_event_duration: int, day_date: datetime) -> float:
    """Lower score = better. Prefer days that finish earlier."""
    slot = _find_earliest_slot(day_events, new_event_duration, day_date)
    if slot is None:
        return float('inf')  # Can't fit
    
    # Calculate finish time if we add this event
    new_finish = slot + timedelta(minutes=new_event_duration)
    
    # Score based on how late the day would end
    # Earlier finish = lower score = better
    return new_finish.hour + new_finish.minute / 60.0
```

### Summary of changes

- **File**: `[clb-app/backend/app/services/schedule_optimizer.py](clb-app/backend/app/services/schedule_optimizer.py)`
- **Functions to modify**: `optimize_week()`
- **New helpers**: `_find_earliest_slot()`, `_score_day_for_event()`
- **Logic**: 
  - Track occupied time ranges per day (unmovable + assigned movable)
  - When placing a movable event, find the EARLIEST non-overlapping slot
  - Pack events tightly (back-to-back is fine)
  - Choose days that result in earliest overall finish time
  - Goal: maximize free evening time, minimize mid-day gaps

---

## Task 2: Switch from OpenAI to Gemini API

### Changes to `event_classifier.py`

Replace OpenAI client with Google's Generative AI (Gemini):

```python
import google.generativeai as genai

def classify_event(title: str, duration_minutes: int, description: Optional[str] = None) -> str:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        return _classify_fallback(title, duration_minutes, description)
    
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel("gemini-1.5-flash")
    
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
        response = model.generate_content(prompt)
        result = response.text.strip().lower()
        # ... validation logic stays the same
    except Exception as e:
        print(f"Gemini API error: {e}")
        return _classify_fallback(title, duration_minutes, description)
```

### Changes to `requirements.txt`

Replace:

```
openai>=1.0.0
```

With:

```
google-generativeai>=0.3.0
```

### Environment variable

Change from `OPENAI_API_KEY` to `GEMINI_API_KEY` in `.env` file