import React, { useState, useRef, useEffect, useCallback } from "react";

import { usePresage } from "../hooks/usePresage";

const getStressColor = (stress) => {
  if (stress >= 70) return "text-debt";
  if (stress >= 40) return "text-warning";
  return "text-recovery";
};

// WebSocket base URL (backend is mounted under /api)
const WS_BASE = "ws://localhost:8000/api";

// Reconnect settings
const METRICS_RECONNECT_DELAY_MS = 2000;
const METRICS_MAX_RECONNECT_ATTEMPTS = 5;

// Simulated data generator for fallback when daemon is unavailable
const generateSimulatedReading = () => ({
  hrv: Math.floor(40 + Math.random() * 40),
  breathing_rate: Math.floor(12 + Math.random() * 8),
  focus_score: Math.floor(60 + Math.random() * 35),
  stress_level: Math.floor(20 + Math.random() * 60),
  cognitive_cost_delta: Math.floor(-5 + Math.random() * 15),
  pulse_rate: Math.floor(60 + Math.random() * 30),
  confidence: 0,  // 0 indicates simulated data
  simulated: true,
});

const SageMode = ({ events = [], onSessionEnd }) => {
  const { active, start, stop } = usePresage();
  const [lastResult, setLastResult] = useState(null);

  // Session state
  const sessionIdRef = useRef(null);

  // Camera state
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const streamRef = useRef(null);
  const frameIntervalRef = useRef(null);

  // WebSocket refs
  const videoWsRef = useRef(null);    // /ws/presage/video - for sending frames
  const metricsWsRef = useRef(null);  // /ws/presage/metrics - for receiving metrics

  // Reconnect state
  const metricsReconnectAttempts = useRef(0);
  const metricsReconnectTimer = useRef(null);
  const simulationIntervalRef = useRef(null);
  const cameraActiveRef = useRef(false);

  // UI state
  const [cameraActive, setCameraActive] = useState(false);
  const [videoWsConnected, setVideoWsConnected] = useState(false);
  const [metricsWsConnected, setMetricsWsConnected] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [cameraError, setCameraError] = useState(null);
  const [reading, setReading] = useState(null);
  const [usingSimulatedData, setUsingSimulatedData] = useState(false);

  // =========================================================================
  // Video WebSocket - for sending frames and session control
  // =========================================================================
  
  const connectVideoWebSocket = useCallback((sessionId) => {
    const wsUrl = `${WS_BASE}/ws/presage/video`;
    
    try {
      console.log("[Sage] Connecting to video WebSocket:", wsUrl);
      videoWsRef.current = new WebSocket(wsUrl);

      videoWsRef.current.onopen = () => {
        console.log("[Sage] Video WebSocket connected");
        setVideoWsConnected(true);
        
        // Send session_start message
        const startMsg = {
          type: "session_start",
          session_id: sessionId,
          fps: 15,
          width: 320,
          height: 240,
        };
        console.log("[Sage] Sending session_start:", startMsg);
        videoWsRef.current.send(JSON.stringify(startMsg));
      };

      videoWsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          console.log("[Sage] Video WS message:", message.type);
          
          if (message.type === "session_started") {
            console.log("[Sage] Session started confirmed:", message.session_id);
          } else if (message.type === "session_ended") {
            console.log("[Sage] Session ended, frames:", message.frame_count);
            setFrameCount(message.frame_count || 0);
          } else if (message.type === "pong") {
            setFrameCount(message.frame_count || 0);
          } else if (message.type === "error") {
            console.error("[Sage] Video WS error:", message.message);
            setCameraError(message.message);
          }
        } catch (err) {
          console.error("[Sage] Failed to parse video WS message:", err);
        }
      };

      videoWsRef.current.onclose = () => {
        console.log("[Sage] Video WebSocket disconnected");
        setVideoWsConnected(false);
      };

      videoWsRef.current.onerror = (err) => {
        console.error("[Sage] Video WebSocket error:", err);
        setCameraError("Video WebSocket connection failed");
        setVideoWsConnected(false);
      };
    } catch (err) {
      console.error("[Sage] Failed to connect video WebSocket:", err);
      setCameraError(`Connection error: ${err.message}`);
    }
  }, []);

  const disconnectVideoWebSocket = useCallback((sendSessionEnd = true) => {
    if (videoWsRef.current) {
      // Send session_end if connected
      if (sendSessionEnd && videoWsRef.current.readyState === WebSocket.OPEN && sessionIdRef.current) {
        const endMsg = {
          type: "session_end",
          session_id: sessionIdRef.current,
        };
        console.log("[Sage] Sending session_end:", endMsg);
        videoWsRef.current.send(JSON.stringify(endMsg));
      }
      videoWsRef.current.close();
      videoWsRef.current = null;
    }
    setVideoWsConnected(false);
  }, []);

  // =========================================================================
  // Simulated Data Fallback
  // =========================================================================

  const startSimulatedMetrics = useCallback(() => {
    if (simulationIntervalRef.current) return; // Already running
    
    console.log("[Sage] Starting simulated metrics (daemon unavailable)");
    setUsingSimulatedData(true);
    
    // Generate simulated readings at ~1Hz
    simulationIntervalRef.current = setInterval(() => {
      setReading(generateSimulatedReading());
    }, 1000);
  }, []);

  const stopSimulatedMetrics = useCallback(() => {
    if (simulationIntervalRef.current) {
      clearInterval(simulationIntervalRef.current);
      simulationIntervalRef.current = null;
    }
    setUsingSimulatedData(false);
  }, []);

  // =========================================================================
  // Metrics WebSocket - for receiving real-time metrics (with auto-reconnect)
  // =========================================================================
  
  const connectMetricsWebSocket = useCallback(() => {
    // Clear any pending reconnect timer
    if (metricsReconnectTimer.current) {
      clearTimeout(metricsReconnectTimer.current);
      metricsReconnectTimer.current = null;
    }

    const wsUrl = `${WS_BASE}/ws/presage/metrics`;
    
    try {
      console.log("[Sage] Connecting to metrics WebSocket:", wsUrl, `(attempt ${metricsReconnectAttempts.current + 1})`);
      metricsWsRef.current = new WebSocket(wsUrl);

      metricsWsRef.current.onopen = () => {
        console.log("[Sage] Metrics WebSocket connected");
        setMetricsWsConnected(true);
        metricsReconnectAttempts.current = 0; // Reset on successful connection
        
        // Stop simulated data if we were using it
        stopSimulatedMetrics();
      };

      metricsWsRef.current.onmessage = (event) => {
        try {
          const message = JSON.parse(event.data);
          
          if (message.type === "metrics") {
            // Update reading state with real-time metrics
            setReading({
              hrv: message.hrv ?? 0,
              breathing_rate: message.breathing_rate ?? 0,
              focus_score: message.focus_score ?? 0,
              stress_level: message.stress_level ?? 0,
              cognitive_cost_delta: message.cognitive_cost_delta ?? 0,
              pulse_rate: message.pulse_rate ?? 0,
              confidence: message.confidence ?? 0,
              simulated: false,
              realtime: message.realtime ?? false,
              segment_index: message.segment_index,
            });
            
            // If we were using simulated data, stop it now that we have real metrics
            if (usingSimulatedData) {
              stopSimulatedMetrics();
            }
          } else if (message.type === "sdk_status") {
            console.log("[Sage] SDK status:", message.status, message.session_id || "", message.segment_index ?? "");
          } else if (message.type === "connection_status") {
            console.log("[Sage] Daemon connection status:", message.connected);
            // If daemon disconnected, we might start getting no metrics
            if (!message.connected) {
              console.log("[Sage] Daemon disconnected, may switch to simulated data");
            }
          } else if (message.type === "sdk_status") {
            console.log("[Sage] SDK status:", message.status, message.message || "");
          }
        } catch (err) {
          console.error("[Sage] Failed to parse metrics message:", err);
        }
      };

      metricsWsRef.current.onclose = (event) => {
        console.log("[Sage] Metrics WebSocket disconnected", event.code, event.reason);
        setMetricsWsConnected(false);
        
        // Attempt to reconnect if session is still active
        if (cameraActiveRef.current && metricsReconnectAttempts.current < METRICS_MAX_RECONNECT_ATTEMPTS) {
          metricsReconnectAttempts.current += 1;
          console.log(`[Sage] Scheduling metrics reconnect in ${METRICS_RECONNECT_DELAY_MS}ms...`);
          
          metricsReconnectTimer.current = setTimeout(() => {
            if (cameraActiveRef.current) {
              connectMetricsWebSocket();
            }
          }, METRICS_RECONNECT_DELAY_MS);
        } else if (cameraActiveRef.current) {
          // Max reconnect attempts reached, fall back to simulated data
          console.log("[Sage] Max reconnect attempts reached, falling back to simulated data");
          startSimulatedMetrics();
        }
      };

      metricsWsRef.current.onerror = (err) => {
        console.error("[Sage] Metrics WebSocket error:", err);
        // onclose will be called after onerror, so reconnect logic is handled there
      };
    } catch (err) {
      console.error("[Sage] Failed to connect metrics WebSocket:", err);
      
      // Try to reconnect or fall back to simulated data
      if (cameraActiveRef.current && metricsReconnectAttempts.current < METRICS_MAX_RECONNECT_ATTEMPTS) {
        metricsReconnectAttempts.current += 1;
        metricsReconnectTimer.current = setTimeout(() => {
          if (cameraActiveRef.current) {
            connectMetricsWebSocket();
          }
        }, METRICS_RECONNECT_DELAY_MS);
      } else if (cameraActiveRef.current) {
        startSimulatedMetrics();
      }
    }
  }, [stopSimulatedMetrics, startSimulatedMetrics]);

  const disconnectMetricsWebSocket = useCallback(() => {
    // Clear reconnect timer
    if (metricsReconnectTimer.current) {
      clearTimeout(metricsReconnectTimer.current);
      metricsReconnectTimer.current = null;
    }
    
    // Reset reconnect attempts
    metricsReconnectAttempts.current = 0;
    
    // Close WebSocket
    if (metricsWsRef.current) {
      metricsWsRef.current.close();
      metricsWsRef.current = null;
    }
    setMetricsWsConnected(false);
    
    // Stop simulated data
    stopSimulatedMetrics();
  }, [stopSimulatedMetrics]);

  // =========================================================================
  // Camera capture
  // =========================================================================

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
    console.log("[Sage] Attached stream to video element");

    await new Promise((resolve, reject) => {
      video.onloadedmetadata = () => {
        console.log("[Sage] Video metadata loaded:", video.videoWidth, "x", video.videoHeight);
        video
          .play()
          .then(() => {
            console.log("[Sage] Video playing");
            resolve();
          })
          .catch((err) => {
            console.error("[Sage] Play failed:", err);
            reject(err);
          });
      };

      video.onerror = (err) => {
        console.error("[Sage] Video error:", err);
        reject(err);
      };

      // Timeout fallback
      setTimeout(() => {
        console.log("[Sage] Timeout - proceeding anyway");
        resolve();
      }, 2000);
    });
  }, []);

  // Capture and send a single frame
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !videoWsRef.current) return;
    if (videoWsRef.current.readyState !== WebSocket.OPEN) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    canvas.width = video.videoWidth || 320;
    canvas.height = video.videoHeight || 240;
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Get base64 JPEG data (strip the data:image/jpeg;base64, prefix)
    const dataUrl = canvas.toDataURL("image/jpeg", 0.6);
    const base64Data = dataUrl.split(",")[1];

    // Send frame to video WebSocket
    videoWsRef.current.send(JSON.stringify({
      type: "frame",
      data: base64Data,
    }));

    setFrameCount((prev) => prev + 1);
  }, []);

  // Start camera and connect WebSockets
  const startCamera = useCallback(async (sessionId) => {
    try {
      // Get camera stream
      const stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 320 }, height: { ideal: 240 }, facingMode: "user" },
        audio: false,
      });

      streamRef.current = stream;
      console.log("[Sage] Got camera stream:", stream.getVideoTracks());

      await attachStreamToVideo();

      // Connect WebSockets
      connectVideoWebSocket(sessionId);
      connectMetricsWebSocket();

      // Wait for WebSocket connections
      await new Promise((resolve) => setTimeout(resolve, 500));

      cameraActiveRef.current = true;
      setCameraActive(true);
      setCameraError(null);
      setFrameCount(0);

      // Capture frames at 15 FPS
      frameIntervalRef.current = setInterval(() => {
        captureFrame();
      }, 1000 / 15);

      return true;
    } catch (err) {
      console.error("[Sage] Camera error:", err);
      setCameraError(`Camera error: ${err.message}`);
      return false;
    }
  }, [attachStreamToVideo, connectVideoWebSocket, connectMetricsWebSocket, captureFrame]);

  // Stop camera and disconnect WebSockets
  const stopCamera = useCallback((options = {}) => {
    const { sendSessionEnd = true } = options;
    // Stop frame capture
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    // Stop simulated metrics if running
    stopSimulatedMetrics();

    // Disconnect WebSockets
    disconnectVideoWebSocket(sendSessionEnd);
    disconnectMetricsWebSocket();

    // Stop camera stream
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }

    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }

    cameraActiveRef.current = false;
    setCameraActive(false);
    setReading(null);
  }, [disconnectVideoWebSocket, disconnectMetricsWebSocket, stopSimulatedMetrics]);

  // =========================================================================
  // Session handlers
  // =========================================================================

  const handleStartSession = async (eventId) => {
    setLastResult(null);
    setCameraError(null);

    // Start the session via REST API first to get a session_id
    const sessionData = await start(eventId);
    if (!sessionData?.session_id) {
      setCameraError("Failed to start Sage session");
      return;
    }

    const sessionId = sessionData.session_id;
    sessionIdRef.current = sessionId;
    console.log("[Sage] Starting session:", sessionId);

    // Start camera and WebSockets using the server-provided session_id
    const cameraStarted = await startCamera(sessionId);
    if (!cameraStarted) {
      console.error("[Sage] Failed to start camera");
      await stop();
      sessionIdRef.current = null;
    }
  };

  const handleStop = async () => {
    console.log("[Sage] Stopping session:", sessionIdRef.current);

    // Stop camera and WebSockets
    stopCamera({ sendSessionEnd: false });

    // End session via REST API
    const result = await stop();
    if (result?.session) {
      setLastResult(result.session);
      if (onSessionEnd) onSessionEnd();
    }

    sessionIdRef.current = null;
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopCamera({ sendSessionEnd: true });
    };
  }, [stopCamera]);

  // Re-attach stream when active changes
  useEffect(() => {
    if (active && streamRef.current) {
      attachStreamToVideo();
    }
  }, [active, attachStreamToVideo]);

  useEffect(() => {
    cameraActiveRef.current = cameraActive;
  }, [cameraActive]);

  // =========================================================================
  // Render
  // =========================================================================

  return (
    <div className="card">
      <div className="text-lg font-semibold mb-2">Sage Mode</div>
      <p className="text-xs text-slate-400 mb-3">
        Monitor your cognitive load in real-time during work sessions.
      </p>
      
      {!active && (
        <button
          className="px-4 py-2 rounded-lg bg-neutral hover:bg-blue-500 text-sm font-medium"
          onClick={() => handleStartSession(null)}
        >
          Start Session
        </button>
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
                {/* Connection status indicators */}
                <div className="absolute top-2 right-2 flex items-center gap-1">
                  <div 
                    className={`w-2 h-2 rounded-full ${videoWsConnected ? "bg-green-500" : "bg-yellow-500"}`}
                    title={videoWsConnected ? "Video connected" : "Video disconnected"}
                  />
                  <div 
                    className={`w-2 h-2 rounded-full ${metricsWsConnected ? "bg-blue-500" : usingSimulatedData ? "bg-orange-500" : "bg-yellow-500"}`}
                    title={metricsWsConnected ? "Metrics connected" : usingSimulatedData ? "Using simulated data" : "Metrics disconnected"}
                  />
                </div>
                {usingSimulatedData && (
                  <div className="absolute bottom-2 left-2">
                    <span className="text-[10px] text-orange-400 bg-black/60 px-1 rounded">
                      SIMULATED
                    </span>
                  </div>
                )}
                {reading && !reading.simulated && reading.realtime && (
                  <div className="absolute bottom-2 left-2">
                    <span className="text-[10px] text-green-400 bg-black/60 px-1 rounded">
                      LIVE METRICS
                    </span>
                  </div>
                )}
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
            <div className="text-xl font-semibold">{Number(reading.breathing_rate).toFixed(2)}/min</div>
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
          {lastResult.event_id ? (
            <>
              <div className="text-sm font-semibold">
                {events.find(e => e.id === lastResult.event_id)?.title || "Event"} Adjusted
              </div>
              <div className="grid grid-cols-2 gap-2 mt-2 text-xs">
                <div>Estimated Cost: {Number(lastResult.estimated_cost ?? 0).toFixed(2)}</div>
                <div>Actual Cost: {Number(lastResult.actual_cost ?? 0).toFixed(2)}</div>
                <div className="col-span-2 pt-1 border-t border-slate-800">
                  <span className="text-slate-400">Total Adjustment: </span>
                  <span className={lastResult.debt_adjustment > 0 ? "text-debt" : "text-recovery"}>
                    {lastResult.debt_adjustment > 0 ? "+" : ""}{Number(lastResult.debt_adjustment ?? 0).toFixed(2)}
                  </span>
                </div>
              </div>
            </>
          ) : (
            <>
              <div className="text-sm font-semibold text-recovery">Work Session Complete</div>
              <p className="text-[10px] text-slate-400 mt-1 mb-2">
                This amount has been added to your day's total budget.
              </p>
              <div className="grid grid-cols-2 gap-2 text-xs">
                <div>Session Impact:</div>
                <div className={lastResult.actual_cost > 0 ? "text-debt" : "text-recovery"}>
                  {lastResult.actual_cost > 0 ? "+" : ""}{Number(lastResult.actual_cost ?? 0).toFixed(2)} pts
                </div>
                {lastResult.hourly_projection && (
                  <>
                    <div className="text-slate-400 mt-1">Hourly Estimate:</div>
                    <div className="mt-1 font-semibold">
                      {Number(lastResult.hourly_projection).toFixed(2)} pts/hr
                    </div>
                  </>
                )}
              </div>
            </>
          )}
        </div>
      )}
    </div>
  );
};

export default SageMode;
