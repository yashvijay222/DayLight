# Presage SmartSpectra Integration Protocol

This document describes the session-based video recording and vital signs processing protocol between the Python backend and the Presage C++ daemon.

## Architecture Overview

```
┌─────────────┐     WebSocket      ┌─────────────┐       TCP        ┌─────────────────┐
│   Frontend  │◄──────────────────►│   Python    │◄────────────────►│  Presage Daemon │
│  (Browser)  │   /ws/presage/*    │   Backend   │   ports 9001/2   │  (SmartSpectra) │
└─────────────┘                    └─────────────┘                  └─────────────────┘
                                                                            │
                                                                            ▼
                                                                    ┌─────────────────┐
                                                                    │ Video Recording │
                                                                    │  /app/recordings│
                                                                    └─────────────────┘
```

### Processing Flow

1. **Session Start**: Frontend starts a Sage session via REST API or WebSocket
2. **Video Streaming**: Frontend sends video frames via WebSocket → Backend forwards to Presage daemon via TCP
3. **Recording**: Daemon records frames to a video file (`.avi` MJPG codec)
4. **Session End**: Frontend ends the session, triggering SDK processing
5. **SDK Processing**: Daemon processes the recorded video using SmartSpectra SDK
6. **Metrics Emission**: Real vital signs metrics are emitted via the metrics TCP channel
7. **Frontend Receives**: Backend forwards metrics to frontend via WebSocket

**Important**: Metrics are emitted **after** the session ends and SDK processing completes, not in real-time during recording.

## Environment Variables

### Presage Daemon (C++)

| Variable | Default | Description |
|----------|---------|-------------|
| `SMARTSPECTRA_API_KEY` | (required) | API key for SmartSpectra cloud authentication |
| `VIDEO_INPUT_PORT` | `9001` | TCP port for receiving video frames |
| `METRICS_OUTPUT_PORT` | `9002` | TCP port for emitting metrics |
| `PRESAGE_RECORDINGS_DIR` | `/app/recordings` | Directory to store session recordings |
| `PRESAGE_VIDEO_FPS` | `30` | Default frame rate for video recording |
| `HEADLESS` | `true` | Run without GUI (required in Docker) |
| `VERBOSITY` | `1` | Log verbosity (0=quiet, 3=verbose) |

### Python Backend

| Variable | Default | Description |
|----------|---------|-------------|
| `PRESAGE_DAEMON_HOST` | `presage` | Hostname of the Presage daemon |
| `PRESAGE_DAEMON_PORT` | `9002` | Metrics TCP port |
| `PRESAGE_VIDEO_PORT` | `9001` | Video input TCP port |
| `SMARTSPECTRA_API_KEY` | (required) | Passed through to daemon |

## TCP Protocol (Backend ↔ Daemon)

### Video Input Port (9001)

Accepts two types of messages, distinguished by payload content:

#### 1. Video Frames (Binary)

```
┌─────────────────────┬────────────────────────────────┐
│  Length (4 bytes)   │      JPEG Data (N bytes)       │
│   Big-endian uint   │       Raw binary data          │
└─────────────────────┴────────────────────────────────┘
```

- Length prefix: 4 bytes, big-endian unsigned integer
- JPEG data must start with `0xFF 0xD8` (JPEG magic bytes)

#### 2. Control Messages (JSON)

```
┌─────────────────────┬────────────────────────────────┐
│  Length (4 bytes)   │      JSON String (N bytes)     │
│   Big-endian uint   │     UTF-8 encoded, starts {    │
└─────────────────────┴────────────────────────────────┘
```

Control messages are JSON strings that begin with `{`. The daemon detects this and parses as JSON.

**Session Start:**
```json
{
  "type": "session_start",
  "session_id": "uuid-string",
  "fps": 30,
  "width": 1280,
  "height": 720
}
```

**Session End:**
```json
{
  "type": "session_end",
  "session_id": "uuid-string"
}
```

### Metrics Output Port (9002)

Emits newline-delimited JSON messages:

**Vital Signs Metrics:**
```json
{
  "type": "metrics",
  "source": "presage_sdk",
  "session_id": "uuid-string",
  "timestamp": 1706745600000,
  "pulse_rate": 72.5,
  "pulse_confidence": 0.95,
  "pulse_trace": [[0.0, 0.5], [0.033, 0.52], ...],
  "breathing_rate": 15.2,
  "breathing_confidence": 0.92,
  "breathing_amplitude": [[0.0, 0.8], [0.1, 0.82], ...],
  "breathing_upper_trace": [[0.0, 0.3], [0.1, 0.35], ...],
  "blinking": false,
  "talking": false,
  "apnea_detected": false,
  "measurement_id": "sdk-measurement-id",
  "phasic_blood_pressure": 120.5
}
```

**SDK Status Updates:**
```json
{
  "type": "sdk_status",
  "session_id": "uuid-string",
  "status": "processing_started" | "processing_complete" | "error",
  "message": "Human-readable status description",
  "timestamp": 1706745600000
}
```

## REST API Endpoints

### Start Session

**POST** `/presage/start-sage`

Request:
```json
{
  "event_id": "optional-event-id",
  "user_id": "user-identifier",
  "video_fps": 30,
  "video_width": 1280,
  "video_height": 720
}
```

Response:
```json
{
  "status": "started",
  "session_id": "generated-uuid",
  "user_id": "user-identifier",
  "baseline_calibrated": false,
  "baseline_progress": 0.33,
  "recording_started": true
}
```

### End Session

**POST** `/presage/end-sage`

Request:
```json
{
  "session_id": "session-uuid"
}
```

Response:
```json
{
  "status": "ended",
  "session": { ... },
  "recording_ended": true,
  "sdk_processing": true,
  "baseline": {
    "user_id": "user-identifier",
    "is_calibrated": true,
    "calibration_progress": 1.0,
    "calibration_sessions": 5
  }
}
```

### Get Reading

**GET** `/presage/reading?session_id=<uuid>`

Returns the latest vital signs reading for an active session.

### Connection Status

**GET** `/presage/status`

Returns daemon connection status and latest metrics.

## WebSocket Endpoints

### Video Input WebSocket

**Endpoint:** `ws://host:8000/ws/presage/video`

#### Client → Server Messages

**Start Session:**
```json
{
  "type": "session_start",
  "session_id": "optional-uuid",
  "fps": 30,
  "width": 1280,
  "height": 720
}
```

**Send Frame:**
```json
{
  "type": "frame",
  "data": "<base64-encoded-jpeg>"
}
```

**End Session:**
```json
{
  "type": "session_end",
  "session_id": "session-uuid"
}
```

**Ping:**
```json
{
  "type": "ping"
}
```

#### Server → Client Messages

**Session Started:**
```json
{
  "type": "session_started",
  "session_id": "uuid",
  "success": true,
  "fps": 30,
  "width": 1280,
  "height": 720
}
```

**Session Ended:**
```json
{
  "type": "session_ended",
  "session_id": "uuid",
  "success": true,
  "frame_count": 1500,
  "sdk_processing": true
}
```

**Pong:**
```json
{
  "type": "pong",
  "session_id": "uuid-or-null",
  "frame_count": 1500
}
```

**Error:**
```json
{
  "type": "error",
  "message": "Error description"
}
```

### Metrics Stream WebSocket

**Endpoint:** `ws://host:8000/ws/presage/metrics?user_id=<id>&learn_baseline=false`

#### Query Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `user_id` | `"default"` | User ID for personalized baseline |
| `learn_baseline` | `"false"` | Whether to update baseline from these readings |

#### Server → Client Messages

Real-time metrics with cognitive scores:
```json
{
  "type": "metrics",
  "source": "presage_sdk",
  "session_id": "uuid",
  "pulse_rate": 72.5,
  "breathing_rate": 15.2,
  "hrv": 55,
  "focus_score": 78,
  "stress_level": 35,
  "cognitive_cost_delta": -2,
  "confidence": 0.92,
  ...
}
```

Connection status:
```json
{
  "type": "connection_status",
  "connected": true,
  "timestamp": 1706745600000
}
```

## Typical Session Lifecycle

### Using REST API + Video WebSocket

```
1. Frontend: POST /presage/start-sage
   Backend: Creates session, sends session_start to daemon
   Response: { session_id, recording_started: true }

2. Frontend: Connect to ws://host:8000/ws/presage/video
   
3. Frontend: Send frames via WebSocket
   → {"type": "frame", "data": "<base64-jpeg>"}
   → Backend forwards to daemon port 9001
   → Daemon records to /app/recordings/<session_id>.avi

4. Frontend: POST /presage/end-sage
   Backend: Sends session_end to daemon
   Daemon: Stops recording, starts SDK processing

5. Daemon: SDK processes video file
   Daemon: Emits metrics via port 9002
   Backend: Receives and enriches with cognitive scores
   Backend: Forwards to connected WebSocket clients
```

### Using WebSocket-Only Flow

```
1. Frontend: Connect to ws://host:8000/ws/presage/video

2. Frontend: Start session via WebSocket
   → {"type": "session_start", "session_id": "my-session"}
   ← {"type": "session_started", "success": true}

3. Frontend: Stream frames
   → {"type": "frame", "data": "<base64-jpeg>"} (repeat)

4. Frontend: End session via WebSocket
   → {"type": "session_end", "session_id": "my-session"}
   ← {"type": "session_ended", "sdk_processing": true}

5. Frontend: Connect to ws://host:8000/ws/presage/metrics
   ← Receives metrics when SDK processing completes
```

## Recording File Format

- **Location:** `${PRESAGE_RECORDINGS_DIR}/<session_id>.avi`
- **Codec:** MJPG (Motion JPEG)
- **Container:** AVI
- **Resolution:** As specified in session_start (default 1280x720)
- **Frame Rate:** As specified in session_start (default 30 FPS)

Files are retained after processing for debugging. Implement cleanup policy as needed.

## Error Handling

### Connection Failures

If the video WebSocket disconnects while a session is active, the backend automatically sends `session_end` to ensure the recording is finalized and processed. If no `session_start` is sent, the backend auto-starts a session on the first received frame using default settings.

### SDK Processing Errors

If SDK processing fails, an error status is emitted:
```json
{
  "type": "sdk_status",
  "status": "error",
  "session_id": "uuid",
  "error": "Error description",
  "timestamp": 1706745600000
}
```

### Timeout Behavior

- Video socket timeout: 10 seconds for connection
- Metrics socket: Non-blocking reads
- SDK processing: Runs in background thread, no timeout

## Cognitive Load Calculation

The Python backend enriches raw SDK metrics with cognitive scores:

| Metric | Range | Description |
|--------|-------|-------------|
| `hrv` | 20-80 | Heart rate variability score |
| `focus_score` | 0-100 | Attention/focus level |
| `stress_level` | 0-100 | Physiological stress indicator |
| `cognitive_cost_delta` | -10 to +15 | Session cognitive cost adjustment |
| `confidence` | 0.0-1.0 | Measurement confidence |

These scores use personalized baselines if the user has completed calibration (typically 5 sessions).

## Troubleshooting

### No Metrics Received

1. Check daemon logs: `docker logs presage-daemon`
2. Verify API key: `SMARTSPECTRA_API_KEY` must be valid
3. Check recording exists: `docker exec presage-daemon ls -la /app/recordings/`
4. Ensure session was properly ended (triggers processing)

### Low Confidence Scores

1. Ensure adequate lighting on face
2. Minimize head movement during recording
3. Check video quality (resolution, focus)
4. Ensure minimum 20-30 seconds of recording

### Connection Issues

1. Verify both services are running: `docker-compose ps`
2. Check network connectivity: `docker network inspect backend_internal`
3. Test ports: `nc -z presage 9001 && nc -z presage 9002`
