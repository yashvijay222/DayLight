from datetime import datetime
from typing import Dict, List, Optional, Tuple

from app.models import Event, RecoveryActivity

DAILY_BUDGET = 20
BASE_COST_PER_15MIN = 1
PROXIMITY_THRESHOLD_MINUTES = 60  # Events within 1 hour of previous get proximity penalty
PROXIMITY_INCREMENT = 2  # Extra points for back-to-back events

RECOVERY_VALUES = {
    "micro_break": -5,
    "walk_30min": -10,
    "deep_work_60min": -12,
    "exercise": -15,
    "nature_2hr": -20,
    "full_day_off": -40,
}


def calculate_event_base_cost(event: Event) -> int:
    """Calculate the base cost of an event without proximity considerations."""
    # Recovery events have negative costs (reduce debt)
    if event.event_type == "recovery":
        if event.duration_minutes <= 15:
            return RECOVERY_VALUES["micro_break"]
        elif event.duration_minutes <= 30:
            return RECOVERY_VALUES["walk_30min"]
        elif event.duration_minutes <= 60:
            return RECOVERY_VALUES["deep_work_60min"]
        elif event.duration_minutes <= 90:
            return RECOVERY_VALUES["exercise"]
        else:
            return RECOVERY_VALUES["nature_2hr"]
    
    # Deep work has lower cost (focused, no context switching)
    if event.event_type == "deep_work":
        cost = (event.duration_minutes / 15) * BASE_COST_PER_15MIN * 0.5
        return round(cost)
    
    # Regular events (meetings, admin, etc.)
    # Use defaults if fields are None (for incomplete events)
    participants = event.participants if event.participants is not None else 1
    has_agenda = event.has_agenda if event.has_agenda is not None else True
    requires_tool_switch = event.requires_tool_switch if event.requires_tool_switch is not None else False
    
    cost = (event.duration_minutes / 15) * BASE_COST_PER_15MIN
    if requires_tool_switch:
        cost += 3
    cost += participants * 0.5
    if not has_agenda:
        cost += 4
    if event.start_time.hour >= 14:
        cost *= 0.9
    return round(cost)


def calculate_event_cost(event: Event, previous_event_end: Optional[datetime] = None) -> int:
    """Calculate event cost with optional proximity penalty."""
    base_cost = calculate_event_base_cost(event)
    
    # Only add proximity increment for positive-cost events (not recovery)
    if base_cost > 0 and previous_event_end is not None:
        gap_minutes = (event.start_time - previous_event_end).total_seconds() / 60
        if 0 <= gap_minutes <= PROXIMITY_THRESHOLD_MINUTES:
            base_cost += PROXIMITY_INCREMENT
    
    return base_cost


def calculate_cost_breakdown(event: Event, previous_event_end: Optional[datetime] = None) -> Dict:
    """Return a detailed breakdown of how an event's cost is calculated."""
    breakdown = {
        "event_id": event.id,
        "event_type": event.event_type,
        "base": 0,
        "duration_component": 0,
        "tool_switch": 0,
        "participants": 0,
        "no_agenda": 0,
        "afternoon_discount": 0,
        "proximity_increment": 0,
        "total": 0,
    }
    
    if event.event_type == "recovery":
        if event.duration_minutes <= 15:
            breakdown["base"] = RECOVERY_VALUES["micro_break"]
        elif event.duration_minutes <= 30:
            breakdown["base"] = RECOVERY_VALUES["walk_30min"]
        elif event.duration_minutes <= 60:
            breakdown["base"] = RECOVERY_VALUES["deep_work_60min"]
        elif event.duration_minutes <= 90:
            breakdown["base"] = RECOVERY_VALUES["exercise"]
        else:
            breakdown["base"] = RECOVERY_VALUES["nature_2hr"]
        breakdown["total"] = breakdown["base"]
        return breakdown
    
    if event.event_type == "deep_work":
        breakdown["duration_component"] = round((event.duration_minutes / 15) * BASE_COST_PER_15MIN * 0.5)
        breakdown["base"] = breakdown["duration_component"]
        breakdown["total"] = breakdown["base"]
        # Proximity for deep work (positive cost)
        if previous_event_end is not None:
            gap_minutes = (event.start_time - previous_event_end).total_seconds() / 60
            if 0 <= gap_minutes <= PROXIMITY_THRESHOLD_MINUTES:
                breakdown["proximity_increment"] = PROXIMITY_INCREMENT
                breakdown["total"] += PROXIMITY_INCREMENT
        return breakdown
    
    # Regular events (meeting, admin)
    participants = event.participants if event.participants is not None else 1
    has_agenda = event.has_agenda if event.has_agenda is not None else True
    requires_tool_switch = event.requires_tool_switch if event.requires_tool_switch is not None else False
    
    duration_cost = (event.duration_minutes / 15) * BASE_COST_PER_15MIN
    breakdown["duration_component"] = round(duration_cost)
    
    running_total = duration_cost
    
    if requires_tool_switch:
        breakdown["tool_switch"] = 3
        running_total += 3
    
    participant_cost = participants * 0.5
    breakdown["participants"] = round(participant_cost)
    running_total += participant_cost
    
    if not has_agenda:
        breakdown["no_agenda"] = 4
        running_total += 4
    
    if event.start_time.hour >= 14:
        discount = running_total * 0.1
        breakdown["afternoon_discount"] = -round(discount)
        running_total *= 0.9
    
    breakdown["base"] = round(running_total)
    
    # Proximity increment for positive-cost events
    if previous_event_end is not None:
        gap_minutes = (event.start_time - previous_event_end).total_seconds() / 60
        if 0 <= gap_minutes <= PROXIMITY_THRESHOLD_MINUTES:
            breakdown["proximity_increment"] = PROXIMITY_INCREMENT
    
    breakdown["total"] = breakdown["base"] + breakdown["proximity_increment"]
    return breakdown


def calculate_events_with_proximity(events: List[Event]) -> List[Tuple[Event, int]]:
    """Calculate costs for all events considering proximity penalties."""
    sorted_events = sorted(events, key=lambda e: e.start_time)
    results: List[Tuple[Event, int]] = []
    
    previous_end: Optional[datetime] = None
    for event in sorted_events:
        cost = calculate_event_cost(event, previous_end)
        event.calculated_cost = cost
        results.append((event, cost))
        # Track the previous event end time regardless of cost type
        previous_end = event.end_time
    
    return results


def calculate_daily_total(events: List[Event]) -> int:
    """Calculate total cost for a day's events with proximity awareness."""
    results = calculate_events_with_proximity(events)
    return sum(cost for _, cost in results)


def detect_overdraft(total: int, budget: int = DAILY_BUDGET) -> Tuple[bool, int, int]:
    remaining = budget - total
    is_overdrafted = remaining < 0
    overdraft_amount = abs(remaining) if is_overdrafted else 0
    return is_overdrafted, overdraft_amount, remaining


def suggest_recovery_activities(overdraft_amount: int) -> List[RecoveryActivity]:
    if overdraft_amount <= 0:
        return []

    activities = [
        RecoveryActivity(
            activity_type="micro_break",
            name="Micro Break",
            point_value=RECOVERY_VALUES["micro_break"],
            duration_minutes=10,
            description="Quick 5-10 minute reset to reduce overload.",
        ),
        RecoveryActivity(
            activity_type="walk_30min",
            name="30 Min Walk",
            point_value=RECOVERY_VALUES["walk_30min"],
            duration_minutes=30,
            description="Light movement to restore focus and reduce stress.",
        ),
        RecoveryActivity(
            activity_type="deep_work_60min",
            name="Deep Work Block",
            point_value=RECOVERY_VALUES["deep_work_60min"],
            duration_minutes=60,
            description="Protected focus time to rebuild cognitive surplus.",
        ),
        RecoveryActivity(
            activity_type="exercise",
            name="Exercise Session",
            point_value=RECOVERY_VALUES["exercise"],
            duration_minutes=45,
            description="Moderate workout to reset stress and recovery.",
        ),
        RecoveryActivity(
            activity_type="nature_2hr",
            name="Nature Recharge",
            point_value=RECOVERY_VALUES["nature_2hr"],
            duration_minutes=120,
            description="Extended outdoor time for full mental reset.",
        ),
    ]

    activities.sort(key=lambda a: a.point_value)
    return activities
