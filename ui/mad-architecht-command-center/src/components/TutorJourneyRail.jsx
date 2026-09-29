/**
 * ATLAS Tutor Journey Rail — Explicit lesson flow visualization
 * Start → Practice → Check → Reflect → Next
 */

export function TutorJourneyRail({ currentStage = 'start', progress = 0.25, onStageChange = () => {} }) {
  const stages = [
    { id: 'start', label: 'Start', icon: '🎯', description: 'Lesson introduction' },
    { id: 'practice', label: 'Practice', icon: '💪', description: 'Hands-on exercise' },
    { id: 'check', label: 'Check', icon: '✓', description: 'Self-assessment' },
    { id: 'reflect', label: 'Reflect', icon: '💭', description: 'Review & insights' },
    { id: 'next', label: 'Next', icon: '→', description: 'Continue path' },
  ]

  const currentIndex = stages.findIndex((s) => s.id === currentStage)

  return (
    <div
      style={{
        padding: '16px 20px',
        background: 'rgba(77,166,255,0.06)',
        border: '1px solid rgba(77,166,255,0.15)',
        borderRadius: 12,
        marginBottom: 16,
      }}
    >
      {/* Title */}
      <div
        style={{
          fontSize: '0.85rem',
          fontWeight: 600,
          color: 'var(--cyan)',
          marginBottom: 12,
          textTransform: 'uppercase',
          letterSpacing: '0.05em',
        }}
      >
        📚 Your Learning Path
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: '100%',
          height: 4,
          background: 'rgba(77,166,255,0.2)',
          borderRadius: 999,
          marginBottom: 12,
          overflow: 'hidden',
        }}
      >
        <div
          style={{
            height: '100%',
            width: `${progress * 100}%`,
            background: 'var(--cyan)',
            transition: 'width 0.3s ease-out',
          }}
        />
      </div>

      {/* Stage buttons */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 8 }}>
        {stages.map((stage, idx) => {
          const isActive = stage.id === currentStage
          const isPassed = idx < currentIndex
          const isNext = idx === currentIndex

          return (
            <button
              key={stage.id}
              onClick={() => onStageChange(stage.id)}
              style={{
                padding: '12px 8px',
                borderRadius: 8,
                border: isActive ? '2px solid var(--cyan)' : '1px solid rgba(77,166,255,0.3)',
                background: isActive ? 'rgba(77,166,255,0.15)' : isPassed ? 'rgba(77,166,255,0.08)' : 'transparent',
                cursor: 'pointer',
                textAlign: 'center',
                transition: 'all 0.2s',
                display: 'flex',
                flexDirection: 'column',
                alignItems: 'center',
                justifyContent: 'center',
                gap: 4,
              }}
              onMouseEnter={(e) => {
                if (!isActive) e.target.style.background = 'rgba(77,166,255,0.12)'
              }}
              onMouseLeave={(e) => {
                e.target.style.background = isActive
                  ? 'rgba(77,166,255,0.15)'
                  : isPassed
                    ? 'rgba(77,166,255,0.08)'
                    : 'transparent'
              }}
            >
              <div style={{ fontSize: '1.2rem' }}>{stage.icon}</div>
              <div
                style={{
                  fontSize: '0.65rem',
                  fontWeight: 600,
                  color: isActive ? 'var(--cyan)' : 'var(--txt-sec)',
                }}
              >
                {stage.label}
              </div>
            </button>
          )
        })}
      </div>

      {/* Current stage description */}
      <div
        style={{
          marginTop: 12,
          fontSize: '0.75rem',
          color: 'var(--txt-sec)',
          fontStyle: 'italic',
        }}
      >
        {stages[currentIndex]?.description}
      </div>
    </div>
  )
}

/**
 * OutcomesCard — Shows learning progress, mastery trend, and retention
 */
export function OutcomesCard({
  masteryTrend = 0.65, // 0–1 scale
  timeToCompetency = 45, // minutes
  retentionSignal = 0.78, // 0–1
  lessonsCompleted = 3,
  totalLessons = 10,
  nextMilestone = 'Reach 80% mastery on Recursion',
}) {
  const masteryColor = masteryTrend >= 0.75 ? 'var(--cyan)' : masteryTrend >= 0.6 ? 'var(--gold)' : '#ff9500'

  return (
    <div
      style={{
        padding: '16px',
        background: 'rgba(77,166,255,0.04)',
        border: '1px solid rgba(77,166,255,0.12)',
        borderRadius: 12,
        marginBottom: 16,
      }}
    >
      <div style={{ fontSize: '0.9rem', fontWeight: 600, marginBottom: 12, color: 'var(--txt-primary)' }}>
        📊 Learning Dashboard
      </div>

      {/* Mastery progress */}
      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 6,
            fontSize: '0.8rem',
          }}
        >
          <span style={{ fontWeight: 500 }}>Mastery</span>
          <span style={{ color: masteryColor, fontWeight: 600 }}>
            {(masteryTrend * 100).toFixed(0)}%
          </span>
        </div>
        <div
          style={{
            width: '100%',
            height: 6,
            background: 'rgba(255,255,255,0.06)',
            borderRadius: 999,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${masteryTrend * 100}%`,
              height: '100%',
              background: masteryColor,
              transition: 'width 0.3s ease-out',
            }}
          />
        </div>
      </div>

      {/* Retention signal */}
      <div style={{ marginBottom: 14 }}>
        <div
          style={{
            display: 'flex',
            justifyContent: 'space-between',
            marginBottom: 6,
            fontSize: '0.8rem',
          }}
        >
          <span style={{ fontWeight: 500 }}>Retention (spaced recall)</span>
          <span style={{ color: 'var(--cyan)', fontWeight: 600 }}>
            {(retentionSignal * 100).toFixed(0)}%
          </span>
        </div>
        <div
          style={{
            width: '100%',
            height: 6,
            background: 'rgba(255,255,255,0.06)',
            borderRadius: 999,
            overflow: 'hidden',
          }}
        >
          <div
            style={{
              width: `${retentionSignal * 100}%`,
              height: '100%',
              background: 'var(--cyan)',
              transition: 'width 0.3s ease-out',
            }}
          />
        </div>
      </div>

      {/* Quick stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12, marginBottom: 14 }}>
        <div
          style={{
            padding: '8px 12px',
            background: 'rgba(77,166,255,0.08)',
            borderRadius: 6,
            fontSize: '0.75rem',
          }}
        >
          <div style={{ color: 'var(--txt-mut)', marginBottom: 2 }}>Time to competency</div>
          <div style={{ fontWeight: 600, color: 'var(--cyan)' }}>{timeToCompetency} min</div>
        </div>
        <div
          style={{
            padding: '8px 12px',
            background: 'rgba(77,166,255,0.08)',
            borderRadius: 6,
            fontSize: '0.75rem',
          }}
        >
          <div style={{ color: 'var(--txt-mut)', marginBottom: 2 }}>Progress</div>
          <div style={{ fontWeight: 600, color: 'var(--cyan)' }}>
            {lessonsCompleted}/{totalLessons}
          </div>
        </div>
      </div>

      {/* Next milestone */}
      <div
        style={{
          padding: '8px 12px',
          background: 'rgba(180,124,255,0.08)',
          border: '1px solid rgba(180,124,255,0.2)',
          borderRadius: 6,
          fontSize: '0.75rem',
          color: 'var(--txt-sec)',
        }}
      >
        <div style={{ fontWeight: 600, color: 'var(--violet)', marginBottom: 2 }}>🎯 Next milestone</div>
        <div>{nextMilestone}</div>
      </div>
    </div>
  )
}

/**
 * LessonCompletionSummary — shown at end of lesson
 */
export function LessonCompletionSummary({
  lessonTitle = 'Lesson',
  conceptsMastered = [],
  conceptsToReview = [],
  nextLesson = null,
  timeSpent = 0,
  masteryScore = 0.75,
  onContinue = () => {},
}) {
  return (
    <div
      style={{
        padding: '20px',
        background: 'linear-gradient(135deg, rgba(77,166,255,0.08), rgba(0,245,212,0.06))',
        border: '1px solid rgba(77,166,255,0.2)',
        borderRadius: 12,
      }}
    >
      <div style={{ textAlign: 'center', marginBottom: 20 }}>
        <div style={{ fontSize: '2rem', marginBottom: 8 }}>✨</div>
        <h3 style={{ margin: '0 0 4px', fontSize: '1.1rem' }}>Lesson complete!</h3>
        <p style={{ margin: 0, color: 'var(--txt-sec)', fontSize: '0.9rem' }}>Great work on "{lessonTitle}"</p>
      </div>

      {/* Stats */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr 1fr', gap: 12, marginBottom: 16 }}>
        <div style={{ textAlign: 'center', padding: '10px', background: 'rgba(77,166,255,0.06)', borderRadius: 8 }}>
          <div style={{ fontSize: '1.8rem', color: 'var(--cyan)', fontWeight: 700 }}>
            {(masteryScore * 100).toFixed(0)}%
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--txt-sec)', marginTop: 2 }}>Mastery</div>
        </div>
        <div style={{ textAlign: 'center', padding: '10px', background: 'rgba(77,166,255,0.06)', borderRadius: 8 }}>
          <div style={{ fontSize: '1.8rem', color: 'var(--cyan)', fontWeight: 700 }}>
            {Math.round(timeSpent / 60)}m
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--txt-sec)', marginTop: 2 }}>Time</div>
        </div>
        <div style={{ textAlign: 'center', padding: '10px', background: 'rgba(77,166,255,0.06)', borderRadius: 8 }}>
          <div style={{ fontSize: '1.8rem', color: 'var(--cyan)', fontWeight: 700 }}>
            {conceptsMastered.length}
          </div>
          <div style={{ fontSize: '0.7rem', color: 'var(--txt-sec)', marginTop: 2 }}>Concepts</div>
        </div>
      </div>

      {/* Concepts */}
      <div style={{ marginBottom: 16 }}>
        {conceptsMastered.length > 0 && (
          <div style={{ marginBottom: 12 }}>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--cyan)', marginBottom: 6 }}>
              ✓ Mastered
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {conceptsMastered.map((c, i) => (
                <span
                  key={i}
                  style={{
                    padding: '4px 10px',
                    background: 'rgba(77,166,255,0.12)',
                    border: '1px solid rgba(77,166,255,0.3)',
                    borderRadius: 4,
                    fontSize: '0.75rem',
                  }}
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}

        {conceptsToReview.length > 0 && (
          <div>
            <div style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--gold)', marginBottom: 6 }}>
              ⚡ Review later
            </div>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
              {conceptsToReview.map((c, i) => (
                <span
                  key={i}
                  style={{
                    padding: '4px 10px',
                    background: 'rgba(255,193,7,0.12)',
                    border: '1px solid rgba(255,193,7,0.3)',
                    borderRadius: 4,
                    fontSize: '0.75rem',
                  }}
                >
                  {c}
                </span>
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Action */}
      <button
        onClick={onContinue}
        style={{
          width: '100%',
          padding: '12px 16px',
          background: 'var(--cyan)',
          border: 'none',
          borderRadius: 8,
          color: '#000',
          fontSize: '0.9rem',
          fontWeight: 600,
          cursor: 'pointer',
          transition: 'all 0.2s',
        }}
        onMouseEnter={(e) => {
          e.target.style.opacity = '0.9'
        }}
        onMouseLeave={(e) => {
          e.target.style.opacity = '1'
        }}
      >
        {nextLesson ? `Continue to ${nextLesson}` : 'Review again'}
      </button>
    </div>
  )
}
