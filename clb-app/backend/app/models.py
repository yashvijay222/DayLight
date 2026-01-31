from __future__ import annotations

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, Field


class TimeSlot(BaseModel):
    start_time: datetime
    end_time: datetime
    day: str
    available: bool = True


class Event(BaseModel):
    id: str
    google_id: Optional[str] = None
    title: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    participants: int = 1
    has_agenda: bool = True
    requires_tool_switch: bool = False
    event_type: str = "meeting"
    calculated_cost: Optional[int] = None
    actual_cost: Optional[int] = None
    is_flexible: Optional[bool] = None
    flexibility_reason: Optional[str] = None


class EventCreate(BaseModel):
    title: str
    start_time: datetime
    end_time: datetime
    duration_minutes: int
    participants: int = 1
    has_agenda: bool = True
    requires_tool_switch: bool = False
    event_type: str = "meeting"


class FlexibilityClassification(BaseModel):
    event_id: str
    is_flexible: bool
    reason: str = Field(..., description="required|moveable|skippable")


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
    change_type: str
    original_time: datetime
    new_time: Optional[datetime] = None
    applied: bool = False


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
