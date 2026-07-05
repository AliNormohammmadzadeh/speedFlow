"""Backtesting engine + risk management for the trading bot (task 5.3).

Pure functions so the strategy/risk logic is testable without Kafka or a broker.
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from typing import Any


@dataclass
class RiskConfig:
    """Risk-management parameters applied to both live trading and backtests."""

    position_size_usd: float = 1000.0
    max_position_usd: float = 5000.0
    stop_loss_pct: float = 5.0
    take_profit_pct: float = 10.0
    max_daily_loss_usd: float = 2000.0

    def to_dict(self) -> dict[str, float]:
        return {
            "position_size_usd": self.position_size_usd,
            "max_position_usd": self.max_position_usd,
            "stop_loss_pct": self.stop_loss_pct,
            "take_profit_pct": self.take_profit_pct,
            "max_daily_loss_usd": self.max_daily_loss_usd,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "RiskConfig":
        base = cls()
        for k in base.to_dict():
            if data.get(k) is not None:
                setattr(base, k, float(data[k]))
        return base


def generate_price_series(symbol: str, n: int = 120, seed: int | None = None,
                          start_price: float = 100.0, vol: float = 0.02, drift: float = 0.0008) -> list[float]:
    """Deterministic synthetic OHLC-close random walk (geometric Brownian motion)."""
    rng = random.Random(seed if seed is not None else hash(symbol) & 0xFFFFFFFF)
    price = start_price
    series = [round(price, 4)]
    for _ in range(max(1, n) - 1):
        shock = rng.gauss(drift, vol)
        price = max(0.01, price * (1 + shock))
        series.append(round(price, 4))
    return series


def momentum_signals(prices: list[float], lookback: int = 5,
                     buy_threshold: float = 0.01, sell_threshold: float = -0.01) -> list[str]:
    """Simple momentum: compare price to its lookback moving average."""
    signals = ["hold"] * len(prices)
    for i in range(lookback, len(prices)):
        window = prices[i - lookback:i]
        avg = sum(window) / len(window)
        momentum = (prices[i] - avg) / avg if avg else 0.0
        if momentum >= buy_threshold:
            signals[i] = "buy"
        elif momentum <= sell_threshold:
            signals[i] = "sell"
    return signals


@dataclass
class BacktestResult:
    equity_curve: list[dict] = field(default_factory=list)
    trades: list[dict] = field(default_factory=list)
    metrics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {"equity_curve": self.equity_curve, "trades": self.trades, "metrics": self.metrics}


def run_backtest(prices: list[float], risk: RiskConfig, initial_capital: float = 100000.0,
                 lookback: int = 5, buy_threshold: float = 0.01, sell_threshold: float = -0.01) -> BacktestResult:
    """Long/flat momentum backtest with stop-loss / take-profit / daily-loss halting.

    Returns an equity curve, per-trade log, and summary risk metrics.
    """
    signals = momentum_signals(prices, lookback, buy_threshold, sell_threshold)
    cash = float(initial_capital)
    units = 0.0
    entry_price = 0.0
    realized_pnl = 0.0
    day_loss = 0.0
    halted = False
    trades: list[dict] = []
    equity_curve: list[dict] = []
    peak_equity = initial_capital
    max_drawdown = 0.0
    returns: list[float] = []
    prev_equity = initial_capital

    def close_position(i: int, price: float, reason: str):
        nonlocal cash, units, entry_price, realized_pnl, day_loss
        if units <= 0:
            return
        proceeds = units * price
        pnl = proceeds - units * entry_price
        cash += proceeds
        realized_pnl += pnl
        day_loss += min(0.0, pnl)
        trades.append({
            "step": i, "side": "sell", "price": round(price, 4),
            "units": round(units, 6), "pnl_usd": round(pnl, 2), "reason": reason,
        })
        units = 0.0
        entry_price = 0.0

    for i, price in enumerate(prices):
        # Risk exits on an open position.
        if units > 0:
            change_pct = (price - entry_price) / entry_price * 100 if entry_price else 0.0
            if change_pct <= -risk.stop_loss_pct:
                close_position(i, price, "stop_loss")
            elif change_pct >= risk.take_profit_pct:
                close_position(i, price, "take_profit")

        # Daily-loss circuit breaker halts new entries.
        if abs(day_loss) >= risk.max_daily_loss_usd:
            halted = True

        sig = signals[i]
        if sig == "buy" and units == 0 and not halted:
            alloc = min(risk.position_size_usd, risk.max_position_usd, cash)
            if alloc > 0:
                units = alloc / price
                entry_price = price
                cash -= alloc
                trades.append({
                    "step": i, "side": "buy", "price": round(price, 4),
                    "units": round(units, 6), "pnl_usd": 0.0, "reason": "signal",
                })
        elif sig == "sell" and units > 0:
            close_position(i, price, "signal")

        equity = cash + units * price
        peak_equity = max(peak_equity, equity)
        drawdown = (peak_equity - equity) / peak_equity * 100 if peak_equity else 0.0
        max_drawdown = max(max_drawdown, drawdown)
        if prev_equity:
            returns.append((equity - prev_equity) / prev_equity)
        prev_equity = equity
        equity_curve.append({"step": i, "price": round(price, 4), "equity_usd": round(equity, 2)})

    # Liquidate any open position at the last price.
    if units > 0:
        close_position(len(prices) - 1, prices[-1], "final_liquidation")

    final_equity = cash
    total_return_pct = (final_equity - initial_capital) / initial_capital * 100 if initial_capital else 0.0
    wins = [t for t in trades if t["side"] == "sell" and t["pnl_usd"] > 0]
    closed = [t for t in trades if t["side"] == "sell"]
    win_rate = len(wins) / len(closed) if closed else 0.0
    mean_ret = sum(returns) / len(returns) if returns else 0.0
    std_ret = math.sqrt(sum((r - mean_ret) ** 2 for r in returns) / len(returns)) if len(returns) > 1 else 0.0
    sharpe = (mean_ret / std_ret * math.sqrt(252)) if std_ret else 0.0

    metrics = {
        "initial_capital_usd": round(initial_capital, 2),
        "final_equity_usd": round(final_equity, 2),
        "total_return_pct": round(total_return_pct, 2),
        "realized_pnl_usd": round(realized_pnl, 2),
        "num_trades": len(closed),
        "win_rate": round(win_rate, 3),
        "sharpe_ratio": round(sharpe, 3),
        "max_drawdown_pct": round(max_drawdown, 2),
        "halted_on_daily_loss": halted,
    }
    return BacktestResult(equity_curve=equity_curve, trades=trades, metrics=metrics)
