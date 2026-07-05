import { useState } from 'react'
import { Area, AreaChart, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { api } from '../api'
import { Card, PageHeader, StatCard, usePoll } from '../components/ui'
import { useDetail } from '../context/DetailContext'

export default function Trading() {
  const { data: risk, refresh: refreshRisk } = usePoll(() => api.tradingRisk(), 8000)
  const { data: positions } = usePoll(() => api.tradingPositions(), 5000)
  const { openDetail } = useDetail()

  const [symbol, setSymbol] = useState('BTCUSD')
  const [periods, setPeriods] = useState(120)
  const [capital, setCapital] = useState(100000)
  const [result, setResult] = useState<any>(null)
  const [message, setMessage] = useState('')

  const [posSize, setPosSize] = useState('')
  const [stopLoss, setStopLoss] = useState('')
  const [takeProfit, setTakeProfit] = useState('')

  const runBacktest = async () => {
    setMessage('Running backtest…')
    try {
      const r = await api.tradingBacktest({ symbol, periods: Number(periods), initial_capital: Number(capital), seed: 42 })
      setResult(r)
      setMessage('')
    } catch (e) {
      setMessage(String(e))
    }
  }

  const saveRisk = async () => {
    const body: any = {}
    if (posSize) body.position_size_usd = Number(posSize)
    if (stopLoss) body.stop_loss_pct = Number(stopLoss)
    if (takeProfit) body.take_profit_pct = Number(takeProfit)
    try {
      await api.updateTradingRisk(body)
      setMessage('Risk parameters updated')
      refreshRisk()
    } catch (e) {
      setMessage(String(e))
    }
  }

  const equity = (result?.equity_curve ?? []).map((p: any) => ({ step: p.step, equity: p.equity_usd }))
  const m = result?.metrics

  return (
    <div>
      <PageHeader title="Trading — Backtesting & Risk" subtitle="Momentum backtests, risk management, and a mock broker" />

      <div className="mb-6 grid grid-cols-1 gap-6 lg:grid-cols-3">
        <Card className="lg:col-span-2">
          <h3 className="mb-4 text-lg font-semibold">Backtest</h3>
          <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-3">
            <input className="input-field" value={symbol} onChange={e => setSymbol(e.target.value)} placeholder="Symbol" />
            <input className="input-field" type="number" value={periods} onChange={e => setPeriods(Number(e.target.value))} placeholder="Periods" />
            <input className="input-field" type="number" value={capital} onChange={e => setCapital(Number(e.target.value))} placeholder="Capital USD" />
          </div>
          <button type="button" onClick={runBacktest} className="btn-action-primary w-full sm:w-auto sm:px-8">Run Backtest</button>
          {message && <p className="mt-3 text-sm text-white/60">{message}</p>}

          <div className="mt-4 h-56">
            {equity.length > 0 ? (
              <ResponsiveContainer width="100%" height="100%">
                <AreaChart data={equity}>
                  <defs>
                    <linearGradient id="gEq" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="0%" stopColor="#34d399" stopOpacity={0.5} />
                      <stop offset="100%" stopColor="#34d399" stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <XAxis dataKey="step" stroke="#ffffff40" fontSize={11} />
                  <YAxis stroke="#ffffff40" fontSize={11} domain={['auto', 'auto']} />
                  <Tooltip contentStyle={{ background: '#12121a', border: '1px solid rgba(255,255,255,0.1)', borderRadius: 12 }} />
                  <Area type="monotone" dataKey="equity" name="Equity USD" stroke="#34d399" fill="url(#gEq)" strokeWidth={2} />
                </AreaChart>
              </ResponsiveContainer>
            ) : (
              <p className="text-white/40">Run a backtest to see the equity curve.</p>
            )}
          </div>
        </Card>

        <Card>
          <h3 className="mb-4 text-lg font-semibold">Risk Management</h3>
          {risk && (
            <div className="mb-4 space-y-1 text-sm text-white/60">
              <div className="flex justify-between"><span>Position size</span><span className="font-mono">${risk.position_size_usd}</span></div>
              <div className="flex justify-between"><span>Max position</span><span className="font-mono">${risk.max_position_usd}</span></div>
              <div className="flex justify-between"><span>Stop loss</span><span className="font-mono">{risk.stop_loss_pct}%</span></div>
              <div className="flex justify-between"><span>Take profit</span><span className="font-mono">{risk.take_profit_pct}%</span></div>
              <div className="flex justify-between"><span>Max daily loss</span><span className="font-mono">${risk.max_daily_loss_usd}</span></div>
            </div>
          )}
          <div className="space-y-2">
            <input className="input-field" value={posSize} onChange={e => setPosSize(e.target.value)} placeholder="Position size USD" />
            <input className="input-field" value={stopLoss} onChange={e => setStopLoss(e.target.value)} placeholder="Stop loss %" />
            <input className="input-field" value={takeProfit} onChange={e => setTakeProfit(e.target.value)} placeholder="Take profit %" />
            <button type="button" onClick={saveRisk} className="btn-action-secondary w-full">Update Risk</button>
          </div>
        </Card>
      </div>

      {m && (
        <div className="mb-6 grid grid-cols-2 gap-4 md:grid-cols-4">
          <StatCard label="Total Return" value={`${m.total_return_pct}%`} accent={m.total_return_pct >= 0 ? 'emerald' : undefined} onClick={() => openDetail({ title: 'Backtest metrics', kind: 'generic', data: m })} />
          <StatCard label="Realized PnL" value={`$${m.realized_pnl_usd}`} accent="cyan" />
          <StatCard label="Win Rate" value={`${Math.round((m.win_rate ?? 0) * 100)}%`} accent="violet" />
          <StatCard label="Max Drawdown" value={`${m.max_drawdown_pct}%`} />
        </div>
      )}

      <Card>
        <h3 className="mb-4 text-lg font-semibold">Mock Broker — Positions & Orders</h3>
        {positions && (
          <p className="mb-3 text-sm text-white/50">
            Provider: <span className="font-mono text-accent-cyan">{positions.provider}</span> · Cash: <span className="font-mono">${positions.cash_usd}</span>
          </p>
        )}
        <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
          <div>
            <p className="mb-2 text-xs uppercase text-white/40">Open Positions</p>
            <div className="space-y-1">
              {(positions?.positions ?? []).map((p: any) => (
                <div key={p.symbol} className="clickable-row">
                  <span className="font-mono text-white/70">{p.symbol}</span>
                  <span>{p.units} @ ${p.avg_price}</span>
                </div>
              ))}
              {!(positions?.positions ?? []).length && <p className="py-3 text-center text-white/40">No open positions</p>}
            </div>
          </div>
          <div>
            <p className="mb-2 text-xs uppercase text-white/40">Recent Orders</p>
            <div className="max-h-48 space-y-1 overflow-y-auto">
              {(positions?.recent_orders ?? []).slice().reverse().map((o: any) => (
                <div key={o.order_id} className="clickable-row">
                  <span className={o.side === 'buy' ? 'text-emerald-400' : 'text-red-400'}>{o.side.toUpperCase()}</span>
                  <span className="font-mono text-white/60">{o.symbol}</span>
                  <span className="text-white/40">${o.notional_usd}</span>
                </div>
              ))}
              {!(positions?.recent_orders ?? []).length && <p className="py-3 text-center text-white/40">No orders yet</p>}
            </div>
          </div>
        </div>
      </Card>
    </div>
  )
}
