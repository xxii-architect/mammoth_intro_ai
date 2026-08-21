import { getAccessToken } from '../lib/supabase'

function normalizePath(path) {
  return path.startsWith('/') ? path : `/${path}`
}

function normalizeBackendBase(rawBase) {
  if (!rawBase) return ''
  return rawBase.trim().replace(/\/+$/, '').replace(/\/api$/, '')
}

function readBackendBase() {
  if (import.meta.env.VITE_MAMMOTH_API_BASE_URL) return import.meta.env.VITE_MAMMOTH_API_BASE_URL
  if (import.meta.env.VITE_MAMMOTH_BACKEND_URL) return import.meta.env.VITE_MAMMOTH_BACKEND_URL
  if (typeof window !== 'undefined') {
    const localOverride = window.localStorage.getItem('mammoth_api_base_url')
    if (localOverride) return localOverride
  }
  return ''
}

const BACKEND_BASE = normalizeBackendBase(readBackendBase())

export function buildApiUrl(path) {
  const normalizedPath = normalizePath(path)
  return BACKEND_BASE ? `${BACKEND_BASE}/api${normalizedPath}` : `/api${normalizedPath}`
}

export function buildWsUrl(path) {
  const normalizedPath = normalizePath(path)
  if (!BACKEND_BASE) {
    const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
    return `${protocol}//${window.location.host}${normalizedPath}`
  }

  const wsBase = BACKEND_BASE.replace(/^http:/, 'ws:').replace(/^https:/, 'wss:')
  return `${wsBase}${normalizedPath}`
}

function buildBackendErrorMessage(status, text) {
  const body = String(text || '').trim()
  const maybeHtml = body.startsWith('<') || /<!doctype html>|<html/i.test(body)
  if (maybeHtml) {
    return 'Backend returned HTML instead of JSON. Set VITE_MAMMOTH_API_BASE_URL (or VITE_MAMMOTH_BACKEND_URL) to your deployed API origin, or set localStorage.mammoth_api_base_url for this browser session.'
  }
  return body || `Request failed (${status})`
}

async function parseApiResponse(res) {
  if (res.status === 204) {
    return null
  }

  const contentType = res.headers.get('content-type') || ''
  const text = await res.text()

  if (!res.ok) {
    throw new Error(buildBackendErrorMessage(res.status, text))
  }

  if (!text) {
    return null
  }

  if (contentType.includes('application/json')) {
    try {
      return JSON.parse(text)
    } catch {
      throw new Error('Backend returned invalid JSON.')
    }
  }

  if (/<!doctype html>|<html/i.test(text)) {
    throw new Error(buildBackendErrorMessage(res.status, text))
  }

  return text
}

export async function authorizedFetch(path, options = {}) {
  const token = await getAccessToken()
  const headers = new Headers(options.headers || {})
  if (token) {
    headers.set('Authorization', `Bearer ${token}`)
  }
  return fetch(buildApiUrl(path), { ...options, headers })
}

export async function api(path, options = {}) {
  const headers = new Headers(options.headers || {})
  const requestOptions = { ...options, headers }

  if (options.body !== undefined && !(options.body instanceof FormData)) {
    if (!headers.has('Content-Type')) {
      headers.set('Content-Type', 'application/json')
    }
    requestOptions.body = typeof options.body === 'string' ? options.body : JSON.stringify(options.body)
  }

  const res = await authorizedFetch(path, requestOptions)
  return parseApiResponse(res)
}

export function openTerminalWS(token = '') {
  const wsUrl = buildWsUrl('/ws/terminal')
  const fullUrl = token
    ? `${wsUrl}${wsUrl.includes('?') ? '&' : '?'}access_token=${encodeURIComponent(token)}`
    : wsUrl
  return new WebSocket(fullUrl)
}
