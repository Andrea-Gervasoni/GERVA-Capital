"""Verifica di backtest altrui: le proprieta' matematiche, non i numeri stampati."""
import math
import subprocess
import sys
import os

import pytest

from quantlab import luck, stats as QS


@pytest.mark.parametrize("k,n", [(7, 9), (0, 10), (10, 10), (4220, 5944)])
def test_wilson_endpoints_solve_the_score_equation(k, n):
    lo, hi = luck.wilson(k, n)
    z, ph = 1.6449, k / n
    for p in (lo, hi):
        if 0 < p < 1:
            assert abs(abs(ph - p) / math.sqrt(p * (1 - p) / n) - z) < 1e-3
    assert lo <= ph <= hi


def test_deflated_min_trl_is_where_dsr_reaches_95():
    sr_a, n_trials = 0.8, 55
    r = luck.check(sharpe_annual=sr_a, n_obs=2520, n_trials=n_trials)["sharpe"]
    n_star = round(r["min_trl_osservazioni"])
    m = QS.Moments(sr=sr_a / math.sqrt(252), n=n_star, skew=0.0, kurt=3.0)
    sr0 = QS.expected_max_sr(n_trials, luck._null_var(n_star, 0.0, 3.0))
    assert QS.psr(m, sr0) == pytest.approx(0.95, abs=0.005)


def test_trials_to_explain_matches_expected_max():
    sr = 1.2 / math.sqrt(252)
    n = luck.trials_to_explain(sr, 1000)
    v = luck._null_var(1000, 0.0, 3.0)
    assert QS.expected_max_sr(int(n), v) >= sr > QS.expected_max_sr(int(n * 0.98), v)


def test_claimed_hit_rate_coherence():
    assert not luck.check(trades=9, claimed_hit_rate=0.83)["coerenza"]["coerente"]     # 7/9=78%, 8/9=89%
    assert luck.check(trades=9, claimed_hit_rate=0.78)["coerenza"]["coerente"]
    assert luck.check(trades=6, claimed_hit_rate=0.83)["coerenza"]["coerente"]         # 5/6


def test_break_even_and_costs():
    r = luck.check(wins=60, trades=100, payoff_ratio=0.5, edge_per_trade=0.002, cost_per_trade=0.003)
    assert r["vincite"]["pareggio"] == pytest.approx(2 / 3)
    assert r["costi"]["margine_netto"] < 0


def test_cli_runs_without_a_database(tmp_path):
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out = subprocess.run([sys.executable, "firm.py", "check-backtest", "--trades", "9", "--hit-rate", "0.83"], cwd=root,
                         env=dict(os.environ, GERVA_VAR=str(tmp_path / "v")), capture_output=True, text=True)
    assert out.returncode == 0 and "Incoerenza" in out.stdout and not (tmp_path / "v").exists()
