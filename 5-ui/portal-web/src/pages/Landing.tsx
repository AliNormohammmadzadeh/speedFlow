import { useEffect, useState } from 'react'
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
  Gamepad2,
  Layers,
  LineChart,
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

const FEATURES = [
  {
    icon: BrainCircuit,
    title: 'Agentic Brain',
    desc: 'A hierarchical planner decomposes objectives into phases → tasks → steps, resolves configs, executes against the agent swarm, and verifies every step.',
    accent: 'from-violet-500 to-fuchsia-500',
  },
  {
    icon: Cloud,
    title: 'Adaptive Ingestion',
    desc: 'Crawlee workers plus REST, WebSocket & Selenium scrapers publish Avro RawEvents to Kafka — the AI picks crawl parameters from plain-English requirements.',
    accent: 'from-cyan-500 to-blue-500',
  },
  {
    icon: Cpu,
    title: 'Real-Time Stream Compute',
    desc: 'A stream processor (plus real PyFlink jobs) turns raw_stream into enriched processed_stream events with rolling features and live signals.',
    accent: 'from-fuchsia-500 to-pink-500',
  },
  {
    icon: Users,
    title: 'Multi-Tenant Gateway',
    desc: 'Subscription plans, API keys, per-tenant quotas, dedicated Kafka topics, metering and billing — self-serve from starter to enterprise.',
    accent: 'from-emerald-500 to-teal-500',
  },
  {
    icon: Layers,
    title: 'Serving Apps',
    desc: 'A trading bot, accommodation aggregator, data marketplace, auditing and dashboards — all feeding metrics back into the Brain.',
    accent: 'from-amber-500 to-orange-500',
  },
  {
    icon: Workflow,
    title: 'Control Portal',
    desc: 'This portal: real-time health, a live pipeline canvas, ingestion, stream, agents, trading, tenants & billing — and a one-click MVP proof.',
    accent: 'from-sky-500 to-indigo-500',
  },
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

function StatPill({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="glass px-5 py-4 text-center">
      <p className="gradient-text text-3xl font-bold sm:text-4xl">{value}</p>
      <p className="mt-1 text-xs font-medium uppercase tracking-wider text-white/45">{label}</p>
    </div>
  )
}

export default function Landing() {
  const navigate = useNavigate()
  const [status, setStatus] = useState<MvpStatus | null>(null)

  useEffect(() => {
    let active = true
    const load = () => api.mvpStatus().then(d => { if (active) setStatus(d) }).catch(() => {})
    load()
    const id = setInterval(load, 8000)
    return () => { active = false; clearInterval(id) }
  }, [])

  const servicesLive = status ? `${status.services_up}/${status.services_total}` : '—'

  return (
    <div className="min-h-screen overflow-x-hidden">
      {/* Ambient background orbs */}
      <div className="pointer-events-none fixed inset-0 -z-10 overflow-hidden">
        <div className="absolute -left-40 top-[-10%] h-[36rem] w-[36rem] rounded-full bg-accent-cyan/10 blur-[120px]" />
        <div className="absolute right-[-10%] top-[20%] h-[32rem] w-[32rem] rounded-full bg-accent-violet/10 blur-[120px]" />
        <div className="absolute bottom-[-10%] left-1/3 h-[30rem] w-[30rem] rounded-full bg-accent-pink/10 blur-[120px]" />
      </div>

      {/* Nav */}
      <header className="sticky top-0 z-40 border-b border-white/10 bg-[#08080f]/70 backdrop-blur-xl">
        <div className="mx-auto flex max-w-7xl items-center gap-4 px-5 py-4 sm:px-8">
          <Link to="/" className="flex items-center gap-3">
            <div className="flex h-10 w-10 items-center justify-center rounded-xl bg-gradient-to-br from-accent-cyan to-accent-violet shadow-lg shadow-accent-cyan/20">
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
            <button type="button" onClick={() => navigate('/showcase')} className="btn-action-secondary hidden px-4 sm:block">
              Live Demo
            </button>
            <button type="button" onClick={() => navigate('/overview')} className="btn-action-primary px-4">
              Launch Console
            </button>
          </div>
        </div>
      </header>

      {/* Hero */}
      <section className="mx-auto max-w-7xl px-5 pb-16 pt-16 sm:px-8 sm:pt-24">
        <div className="mx-auto max-w-3xl text-center">
          <span className="inline-flex items-center gap-2 rounded-full border border-emerald-400/30 bg-emerald-500/10 px-3.5 py-1.5 text-xs font-medium text-emerald-300">
            <span className="relative flex h-2 w-2">
              <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
              <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-400" />
            </span>
            MVP live · {servicesLive} services online
          </span>

          <h1 className="mt-6 text-4xl font-bold leading-[1.1] tracking-tight sm:text-6xl">
            Turn raw web data into
            <br className="hidden sm:block" />
            <span className="gradient-text"> monetizable products.</span>
          </h1>

          <p className="mx-auto mt-6 max-w-2xl text-lg text-white/55">
            SpeedFlow is an AI-driven, multi-tenant data platform. A cognitive <b className="text-white/80">Brain</b> plans
            what to scrape, how to process it in real time, and how to serve it — then verifies every step end-to-end.
          </p>

          <div className="mt-9 flex flex-col items-center justify-center gap-3 sm:flex-row">
            <button
              type="button"
              onClick={() => navigate('/showcase')}
              className="group flex w-full items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-cyan to-accent-violet px-6 py-3.5 text-sm font-semibold text-white shadow-lg shadow-accent-cyan/25 transition hover:opacity-90 active:scale-[0.98] sm:w-auto"
            >
              <Rocket className="h-4 w-4" />
              Prove the MVP live
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </button>
            <button
              type="button"
              onClick={() => navigate('/overview')}
              className="flex w-full items-center justify-center gap-2 rounded-xl border border-white/15 bg-white/5 px-6 py-3.5 text-sm font-semibold text-white/80 transition hover:border-accent-cyan/40 hover:bg-white/10 active:scale-[0.98] sm:w-auto"
            >
              <Activity className="h-4 w-4" />
              Open the console
            </button>
          </div>
        </div>

        {/* Live metrics strip */}
        <div className="mx-auto mt-16 grid max-w-4xl grid-cols-2 gap-3 sm:grid-cols-4">
          <StatPill label="Services online" value={servicesLive} />
          <StatPill label="Capabilities ready" value={status ? `${status.capabilities_ready}/${status.capabilities_total}` : '—'} />
          <StatPill label="Brain objectives" value={status ? status.metrics.brain_objectives : '—'} />
          <StatPill label="Jobs completed" value={status ? status.metrics.completed_jobs : '—'} />
        </div>
      </section>

      {/* Features */}
      <section id="platform" className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="mb-12 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent-cyan/80">The platform</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Everything to ship a data product</h2>
          <p className="mx-auto mt-3 max-w-2xl text-white/50">Six layers, one product — from ingestion to monetization, coordinated by the Brain.</p>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-2 lg:grid-cols-3">
          {FEATURES.map(({ icon: Icon, title, desc, accent }) => (
            <div key={title} className="glass-hover group p-6">
              <div className={`mb-4 inline-flex h-12 w-12 items-center justify-center rounded-xl bg-gradient-to-br ${accent} shadow-lg`}>
                <Icon className="h-6 w-6 text-white" />
              </div>
              <h3 className="text-lg font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/55">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Architecture */}
      <section id="architecture" className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="glass overflow-hidden p-8 sm:p-12">
          <div className="mb-10 text-center">
            <p className="text-sm font-semibold uppercase tracking-widest text-accent-violet/80">Architecture</p>
            <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">A verified, real-time data pipeline</h2>
          </div>

          <div className="flex flex-col items-stretch gap-4 lg:flex-row lg:items-center">
            {PIPELINE.map(({ icon: Icon, label, sub, color }, i) => (
              <div key={label} className="flex flex-1 items-center gap-4 lg:flex-col lg:gap-3">
                <div className="flex flex-1 flex-col items-center rounded-2xl border border-white/10 bg-white/[0.03] px-6 py-6 text-center lg:w-full">
                  <Icon className={`h-8 w-8 ${color}`} />
                  <p className="mt-3 font-semibold">{label}</p>
                  <p className="text-xs text-white/40">{sub}</p>
                </div>
                {i < PIPELINE.length - 1 && (
                  <ArrowRight className="h-5 w-5 shrink-0 rotate-90 text-white/25 lg:rotate-0" />
                )}
              </div>
            ))}
          </div>

          <div className="mt-6 flex items-center justify-center gap-3 rounded-2xl border border-accent-violet/20 bg-gradient-to-r from-accent-violet/10 to-accent-cyan/10 px-6 py-4 text-center">
            <BrainCircuit className="h-5 w-5 shrink-0 text-accent-violet" />
            <p className="text-sm text-white/70">
              The <b className="text-white">Brain</b> plans, configures & <b className="text-white">verifies every step</b> across the whole pipeline.
            </p>
          </div>
        </div>
      </section>

      {/* Verticals */}
      <section id="verticals" className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="mb-12 text-center">
          <p className="text-sm font-semibold uppercase tracking-widest text-accent-pink/80">Verticals</p>
          <h2 className="mt-2 text-3xl font-bold tracking-tight sm:text-4xl">Three business verticals, out of the box</h2>
        </div>
        <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
          {VERTICALS.map(({ icon: Icon, title, desc, accent }) => (
            <div key={title} className={`glass-hover bg-gradient-to-br ${accent} p-7`}>
              <Icon className="h-9 w-9 text-white/90" />
              <h3 className="mt-4 text-xl font-semibold">{title}</h3>
              <p className="mt-2 text-sm leading-relaxed text-white/55">{desc}</p>
            </div>
          ))}
        </div>
      </section>

      {/* CTA band */}
      <section className="mx-auto max-w-7xl px-5 py-16 sm:px-8">
        <div className="glass relative overflow-hidden p-10 text-center sm:p-16">
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
              className="group mx-auto mt-8 flex items-center justify-center gap-2 rounded-xl bg-gradient-to-r from-accent-cyan to-accent-violet px-7 py-3.5 text-sm font-semibold text-white shadow-lg shadow-accent-cyan/25 transition hover:opacity-90 active:scale-[0.98]"
            >
              <Sparkles className="h-4 w-4" />
              Run the live demo
              <ArrowRight className="h-4 w-4 transition group-hover:translate-x-0.5" />
            </button>
          </div>
        </div>
      </section>

      {/* Footer */}
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
