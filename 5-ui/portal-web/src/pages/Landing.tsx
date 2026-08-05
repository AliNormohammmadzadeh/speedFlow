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
