"""
User Baseline Service - Phase 3 Personalization

This module provides per-user baseline learning for vital signs.
Instead of using population norms, we learn each user's personal
resting pulse and breathing rates during initial sessions and
adjust optimal ranges accordingly.

Key concepts:
  - Baseline: A user's average resting vitals (pulse, breathing, HRV)
  - Calibration: Initial period where baseline is learned (N sessions)
  - Personalized ranges: Optimal bands centered on user's baseline
"""

from dataclasses import dataclass, field, asdict
from datetime import datetime, timedelta
from statistics import mean, stdev
from typing import Dict, List, Optional
import json
import logging
import os

logger = logging.getLogger(__name__)


# ============================================================================
# Baseline Models
# ============================================================================

@dataclass
class VitalBaseline:
    """Baseline statistics for a single vital sign."""
    
    mean: float = 0.0
    std_dev: float = 0.0
    min_observed: float = float('inf')
    max_observed: float = float('-inf')
    sample_count: int = 0
    
    def update(self, value: float):
        """Update baseline with a new observation using online algorithm."""
        if value <= 0:
            return
            
        self.sample_count += 1
        
        # Update min/max
        self.min_observed = min(self.min_observed, value)
        self.max_observed = max(self.max_observed, value)
        
        # Welford's online algorithm for mean and variance
        if self.sample_count == 1:
            self.mean = value
            self._m2 = 0.0
        else:
            delta = value - self.mean
            self.mean += delta / self.sample_count
            delta2 = value - self.mean
            self._m2 = getattr(self, '_m2', 0.0) + delta * delta2
            
            if self.sample_count > 1:
                self.std_dev = (self._m2 / (self.sample_count - 1)) ** 0.5
    
    def is_calibrated(self, min_samples: int = 30) -> bool:
        """Check if we have enough samples for reliable baseline."""
        return self.sample_count >= min_samples
    
    @property
    def optimal_min(self) -> float:
        """Lower bound of optimal range (mean - 0.5 * std_dev)."""
        if self.sample_count < 5:
            return self.mean
        return self.mean - 0.5 * self.std_dev
    
    @property
    def optimal_max(self) -> float:
        """Upper bound of optimal range (mean + 0.5 * std_dev)."""
        if self.sample_count < 5:
            return self.mean
        return self.mean + 0.5 * self.std_dev
    
    @property
    def warning_min(self) -> float:
        """Lower warning threshold (mean - 1.5 * std_dev)."""
        if self.sample_count < 5:
            return self.mean - 10
        return self.mean - 1.5 * self.std_dev
    
    @property
    def warning_max(self) -> float:
        """Upper warning threshold (mean + 1.5 * std_dev)."""
        if self.sample_count < 5:
            return self.mean + 10
        return self.mean + 1.5 * self.std_dev
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "mean": self.mean,
            "std_dev": self.std_dev,
            "min_observed": self.min_observed if self.min_observed != float('inf') else None,
            "max_observed": self.max_observed if self.max_observed != float('-inf') else None,
            "sample_count": self.sample_count,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'VitalBaseline':
        """Deserialize from dictionary."""
        baseline = cls()
        baseline.mean = data.get("mean", 0.0)
        baseline.std_dev = data.get("std_dev", 0.0)
        baseline.min_observed = data.get("min_observed") or float('inf')
        baseline.max_observed = data.get("max_observed") or float('-inf')
        baseline.sample_count = data.get("sample_count", 0)
        return baseline


@dataclass
class UserBaseline:
    """Complete baseline profile for a user."""
    
    user_id: str
    pulse: VitalBaseline = field(default_factory=VitalBaseline)
    breathing: VitalBaseline = field(default_factory=VitalBaseline)
    hrv: VitalBaseline = field(default_factory=VitalBaseline)
    
    # Metadata
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    calibration_sessions: int = 0
    
    # Calibration settings
    min_calibration_sessions: int = 5
    min_samples_per_vital: int = 30
    
    @property
    def is_calibrated(self) -> bool:
        """Check if baseline is fully calibrated."""
        return (
            self.calibration_sessions >= self.min_calibration_sessions and
            self.pulse.is_calibrated(self.min_samples_per_vital) and
            self.breathing.is_calibrated(self.min_samples_per_vital)
        )
    
    @property
    def calibration_progress(self) -> float:
        """Return calibration progress as percentage (0-100)."""
        pulse_progress = min(100, (self.pulse.sample_count / self.min_samples_per_vital) * 100)
        breathing_progress = min(100, (self.breathing.sample_count / self.min_samples_per_vital) * 100)
        session_progress = min(100, (self.calibration_sessions / self.min_calibration_sessions) * 100)
        
        # Average of all progress indicators
        return round((pulse_progress + breathing_progress + session_progress) / 3, 1)
    
    def add_reading(self, pulse_rate: float, breathing_rate: float, hrv: Optional[float] = None):
        """Add a single reading to the baseline."""
        if pulse_rate > 0:
            self.pulse.update(pulse_rate)
        if breathing_rate > 0:
            self.breathing.update(breathing_rate)
        if hrv is not None and hrv > 0:
            self.hrv.update(hrv)
        self.updated_at = datetime.utcnow()
    
    def complete_session(self):
        """Mark a calibration session as complete."""
        self.calibration_sessions += 1
        self.updated_at = datetime.utcnow()
    
    def to_dict(self) -> dict:
        """Serialize to dictionary for storage."""
        return {
            "user_id": self.user_id,
            "pulse": self.pulse.to_dict(),
            "breathing": self.breathing.to_dict(),
            "hrv": self.hrv.to_dict(),
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "calibration_sessions": self.calibration_sessions,
            "min_calibration_sessions": self.min_calibration_sessions,
            "min_samples_per_vital": self.min_samples_per_vital,
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> 'UserBaseline':
        """Deserialize from dictionary."""
        baseline = cls(user_id=data["user_id"])
        baseline.pulse = VitalBaseline.from_dict(data.get("pulse", {}))
        baseline.breathing = VitalBaseline.from_dict(data.get("breathing", {}))
        baseline.hrv = VitalBaseline.from_dict(data.get("hrv", {}))
        baseline.created_at = datetime.fromisoformat(data["created_at"]) if "created_at" in data else datetime.utcnow()
        baseline.updated_at = datetime.fromisoformat(data["updated_at"]) if "updated_at" in data else datetime.utcnow()
        baseline.calibration_sessions = data.get("calibration_sessions", 0)
        baseline.min_calibration_sessions = data.get("min_calibration_sessions", 5)
        baseline.min_samples_per_vital = data.get("min_samples_per_vital", 30)
        return baseline
    
    def get_summary(self) -> dict:
        """Get a human-readable summary of the baseline."""
        return {
            "user_id": self.user_id,
            "is_calibrated": self.is_calibrated,
            "calibration_progress": self.calibration_progress,
            "calibration_sessions": self.calibration_sessions,
            "pulse": {
                "mean": round(self.pulse.mean, 1),
                "std_dev": round(self.pulse.std_dev, 1),
                "optimal_range": [round(self.pulse.optimal_min, 1), round(self.pulse.optimal_max, 1)],
                "samples": self.pulse.sample_count,
            } if self.pulse.sample_count > 0 else None,
            "breathing": {
                "mean": round(self.breathing.mean, 1),
                "std_dev": round(self.breathing.std_dev, 1),
                "optimal_range": [round(self.breathing.optimal_min, 1), round(self.breathing.optimal_max, 1)],
                "samples": self.breathing.sample_count,
            } if self.breathing.sample_count > 0 else None,
            "hrv": {
                "mean": round(self.hrv.mean, 1),
                "std_dev": round(self.hrv.std_dev, 1),
                "samples": self.hrv.sample_count,
            } if self.hrv.sample_count > 0 else None,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }


# ============================================================================
# Baseline Storage (In-Memory with File Persistence)
# ============================================================================

class BaselineStorage:
    """
    Storage for user baselines.
    
    Uses in-memory storage with optional file persistence.
    In production, this would be backed by a database.
    """
    
    def __init__(self, storage_path: Optional[str] = None):
        self._baselines: Dict[str, UserBaseline] = {}
        self._storage_path = storage_path or os.getenv(
            "BASELINE_STORAGE_PATH",
            "/tmp/daylight_baselines.json"
        )
        self._load_from_file()
    
    def get(self, user_id: str) -> Optional[UserBaseline]:
        """Get baseline for a user."""
        return self._baselines.get(user_id)
    
    def get_or_create(self, user_id: str) -> UserBaseline:
        """Get existing baseline or create new one."""
        if user_id not in self._baselines:
            self._baselines[user_id] = UserBaseline(user_id=user_id)
            self._save_to_file()
        return self._baselines[user_id]
    
    def save(self, baseline: UserBaseline):
        """Save or update a baseline."""
        self._baselines[baseline.user_id] = baseline
        self._save_to_file()
    
    def delete(self, user_id: str) -> bool:
        """Delete a user's baseline."""
        if user_id in self._baselines:
            del self._baselines[user_id]
            self._save_to_file()
            return True
        return False
    
    def list_users(self) -> List[str]:
        """List all users with baselines."""
        return list(self._baselines.keys())
    
    def _save_to_file(self):
        """Persist baselines to file."""
        try:
            data = {
                user_id: baseline.to_dict()
                for user_id, baseline in self._baselines.items()
            }
            with open(self._storage_path, 'w') as f:
                json.dump(data, f, indent=2)
        except Exception as e:
            logger.warning(f"Failed to save baselines to file: {e}")
    
    def _load_from_file(self):
        """Load baselines from file."""
        try:
            if os.path.exists(self._storage_path):
                with open(self._storage_path, 'r') as f:
                    data = json.load(f)
                    for user_id, baseline_data in data.items():
                        self._baselines[user_id] = UserBaseline.from_dict(baseline_data)
                logger.info(f"Loaded {len(self._baselines)} baselines from storage")
        except Exception as e:
            logger.warning(f"Failed to load baselines from file: {e}")


# Global storage instance
_baseline_storage: Optional[BaselineStorage] = None


def get_baseline_storage() -> BaselineStorage:
    """Get or create the baseline storage singleton."""
    global _baseline_storage
    if _baseline_storage is None:
        _baseline_storage = BaselineStorage()
    return _baseline_storage


# ============================================================================
# Baseline Learning Functions
# ============================================================================

def learn_from_session(
    user_id: str,
    readings: List['PresageReading'],
    complete_session: bool = True
) -> UserBaseline:
    """
    Learn baseline from a session's readings.
    
    Args:
        user_id: User identifier
        readings: List of PresageReading from the session
        complete_session: Whether to mark the session as complete
        
    Returns:
        Updated UserBaseline
    """
    storage = get_baseline_storage()
    baseline = storage.get_or_create(user_id)
    
    # Add each reading to the baseline (only during calibration)
    if not baseline.is_calibrated:
        for reading in readings:
            pulse_rate = getattr(reading, "pulse_rate", None)
            baseline.add_reading(
                pulse_rate=float(pulse_rate) if pulse_rate else 0,
                breathing_rate=reading.breathing_rate,
                hrv=reading.hrv
            )
    
    # Mark session complete if requested (first N sessions)
    if complete_session and readings and baseline.calibration_sessions < baseline.min_calibration_sessions:
        baseline.complete_session()
    
    # Save updated baseline
    storage.save(baseline)
    
    logger.info(f"Updated baseline for user {user_id}: {baseline.calibration_progress}% calibrated")
    
    return baseline


def learn_from_reading(
    user_id: str,
    pulse_rate: float,
    breathing_rate: float,
    hrv: Optional[float] = None
) -> UserBaseline:
    """
    Add a single reading to user's baseline.
    
    Use this for continuous learning during sessions.
    """
    storage = get_baseline_storage()
    baseline = storage.get_or_create(user_id)
    
    if not baseline.is_calibrated:
        baseline.add_reading(pulse_rate, breathing_rate, hrv)
        storage.save(baseline)
    
    return baseline


def get_personalized_config(
    user_id: str,
    fallback_config: Optional['CognitiveLoadConfig'] = None
) -> 'CognitiveLoadConfig':
    """
    Get a CognitiveLoadConfig personalized to the user's baseline.
    
    If the user's baseline is calibrated, returns config with ranges
    adjusted to their personal resting vitals. Otherwise, returns
    the fallback config (or default population norms).
    
    Args:
        user_id: User identifier
        fallback_config: Config to use if baseline not calibrated
        
    Returns:
        CognitiveLoadConfig with personalized ranges
    """
    from app.services.cognitive_load import CognitiveLoadConfig, DEFAULT_CONFIG
    
    fallback = fallback_config or DEFAULT_CONFIG
    
    storage = get_baseline_storage()
    baseline = storage.get(user_id)
    
    if baseline is None or not baseline.is_calibrated:
        return fallback
    
    # Create personalized config based on user's baseline
    config = CognitiveLoadConfig(
        # Breathing ranges from baseline
        breathing_optimal_min=max(8, baseline.breathing.optimal_min),
        breathing_optimal_max=min(24, baseline.breathing.optimal_max),
        breathing_warning_min=max(6, baseline.breathing.warning_min),
        breathing_warning_max=min(28, baseline.breathing.warning_max),
        breathing_critical_max=min(30, baseline.breathing.warning_max + 2),
        
        # Pulse ranges from baseline
        pulse_optimal_min=max(40, baseline.pulse.optimal_min),
        pulse_optimal_max=min(120, baseline.pulse.optimal_max),
        pulse_warning_min=max(35, baseline.pulse.warning_min),
        pulse_warning_max=min(130, baseline.pulse.warning_max),
        pulse_critical_max=min(140, baseline.pulse.warning_max + 10),
        
        # Keep other settings from fallback
        hrv_min=fallback.hrv_min,
        hrv_max=fallback.hrv_max,
        hrv_multiplier=fallback.hrv_multiplier,
        weight_breathing=fallback.weight_breathing,
        weight_pulse=fallback.weight_pulse,
        weight_hrv=fallback.weight_hrv,
        stress_breathing_penalty=fallback.stress_breathing_penalty,
        stress_pulse_penalty=fallback.stress_pulse_penalty,
        max_cost_delta=fallback.max_cost_delta,
        hrv_min_samples=fallback.hrv_min_samples,
        hrv_default=baseline.hrv.mean if baseline.hrv.sample_count > 0 else fallback.hrv_default,
        hrv_rmssd_scale=fallback.hrv_rmssd_scale,
    )
    
    return config


def reset_baseline(user_id: str) -> bool:
    """
    Reset a user's baseline to start fresh calibration.
    
    Returns True if baseline existed and was deleted.
    """
    storage = get_baseline_storage()
    return storage.delete(user_id)


def get_baseline_summary(user_id: str) -> Optional[dict]:
    """
    Get a summary of user's baseline status.
    
    Returns None if no baseline exists.
    """
    storage = get_baseline_storage()
    baseline = storage.get(user_id)
    
    if baseline is None:
        return None
    
    return baseline.get_summary()
