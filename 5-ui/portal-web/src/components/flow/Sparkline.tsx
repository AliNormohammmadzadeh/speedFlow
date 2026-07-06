import { useId } from 'react'

/**
 * Minimal SVG sparkline used inside pipeline nodes. Renders a smoothed line plus
 * a subtle filled area and a leading dot at the latest value.
 */
export default function Sparkline({
  data,
  width = 104,
  height = 34,
  color = '#22d3ee',
  muted = false,
}: {
  data: number[]
  width?: number
  height?: number
  color?: string
  muted?: boolean
}) {
  const gradientId = useId()
  const stroke = muted ? '#64748b' : color

  if (data.length < 2) {
    return <svg width={width} height={height} aria-hidden="true" />
  }

  const max = Math.max(...data)
  const min = Math.min(...data)
  const range = max - min || 1
  const step = width / (data.length - 1)

  const points = data.map((v, i) => {
    const x = i * step
    const y = height - ((v - min) / range) * (height - 6) - 3
    return [x, y] as const
  })

  const line = points.map(([x, y], i) => `${i === 0 ? 'M' : 'L'}${x.toFixed(1)} ${y.toFixed(1)}`).join(' ')
  const area = `${line} L ${width} ${height} L 0 ${height} Z`
  const [lastX, lastY] = points[points.length - 1]

  return (
    <svg width={width} height={height} className="overflow-visible" aria-hidden="true">
      <defs>
        <linearGradient id={gradientId} x1="0" y1="0" x2="0" y2="1">
          <stop offset="0%" stopColor={stroke} stopOpacity={muted ? 0.15 : 0.35} />
          <stop offset="100%" stopColor={stroke} stopOpacity="0" />
        </linearGradient>
      </defs>
      <path d={area} fill={`url(#${gradientId})`} />
      <path
        d={line}
        fill="none"
        stroke={stroke}
        strokeWidth={1.5}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
      <circle cx={lastX} cy={lastY} r={2.2} fill={stroke} />
    </svg>
  )
}
