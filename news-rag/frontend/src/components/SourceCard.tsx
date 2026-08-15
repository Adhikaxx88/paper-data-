import { useState } from 'react'
import { ChevronDown, ChevronRight } from 'lucide-react'
import type { Source } from '../types'

interface SourceCardProps {
  source: Source
}

export function SourceCard({ source }: SourceCardProps) {
  const [expanded, setExpanded] = useState(false)
  const relevancePercent = Math.round(Math.max(0, Math.min(1, source.score)) * 100)

  return (
    <div className="rounded-lg border border-gray-200 bg-gray-50 text-sm">
      <button
        type="button"
        onClick={() => setExpanded((prev) => !prev)}
        className="flex w-full items-center gap-2 px-3 py-2 text-left text-gray-700"
      >
        {expanded ? <ChevronDown size={14} /> : <ChevronRight size={14} />}
        <span className="truncate font-medium">{source.title}</span>
      </button>
      {expanded && (
        <div className="space-y-2 px-3 pb-3">
          <div className="text-gray-500">
            {source.source} · {source.date}
          </div>
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-gray-200">
            <div className="h-full rounded-full bg-blue-500" style={{ width: `${relevancePercent}%` }} />
          </div>
          <div className="text-xs text-gray-400">Relevansi: {relevancePercent}%</div>
        </div>
      )}
    </div>
  )
}
