import { useState } from 'react'
import { api } from '../api/client'
import LessonContent from './LessonContent'

export default function CurriculumArtifactPanel({ curriculum, onStart, onSaved, alreadySaved = false }) {
  const [course, setCourse] = useState(curriculum)
  const [saved, setSaved] = useState(alreadySaved)
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState('')
  const [notice, setNotice] = useState('')
  const ready = course.quality?.ready === true
  const save = async () => {
    setBusy(true)
    setError('')
    try {
      const result = await api('/atlas/curricula', { method: 'POST', body: { curriculum: course } })
      setCourse(result.curriculum)
      setSaved(true)
      setNotice('Saved to your curricula.')
      onSaved?.()
    } catch (cause) {
      setError(cause.message || 'Could not save this curriculum.')
    } finally { setBusy(false) }
  }
  const start = async () => {
    setBusy(true)
    setError('')
    try {
      await onStart(course.curriculum_id)
    } catch (cause) {
      setError(cause.message || 'Could not start this curriculum.')
    } finally { setBusy(false) }
  }
  const download = () => {
    const url = URL.createObjectURL(new Blob([JSON.stringify(course, null, 2)], { type: 'application/json' }))
    const anchor = document.createElement('a')
    anchor.href = url
    anchor.download = 'atlas-curriculum.json'
    anchor.click()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
  }
  return (
    <article aria-label="Curriculum preview" style={{ minWidth: 0, overflowWrap: 'anywhere', fontSize: '0.82rem' }}>
      <h2 style={{ margin: '0 0 8px', fontSize: '1rem' }}>{course.title || course.subject}</h2>
      <p>{ready ? 'Ready for learner review' : 'Draft: teaching content needs review or regeneration'}</p>
      <p style={{ color: 'var(--txt-sec)' }}>Automated checks do not verify factual accuracy or confer professional certification. Duration is an estimate.</p>
      {course.generation_warnings?.length > 0 && <details><summary>Generation warnings ({course.generation_warnings.length})</summary><ul>{course.generation_warnings.map((warning, index) => <li key={index}>{warning}</li>)}</ul></details>}
      {(course.modules || []).map((module, index) => (
        <details key={module.module_id || index} style={{ margin: '10px 0' }}>
          <summary>{module.title} ({module.lessons?.length || 0} lessons)</summary>
          {(module.lessons || []).map((lesson, lessonIndex) => {
            const quality = course.quality?.lessons?.find(item => item.lesson_id === lesson.lesson_id)
            return <details key={lesson.lesson_id || lessonIndex} style={{ padding: '8px 12px' }}>
              <summary>{lesson.title}{quality?.ready === false ? ' - needs work' : ''}</summary>
              <p>{lesson.summary}</p>
              <ul>{(lesson.objectives || []).map((objective, itemIndex) => <li key={itemIndex}>{objective}</li>)}</ul>
              {lesson.content ? <LessonContent content={lesson.content} /> : <p>No authored teaching content yet.</p>}
              {quality?.errors?.length > 0 && <ul>{quality.errors.map((issue, itemIndex) => <li key={itemIndex}>{issue}</li>)}</ul>}
            </details>
          })}
        </details>
      ))}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginTop: 12 }}>
        <button type="button" onClick={save} disabled={busy}>{saved ? 'Save again' : 'Save to my curricula'}</button>
        {onStart && <button type="button" onClick={start} disabled={busy || !saved || !ready}>Start this curriculum</button>}
        <button type="button" onClick={download}>Download curriculum JSON</button>
      </div>
      {onStart && <p>Review and save before starting. Start begins at the first lesson and replaces your active lesson; your learning history is retained. Use Lesson &amp; practice to continue your current course.</p>}
      {notice && <p role="status">{notice}</p>}
      {error && <p role="alert">{error}</p>}
    </article>
  )
}
