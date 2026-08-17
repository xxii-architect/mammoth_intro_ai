import { useState, useEffect } from 'react'
import { Brain, ChevronLeft, ChevronRight, RotateCcw, CheckCircle, XCircle, Shuffle } from 'lucide-react'

const SAMPLE_CARDS = [
  { q: 'What is a closure in JavaScript?', a: 'A function that retains access to its outer scope variables even after the outer function has returned.' },
  { q: 'What does async/await do in Python?', a: 'Allows writing asynchronous code that looks synchronous. async defines a coroutine, await pauses execution until the awaited coroutine completes.' },
  { q: 'What is the difference between == and === in JavaScript?', a: '== checks value equality with type coercion. === checks value AND type equality (strict).' },
  { q: 'What is a REST API?', a: 'An architectural style for APIs using HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources identified by URLs.' },
  { q: 'What does the box-sizing: border-box CSS property do?', a: 'Makes padding and border included in the element\'s total width and height, preventing unexpected layout overflow.' },
]

export default function FlashcardsPage() {
  const [cards, setCards] = useState(SAMPLE_CARDS)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [score, setScore] = useState({ got: 0, missed: 0 })
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)

  const current = cards[index]
  const total = cards.length

  // Try to load flashcards from ATLAS backend
  useEffect(() => {
    setLoading(true)
    fetch('/api/flashcards')
      .then(r => r.json())
      .then(data => {
        if (data.cards && data.cards.length > 0) setCards(data.cards)
      })
      .catch(() => {}) // silently fall back to sample cards
      .finally(() => setLoading(false))
  }, [])

  const flip = () => setFlipped(f => !f)

  const mark = (correct) => {
    setScore(s => ({ ...s, got: correct ? s.got + 1 : s.got, missed: correct ? s.missed : s.missed + 1 }))
    setFlipped(false)
    if (index + 1 >= total) {
      setDone(true)
    } else {
      setIndex(i => i + 1)
    }
  }

  const reset = () => {
    setIndex(0)
    setFlipped(false)
    setScore({ got: 0, missed: 0 })
    setDone(false)
  }

  const shuffle = () => {
    setCards(c => [...c].sort(() => Math.random() - 0.5))
    reset()
  }

  return (
    <div style={{ padding: 24, maxWidth: 760, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 24 }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
          <Brain size={22} style={{ color: 'var(--violet)' }} />
          <div>
            <h1 style={{ margin: 0, fontSize: '1.1rem', fontWeight: 700, color: 'var(--txt-pri)' }}>Flashcards</h1>
            <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
              {loading ? 'Loading from ATLAS...' : `${total} cards · ATLAS lesson deck`}
            </p>
          </div>
        </div>
        <div style={{ display: 'flex', gap: 8 }}>
          <button onClick={shuffle}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}>
            <Shuffle size={14} /> Shuffle
          </button>
          <button onClick={reset}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}>
            <RotateCcw size={14} /> Reset
          </button>
        </div>
      </div>

      {/* Score bar */}
      <div style={{ display: 'flex', gap: 12, marginBottom: 20 }}>
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: 'var(--cyan)' }}>{score.got}</p>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Got it</p>
        </div>
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: 'var(--txt-mut)' }}>{index}/{total}</p>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Progress</p>
        </div>
        <div style={{ flex: 1, background: 'rgba(255,255,255,0.04)', border: '1px solid var(--border)', borderRadius: 10, padding: '10px 14px', textAlign: 'center' }}>
          <p style={{ margin: 0, fontSize: '1.3rem', fontWeight: 700, color: 'var(--ember, #c0392b)' }}>{score.missed}</p>
          <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Missed</p>
        </div>
      </div>

      {/* Card */}
      {!done ? (
        <>
          <div onClick={flip}
            style={{
              minHeight: 220, borderRadius: 16, cursor: 'pointer',
              border: `1px solid ${flipped ? 'rgba(180,124,255,0.4)' : 'var(--border)'}`,
              background: flipped ? 'rgba(180,124,255,0.08)' : 'rgba(255,255,255,0.04)',
              display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center',
              padding: 32, textAlign: 'center', transition: 'all 0.25s',
              boxShadow: flipped ? '0 0 24px rgba(180,124,255,0.15)' : 'none',
              marginBottom: 16,
            }}>
            <p style={{ fontSize: '0.68rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase', color: flipped ? 'var(--violet)' : 'var(--txt-mut)', marginBottom: 12 }}>
              {flipped ? '💡 Answer' : '❓ Question'}
            </p>
            <p style={{ fontSize: '1rem', color: 'var(--txt-pri)', lineHeight: 1.6, margin: 0 }}>
              {flipped ? current.a : current.q}
            </p>
            {!flipped && (
              <p style={{ margin: '16px 0 0', fontSize: '0.7rem', color: 'var(--txt-mut)' }}>Click to reveal answer</p>
            )}
          </div>

          {/* Nav + mark buttons */}
          <div style={{ display: 'flex', gap: 10, justifyContent: 'center' }}>
            <button onClick={() => { setIndex(i => Math.max(0, i - 1)); setFlipped(false) }}
              disabled={index === 0}
              style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: index === 0 ? 'not-allowed' : 'pointer', opacity: index === 0 ? 0.4 : 1 }}>
              <ChevronLeft size={16} />
            </button>
            <button onClick={() => mark(false)}
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 20px', borderRadius: 8, border: '1px solid rgba(192,57,43,0.4)', background: 'rgba(192,57,43,0.1)', color: '#e74c3c', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem' }}>
              <XCircle size={16} /> Missed it
            </button>
            <button onClick={() => mark(true)}
              style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 20px', borderRadius: 8, border: '1px solid rgba(46,160,67,0.4)', background: 'rgba(46,160,67,0.1)', color: '#3fb950', cursor: 'pointer', fontWeight: 600, fontSize: '0.82rem' }}>
              <CheckCircle size={16} /> Got it
            </button>
            <button onClick={() => { setIndex(i => Math.min(total - 1, i + 1)); setFlipped(false) }}
              disabled={index === total - 1}
              style={{ padding: '8px 14px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: index === total - 1 ? 'not-allowed' : 'pointer', opacity: index === total - 1 ? 0.4 : 1 }}>
              <ChevronRight size={16} />
            </button>
          </div>
        </>
      ) : (
        // Done screen
        <div style={{ textAlign: 'center', padding: 48, border: '1px solid var(--border)', borderRadius: 16, background: 'rgba(255,255,255,0.03)' }}>
          <p style={{ fontSize: '2.5rem', marginBottom: 8 }}>🐘</p>
          <h2 style={{ color: 'var(--txt-pri)', marginBottom: 4 }}>Deck Complete!</h2>
          <p style={{ color: 'var(--txt-mut)', fontSize: '0.85rem', marginBottom: 20 }}>
            You got <strong style={{ color: 'var(--cyan)' }}>{score.got}</strong> right and missed <strong style={{ color: '#e74c3c' }}>{score.missed}</strong> out of {total} cards.
          </p>
          <button onClick={reset}
            style={{ padding: '10px 24px', borderRadius: 10, border: 'none', background: 'var(--violet)', color: '#fff', fontWeight: 700, cursor: 'pointer', fontSize: '0.9rem' }}>
            Go Again
          </button>
        </div>
      )}

      <p style={{ textAlign: 'center', color: 'var(--txt-mut)', fontSize: '0.68rem', marginTop: 20 }}>
        Cards generated by ATLAS from your active lesson · <span style={{ color: 'var(--violet)' }}>Pro</span> feature unlocks custom decks
      </p>
    </div>
  )
}
