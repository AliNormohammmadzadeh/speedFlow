# SpeedFlow Control Portal (Web)

React + Vite + Tailwind single-page app for operating and visualizing the
SpeedFlow platform. Served in production by `portal-api` (FastAPI) at
`http://localhost:8030`.

---

## Run

From the repository root, the simplest path is:

```bash
./run.sh            # builds this UI + starts the whole platform
```

See [`../../QUICKSTART.md`](../../QUICKSTART.md) and [`../../README.md`](../../README.md)
for the full stack.

### UI-only workflows

```bash
npm install                 # install dependencies
npm run build               # production build → dist/ (served by portal-api)
npm run dev                 # hot-reload dev server on http://localhost:5173
```

`npm run dev` proxies `/api/*` to `http://localhost:8030` (see `vite.config.ts`),
so run the backend (`make start-local`) first, then develop the UI with
hot-reload against live data.

> `portal-api` serves the built `dist/` directory and falls back to `index.html`
> for client-side routes (e.g. `/canvas`), so deep links and refreshes work.
> After changing UI code you must `npm run build` for the served bundle to update.

---

## Pipeline Canvas

Route: `/canvas` — an interactive, real-time [React Flow](https://reactflow.dev)
visualization of the data pipeline.

| Feature | Where |
|---------|-------|
| Auto-layout (left → right) with `dagre` | `src/lib/layout.ts` |
| Graph topology (nodes + edges + volumes) | `src/lib/pipelineGraph.ts` |
| Bento-card node (icon, live status badge, sparkline) | `src/components/flow/CustomNode.tsx` |
| SVG sparkline | `src/components/flow/Sparkline.tsx` |
| Bezier edge with animated particle flow | `src/components/flow/CustomEdge.tsx` |
| Canvas page (Background dots, MiniMap, Controls, polling) | `src/pages/PipelineCanvas.tsx` |
| Dark MiniMap/Controls + edge-flow keyframes | `src/index.css` (`.sf-flow`, `sf-edge-flow`) |

**Behavior**

- **Live health** — node status badges (`Healthy` / `Lagging` / `Offline`) come
  from `GET /api/overview` (polled every 5s). Nodes without a backing health
  endpoint (host workers, Postgres) are treated as healthy while the local stack
  runs. Edges into an offline node dim and stop animating.
- **Metrics** — the sparklines and the headline number are a lightweight,
  client-side mocked time series (a baseline random-walk per node, refreshed
  every ~1.6s) to convey throughput/CPU. They are illustrative, not sourced from
  real metrics.
- **Data volume** — each edge has a relative `volume` (1–10) that drives its
  thickness and particle speed; higher volume = thicker, faster particles.

**Extending the graph** — add a node to `PIPELINE_NODES` and any edges to
`PIPELINE_EDGES` in `src/lib/pipelineGraph.ts`; layout, rendering and status
wiring are automatic. Set a node's `statusKey` to a key in the `/api/overview`
`services` map to bind it to live health.

---

## Project layout

```
src/
├── App.tsx                    # routes
├── api.ts                     # typed fetch wrappers for /api/*
├── components/
│   ├── Layout.tsx             # sidebar nav, header, health badge
│   ├── DetailDrawer.tsx       # slide-in detail panel
│   ├── ui.tsx                 # shared primitives (usePoll, Card, StatusBadge…)
│   └── flow/                  # Pipeline Canvas node/edge/sparkline components
├── lib/
│   ├── serviceMeta.ts         # service/worker/topic metadata
│   ├── pipelineGraph.ts       # Pipeline Canvas graph definition
│   └── layout.ts              # dagre auto-layout
└── pages/                     # Overview, PipelineCanvas, Ingestion, Stream, …
```
