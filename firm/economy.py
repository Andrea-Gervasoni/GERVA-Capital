"""
Economia interna: Gerva-Coin (GC), alpha netto dei pod, bonus pool, riallocazione del capitale.

  * 1 GC = 1/gc_per_eur EUR di budget di calcolo REALE (i GC ripartiscono il budget di Andrea,
    non lo aumentano).
  * Alpha netto di un pod = alpha (vs Pod Zero, al netto di beta) * capitale
                           - costi di transazione - tassa sul capitale - costo di calcolo.
    Senza questa sottrazione, in un mercato che sale tutti sembrano geni.
  * Riallocazione mensile (DECISIONS D6): stima bayesiana normale-normale dell'alpha annuo con
    prior N(0, tau^2) -> con pochi giorni la stima resta vicina a zero (shrinkage); campione
    minimo; penalita' per drawdown e correlazione; spostamento massimo per mese; se nessun pod
    batte il Pod Zero con evidenza, il capitale resta al Pod Zero.
"""
from __future__ import annotations

import math

import numpy as np
from scipy.stats import norm

from . import db, events, pods, gateway
from . import settings as S

TD = 252


# ---------------------------------------------------------------------------
# Gerva-Coin
# ---------------------------------------------------------------------------
def gc_balance(agent_id: str) -> float:
    """Saldo MATURATO: il bonus differito (kind='differito') non e' ancora dell'agente."""
    return float(db.one("SELECT COALESCE(SUM(amount),0) s FROM gc_ledger WHERE agent_id=? AND kind!='differito'",
                        (agent_id,))["s"])


def gc_unvested(agent_id: str) -> float:
    return float(db.one("SELECT COALESCE(SUM(amount),0) s FROM gc_ledger WHERE agent_id=? AND kind='differito'",
                        (agent_id,))["s"])


def gc_move(agent_id: str, amount: float, kind: str, memo: str, pod: str | None = None):
    if kind == "spesa" and gc_balance(agent_id) + amount < 0:
        raise ValueError("Gerva-Coin insufficienti")
    db.ex("INSERT INTO gc_ledger(ts,agent_id,pod,amount,kind,memo) VALUES(?,?,?,?,?,?)",
          (db.now_iso(), agent_id, pod, float(amount), kind, memo))
    events.publish("gc.move", "economia", dict(agente=agent_id, importo=round(amount, 2), tipo=kind, memo=memo))


def gc_history(agent_id: str) -> dict:
    rows = db.q("SELECT kind, SUM(amount) s FROM gc_ledger WHERE agent_id=? GROUP BY kind", (agent_id,))
    return {r["kind"]: r["s"] for r in rows} | {"saldo": gc_balance(agent_id), "differito": gc_unvested(agent_id)}


# ---------------------------------------------------------------------------
# Alpha netto
# ---------------------------------------------------------------------------
def alpha_beta(r_pod, r_bench) -> tuple[float, float, float]:
    """OLS r_pod = a + b r_bench + e. Ritorna (alpha giornaliero, beta, sd dei residui)."""
    y, x = np.asarray(r_pod, float), np.asarray(r_bench, float)
    n = min(len(x), len(y))
    y, x = y[-n:], x[-n:]
    if n < 3 or np.var(x) == 0:
        return (float(np.mean(y)) if n else 0.0), 0.0, (float(np.std(y, ddof=1)) if n > 1 else 0.0)
    b = float(np.cov(x, y, ddof=1)[0, 1] / np.var(x, ddof=1))
    a = float(y.mean() - b * x.mean())
    e = y - a - b * x
    return a, b, float(e.std(ddof=2))


def compute_cost_eur(pid: str) -> float:
    heads = [r["id"] for r in db.q("SELECT id FROM agents WHERE profile LIKE ?", (f'%"pod": "{pid}"%',))]
    if not heads:
        return 0.0
    ph = ",".join("?" * len(heads))
    return float(db.one(f"SELECT COALESCE(SUM(cost_eur),0) s FROM llm_calls WHERE agent_id IN ({ph})",
                        tuple(heads))["s"])


def net_alpha(pid: str) -> dict:
    r = pods.pod_returns(pid)
    rb = pods.pod_returns("pod_zero")
    a, b, sd = alpha_beta(r, rb)
    n = len(r)
    book = gateway.pod_book(pid)
    cap = book["base"]
    years = n / TD
    alpha_eur = a * n * cap
    tax = float(S.get("pods.capital_tax_annual")) * cap * years
    comp = compute_cost_eur(pid)
    # le commissioni sono gia' dentro i rendimenti del pod (P&L netto): si riportano per trasparenza
    return dict(pod=pid, giorni=n, alpha_giornaliero=a, beta=b, sd_residui=sd, alpha_eur=alpha_eur,
                costi_transazione_eur=book["fees"], tassa_capitale_eur=tax, costo_calcolo_eur=comp,
                alpha_netto_eur=alpha_eur - tax - comp)


# ---------------------------------------------------------------------------
# Stima bayesiana con shrinkage
# ---------------------------------------------------------------------------
def posterior_alpha(alpha_daily: float, sd_resid_daily: float, n_days: int, prior_sd_annual: float) -> dict:
    """Prior N(0, tau^2) sull'alpha annuo; verosimiglianza N(alpha_hat, se^2), se = sigma*sqrt(252)/sqrt(anni)."""
    if n_days < 2 or sd_resid_daily <= 0:
        return dict(media=0.0, sd=prior_sd_annual, p_positivo=0.5, peso_dati=0.0)
    a_ann = alpha_daily * TD
    se = sd_resid_daily * math.sqrt(TD) / math.sqrt(n_days / TD)
    w = prior_sd_annual ** 2 / (prior_sd_annual ** 2 + se ** 2)
    mean = w * a_ann
    sd = math.sqrt(w) * se
    return dict(media=mean, sd=sd, p_positivo=float(norm.cdf(mean / sd)) if sd > 0 else 0.5, peso_dati=w)


def reallocate(apply: bool = True, p_min: float = 0.80, dd_penalty: float = 0.5, corr_penalty: float = 0.02) -> list[dict]:
    lim = S.risk_limits()["pod"]
    min_days = int(S.get("economy.min_days_for_realloc"))
    max_shift = float(S.get("economy.max_monthly_shift"))
    tau = float(S.get("economy.prior_alpha_sd_annual"))
    corr = pods.mean_pod_correlation() or 0.0
    out = []
    for p in pods.all_pods():
        if p["id"] == "pod_zero" or p["status"] == "chiuso":
            continue
        na = net_alpha(p["id"])
        post = posterior_alpha(na["alpha_giornaliero"], na["sd_residui"], na["giorni"], tau)
        dd = gateway.pod_book(p["id"])["drawdown"]
        score = post["media"] + dd_penalty * dd - corr_penalty * max(corr, 0)
        cur = p["capital_frac"]
        if na["giorni"] < min_days:
            new, why = cur, f"campione insufficiente ({na['giorni']}/{min_days} giorni)"
        elif post["p_positivo"] >= p_min and score > 0:
            new, why = min(cur + max_shift, lim["max_capital_frac"]), f"P(alpha>0)={post['p_positivo']:.2f}"
        elif post["p_positivo"] < 0.5 or score < 0:
            new, why = max(cur - max_shift, 0.0), f"P(alpha>0)={post['p_positivo']:.2f}, punteggio {score:.3f}"
        else:
            new, why = cur, "evidenza non sufficiente: capitale invariato"
        if apply and abs(new - cur) > 1e-12:
            pods.set_capital(p["id"], new, f"riallocazione mensile: {why}", actor="economia")
        out.append(dict(pod=p["id"], da=cur, a=new, motivo=why, posterior=post, alpha_netto=na))
    return out


# ---------------------------------------------------------------------------
# Bonus pool
# ---------------------------------------------------------------------------
def distribute_bonus(pid: str) -> dict:
    na = net_alpha(pid)
    # l'alpha netto e' cumulato dall'inizio: si paga solo la parte sopra quella gia' pagata (high-water mark),
    # altrimenti lo stesso guadagno verrebbe ripagato ogni mese
    paid = float(db.runtime_get(f"bonus_paid_alpha:{pid}", 0.0) or 0.0)
    new_alpha = na["alpha_netto_eur"] - paid
    if new_alpha <= 0:
        return dict(pod=pid, bonus_gc=0.0, motivo="nessun alpha netto nuovo sopra il massimo gia' pagato")
    db.runtime_set(f"bonus_paid_alpha:{pid}", na["alpha_netto_eur"])
    pool_gc = new_alpha * float(S.get("economy.bonus_share")) * float(S.get("economy.gc_per_eur"))
    head = pods.get(pid)["head"]
    members = [r["id"] for r in db.q("SELECT id FROM agents WHERE profile LIKE ? AND kind='llm'",
                                     (f'%"pod": "{pid}"%',))]
    contrib = {m: max(0.0, float(db.one("SELECT COALESCE(SUM(value),0) s FROM evaluations WHERE agent_id=? "
                                       "AND metric='contributo_alpha'", (m,))["s"])) for m in members if m != head}
    head_share = float(S.get("economy.head_share")) if contrib and sum(contrib.values()) > 0 else 1.0
    from . import compensation
    compensation.award_bonus(head, pool_gc * head_share, f"bonus pool del pod {pid}", pid)
    tot = sum(contrib.values())
    for m, c in contrib.items():
        if tot > 0 and c > 0:
            compensation.award_bonus(m, pool_gc * (1 - head_share) * c / tot, f"bonus per contributo nel pod {pid}", pid)
    return dict(pod=pid, bonus_gc=pool_gc, capo_pod=head, quota_capo=head_share)


def leaderboard() -> dict:
    from quantlab import stats as QS
    rows = []
    for p in pods.all_pods():
        r = pods.pod_returns(p["id"])
        book = gateway.pod_book(p["id"]) if p["id"] != "pod_zero" else None
        sh, ci = None, None
        if len(r) >= 30 and np.std(r) > 0:
            sh = float(np.mean(r) / np.std(r, ddof=1) * math.sqrt(TD))
            ci = QS.sharpe_ci_bootstrap(r, n_boot=500)
        rows.append(dict(pod=p["id"], nome=p["name"], capitale=p["capital_frac"], stato=p["status"],
                         giorni=len(r), sharpe=sh, sharpe_ci90=ci,
                         drawdown=book["drawdown"] if book else None,
                         alpha_netto_eur=net_alpha(p["id"])["alpha_netto_eur"] if p["id"] != "pod_zero" else None))
    people = [dict(agente=r["agent_id"], gc=r["s"]) for r in
              db.q("SELECT agent_id, SUM(amount) s FROM gc_ledger WHERE kind!='differito' GROUP BY agent_id "
                   "ORDER BY s DESC LIMIT 20")]
    return dict(pod=rows, persone=people)
