// MammothWelcome.jsx
// First-run immersive welcome overlay — shown once per browser session
// Uses inline styles (no Tailwind dependency)
import React, { useEffect, useState } from "react";

const STORAGE_KEY = "mammoth_welcomed_v1";

const steps = [
  {
    icon: "🦣",
    headline: "Welcome to MammothOS",
    body: "A multi-agent cognitive operating system built for the long game. Every agent you see here works together — planning, coding, learning, and evolving.",
    accent: "var(--photon)",
  },
  {
    icon: "🧠",
    headline: "Meet ATLAS",
    body: "ATLAS (Mammoth Mind) is your personal AI tutor. It adapts to how you learn, tracks your progress, and gets sharper every session.",
    accent: "var(--violet)",
  },
  {
    icon: "⚡",
    headline: "You're in control",
    body: "Run plans. Trigger agents. Review outputs before anything ships. MammothOS is approval-safe — nothing moves without you.",
    accent: "var(--cyan)",
  },
];

export default function MammothWelcome({ onDismiss }) {
  const [visible, setVisible] = useState(false);
  const [step, setStep] = useState(0);
  const [animating, setAnimating] = useState(false);

  useEffect(() => {
    const seen = sessionStorage.getItem(STORAGE_KEY);
    if (!seen) setVisible(true);
  }, []);

  const dismiss = () => {
    sessionStorage.setItem(STORAGE_KEY, "1");
    setVisible(false);
    onDismiss?.();
  };

  const advance = (dir) => {
    setAnimating(true);
    setTimeout(() => {
      setStep(s => s + dir);
      setAnimating(false);
    }, 120);
  };

  if (!visible) return null;

  const current = steps[step];
  const isLast = step === steps.length - 1;

  return (
    <div
      style={{
        position: "fixed", inset: 0, zIndex: 9999,
        background: "rgba(0,0,0,0.82)", backdropFilter: "blur(6px)",
        display: "flex", alignItems: "center", justifyContent: "center",
        padding: 16,
      }}
    >
      <div
        style={{
          background: "var(--card, #0d0d1a)",
          border: `1px solid ${current.accent}44`,
          borderRadius: 24,
          width: "100%", maxWidth: 480,
          padding: "40px 36px 32px",
          textAlign: "center",
          boxShadow: `0 0 48px ${current.accent}22, 0 16px 48px rgba(0,0,0,0.6)`,
          opacity: animating ? 0 : 1,
          transform: animating ? "scale(0.97)" : "scale(1)",
          transition: "opacity 0.12s ease, transform 0.12s ease, border-color 0.3s ease, box-shadow 0.3s ease",
        }}
      >
        {/* Icon */}
        <div style={{ fontSize: 52, marginBottom: 20, lineHeight: 1 }}>
          {current.icon}
        </div>

        {/* Headline */}
        <h2 style={{
          margin: "0 0 12px",
          fontSize: "1.45rem", fontWeight: 800,
          color: "var(--txt-pri, #fff)",
          letterSpacing: "-0.02em",
          lineHeight: 1.2,
        }}>
          {current.headline}
        </h2>

        {/* Body */}
        <p style={{
          margin: "0 0 28px",
          fontSize: "0.9rem",
          color: "var(--txt-sec, #aaaacc)",
          lineHeight: 1.7,
        }}>
          {current.body}
        </p>

        {/* Step dots */}
        <div style={{ display: "flex", justifyContent: "center", gap: 6, marginBottom: 28 }}>
          {steps.map((_, i) => (
            <div
              key={i}
              style={{
                height: 6, borderRadius: 3,
                width: i === step ? 22 : 6,
                background: i === step ? current.accent : "rgba(255,255,255,0.15)",
                transition: "width 0.25s ease, background 0.25s ease",
              }}
            />
          ))}
        </div>

        {/* Buttons */}
        <div style={{ display: "flex", gap: 10, justifyContent: "center" }}>
          {step > 0 && (
            <button
              onClick={() => advance(-1)}
              style={{
                padding: "10px 18px", borderRadius: 10,
                border: "1px solid rgba(255,255,255,0.12)",
                background: "rgba(255,255,255,0.04)",
                color: "var(--txt-sec, #aaaacc)",
                fontSize: "0.84rem", fontWeight: 600,
                cursor: "pointer",
              }}
            >
              Back
            </button>
          )}
          <button
            onClick={isLast ? dismiss : () => advance(1)}
            style={{
              padding: "10px 28px", borderRadius: 10,
              border: "none",
              background: current.accent,
              color: "#fff",
              fontSize: "0.84rem", fontWeight: 700,
              cursor: "pointer",
              boxShadow: `0 0 16px ${current.accent}55`,
            }}
          >
            {isLast ? "Let's go 🚀" : "Next"}
          </button>
        </div>

        {/* Skip */}
        <button
          onClick={dismiss}
          style={{
            display: "block", margin: "16px auto 0",
            background: "none", border: "none",
            color: "rgba(255,255,255,0.25)",
            fontSize: "0.72rem", cursor: "pointer",
          }}
        >
          Skip intro
        </button>
      </div>
    </div>
  );
}
