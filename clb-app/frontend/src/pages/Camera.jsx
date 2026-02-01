import React, { useState } from "react";
import CameraFeed from "../components/CameraFeed";

const Camera = () => {
  const [results, setResults] = useState([]);

  const handleResult = (result) => {
    setResults((prev) => [...prev.slice(-9), result]); // Keep last 10 results
  };

  return (
    <div className="min-h-screen bg-slate-950 p-6">
      <div className="max-w-4xl mx-auto">
        <div className="mb-6">
          <h1 className="text-2xl font-bold text-white mb-2">
            Real-Time Camera Feed
          </h1>
          <p className="text-slate-400">
            Stream camera frames via WebSocket for real-time processing.
          </p>
        </div>

        <div className="grid gap-6 lg:grid-cols-2">
          <CameraFeed onResult={handleResult} />

          <div className="bg-slate-900 rounded-xl p-6 border border-slate-800">
            <h2 className="text-xl font-semibold text-white mb-4">
              Processing Results
            </h2>
            
            {results.length === 0 ? (
              <div className="text-slate-500 text-sm">
                Results will appear here once the camera starts streaming...
              </div>
            ) : (
              <div className="space-y-2 max-h-96 overflow-auto">
                {results.map((result, idx) => (
                  <div
                    key={idx}
                    className="p-3 bg-slate-800 rounded-lg text-sm"
                  >
                    <div className="text-slate-400 text-xs mb-1">
                      Frame #{result.frame_number || "?"}
                    </div>
                    <div className="text-slate-200">
                      {result.message || JSON.stringify(result)}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        <div className="mt-6 p-4 bg-slate-900/50 rounded-lg border border-slate-800">
          <h3 className="text-sm font-medium text-slate-300 mb-2">
            How it works:
          </h3>
          <ul className="text-xs text-slate-400 space-y-1">
            <li>1. Click "Start Camera" to begin capturing</li>
            <li>2. Frames are sent via WebSocket at 30 FPS</li>
            <li>3. Backend receives and processes each frame</li>
            <li>4. Results are streamed back in real-time</li>
          </ul>
        </div>
      </div>
    </div>
  );
};

export default Camera;
