import { memo } from 'react'
import { Handle, Position, type NodeProps } from 'reactflow'
import type { PipelineNodeDef } from '../../lib/pipelineGraph'
import Sparkline from './Sparkline'

export type NodeStatus = 'up' | 'degraded' | 'down'

export type CustomNodeData = {
  def: PipelineNodeDef
  status: NodeStatus
  spark: number[]
}

const STATUS_META: Record<NodeStatus, { label: string; dot: string; text: string; ring: string; pulse: boolean }> = {
  up: { label: 'Healthy', dot: 'bg-emerald-400', text: 'text-emerald-300', ring: 'ring-emerald-400/50', pulse: true },
  degraded: { label: 'Lagging', dot: 'bg-amber-400', text: 'text-amber-300', ring: 'ring-amber-400/50', pulse: true },
  down: { label: 'Offline', dot: 'bg-red-400', text: 'text-red-300', ring: 'ring-red-400/40', pulse: false },
}

function CustomNode({ data, selected }: NodeProps<CustomNodeData>) {
  const { def, status, spark } = data
  const meta = STATUS_META[status]
  const Icon = def.icon
  const active = status !== 'down'
  const latest = spark.length ? spark[spark.length - 1] : def.baseline

  return (
    <div
      className={`group relative w-[240px] overflow-hidden rounded-xl border bg-slate-900/80 p-4 backdrop-blur-xl transition-all duration-300
        ${active ? 'border-slate-700' : 'border-slate-800/70 opacity-70'}
        ${selected ? 'ring-2 ring-cyan-400/60' : ''}`}
      style={active ? { boxShadow: `0 0 26px -8px ${def.glow}` } : undefined}
    >
      {/* Glowing gradient border sheen for active nodes */}
      {active && (
        <div
          className={`pointer-events-none absolute inset-0 rounded-xl bg-gradient-to-br ${def.accent} opacity-[0.07]`}
        />
      )}

      <Handle
        type="target"
        position={Position.Left}
        className="!h-2 !w-2 !-left-1 !border-0 !bg-slate-500"
      />
      <Handle
        type="source"
        position={Position.Right}
        className="!h-2 !w-2 !-right-1 !border-0 !bg-slate-500"
      />

      <div className="relative flex items-start gap-3">
        <div className={`inline-flex shrink-0 rounded-lg bg-gradient-to-br ${def.accent} p-2 shadow-lg`}>
          <Icon className="h-4 w-4 text-white" />
        </div>
        <div className="min-w-0 flex-1">
          <h3 className="truncate text-sm font-semibold text-slate-100">{def.label}</h3>
          <p className="truncate text-[11px] text-slate-400">{def.subtitle}</p>
        </div>
        <span
          className={`inline-flex shrink-0 items-center gap-1.5 rounded-full bg-slate-950/50 px-2 py-0.5 text-[10px] font-medium ring-1 ${meta.ring} ${meta.text}`}
        >
          <span className={`h-1.5 w-1.5 rounded-full ${meta.dot} ${meta.pulse ? 'animate-pulse' : ''}`} />
          {meta.label}
        </span>
      </div>

      <div className="relative mt-3 flex items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-[10px] uppercase tracking-wider text-slate-500">{def.metric}</p>
          <p className="text-lg font-bold leading-none text-slate-100">
            {Math.round(latest)}
            <span className="ml-1 text-[10px] font-normal text-slate-500">{def.unit}</span>
          </p>
        </div>
        <Sparkline data={spark} muted={!active} />
      </div>
    </div>
  )
}

export default memo(CustomNode)
