import dagre from 'dagre'
import { Position, type Edge, type Node } from 'reactflow'

export const NODE_WIDTH = 240
export const NODE_HEIGHT = 132

/**
 * Auto-position nodes left → right with dagre so the graph never needs manual
 * dragging. Returns a new array of nodes with computed `position` plus fixed
 * source/target handle sides.
 */
export function layoutGraph(nodes: Node[], edges: Edge[]): Node[] {
  const g = new dagre.graphlib.Graph()
  g.setDefaultEdgeLabel(() => ({}))
  g.setGraph({ rankdir: 'LR', nodesep: 44, ranksep: 110, marginx: 24, marginy: 24 })

  nodes.forEach(n => g.setNode(n.id, { width: NODE_WIDTH, height: NODE_HEIGHT }))
  edges.forEach(e => g.setEdge(e.source, e.target))

  dagre.layout(g)

  return nodes.map(n => {
    const { x, y } = g.node(n.id)
    return {
      ...n,
      sourcePosition: Position.Right,
      targetPosition: Position.Left,
      position: { x: x - NODE_WIDTH / 2, y: y - NODE_HEIGHT / 2 },
    }
  })
}
