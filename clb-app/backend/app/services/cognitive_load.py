"""
Cognitive Load Calculation Service

This module provides cognitive load metrics calculation from vital signs
(pulse rate, breathing rate, HRV) captured by the Presage SmartSpectra SDK.

Outputs:
  - focus_score (0-100): Higher = better focus/calm state
  - stress_level (0-100): Higher = more stressed
  - cognitive_cost_delta (0-max_delta): Points to add to event cost

References:
  - Optimal resting pulse: 60-80 BPM (normal: 60-100)
  - Optimal resting breathing: 12-16 BPM (normal: 12-20)
  - HRV: Higher variability correlates with lower stress
"""

from dataclasses import dataclass, field
from datetime import datetime
from statistics import median
from typing import List, Optional

from app.models import PresageReading


# ============================================================================
# Configuration
# ============================================================================

@dataclass
class CognitiveLoadConfig:
    """Tunable parameters for cognitive load calculation."""
    
    # Breathing rate (BPM)
    breathing_optimal_min: float = 12.0
    breathing_optimal_max: float = 16.0
    breathing_warning_min: float = 10.0
    breathing_warning_max: float = 18.0
    breathing_critical_max: float = 20.0
    
    # Pulse rate (BPM)
    pulse_optimal_min: float = 60.0
    pulse_optimal_max: float = 80.0
    pulse_warning_min: float = 50.0
    pulse_warning_max: float = 90.0
    pulse_critical_max: float = 100.0
    
    # HRV scoring
    hrv_min: float = 20.0
    hrv_max: float = 80.0
    hrv_multiplier: float = 1.5
    
    # Focus score weights (must sum to 1.0)
    weight_breathing: float = 0.35
    weight_pulse: float = 0.25
    weight_hrv: float = 0.40
    
    # Stress penalties
    stress_breathing_penalty: float = 3.0  # per BPM over critical
    stress_pulse_penalty: float = 2.0  # per BPM over critical
    
    # Cognitive cost delta
    max_cost_delta: int = 6
    
    # HRV calculation
    hrv_min_samples: int = 5
    hrv_default: float = 50.0
    hrv_rmssd_scale: float = 2.0


# Default configuration
DEFAULT_CONFIG = CognitiveLoadConfig()


# ============================================================================
# Input Model
# ============================================================================

@dataclass
class VitalMetricsInput:
    """Input data for cognitive load calculation."""
    
    pulse_rate: float
    breathing_rate: float
    pulse_history: List[float] = field(default_factory=list)
    
    # Optional enhanced metrics (from full SDK)
    pulse_confidence: Optional[float] = None
    breathing_confidence: Optional[float] = None
    pulse_trace: Optional[List[tuple]] = None  # [(time, value), ...] - PPG signal
    breathing_amplitude: Optional[List[tuple]] = None  # [(time, value), ...] - breathing depth
    breathing_upper_trace: Optional[List[tuple]] = None  # [(time, value), ...] - chest movement
    blinking: Optional[bool] = None
    talking: Optional[bool] = None
    apnea_detected: Optional[bool] = None


@dataclass
class CognitiveLoadResult:
    """Output of cognitive load calculation."""
    
    hrv: int
    focus_score: int
    stress_level: int
    cognitive_cost_delta: int
    
    # Component scores for debugging/visualization
    breathing_score: float = 0.0
    pulse_score: float = 0.0
    hrv_score: float = 0.0
    
    # Confidence (0-1), lower if input had issues
    confidence: float = 1.0


# ============================================================================
# Core Calculation Functions
# ============================================================================

def calculate_hrv_from_pulse(
    pulse_history: List[float],
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> float:
    """
    Estimate HRV from pulse rate history using RMSSD-style approximation.
    
    Note: This is a rough approximation. True HRV requires RR intervals from
    the PPG pulse trace, which we can add when full SDK metrics are available.
    
    Args:
        pulse_history: List of recent pulse rate measurements (BPM)
        config: Configuration parameters
        
    Returns:
        Estimated HRV score (20-80 range)
    """
    if len(pulse_history) < config.hrv_min_samples:
        return config.hrv_default
    
    # Calculate successive differences (approximating RR interval variability)
    diffs_squared = []
    for i in range(1, len(pulse_history)):
        diff = pulse_history[i] - pulse_history[i - 1]
        diffs_squared.append(diff ** 2)
    
    if not diffs_squared:
        return config.hrv_default
    
    # RMSSD approximation
    rmssd = (sum(diffs_squared) / len(diffs_squared)) ** 0.5
    
    # Map to HRV score: lower variability in BPM = higher HRV score
    # (stable pulse rate indicates good HRV)
    hrv = config.hrv_default - (rmssd * config.hrv_rmssd_scale)
    hrv = max(config.hrv_min, min(config.hrv_max, hrv))
    
    return round(hrv)


def calculate_hrv_from_trace(
    pulse_trace: List[tuple],
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> float:
    """
    Calculate HRV from PPG pulse trace using peak detection and RMSSD.
    
    This extracts RR intervals from the raw PPG signal by detecting peaks,
    computes RMSSD (Root Mean Square of Successive Differences) in milliseconds,
    then maps to a 0-100 HRV score.
    
    Args:
        pulse_trace: List of (time_seconds, ppg_value) tuples from PPG signal
        config: Configuration parameters
        
    Returns:
        HRV score (20-80 range)
    """
    if len(pulse_trace) < 10:
        return config.hrv_default
    
    # Extract times and values
    times = [p[0] for p in pulse_trace]
    values = [p[1] for p in pulse_trace]
    
    # Simple peak detection: find local maxima
    # A peak is where value[i] > value[i-1] and value[i] > value[i+1]
    peaks = []
    for i in range(1, len(values) - 1):
        if values[i] > values[i - 1] and values[i] > values[i + 1]:
            # Additional check: peak must be above mean (to filter noise)
            if values[i] > sum(values) / len(values):
                peaks.append(i)
    
    if len(peaks) < 3:
        return config.hrv_default
    
    # Calculate RR intervals (time between successive peaks) in milliseconds
    rr_intervals = []
    for i in range(1, len(peaks)):
        rr_ms = (times[peaks[i]] - times[peaks[i - 1]]) * 1000  # Convert to ms
        # Filter unrealistic intervals (300ms to 2000ms = 30-200 BPM)
        if 300 <= rr_ms <= 2000:
            rr_intervals.append(rr_ms)
    
    if len(rr_intervals) < 2:
        return config.hrv_default
    
    # Calculate RMSSD (Root Mean Square of Successive Differences)
    successive_diffs_squared = []
    for i in range(1, len(rr_intervals)):
        diff = rr_intervals[i] - rr_intervals[i - 1]
        successive_diffs_squared.append(diff ** 2)
    
    if not successive_diffs_squared:
        return config.hrv_default
    
    rmssd = (sum(successive_diffs_squared) / len(successive_diffs_squared)) ** 0.5
    
    # Map RMSSD to HRV score (0-100)
    # Normal RMSSD range: 20-100ms for healthy adults
    # Higher RMSSD = higher HRV = better parasympathetic tone
    # Mapping: RMSSD 20ms -> HRV 20, RMSSD 100ms -> HRV 80
    hrv_score = config.hrv_min + (rmssd - 20) * (config.hrv_max - config.hrv_min) / 80
    hrv_score = max(config.hrv_min, min(config.hrv_max, hrv_score))
    
    return round(hrv_score)


def calculate_breathing_score(
    breathing_rate: float,
    breathing_confidence: Optional[float] = None,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> float:
    """
    Calculate breathing component score (0-100).
    
    Optimal: 12-16 BPM (deep, relaxed breathing)
    Warning: 10-12 or 16-18 BPM
    Poor: <10 or >18 BPM
    """
    score = 100.0
    
    if breathing_rate < config.breathing_warning_min:
        # Too slow (unusual, possible measurement error)
        penalty = (config.breathing_warning_min - breathing_rate) * 10
        score -= penalty
    elif breathing_rate > config.breathing_warning_max:
        # Rapid breathing (stress indicator)
        penalty = (breathing_rate - config.breathing_warning_max) * 8
        score -= penalty
    elif breathing_rate > config.breathing_optimal_max:
        # Slightly elevated
        penalty = (breathing_rate - config.breathing_optimal_max) * 3
        score -= penalty
    # Optimal range: no penalty
    
    # Apply confidence scaling if available
    if breathing_confidence is not None:
        score *= breathing_confidence
    
    return max(0.0, min(100.0, score))


def calculate_pulse_score(
    pulse_rate: float,
    pulse_confidence: Optional[float] = None,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> float:
    """
    Calculate pulse component score (0-100).
    
    Optimal: 60-80 BPM (calm, resting)
    Warning: 50-60 or 80-90 BPM
    Poor: <50 (bradycardia) or >90 (elevated)
    """
    score = 100.0
    
    if pulse_rate < config.pulse_warning_min:
        # Bradycardia
        penalty = (config.pulse_warning_min - pulse_rate) * 2
        score -= penalty
    elif pulse_rate > config.pulse_warning_max:
        # Elevated (stress/exertion)
        penalty = (pulse_rate - config.pulse_warning_max) * 2
        score -= penalty
    elif pulse_rate > config.pulse_optimal_max:
        # Slightly elevated
        penalty = (pulse_rate - config.pulse_optimal_max) * 1
        score -= penalty
    # Optimal range: no penalty
    
    # Apply confidence scaling if available
    if pulse_confidence is not None:
        score *= pulse_confidence
    
    return max(0.0, min(100.0, score))


def calculate_hrv_score(
    hrv: float,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> float:
    """
    Calculate HRV component score (0-100).
    
    Higher HRV generally indicates better parasympathetic tone (relaxation).
    """
    score = hrv * config.hrv_multiplier
    return max(0.0, min(100.0, score))


def calculate_focus_score(
    breathing_score: float,
    pulse_score: float,
    hrv_score: float,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> int:
    """
    Calculate combined focus score from component scores.
    
    Weighted combination:
      - Breathing: 35% (most direct indicator of mental state)
      - Pulse: 25% (affected by many factors)
      - HRV: 40% (best indicator of stress/recovery balance)
    """
    focus = (
        breathing_score * config.weight_breathing +
        pulse_score * config.weight_pulse +
        hrv_score * config.weight_hrv
    )
    return int(max(0, min(100, focus)))


def calculate_stress_level(
    focus_score: int,
    pulse_rate: float,
    breathing_rate: float,
    apnea_detected: Optional[bool] = None,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> int:
    """
    Calculate stress level from focus score and vital signs.
    
    Base stress is inverse of focus, with additional penalties for:
      - Very rapid breathing (>20 BPM)
      - Very elevated pulse (>100 BPM)
      - Apnea events (if detected)
    """
    stress = 100 - focus_score
    
    # Penalty for critical breathing rate
    if breathing_rate > config.breathing_critical_max:
        stress += (breathing_rate - config.breathing_critical_max) * config.stress_breathing_penalty
    
    # Penalty for critical pulse rate
    if pulse_rate > config.pulse_critical_max:
        stress += (pulse_rate - config.pulse_critical_max) * config.stress_pulse_penalty
    
    # Penalty for apnea
    if apnea_detected:
        stress += 15
    
    return int(max(0, min(100, stress)))


def calculate_cognitive_cost_delta(
    stress_level: int,
    max_delta: int = DEFAULT_CONFIG.max_cost_delta
) -> float:
    """
    Calculate cognitive cost adjustment based on stress level.
    
    Maps stress (0-100) to cost delta (0-max_delta).
    Higher stress = higher cost added to event.
    """
    return (stress_level / 100) * max_delta


# ============================================================================
# Main Calculation Entry Point
# ============================================================================

def calculate_cognitive_load(
    metrics: VitalMetricsInput,
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> CognitiveLoadResult:
    """
    Calculate cognitive load from vital signs metrics.
    
    This is the main entry point that combines all component calculations.
    
    Args:
        metrics: Input vital signs data
        config: Configuration parameters
        
    Returns:
        CognitiveLoadResult with all computed metrics
    """
    # Calculate HRV (prefer trace if available, fall back to pulse history)
    if metrics.pulse_trace:
        hrv = calculate_hrv_from_trace(metrics.pulse_trace, config)
    else:
        hrv = calculate_hrv_from_pulse(metrics.pulse_history, config)
    
    # Calculate component scores
    breathing_score = calculate_breathing_score(
        metrics.breathing_rate,
        metrics.breathing_confidence,
        config
    )
    pulse_score = calculate_pulse_score(
        metrics.pulse_rate,
        metrics.pulse_confidence,
        config
    )
    hrv_score = calculate_hrv_score(hrv, config)
    
    # Calculate focus score
    focus_score = calculate_focus_score(
        breathing_score, pulse_score, hrv_score, config
    )
    
    # Calculate stress level
    stress_level = calculate_stress_level(
        focus_score,
        metrics.pulse_rate,
        metrics.breathing_rate,
        metrics.apnea_detected,
        config
    )
    
    # Calculate cost delta
    cognitive_cost_delta = calculate_cognitive_cost_delta(
        stress_level, config.max_cost_delta
    )
    
    # Determine confidence based on input quality
    confidence = 1.0
    if metrics.pulse_confidence is not None:
        confidence = min(confidence, metrics.pulse_confidence)
    if metrics.breathing_confidence is not None:
        confidence = min(confidence, metrics.breathing_confidence)
    if len(metrics.pulse_history) < config.hrv_min_samples:
        confidence *= 0.8  # Lower confidence with limited history
    
    return CognitiveLoadResult(
        hrv=int(hrv),
        focus_score=focus_score,
        stress_level=stress_level,
        cognitive_cost_delta=cognitive_cost_delta,
        breathing_score=breathing_score,
        pulse_score=pulse_score,
        hrv_score=hrv_score,
        confidence=confidence,
    )


def calculate_cognitive_load_personalized(
    metrics: VitalMetricsInput,
    user_id: str,
    learn_baseline: bool = False,
    fallback_config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> CognitiveLoadResult:
    """
    Calculate cognitive load using personalized baseline for a user.
    
    This function:
    1. Gets or creates the user's baseline
    2. Optionally learns from the current reading
    3. Uses personalized config if baseline is calibrated
    4. Falls back to population norms if not calibrated
    
    Args:
        metrics: Input vital signs data
        user_id: User identifier for baseline lookup
        learn_baseline: Whether to add this reading to baseline learning
        fallback_config: Config to use if baseline not calibrated
        
    Returns:
        CognitiveLoadResult with all computed metrics
    """
    from app.services.user_baseline import (
        get_personalized_config,
        learn_from_reading,
    )
    
    # Optionally learn from this reading
    if learn_baseline and metrics.pulse_rate > 0:
        # Calculate HRV for baseline learning
        if metrics.pulse_trace:
            hrv = calculate_hrv_from_trace(metrics.pulse_trace, fallback_config)
        else:
            hrv = calculate_hrv_from_pulse(metrics.pulse_history, fallback_config)
        
        learn_from_reading(
            user_id=user_id,
            pulse_rate=metrics.pulse_rate,
            breathing_rate=metrics.breathing_rate,
            hrv=hrv
        )
    
    # Get personalized config (uses baseline if calibrated)
    config = get_personalized_config(user_id, fallback_config)
    
    # Calculate cognitive load with personalized config
    return calculate_cognitive_load(metrics, config)


# ============================================================================
# Session Aggregation
# ============================================================================

def aggregate_session_delta(
    readings: List[PresageReading],
    method: str = "median"
) -> float:
    """
    Aggregate cognitive cost deltas from a session's readings.
    
    Using median or percentile reduces impact of outliers (e.g., momentary
    stress spikes that don't represent the overall session).
    
    Args:
        readings: List of PresageReading from a session
        method: Aggregation method - "mean", "median", or "p90"
        
    Returns:
        Aggregated cognitive cost delta
    """
    if not readings:
        return 0.0
    
    deltas = [r.cognitive_cost_delta for r in readings]
    
    if method == "mean":
        return sum(deltas) / len(deltas)
    elif method == "median":
        return float(median(deltas))
    elif method == "p90":
        # 90th percentile - captures sustained high stress
        sorted_deltas = sorted(deltas)
        idx = int(len(sorted_deltas) * 0.9)
        return float(sorted_deltas[min(idx, len(sorted_deltas) - 1)])
    else:
        # Default to median
        return float(median(deltas))


def aggregate_session_metrics(
    readings: List[PresageReading]
) -> dict:
    """
    Compute summary statistics for a session's readings.
    
    Useful for end-of-session reports.
    """
    if not readings:
        return {
            "count": 0,
            "avg_focus": 0,
            "avg_stress": 0,
            "avg_hrv": 0,
            "total_cost_delta": 0,
        }
    
    return {
        "count": len(readings),
        "avg_focus": round(sum(r.focus_score for r in readings) / len(readings)),
        "avg_stress": round(sum(r.stress_level for r in readings) / len(readings)),
        "avg_hrv": round(sum(r.hrv for r in readings) / len(readings)),
        "total_cost_delta": aggregate_session_delta(readings, method="median"),
        "min_focus": min(r.focus_score for r in readings),
        "max_stress": max(r.stress_level for r in readings),
    }


# ============================================================================
# Convenience Functions
# ============================================================================

def metrics_to_reading(
    metrics: dict,
    pulse_history: List[float],
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> PresageReading:
    """
    Convert raw daemon metrics dict to PresageReading model.
    
    This is the bridge between raw Presage daemon output and the app's
    PresageReading model. Supports extended Phase 2 metrics.
    """
    # Parse pulse_trace from daemon (list of [time, value] pairs)
    raw_trace = metrics.get("pulse_trace", [])
    pulse_trace = [(p[0], p[1]) for p in raw_trace] if raw_trace else None
    
    # Parse breathing_amplitude from daemon (list of [time, value] pairs)
    raw_amplitude = metrics.get("breathing_amplitude", [])
    breathing_amplitude = [(a[0], a[1]) for a in raw_amplitude] if raw_amplitude else None
    
    # Parse breathing_upper_trace from daemon (list of [time, value] pairs)
    raw_upper_trace = metrics.get("breathing_upper_trace", [])
    breathing_upper_trace = [(t[0], t[1]) for t in raw_upper_trace] if raw_upper_trace else None
    
    # Build input from raw metrics
    vital_input = VitalMetricsInput(
        pulse_rate=metrics.get("pulse_rate", 70),
        breathing_rate=metrics.get("breathing_rate", 15),
        pulse_history=list(pulse_history),
        pulse_confidence=metrics.get("pulse_confidence"),
        breathing_confidence=metrics.get("breathing_confidence"),
        pulse_trace=pulse_trace,
        breathing_amplitude=breathing_amplitude,
        breathing_upper_trace=breathing_upper_trace,
        blinking=metrics.get("blinking"),
        talking=metrics.get("talking"),
        apnea_detected=metrics.get("apnea_detected"),
    )
    
    # Calculate cognitive load
    result = calculate_cognitive_load(vital_input, config)
    
    # Return as PresageReading
    return PresageReading(
        pulse_rate=float(vital_input.pulse_rate),
        hrv=result.hrv,
        breathing_rate=int(vital_input.breathing_rate),
        focus_score=result.focus_score,
        stress_level=result.stress_level,
        timestamp=datetime.utcnow(),
        cognitive_cost_delta=result.cognitive_cost_delta,
    )


def calculate_focus_from_vitals(
    pulse_rate: float,
    breathing_rate: float,
    pulse_history: List[float],
    config: CognitiveLoadConfig = DEFAULT_CONFIG
) -> dict:
    """
    Simplified function matching the old calculate_focus_metrics signature.
    
    For backward compatibility with existing code.
    """
    vital_input = VitalMetricsInput(
        pulse_rate=pulse_rate,
        breathing_rate=breathing_rate,
        pulse_history=pulse_history,
    )
    
    result = calculate_cognitive_load(vital_input, config)
    
    return {
        "hrv": result.hrv,
        "focus_score": result.focus_score,
        "stress_level": result.stress_level,
    }
