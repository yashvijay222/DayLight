import React, { useEffect, useRef } from "react";
import { useNavigate, useSearchParams } from "react-router-dom";

import CalendarConnect from "../components/CalendarConnect";
import { useGoogleCalendar } from "../hooks/useGoogleCalendar";

const features = [
  { icon: "📊", title: "Track Load", desc: "See your cognitive cost per meeting" },
  { icon: "⚡", title: "Optimize", desc: "Get AI suggestions to reduce overload" },
  { icon: "🧘", title: "Recover", desc: "Schedule breaks to restore focus" },
];

const Onboarding = () => {
  const [params] = useSearchParams();
  const navigate = useNavigate();
  const { finish } = useGoogleCalendar();
  const hasProcessedCode = useRef(false);

  useEffect(() => {
    const code = params.get("code");
    if (code && !hasProcessedCode.current) {
      hasProcessedCode.current = true;
      finish(code).then(() => navigate("/analysis"));
    }
  }, [params, finish, navigate]);

  return (
    <div className="min-h-screen flex items-center justify-center p-6">
      <div className="max-w-2xl w-full space-y-8">
        <div className="text-center">
          <h1 className="text-4xl font-bold bg-gradient-to-r from-neutral via-recovery to-warning bg-clip-text text-transparent">
            Cognitive Load Budgeting
          </h1>
          <p className="text-slate-400 mt-3 text-lg">
            Track your cognitive budget, optimize your schedule, and prevent burnout.
          </p>
        </div>

        <div className="grid grid-cols-3 gap-4">
          {features.map((f) => (
            <div key={f.title} className="card text-center">
              <div className="text-3xl mb-2">{f.icon}</div>
              <div className="font-semibold">{f.title}</div>
              <div className="text-xs text-slate-400 mt-1">{f.desc}</div>
            </div>
          ))}
        </div>

        <CalendarConnect />

        <div className="text-center">
          <button
            onClick={() => navigate("/dashboard")}
            className="text-sm text-slate-500 hover:text-slate-300 transition"
          >
            Skip to Dashboard with demo data →
          </button>
        </div>
      </div>
    </div>
  );
};

export default Onboarding;
