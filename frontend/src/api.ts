import type { Bootstrap, RunSnapshot } from './types'

async function json<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const detail = await res.text().catch(() => '')
    throw new Error(`${res.status} ${res.statusText}${detail ? ` — ${detail}` : ''}`)
  }
  return (await res.json()) as T
}

export const api = {
  bootstrap: () => fetch('/api/bootstrap').then(json<Bootstrap>),

  startRun: (body: {
    scenario: string
    backend: string
    variant: string
    human_in_the_loop: boolean
    pressure: string
  }) =>
    fetch('/api/runs', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body),
    }).then(json<{ run_id: string; status: string }>),

  snapshot: (runId: string) => fetch(`/api/runs/${runId}`).then(json<RunSnapshot>),

  decide: (runId: string, choice: string) =>
    fetch(`/api/runs/${runId}/decide`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ choice }),
    }).then(json<{ ok: boolean; choice: string }>),
}
