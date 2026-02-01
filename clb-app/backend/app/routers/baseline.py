"""
Baseline Router - User Baseline Management API

Endpoints for managing per-user vital sign baselines used
for personalized cognitive load calculation.

Phase 3: Personalization
"""

import logging
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.services.user_baseline import (
    get_baseline_storage,
    get_baseline_summary,
    reset_baseline,
    get_personalized_config,
    UserBaseline,
)
from app.services.cognitive_load import DEFAULT_CONFIG

router = APIRouter()
logger = logging.getLogger(__name__)


# ============================================================================
# Request/Response Models
# ============================================================================

class BaselineStatusResponse(BaseModel):
    """Response for baseline status endpoint."""
    user_id: str
    exists: bool
    is_calibrated: bool
    calibration_progress: float
    calibration_sessions: int
    pulse_mean: Optional[float] = None
    pulse_std_dev: Optional[float] = None
    pulse_optimal_range: Optional[list] = None
    pulse_samples: Optional[int] = None
    breathing_mean: Optional[float] = None
    breathing_std_dev: Optional[float] = None
    breathing_optimal_range: Optional[list] = None
    breathing_samples: Optional[int] = None
    hrv_mean: Optional[float] = None
    hrv_samples: Optional[int] = None
    message: str


class PersonalizedConfigResponse(BaseModel):
    """Response showing personalized vs default config."""
    user_id: str
    is_personalized: bool
    breathing_optimal_range: list
    pulse_optimal_range: list
    hrv_default: float
    message: str


class ResetResponse(BaseModel):
    """Response for reset endpoint."""
    user_id: str
    success: bool
    message: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/baseline/{user_id}", response_model=BaselineStatusResponse)
async def get_user_baseline(user_id: str) -> BaselineStatusResponse:
    """
    Get the current baseline status for a user.
    
    Returns calibration progress and learned vital sign ranges.
    """
    summary = get_baseline_summary(user_id)
    
    if summary is None:
        return BaselineStatusResponse(
            user_id=user_id,
            exists=False,
            is_calibrated=False,
            calibration_progress=0.0,
            calibration_sessions=0,
            message="No baseline exists for this user. Start a Sage session to begin calibration."
        )
    
    response = BaselineStatusResponse(
        user_id=user_id,
        exists=True,
        is_calibrated=summary["is_calibrated"],
        calibration_progress=summary["calibration_progress"],
        calibration_sessions=summary["calibration_sessions"],
        message="Baseline is fully calibrated. Personalized ranges are active." if summary["is_calibrated"] 
                else f"Calibration in progress: {summary['calibration_progress']}% complete."
    )
    
    # Add pulse data if available
    if summary.get("pulse"):
        response.pulse_mean = summary["pulse"]["mean"]
        response.pulse_std_dev = summary["pulse"]["std_dev"]
        response.pulse_optimal_range = summary["pulse"]["optimal_range"]
        response.pulse_samples = summary["pulse"]["samples"]
    
    # Add breathing data if available
    if summary.get("breathing"):
        response.breathing_mean = summary["breathing"]["mean"]
        response.breathing_std_dev = summary["breathing"]["std_dev"]
        response.breathing_optimal_range = summary["breathing"]["optimal_range"]
        response.breathing_samples = summary["breathing"]["samples"]
    
    # Add HRV data if available
    if summary.get("hrv"):
        response.hrv_mean = summary["hrv"]["mean"]
        response.hrv_samples = summary["hrv"]["samples"]
    
    return response


@router.get("/baseline/{user_id}/config", response_model=PersonalizedConfigResponse)
async def get_user_config(user_id: str) -> PersonalizedConfigResponse:
    """
    Get the cognitive load config that would be used for a user.
    
    Shows whether personalized ranges are active and what they are.
    """
    config = get_personalized_config(user_id, DEFAULT_CONFIG)
    
    # Check if this is actually personalized
    is_personalized = (
        config.breathing_optimal_min != DEFAULT_CONFIG.breathing_optimal_min or
        config.breathing_optimal_max != DEFAULT_CONFIG.breathing_optimal_max or
        config.pulse_optimal_min != DEFAULT_CONFIG.pulse_optimal_min or
        config.pulse_optimal_max != DEFAULT_CONFIG.pulse_optimal_max
    )
    
    return PersonalizedConfigResponse(
        user_id=user_id,
        is_personalized=is_personalized,
        breathing_optimal_range=[
            round(config.breathing_optimal_min, 1),
            round(config.breathing_optimal_max, 1)
        ],
        pulse_optimal_range=[
            round(config.pulse_optimal_min, 1),
            round(config.pulse_optimal_max, 1)
        ],
        hrv_default=round(config.hrv_default, 1),
        message="Using personalized ranges based on your baseline." if is_personalized
                else "Using population norms. Complete more sessions to enable personalization."
    )


@router.delete("/baseline/{user_id}", response_model=ResetResponse)
async def reset_user_baseline(user_id: str) -> ResetResponse:
    """
    Reset a user's baseline to start fresh calibration.
    
    This removes all learned vital sign data for the user.
    Use this if the user's baseline seems inaccurate.
    """
    success = reset_baseline(user_id)
    
    if success:
        logger.info(f"Reset baseline for user {user_id}")
        return ResetResponse(
            user_id=user_id,
            success=True,
            message="Baseline reset successfully. Calibration will restart on next session."
        )
    else:
        return ResetResponse(
            user_id=user_id,
            success=False,
            message="No baseline existed for this user."
        )


@router.get("/baseline")
async def list_all_baselines() -> dict:
    """
    List all users with baselines (admin endpoint).
    """
    storage = get_baseline_storage()
    users = storage.list_users()
    
    summaries = []
    for user_id in users:
        summary = get_baseline_summary(user_id)
        if summary:
            summaries.append({
                "user_id": user_id,
                "is_calibrated": summary["is_calibrated"],
                "calibration_progress": summary["calibration_progress"],
                "calibration_sessions": summary["calibration_sessions"],
            })
    
    return {
        "total_users": len(users),
        "baselines": summaries
    }


@router.post("/baseline/{user_id}/complete-session")
async def mark_session_complete(user_id: str) -> dict:
    """
    Manually mark a calibration session as complete.
    
    Normally this is done automatically at the end of a Sage session,
    but this endpoint allows manual completion if needed.
    """
    storage = get_baseline_storage()
    baseline = storage.get_or_create(user_id)
    baseline.complete_session()
    storage.save(baseline)
    
    return {
        "user_id": user_id,
        "calibration_sessions": baseline.calibration_sessions,
        "is_calibrated": baseline.is_calibrated,
        "calibration_progress": baseline.calibration_progress,
        "message": f"Session {baseline.calibration_sessions} marked complete."
    }
