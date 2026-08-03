import { useEffect, useState } from 'react'
import { BrainCircuit, CheckCircle2, XCircle, MinusCircle, Play, ListTree } from 'lucide-react'
import { api } from '../api'
import { Card, PageHeader, StatusBadge } from '../components/ui'
import { useDetail } from '../context/DetailContext'

type Objective = {
  objective: string
  goal: string
  phase_count: number
  step_count: number
  variables: Record<string, any>
}

function StepStatusIcon({ status }: { status: string }) {
  if (status === 'passed') return <CheckCircle2 className="h-4 w-4 text-emerald-400" />
  if (status === 'skipped') return <MinusCircle className="h-4 w-4 text-white/30" />
  return <XCircle className="h-4 w-4 text-red-400" />
}

export default function Brain() {
  const [objectives, setObjectives] = useState<Objective[]>([])
  const [selected, setSelected] = useState<string | null>(null)
  const [plan, setPlan] = useState<any>(null)
  const [report, setReport] = useState<any>(null)
  const [busy, setBusy] = useState<'' | 'plan' | 'execute'>('')
  const [err, setErr] = useState<string | null>(null)
  const { openDetail } = useDetail()

  useEffect(() => {
    api.brainObjectives()
      .then(d => {
        const list: Objective[] = d.objectives || []
        setObjectives(list)
        if (list.length && !selected) setSelected(list[0].objective)
      })
      .catch(e => setErr(String(e)))
  }, [])

  const current = objectives.find(o => o.objective === selected)

  const buildPlan = async () => {
    if (!selected) return
    setBusy('plan'); setErr(null); setReport(null)
    try {
      setPlan(await api.brainPlan({ objective: selected }))
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy('')
    }
  }

  const execute = async () => {
    if (!selected) return
    setBusy('execute'); setErr(null)
    try {
      const res = await api.brainExecute({ objective: selected })
      setPlan(res.plan)
      setReport(res.report)
    } catch (e) {
      setErr(String(e))
    } finally {
      setBusy('')
    }
  }

  const resultForStep = (stepId: string) =>
    report?.steps?.find((s: any) => s.step_id === stepId)

  const summary = report?.summary

  return (
    <div>
      <PageHeader
        title="Brain"
        subtitle="Agentic hierarchical planning — decompose an objective, resolve configs, execute & verify every step"
      />

      {err && (
        <Card className="mb-6 border border-red-500/30">
          <p className="text-sm text-red-300">{err}</p>
        </Card>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        {objectives.map(o => (
          <Card
            key={o.objective}
            onClick={() => { setSelected(o.objective); setPlan(null); setReport(null) }}
            className={`group ${selected === o.objective ? 'ring-2 ring-accent-cyan' : ''}`}
          >
            <div className="flex items-start justify-between">
              <div className="flex items-center gap-2">
                <BrainCircuit className="h-5 w-5 text-accent-violet" />
                <h4 className="font-semibold">{o.objective}</h4>
              </div>
              <span className="rounded-full bg-white/5 px-2 py-0.5 text-[11px] text-white/50">
                {o.phase_count} phases · {o.step_count} steps
              </span>
            </div>
            <p className="mt-2 text-sm text-white/50">{o.goal}</p>
          </Card>
        ))}
      </div>

      {current && (
        <Card className="mt-8">
          <div className="flex flex-wrap items-center justify-between gap-4">
            <div>
              <h3 className="text-lg font-semibold">{current.objective}</h3>
              <p className="mt-1 text-sm text-white/50">{current.goal}</p>
            </div>
            <div className="flex gap-3">
              <button type="button" onClick={buildPlan} disabled={busy !== ''} className="btn-action-secondary px-5">
                <ListTree className="mr-2 inline h-4 w-4" />
                {busy === 'plan' ? 'Planning…' : 'Build Plan'}
              </button>
              <button type="button" onClick={execute} disabled={busy !== ''} className="btn-action-primary px-5">
                <Play className="mr-2 inline h-4 w-4" />
                {busy === 'execute' ? 'Executing…' : 'Execute & Verify'}
              </button>
            </div>
          </div>

          <div className="mt-4 rounded-xl bg-black/30 p-4">
            <p className="mb-2 text-xs uppercase tracking-wide text-white/40">Resolved variables / configs</p>
            <div className="flex flex-wrap gap-2">
              {Object.entries((plan?.variables) || current.variables || {}).map(([k, v]) => (
                <span key={k} className="rounded-lg bg-white/5 px-2.5 py-1 text-xs">
                  <span className="text-accent-cyan">{k}</span>
                  <span className="text-white/40"> = </span>
                  <span className="text-white/80">{typeof v === 'object' ? JSON.stringify(v) : String(v)}</span>
                </span>
              ))}
            </div>
          </div>
        </Card>
      )}

      {summary && (
        <Card className="mt-6">
          <div className="flex flex-wrap items-center gap-6">
            <div className="flex items-center gap-2">
              <StatusBadge status={report.success ? 'up' : 'down'} />
              <span className="text-sm text-white/60">{report.success ? 'All steps verified' : 'Verification failed'}</span>
            </div>
            <div className="text-sm text-white/60">
              Steps <span className="font-semibold text-emerald-300">{summary.passed}</span>/{summary.total} passed
              {summary.failed ? <span className="ml-2 text-red-300">· {summary.failed} failed</span> : null}
              {summary.skipped ? <span className="ml-2 text-white/40">· {summary.skipped} skipped</span> : null}
            </div>
            <div className="text-sm text-white/60">
              Checks <span className="font-semibold text-emerald-300">{summary.checks_passed}</span>/{summary.checks}
            </div>
          </div>
        </Card>
      )}

      {plan && (
        <div className="mt-6 space-y-6">
          {plan.phases.map((phase: any, pi: number) => (
            <Card key={phase.id}>
              <div className="mb-4 flex items-center gap-3">
                <span className="flex h-7 w-7 items-center justify-center rounded-full bg-accent-violet/20 text-sm font-bold text-accent-violet">
                  {pi + 1}
                </span>
                <div>
                  <h4 className="font-semibold">{phase.name}</h4>
                  {phase.description && <p className="text-xs text-white/40">{phase.description}</p>}
                </div>
              </div>
              <div className="space-y-3">
                {phase.tasks.map((task: any) => (
                  <div key={task.id} className="rounded-xl border border-white/10 p-3">
                    <p className="mb-2 text-sm font-medium text-white/70">{task.name}</p>
                    <div className="space-y-2">
                      {task.steps.map((step: any) => {
                        const res = resultForStep(step.id)
                        return (
                          <button
                            key={step.id}
                            type="button"
                            onClick={() => openDetail({
                              title: step.name,
                              subtitle: `${step.action} · ${res?.status || 'not run'}`,
                              kind: 'generic',
                              logName: 'orchestrator',
                              data: { step, result: res },
                            })}
                            className="flex w-full items-center justify-between rounded-lg bg-black/30 px-3 py-2 text-left transition hover:bg-black/50"
                          >
                            <div className="flex min-w-0 items-center gap-2">
                              {res ? <StepStatusIcon status={res.status} /> : <MinusCircle className="h-4 w-4 text-white/20" />}
                              <span className="truncate text-sm">{step.name}</span>
                              <span className="rounded bg-white/5 px-1.5 py-0.5 text-[10px] text-white/40">{step.action}</span>
                            </div>
                            <div className="flex items-center gap-2 text-xs text-white/40">
                              {res?.verification && (
                                <span>
                                  {res.verification.checks.filter((c: any) => c.passed).length}/{res.verification.checks.length} checks
                                </span>
                              )}
                              {res?.duration_ms != null && <span>{res.duration_ms} ms</span>}
                            </div>
                          </button>
                        )
                      })}
                    </div>
                  </div>
                ))}
              </div>
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}
