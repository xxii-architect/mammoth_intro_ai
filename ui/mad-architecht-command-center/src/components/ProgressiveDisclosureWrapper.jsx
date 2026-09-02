/**
 * ProgressiveDisclosureWrapper — HOC to apply collapse-by-default behavior to a page
 * Wraps context panels and heavy-info surfaces in collapsed state by default
 */

import { useState } from 'react'
import { DisclosurePanel } from '../lib/progressiveDisclosure'

export function withProgressiveDisclosure(Component, panels = []) {
  return function ProgressiveDisclosureWrapper(props) {
    const [openPanels, setOpenPanels] = useState({})

    const togglePanel = (panelId) => {
      setOpenPanels((prev) => ({
        ...prev,
        [panelId]: !prev[panelId],
      }))
    }

    return (
      <Component
        {...props}
        progressiveDisclosure={{
          openPanels,
          togglePanel,
          DisclosurePanel,
        }}
      />
    )
  }
}

/**
 * Example: CollapsibleContextBar for ChatPage and similar surfaces
 * Shows repo/lesson context, collapsible by default
 */
export function CollapsibleContextBar({
  title = 'Context',
  context = {},
  onToggle = () => {},
  isOpen = false,
  accentColor = 'var(--cyan)',
}) {
  return (
    <DisclosurePanel
      title={title}
      open={isOpen}
      onToggle={onToggle}
      accentColor={accentColor}
      compact={true}
      style={{ marginBottom: 8 }}
      contentStyle={{ fontSize: '0.8rem', lineHeight: 1.5 }}
    >
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
        {Object.entries(context).map(([key, value]) => (
          <div key={key}>
            <div style={{ fontWeight: 600, color: accentColor, marginBottom: 2 }}>
              {key}
            </div>
            <div style={{ color: 'var(--txt-sec)', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
              {String(value).slice(0, 60)}
              {String(value).length > 60 ? '…' : ''}
            </div>
          </div>
        ))}
      </div>
    </DisclosurePanel>
  )
}

/**
 * CollapsibleLessonOverview — for LessonsPage
 * Hides intro/overview banners behind a click by default
 */
export function CollapsibleLessonOverview({
  title = 'Learning Stride',
  body = '',
  details = [],
  isOpen = false,
  onToggle = () => {},
}) {
  return (
    <DisclosurePanel
      title={`📚 ${title}`}
      open={isOpen}
      onToggle={onToggle}
      accentColor="var(--cyan)"
      style={{ marginBottom: 16 }}
    >
      <div style={{ lineHeight: 1.6, fontSize: '0.9rem', color: 'var(--txt-sec)' }}>
        <div style={{ marginBottom: 12 }}>{body}</div>
        {details.length > 0 && (
          <div style={{ display: 'grid', gap: 8 }}>
            {details.map((detail, i) => (
              <div
                key={i}
                style={{
                  background: 'rgba(77,166,255,0.05)',
                  border: '1px solid rgba(77,166,255,0.2)',
                  borderRadius: 6,
                  padding: '8px 12px',
                  fontSize: '0.8rem',
                }}
              >
                <strong>{detail.label}:</strong> {detail.text}
              </div>
            ))}
          </div>
        )}
      </div>
    </DisclosurePanel>
  )
}

/**
 * CollapsibleAdvancedOptions — for pages with many knobs/toggles
 * Groups complex controls behind a disclosure panel
 */
export function CollapsibleAdvancedOptions({
  title = 'Advanced Options',
  children,
  isOpen = false,
  onToggle = () => {},
  accentColor = 'var(--violet)',
}) {
  return (
    <DisclosurePanel
      title={`⚙️ ${title}`}
      open={isOpen}
      onToggle={onToggle}
      accentColor={accentColor}
      compact={true}
      style={{ marginTop: 12 }}
    >
      <div style={{ display: 'grid', gap: 12 }}>{children}</div>
    </DisclosurePanel>
  )
}
