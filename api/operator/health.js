import { readFileSync, writeFileSync, existsSync } from 'fs'
import path from 'path'

const FILE = path.join(process.cwd(), '.mammoth', 'operator_health.json')

export async function getOperatorHealth() {
  if (!existsSync(FILE)) {
    return {
      energy: 50,
      focus: 50,
      mood: 50,
      stress: 50,
      sleep: 50,
      uptime: 0,
      fatigue: 0,
      history: []
    }
  }
  return JSON.parse(readFileSync(FILE, 'utf8'))
}

export async function setOperatorHealth(payload) {
  const current = await getOperatorHealth()
  const updated = {
    ...current,
    ...payload,
    history: [
      ...current.history,
      { ts: Date.now(), ...payload }
    ]
  }
  writeFileSync(FILE, JSON.stringify(updated, null, 2))
  return updated
}

export default async function handler(req, res) {
  if (req.method === 'GET') {
    const data = await getOperatorHealth()
    return res.status(200).json(data)
  }

  if (req.method === 'POST') {
    const updated = await setOperatorHealth(req.body)
    return res.status(200).json(updated)
  }

  res.status(405).end()
}
