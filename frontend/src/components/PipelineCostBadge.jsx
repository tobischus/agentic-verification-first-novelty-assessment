import { useEffect, useState } from 'react'
import { api } from '../api'

const usd = (v) => '$' + (Number(v || 0)).toFixed(4)

// Running token/cost total for the WHOLE run so far (document processing, claim
// extraction, retrieval, review) -- the same badge is shown on every tab so the
// reviewer can see, at any point, what the run has cost up to now.
export default function PipelineCostBadge({ submissionId, refreshKey }) {
  const [cost, setCost] = useState(null)

  useEffect(() => {
    let cancelled = false
    api.pipelineCost(submissionId).then((d) => { if (!cancelled) setCost(d) }).catch(() => {})
    return () => { cancelled = true }
  }, [submissionId, refreshKey])

  if (!cost || cost.total_usd <= 0) return null
  const toks = (cost.total_prompt_tokens || 0) + (cost.total_completion_tokens || 0)
  return (
    <div className="cost-badge" title="Total token cost of the run so far (document processing, claims, retrieval, review)">
      💰 {usd(cost.total_usd)}
      <span className="cost-tok">{toks.toLocaleString()} tok · {cost.model}</span>
    </div>
  )
}
