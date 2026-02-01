"""
WebSocket endpoint for real-time camera feed processing.

Optional: set SMARTSPECTRA_FRAME_DIR to write each frame to disk in SmartSpectra
file-stream format. Then run SmartSpectra C++ with:
  --file_stream_path=$SMARTSPECTRA_FRAME_DIR/frame0000000000000.jpg
  --erase_read_files=true
See docs/WEBSOCKET_TO_SMARTSPECTRA.md.
"""
import asyncio
import base64
import json
import os
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

router = APIRouter()

# SmartSpectra file-stream: directory and filename digit count (must match --file_stream_path mask)
SMARTSPECTRA_FRAME_DIR = os.getenv("SMARTSPECTRA_FRAME_DIR", "")
SMARTSPECTRA_FRAME_DIGITS = 13

# Store active connections
active_connections: Dict[str, WebSocket] = {}


class ConnectionManager:
    def __init__(self):
        self.active_connections: Dict[str, WebSocket] = {}
        self.frame_counts: Dict[str, int] = {}
    
    async def connect(self, websocket: WebSocket, client_id: str):
        await websocket.accept()
        self.active_connections[client_id] = websocket
        self.frame_counts[client_id] = 0
        print(f"[Camera WS] Client {client_id} connected")
    
    def disconnect(self, client_id: str):
        if client_id in self.active_connections:
            del self.active_connections[client_id]
        if client_id in self.frame_counts:
            del self.frame_counts[client_id]
        print(f"[Camera WS] Client {client_id} disconnected")
    
    async def send_message(self, client_id: str, message: dict):
        if client_id in self.active_connections:
            await self.active_connections[client_id].send_json(message)
    
    def increment_frame(self, client_id: str) -> int:
        if client_id in self.frame_counts:
            self.frame_counts[client_id] += 1
            return self.frame_counts[client_id]
        return 0


manager = ConnectionManager()


def write_frame_for_smartspectra(frame_data_b64: str, timestamp_us: Optional[int] = None) -> Optional[str]:
    """
    Decode base64 frame and write to SmartSpectra file-stream directory.
    Only runs if SMARTSPECTRA_FRAME_DIR is set. Returns written path or None.
    Filename format: frame{timestamp_us zero-padded to N digits}.jpg
    """
    if not SMARTSPECTRA_FRAME_DIR:
        return None
    raw = frame_data_b64
    if raw.startswith("data:image"):
        raw = raw.split(",", 1)[1]
    try:
        decoded = base64.b64decode(raw)
    except Exception:
        return None
    Path(SMARTSPECTRA_FRAME_DIR).mkdir(parents=True, exist_ok=True)
    ts = timestamp_us if timestamp_us is not None else int(time.time() * 1e6)
    filename = f"frame{str(ts).zfill(SMARTSPECTRA_FRAME_DIGITS)}.jpg"
    path = Path(SMARTSPECTRA_FRAME_DIR) / filename
    path.write_bytes(decoded)
    return str(path)


@router.websocket("/ws/camera/{client_id}")
async def camera_websocket(websocket: WebSocket, client_id: str):
    """
    WebSocket endpoint for receiving camera frames.
    
    Client sends:
    - {"type": "frame", "data": "<base64 encoded image>", "timestamp": <ms>}
    
    Server responds:
    - {"type": "ack", "frame_number": <int>, "timestamp": <ms>}
    - {"type": "result", "data": {...}}  # Processing results
    """
    await manager.connect(websocket, client_id)
    
    try:
        # Send initial connection confirmation
        await manager.send_message(client_id, {
            "type": "connected",
            "message": "Camera feed connected",
            "timestamp": datetime.utcnow().isoformat(),
        })
        
        while True:
            # Receive frame data
            data = await websocket.receive_text()
            
            try:
                message = json.loads(data)
                msg_type = message.get("type", "")
                
                if msg_type == "frame":
                    # Process incoming frame
                    frame_data = message.get("data", "")
                    timestamp = message.get("timestamp", 0)
                    
                    frame_number = manager.increment_frame(client_id)
                    
                    # Optional: write to SmartSpectra file-stream dir (see WEBSOCKET_TO_SMARTSPECTRA.md)
                    if SMARTSPECTRA_FRAME_DIR:
                        timestamp_us = int(timestamp * 1000) if timestamp else None
                        write_frame_for_smartspectra(frame_data, timestamp_us)
                    
                    result = await process_frame(frame_data, frame_number)
                    
                    await manager.send_message(client_id, {
                        "type": "ack",
                        "frame_number": frame_number,
                        "timestamp": timestamp,
                        "processing_time_ms": result.get("processing_time_ms", 0),
                    })
                    
                    # Send results if available
                    if result.get("has_result"):
                        await manager.send_message(client_id, {
                            "type": "result",
                            "frame_number": frame_number,
                            "data": result.get("data", {}),
                        })
                
                elif msg_type == "ping":
                    await manager.send_message(client_id, {
                        "type": "pong",
                        "timestamp": datetime.utcnow().isoformat(),
                    })
                
                elif msg_type == "stop":
                    await manager.send_message(client_id, {
                        "type": "stopped",
                        "total_frames": manager.frame_counts.get(client_id, 0),
                    })
                    break
                    
            except json.JSONDecodeError:
                await manager.send_message(client_id, {
                    "type": "error",
                    "message": "Invalid JSON",
                })
                
    except WebSocketDisconnect:
        manager.disconnect(client_id)
    except Exception as e:
        print(f"[Camera WS] Error: {e}")
        manager.disconnect(client_id)


async def process_frame(frame_data: str, frame_number: int) -> dict:
    """
    Process a single camera frame.
    
    This is where you would integrate with SmartSpectra SDK or other
    processing logic for health vitals, etc.
    
    Args:
        frame_data: Base64 encoded image data
        frame_number: Sequential frame number
        
    Returns:
        Processing result dictionary
    """
    import time
    start = time.time()
    
    # Placeholder: Decode and process frame
    # In production, this would call SmartSpectra SDK or similar
    try:
        # Validate base64 data (just check it's decodable)
        if frame_data.startswith("data:image"):
            # Strip data URL prefix if present
            frame_data = frame_data.split(",")[1] if "," in frame_data else frame_data
        
        # Decode to verify it's valid base64
        decoded = base64.b64decode(frame_data)
        frame_size = len(decoded)
        
        processing_time = (time.time() - start) * 1000
        
        # Return mock result every 30 frames (1 second at 30fps)
        has_result = frame_number % 30 == 0
        
        result = {
            "processing_time_ms": round(processing_time, 2),
            "frame_size_bytes": frame_size,
            "has_result": has_result,
        }
        
        if has_result:
            result["data"] = {
                "frame_number": frame_number,
                "status": "processing",
                "message": f"Processed {frame_number} frames",
            }
        
        return result
        
    except Exception as e:
        return {
            "processing_time_ms": 0,
            "has_result": True,
            "data": {"error": str(e)},
        }


@router.get("/camera/status")
def get_camera_status():
    """Get status of active camera connections."""
    return {
        "active_connections": len(manager.active_connections),
        "clients": list(manager.active_connections.keys()),
        "frame_counts": manager.frame_counts,
    }
