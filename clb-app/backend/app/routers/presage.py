"""
Presage Router - SmartSpectra Vital Signs Integration

This module handles communication between the frontend and the Presage
container for vital signs detection. Video frames come from the frontend,
get forwarded to the Presage container, and metrics are sent back.

Architecture:
  Frontend (WebSocket) -> Backend -> Presage Container (TCP)
  Frontend <- Backend (WebSocket) <- Presage Container (TCP)
"""

import asyncio
import base64
import json
import logging
import os
import random
import socket
import struct
from collections import deque
from datetime import datetime
from typing import Optional
from uuid import uuid4

from fastapi import APIRouter, Request, WebSocket, WebSocketDisconnect

from app.models import PresageReading, SageSession
from app.services.cognitive_calculator import calculate_event_cost
from app.services.cognitive_load import (
    VitalMetricsInput,
    calculate_cognitive_load_personalized,
    aggregate_session_delta,
)
from app.services.user_baseline import (
    learn_from_session,
    get_baseline_summary,
)
from app.services.metrics_buffer import (
    get_session_buffer,
    remove_session_buffer,
)

router = APIRouter()
logger = logging.getLogger(__name__)

DEFAULT_VIDEO_FPS = int(os.getenv("PRESAGE_VIDEO_FPS", "30"))
DEFAULT_VIDEO_WIDTH = 1280
DEFAULT_VIDEO_HEIGHT = 720


def _parse_time_series(raw_values: Optional[list]) -> Optional[list[tuple]]:
    """Parse list of [time, value] pairs into tuples."""
    if not raw_values:
        return None
    try:
        return [(item[0], item[1]) for item in raw_values]
    except (TypeError, IndexError):
        return None


def _build_vital_input(metrics: dict, pulse_history: deque) -> VitalMetricsInput:
    """Build VitalMetricsInput from raw daemon metrics."""
    return VitalMetricsInput(
        pulse_rate=metrics.get("pulse_rate", 70),
        breathing_rate=metrics.get("breathing_rate", 15),
        pulse_history=list(pulse_history),
        pulse_confidence=metrics.get("pulse_confidence"),
        breathing_confidence=metrics.get("breathing_confidence"),
        pulse_trace=_parse_time_series(metrics.get("pulse_trace")),
        breathing_amplitude=_parse_time_series(metrics.get("breathing_amplitude")),
        breathing_upper_trace=_parse_time_series(metrics.get("breathing_upper_trace")),
        blinking=metrics.get("blinking"),
        talking=metrics.get("talking"),
        apnea_detected=metrics.get("apnea_detected"),
    )


# ============================================================================
# Presage Connection Client
# ============================================================================

class PresageClient:
    """Client for communicating with the Presage C++ daemon via TCP."""
    
    def __init__(self):
        self.metrics_host = os.getenv("PRESAGE_DAEMON_HOST", "presage")
        self.metrics_port = int(os.getenv("PRESAGE_DAEMON_PORT", "9002"))
        self.video_port = int(os.getenv("PRESAGE_VIDEO_PORT", "9001"))
        
        self.metrics_socket: Optional[socket.socket] = None
        self.video_socket: Optional[socket.socket] = None
        self.connected = False
        self.buffer = ""
        
        # Metrics history for calculations
        self.pulse_history: deque = deque(maxlen=60)
        self.breathing_history: deque = deque(maxlen=60)
        self.latest_metrics: Optional[dict] = None
        
    def connect(self) -> bool:
        """Connect to the Presage daemon for metrics."""
        try:
            # Close existing socket if any
            if self.metrics_socket:
                try:
                    self.metrics_socket.close()
                except Exception:
                    pass
                self.metrics_socket = None
            
            # Connect to metrics port
            self.metrics_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.metrics_socket.settimeout(10.0)
            self.metrics_socket.connect((self.metrics_host, self.metrics_port))
            self.metrics_socket.setblocking(False)
            
            # Set TCP keepalive to detect broken connections
            self.metrics_socket.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
            
            self.connected = True
            logger.info(f"Connected to Presage daemon at {self.metrics_host}:{self.metrics_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Presage daemon: {e}")
            self.connected = False
            return False
    
    def connect_video(self) -> bool:
        """Connect to the Presage daemon for video input."""
        try:
            self.video_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.video_socket.settimeout(10.0)
            self.video_socket.connect((self.metrics_host, self.video_port))
            logger.info(f"Connected to Presage video input at {self.metrics_host}:{self.video_port}")
            return True
        except Exception as e:
            logger.error(f"Failed to connect to Presage video input: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from the daemon."""
        if self.metrics_socket:
            try:
                self.metrics_socket.close()
            except Exception:
                pass
            self.metrics_socket = None
            
        if self.video_socket:
            try:
                self.video_socket.close()
            except Exception:
                pass
            self.video_socket = None
            
        self.connected = False
        logger.info("Disconnected from Presage daemon")
    
    def send_frame(self, jpeg_data: bytes) -> bool:
        """Send a video frame to the Presage daemon."""
        if not self.video_socket:
            if not self.connect_video():
                return False
        
        try:
            # Send frame length (4 bytes, big-endian) followed by frame data
            frame_length = len(jpeg_data)
            header = struct.pack(">I", frame_length)
            self.video_socket.sendall(header + jpeg_data)
            return True
        except Exception as e:
            logger.error(f"Failed to send frame: {e}")
            self.video_socket = None
            return False
    
    def send_control_message(self, message: dict) -> bool:
        """
        Send a JSON control message to the Presage daemon over the video socket.
        
        Control messages are sent as JSON strings with a length prefix,
        similar to frames but with JSON content that starts with '{'.
        """
        if not self.video_socket:
            if not self.connect_video():
                return False
        
        try:
            # Serialize message to JSON
            json_str = json.dumps(message)
            json_bytes = json_str.encode('utf-8')
            
            # Send length (4 bytes, big-endian) followed by JSON data
            msg_length = len(json_bytes)
            header = struct.pack(">I", msg_length)
            self.video_socket.sendall(header + json_bytes)
            
            logger.info(f"Sent control message: {message.get('type')}")
            return True
        except Exception as e:
            logger.error(f"Failed to send control message: {e}")
            self.video_socket = None
            return False
    
    def start_session(
        self, 
        session_id: str, 
        fps: int = 30, 
        width: int = 1280, 
        height: int = 720
    ) -> bool:
        """
        Send session_start control message to the Presage daemon.
        
        This tells the daemon to start recording frames for this session.
        The recorded video will be processed by the SDK when the session ends.
        
        Args:
            session_id: Unique identifier for this session
            fps: Frame rate for video recording (default 30)
            width: Video width in pixels (default 1280)
            height: Video height in pixels (default 720)
            
        Returns:
            True if message sent successfully, False otherwise
        """
        message = {
            "type": "session_start",
            "session_id": session_id,
            "fps": fps,
            "width": width,
            "height": height,
        }
        
        success = self.send_control_message(message)
        if success:
            self._current_session_id = session_id
            logger.info(f"Started recording session: {session_id}")
        return success
    
    def end_session(self, session_id: str) -> bool:
        """
        Send session_end control message to the Presage daemon.
        
        This tells the daemon to stop recording and process the video
        through the SmartSpectra SDK. Metrics will be emitted via the
        metrics TCP channel after processing completes.
        
        Args:
            session_id: Unique identifier for the session to end
            
        Returns:
            True if message sent successfully, False otherwise
        """
        message = {
            "type": "session_end",
            "session_id": session_id,
        }
        
        success = self.send_control_message(message)
        if success:
            self._current_session_id = None
            logger.info(f"Ended recording session: {session_id}")
        return success
    
    @property
    def current_session_id(self) -> Optional[str]:
        """Get the current active session ID, if any."""
        return getattr(self, '_current_session_id', None)
    
    def read_metrics(self) -> list[dict]:
        """Read available metrics from the daemon (non-blocking)."""
        if not self.connected or not self.metrics_socket:
            return []
        
        metrics = []
        try:
            data = self.metrics_socket.recv(4096)
            if data:
                self.buffer += data.decode('utf-8')
                logger.debug(f"Received {len(data)} bytes from daemon")
                
                # Parse newline-delimited JSON messages
                while '\n' in self.buffer:
                    line, self.buffer = self.buffer.split('\n', 1)
                    if line.strip():
                        try:
                            msg = json.loads(line)
                            metrics.append(msg)
                            
                            # Log received metrics for debugging
                            msg_type = msg.get("type", "unknown")
                            if msg_type == "metrics":
                                logger.info(f"Received core metrics: pulse={msg.get('pulse_rate')}, breathing={msg.get('breathing_rate')}")
                            elif msg_type == "edge_metrics":
                                logger.debug(f"Received edge metrics with {len(msg.get('breathing_upper_trace', []))} breathing points")
                            
                            # Update history for metrics messages
                            if msg.get("type") == "metrics":
                                if "pulse_rate" in msg:
                                    self.pulse_history.append(msg["pulse_rate"])
                                if "breathing_rate" in msg:
                                    self.breathing_history.append(msg["breathing_rate"])
                                self.latest_metrics = msg
                                
                        except json.JSONDecodeError:
                            logger.warning(f"Invalid JSON from daemon: {line[:100]}")
                            
        except BlockingIOError:
            pass  # No data available, this is normal
        except ConnectionResetError:
            logger.warning("Connection reset by daemon - will reconnect")
            self.connected = False
        except BrokenPipeError:
            logger.warning("Broken pipe to daemon - will reconnect")
            self.connected = False
        except Exception as e:
            logger.error(f"Error reading from daemon: {type(e).__name__}: {e}")
            self.connected = False
            
        return metrics


# Global client instance
_presage_client: Optional[PresageClient] = None
_websocket_clients: set[WebSocket] = set()


def get_presage_client() -> PresageClient:
    """Get or create the Presage client singleton."""
    global _presage_client
    if _presage_client is None:
        _presage_client = PresageClient()
    return _presage_client


# ============================================================================
# Simulation Fallback
# ============================================================================

def _simulate_reading() -> PresageReading:
    """Generate simulated reading for testing without hardware."""
    hrv = random.randint(40, 80)
    breathing_rate = random.randint(12, 20)
    pulse_rate = random.randint(55, 95)
    focus_score = random.randint(60, 95)
    stress_level = random.randint(20, 90)
    # Use cognitive_load service for consistency
    from app.services.cognitive_load import calculate_cognitive_cost_delta
    cognitive_delta = calculate_cognitive_cost_delta(stress_level)
    return PresageReading(
        pulse_rate=pulse_rate,
        hrv=hrv,
        breathing_rate=breathing_rate,
        focus_score=focus_score,
        stress_level=stress_level,
        timestamp=datetime.utcnow(),
        cognitive_cost_delta=cognitive_delta,
    )


# ============================================================================
# API Endpoints - Connection Status
# ============================================================================

@router.get("/presage/status")
async def presage_status() -> dict:
    """Get the status of the Presage daemon connection."""
    client = get_presage_client()
    
    return {
        "daemon_host": client.metrics_host,
        "metrics_port": client.metrics_port,
        "video_port": client.video_port,
        "connected": client.connected,
        "latest_metrics": client.latest_metrics,
        "pulse_history_size": len(client.pulse_history),
        "breathing_history_size": len(client.breathing_history),
    }


@router.post("/presage/connect")
async def connect_to_presage() -> dict:
    """Connect to the Presage daemon."""
    client = get_presage_client()
    
    if client.connected:
        return {"status": "already_connected"}
    
    if client.connect():
        return {"status": "connected"}
    else:
        return {"status": "error", "message": "Failed to connect to Presage daemon"}


@router.post("/presage/disconnect")
async def disconnect_from_presage() -> dict:
    """Disconnect from the Presage daemon."""
    client = get_presage_client()
    client.disconnect()
    return {"status": "disconnected"}


# ============================================================================
# API Endpoints - Sage Sessions
# ============================================================================

@router.post("/presage/start-sage")
def start_sage(request: Request, payload: dict) -> dict:
    """
    Start a Sage monitoring session.
    
    Payload:
        event_id: Optional event to associate with session
        user_id: Optional user ID for personalized baseline learning
        video_fps: Optional video frame rate (default 30)
        video_width: Optional video width (default 1280)
        video_height: Optional video height (default 720)
    """
    event_id = payload.get("event_id")
    user_id = payload.get("user_id", "default")  # Default user if not specified
    
    # Video recording parameters
    video_fps = payload.get("video_fps", DEFAULT_VIDEO_FPS)
    video_width = payload.get("video_width", DEFAULT_VIDEO_WIDTH)
    video_height = payload.get("video_height", DEFAULT_VIDEO_HEIGHT)
    
    estimated_cost = 0
    for event in request.app.state.events:
        if event.id == event_id:
            estimated_cost = calculate_event_cost(event)
            break
    
    session = SageSession(
        session_id=str(uuid4()),
        event_id=event_id,
        start_time=datetime.utcnow(),
        estimated_cost=estimated_cost,
    )
    
    # Store user_id with session for baseline learning
    request.app.state.sage_sessions[session.session_id] = {
        "session": session,
        "user_id": user_id,
    }
    
    # Send session_start control message to the Presage daemon
    # This tells the daemon to start recording video frames
    client = get_presage_client()
    recording_started = client.start_session(
        session_id=session.session_id,
        fps=video_fps,
        width=video_width,
        height=video_height,
    )
    
    # Get baseline status for response
    baseline_summary = get_baseline_summary(user_id)
    
    return {
        "status": "started",
        "session_id": session.session_id,
        "user_id": user_id,
        "baseline_calibrated": baseline_summary["is_calibrated"] if baseline_summary else False,
        "baseline_progress": baseline_summary["calibration_progress"] if baseline_summary else 0,
        "recording_started": recording_started,
    }


@router.get("/presage/reading")
def get_reading(request: Request) -> dict:
    """
    Get current reading for a session.
    
    Uses personalized baseline if available for the session's user.
    Baseline learning is finalized when the session ends.
    """
    session_id = request.query_params.get("session_id")
    session_data = request.app.state.sage_sessions.get(session_id)
    if not session_data:
        return {"status": "not_found"}
    
    session = session_data["session"]
    user_id = session_data.get("user_id", "default")
    
    client = get_presage_client()
    if client.connected and client.latest_metrics:
        vital_input = _build_vital_input(client.latest_metrics, client.pulse_history)
        
        # Use personalized calculation (uses baseline if calibrated)
        cognitive = calculate_cognitive_load_personalized(
            vital_input,
            user_id=user_id
        )
        
        reading = PresageReading(
            pulse_rate=float(vital_input.pulse_rate),
            hrv=cognitive.hrv,
            breathing_rate=int(vital_input.breathing_rate),
            focus_score=cognitive.focus_score,
            stress_level=cognitive.stress_level,
            timestamp=datetime.utcnow(),
            cognitive_cost_delta=cognitive.cognitive_cost_delta,
        )
    else:
        reading = _simulate_reading()
    
    session.readings.append(reading)
    return {"status": "ok", "reading": reading}


@router.post("/presage/end-sage")
def end_sage(request: Request, payload: dict) -> dict:
    """
    End a Sage monitoring session.
    
    Sends session_end control message to the Presage daemon to stop recording
    and trigger SDK processing. Completes baseline learning for the session
    and calculates final costs.
    
    Note: After ending a session, the SDK will process the recorded video
    in the background. Metrics will be emitted via the metrics channel
    with the session_id once processing completes.
    """
    session_id = payload.get("session_id")
    session_data = request.app.state.sage_sessions.get(session_id)
    if not session_data:
        return {"status": "not_found"}
    
    session = session_data["session"]
    user_id = session_data.get("user_id", "default")
    
    # Send session_end control message to the Presage daemon
    # This tells the daemon to stop recording and process the video with the SDK
    client = get_presage_client()
    recording_ended = client.end_session(session_id)
    
    # Complete the session for baseline learning
    baseline = learn_from_session(user_id, session.readings, complete_session=True)
    
    # Use aggregate_session_delta from cognitive_load service
    # This uses median instead of mean for better outlier handling
    avg_delta = aggregate_session_delta(session.readings, method="median")
    
    session.actual_cost = session.estimated_cost + avg_delta
    session.debt_adjustment = session.actual_cost - session.estimated_cost
    
    # Calculate hourly projection (4 is base points for 60 min regular session)
    session.hourly_projection = 4 + avg_delta
    
    if session.event_id:
        for event in request.app.state.events:
            if event.id == session.event_id:
                event.actual_cost = session.actual_cost
                break
    else:
        # For standalone sessions (no event), record the cost impact for today's budget
        today_str = datetime.utcnow().strftime("%Y-%m-%d")
        # Use actual_cost if it was a standalone session (estimated_cost was 0)
        # equivalently use debt_adjustment.
        request.app.state.daily_session_costs.append({
            "date": today_str,
            "amount": session.actual_cost
        })
        logger.info(f"Recorded standalone session cost: {session.actual_cost} for {today_str}")
    
    # Remove session from active sessions
    del request.app.state.sage_sessions[session_id]
    
    return {
        "status": "ended",
        "session": session,
        "recording_ended": recording_ended,
        "sdk_processing": recording_ended,  # SDK processing starts after recording ends
        "baseline": {
            "user_id": user_id,
            "is_calibrated": baseline.is_calibrated,
            "calibration_progress": baseline.calibration_progress,
            "calibration_sessions": baseline.calibration_sessions,
        }
    }


# ============================================================================
# WebSocket Endpoints
# ============================================================================

@router.websocket("/ws/presage/video")
async def websocket_video_input(websocket: WebSocket):
    """
    WebSocket endpoint to receive video frames from frontend.
    
    Expected message formats:
    
    Start a session (before sending frames):
    {
        "type": "session_start",
        "session_id": "<session-id>",
        "fps": 30,           # optional, default 30
        "width": 1280,       # optional, default 1280
        "height": 720        # optional, default 720
    }
    
    Send a video frame:
    {
        "type": "frame",
        "data": "<base64-encoded JPEG>"
    }
    
    End the session (before disconnecting):
    {
        "type": "session_end",
        "session_id": "<session-id>"
    }
    
    Ping/pong for keepalive:
    {
        "type": "ping"
    }
    
    Note: If the WebSocket disconnects while a session is active,
    the session will be automatically ended to trigger SDK processing.
    """
    await websocket.accept()
    logger.info("Video WebSocket client connected")
    
    client = get_presage_client()
    
    # Track active session for this WebSocket connection
    active_session_id: Optional[str] = None
    frame_count = 0
    
    try:
        while True:
            data = await websocket.receive_json()
            msg_type = data.get("type")
            
            if msg_type == "session_start":
                # Client wants to start a new recording session
                session_id = data.get("session_id")
                if not session_id:
                    session_id = str(uuid4())
                
                fps = data.get("fps", DEFAULT_VIDEO_FPS)
                width = data.get("width", DEFAULT_VIDEO_WIDTH)
                height = data.get("height", DEFAULT_VIDEO_HEIGHT)
                
                # End any existing session first
                if active_session_id:
                    logger.warning(f"Ending previous session {active_session_id} before starting new one")
                    client.end_session(active_session_id)
                
                # Start new session (skip if already active with same ID)
                if client.current_session_id == session_id:
                    success = True
                else:
                    success = client.start_session(
                        session_id=session_id,
                        fps=fps,
                        width=width,
                        height=height,
                    )
                
                if success:
                    active_session_id = session_id
                    frame_count = 0
                    logger.info(f"Video WebSocket started session: {session_id}")
                
                await websocket.send_json({
                    "type": "session_started",
                    "session_id": session_id,
                    "success": success,
                    "fps": fps,
                    "width": width,
                    "height": height,
                })
                
            elif msg_type == "session_end":
                # Client wants to end the recording session
                session_id = data.get("session_id") or active_session_id
                
                if session_id:
                    success = client.end_session(session_id)
                    
                    if session_id == active_session_id:
                        active_session_id = None
                    
                    logger.info(f"Video WebSocket ended session: {session_id} (frames: {frame_count})")
                    
                    await websocket.send_json({
                        "type": "session_ended",
                        "session_id": session_id,
                        "success": success,
                        "frame_count": frame_count,
                        "sdk_processing": success,
                    })
                    frame_count = 0
                else:
                    await websocket.send_json({
                        "type": "error",
                        "message": "No active session to end",
                    })
            
            elif msg_type == "frame":
                # Decode and forward base64 frame
                try:
                    jpeg_data = base64.b64decode(data.get("data", ""))
                    if jpeg_data:
                        # Auto-start session if needed (first frame)
                        if not active_session_id:
                            # Prefer any session already started via REST
                            active_session_id = client.current_session_id or str(uuid4())
                            fps = data.get("fps", DEFAULT_VIDEO_FPS)
                            width = data.get("width", DEFAULT_VIDEO_WIDTH)
                            height = data.get("height", DEFAULT_VIDEO_HEIGHT)
                            if client.current_session_id == active_session_id:
                                started = True
                            else:
                                started = client.start_session(
                                    session_id=active_session_id,
                                    fps=fps,
                                    width=width,
                                    height=height,
                                )
                            
                            await websocket.send_json({
                                "type": "session_started",
                                "session_id": active_session_id,
                                "success": started,
                                "fps": fps,
                                "width": width,
                                "height": height,
                                "auto_started": True,
                            })
                            
                            if not started:
                                active_session_id = None
                        
                        success = client.send_frame(jpeg_data)
                        if success:
                            frame_count += 1
                        else:
                            await websocket.send_json({
                                "type": "error",
                                "message": "Failed to forward frame to Presage"
                            })
                except Exception as e:
                    logger.error(f"Error processing frame: {e}")
                    await websocket.send_json({
                        "type": "error",
                        "message": f"Error processing frame: {str(e)}"
                    })
                    
            elif msg_type == "ping":
                await websocket.send_json({
                    "type": "pong",
                    "session_id": active_session_id,
                    "frame_count": frame_count,
                })
                
    except WebSocketDisconnect:
        logger.info("Video WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Video WebSocket error: {e}")
    finally:
        # Auto-end session on disconnect if one was active
        if active_session_id:
            logger.info(f"Auto-ending session {active_session_id} on disconnect (frames: {frame_count})")
            client.end_session(active_session_id)


@router.websocket("/ws/presage/metrics")
async def websocket_metrics_stream(websocket: WebSocket):
    """
    WebSocket endpoint for real-time metrics streaming to frontend.
    
    Sends JSON messages:
    {
        "type": "metrics" | "status",
        "pulse_rate": <float>,
        "breathing_rate": <float>,
        "focus_score": <int>,
        "stress_level": <int>,
        ...
    }
    """
    await websocket.accept()
    _websocket_clients.add(websocket)
    logger.info(f"Metrics WebSocket client connected. Total: {len(_websocket_clients)}")
    
    client = get_presage_client()
    user_id = websocket.query_params.get("user_id", "default")
    learn_baseline = websocket.query_params.get("learn_baseline", "false").lower() in {"1", "true", "yes"}
    
    # Try to connect to daemon
    if not client.connected:
        client.connect()
    
    try:
        while True:
            # Read metrics from daemon
            if client.connected:
                metrics_list = client.read_metrics()
                
                for metrics in metrics_list:
                    msg_type = metrics.get("type")
                    
                    # Handle core metrics (from cloud processing)
                    if msg_type == "metrics":
                        vital_input = _build_vital_input(metrics, client.pulse_history)
                        cognitive = calculate_cognitive_load_personalized(
                            vital_input,
                            user_id=user_id,
                            learn_baseline=learn_baseline
                        )
                        metrics.update({
                            "hrv": cognitive.hrv,
                            "focus_score": cognitive.focus_score,
                            "stress_level": cognitive.stress_level,
                            "cognitive_cost_delta": cognitive.cognitive_cost_delta,
                            "confidence": round(cognitive.confidence, 2),
                        })
                    
                    # Handle edge metrics (real-time frame-by-frame data)
                    elif msg_type == "edge_metrics":
                        # Edge metrics provide pulse_trace and breathing traces
                        # Use these for real-time HRV calculation
                        vital_input = _build_vital_input(metrics, client.pulse_history)
                        cognitive = calculate_cognitive_load_personalized(
                            vital_input,
                            user_id=user_id,
                            learn_baseline=learn_baseline
                        )
                        metrics.update({
                            "hrv": cognitive.hrv,
                            "focus_score": cognitive.focus_score,
                            "stress_level": cognitive.stress_level,
                            "cognitive_cost_delta": cognitive.cognitive_cost_delta,
                            "confidence": round(cognitive.confidence, 2),
                            # Mark this as processed edge metrics
                            "type": "metrics",  # Frontend expects "metrics" type
                            "source": "edge",  # But note it came from edge
                        })
                    
                    # Handle imaging status (face detected, signal quality, etc.)
                    elif msg_type == "imaging_status":
                        # Pass through imaging status for debugging/UI feedback
                        logger.debug(f"Imaging status: {metrics.get('status')}")
                    
                    # Send all messages to frontend
                    await websocket.send_json(metrics)
            else:
                # Try to reconnect
                client.connect()
                await websocket.send_json({
                    "type": "connection_status",
                    "connected": client.connected,
                    "timestamp": int(datetime.utcnow().timestamp() * 1000)
                })
            
            await asyncio.sleep(0.1)
            
            # Handle incoming commands
            try:
                data = await asyncio.wait_for(websocket.receive_json(), timeout=0.01)
                
                if data.get("command") == "reconnect":
                    client.disconnect()
                    success = client.connect()
                    await websocket.send_json({
                        "type": "command_response",
                        "command": "reconnect",
                        "success": success
                    })
                    
            except asyncio.TimeoutError:
                pass
                
    except WebSocketDisconnect:
        logger.info("Metrics WebSocket client disconnected")
    except Exception as e:
        logger.error(f"Metrics WebSocket error: {e}")
    finally:
        _websocket_clients.discard(websocket)
        logger.info(f"Metrics WebSocket removed. Total: {len(_websocket_clients)}")
