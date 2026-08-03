export async function api(path, options = {}) {
  const res = await fetch(`/api${path}`, {
    headers: { 'Content-Type': 'application/json', ...options.headers },
    ...options,
    body: options.body ? JSON.stringify(options.body) : undefined,
  })
  if (!res.ok) throw new Error(await res.text())
  return res.json()
}

export function openTerminalWS() {
  const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:'
  return new WebSocket(`${protocol}//${location.host}/ws/terminal`)
}
