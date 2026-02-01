from __future__ import annotations

from datetime import datetime
from typing import List, Literal, Optional

from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    day: str
    available: bool = True
    priority: Optional[str] = "normal"  # "high" for overloaded days, "normal" otherwise


class Event(BaseModel):
    id: str
    google_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    # Meeting-specific fields - Optional for incomplete events (user will enrich)
    participants: Optional[int] = None
    has_agenda: Optional[bool] = None
    requires_tool_switch: Optional[bool] = None
    event_type: Optional[str] = None  # Set by classifier
    calculated_cost: Optional[int] = None
    actual_cost: Optional[int] = None
    is_flexible: Optional[bool] = None  # True = movable, False = unmovable


class EventCreate(BaseModel):
    title: str
    description: Optional[str] = None
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    participants: Optional[int] = None
    has_agenda: Optional[bool] = None
    requires_tool_switch: Optional[bool] = None
    event_type: Optional[str] = None


class EventEnrich(BaseModel):
    """Payload for enriching meeting-specific fields."""
    participants: Optional[int] = None
    has_agenda: Optional[bool] = None
    requires_tool_switch: Optional[bool] = None


class FlexibilityClassification(BaseModel):
    """Simplified flexibility: only movable or unmovable."""
    event_id: str
    is_flexible: bool  # True = movable, False = unmovable


class CostBreakdown(BaseModel):
    """Detailed breakdown of how an event's cost is calculated."""
    event_id: str
    event_type: Optional[str] = None
    base: int = 0
    duration_component: int = 0
    tool_switch: int = 0
    participants: int = 0
    no_agenda: int = 0
    afternoon_discount: int = 0
    proximity_increment: int = 0
    total: int = 0


class BudgetStatus(BaseModel):
    daily_budget: int
    spent: int
    remaining: int
    is_overdrafted: bool
    overdraft_amount: int
    weekly_total: int
    weekly_debt: int


class RecoveryActivity(BaseModel):
    activity_type: str
    name: str
    point_value: int
    duration_minutes: int
    description: str
    suggested_slots: List[TimeSlot] = []


class OptimizationSuggestion(BaseModel):
    suggestion_id: str
    event_id: str
    suggestion_type: str
    new_time: Optional[datetime] = None
    debt_reduction: int
    reason: Optional[str] = None


class ScheduleChange(BaseModel):
    event_id: str
    event_title: Optional[str] = None
    change_type: str
    original_time: datetime
    new_time: Optional[datetime] = None
    applied: bool = False


class WeekOptimizationProposal(BaseModel):
    """Proposed schedule changes to optimize the week."""
    proposal_id: str
    changes: List[ScheduleChange] = []
    current_max_daily_debt: int = 0
    proposed_max_daily_debt: int = 0
    total_debt_reduction: int = 0


class PresageReading(BaseModel):
    hrv: int
    breathing_rate: int
    focus_score: int
    stress_level: int
    timestamp: datetime
    cognitive_cost_delta: int


class SageSession(BaseModel):
    session_id: str
    event_id: Optional[str] = None
    start_time: datetime
    readings: List[PresageReading] = []
    estimated_cost: int
    actual_cost: Optional[int] = None
    debt_adjustment: Optional[int] = None


class TeamMetrics(BaseModel):
    health_score: int
    high_risk_percentage: int
    avg_context_switches: float
    insights: List[str]
