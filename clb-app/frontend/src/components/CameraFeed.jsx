import React, { useRef, useState, useEffect, useCallback } from "react";

const CameraFeed = ({ onResult }) => {
  const videoRef = useRef(null);
  const canvasRef = useRef(null);
  const wsRef = useRef(null);
  const streamRef = useRef(null);
  const frameIntervalRef = useRef(null);

  const [isConnected, setIsConnected] = useState(false);
  const [isStreaming, setIsStreaming] = useState(false);
  const [frameCount, setFrameCount] = useState(0);
  const [fps, setFps] = useState(0);
  const [error, setError] = useState(null);
  const [lastResult, setLastResult] = useState(null);

  const clientId = useRef(`client-${Date.now()}`);

  // Connect to WebSocket
  const connectWebSocket = useCallback(() => {
    const wsUrl = `ws://localhost:8000/api/ws/camera/${clientId.current}`;
    
    try {
      wsRef.current = new WebSocket(wsUrl);

      wsRef.current.onopen = () => {
        console.log("[Camera] WebSocket connected");
        setIsConnected(true);
        setError(null);
      };

      wsRef.current.onmessage = (event) => {
        const message = JSON.parse(event.data);
        
        if (message.type === "ack") {
          setFrameCount(message.frame_number);
        } else if (message.type === "result") {
          setLastResult(message.data);
          if (onResult) {
            onResult(message.data);
          }
        } else if (message.type === "error") {
          console.error("[Camera] Server error:", message.message);
        }
      };

      wsRef.current.onclose = () => {
        console.log("[Camera] WebSocket disconnected");
        setIsConnected(false);
        setIsStreaming(false);
      };

      wsRef.current.onerror = (err) => {
        console.error("[Camera] WebSocket error:", err);
        setError("WebSocket connection failed");
        setIsConnected(false);
      };
    } catch (err) {
      setError(`Failed to connect: ${err.message}`);
    }
  }, [onResult]);

  // Start camera
  const startCamera = async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({
        video: {
          width: { ideal: 640 },
          height: { ideal: 480 },
          facingMode: "user",
        },
        audio: false,
      });

      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
      }
      setError(null);
      return true;
    } catch (err) {
      setError(`Camera access denied: ${err.message}`);
      return false;
    }
  };

  // Stop camera
  const stopCamera = () => {
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  };

  // Capture and send frame
  const captureFrame = useCallback(() => {
    if (!videoRef.current || !canvasRef.current || !wsRef.current) return;
    if (wsRef.current.readyState !== WebSocket.OPEN) return;

    const video = videoRef.current;
    const canvas = canvasRef.current;
    const ctx = canvas.getContext("2d");

    // Set canvas size to match video
    canvas.width = video.videoWidth || 640;
    canvas.height = video.videoHeight || 480;

    // Draw current frame
    ctx.drawImage(video, 0, 0, canvas.width, canvas.height);

    // Convert to base64 JPEG
    const frameData = canvas.toDataURL("image/jpeg", 0.7);

    // Send via WebSocket
    wsRef.current.send(
      JSON.stringify({
        type: "frame",
        data: frameData,
        timestamp: Date.now(),
      })
    );
  }, []);

  // Start streaming frames
  const startStreaming = async () => {
    const cameraStarted = await startCamera();
    if (!cameraStarted) return;

    if (!isConnected) {
      connectWebSocket();
    }

    // Wait for WebSocket to connect
    await new Promise((resolve) => setTimeout(resolve, 500));

    setIsStreaming(true);
    setFrameCount(0);

    // Capture at 30 FPS
    const targetFps = 30;
    const interval = 1000 / targetFps;
    let lastTime = performance.now();
    let framesSinceLastFps = 0;

    frameIntervalRef.current = setInterval(() => {
      captureFrame();
      framesSinceLastFps++;

      const now = performance.now();
      if (now - lastTime >= 1000) {
        setFps(framesSinceLastFps);
        framesSinceLastFps = 0;
        lastTime = now;
      }
    }, interval);
  };

  // Stop streaming
  const stopStreaming = () => {
    if (frameIntervalRef.current) {
      clearInterval(frameIntervalRef.current);
      frameIntervalRef.current = null;
    }

    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(JSON.stringify({ type: "stop" }));
    }

    setIsStreaming(false);
    stopCamera();
  };

  // Cleanup on unmount
  useEffect(() => {
    return () => {
      stopStreaming();
      if (wsRef.current) {
        wsRef.current.close();
      }
    };
  }, []);

  return (
    <div className="bg-slate-900 rounded-xl p-6 border border-slate-800">
      <div className="flex items-center justify-between mb-4">
        <h2 className="text-xl font-semibold text-white">Camera Feed</h2>
        <div className="flex items-center gap-3">
          <div
            className={`w-3 h-3 rounded-full ${
              isConnected ? "bg-green-500" : "bg-red-500"
            }`}
          />
          <span className="text-sm text-slate-400">
            {isConnected ? "Connected" : "Disconnected"}
          </span>
        </div>
      </div>

      {error && (
        <div className="mb-4 p-3 bg-red-500/20 border border-red-500/50 rounded-lg text-red-400 text-sm">
          {error}
        </div>
      )}

      <div className="relative aspect-video bg-black rounded-lg overflow-hidden mb-4">
        <video
          ref={videoRef}
          autoPlay
          playsInline
          muted
          className="w-full h-full object-cover"
        />
        <canvas ref={canvasRef} className="hidden" />

        {isStreaming && (
          <div className="absolute top-3 left-3 flex items-center gap-2">
            <div className="w-2 h-2 bg-red-500 rounded-full animate-pulse" />
            <span className="text-xs text-white bg-black/50 px-2 py-1 rounded">
              LIVE
            </span>
          </div>
        )}

        {isStreaming && (
          <div className="absolute bottom-3 left-3 right-3 flex justify-between">
            <span className="text-xs text-white bg-black/50 px-2 py-1 rounded">
              Frames: {frameCount}
            </span>
            <span className="text-xs text-white bg-black/50 px-2 py-1 rounded">
              {fps} FPS
            </span>
          </div>
        )}
      </div>

      <div className="flex gap-3">
        {!isStreaming ? (
          <button
            onClick={startStreaming}
            className="flex-1 px-4 py-2 bg-green-600 hover:bg-green-500 text-white rounded-lg transition font-medium"
          >
            Start Camera
          </button>
        ) : (
          <button
            onClick={stopStreaming}
            className="flex-1 px-4 py-2 bg-red-600 hover:bg-red-500 text-white rounded-lg transition font-medium"
          >
            Stop Camera
          </button>
        )}
      </div>

      {lastResult && (
        <div className="mt-4 p-3 bg-slate-800 rounded-lg">
          <div className="text-xs text-slate-400 mb-1">Last Result:</div>
          <pre className="text-xs text-slate-300 overflow-auto">
            {JSON.stringify(lastResult, null, 2)}
          </pre>
        </div>
      )}
    </div>
  );
};

export default CameraFeed;
