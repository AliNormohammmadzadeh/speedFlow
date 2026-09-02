import { useEffect, useRef, useState } from 'react'
import type { ReactNode } from 'react'
import { Link, useNavigate } from 'react-router-dom'
import {
  Activity,
  ArrowRight,
  Boxes,
  BrainCircuit,
  Building2,
  CandlestickChart,
  Cloud,
  Cpu,
  Database,
  Gamepad2,
  Layers,
  LineChart,
  Radio,
  Rocket,
  ShieldCheck,
  Sparkles,
  Users,
  Workflow,
  Zap,
} from 'lucide-react'
import { api } from '../api'

type MvpStatus = {
  services_up: number
  services_total: number
  capabilities_ready: number
  capabilities_total: number
  metrics: { tenants: number; completed_jobs: number; total_jobs: number; brain_objectives: number; schemas: number }
}

/* ---------- small building blocks ---------- */

// Reveals children when scrolled into view (fade + slide/scale).
function Reveal({
  children,
  className = '',
  variant = '',
  delay = 0,
  as: Tag = 'div',
}: {
  children: ReactNode
  className?: string
  variant?: '' | 'reveal-left' | 'reveal-right' | 'reveal-scale'
  delay?: number
  as?: any
}) {
  const ref = useRef<HTMLElement>(null)
  useEffect(() => {
    const el = ref.current
    if (!el) return
    const io = new IntersectionObserver(
      entries => {
        entries.forEach(e => {
          if (e.isIntersecting) {
            el.classList.add('reveal-visible')
            io.unobserve(el)
          }
        })
      },
      { threshold: 0.15, rootMargin: '0px 0px -8% 0px' },
    )
    io.observe(el)
    return () => io.disconnect()
  }, [])
  return (
    <Tag ref={ref as any} style={{ transitionDelay: `${delay}ms` }} className={`reveal ${variant} ${className}`}>
      {children}
    </Tag>
  )
}

// Pointer-driven 3D tilt wrapper.
function Tilt({ children, className = '', max = 12 }: { children: ReactNode; className?: string; max?: number }) {
  const ref = useRef<HTMLDivElement>(null)
  const raf = useRef(0)
  const onMove = (e: React.MouseEvent) => {
    const el = ref.current
    if (!el) return
    const r = el.getBoundingClientRect()
    const px = (e.clientX - r.left) / r.width
    const py = (e.clientY - r.top) / r.height
    cancelAnimationFrame(raf.current)
    raf.current = requestAnimationFrame(() => {
      el.style.transform = `perspective(1000px) rotateX(${(0.5 - py) * max}deg) rotateY(${(px - 0.5) * max}deg)`
    })
  }
  const onLeave = () => {
    const el = ref.current
    if (el) el.style.transform = 'perspective(1000px) rotateX(0deg) rotateY(0deg)'
  }
  return (
    <div ref={ref} onMouseMove={onMove} onMouseLeave={onLeave} className={`tilt ${className}`}>
      {children}
    </div>
  )
}

// Count-up number that animates 0 → value when value first arrives.
function CountUp({ value, duration = 1300 }: { value: number; duration?: number }) {
  const [display, setDisplay] = useState(0)
  useEffect(() => {
    let raf = 0
    const start = performance.now()
    const tick = (t: number) => {
      const p = Math.min(1, (t - start) / duration)
      const eased = 1 - Math.pow(1 - p, 3)
      setDisplay(Math.round(value * eased))
      if (p < 1) raf = requestAnimationFrame(tick)
    }
    raf = requestAnimationFrame(tick)
    return () => cancelAnimationFrame(raf)
  }, [value, duration])
  return <>{display}</>
}

function Chip({
  icon: Icon,
  label,
  className = '',
  depth = 40,
  delay = 0,
}: {
  icon: any
  label: string
  className?: string
  depth?: number
  delay?: number
}) {
  return (
    <div className={`absolute ${className}`} style={{ transform: `translateZ(${depth}px)` }}>
      <div
        className="chip-float glass-flat holo flex items-center gap-2 rounded-xl px-3 py-2 text-xs font-medium text-white/85 shadow-2xl"
        style={{ animationDelay: `${delay}s` }}
      >
        <Icon className="h-3.5 w-3.5 text-accent-cyan" />
        {label}
      </div>
    </div>
  )
}

/* ---------- content data ---------- */

const FEATURES = [
  { icon: BrainCircuit, title: 'Agentic Brain', desc: 'A hierarchical planner decomposes objectives into phases → tasks → steps, resolves configs, executes against the agent swarm, and verifies every step.', accent: 'from-violet-500 to-fuchsia-500' },
  { icon: Cloud, title: 'Adaptive Ingestion', desc: 'Crawlee workers plus REST, WebSocket & Selenium scrapers publish Avro RawEvents to Kafka — the AI picks crawl parameters from plain-English requirements.', accent: 'from-cyan-500 to-blue-500' },
  { icon: Cpu, title: 'Real-Time Stream Compute', desc: 'A stream processor (plus real PyFlink jobs) turns raw_stream into enriched processed_stream events with rolling features and live signals.', accent: 'from-fuchsia-500 to-pink-500' },
  { icon: Users, title: 'Multi-Tenant Gateway', desc: 'Subscription plans, API keys, per-tenant quotas, dedicated Kafka topics, metering and billing — self-serve from starter to enterprise.', accent: 'from-emerald-500 to-teal-500' },
  { icon: Layers, title: 'Serving Apps', desc: 'A trading bot, accommodation aggregator, data marketplace, auditing and dashboards — all feeding metrics back into the Brain.', accent: 'from-amber-500 to-orange-500' },
  { icon: Workflow, title: 'Control Portal', desc: 'This portal: real-time health, a live pipeline canvas, ingestion, stream, agents, trading, tenants & billing — and a one-click MVP proof.', accent: 'from-sky-500 to-indigo-500' },
]

const PIPELINE = [
  { icon: Cloud, label: 'Ingest', sub: 'Crawlee · scrapers', color: 'text-cyan-300' },
  { icon: Boxes, label: 'Kafka + Avro', sub: 'raw_stream', color: 'text-violet-300' },
  { icon: Cpu, label: 'Stream Compute', sub: 'processed_stream', color: 'text-fuchsia-300' },
  { icon: LineChart, label: 'Serve', sub: 'apps · signals', color: 'text-emerald-300' },
]

const VERTICALS = [
  { icon: Gamepad2, title: 'Gaming & Esports', desc: 'Live odds and stats ingestion feeding dashboards and a data marketplace.', accent: 'from-fuchsia-500/20 to-purple-500/10' },
  { icon: CandlestickChart, title: 'Financial Markets', desc: 'Market data streamed to a trading bot with backtesting, risk limits and a mock broker.', accent: 'from-emerald-500/20 to-teal-500/10' },
  { icon: Building2, title: 'Accommodation', desc: 'Listings ingestion powering a search & aggregation API for travel products.', accent: 'from-cyan-500/20 to-blue-500/10' },
]

/** Investor market sizing — aligned with docs/monetization-for-investors.md */
const MARKET_LAYERS = [
  {
    abbrev: 'TAM',
    name: 'Total addressable market',
    headline: '$100B+',
    desc: 'Global data platforms, market data & analytics.',
    accent: 'from-cyan-500 to-blue-500',
    stroke: '#22d3ee',
    fill: 'rgba(34, 211, 238, 0.1)',
    activeFill: 'rgba(34, 211, 238, 0.32)',
    radius: 88,
    ringHover: 'hover:border-cyan-500/40 hover:bg-cyan-500/[0.08] hover:shadow-cyan-500/15',
    activeRing: 'border-cyan-500/45 bg-cyan-500/[0.12] shadow-md shadow-cyan-500/20 -translate-y-0.5',
    badgeActive: 'border-cyan-400/70 shadow-cyan-500/25 scale-110',
  },
  {
    abbrev: 'TOM',
    name: 'Total obtainable market',
    headline: '$8–15B',
    desc: 'Teams shipping monetizable web & API datasets.',
    accent: 'from-violet-500 to-fuchsia-500',
    stroke: '#a78bfa',
    fill: 'rgba(167, 139, 250, 0.16)',
    activeFill: 'rgba(167, 139, 250, 0.34)',
    radius: 58,
    ringHover: 'hover:border-violet-500/40 hover:bg-violet-500/[0.08] hover:shadow-violet-500/15',
    activeRing: 'border-violet-500/45 bg-violet-500/[0.12] shadow-md shadow-violet-500/20 -translate-y-0.5',
    badgeActive: 'border-violet-400/70 shadow-violet-500/25 scale-110',
  },
  {
    abbrev: 'SOM',
    name: 'Serviceable obtainable market',
    headline: '$50–150M',
    desc: 'Fintech & gaming · Year 3 wedge.',
    accent: 'from-pink-500 to-rose-500',
    stroke: '#f472b6',
    fill: 'rgba(244, 114, 182, 0.22)',
    activeFill: 'rgba(244, 114, 182, 0.4)',
    radius: 28,
    ringHover: 'hover:border-pink-500/40 hover:bg-pink-500/[0.08] hover:shadow-pink-500/15',
    activeRing: 'border-pink-500/45 bg-pink-500/[0.12] shadow-md shadow-pink-500/20 -translate-y-0.5',
    badgeActive: 'border-pink-400/70 shadow-pink-500/25 scale-110',
  },
] as const

type MarketAbbrev = (typeof MARKET_LAYERS)[number]['abbrev']

const MARKET_CX = 100
const MARKET_CY = 100

function marketLayerAt(svg: SVGSVGElement, clientX: number, clientY: number): MarketAbbrev | null {
  const pt = svg.createSVGPoint()
  pt.x = clientX
  pt.y = clientY
  const ctm = svg.getScreenCTM()
  if (!ctm) return null
  const { x, y } = pt.matrixTransform(ctm.inverse())
  const d = Math.hypot(x - MARKET_CX, y - MARKET_CY)
  if (d > 88) return null
  if (d <= 28) return 'SOM'
  if (d <= 58) return 'TOM'
  return 'TAM'
}

function MarketSizingPanel() {
  const [active, setActive] = useState<MarketAbbrev | null>(null)

  const layerState = (abbrev: MarketAbbrev) => ({
    on: active === abbrev,
    dim: active !== null && active !== abbrev,
  })

  return (
    <div
      className="mx-auto flex flex-col items-center justify-center gap-5 sm:flex-row sm:items-center sm:gap-8 lg:gap-10"
      onMouseLeave={() => setActive(null)}
    >
      <Tilt max={9}>
        <div className={`flex flex-col items-center px-1 transition-transform duration-300 ease-out ${active ? 'scale-[1.02]' : ''}`}>
          <div className="relative mx-auto h-40 w-40 shrink-0 sm:h-48 sm:w-48 lg:h-52 lg:w-52">
            <svg
              viewBox="0 0 200 200"
              className="h-full w-full cursor-pointer"
              aria-label="TAM, TOM and SOM market sizing — hover each ring"
              onMouseMove={e => setActive(marketLayerAt(e.currentTarget, e.clientX, e.clientY))}
            >
              {MARKET_LAYERS.map(layer => {
                const { on, dim } = layerState(layer.abbrev)
                const scale = on ? 1.05 : 1
                return (
                  <circle
                    key={layer.abbrev}
                    cx={MARKET_CX}
                    cy={MARKET_CY}
                    r={layer.radius}
                    fill={on ? layer.activeFill : layer.fill}
                    stroke={layer.stroke}
                    strokeWidth={on ? 2.5 : 1.5}
                    strokeOpacity={on ? 1 : dim ? 0.3 : 0.65}
                    opacity={dim ? 0.35 : 1}
                    style={{
                      transition: 'all 0.28s cubic-bezier(0.16, 0.84, 0.44, 1)',
                      transform: `translate(${MARKET_CX}px, ${MARKET_CY}px) scale(${scale}) translate(${-MARKET_CX}px, ${-MARKET_CY}px)`,
                      filter: on ? `drop-shadow(0 0 14px ${layer.stroke}99)` : undefined,
                    }}
                  />
                )
              })}
            </svg>

            <div
              className={`pointer-events-none absolute left-1/2 top-0 -translate-x-1/2 -translate-y-0.5 rounded-md border border-cyan-500/35 bg-[#0a1520]/90 px-1.5 py-0.5 text-center shadow-lg backdrop-blur-sm transition-all duration-300 sm:px-2 sm:py-1 ${layerState('TAM').on ? MARKET_LAYERS[0].badgeActive : ''}`}
            >
              <p className="text-[7px] font-bold tracking-wide text-cyan-400 sm:text-[8px]">TAM</p>
              <p className="text-[10px] font-bold leading-tight text-cyan-200 sm:text-xs">$100B+</p>
            </div>

            <div
              className={`pointer-events-none absolute -right-0.5 top-[34%] translate-x-0.5 rounded-md border border-violet-500/35 bg-[#12101a]/90 px-1.5 py-0.5 text-center shadow-lg backdrop-blur-sm transition-all duration-300 sm:px-2 sm:py-1 ${layerState('TOM').on ? MARKET_LAYERS[1].badgeActive : ''}`}
            >
              <p className="text-[7px] font-bold tracking-wide text-violet-400 sm:text-[8px]">TOM</p>
              <p className="text-[10px] font-bold leading-tight text-violet-200 sm:text-xs">$8–15B</p>
            </div>

            <div
              className={`pointer-events-none absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2 rounded-md border border-pink-500/40 bg-[#1a0f16]/90 px-1.5 py-1 text-center shadow-lg backdrop-blur-sm transition-all duration-300 sm:px-2 ${layerState('SOM').on ? MARKET_LAYERS[2].badgeActive : ''}`}
            >
              <p className="text-[7px] font-bold tracking-wide text-pink-400 sm:text-[8px]">SOM</p>
              <p className="text-[11px] font-bold leading-tight text-pink-200 sm:text-sm">$50–150M</p>
            </div>
          </div>

          <div className="mt-3 flex flex-wrap justify-center gap-1 sm:mt-4 sm:gap-1.5">
            {MARKET_LAYERS.map(layer => (
              <span
                key={layer.abbrev}
                role="presentation"
                onMouseEnter={() => setActive(layer.abbrev)}
                onMouseLeave={() => setActive(null)}
                className={`cursor-default rounded-full border border-white/10 bg-white/[0.04] px-2 py-0.5 text-[9px] transition-all duration-200 sm:text-[10px] ${
                  layerState(layer.abbrev).on ? `${layer.activeRing} border-white/20` : 'hover:scale-105 hover:border-white/20 hover:bg-white/[0.07]'
                } ${layerState(layer.abbrev).dim ? 'opacity-40' : ''}`}
              >
                <span className="font-bold text-white/55">{layer.abbrev}</span>{' '}
                <span className={`font-bold bg-gradient-to-r bg-clip-text text-transparent ${layer.accent}`}>{layer.headline}</span>
              </span>
            ))}
          </div>
        </div>
      </Tilt>

      <div className="w-full max-w-[14.5rem] shrink-0 space-y-1.5 sm:max-w-[16rem] sm:space-y-2">
        {MARKET_LAYERS.map(layer => {
          const { on, dim } = layerState(layer.abbrev)
          return (
            <div
              key={layer.abbrev}
              role="presentation"
              onMouseEnter={() => setActive(layer.abbrev)}
              onMouseLeave={() => setActive(null)}
              className={`flex cursor-default items-start gap-2 rounded-lg border px-2.5 py-2 transition-all duration-200 sm:gap-2.5 sm:px-3 sm:py-2.5 ${
                on
                  ? layer.activeRing
                  : `border-white/[0.06] bg-white/[0.02] ${layer.ringHover}`
              } ${dim ? 'opacity-45' : ''}`}
            >
              <div
                className={`mt-px flex h-6 w-6 shrink-0 items-center justify-center rounded-md bg-gradient-to-br text-[8px] font-bold text-white transition-transform duration-200 sm:h-7 sm:w-7 sm:text-[9px] ${layer.accent} ${on ? 'scale-110' : ''}`}
              >
                {layer.abbrev}
              </div>
              <div className="min-w-0">
                <p className={`text-[10px] font-medium leading-snug sm:text-[11px] ${on ? 'text-white' : 'text-white/80'}`}>{layer.name}</p>
                <p className="mt-0.5 text-[9px] leading-snug text-white/45 sm:text-[10px]">{layer.desc}</p>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}

const AI_DATA_CHANNELS = [
  { icon: BrainCircuit, label: 'Agents & LLMs', sub: 'Verified pipelines' },
  { icon: Database, label: 'RAG & training', sub: 'Schema-governed chunks' },
  { icon: Cpu, label: 'Live signals', sub: 'Kafka streams' },
  { icon: Layers, label: 'Marketplace', sub: 'Ready-made feeds' },
]

const PARTICLES = Array.from({ length: 22 }, (_, i) => ({
  left: `${(i * 37) % 100}%`,
  delay: `${(i % 11) * 0.9}s`,
  duration: `${7 + (i % 6) * 1.6}s`,
  top: `${(i * 41) % 96}%`,
}))

/* ---------- page ---------- */

export default function Landing() {
  const navigate = useNavigate()
  const rootRef = useRef<HTMLDivElement>(null)
  const [status, setStatus] = useState<MvpStatus | null>(null)
  const [progress, setProgress] = useState(0)

  useEffect(() => {
    let active = true
    const load = () => api.mvpStatus().then(d => active && setStatus(d)).catch(() => {})
    load()
    const id = setInterval(load, 8000)
    return () => {
      active = false
      clearInterval(id)
    }
  }, [])

  // Scroll progress bar.
  useEffect(() => {
    const onScroll = () => {
      const h = document.documentElement
      const max = h.scrollHeight - h.clientHeight
      setProgress(max > 0 ? (h.scrollTop / max) * 100 : 0)
    }
    onScroll()
    window.addEventListener('scroll', onScroll, { passive: true })
    return () => window.removeEventListener('scroll', onScroll)
  }, [])

  // Mouse-follow spotlight.
  const onPointerMove = (e: React.MouseEvent) => {
    const el = rootRef.current
    if (!el) return
    el.style.setProperty('--mx', `${e.clientX}px`)
    el.style.setProperty('--my', `${e.clientY}px`)
  }

  const servicesLive = status ? `${status.services_up}/${status.services_total}` : '—'
  const frac = status && status.services_total ? status.services_up / status.services_total : 0
  const R = 52
  const CIRC = 2 * Math.PI * R

  return (
    <div ref={rootRef} onMouseMove={onPointerMove} className="relative min-h-screen overflow-x-hidden">
      {/* scroll progress */}
      <div className="fixed inset-x-0 top-0 z-[60] h-0.5 bg-transparent">
        <div className="h-full bg-gradient-to-r from-accent-cyan via-accent-violet to-accent-pink transition-[width] duration-150" style={{ width: `${progress}%` }} />
      </div>

      {/* fantastic animated background — absolutely anchored to the page (not
          fixed) so it never fights scroll compositing, with glow spread down */}
      <div className="pointer-events-none absolute inset-0 -z-10 overflow-hidden">
        <div className="aurora aurora-1 -left-40 top-[-4%] h-[38rem] w-[38rem] bg-accent-cyan/25" />
        <div className="aurora aurora-2 right-[-12%] top-[26%] h-[34rem] w-[34rem] bg-accent-violet/25" />
        <div className="aurora aurora-3 left-1/4 top-[52%] h-[32rem] w-[32rem] bg-accent-pink/20" />
        <div className="aurora aurora-1 right-[-8%] top-[76%] h-[30rem] w-[30rem] bg-accent-cyan/20" />
        <div className="grid-floor opacity-40" />
        {PARTICLES.map((p, i) => (
          <span key={i} className="particle" style={{ left: p.left, top: p.top, animationDelay: p.delay, animationDuration: p.duration }} />
        ))}
      </div>
      <div className="spotlight-layer" />

      {/* nav */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#08080f]/60 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-5 py-4 sm:px-8">
          <Link to="/" className="group flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-cyan to-accent-violet shadow-lg shadow-accent-cyan/25 transition group-hover:scale-110">
              <Zap className="h-5 w-5 text-white" />
            </div>
            <div className="leading-tight">
              <p className="text-base font-bold tracking-tight">SpeedFlow</p>
              <p className="text-[11px] text-white/40">AI Data Platform</p>
            </div>
          </Link>
          <nav className="ml-auto hidden items-center gap-7 text-sm text-white/60 md:flex">
            <a href="#platform" className="transition hover:text-white">Platform</a>
            <a href="#architecture" className="transition hover:text-white">Architecture</a>
            <a href="#verticals" className="transition hover:text-white">Verticals</a>
            <a href="#market" className="transition hover:text-white">Market</a>
          </nav>
          <div className="ml-auto flex items-center gap-2 md:ml-6">
            <button type="button" onClick={() => navigate('/showcase')} className="btn-action-secondary hidden px-4 sm:block">Live Demo</button>
            <button type="button" onClick={() => navigate('/overview')} className="btn-action-primary px-4">Launch Console</button>
          </div>
        </div>
      </header>

      {/* hero */}
      <section className="relative mx-auto grid max-w-7xl grid-cols-1 items-center gap-12 px-5 pb-20 pt-16 sm:px-8 sm:pt-24 lg:grid-cols-[1.05fr_0.95fr]">
        <div>
          <Reveal>
            <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3.5 py-1.5 text-xs font-medium text-emerald-300">
              <span className="relative flex h-2 w-2">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
                <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
              </span>
              MVP live · {servicesLive} services online
            </span>
          </Reveal>

          <Reveal delay={80}>
            <h1 className="mt-6 text-[2.6rem] font-bold leading-[1.05] tracking-tight sm:text-6xl">
              Turn raw web data into
              <br className="hidden sm:block" />
              <span className="text-shimmer"> monetizable products.</span>
            </h1>
          </Reveal>

          <Reveal delay={160}>
            <p className="mt-6 max-w-xl text-lg text-white/55">
              SpeedFlow is an AI-driven, multi-tenant data platform. A cognitive <b className="text-white/80">Brain</b> plans
              what to scrape, how to process it in real time, and how to serve it — then verifies every step end-to-end.
            </p>
          </Reveal>

          <Reveal delay={240}>
            <div className="mt-9 flex flex-col items-start gap-3 sm:flex-row">
              <button
                type="button"
                onClick={() => navigate('/showcase')}
                className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-cyan to-accent-violet px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-accent-cyan/25 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent-violet/30 active:scale-[0.98] sm:w-auto"
              >
                <Rocket className="h-4 w-4" />
                Prove the MVP live
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </button>
              <button
                type="button"
                onClick={() => navigate('/overview')}
                className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-semibold text-white/80 transition hover:-translate-y-0.5 hover:border-accent-cyan/40 hover:bg-white/10 active:scale-[0.98] sm:w-auto"
              >
                <Activity className="h-4 w-4" />
                Open the console
              </button>
            </div>
          </Reveal>
        </div>

        {/* 3D holographic console preview */}
        <Reveal variant="reveal-scale" delay={200} className="[perspective:1400px]">
          <Tilt max={14} className="relative mx-auto max-w-md">
            <div className="holo glass-flat tilt-layer relative rounded-3xl p-6 shadow-2xl shadow-accent-violet/10">
              <div className="mb-5 flex items-center gap-2">
                <span className="h-2.5 w-2.5 rounded-full bg-red-400/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-amber-400/80" />
                <span className="h-2.5 w-2.5 rounded-full bg-emerald-400/80" />
                <span className="ml-2 text-xs text-white/50">SpeedFlow Console · live</span>
                <span className="ml-auto inline-flex items-center gap-1.5 rounded-full bg-emerald-500/10 px-2 py-0.5 text-[10px] text-emerald-300">
                  <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-emerald-400" /> online
                </span>
              </div>

              <div className="flex items-center gap-5">
                <div className="relative h-36 w-36 shrink-0" style={{ transform: 'translateZ(40px)' }}>
                  <svg viewBox="0 0 140 140" className="h-36 w-36 -rotate-90">
                    <circle cx="70" cy="70" r={R} fill="none" stroke="rgba(255,255,255,0.08)" strokeWidth="10" />
                    <circle
                      cx="70" cy="70" r={R} fill="none" stroke="url(#ring)" strokeWidth="10" strokeLinecap="round"
                      strokeDasharray={CIRC} strokeDashoffset={CIRC * (1 - frac)} style={{ transition: 'stroke-dashoffset 1.2s cubic-bezier(0.16,0.84,0.44,1)' }}
                    />
                    <defs>
                      <linearGradient id="ring" x1="0" y1="0" x2="1" y2="1">
                        <stop offset="0%" stopColor="#22d3ee" />
                        <stop offset="100%" stopColor="#a78bfa" />
                      </linearGradient>
                    </defs>
                  </svg>
                  <div className="absolute inset-0 flex flex-col items-center justify-center">
                    <span className="gradient-text text-2xl font-bold">{servicesLive}</span>
                    <span className="text-[10px] uppercase tracking-wider text-white/45">services</span>
                  </div>
                </div>

                <div className="min-w-0 flex-1 space-y-3" style={{ transform: 'translateZ(24px)' }}>
                  {[
                    { label: 'Brain objectives', value: status?.metrics.brain_objectives ?? 0, max: 3, color: 'from-violet-400 to-fuchsia-400' },
                    { label: 'Jobs completed', value: status?.metrics.completed_jobs ?? 0, max: Math.max(20, status?.metrics.completed_jobs ?? 0), color: 'from-cyan-400 to-blue-400' },
                    { label: 'Capabilities', value: status?.capabilities_ready ?? 0, max: status?.capabilities_total ?? 6, color: 'from-emerald-400 to-teal-400' },
                  ].map(row => (
                    <div key={row.label}>
                      <div className="mb-1 flex items-center justify-between text-[11px]">
                        <span className="text-white/55">{row.label}</span>
                        <span className="font-semibold text-white/80"><CountUp value={row.value} /></span>
                      </div>
                      <div className="h-1.5 overflow-hidden rounded-full bg-white/10">
                        <div className={`h-full rounded-full bg-gradient-to-r ${row.color} transition-all duration-1000`} style={{ width: `${Math.min(100, (row.value / (row.max || 1)) * 100)}%` }} />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="mt-6 flex items-center justify-between rounded-2xl border border-white/10 bg-white/[0.03] px-3 py-3" style={{ transform: 'translateZ(30px)' }}>
                {PIPELINE.map((p, i) => (
                  <div key={p.label} className="flex items-center gap-2">
                    <div className="flex flex-col items-center">
                      <p.icon className={`h-4 w-4 ${p.color}`} />
                      <span className="mt-1 text-[9px] text-white/45">{p.label.split(' ')[0]}</span>
                    </div>
                    {i < PIPELINE.length - 1 && <span className="flow-pulse h-1 w-1 rounded-full bg-accent-cyan" style={{ animationDelay: `${i * 0.25}s` }} />}
                  </div>
                ))}
              </div>
            </div>

            {/* floating depth chips */}
            <Chip icon={Boxes} label="Kafka" className="-left-6 -top-5 sm:-left-10" depth={70} delay={0} />
            <Chip icon={Database} label="Avro" className="-right-4 top-8 sm:-right-8" depth={55} delay={1.2} />
            <Chip icon={BrainCircuit} label="Brain" className="-left-4 bottom-10 sm:-left-9" depth={60} delay={0.6} />
            <Chip icon={Radio} label="Live signals" className="-right-3 -bottom-4 sm:-right-10" depth={65} delay={1.8} />
          </Tilt>
        </Reveal>
      </section>

      {/* metrics strip */}
      <section className="mx-auto max-w-6xl px-5 pb-8 sm:px-8">
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
          {[
            { label: 'Services online', value: servicesLive },
            { label: 'Capabilities ready', value: status ? `${status.capabilities_ready}/${status.capabilities_total}` : '—' },
            { label: 'Brain objectives', node: status ? <CountUp value={status.metrics.brain_objectives} /> : '—' },
            { label: 'Jobs completed', node: status ? <CountUp value={status.metrics.completed_jobs} /> : '—' },
          ].map((s, i) => (
            <Reveal key={s.label} delay={i * 90} variant="reveal-scale">
              <div className="holo glass-flat card-3d px-5 py-4 text-center hover:-translate-y-1 hover:shadow-xl hover:shadow-accent-cyan/10">
                <p className="gradient-text text-3xl font-bold sm:text-4xl">{s.node ?? s.value}</p>
                <p className="mt-1 text-xs font-medium uppercase tracking-wider text-white/45">{s.label}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* features */}
      <section id="platform" className="mx-auto max-w-7xl px-5 py-20 sm:px-8">
        <Reveal className="mb-12 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent-cyan/80">The platform</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Everything to ship a data product</h2>
          <p className="mx-auto mt-3 max-w-2xl text-white/50">Six layers, one product — from ingestion to monetization, coordinated by the Brain.</p>
        </Reveal>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3 [perspective:1200px]">
          {FEATURES.map(({ icon: Icon, title, desc, accent }, i) => (
            <Reveal key={title} delay={(i % 3) * 100} variant="reveal-scale">
              <Tilt max={13}>
                <div className="holo glass-flat card-3d group h-full p-6 hover:border-accent-cyan/30 hover:shadow-2xl hover:shadow-accent-violet/10">
                  <div className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${accent} shadow-lg transition duration-300 group-hover:-translate-y-1 group-hover:scale-110`} style={{ transform: 'translateZ(30px)' }}>
                    <Icon className="h-6 w-6 text-white" />
                  </div>
                  <h3 className="text-lg font-semibold" style={{ transform: 'translateZ(18px)' }}>{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{desc}</p>
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </section>

      {/* architecture */}
      <section id="architecture" className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <Reveal>
          <div className="holo glass-flat overflow-hidden p-8 sm:p-12">
            <div className="mb-10 text-center">
              <p className="text-sm font-semibold uppercase tracking-widest text-accent-violet/80">Architecture</p>
              <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">A verified, real-time data pipeline</h2>
            </div>
            <div className="flex flex-col items-stretch gap-4 lg:flex-row lg:items-center">
              {PIPELINE.map(({ icon: Icon, label, sub, color }, i) => (
                <Reveal key={label} variant="reveal-scale" delay={i * 120} className="flex flex-1 items-center gap-4 lg:flex-col lg:gap-3">
                  <div className="group flex flex-1 flex-col items-center rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-6 text-center transition hover:-translate-y-1.5 hover:border-accent-cyan/30 hover:bg-white/[0.06] hover:shadow-xl hover:shadow-accent-cyan/10 lg:w-full">
                    <Icon className={`h-8 w-8 ${color} transition group-hover:scale-110`} />
                    <p className="mt-3 font-semibold">{label}</p>
                    <p className="text-xs text-white/40">{sub}</p>
                  </div>
                  {i < PIPELINE.length - 1 && <ArrowRight className="h-5 w-5 shrink-0 rotate-90 text-white/25 lg:rotate-0" />}
                </Reveal>
              ))}
            </div>
            <div className="mt-6 flex items-center justify-center gap-3 rounded-2xl border border-accent-violet/20 bg-gradient-to-r from-accent-violet/10 to-accent-cyan/10 px-6 py-4 text-center">
              <BrainCircuit className="h-5 w-5 shrink-0 text-accent-violet" />
              <p className="text-sm text-white/70">
                The <b className="text-white">Brain</b> plans, configures & <b className="text-white">verifies every step</b> across the whole pipeline.
              </p>
            </div>
          </div>
        </Reveal>
      </section>

      {/* verticals */}
      <section id="verticals" className="mx-auto max-w-7xl px-5 py-20 sm:px-8">
        <Reveal className="mb-12 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent-pink/80">Verticals</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Three business verticals, out of the box</h2>
        </Reveal>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-3 [perspective:1200px]">
          {VERTICALS.map(({ icon: Icon, title, desc, accent }, i) => (
            <Reveal key={title} delay={i * 120} variant="reveal-scale">
              <Tilt max={14}>
                <div className={`holo glass-flat card-3d group h-full bg-gradient-to-br ${accent} p-7 hover:shadow-2xl hover:shadow-accent-pink/10`}>
                  <Icon className="h-9 w-9 text-white/90 transition duration-300 group-hover:-translate-y-1 group-hover:scale-110" style={{ transform: 'translateZ(28px)' }} />
                  <h3 className="mt-4 text-xl font-semibold" style={{ transform: 'translateZ(16px)' }}>{title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-white/55">{desc}</p>
                </div>
              </Tilt>
            </Reveal>
          ))}
        </div>
      </section>

      {/* market opportunity — TAM / TOM / SOM (after verticals) */}
      <section id="market" className="mx-auto max-w-7xl px-5 py-14 sm:px-8 sm:py-20">
        <Reveal className="mb-8 text-center sm:mb-10">
          <p className="text-xs font-semibold uppercase tracking-widest text-accent-violet/80 sm:text-sm">Market opportunity</p>
          <h2 className="mt-2 text-2xl font-bold tracking-tight sm:text-3xl lg:text-4xl">
            A <span className="gradient-text">$100B+</span> market with a clear wedge
          </h2>
          <p className="mx-auto mt-2 max-w-lg text-sm text-white/50 sm:mt-3 sm:max-w-xl">
            Data infra, AI agents, and vertical SaaS — one platform, one budget line.
          </p>
        </Reveal>

        <Reveal variant="reveal-scale">
          <div className="mx-auto max-w-4xl">
            <div className="holo glass-flat p-4 sm:px-8 sm:py-7 lg:px-10 lg:py-8">
              <MarketSizingPanel />
            </div>
          </div>
        </Reveal>

        <Reveal delay={120} className="mt-5 sm:mt-6">
          <div className="mx-auto max-w-4xl holo glass-flat overflow-hidden">
            <div className="flex flex-col items-center gap-2 border-b border-white/10 bg-gradient-to-r from-accent-violet/10 via-accent-cyan/10 to-accent-pink/10 px-4 py-4 text-center sm:gap-3 sm:px-8 sm:py-5">
              <div className="flex items-center gap-2.5 sm:gap-3">
                <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-gradient-to-br from-accent-violet to-accent-cyan shadow-lg shadow-accent-violet/20 sm:h-9 sm:w-9 sm:rounded-xl">
                  <Sparkles className="h-3.5 w-3.5 text-white sm:h-4 sm:w-4" />
                </div>
                <div className="text-left">
                  <p className="text-[10px] font-semibold uppercase tracking-widest text-accent-cyan/80 sm:text-xs">AI-ready data</p>
                  <h3 className="text-sm font-bold tracking-tight sm:text-base lg:text-lg">Data for model-hungry AI</h3>
                </div>
              </div>
              <p className="max-w-sm text-[10px] text-white/50 sm:max-w-md sm:text-xs">
                Governed streams and marketplace feeds — not months of custom pipeline work.
              </p>
            </div>
            <div className="grid grid-cols-2 gap-px bg-white/10 sm:grid-cols-4">
              {AI_DATA_CHANNELS.map(({ icon: Icon, label, sub }) => (
                <div key={label} className="flex flex-col items-center gap-1 bg-[#0e0e18]/75 px-2 py-3 text-center sm:gap-1.5 sm:px-4 sm:py-4">
                  <div className="flex h-7 w-7 shrink-0 items-center justify-center rounded-lg bg-white/5 ring-1 ring-white/10 sm:h-8 sm:w-8">
                    <Icon className="h-3.5 w-3.5 text-accent-cyan sm:h-4 sm:w-4" />
                  </div>
                  <p className="text-[10px] font-medium text-white/85 sm:text-xs">{label}</p>
                  <p className="text-[9px] text-white/40 sm:text-[10px]">{sub}</p>
                </div>
              ))}
            </div>
          </div>
        </Reveal>
      </section>

      {/* CTA */}
      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <Reveal variant="reveal-scale">
          <div className="holo glass-flat relative overflow-hidden p-10 text-center sm:p-16">
            <div className="pointer-events-none absolute inset-0 bg-gradient-to-r from-accent-cyan/10 via-accent-violet/10 to-accent-pink/10" />
            <div className="relative">
              <ShieldCheck className="mx-auto h-10 w-10 text-emerald-400" />
              <h2 className="mx-auto mt-4 max-w-2xl text-3xl font-bold tracking-tight sm:text-4xl">
                Don't take our word for it — watch the MVP prove itself
              </h2>
              <p className="mx-auto mt-4 max-w-xl text-white/55">
                Run a live end-to-end demo: provision a tenant, submit an AI-planned scrape, stream it through Kafka,
                and let the Brain verify every step — in real time.
              </p>
              <button
                type="button"
                onClick={() => navigate('/showcase')}
                className="group mx-auto mt-8 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-cyan to-accent-violet px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-accent-cyan/25 transition hover:-translate-y-0.5 hover:shadow-xl hover:shadow-accent-violet/30 active:scale-[0.98]"
              >
                <Sparkles className="h-4 w-4" />
                Run the live demo
                <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
              </button>
            </div>
          </div>
        </Reveal>
      </section>

      {/* footer */}
      <footer className="border-t border-white/10">
        <div className="mx-auto flex max-w-7xl flex-col items-center justify-between gap-4 px-5 py-8 text-sm text-white/40 sm:flex-row sm:px-8">
          <div className="flex items-center gap-2">
            <Zap className="h-4 w-4 text-accent-cyan" />
            <span>SpeedFlow · AI-driven multi-tenant data platform</span>
          </div>
          <div className="flex items-center gap-5">
            <Link to="/overview" className="transition hover:text-white">Console</Link>
            <Link to="/showcase" className="transition hover:text-white">Live Demo</Link>
            <Link to="/brain" className="transition hover:text-white">The Brain</Link>
          </div>
        </div>
      </footer>
    </div>
  )
}
