import { useState, useEffect } from 'react'
import { Brain, ChevronLeft, ChevronRight, RotateCcw, CheckCircle, XCircle, Shuffle, Sparkles } from 'lucide-react'
import { api } from '../api/client'

const SAMPLE_CARDS = [
  { q: 'What is a closure in JavaScript?', a: 'A function that retains access to its outer scope variables even after the outer function has returned.' },
  { q: 'What does async/await do in Python?', a: 'Allows writing asynchronous code that looks synchronous. async defines a coroutine, await pauses execution until the awaited coroutine completes.' },
  { q: 'What is the difference between == and === in JavaScript?', a: '== checks value equality with type coercion. === checks value AND type equality (strict).' },
  { q: 'What is a REST API?', a: 'An architectural style for APIs using HTTP methods (GET, POST, PUT, DELETE) to perform operations on resources identified by URLs.' },
  { q: 'What does the box-sizing: border-box CSS property do?', a: 'Makes padding and border included in the element\'s total width and height, preventing unexpected layout overflow.' },
]

function normalizeCard(raw, index) {
  if (!raw || typeof raw !== 'object') return null
  const q = String(raw.q || raw.front || raw.question || '').trim()
  const a = String(raw.a || raw.back || raw.answer || '').trim()
  if (!q || !a) return null
  return {
    id: String(raw.id || `card-${index + 1}`),
    q,
    a,
    source: raw.source && typeof raw.source === 'object' ? raw.source : null,
  }
}

export default function FlashcardsPage() {
  const [cards, setCards] = useState(SAMPLE_CARDS)
  const [index, setIndex] = useState(0)
  const [flipped, setFlipped] = useState(false)
  const [score, setScore] = useState({ got: 0, missed: 0 })
  const [done, setDone] = useState(false)
  const [loading, setLoading] = useState(false)
  const [loadError, setLoadError] = useState('')

  const total = cards.length
  const current = cards[index] || { q: 'No cards in this deck yet.', a: 'Add or sync a lesson deck to begin review.' }
  const attempted = score.got + score.missed
  const accuracy = attempted > 0 ? Math.round((score.got / attempted) * 100) : 0

  useEffect(() => {
    setLoading(true)
    setLoadError('')
    api('/flashcards')
      .then(data => {
        if (!Array.isArray(data?.cards)) return
        const normalized = data.cards
          .map((card, index) => normalizeCard(card, index))
          .filter(Boolean)
        if (normalized.length > 0) setCards(normalized)
      })
      .catch(err => {
        setLoadError(err instanceof Error ? err.message : 'Could not load flashcards from the backend.')
      })
      .finally(() => setLoading(false))
  }, [])

  const flip = () => setFlipped(f => !f)

  const mark = (correct) => {
    setScore(s => ({
      got: correct ? s.got + 1 : s.got,
      missed: correct ? s.missed : s.missed + 1,
    }))
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
    <div style={{ padding: 24, maxWidth: 880, margin: '0 auto' }}>
      <div style={{ display: 'grid', gap: 18, marginBottom: 20 }}>
        <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ display: 'grid', placeItems: 'center', width: 42, height: 42, borderRadius: 14, background: 'linear-gradient(135deg, rgba(180,124,255,0.18), rgba(77,166,255,0.12))', border: '1px solid rgba(180,124,255,0.35)' }}>
              <Brain size={20} style={{ color: 'var(--violet)' }} />
            </div>
            <div>
              <div className="eyebrow" style={{ marginBottom: 4 }}>Active recall loop</div>
              <h1 style={{ margin: 0, fontSize: '1.2rem', fontWeight: 800, color: 'var(--txt-pri)' }}>Flashcards</h1>
              <p style={{ margin: 0, fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
                {loading ? 'Loading from ATLAS...' : `${total} cards · learned in short, repeatable bursts`}
              </p>
            </div>
          </div>
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
            <button onClick={shuffle} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}>
              <Shuffle size={14} /> Shuffle
            </button>
            <button onClick={reset} style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: 'pointer', fontSize: '0.78rem' }}>
              <RotateCcw size={14} /> Reset
            </button>
          </div>
        </div>

        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit,minmax(150px,1fr))', gap: 12 }}>
          <div className="glass-card-solid" style={{ padding: 14 }}>
            <div style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--txt-mut)', textTransform: 'uppercase', marginBottom: 6 }}>Accuracy</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--cyan)' }}>{accuracy}%</div>
          </div>
          <div className="glass-card-solid" style={{ padding: 14 }}>
            <div style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--txt-mut)', textTransform: 'uppercase', marginBottom: 6 }}>Progress</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--txt-pri)' }}>{Math.min(index + 1, total)}/{total}</div>
          </div>
          <div className="glass-card-solid" style={{ padding: 14 }}>
            <div style={{ fontSize: '0.68rem', letterSpacing: '0.12em', color: 'var(--txt-mut)', textTransform: 'uppercase', marginBottom: 6 }}>Recall wins</div>
            <div style={{ fontSize: '1.5rem', fontWeight: 800, color: 'var(--violet)' }}>{score.got}</div>
          </div>
        </div>
      </div>

      {loadError ? (
        <div style={{ marginBottom: 16, padding: 12, borderRadius: 12, border: '1px solid rgba(239,68,68,0.22)', background: 'rgba(127,29,29,0.18)', color: '#fecaca', fontSize: '0.78rem' }}>{loadError}</div>
      ) : null}

      {!done ? (
        <>
          <div onClick={flip} style={{
            minHeight: 240,
            borderRadius: 20,
            cursor: 'pointer',
            border: `1px solid ${flipped ? 'rgba(180,124,255,0.45)' : 'var(--border)'}`,
            background: flipped ? 'linear-gradient(135deg, rgba(180,124,255,0.12), rgba(77,166,255,0.08))' : 'rgba(255,255,255,0.04)',
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            padding: 28,
            textAlign: 'center',
            transition: 'all 0.25s ease',
            boxShadow: flipped ? '0 0 24px rgba(180,124,255,0.14)' : 'none',
            marginBottom: 16,
          }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12, color: flipped ? 'var(--violet)' : 'var(--txt-mut)', fontSize: '0.7rem', fontWeight: 700, letterSpacing: '0.12em', textTransform: 'uppercase' }}>
              <Sparkles size={13} />
              {flipped ? 'Answer' : 'Prompt'}
            </div>
            <p style={{ fontSize: '1.04rem', color: 'var(--txt-pri)', lineHeight: 1.7, margin: 0, maxWidth: 620 }}>
              {flipped ? current.a : current.q}
            </p>
            {!flipped && (<p style={{ margin: '16px 0 0', fontSize: '0.72rem', color: 'var(--txt-mut)' }}>Click the card to reveal the answer</p>)}
          </div>

          <div style={{ display: 'flex', gap: 10, justifyContent: 'center', flexWrap: 'wrap' }}>
            <button onClick={() => { setIndex(i => Math.max(0, i - 1)); setFlipped(false) }} disabled={index === 0} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: index === 0 ? 'not-allowed' : 'pointer', opacity: index === 0 ? 0.4 : 1 }}>
              <ChevronLeft size={16} />
            </button>
            <button onClick={() => mark(false)} style={{ flex: '1 1 160px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 18px', borderRadius: 10, border: '1px solid rgba(192,57,43,0.4)', background: 'rgba(192,57,43,0.1)', color: '#e74c3c', cursor: 'pointer', fontWeight: 700, fontSize: '0.82rem' }}>
              <XCircle size={16} /> Missed it
            </button>
            <button onClick={() => mark(true)} style={{ flex: '1 1 160px', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 6, padding: '10px 18px', borderRadius: 10, border: '1px solid rgba(46,160,67,0.4)', background: 'rgba(46,160,67,0.1)', color: '#3fb950', cursor: 'pointer', fontWeight: 700, fontSize: '0.82rem' }}>
              <CheckCircle size={16} /> Got it
            </button>
            <button onClick={() => { setIndex(i => Math.min(total - 1, i + 1)); setFlipped(false) }} disabled={index === total - 1} style={{ padding: '8px 14px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.04)', color: 'var(--txt-sec)', cursor: index === total - 1 ? 'not-allowed' : 'pointer', opacity: index === total - 1 ? 0.4 : 1 }}>
              <ChevronRight size={16} />
            </button>
          </div>
        </>
      ) : (
        <div style={{ textAlign: 'center', padding: 40, border: '1px solid var(--border)', borderRadius: 18, background: 'rgba(255,255,255,0.03)' }}>
          <p style={{ fontSize: '2.6rem', marginBottom: 10 }}>🐘</p>
          <h2 style={{ color: 'var(--txt-pri)', marginBottom: 6 }}>Deck complete</h2>
          <p style={{ color: 'var(--txt-mut)', fontSize: '0.85rem', marginBottom: 20 }}>
            You got <strong style={{ color: 'var(--cyan)' }}>{score.got}</strong> right and missed <strong style={{ color: '#e74c3c' }}>{score.missed}</strong> out of {total} cards.
          </p>
          <button onClick={reset} style={{ padding: '10px 22px', borderRadius: 10, border: 'none', background: 'linear-gradient(90deg, var(--violet), var(--photon))', color: '#fff', fontWeight: 800, cursor: 'pointer', fontSize: '0.9rem' }}>
            Review again
          </button>
        </div>
      )}

      <p style={{ textAlign: 'center', color: 'var(--txt-mut)', fontSize: '0.7rem', marginTop: 20 }}>
        Cards generated by ATLAS from your active lesson · <span style={{ color: 'var(--violet)' }}>Pro</span> decks unlock custom review loops
      </p>
    </div>
  )
}
