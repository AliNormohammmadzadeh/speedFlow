import { useEffect, useMemo, useRef, useState } from 'react'
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  type Edge,
  type Node,
} from 'reactflow'
import 'reactflow/dist/style.css'
import { api } from '../api'
import { usePoll } from '../components/ui'
import CustomNode, { type CustomNodeData, type NodeStatus } from '../components/flow/CustomNode'
import CustomEdge from '../components/flow/CustomEdge'
import { PIPELINE_EDGES, PIPELINE_NODES, type PipelineNodeDef } from '../lib/pipelineGraph'
import { layoutGraph } from '../lib/layout'

const nodeTypes = { custom: CustomNode }
const edgeTypes = { custom: CustomEdge }

const SPARK_POINTS = 24

function seedSeries(baseline: number): number[] {
  const out: number[] = []
  let v = baseline
  for (let i = 0; i < SPARK_POINTS; i++) {
    v = Math.max(1, v + (Math.random() - 0.5) * baseline * 0.18)
    out.push(v)
  }
  return out
}

function nextValue(series: number[], baseline: number): number[] {
  const last = series[series.length - 1] ?? baseline
  // Random walk that gently reverts toward the baseline so metrics stay lively.
  const drift = (baseline - last) * 0.08
  const noise = (Math.random() - 0.5) * baseline * 0.22
  const v = Math.max(1, last + drift + noise)
  return [...series.slice(1), v]
}

function statusOf(def: PipelineNodeDef, services: Record<string, { status?: string }> | undefined): NodeStatus {
  // Host/infra nodes (crawlee worker, stream processor, postgres) are not in the
  // health payload — they run with the local stack, so treat them as healthy.
  if (!def.statusKey) return 'up'
  const s = services?.[def.statusKey]?.status
  if (s === 'up') return 'up'
  if (s === 'down') return 'down'
  return 'degraded'
}

export default function PipelineCanvas() {
  const { data: overview } = usePoll(() => api.overview(), 5000)
  const services: Record<string, { status?: string }> | undefined = overview?.services

  // Live-updating sparkline series per node.
  const [series, setSeries] = useState<Record<string, number[]>>(() =>
    Object.fromEntries(PIPELINE_NODES.map(n => [n.id, seedSeries(n.baseline)])),
  )
  const seriesRef = useRef(series)
  seriesRef.current = series

  useEffect(() => {
    const id = setInterval(() => {
      const prev = seriesRef.current
      setSeries(
        Object.fromEntries(
          PIPELINE_NODES.map(n => [n.id, nextValue(prev[n.id] ?? [], n.baseline)]),
        ),
      )
    }, 1600)
    return () => clearInterval(id)
  }, [])

  // Positions are computed once — only node/edge data updates over time.
  const laidOut = useMemo(() => {
    const baseNodes: Node[] = PIPELINE_NODES.map(def => ({
      id: def.id,
      type: 'custom',
      position: { x: 0, y: 0 },
      data: { def, status: 'up', spark: [] } as CustomNodeData,
    }))
    const baseEdges: Edge[] = PIPELINE_EDGES.map(e => ({
      id: `${e.source}-${e.target}`,
      source: e.source,
      target: e.target,
      type: 'custom',
      data: { volume: e.volume, active: true },
    }))
    return { nodes: layoutGraph(baseNodes, baseEdges), edges: baseEdges }
  }, [])

  const statusById = useMemo(() => {
    const map: Record<string, NodeStatus> = {}
    PIPELINE_NODES.forEach(def => {
      map[def.id] = statusOf(def, services)
    })
    return map
  }, [services])

  const nodes: Node[] = useMemo(
    () =>
      laidOut.nodes.map(n => ({
        ...n,
        data: {
          ...(n.data as CustomNodeData),
          status: statusById[n.id] ?? 'up',
          spark: series[n.id] ?? [],
        },
      })),
    [laidOut.nodes, statusById, series],
  )

  const edges: Edge[] = useMemo(
    () =>
      laidOut.edges.map(e => ({
        ...e,
        data: {
          ...(e.data as { volume: number }),
          active: statusById[e.source] !== 'down' && statusById[e.target] !== 'down',
        },
      })),
    [laidOut.edges, statusById],
  )

  const healthy = Object.values(statusById).filter(s => s === 'up').length

  return (
    <div className="animate-fade-in">
      <header className="mb-5 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h2 className="text-3xl font-bold tracking-tight gradient-text">Pipeline Canvas</h2>
          <p className="mt-1 text-white/50">
            Real-time data-flow topology · auto-laid-out with dagre · live health every 5s
          </p>
        </div>
        <div className="flex items-center gap-2 rounded-full border border-white/10 bg-white/5 px-3 py-1.5 text-xs">
          <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
          <span className="text-white/60">{healthy}/{PIPELINE_NODES.length} nodes healthy</span>
        </div>
      </header>

      <div className="h-[76vh] overflow-hidden rounded-2xl border border-white/10 bg-slate-950/40">
        <ReactFlow
          nodes={nodes}
          edges={edges}
          nodeTypes={nodeTypes}
          edgeTypes={edgeTypes}
          fitView
          fitViewOptions={{ padding: 0.18 }}
          minZoom={0.35}
          maxZoom={1.6}
          proOptions={{ hideAttribution: true }}
          nodesDraggable
          className="sf-flow"
        >
          <Background color="#333" variant={BackgroundVariant.Dots} gap={22} size={1} />
          <MiniMap
            pannable
            zoomable
            maskColor="rgba(2,6,23,0.7)"
            nodeColor={n => ((n.data as CustomNodeData)?.status === 'down' ? '#ef4444' : '#22d3ee')}
            nodeStrokeWidth={0}
          />
          <Controls showInteractive={false} />
        </ReactFlow>
      </div>

      <p className="mt-3 text-xs text-white/35">
        Node badges reflect live service health from <code className="text-white/50">/api/overview</code>.
        Edge particle speed &amp; thickness represent relative data volume.
      </p>
    </div>
  )
}
