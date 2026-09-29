import { useState } from 'react'

const ROLE_PRESETS = [
  {
    id: 'learner',
    title: '🎓 Learner',
    subtitle: 'Master a skill or topic with adaptive pacing',
    description: 'Start with ATLAS lessons, practice problems, and adaptive feedback loops.',
    color: 'var(--cyan)',
    primaryAction: 'lessons',
    onboardingSteps: [
      {
        title: 'Pick a topic',
        body: 'Choose a subject from the materials library or describe what you want to learn.',
        tip: 'Try "Python async/await" or "Linear algebra fundamentals"',
      },
      {
        title: 'Learn → Practice → Check',
        body: 'ATLAS will guide you through structured lessons, hands-on exercises, and self-check quizzes.',
        tip: 'Each lesson builds on the previous one. No rush.',
      },
      {
        title: 'Review and recall',
        body: 'Use flashcards and recap to lock in weak concepts before moving forward.',
        tip: 'Spaced repetition is built in—come back tomorrow for a fresh challenge.',
      },
    ],
  },
  {
    id: 'builder',
    title: '🔧 Builder',
    subtitle: 'Ship code with context-aware guidance and execution',
    description: 'Use Mammoth Mind for repo-aware development and ATLAS for problem-solving.',
    color: 'var(--photon)',
    primaryAction: 'chat',
    onboardingSteps: [
      {
        title: 'Ground your repo',
        body: 'Pick your repository path so Mammoth Mind understands your codebase context.',
        tip: 'This unlocks /guide flows and execution-aware suggestions.',
      },
      {
        title: 'Ask with intent',
        body: 'Instead of "fix my code," try "/guide src/auth.ts" or "refactor the login flow".',
        tip: 'Named artifacts and structured output make a huge difference.',
      },
      {
        title: 'Inspect before shipping',
        body: 'Review the generated code, run tests, and use the Agent page for approvals before deploy.',
        tip: 'Look at the trust posture banner—it tells you if the system is confident.',
      },
    ],
  },
  {
    id: 'operator',
    title: '⚙️ Operator',
    subtitle: 'Keep automation explainable with approvals and audits',
    description: 'Use agent workflows, approvals, and observability dashboards.',
    color: 'var(--violet)',
    primaryAction: 'agent',
    onboardingSteps: [
      {
        title: 'Set approval gates',
        body: 'Configure which agent actions need human review before execution.',
        tip: 'Approve plans first, then runs, then deploy. Keep power visible.',
      },
      {
        title: 'Monitor agent health',
        body: 'Use the Agent page to see all runs, artifacts, and runtime status in one place.',
        tip: 'Scroll to the Diagnostics page to see provider health and trust signals.',
      },
      {
        title: 'Build runbooks',
        body: 'Create repeatable workflows so team members can execute safely without being experts.',
        tip: 'Share command presets and policy bundles with your team.',
      },
    ],
  },
  {
    id: 'founder',
    title: '🚀 Founder',
    subtitle: 'Understand the full MammothOS vision',
    description: 'Explore all surfaces to see how learning, building, and operations fit together.',
    color: 'var(--gold)',
    primaryAction: 'landing',
    onboardingSteps: [
      {
        title: 'Context before charisma',
        body: 'MammothOS attaches the right page, lesson, repo, and workflow before asking the model to speak.',
        tip: 'This is the core design principle—not just a chat box.',
      },
      {
        title: 'Agent surfaces, not overloads',
        body: 'Guide, Tutor, Build, Agent, and Terminal each serve a different job.',
        tip: 'Users pick the right tool for the right task instead of one bloated UI.',
      },
      {
        title: 'Learning loops with memory',
        body: 'ATLAS is built to coach through multiple passes, not one-shot answers.',
        tip: 'Recap, practice, feedback, weak-concept recovery, and next-step pacing.',
      },
    ],
  },
]

export default function First15MinutesModal({ isOpen, onClose, onSelectRole }) {
  const [step, setStep] = useState('role-select') // 'role-select' | 'onboarding' | 'done'
  const [selectedRole, setSelectedRole] = useState(null)
  const [currentStepIndex, setCurrentStepIndex] = useState(0)

  const handleRoleSelect = (role) => {
    setSelectedRole(role)
    setStep('onboarding')
    setCurrentStepIndex(0)
  }

  const handleNextStep = () => {
    if (currentStepIndex < selectedRole.onboardingSteps.length - 1) {
      setCurrentStepIndex(currentStepIndex + 1)
    } else {
      setStep('done')
    }
  }

  const handlePrevStep = () => {
    if (currentStepIndex > 0) {
      setCurrentStepIndex(currentStepIndex - 1)
    }
  }

  const handleFinish = () => {
    onSelectRole?.(selectedRole)
    onClose()
  }

  if (!isOpen) return null

  return (
    <div
      style={{
        position: 'fixed',
        inset: 0,
        background: 'rgba(0,0,0,0.88)',
        display: 'grid',
        placeItems: 'center',
        zIndex: 9999,
        padding: 16,
        backdropFilter: 'blur(4px)',
      }}
      onClick={(e) => e.target === e.currentTarget && onClose()}
    >
      <div
        style={{
          background: 'rgba(13,17,23,0.96)',
          border: '1px solid rgba(255,255,255,0.08)',
          borderRadius: 24,
          padding: '40px 32px',
          maxWidth: 640,
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto',
          boxShadow: '0 25px 50px rgba(0,0,0,0.5)',
        }}
      >
        {step === 'role-select' && (
          <div>
            <div style={{ marginBottom: 32, textAlign: 'center' }}>
              <h2 style={{ margin: '0 0 8px', fontSize: '1.4rem', fontWeight: 600 }}>
                🐘 Welcome to MammothOS
              </h2>
              <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.95rem' }}>
                Let's set you up for success in 15 minutes.
              </p>
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 24 }}>
              {ROLE_PRESETS.map((role) => (
                <button
                  key={role.id}
                  onClick={() => handleRoleSelect(role)}
                  style={{
                    background: 'rgba(255,255,255,0.03)',
                    border: `2px solid ${role.color}`,
                    borderRadius: 12,
                    padding: '16px 12px',
                    cursor: 'pointer',
                    transition: 'all 0.2s',
                    textAlign: 'left',
                    color: 'var(--txt-primary)',
                    fontSize: '0.9rem',
                  }}
                  onMouseEnter={(e) => {
                    e.target.style.background = `${role.color}15`
                    e.target.style.borderColor = role.color
                  }}
                  onMouseLeave={(e) => {
                    e.target.style.background = 'rgba(255,255,255,0.03)'
                    e.target.style.borderColor = role.color
                  }}
                >
                  <div style={{ fontWeight: 600, marginBottom: 4, fontSize: '1rem' }}>{role.title}</div>
                  <div style={{ fontSize: '0.75rem', color: 'var(--txt-sec)' }}>{role.subtitle}</div>
                </button>
              ))}
            </div>

            <p
              style={{
                margin: 0,
                fontSize: '0.8rem',
                color: 'var(--txt-sec)',
                textAlign: 'center',
              }}
            >
              You can change this anytime in Settings. Let's go! 👇
            </p>
          </div>
        )}

        {step === 'onboarding' && selectedRole && (
          <div>
            <div style={{ marginBottom: 28 }}>
              <div style={{ fontSize: '1rem', marginBottom: 4, fontWeight: 600, color: selectedRole.color }}>
                {selectedRole.title}
              </div>
              <h3 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 600 }}>
                Step {currentStepIndex + 1}: {selectedRole.onboardingSteps[currentStepIndex].title}
              </h3>
            </div>

            <div
              style={{
                background: 'rgba(255,255,255,0.02)',
                border: `1px solid ${selectedRole.color}40`,
                borderRadius: 12,
                padding: 20,
                marginBottom: 24,
              }}
            >
              <p style={{ margin: '0 0 12px', fontSize: '0.95rem', lineHeight: 1.6 }}>
                {selectedRole.onboardingSteps[currentStepIndex].body}
              </p>
              <div
                style={{
                  background: `${selectedRole.color}15`,
                  border: `1px solid ${selectedRole.color}30`,
                  borderRadius: 8,
                  padding: '10px 12px',
                  fontSize: '0.8rem',
                  color: selectedRole.color,
                }}
              >
                💡 Tip: {selectedRole.onboardingSteps[currentStepIndex].tip}
              </div>
            </div>

            <div
              style={{
                display: 'flex',
                gap: 12,
                justifyContent: 'space-between',
                marginBottom: 16,
              }}
            >
              <button
                onClick={handlePrevStep}
                disabled={currentStepIndex === 0}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  background: currentStepIndex === 0 ? 'rgba(255,255,255,0.03)' : 'rgba(255,255,255,0.08)',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 8,
                  cursor: currentStepIndex === 0 ? 'not-allowed' : 'pointer',
                  color: currentStepIndex === 0 ? 'var(--txt-sec)' : 'var(--txt-primary)',
                  fontSize: '0.9rem',
                  fontWeight: 500,
                }}
              >
                ← Previous
              </button>

              <div
                style={{
                  display: 'flex',
                  gap: 4,
                  alignItems: 'center',
                  justifyContent: 'center',
                  flex: 1,
                }}
              >
                {selectedRole.onboardingSteps.map((_, i) => (
                  <div
                    key={i}
                    style={{
                      width: 6,
                      height: 6,
                      borderRadius: '50%',
                      background: i === currentStepIndex ? selectedRole.color : 'rgba(255,255,255,0.2)',
                      transition: 'all 0.2s',
                    }}
                  />
                ))}
              </div>

              <button
                onClick={handleNextStep}
                style={{
                  flex: 1,
                  padding: '10px 16px',
                  background: selectedRole.color,
                  border: `1px solid ${selectedRole.color}`,
                  borderRadius: 8,
                  cursor: 'pointer',
                  color: '#000',
                  fontSize: '0.9rem',
                  fontWeight: 600,
                  transition: 'all 0.2s',
                }}
                onMouseEnter={(e) => {
                  e.target.style.opacity = '0.9'
                }}
                onMouseLeave={(e) => {
                  e.target.style.opacity = '1'
                }}
              >
                {currentStepIndex === selectedRole.onboardingSteps.length - 1 ? 'Finish →' : 'Next →'}
              </button>
            </div>

            <div
              style={{
                display: 'flex',
                gap: 8,
                justifyContent: 'space-between',
              }}
            >
              <button
                onClick={() => setStep('role-select')}
                style={{
                  padding: '8px 12px',
                  background: 'transparent',
                  border: '1px solid rgba(255,255,255,0.1)',
                  borderRadius: 6,
                  cursor: 'pointer',
                  color: 'var(--txt-sec)',
                  fontSize: '0.8rem',
                }}
              >
                Back to roles
              </button>
            </div>
          </div>
        )}

        {step === 'done' && selectedRole && (
          <div style={{ textAlign: 'center' }}>
            <div style={{ fontSize: '3rem', marginBottom: 16 }}>✨</div>
            <h2 style={{ margin: '0 0 8px', fontSize: '1.2rem', fontWeight: 600 }}>
              You're all set!
            </h2>
            <p style={{ margin: '0 0 24px', color: 'var(--txt-sec)', fontSize: '0.95rem' }}>
              Remember: context before charisma. Get your repo, lesson, or workflow grounded first, then ask.
            </p>

            <button
              onClick={handleFinish}
              style={{
                width: '100%',
                padding: '12px 20px',
                background: selectedRole.color,
                border: `1px solid ${selectedRole.color}`,
                borderRadius: 8,
                cursor: 'pointer',
                color: '#000',
                fontSize: '1rem',
                fontWeight: 600,
                transition: 'all 0.2s',
              }}
              onMouseEnter={(e) => {
                e.target.style.opacity = '0.9'
              }}
              onMouseLeave={(e) => {
                e.target.style.opacity = '1'
              }}
            >
              Start as {selectedRole.title}
            </button>
          </div>
        )}
      </div>
    </div>
  )
}
