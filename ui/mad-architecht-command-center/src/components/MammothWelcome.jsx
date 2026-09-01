// MammothWelcome.jsx
// First-run immersive welcome overlay — shown once per browser session
import React, { useEffect, useState } from "react";

const STORAGE_KEY = "mammoth_welcomed_v1";

export default function MammothWelcome({ onDismiss }) {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);

  useEffect(() => {
    const seen = sessionStorage.getItem(STORAGE_KEY);
    if (!seen) {
      setVisible(true);
    }
  }, []);

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
    onDismiss?.();
  };

  if (!visible) return null;

  const steps = [
    {
      icon: "🦣",
      headline: "Welcome to MammothOS",
      body: "A multi-agent cognitive operating system built for the long game. Every agent you see here works together — planning, coding, learning, and evolving.",
    },
    {
      icon: "🧠",
      headline: "Meet ATLAS",
      body: "ATLAS (Mammoth Mind) is your personal AI tutor. It adapts to how you learn, tracks your progress, and gets sharper every session.",
    },
    {
      icon: "⚡",
      headline: "You're in control",
      body: "Run plans. Trigger agents. Review outputs before anything ships. MammothOS is approval-safe — nothing moves without you.",
    },
  ];

  const current = steps[step];
  const isLast = step === steps.length - 1;

  return (
    <div className="fixed inset-0 bg-black/80 backdrop-blur-sm z-50 flex items-center justify-center p-4">
      <div className="bg-[#0d0d1a] border border-[#3d3d5c] rounded-3xl w-full max-w-lg p-10 text-center shadow-2xl animate-fade-in">
        <div className="text-6xl mb-6">{current.icon}</div>
        <h2 className="text-white text-2xl font-bold mb-3">{current.headline}</h2>
        <p className="text-[#aaaacc] text-base leading-relaxed mb-8">{current.body}</p>

        <div className="flex justify-center gap-2 mb-8">
          {steps.map((_, i) => (
            <div
              key={i}
              className={`w-2 h-2 rounded-full transition-all ${i === step ? "bg-[#6655cc] w-6" : "bg-[#3d3d5c]"}`}
            />
          ))}
        </div>

        <div className="flex gap-3 justify-center">
          {step > 0 && (
            <button
              onClick={() => setStep(s => s - 1)}
              className="px-5 py-2.5 rounded-xl border border-[#3d3d5c] text-[#aaaacc] hover:text-white hover:border-[#6655cc] text-sm transition-colors"
            >
              Back
            </button>
          )}
          <button
            onClick={isLast ? dismiss : () => setStep(s => s + 1)}
            className="px-8 py-2.5 rounded-xl bg-[#6655cc] hover:bg-[#7766dd] text-white text-sm font-semibold transition-colors"
          >
            {isLast ? "Let's go 🚀" : "Next"}
          </button>
        </div>

        <button onClick={dismiss} className="mt-4 text-[#555577] hover:text-[#8888aa] text-xs transition-colors">
          Skip intro
        </button>
      </div>
    </div>
  );
}
