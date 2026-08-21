import { useEffect, useMemo, useState } from 'react'
import { User, Clock3, BarChart3, ShieldCheck, Sparkles, Save, Shuffle, RefreshCw, Brain, Target, GitBranch, Trophy, Award, CheckCircle2, BookmarkPlus, BookmarkCheck } from 'lucide-react'
import { api } from '../api/client'
import { useAuth } from '../lib/authContext'

const AVATAR_STORAGE_KEY = 'mammoth.account.avatar.v1'
const ACTIVE_TIME_STORAGE_KEY = 'mammoth.app.active_seconds'
const GOAL_MILESTONE_STORAGE_KEY = 'mammoth.account.goal_milestones.v1'
const SAVED_WINS_STORAGE_KEY = 'mammoth.account.saved_wins.v1'
const CONFIDENCE_CONCEPT_STORAGE_KEY = 'mammoth.account.confidence_concept.v1'

const PREHISTORIC_AVATARS = [
  { id: 'mammoth', icon: '🐘', label: 'Mammoth' },
  { id: 'sabertooth', icon: '🐅', label: 'Sabertooth' },
  { id: 'direwolf', icon: '🐺', label: 'Dire Wolf' },
  { id: 'cavebear', icon: '🐻', label: 'Cave Bear' },
  { id: 'eagle', icon: '🦅', label: 'Eagle' },
]

const EMPTY_PROFILE = { display_name: '', email: '', organization: '' }

function getTierLabel(entitlements) {
  const tier = String(entitlements?.effective_tier || entitlements?.tier || 'explorer')
  return tier.charAt(0).toUpperCase() + tier.slice(1)
}

function formatHours(seconds) {
  const value = Math.max(0, Number(seconds || 0)) / 3600
  return value.toFixed(value >= 10 ? 1 : 2)
}

function clampPercent(value) {
  return Math.max(0, Math.min(100, Number(value || 0)))
}

function toTitle(value) {
  const normalized = String(value || '').replace(/[_-]+/g, ' ').trim()
  if (!normalized) return 'Unknown'
  return normalized.replace(/\b\w/g, (char) => char.toUpperCase())
}

function parseList(value) {
  if (Array.isArray(value)) return value.map((item) => String(item || '').trim()).filter(Boolean)
  return String(value || '')
    .split(',')
    .map((item) => item.trim())
    .filter(Boolean)
}

function isoDayLabel(offset) {
  const date = new Date()
  date.setHours(0, 0, 0, 0)
  date.setDate(date.getDate() - offset)
  return date.toISOString().slice(0, 10)
}

function shortDayLabel(isoDate) {
  const date = new Date(`${isoDate}T00:00:00`)
  return date.toLocaleDateString(undefined, { weekday: 'short' })
}

function readLocalJson(key, fallback) {
  try {
    const raw = window.localStorage.getItem(key)
    return raw ? JSON.parse(raw) : fallback
  } catch {
    return fallback
  }
}

function writeLocalJson(key, value) {
  try {
    window.localStorage.setItem(key, JSON.stringify(value))
    return true
  } catch {
    return false
  }
}

export default function AccountPage({ setPage }) {
  const { user } = useAuth()
  const [loading, setLoading] = useState(true)
  const [saving, setSaving] = useState(false)
  const [goalSaving, setGoalSaving] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const [entitlements, setEntitlements] = useState(null)
  const [billingUsage, setBillingUsage] = useState(null)
  const [profileMeta, setProfileMeta] = useState(null)
  const [atlasStatus, setAtlasStatus] = useState(null)
  const [atlasLibrary, setAtlasLibrary] = useState(null)
  const [profile, setProfile] = useState(EMPTY_PROFILE)
  const [avatarState, setAvatarState] = useState({ mode: 'icon', iconId: PREHISTORIC_AVATARS[0].id, imageData: '' })
  const [activeSeconds, setActiveSeconds] = useState(0)
  const [goalDraft, setGoalDraft] = useState('')
  const [goalMilestones, setGoalMilestones] = useState({})
  const [savedWins, setSavedWins] = useState({})
  const [selectedConfidenceConcept, setSelectedConfidenceConcept] = useState('')

  const refreshAccount = async () => {
    setLoading(true)
    setError('')
    const [entitlementsResult, billingResult, profileResult, statusResult, libraryResult] = await Promise.allSettled([
      api('/entitlements'),
      api('/billing/usage/current'),
      api('/account/profile'),
      api('/atlas/status'),
      api('/atlas/library'),
    ])

    const failures = []
    if (entitlementsResult.status === 'fulfilled') {
      setEntitlements(entitlementsResult.value)
    } else {
      failures.push(`Entitlements: ${entitlementsResult.reason?.message || 'failed to load'}`)
    }

    if (billingResult.status === 'fulfilled') {
      setBillingUsage(billingResult.value)
    } else {
      failures.push(`Billing usage: ${billingResult.reason?.message || 'failed to load'}`)
    }

    if (profileResult.status === 'fulfilled') {
      setProfile(profileResult.value?.profile || EMPTY_PROFILE)
      setProfileMeta(profileResult.value || null)
    } else {
      failures.push(`Profile: ${profileResult.reason?.message || 'failed to load'}`)
    }

    if (statusResult.status === 'fulfilled') {
      setAtlasStatus(statusResult.value)
    } else {
      failures.push(`ATLAS status: ${statusResult.reason?.message || 'failed to load'}`)
    }

    if (libraryResult.status === 'fulfilled') {
      setAtlasLibrary(libraryResult.value)
    } else {
      failures.push(`ATLAS library: ${libraryResult.reason?.message || 'failed to load'}`)
    }

    setError(failures.join(' | '))
    setLoading(false)
  }

  useEffect(() => {
    refreshAccount()
  }, [])

  useEffect(() => {
    try {
      const raw = window.localStorage.getItem(AVATAR_STORAGE_KEY)
      if (!raw) return
      const parsed = JSON.parse(raw)
      const hasKnownIcon = PREHISTORIC_AVATARS.some((item) => item.id === parsed.iconId)
      setAvatarState({
        mode: parsed.mode === 'upload' ? 'upload' : 'icon',
        iconId: hasKnownIcon ? parsed.iconId : PREHISTORIC_AVATARS[0].id,
        imageData: parsed.mode === 'upload' ? String(parsed.imageData || '') : '',
      })
    } catch {
      window.localStorage.removeItem(AVATAR_STORAGE_KEY)
    }
    try {
      setActiveSeconds(Number(window.localStorage.getItem(ACTIVE_TIME_STORAGE_KEY) || 0))
    } catch {
      setActiveSeconds(0)
    }
    setGoalMilestones(readLocalJson(GOAL_MILESTONE_STORAGE_KEY, {}))
    setSavedWins(readLocalJson(SAVED_WINS_STORAGE_KEY, {}))
    try {
      setSelectedConfidenceConcept(String(window.localStorage.getItem(CONFIDENCE_CONCEPT_STORAGE_KEY) || ''))
    } catch {
      setSelectedConfidenceConcept('')
    }

    const interval = window.setInterval(() => {
      try {
        setActiveSeconds(Number(window.localStorage.getItem(ACTIVE_TIME_STORAGE_KEY) || 0))
      } catch {
        setActiveSeconds(0)
      }
    }, 5000)
    return () => window.clearInterval(interval)
  }, [])

  const saveAvatarState = (nextState) => {
    setAvatarState(nextState)
    try {
      window.localStorage.setItem(AVATAR_STORAGE_KEY, JSON.stringify(nextState))
    } catch {
      setNotice('Avatar preview is set, but browser storage is restricted.')
    }
  }

  const persistGoalMilestones = (nextState) => {
    setGoalMilestones(nextState)
    if (!writeLocalJson(GOAL_MILESTONE_STORAGE_KEY, nextState)) {
      setNotice('Goal milestones updated for now, but browser storage is restricted.')
    }
  }

  const persistSavedWins = (nextState) => {
    setSavedWins(nextState)
    if (!writeLocalJson(SAVED_WINS_STORAGE_KEY, nextState)) {
      setNotice('Saved wins updated for now, but browser storage is restricted.')
    }
  }

  const saveProfile = async () => {
    setSaving(true)
    setNotice('')
    setError('')
    try {
      const res = await api('/account/profile', { method: 'POST', body: profile })
      if (res?.status !== 'ok') {
        throw new Error(res?.error || 'Profile save failed.')
      }
      setProfile(res.profile || profile)
      setProfileMeta((prev) => ({ ...(prev || {}), ...res }))
      setNotice('Account profile saved.')
    } catch (saveError) {
      setError(saveError?.message || 'Profile save failed.')
    } finally {
      setSaving(false)
    }
  }

  const saveGoals = async () => {
    setGoalSaving(true)
    setNotice('')
    setError('')
    try {
      const goals = parseList(goalDraft)
      const res = await api('/atlas/onboard', {
        method: 'POST',
        body: {
          experience_level: onboarding.experience_level || learnerExperience,
          preferred_pacing: onboarding.preferred_pacing || learnerPacing,
          learning_style: onboarding.learning_style || learnerStyle,
          goals,
          focus_areas: focusAreas,
        },
      })
      if (res?.status !== 'ok') {
        throw new Error(res?.error || 'Goal save failed.')
      }
      await refreshAccount()
      setNotice('Goals updated.')
    } catch (saveError) {
      setError(saveError?.message || 'Goal save failed.')
    } finally {
      setGoalSaving(false)
    }
  }

  const onAvatarUpload = (event) => {
    const file = event.target.files?.[0]
    if (!file) return
    if (!String(file.type || '').startsWith('image/')) {
      setError('Please upload an image file for your avatar.')
      return
    }
    if (file.size > 2 * 1024 * 1024) {
      setError('Avatar image must be 2MB or smaller.')
      return
    }
    const reader = new FileReader()
    reader.onload = () => {
      setError('')
      const imageData = String(reader.result || '')
      saveAvatarState({ mode: 'upload', iconId: PREHISTORIC_AVATARS[0].id, imageData })
      setNotice('Avatar photo updated.')
    }
    reader.onerror = () => {
      setError('Unable to read the selected image.')
    }
    reader.readAsDataURL(file)
  }

  const randomizeIcon = () => {
    const pick = PREHISTORIC_AVATARS[Math.floor(Math.random() * PREHISTORIC_AVATARS.length)]
    saveAvatarState({ mode: 'icon', iconId: pick.id, imageData: '' })
    setNotice(`Avatar icon set to ${pick.label}.`)
    setError('')
  }

  const selectedIcon = PREHISTORIC_AVATARS.find((item) => item.id === avatarState.iconId) || PREHISTORIC_AVATARS[0]
  const modules = Array.isArray(atlasLibrary?.modules) ? atlasLibrary.modules : []
  const lessons = modules.flatMap((module) => (Array.isArray(module.lessons) ? module.lessons : []))
  const learnerModel = (atlasStatus && typeof atlasStatus.learner_model === 'object' && atlasStatus.learner_model) ? atlasStatus.learner_model : {}
  const learnerContext = (atlasStatus && typeof atlasStatus.learner_context === 'object' && atlasStatus.learner_context) ? atlasStatus.learner_context : {}
  const onboarding = (learnerModel && typeof learnerModel.onboarding === 'object' && learnerModel.onboarding) ? learnerModel.onboarding : {}
  const lessonHistory = Array.isArray(atlasStatus?.lesson_history) ? atlasStatus.lesson_history : []
  const focusAreas = Array.isArray(onboarding.focus_areas) ? onboarding.focus_areas.slice(0, 4) : []
  const onboardingGoals = parseList(onboarding.goals).slice(0, 5)
  const weakConcepts = Array.isArray(learnerModel.weak_concepts) ? learnerModel.weak_concepts.slice(0, 4) : []
  const learnerPacing = String(onboarding.preferred_pacing || learnerContext.pacing || 'balanced')
  const learnerStyle = String(onboarding.learning_style || 'guided')
  const learnerExperience = String(onboarding.experience_level || 'unknown')
  const lessonStreak = Number(learnerContext.session_streak_days || learnerContext.streak || learnerModel.session_streak_days || learnerModel.streak || 0)
  const recentLessonTitle = String(
    atlasStatus?.current_lesson?.title ||
    atlasStatus?.current_exercise?.title ||
    atlasStatus?.topic ||
    ''
  ).trim()
  const completedLessons = lessons.filter((lesson) => lesson.completed).length
  const persistedLessons = lessons.filter((lesson) => lesson.persisted).length
  const masteryTopics = Object.keys((learnerModel && typeof learnerModel.mastery === 'object' && learnerModel.mastery) ? learnerModel.mastery : {})
  const confidenceTopics = Object.keys((learnerModel && typeof learnerModel.confidence === 'object' && learnerModel.confidence) ? learnerModel.confidence : {})
  const recentOutcomes = Array.isArray(learnerModel.recent_outcomes) ? learnerModel.recent_outcomes : []
  const memoryGraph = (learnerModel && typeof learnerModel.memory_graph === 'object' && learnerModel.memory_graph) ? learnerModel.memory_graph : {}
  const memoryNodes = Array.isArray(memoryGraph.nodes) ? memoryGraph.nodes.length : 0
  const memoryEdges = Array.isArray(memoryGraph.edges) ? memoryGraph.edges.length : 0
  const chatTurns = (Array.isArray(atlasStatus?.chat_history) ? atlasStatus.chat_history.length : 0) +
    (Array.isArray(atlasStatus?.assistant_chat_history) ? atlasStatus.assistant_chat_history.length : 0)
  const completionRate = lessons.length ? Math.round((completedLessons / lessons.length) * 100) : 0
  const percentUsed = Number(billingUsage?.percent_used || 0)
  const usageWarning = String(billingUsage?.warning_level || 'normal')
  const tierLabel = getTierLabel(entitlements)
  const attempts = Number(learnerContext.attempts || learnerModel.attempts || 0)
  const recommendedDifficulty = String(learnerContext.recommended_difficulty || atlasStatus?.learner_profile?.recommended_difficulty || 'beginner')

  const usageTone = useMemo(() => {
    if (usageWarning === 'blocked' || usageWarning === 'critical') return '#f87171'
    if (usageWarning === 'elevated') return '#f59e0b'
    return 'var(--cyan)'
  }, [usageWarning])

  const weeklyActivity = useMemo(() => {
    const countsByDay = new Map()
    for (let index = 6; index >= 0; index -= 1) {
      countsByDay.set(isoDayLabel(index), 0)
    }
    lessonHistory.forEach((entry) => {
      const rawDate = String(entry?.updated_at || entry?.created_at || '').slice(0, 10)
      if (!countsByDay.has(rawDate)) return
      countsByDay.set(rawDate, countsByDay.get(rawDate) + 1)
    })
    const maxCount = Math.max(1, ...countsByDay.values())
    return Array.from(countsByDay.entries()).map(([date, count]) => ({
      date,
      label: shortDayLabel(date),
      count,
      height: count ? Math.max(18, Math.round((count / maxCount) * 84)) : 10,
    }))
  }, [lessonHistory])

  const progressStory = useMemo(() => {
    const checkpoints = [
      `Started with a ${toTitle(learnerExperience)} experience level.`,
      `Chose a ${toTitle(learnerPacing)} pace with a ${toTitle(learnerStyle)} learning style.`,
      `Built ${attempts} tracked practice attempt${attempts === 1 ? '' : 's'} so far.`,
      `Completed ${completedLessons} lesson${completedLessons === 1 ? '' : 's'} and saved ${persistedLessons} lesson chunk${persistedLessons === 1 ? '' : 's'} for reuse.`,
    ]
    if (lessonStreak > 0) {
      checkpoints.push(`Maintained a ${lessonStreak}-day lesson streak.`)
    }
    return checkpoints
  }, [attempts, completedLessons, learnerExperience, learnerPacing, learnerStyle, lessonStreak, persistedLessons])

  const goalCards = useMemo(() => (
    onboardingGoals.map((goal, index) => {
      const confidenceTracked = confidenceTopics.length > index
      const completed = Boolean(goalMilestones[goal]) || completionRate >= Math.min(100, (index + 1) * 25)
      return {
        goal,
        status: Boolean(goalMilestones[goal]) ? 'Milestone complete' : completed ? 'Momentum building' : confidenceTracked ? 'In progress' : 'Just getting started',
        tone: completed ? 'var(--cyan)' : confidenceTracked ? 'var(--violet)' : 'var(--txt-mut)',
      }
    })
  ), [completionRate, confidenceTopics.length, goalMilestones, onboardingGoals])

  const confidenceConceptOptions = useMemo(() => {
    const ordered = []
    recentOutcomes.forEach((item) => {
      const concept = String(item?.concept || '').trim()
      if (concept && !ordered.includes(concept)) ordered.push(concept)
    })
    confidenceTopics.forEach((concept) => {
      if (concept && !ordered.includes(concept)) ordered.push(concept)
    })
    return ordered
  }, [confidenceTopics, recentOutcomes])

  const confidenceSeries = useMemo(() => {
    const concept = selectedConfidenceConcept || confidenceConceptOptions[0] || ''
    return recentOutcomes
      .filter((item) => String(item?.concept || '') === concept)
      .map((item, index) => ({
        label: `A${index + 1}`,
        confidence: Math.round(Number(item?.confidence_after || 0) * 100),
        delta: Number(item?.confidence_delta || 0),
        passed: Boolean(item?.passed),
        timestamp: item?.timestamp || '',
      }))
  }, [confidenceConceptOptions, recentOutcomes, selectedConfidenceConcept])

  const heatmapDays = useMemo(() => {
    const countsByDay = new Map()
    for (let index = 27; index >= 0; index -= 1) {
      countsByDay.set(isoDayLabel(index), 0)
    }
    lessonHistory.forEach((entry) => {
      const rawDate = String(entry?.updated_at || entry?.created_at || '').slice(0, 10)
      if (!countsByDay.has(rawDate)) return
      countsByDay.set(rawDate, countsByDay.get(rawDate) + 1)
    })
    const maxCount = Math.max(1, ...countsByDay.values())
    return Array.from(countsByDay.entries()).map(([date, count]) => ({
      date,
      count,
      intensity: count ? Math.max(0.2, count / maxCount) : 0,
      label: shortDayLabel(date),
    }))
  }, [lessonHistory])

  const winsTimeline = useMemo(() => recentOutcomes
    .slice()
    .reverse()
    .map((item, index) => {
      const timestamp = String(item?.timestamp || '')
      const id = `${item?.concept || 'general'}:${timestamp || index}`
      const confidenceAfter = Math.round(Number(item?.confidence_after || 0) * 100)
      const masteryAfter = Math.round(Number(item?.mastery_after || 0) * 100)
      return {
        id,
        title: `${toTitle(item?.concept || 'general')} ${item?.passed ? 'clicked' : 'is still being refined'}`,
        detail: `Confidence ${confidenceAfter}% · Mastery ${masteryAfter}% · Attempt ${Number(item?.attempts || 0)}`,
        timestamp,
        passed: Boolean(item?.passed),
      }
    }), [recentOutcomes])

  const earnedAwards = useMemo(() => {
    const awards = []
    if (attempts >= 1) awards.push({ id: 'first-step', icon: '🥾', title: 'First Step', detail: 'Started building momentum with the first tracked attempt.' })
    if (lessonStreak >= 3) awards.push({ id: 'streak', icon: '🔥', title: 'Consistency', detail: `Reached a ${lessonStreak}-day streak.` })
    if (completedLessons >= 3) awards.push({ id: 'builder', icon: '🏗️', title: 'Builder', detail: 'Completed multiple lessons and kept the work moving.' })
    if (Object.values(goalMilestones).some(Boolean)) awards.push({ id: 'goal', icon: '🎯', title: 'Goal Closer', detail: 'Checked off at least one learner milestone.' })
    if (memoryNodes >= 5) awards.push({ id: 'memory', icon: '🧠', title: 'Memory Mapper', detail: 'Built a meaningful knowledge graph footprint.' })
    return awards
  }, [attempts, completedLessons, goalMilestones, lessonStreak, memoryNodes])

  useEffect(() => {
    setGoalDraft(onboardingGoals.join(', '))
  }, [onboardingGoals])

  useEffect(() => {
    if (selectedConfidenceConcept && confidenceConceptOptions.includes(selectedConfidenceConcept)) return
    const nextConcept = confidenceConceptOptions[0] || ''
    setSelectedConfidenceConcept(nextConcept)
    try {
      if (nextConcept) {
        window.localStorage.setItem(CONFIDENCE_CONCEPT_STORAGE_KEY, nextConcept)
      }
    } catch {
      // Keep the selection in memory if storage is unavailable.
    }
  }, [confidenceConceptOptions, selectedConfidenceConcept])

  return (
    <div className="page-enter" style={{ padding: 24 }}>
      <div style={{ marginBottom: 22, display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap' }}>
        <h1 style={{ fontSize: '1.1rem', fontWeight: 700, margin: 0, display: 'flex', alignItems: 'center', gap: 8 }}>
          <User size={20} color="var(--photon)" /> Account
        </h1>
        <div style={{ display: 'grid', gap: 8 }}>
          <p style={{ margin: 0, fontSize: '0.82rem', color: 'var(--txt-sec)' }}>
            Manage your profile, account status, usage, and learning analytics.
          </p>
          <div>
            <button
              onClick={refreshAccount}
              disabled={loading}
              style={{
                display: 'inline-flex',
                alignItems: 'center',
                gap: 6,
                borderRadius: 8,
                border: '1px solid var(--border)',
                background: 'rgba(255,255,255,0.03)',
                color: 'var(--txt-sec)',
                padding: '7px 10px',
                fontSize: '0.74rem',
                cursor: 'pointer',
                opacity: loading ? 0.6 : 1,
              }}
            >
              <RefreshCw size={13} /> Refresh snapshot
            </button>
          </div>
        </div>
      </div>

      {(error || notice) && (
        <div
          className="glass-card-solid"
          style={{
            marginBottom: 14,
            padding: '10px 12px',
            borderLeft: `3px solid ${error ? '#f87171' : 'var(--cyan)'}`,
            color: error ? '#fecaca' : 'var(--txt-sec)',
            fontSize: '0.77rem',
            lineHeight: 1.5,
          }}
        >
          {error || notice}
        </div>
      )}

      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(320px, 1fr))', gap: 18 }}>
        <div className="glass-card-solid" style={{ padding: 18, gridColumn: '1 / -1', borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 12, flexWrap: 'wrap', marginBottom: 12 }}>
            <div>
              <p style={{ margin: 0, fontSize: '0.68rem', letterSpacing: '0.14em', textTransform: 'uppercase', color: 'var(--txt-sec)', fontWeight: 700 }}>Progress story</p>
              <h2 style={{ margin: '6px 0 0', fontSize: '1rem', color: 'var(--txt-pri)' }}>You started here. Look how far the work has already moved.</h2>
            </div>
            <div style={{ padding: '6px 10px', borderRadius: 999, border: '1px solid rgba(0,245,212,0.26)', background: 'rgba(0,245,212,0.08)', color: 'var(--cyan)', fontSize: '0.72rem', fontWeight: 700 }}>
              {completionRate}% lesson completion
            </div>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', gap: 10 }}>
            {progressStory.map((item) => (
              <div key={item} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', fontSize: '0.76rem', lineHeight: 1.55 }}>
                {item}
              </div>
            ))}
          </div>
          <p style={{ margin: '12px 0 0', fontSize: '0.74rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
            The account page keeps this focused on learner growth and consistency. It celebrates progress without making assumptions about diagnoses or limitations.
          </p>
        </div>

        <div className="glass-card-solid" style={{ padding: 18 }}>
          <div style={{ display: 'flex', gap: 14, alignItems: 'center', marginBottom: 14 }}>
            <div style={{ width: 72, height: 72, borderRadius: '50%', border: '1px solid var(--border)', display: 'grid', placeItems: 'center', fontSize: '2rem', overflow: 'hidden', background: 'rgba(255,255,255,0.03)' }}>
              {avatarState.mode === 'upload' && avatarState.imageData
                ? <img src={avatarState.imageData} alt="Account avatar" style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
                : <span>{selectedIcon.icon}</span>}
            </div>
            <div>
              <p style={{ margin: 0, fontWeight: 700, color: 'var(--txt-pri)' }}>{profile.display_name || user?.email || 'Mammoth learner'}</p>
              <p style={{ margin: '4px 0 0', fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
                {profile.organization || 'No organization set'}
              </p>
            </div>
          </div>

          <label style={{ display: 'grid', gap: 6, marginBottom: 10 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Avatar photo</span>
            <input type="file" accept="image/*" onChange={onAvatarUpload} />
          </label>
          <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6, marginBottom: 10 }}>
            {PREHISTORIC_AVATARS.map((item) => (
              <button
                key={item.id}
                onClick={() => saveAvatarState({ mode: 'icon', iconId: item.id, imageData: '' })}
                style={{
                  borderRadius: 999,
                  border: `1px solid ${avatarState.mode === 'icon' && avatarState.iconId === item.id ? 'var(--photon)' : 'var(--border)'}`,
                  background: 'rgba(255,255,255,0.03)',
                  color: 'var(--txt-sec)',
                  padding: '4px 9px',
                  fontSize: '0.72rem',
                  cursor: 'pointer',
                }}
              >
                {item.icon} {item.label}
              </button>
            ))}
          </div>
          <button
            onClick={randomizeIcon}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', borderRadius: 8, padding: '7px 10px', fontSize: '0.74rem', cursor: 'pointer' }}
          >
            <Shuffle size={13} /> Random icon
          </button>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <ShieldCheck size={15} color="var(--photon)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Profile + account status
            </p>
          </div>

          <div style={{ display: 'grid', gap: 10, marginBottom: 12 }}>
            <label style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Display name</span>
              <input value={profile.display_name || ''} onChange={(event) => setProfile((prev) => ({ ...prev, display_name: event.target.value }))} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)' }} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Email</span>
              <input value={profile.email || ''} onChange={(event) => setProfile((prev) => ({ ...prev, email: event.target.value }))} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)' }} />
            </label>
            <label style={{ display: 'grid', gap: 4 }}>
              <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Organization</span>
              <input value={profile.organization || ''} onChange={(event) => setProfile((prev) => ({ ...prev, organization: event.target.value }))} style={{ padding: '8px 10px', borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)' }} />
            </label>
          </div>
          <button
            onClick={saveProfile}
            disabled={saving}
            style={{
              display: 'inline-flex',
              alignItems: 'center',
              gap: 6,
              border: 'none',
              borderRadius: 8,
              background: 'linear-gradient(90deg, var(--photon), var(--cyan))',
              color: '#050608',
              fontWeight: 700,
              padding: '8px 12px',
              cursor: 'pointer',
              opacity: saving ? 0.7 : 1,
            }}
          >
            <Save size={13} /> {saving ? 'Saving…' : 'Save profile'}
          </button>

          <div style={{ marginTop: 12, display: 'grid', gap: 6, fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
            <div>Plan: <strong style={{ color: 'var(--txt-pri)' }}>{tierLabel}</strong></div>
            <div>Auth mode: <strong style={{ color: 'var(--txt-pri)' }}>{profileMeta?.auth_mode || entitlements?.auth_mode || 'local'}</strong></div>
            <div>Active account: <strong style={{ color: 'var(--txt-pri)' }}>{profileMeta?.active_account_id || entitlements?.active_account_id || 'default'}</strong></div>
            <div>Profile complete: <strong style={{ color: 'var(--txt-pri)' }}>{profileMeta?.profile_complete ? 'Yes' : 'Not yet'}</strong></div>
          </div>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Clock3 size={15} color="var(--cyan)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Activity snapshot
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(2, minmax(0, 1fr))', gap: 10 }}>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Hours in app</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{formatHours(activeSeconds)}h</p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Chat turns</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{chatTurns}</p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Completed lessons</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{completedLessons}</p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.68rem', color: 'var(--txt-mut)' }}>Lesson completion</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.05rem', fontWeight: 700, color: 'var(--txt-pri)' }}>{completionRate}%</p>
            </div>
          </div>
          <p style={{ margin: '10px 0 0', fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
            Persisted lesson chunks: <strong style={{ color: 'var(--txt-pri)' }}>{persistedLessons}</strong> · Total lessons tracked: <strong style={{ color: 'var(--txt-pri)' }}>{lessons.length}</strong>
          </p>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Target size={15} color="var(--amber)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Goal tracking
            </p>
          </div>
          <label style={{ display: 'grid', gap: 6, marginBottom: 12 }}>
            <span style={{ fontSize: '0.72rem', color: 'var(--txt-sec)' }}>Editable goals</span>
            <textarea
              value={goalDraft}
              onChange={(event) => setGoalDraft(event.target.value)}
              rows={4}
              placeholder="Add comma-separated learner goals"
              style={{ resize: 'vertical', padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', lineHeight: 1.5 }}
            />
          </label>
          <button
            onClick={saveGoals}
            disabled={goalSaving}
            style={{ display: 'inline-flex', alignItems: 'center', gap: 6, marginBottom: 12, border: 'none', borderRadius: 8, background: 'linear-gradient(90deg, var(--ember), var(--amber))', color: '#050608', fontWeight: 700, padding: '8px 12px', cursor: 'pointer', opacity: goalSaving ? 0.7 : 1 }}
          >
            <Save size={13} /> {goalSaving ? 'Saving goals…' : 'Save goals'}
          </button>
          {goalCards.length > 0 ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {goalCards.map((item) => (
                <div key={item.goal} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 8 }}>
                    <span style={{ color: 'var(--txt-pri)', fontSize: '0.78rem', fontWeight: 600 }}>{item.goal}</span>
                    <span style={{ color: item.tone, fontSize: '0.68rem', fontWeight: 700 }}>{item.status}</span>
                  </div>
                  <label style={{ display: 'flex', alignItems: 'center', gap: 8, fontSize: '0.72rem', color: 'var(--txt-sec)', cursor: 'pointer' }}>
                    <input
                      type="checkbox"
                      checked={Boolean(goalMilestones[item.goal])}
                      onChange={() => persistGoalMilestones({ ...goalMilestones, [item.goal]: !goalMilestones[item.goal] })}
                      style={{ accentColor: 'var(--amber)' }}
                    />
                    Milestone complete
                  </label>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
              Onboarding goals have not been set yet. Once goals are added, this space can track their momentum over time.
            </p>
          )}
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--violet)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Brain size={15} color="var(--violet)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Learning profile
            </p>
          </div>
          <div style={{ display: 'grid', gap: 8, fontSize: '0.76rem', color: 'var(--txt-sec)' }}>
            <div>Experience: <strong style={{ color: 'var(--txt-pri)' }}>{learnerExperience}</strong></div>
            <div>Pacing: <strong style={{ color: 'var(--txt-pri)' }}>{learnerPacing}</strong></div>
            <div>Style: <strong style={{ color: 'var(--txt-pri)' }}>{learnerStyle}</strong></div>
            <div>Lesson streak: <strong style={{ color: 'var(--txt-pri)' }}>{lessonStreak} day(s)</strong></div>
            <div>Current focus: <strong style={{ color: 'var(--txt-pri)' }}>{recentLessonTitle || 'No active lesson yet'}</strong></div>
          </div>

          {(focusAreas.length > 0 || weakConcepts.length > 0) && (
            <div style={{ marginTop: 12, display: 'grid', gap: 10 }}>
              {focusAreas.length > 0 && (
                <div>
                  <p style={{ margin: '0 0 6px', fontSize: '0.66rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Focus areas</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {focusAreas.map((item) => (
                      <span key={item} style={{ fontSize: '0.68rem', border: '1px solid rgba(180,124,255,0.35)', background: 'rgba(180,124,255,0.1)', color: 'var(--violet)', borderRadius: 999, padding: '3px 8px' }}>
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
              {weakConcepts.length > 0 && (
                <div>
                  <p style={{ margin: '0 0 6px', fontSize: '0.66rem', color: 'var(--txt-mut)', textTransform: 'uppercase', letterSpacing: '0.12em' }}>Coach recommends more reps on</p>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                    {weakConcepts.map((item) => (
                      <span key={item} style={{ fontSize: '0.68rem', border: '1px solid rgba(244,114,182,0.35)', background: 'rgba(244,114,182,0.1)', color: '#f472b6', borderRadius: 999, padding: '3px 8px' }}>
                        {item}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <BarChart3 size={15} color="var(--cyan)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Streak calendar heatmap
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(7, minmax(0, 1fr))', gap: 8 }}>
            {heatmapDays.map((day) => (
              <div key={day.date} title={`${day.date}: ${day.count} lesson update(s)`} style={{ display: 'grid', justifyItems: 'center', gap: 6 }}>
                <div
                  style={{
                    width: '100%',
                    aspectRatio: '1 / 1',
                    borderRadius: 8,
                    border: '1px solid rgba(255,255,255,0.06)',
                    background: day.count
                      ? `rgba(0,245,212,${0.15 + day.intensity * 0.75})`
                      : 'rgba(255,255,255,0.04)',
                    boxShadow: day.count ? '0 0 12px rgba(0,245,212,0.12)' : 'none',
                  }}
                />
                <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)' }}>{day.label}</span>
              </div>
            ))}
          </div>
          <p style={{ margin: '12px 0 0', fontSize: '0.74rem', color: 'var(--txt-mut)' }}>
            Current streak: <strong style={{ color: 'var(--txt-pri)' }}>{lessonStreak} day(s)</strong> · Recommended difficulty: <strong style={{ color: 'var(--txt-pri)' }}>{toTitle(recommendedDifficulty)}</strong>
          </p>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--photon)' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 12, flexWrap: 'wrap' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <BarChart3 size={15} color="var(--photon)" />
              <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
                Confidence over time
              </p>
            </div>
            <select
              value={selectedConfidenceConcept}
              onChange={(event) => {
                setSelectedConfidenceConcept(event.target.value)
                try {
                  window.localStorage.setItem(CONFIDENCE_CONCEPT_STORAGE_KEY, event.target.value)
                } catch {
                  // Keep the selection in memory if storage is unavailable.
                }
              }}
              style={{ borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-pri)', padding: '6px 10px', fontSize: '0.72rem' }}
            >
              {confidenceConceptOptions.length > 0 ? confidenceConceptOptions.map((concept) => (
                <option key={concept} value={concept}>{toTitle(concept)}</option>
              )) : <option value="">No concept data yet</option>}
            </select>
          </div>
          {confidenceSeries.length > 0 ? (
            <>
              <div style={{ display: 'flex', alignItems: 'flex-end', gap: 10, minHeight: 140 }}>
                {confidenceSeries.map((point) => (
                  <div key={`${point.label}-${point.timestamp}`} style={{ flex: 1, display: 'grid', justifyItems: 'center', gap: 6 }}>
                    <div
                      title={`${point.confidence}% confidence after ${point.label}`}
                      style={{
                        width: '100%',
                        maxWidth: 34,
                        height: `${Math.max(18, Math.round((point.confidence / 100) * 110))}px`,
                        borderRadius: 999,
                        background: point.passed ? 'linear-gradient(180deg, var(--photon), var(--cyan))' : 'rgba(244,114,182,0.7)',
                      }}
                    />
                    <span style={{ fontSize: '0.62rem', color: 'var(--txt-mut)' }}>{point.label}</span>
                  </div>
                ))}
              </div>
              <p style={{ margin: '10px 0 0', fontSize: '0.72rem', color: 'var(--txt-mut)' }}>
                Tracking <strong style={{ color: 'var(--txt-pri)' }}>{toTitle(selectedConfidenceConcept)}</strong> across recent attempts.
              </p>
            </>
          ) : (
            <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
              Confidence data will appear here after more repeated attempts on the same concept.
            </p>
          )}
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--violet)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <GitBranch size={15} color="var(--violet)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Memory mapping
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, minmax(0, 1fr))', gap: 10 }}>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.66rem', color: 'var(--txt-mut)' }}>Memory nodes</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.02rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{memoryNodes}</p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.66rem', color: 'var(--txt-mut)' }}>Memory links</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.02rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{memoryEdges}</p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: 0, fontSize: '0.66rem', color: 'var(--txt-mut)' }}>Mastery topics</p>
              <p style={{ margin: '6px 0 0', fontSize: '1.02rem', color: 'var(--txt-pri)', fontWeight: 700 }}>{masteryTopics.length}</p>
            </div>
          </div>
          <p style={{ margin: '12px 0 0', fontSize: '0.74rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
            This is the early shape of a learner knowledge map: what ATLAS has seen, connected, and practiced often enough to remember.
          </p>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Award size={15} color="var(--amber)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Trophy case
            </p>
          </div>
          {earnedAwards.length > 0 ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {earnedAwards.map((award) => (
                <div key={award.id} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid rgba(245,158,11,0.24)', background: 'rgba(245,158,11,0.08)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 4 }}>
                    <span style={{ fontSize: '1rem' }}>{award.icon}</span>
                    <span style={{ color: 'var(--txt-pri)', fontWeight: 700, fontSize: '0.78rem' }}>{award.title}</span>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{award.detail}</p>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
              Awards will unlock as the learner builds attempts, streaks, completions, and saved milestones.
            </p>
          )}
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--cyan)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Trophy size={15} color="var(--cyan)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Saved wins + breakthroughs
            </p>
          </div>
          {winsTimeline.length > 0 ? (
            <div style={{ display: 'grid', gap: 10 }}>
              {winsTimeline.map((win) => (
                <div key={win.id} style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: win.passed ? 'rgba(0,245,212,0.06)' : 'rgba(255,255,255,0.03)' }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 10, marginBottom: 6 }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                      {win.passed ? <CheckCircle2 size={14} color="var(--cyan)" /> : <Sparkles size={14} color="var(--violet)" />}
                      <span style={{ color: 'var(--txt-pri)', fontWeight: 600, fontSize: '0.78rem' }}>{win.title}</span>
                    </div>
                    <button
                      onClick={() => persistSavedWins({ ...savedWins, [win.id]: !savedWins[win.id] })}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: 4, borderRadius: 8, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: savedWins[win.id] ? 'var(--cyan)' : 'var(--txt-sec)', padding: '5px 8px', cursor: 'pointer', fontSize: '0.68rem' }}
                    >
                      {savedWins[win.id] ? <BookmarkCheck size={12} /> : <BookmarkPlus size={12} />}
                      {savedWins[win.id] ? 'Saved' : 'Save'}
                    </button>
                  </div>
                  <p style={{ margin: 0, fontSize: '0.72rem', color: 'var(--txt-sec)', lineHeight: 1.5 }}>{win.detail}</p>
                </div>
              ))}
            </div>
          ) : (
            <p style={{ margin: 0, fontSize: '0.76rem', color: 'var(--txt-mut)', lineHeight: 1.6 }}>
              Recent wins will show up here as soon as ATLAS has enough learner outcome history to summarize.
            </p>
          )}
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: '3px solid var(--amber)' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <Trophy size={15} color="var(--amber)" />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Onboarding to now
            </p>
          </div>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', gap: 10 }}>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: '0 0 6px', fontSize: '0.66rem', color: 'var(--txt-mut)' }}>Started with</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-pri)', lineHeight: 1.6 }}>
                {toTitle(learnerExperience)} experience · {toTitle(learnerPacing)} pace · {toTitle(learnerStyle)} learning style
              </p>
            </div>
            <div style={{ padding: '10px 12px', borderRadius: 10, border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)' }}>
              <p style={{ margin: '0 0 6px', fontSize: '0.66rem', color: 'var(--txt-mut)' }}>Now showing</p>
              <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--txt-pri)', lineHeight: 1.6 }}>
                {attempts} attempts · {completedLessons} completions · {weakConcepts.length} active concept(s) to reinforce
              </p>
            </div>
          </div>
        </div>

        <div className="glass-card-solid" style={{ padding: 18, borderLeft: `3px solid ${usageTone}` }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
            <BarChart3 size={15} color={usageTone} />
            <p style={{ margin: 0, fontSize: '0.72rem', textTransform: 'uppercase', letterSpacing: '0.12em', color: 'var(--txt-sec)', fontWeight: 700 }}>
              Usage + credit status
            </p>
          </div>

          <div style={{ marginBottom: 10, fontSize: '0.78rem', color: 'var(--txt-sec)' }}>
            Current monthly usage: <strong style={{ color: usageTone }}>{percentUsed}%</strong> ({billingUsage?.usage?.requests || 0}/{billingUsage?.usage?.request_limit || 0} requests)
          </div>
          <div style={{ height: 8, borderRadius: 999, background: 'rgba(255,255,255,0.08)', overflow: 'hidden', marginBottom: 10 }}>
            <div style={{ height: '100%', width: `${clampPercent(percentUsed)}%`, background: usageTone }} />
          </div>
          <p style={{ margin: 0, fontSize: '0.72rem', color: usageTone }}>
            {usageWarning === 'normal' && 'Usage is in a healthy range.'}
            {usageWarning === 'elevated' && 'Usage is getting close to your warning threshold.'}
            {usageWarning === 'critical' && 'Warning: usage is close to your plan limit.'}
            {usageWarning === 'blocked' && 'Limit reached. Upgrade or reduce usage to continue.'}
          </p>

          <div style={{ display: 'flex', gap: 8, marginTop: 14, flexWrap: 'wrap' }}>
            <button
              onClick={() => setPage?.('pricing')}
              style={{ border: '1px solid rgba(180,124,255,0.35)', background: 'rgba(180,124,255,0.08)', color: 'var(--violet)', borderRadius: 8, padding: '7px 10px', cursor: 'pointer', fontSize: '0.74rem', fontWeight: 600 }}
            >
              Manage plan
            </button>
            <button
              onClick={() => setPage?.('lessons')}
              style={{ border: '1px solid var(--border)', background: 'rgba(255,255,255,0.03)', color: 'var(--txt-sec)', borderRadius: 8, padding: '7px 10px', cursor: 'pointer', fontSize: '0.74rem', fontWeight: 600 }}
            >
              Continue learning
            </button>
          </div>
        </div>
      </div>

      {loading && (
        <div style={{ marginTop: 14, fontSize: '0.76rem', color: 'var(--txt-mut)', display: 'flex', alignItems: 'center', gap: 8 }}>
          <Sparkles size={13} /> Refreshing account data...
        </div>
      )}
    </div>
  )
}
