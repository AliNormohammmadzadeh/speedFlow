import { useEffect, useState } from 'react'
import { NavLink, useLocation } from 'react-router-dom'
import {
  Activity,
  Bot,
  ChevronRight,
  Cloud,
  Cpu,
  CreditCard,
  Layers,
  LayoutDashboard,
  LineChart,
  Menu,
  PanelLeftClose,
  PanelLeftOpen,
  Shapes,
  Users,
  Workflow,
  X,
  Zap,
} from 'lucide-react'
import { api } from '../api'
import DetailDrawer from './DetailDrawer'
import { DetailProvider } from '../context/DetailContext'
import { usePoll } from './ui'

const NAV = [
  { to: '/', icon: LayoutDashboard, label: 'Overview', desc: 'Health & pipeline' },
  { to: '/canvas', icon: Workflow, label: 'Pipeline Canvas', desc: 'Live flow topology' },
  { to: '/ingestion', icon: Cloud, label: 'Ingestion', desc: 'Scrapers & jobs' },
  { to: '/stream', icon: Cpu, label: 'Stream Compute', desc: 'Kafka & Flink' },
  { to: '/ai', icon: Bot, label: 'AI Intelligence', desc: 'Agents & bridges' },
  { to: '/apps', icon: Layers, label: 'Applications', desc: 'Serving APIs' },
  { to: '/trading', icon: LineChart, label: 'Trading', desc: 'Backtest & risk' },
  { to: '/verticals', icon: Shapes, label: 'Verticals', desc: 'Industry plug-ins' },
  { to: '/tenants', icon: Users, label: 'Tenants', desc: 'Plans & scrape' },
  { to: '/billing', icon: CreditCard, label: 'Billing', desc: 'Usage & rate limits' },
]

const PAGE_TITLES: Record<string, string> = {
  '/': 'Overview',
  '/canvas': 'Pipeline Canvas',
  '/ingestion': 'Ingestion',
  '/stream': 'Stream Compute',
  '/ai': 'AI Intelligence',
  '/apps': 'Applications',
  '/trading': 'Trading',
  '/verticals': 'Verticals',
  '/tenants': 'Tenants',
  '/billing': 'Billing',
}

export default function Layout({ children }: { children: React.ReactNode }) {
  const [mobileOpen, setMobileOpen] = useState(false)
  const [collapsed, setCollapsed] = useState(false)
  const location = useLocation()
  const { data: overview } = usePoll(() => api.overview(), 5000)

  useEffect(() => {
    setMobileOpen(false)
  }, [location.pathname])

  const pageTitle = PAGE_TITLES[location.pathname] || 'SpeedFlow'

  return (
    <DetailProvider>
      <div className="flex min-h-screen">
        {mobileOpen && (
          <button
            type="button"
            className="fixed inset-0 z-40 bg-black/70 backdrop-blur-sm lg:hidden"
            onClick={() => setMobileOpen(false)}
            aria-label="Close menu"
          />
        )}

        <aside
          className={`sidebar fixed inset-y-0 left-0 z-50 flex flex-col border-r border-white/10 bg-black/50 backdrop-blur-2xl transition-all duration-300 ease-out
            ${mobileOpen ? 'translate-x-0' : '-translate-x-full'}
            lg:translate-x-0
            ${collapsed ? 'lg:w-[5.25rem]' : 'lg:w-72'}
            w-72`}
        >
          <div className={`flex items-center gap-3 border-b border-white/10 ${collapsed ? 'justify-center px-3 py-5' : 'px-5 py-5'}`}>
            <div className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl bg-gradient-to-br from-accent-cyan to-accent-violet shadow-lg shadow-accent-cyan/20">
              <Zap className="h-5 w-5 text-white" />
            </div>
            {!collapsed && (
              <div className="min-w-0">
                <h1 className="text-lg font-bold tracking-tight">SpeedFlow</h1>
                <p className="text-xs text-white/45">Control Portal 2026</p>
              </div>
            )}
            <button
              type="button"
              className="btn-icon ml-auto lg:hidden"
              onClick={() => setMobileOpen(false)}
              aria-label="Close sidebar"
            >
              <X className="h-5 w-5" />
            </button>
          </div>

          <nav className="flex-1 space-y-1.5 overflow-y-auto p-3">
            {NAV.map(({ to, icon: Icon, label, desc }) => (
              <NavLink
                key={to}
                to={to}
                end={to === '/'}
                title={collapsed ? label : undefined}
                className={({ isActive }) =>
                  `nav-link group ${isActive ? 'nav-link-active' : ''} ${collapsed ? 'nav-link-collapsed' : ''}`
                }
              >
                <span className="nav-link-icon">
                  <Icon className="h-[1.125rem] w-[1.125rem]" />
                </span>
                {!collapsed && (
                  <>
                    <span className="min-w-0 flex-1">
                      <span className="block text-sm font-semibold">{label}</span>
                      <span className="nav-link-desc block text-[11px] text-white/40">{desc}</span>
                    </span>
                    <ChevronRight className="nav-link-chevron h-4 w-4 shrink-0 text-white/30" />
                  </>
                )}
              </NavLink>
            ))}
          </nav>

          <div className={`border-t border-white/10 p-3 ${collapsed ? 'flex flex-col items-center gap-2' : ''}`}>
            {!collapsed && overview && (
              <button
                type="button"
                className="mb-2 w-full rounded-xl bg-gradient-to-r from-emerald-500/10 to-cyan-500/10 px-3 py-2.5 text-left ring-1 ring-emerald-500/20 transition hover:ring-emerald-400/40"
              >
                <div className="flex items-center gap-2 text-xs">
                  <Activity className="h-3.5 w-3.5 text-emerald-400" />
                  <span className="text-white/60">Services online</span>
                </div>
                <p className="mt-1 text-lg font-bold text-emerald-300">
                  {overview.services_up}/{overview.services_total}
                </p>
              </button>
            )}
            <div className={`flex items-center gap-2 ${collapsed ? 'flex-col' : ''}`}>
              <button
                type="button"
                onClick={() => setCollapsed(c => !c)}
                className="btn-icon hidden lg:flex"
                aria-label={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
              >
                {collapsed ? <PanelLeftOpen className="h-5 w-5" /> : <PanelLeftClose className="h-5 w-5" />}
              </button>
              {!collapsed && (
                <span className="text-[10px] text-white/35">Live · 5s poll</span>
              )}
            </div>
          </div>
        </aside>

        <div className={`flex min-h-screen flex-1 flex-col transition-all duration-300 ${collapsed ? 'lg:ml-[5.25rem]' : 'lg:ml-72'}`}>
          <header className="sticky top-0 z-30 flex items-center gap-4 border-b border-white/10 bg-[#08080f]/80 px-4 py-3 backdrop-blur-xl sm:px-8">
            <button
              type="button"
              className="btn-icon lg:hidden"
              onClick={() => setMobileOpen(true)}
              aria-label="Open menu"
            >
              <Menu className="h-5 w-5" />
            </button>
            <button
              type="button"
              className="btn-icon hidden lg:flex"
              onClick={() => setCollapsed(c => !c)}
              aria-label="Toggle sidebar"
            >
              <Menu className="h-5 w-5" />
            </button>
            <div className="min-w-0 flex-1">
              <h2 className="truncate text-lg font-semibold">{pageTitle}</h2>
            </div>
            {overview && (
              <div className="hidden items-center gap-2 rounded-full bg-white/5 px-3 py-1.5 text-xs sm:flex">
                <span className="h-2 w-2 animate-pulse rounded-full bg-emerald-400" />
                <span className="text-white/60">{overview.services_up} services up</span>
              </div>
            )}
          </header>

          <main className="flex-1 p-4 sm:p-8">{children}</main>
        </div>
      </div>
      <DetailDrawer />
    </DetailProvider>
  )
}
