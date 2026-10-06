import { useEffect, useRef, useState } from 'react'
import { api, buildApiUrl } from '../api/client'
import { getAccessToken } from '../lib/supabase'

export default function useDocumentUpload(scope, onUploaded) {
  const [policy, setPolicy] = useState(null)
  const [policyError, setPolicyError] = useState('')
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(false)
  const request = useRef(null)
  const stopped = useRef(false)
  const mounted = useRef(true)
  const retryFiles = useRef([])

  const loadPolicy = async () => {
    setPolicyError('')
    try {
      const result = await api(`/${scope}/files/capabilities`)
      if (!Array.isArray(result?.extensions) || !(result.max_file_bytes > 0)) throw new Error('Upload capabilities are unavailable.')
      if (mounted.current) setPolicy(result)
    } catch (cause) {
      if (mounted.current) { setPolicy(null); setPolicyError(cause.message || 'Could not load upload limits.') }
    }
  }

  useEffect(() => {
    mounted.current = true
    loadPolicy()
    return () => { mounted.current = false; stopped.current = true; request.current?.abort() }
  }, [scope])

  const upload = async (files, tag = 'other') => {
    if (!policy || busy) return
    stopped.current = false
    retryFiles.current = []
    setBusy(true)
    setItems(files.map((file, index) => ({ id: index, name: file.name, state: 'queued', progress: 0 })))
    const update = (id, value) => { if (mounted.current) setItems(previous => previous.map(item => item.id === id ? { ...item, ...value } : item)) }
    for (const [id, file] of files.entries()) {
      if (stopped.current) { update(id, { state: 'cancelled', error: 'Cancelled. Refresh the library before retrying if processing had started.' }); continue }
      try {
        if (file.size > policy.max_file_bytes) throw new Error(`Exceeds the ${Math.round(policy.max_file_bytes / 1048576)} MB limit.`)
        const extension = '.' + file.name.split('.').pop().toLowerCase()
        if (!policy.extensions.includes(extension)) throw new Error('Unsupported file type.')
        update(id, { state: 'uploading' })
        const token = await getAccessToken()
        if (stopped.current) throw new Error('Upload cancelled.')
        const data = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest()
          request.current = xhr
          xhr.open('POST', buildApiUrl(`/${scope}/files/upload`))
          if (token) xhr.setRequestHeader('Authorization', `Bearer ${token}`)
          xhr.upload.onprogress = event => {
            if (event.lengthComputable) update(id, { progress: Math.round(event.loaded / event.total * 100), state: event.loaded === event.total ? 'processing' : 'uploading' })
          }
          xhr.onload = () => {
            try {
              const result = JSON.parse(xhr.responseText)
              if (xhr.status < 200 || xhr.status >= 300 || result.status !== 'ok') throw new Error(result.error || 'Upload failed.')
              resolve(result)
            } catch (cause) { reject(new Error(cause instanceof SyntaxError ? 'Server returned an invalid upload response.' : cause.message)) }
          }
          xhr.onerror = () => reject(new Error('Connection lost during upload. Refresh the library before retrying.'))
          xhr.onabort = () => reject(new Error('Cancelled. Refresh the library before retrying if processing had started.'))
          xhr.timeout = 120000
          xhr.ontimeout = () => reject(new Error('Upload timed out. Refresh the library before retrying.'))
          const form = new FormData()
          form.append('file', file)
          if (scope === 'atlas') form.append('tag', tag)
          xhr.send(form)
        })
        if (mounted.current) {
          onUploaded(data)
          update(id, { state: data.processing_status, progress: 100, warnings: data.warnings })
        }
      } catch (cause) {
        retryFiles.current.push(file)
        update(id, { state: stopped.current ? 'cancelled' : 'failed', error: cause.message || 'Upload failed.' })
      } finally {
        request.current = null
      }
    }
    if (mounted.current) { setBusy(false); loadPolicy() }
  }

  return { policy, policyError, items, busy, loadPolicy, upload,
    cancel: () => { stopped.current = true; request.current?.abort() },
    retry: tag => upload(retryFiles.current, tag),
  }
}
