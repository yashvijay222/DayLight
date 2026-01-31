from typing import List, Tuple

from app.models import Event, RecoveryActivity

DAILY_BUDGET = 32
BASE_COST_PER_15MIN = 1

RECOVERY_VALUES = {
    "micro_break": -5,
    "walk_30min": -10,
    "deep_work_60min": -12,
    "exercise": -15,
    "nature_2hr": -20,
    "full_day_off": -40,
}


def calculate_event_cost(event: Event) -> int:
    # Recovery events have negative costs (reduce debt)
    if event.event_type == "recovery":
        # Map duration to recovery value
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
    cost = (event.duration_minutes / 15) * BASE_COST_PER_15MIN
    if event.requires_tool_switch:
        cost += 3
    cost += event.participants * 0.5
    if not event.has_agenda:
        cost += 4
    if event.start_time.hour >= 14:
        cost *= 0.9
    return round(cost)


def calculate_daily_total(events: List[Event]) -> int:
    return sum(calculate_event_cost(e) for e in events)


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
