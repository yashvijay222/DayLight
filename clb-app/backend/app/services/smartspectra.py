import json
import os
import subprocess
import time
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


def _get_env_path(name: str, default: Optional[str] = None) -> Optional[str]:
    value = os.getenv(name, default)
    if not value:
        return None
    return value


def _find_latest_metrics(output_dir: Path) -> Optional[Path]:
    candidates = sorted(output_dir.glob("metrics_*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    return candidates[0] if candidates else None


def _extract_latest_value(series: Any) -> Optional[float]:
    if isinstance(series, list) and series:
        last = series[-1]
        if isinstance(last, dict) and "value" in last:
            return float(last["value"])
    if isinstance(series, dict) and series:
        # Map-style series keyed by time
        try:
            last_key = sorted(series.keys(), key=lambda k: float(k))[-1]
            value = series[last_key]
            if isinstance(value, dict) and "value" in value:
                return float(value["value"])
        except (ValueError, TypeError):
            return None
    return None


def _extract_rate(metrics: Dict[str, Any], key: str) -> Optional[float]:
    if key not in metrics:
        return None
    block = metrics.get(key) or {}
    # Prefer rate array if present
    rate = _extract_latest_value(block.get("rate"))
    if rate is not None:
        return rate
    # Fallback to strict value if present
    strict = block.get("strict")
    if isinstance(strict, dict) and "value" in strict:
        return float(strict["value"])
    return None


def run_spot_capture(
    api_key: str,
    duration_seconds: float = 30.0,
    camera_device_index: int = 0,
    output_directory: Optional[str] = None,
) -> Tuple[Dict[str, Any], Dict[str, Any]]:
    """
    Run SmartSpectra REST Spot capture and return raw metrics and derived vitals.
    Requires SMARTSPECTRA_BIN to be set to the built rest_spot_example binary.
    """
    binary = _get_env_path("SMARTSPECTRA_BIN")
    if not binary:
        raise RuntimeError("SMARTSPECTRA_BIN is not set.")

    output_dir = Path(output_directory or _get_env_path("SMARTSPECTRA_OUTPUT_DIR", "smartspectra_output"))
    output_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        binary,
        "--also_log_to_stderr",
        f"--camera_device_index={camera_device_index}",
        f"--spot_duration={duration_seconds}",
        "--save_metrics_to_disk=true",
        f"--output_directory={str(output_dir)}",
        f"--api_key={api_key}",
    ]

    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError(f"SmartSpectra failed: {result.stderr or result.stdout}")

    # Give filesystem a moment in case writes lag slightly
    time.sleep(0.5)

    metrics_path = _find_latest_metrics(output_dir)
    if not metrics_path:
        raise RuntimeError("No metrics JSON file produced.")

    raw = json.loads(metrics_path.read_text())

    # Extract pulse/breathing rates
    pulse_rate = _extract_rate(raw, "pulse")
    breathing_rate = _extract_rate(raw, "breathing") or _extract_rate(raw, "breath")

    # Basic derived values (heuristic)
    heart_rate = round(pulse_rate) if pulse_rate is not None else None
    breathing = round(breathing_rate) if breathing_rate is not None else None
    stress_level = min(100, max(0, int((heart_rate or 70) * 0.7)))
    focus_score = max(0, 100 - stress_level)
    cognitive_cost_delta = max(0, min(6, int((stress_level / 100) * 6)))

    vitals = {
        "heart_rate": heart_rate,
        "breathing_rate": breathing,
        "stress_level": stress_level,
        "focus_score": focus_score,
        "cognitive_cost_delta": cognitive_cost_delta,
        "metrics_path": str(metrics_path),
    }

    return raw, vitals
