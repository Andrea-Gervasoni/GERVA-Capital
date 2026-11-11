"""Libro dei trade a margine isolato: la leva alta non deve mai poter mettere a rischio il conto."""
import math

import pytest

from gerva.risk.isolated import (BookLimits, STOP_TO_LIQ, TradeBook, safe_leverage, tier_for)


def book():
    return TradeBook(BookLimits())


def test_safe_leverage_keeps_stop_before_liquidation():
    for stop in (0.004, 0.009, 0.017, 0.027, 0.05, 0.10):
        L = safe_leverage(stop)
        assert stop <= STOP_TO_LIQ * (1 / L - 0.005) + 1e-12
    assert safe_leverage(0.017) == pytest.approx(30, abs=0.2)
    assert safe_leverage(0.05) == pytest.approx(11.3, abs=0.2)


def test_no_trade_below_confirmed_score():
    b = book()
    for s in (None, float("nan"), 0.2, 0.60):
        assert not b.propose("BTC", 1, 100.0, 0.05, s, 10_000, 50).ok
    assert tier_for(0.61, b.limits).name == "confermato"
    assert tier_for(0.80, b.limits).name == "eccezionale"


def test_confirmed_trade_numbers():
    d = book().propose("BTC", 1, 100.0, 0.05, 0.70, 10_000, 50)
    t = d.trade
    assert d.ok and t.tier == "confermato"
    assert t.risk == pytest.approx(100.0)                 # 1% di 10.000
    assert t.notional == pytest.approx(2_000.0)           # 100 / 5%
    assert t.leverage == pytest.approx(safe_leverage(0.05))
    assert t.margin == pytest.approx(t.notional / t.leverage)
    assert t.stop == pytest.approx(95.0) and t.liquidation < t.stop
    assert d.checks["stop_over_liq"] <= STOP_TO_LIQ + 1e-9
    assert t.margin <= 2.0 * t.risk                       # il massimo che si puo' perdere resta vicino al rischio dichiarato


def test_exceptional_tight_is_30x_with_smaller_risk():
    d = book().propose("ETH", 1, 100.0, 0.05, 0.9, 10_000, 50, tight=True)
    assert d.ok and d.trade.leverage == pytest.approx(30, abs=0.2)
    assert d.trade.risk == pytest.approx(50.0)            # 0,5%: piu' leva, MENO rischio


def test_venue_cap_and_hard_cap_bind():
    assert book().propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 2).trade.leverage == 2          # sede a 2x: 2x
    b = TradeBook(BookLimits(exceptional_tight=BookLimits().exceptional_tight.__class__("x", 0.005, None, 0.004, 100.0, None)))
    assert b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 100, tight=True).trade.leverage <= 30


def test_ai_can_only_reduce():
    b = book()
    assert not b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, ai_multiplier=1.5).ok
    assert not b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, ai_multiplier=-0.1).ok
    assert not b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, ai_multiplier=0.0).ok
    half = b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, ai_multiplier=0.5).trade
    assert half.risk == pytest.approx(100.0)              # 2% dimezzato


def test_engine_scale_blocks_and_reduces():
    b = book()
    assert not b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, engine_scale=0.0).ok
    assert b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50, engine_scale=0.5).trade.risk == pytest.approx(100.0)


def test_book_limits_on_open_risk_margin_and_count():
    b = book()
    for s in ("BTC", "ETH", "SOL"):
        d = b.propose(s, 1, 100.0, 0.05, 0.9, 10_000, 50)
        assert d.ok
        b.add(d.trade)
    assert b.totals(10_000)["risk"] == pytest.approx(0.06)
    assert not b.propose("XRP", 1, 100.0, 0.05, 0.9, 10_000, 50).ok          # rischio aperto esaurito
    assert not b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50).ok          # gia' aperto
    assert b.totals(10_000)["margin"] <= b.limits.max_margin + 1e-9
    assert b.totals(10_000)["notional"] <= b.limits.max_notional + 1e-9


def test_loss_never_exceeds_isolated_margin_even_on_a_gap():
    b = book()
    t = b.propose("BTC", 1, 100.0, 0.05, 0.9, 10_000, 50).trade
    b.add(t)
    pnl = b.close("BTC", 40.0, 10_000)                    # crollo del 60% senza che lo stop sia eseguito
    assert pnl == pytest.approx(-t.margin)
    assert -pnl / 10_000 < 0.04                           # il conto perde meno del 4% con un trade al 2% di rischio


def test_daily_breaker_blocks_new_trades_and_flattens():
    b = book()
    for s in ("BTC", "ETH"):
        b.add(b.propose(s, 1, 100.0, 0.05, 0.9, 10_000, 50).trade)
    b.close("BTC", 95.0, 10_000)
    b.close("ETH", 95.0, 10_000)                          # -2% e -2% = -4%: niente nuovi trade
    assert b.day_pnl == pytest.approx(-0.04)
    assert not b.propose("SOL", 1, 100.0, 0.05, 0.9, 10_000, 50).ok
    b.new_day()
    b.add(b.propose("SOL", 1, 100.0, 0.05, 0.9, 10_000, 50).trade)
    b.day_pnl = -0.04
    b.close("SOL", 95.0, 10_000)
    assert b.must_flatten()


def test_trailing_stop_only_ratchets():
    b = book()
    t = b.propose("BTC", 1, 100.0, 0.05, 0.7, 10_000, 50).trade
    b.add(t)
    assert b.update_stop("BTC", 101.0, 99.0) == pytest.approx(95.0)           # 101 - 10% = 90,9: non peggiora lo stop
    assert b.update_stop("BTC", 120.0, 110.0) == pytest.approx(108.0)         # 120 * (1 - 2 * 5%)
    assert b.update_stop("BTC", 110.0, 100.0) == pytest.approx(108.0)         # mai indietro
    s = b.propose("ETH", -1, 100.0, 0.05, 0.7, 10_000, 50).trade
    b.add(s)
    assert s.stop == pytest.approx(105.0) and s.liquidation > s.stop
    assert b.update_stop("ETH", 90.0, 80.0) == pytest.approx(88.0)
    assert math.isclose(b.update_stop("ETH", 95.0, 85.0), 88.0)
