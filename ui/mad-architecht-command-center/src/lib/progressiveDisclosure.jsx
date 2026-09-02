import { useState, useCallback } from 'react'

/**
 * useProgressiveDisclosure — default-collapsed pattern for context panels
 * Makes dense UIs feel lighter by hiding supplementary content behind a tap/click
 */
export function useProgressiveDisclosure(initialOpen = false) {
  const [open, setOpen] = useState(initialOpen)
  const toggle = useCallback(() => setOpen((prev) => !prev), [])
  const close = useCallback(() => setOpen(false), [])
  const expand = useCallback(() => setOpen(true), [])
  return { open, toggle, close, expand, setOpen }
}

/**
 * DisclosurePanel — reusable collapsed/expanded component
 */
export function DisclosurePanel({
  title,
  children,
  open = false,
  onToggle = () => {},
  icon = '▼',
  style = {},
  contentStyle = {},
  accentColor = 'var(--cyan)',
  compact = false,
}) {
  return (
    <div
      style={{
        border: `1px solid rgba(255,255,255,0.06)`,
        borderRadius: 8,
        background: 'rgba(255,255,255,0.01)',
        overflow: 'hidden',
        ...style,
      }}
    >
      <button
        onClick={onToggle}
        style={{
          width: '100%',
          padding: compact ? '8px 12px' : '12px 16px',
          background: open ? `${accentColor}10` : 'transparent',
          border: 'none',
          borderBottom: open ? `1px solid ${accentColor}30` : 'none',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'space-between',
          cursor: 'pointer',
          transition: 'all 0.2s',
          fontSize: compact ? '0.85rem' : '0.95rem',
          fontWeight: 500,
          color: 'var(--txt-primary)',
        }}
        onMouseEnter={(e) => {
          e.target.style.background = `${accentColor}15`
        }}
        onMouseLeave={(e) => {
          e.target.style.background = open ? `${accentColor}10` : 'transparent'
        }}
      >
        <span>{title}</span>
        <span
          style={{
            transform: open ? 'rotate(180deg)' : 'rotate(0deg)',
            transition: 'transform 0.2s',
            fontSize: compact ? '0.75rem' : '0.85rem',
            color: open ? accentColor : 'var(--txt-sec)',
          }}
        >
          {icon}
        </span>
      </button>

      {open && (
        <div
          style={{
            padding: compact ? '12px 16px' : '16px 20px',
            borderTop: `1px solid ${accentColor}20`,
            fontSize: compact ? '0.85rem' : '0.9rem',
            lineHeight: 1.6,
            ...contentStyle,
          }}
        >
          {children}
        </div>
      )}
    </div>
  )
}

/**
 * Quick utility: toggle visibility of a panel in a minimal way
 */
export function createCompactPanel(title, content, { accentColor = 'var(--cyan)', isOpen = false } = {}) {
  const Panel = () => {
    const [open, setOpen] = useState(isOpen)
    return (
      <div
        style={{
          border: `1px solid rgba(255,255,255,0.06)`,
          borderRadius: 6,
          overflow: 'hidden',
        }}
      >
        <button
          onClick={() => setOpen(!open)}
          style={{
            width: '100%',
            padding: '8px 12px',
            background: 'transparent',
            border: 'none',
            display: 'flex',
            justifyContent: 'space-between',
            alignItems: 'center',
            cursor: 'pointer',
            fontSize: '0.85rem',
            fontWeight: 500,
            color: 'var(--txt-primary)',
          }}
        >
          <span>{title}</span>
          <span style={{ fontSize: '0.7rem', transform: open ? 'rotate(180deg)' : '', transition: '0.2s' }}>
            ▼
          </span>
        </button>
        {open && (
          <div
            style={{
              padding: '10px 12px',
              borderTop: `1px solid rgba(255,255,255,0.06)`,
              fontSize: '0.8rem',
              color: 'var(--txt-sec)',
            }}
          >
            {content}
          </div>
        )}
      </div>
    )
  }
  return Panel
}
