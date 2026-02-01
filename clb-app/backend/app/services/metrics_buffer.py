"""
Metrics Buffer Service

This module provides a sliding-window buffer for aggregating real-time vital signs
metrics from the Presage daemon. It smooths out noise and provides stable readings
by averaging metrics over configurable time windows.
"""

from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Deque, Dict, List, Optional, Tuple
import statistics


@dataclass
class MetricReading:
    """A single metric reading from the daemon."""
    timestamp: datetime
    pulse_rate: float
    breathing_rate: float
    pulse_confidence: float = 0.0
    breathing_confidence: float = 0.0
    pulse_trace: List[Tuple[float, float]] = field(default_factory=list)
    breathing_amplitude: List[Tuple[float, float]] = field(default_factory=list)
    segment_index: Optional[int] = None
    realtime: bool = False


@dataclass
class AggregatedMetrics:
    """Aggregated metrics computed from buffered readings."""
    pulse_rate: float
    breathing_rate: float
    hrv: int  # Heart rate variability computed from pulse trace
    confidence: float
    reading_count: int
    buffer_duration_seconds: float
    is_stable: bool  # True if we have enough data for reliable metrics
    segment_index: Optional[int] = None
    
    def to_dict(self) -> Dict:
        """Convert to dictionary for JSON serialization."""
        return {
            "pulse_rate": round(self.pulse_rate, 1),
            "breathing_rate": round(self.breathing_rate, 1),
            "hrv": self.hrv,
            "confidence": round(self.confidence, 2),
            "reading_count": self.reading_count,
            "buffer_duration_seconds": round(self.buffer_duration_seconds, 1),
            "is_stable": self.is_stable,
            "segment_index": self.segment_index,
        }


class MetricsBuffer:
    """
    Buffers incoming daemon metrics and produces stable aggregated readings.
    
    Implements a sliding window for consistent output. The buffer accumulates
    readings and computes averages, discarding readings older than the window.
    
    Usage:
        buffer = MetricsBuffer(window_seconds=5.0, min_readings=2)
        buffer.add_reading({...})  # Add daemon metrics
        if buffer.is_stable():
            metrics = buffer.get_aggregated_metrics()
    """
    
    # Minimum viable readings for basic metrics
    MIN_READINGS_FOR_PULSE = 1
    MIN_READINGS_FOR_STABLE = 2
    
    # HRV calculation constants
    MIN_RR_INTERVALS_FOR_HRV = 5
    DEFAULT_HRV = 50  # Default when not enough data
    
    def __init__(
        self,
        window_seconds: float = 5.0,
        min_readings_for_stable: int = 2,
    ):
        """
        Initialize the metrics buffer.
        
        Args:
            window_seconds: Duration of the sliding window in seconds
            min_readings_for_stable: Minimum readings needed for stable output
        """
        self.window_seconds = window_seconds
        self.min_readings_for_stable = min_readings_for_stable
        self.readings: Deque[MetricReading] = deque()
        self._all_pulse_traces: List[Tuple[float, float]] = []
        self._latest_segment_index: Optional[int] = None
    
    def add_reading(self, metrics: Dict) -> None:
        """
        Add a new reading to the buffer.
        
        Args:
            metrics: Dictionary from daemon with pulse_rate, breathing_rate, etc.
        """
        # Parse reading from daemon format
        reading = MetricReading(
            timestamp=datetime.utcnow(),
            pulse_rate=float(metrics.get("pulse_rate", 0)),
            breathing_rate=float(metrics.get("breathing_rate", 0)),
            pulse_confidence=float(metrics.get("pulse_confidence", 0)),
            breathing_confidence=float(metrics.get("breathing_confidence", 0)),
            pulse_trace=metrics.get("pulse_trace", []),
            breathing_amplitude=metrics.get("breathing_amplitude", []),
            segment_index=metrics.get("segment_index"),
            realtime=metrics.get("realtime", False),
        )
        
        self.readings.append(reading)
        
        # Accumulate pulse trace data for HRV calculation
        if reading.pulse_trace:
            self._all_pulse_traces.extend(reading.pulse_trace)
            # Keep only recent trace points (last 30 seconds worth at ~30Hz)
            max_trace_points = 30 * 30
            if len(self._all_pulse_traces) > max_trace_points:
                self._all_pulse_traces = self._all_pulse_traces[-max_trace_points:]
        
        # Track latest segment
        if reading.segment_index is not None:
            self._latest_segment_index = reading.segment_index
        
        # Prune old readings
        self._prune_old_readings()
    
    def _prune_old_readings(self) -> None:
        """Remove readings older than the window duration."""
        cutoff = datetime.utcnow() - timedelta(seconds=self.window_seconds)
        while self.readings and self.readings[0].timestamp < cutoff:
            self.readings.popleft()
    
    def is_calibrating(self) -> bool:
        """True if buffer doesn't have enough data yet for any metrics."""
        return len(self.readings) < self.MIN_READINGS_FOR_PULSE
    
    def is_stable(self) -> bool:
        """True if buffer has enough data for stable, reliable metrics."""
        return len(self.readings) >= self.min_readings_for_stable
    
    def get_buffer_duration_seconds(self) -> float:
        """Get the actual time span of buffered readings."""
        if len(self.readings) < 2:
            return 0.0
        oldest = self.readings[0].timestamp
        newest = self.readings[-1].timestamp
        return (newest - oldest).total_seconds()
    
    def get_aggregated_metrics(self) -> Optional[AggregatedMetrics]:
        """
        Get stable aggregated metrics from buffered readings.
        
        Returns None if insufficient data for any metrics.
        """
        if self.is_calibrating():
            return None
        
        # Collect values for averaging
        pulse_rates = [r.pulse_rate for r in self.readings if r.pulse_rate > 0]
        breathing_rates = [r.breathing_rate for r in self.readings if r.breathing_rate > 0]
        confidences = [r.pulse_confidence for r in self.readings]
        
        # Compute averages
        avg_pulse = statistics.mean(pulse_rates) if pulse_rates else 0
        avg_breathing = statistics.mean(breathing_rates) if breathing_rates else 0
        avg_confidence = statistics.mean(confidences) if confidences else 0
        
        # Calculate HRV from accumulated pulse trace
        hrv = self._calculate_hrv_from_trace()
        
        return AggregatedMetrics(
            pulse_rate=avg_pulse,
            breathing_rate=avg_breathing,
            hrv=hrv,
            confidence=avg_confidence,
            reading_count=len(self.readings),
            buffer_duration_seconds=self.get_buffer_duration_seconds(),
            is_stable=self.is_stable(),
            segment_index=self._latest_segment_index,
        )
    
    def _calculate_hrv_from_trace(self) -> int:
        """
        Calculate HRV (RMSSD) from accumulated pulse trace data.
        
        The pulse trace is a PPG waveform where peaks correspond to heartbeats.
        We detect peaks to find RR intervals, then calculate RMSSD.
        """
        if len(self._all_pulse_traces) < 30:  # Need at least 1 second at 30Hz
            return self.DEFAULT_HRV
        
        # Extract just the values (ignore timestamps for simple peak detection)
        values = [point[1] for point in self._all_pulse_traces[-300:]]  # Last 10s
        
        # Simple peak detection
        peaks = self._detect_peaks(values)
        
        if len(peaks) < self.MIN_RR_INTERVALS_FOR_HRV + 1:
            return self.DEFAULT_HRV
        
        # Calculate RR intervals (in samples, assuming ~30Hz)
        rr_intervals = []
        for i in range(1, len(peaks)):
            rr_ms = (peaks[i] - peaks[i-1]) * (1000 / 30)  # Convert to milliseconds
            # Filter out physiologically implausible intervals
            if 300 < rr_ms < 2000:  # 30-200 BPM range
                rr_intervals.append(rr_ms)
        
        if len(rr_intervals) < self.MIN_RR_INTERVALS_FOR_HRV:
            return self.DEFAULT_HRV
        
        # Calculate RMSSD (Root Mean Square of Successive Differences)
        successive_diffs = [
            abs(rr_intervals[i+1] - rr_intervals[i])
            for i in range(len(rr_intervals) - 1)
        ]
        
        if not successive_diffs:
            return self.DEFAULT_HRV
        
        mean_squared = statistics.mean([d**2 for d in successive_diffs])
        rmssd = mean_squared ** 0.5
        
        # Clamp to reasonable range (20-150ms is typical for healthy adults)
        hrv = max(20, min(150, int(round(rmssd))))
        return hrv
    
    def _detect_peaks(self, values: List[float]) -> List[int]:
        """
        Simple peak detection for PPG waveform.
        
        Returns indices of detected peaks.
        """
        if len(values) < 5:
            return []
        
        # Apply simple smoothing
        smoothed = []
        window = 3
        for i in range(len(values)):
            start = max(0, i - window)
            end = min(len(values), i + window + 1)
            smoothed.append(sum(values[start:end]) / (end - start))
        
        # Find local maxima
        peaks = []
        min_distance = 15  # Minimum samples between peaks (~0.5s at 30Hz = 120 BPM max)
        
        for i in range(2, len(smoothed) - 2):
            # Check if this is a local maximum
            if (smoothed[i] > smoothed[i-1] and 
                smoothed[i] > smoothed[i+1] and
                smoothed[i] > smoothed[i-2] and 
                smoothed[i] > smoothed[i+2]):
                
                # Check minimum distance from last peak
                if not peaks or (i - peaks[-1]) >= min_distance:
                    peaks.append(i)
        
        return peaks
    
    def clear(self) -> None:
        """Clear all buffered readings."""
        self.readings.clear()
        self._all_pulse_traces.clear()
        self._latest_segment_index = None


# Global buffer instances per session
_buffers: Dict[str, MetricsBuffer] = {}


def get_session_buffer(session_id: str, create: bool = True) -> Optional[MetricsBuffer]:
    """
    Get or create a metrics buffer for a session.
    
    Args:
        session_id: The session identifier
        create: If True, create a new buffer if one doesn't exist
    
    Returns:
        The MetricsBuffer for the session, or None if not found and create=False
    """
    if session_id not in _buffers:
        if create:
            _buffers[session_id] = MetricsBuffer()
        else:
            return None
    return _buffers[session_id]


def remove_session_buffer(session_id: str) -> None:
    """Remove and clean up the buffer for a session."""
    if session_id in _buffers:
        _buffers[session_id].clear()
        del _buffers[session_id]


def get_active_buffer_count() -> int:
    """Get the number of active session buffers."""
    return len(_buffers)
