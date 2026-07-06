import { BaseEdge, getBezierPath, type EdgeProps } from 'reactflow'

export type CustomEdgeData = {
  /** Relative data volume 1..10 — thicker + faster particles for higher volume. */
  volume: number
  active: boolean
}

export default function CustomEdge({
  id,
  sourceX,
  sourceY,
  targetX,
  targetY,
  sourcePosition,
  targetPosition,
  data,
}: EdgeProps<CustomEdgeData>) {
  const [path] = getBezierPath({
    sourceX,
    sourceY,
    sourcePosition,
    targetX,
    targetY,
    targetPosition,
  })

  const volume = data?.volume ?? 3
  const active = data?.active ?? true

  // Higher volume → thicker line, longer particles, and a faster animation.
  const width = 1 + Math.min(4, volume / 2.4)
  const dash = Math.max(2, volume * 0.8)
  const duration = Math.max(0.55, 2.4 - volume * 0.18)
  const color = active ? '#22d3ee' : '#475569'

  return (
    <>
      <BaseEdge
        id={id}
        path={path}
        style={{
          stroke: active ? 'rgba(148,163,184,0.22)' : 'rgba(71,85,105,0.2)',
          strokeWidth: width,
        }}
      />
      {active && (
        <path
          d={path}
          fill="none"
          stroke={color}
          strokeWidth={width}
          strokeLinecap="round"
          strokeDasharray={`${dash} 16`}
          className="sf-edge-flow"
          style={{
            animationDuration: `${duration}s`,
            filter: `drop-shadow(0 0 4px ${color})`,
          }}
        />
      )}
    </>
  )
}
