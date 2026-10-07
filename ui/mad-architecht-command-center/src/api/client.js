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

function buildBackendErrorMessage(status, text, requestUrl = '') {
  const body = String(text || '').trim()
  const maybeHtml = body.startsWith('<') || /<!doctype html>|<html/i.test(body)
  if (maybeHtml) {
    let path = '/api'
    try { path = new URL(requestUrl, window.location.origin).pathname } catch { /* diagnostic URL unavailable */ }
    const detail = `HTTP ${status} at ${path}.`
    if ([502, 503, 504].includes(status)) {
      return `The API gateway returned an HTML error page (${detail}) ${status === 504 ? 'The upstream request timed out.' : 'The backend was unavailable.'} This does not establish a missing frontend environment variable. Check server/proxy logs before retrying; no automatic retry was made.`
    }
    return `Expected API JSON but received HTML (${detail}) Check API routing, redirects, and server logs. A frontend API-origin setting is needed only if this site uses a separate API origin; same-origin deployments do not require it.`
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
    throw new Error(buildBackendErrorMessage(res.status, text, res.url))
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
    throw new Error(buildBackendErrorMessage(res.status, text, res.url))
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
