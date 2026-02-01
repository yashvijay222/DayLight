import React, { useState, useRef, useEffect, useCallback } from "react";

import { usePresage } from "../hooks/usePresage";

const getStressColor = (stress) => {
  if (stress >= 70) return "text-debt";
  if (stress >= 40) return "text-warning";
  return "text-recovery";
};

const SageMode = ({ events = [], onSessionEnd }) => {
  const { reading, active, start, stop } = usePresage();
  const [lastResult, setLastResult] = useState(null);

  // Camera state
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const frameIntervalRef = useRef(null);
  const clientId = useRef(`sage-${Date.now()}`);

  const [cameraActive, setCameraActive] = useState(false);
  const [wsConnected, setWsConnected] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [cameraError, setCameraError] = useState(null);

  // Connect WebSocket
  const connectWebSocket = useCallback(() => {
    const wsUrl = `ws://localhost:8000/api/ws/camera/${clientId.current}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("[Sage Camera] WebSocket connected");
        setWsConnected(true);
      };

      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        if (message.type === "ack") {
          setFrameCount(message.frame_number);
        }
      };

      wsRef.current.onclose = () => {
        console.log("[Sage Camera] WebSocket disconnected");
        setWsConnected(false);
      };

      wsRef.current.onerror = () => {
        setCameraError("WebSocket connection failed");
        setWsConnected(false);
      };
    } catch (err) {
      setCameraError(`Connection error: ${err.message}`);
    }
  }, []);

  const attachStreamToVideo = useCallback(async () => {
    if (!streamRef.current) return;

    // Wait for video element to mount if needed
    let attempts = 0;
    while (!videoRef.current && attempts < 10) {
      await new Promise((resolve) => requestAnimationFrame(resolve));
      attempts += 1;
    }

    if (!videoRef.current) {
      setCameraError("Video element not ready");
      return;
    }

    const video = videoRef.current;
    video.srcObject = streamRef.current;
    console.log("[Sage Camera] Attached stream to video element");

    await new Promise((resolve, reject) => {
      video.onloadedmetadata = () => {
        console.log("[Sage Camera] Video metadata loaded:", video.videoWidth, "x", video.videoHeight);
        video
          .play()
          .then(() => {
            console.log("[Sage Camera] Video playing");
            resolve();
          })
          .catch((err) => {
            console.error("[Sage Camera] Play failed:", err);
            reject(err);
          });
      };

      video.onerror = (err) => {
        console.error("[Sage Camera] Video error:", err);
        reject(err);
      };

      // Timeout fallback
      setTimeout(() => {
        console.log("[Sage Camera] Timeout - proceeding anyway");
        resolve();
      }, 2000);
    });
  }, []);

  // Start camera
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: "user" },
        audio: false,
      });

      streamRef.current = stream;
      console.log("[Sage Camera] Got stream:", stream.getVideoTracks());

      await attachStreamToVideo();

      connectWebSocket();

      // Wait for WebSocket
      await new Promise((resolve) => setTimeout(resolve, 500));

      setCameraActive(true);
      setCameraError(null);
      setFrameCount(0);

      // Capture at 15 FPS (lower for embedded view)
      frameIntervalRef.current = setInterval(() => {
        captureFrame();
      }, 1000 / 15);

      return true;
    } catch (err) {
      console.error("[Sage Camera] Error:", err);
      setCameraError(`Camera error: ${err.message}`);
      return false;
    }
  };

  // Stop camera
  const stopCamera = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    if (wsRef.current) {
      if (wsRef.current.readyState === WebSocket.OPEN) {
        wsRef.current.send(JSON.stringify({ type: "stop" }));
      }
      wsRef.current.close();
      wsRef.current = null;
    }

    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    setCameraActive(false);
    setWsConnected(false);
  };

  // Capture frame
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
    if (wsRef.current.readyState !== WebSocket.OPEN) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    const frameData = canvas.toDataURL("image/jpeg", 0.6);
    wsRef.current.send(JSON.stringify({
      type: "frame",
      data: frameData,
      timestamp: Date.now(),
    }));
  }, []);

  // Start camera when session starts
  const handleStartSession = async (eventId) => {
    setLastResult(null);
    setCameraActive(true);
    await startCamera();
    start(eventId);
  };

  // Stop camera when session ends
  const handleStop = async () => {
    stopCamera();
    const result = await stop();
    if (result?.session) {
      setLastResult(result.session);
      if (onSessionEnd) onSessionEnd();
    }
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);

  useEffect(() => {
    if (active && streamRef.current) {
      attachStreamToVideo();
    }
  }, [active, attachStreamToVideo]);

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-2">Sage Mode</div>
      <p className="text-xs text-slate-400 mb-3">
        Monitor your cognitive load in real-time during work sessions.
      </p>
      
      {!active && (
        <div className="flex flex-wrap gap-2">
          {events.slice(0, 4).map((event) => (
            <button
              key={event.id}
              className="px-3 py-1 rounded-lg bg-slate-800 hover:bg-slate-700 text-sm"
              onClick={() => handleStartSession(event.id)}
            >
              {event.title}
            </button>
          ))}
          <button
            className="px-3 py-1 rounded-lg bg-neutral hover:bg-blue-500 text-sm"
            onClick={() => handleStartSession(null)}
          >
            General Work
          </button>
        </div>
      )}

      {active && (
        <div className="flex items-center justify-between mb-3">
          <div className="flex items-center gap-2">
            <span className="animate-pulse w-3 h-3 rounded-full bg-recovery"></span>
            <span className="text-sm text-recovery">Session Active</span>
          </div>
          <button
            className="px-4 py-2 rounded-lg bg-debt hover:bg-red-500 text-sm"
            onClick={handleStop}
          >
            End Session
          </button>
        </div>
      )}

      {(active || cameraActive) && (
        <div className="mb-4">
          {cameraError && (
            <div className="text-xs text-red-400 mb-2">{cameraError}</div>
          )}
          <div className="relative bg-slate-900 rounded-lg overflow-hidden" style={{ width: "320px", height: "240px" }}>
            <video
              ref={videoRef}
              autoPlay
              playsInline
              muted
              style={{ width: "320px", height: "240px", objectFit: "cover" }}
            />
            <canvas ref={canvasRef} style={{ display: "none" }} />
            
            {!cameraActive && (
              <div className="absolute inset-0 flex items-center justify-center">
                <div className="text-slate-500 text-sm">Starting camera...</div>
              </div>
            )}
            
            {cameraActive && (
              <>
                <div className="absolute top-2 left-2 flex items-center gap-1">
                  <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
                  <span className="text-[10px] text-white bg-black/60 px-1 rounded">
                    LIVE
                  </span>
                </div>
                <div className="absolute bottom-2 right-2">
                  <span className="text-[10px] text-white bg-black/60 px-1 rounded">
                    {frameCount} frames
                  </span>
                </div>
                <div className="absolute top-2 right-2">
                  <div className={`w-2 h-2 rounded-full ${wsConnected ? "bg-green-500" : "bg-yellow-500"}`} />
                </div>
              </>
            )}
          </div>
        </div>
      )}

      {reading && (
        <div className="mt-4 grid grid-cols-2 gap-2 text-sm">
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">HRV</div>
            <div className="text-xl font-semibold">{reading.hrv}</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Breathing</div>
            <div className="text-xl font-semibold">{reading.breathing_rate}/min</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Focus</div>
            <div className="text-xl font-semibold">{reading.focus_score}%</div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2">
            <div className="text-slate-400 text-xs">Stress</div>
            <div className={`text-xl font-semibold ${getStressColor(reading.stress_level)}`}>
              {reading.stress_level}
            </div>
          </div>
          <div className="bg-slate-950/40 rounded-lg p-2 col-span-2">
            <div className="text-slate-400 text-xs">Cognitive Cost Ticker</div>
            <div className={`text-xl font-semibold ${reading.cognitive_cost_delta > 0 ? "text-debt" : "text-recovery"}`}>
              {reading.cognitive_cost_delta > 0 ? "+" : ""}{reading.cognitive_cost_delta} pts
            </div>
          </div>
        </div>
      )}

      {lastResult && !active && (
        <div className="mt-4 p-3 bg-slate-950/40 rounded-lg">
          <div className="text-sm font-semibold">Session Complete</div>
          <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
            <div>Estimated Cost: {lastResult.estimated_cost}</div>
            <div>Actual Cost: {lastResult.actual_cost}</div>
            <div className={lastResult.debt_adjustment > 0 ? "text-debt" : "text-recovery"}>
              Adjustment: {lastResult.debt_adjustment > 0 ? "+" : ""}{lastResult.debt_adjustment}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default SageMode;
