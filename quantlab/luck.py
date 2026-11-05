"""
Verifica di un backtest altrui: quanto di quel risultato puo' essere fortuna?

Serve per i numeri che girano online ("83% di trade vincenti", "Sharpe 4,2", "$52 -> $4.392") e per le idee
che arrivano da fuori alla Ricerca. Usa gli stessi strumenti del cancello interno (quantlab.stats):

  * Sharpe: PSR contro 0, Sharpe massimo atteso per pura fortuna dopo N tentativi (Bailey & Lopez de Prado
    2014), Deflated Sharpe, lunghezza minima del track record (MinTRL), e "quanti tentativi a vuoto bastano
    per ottenere questo Sharpe per caso";
  * percentuale di vincite: intervallo di Wilson, p-value binomiale, coerenza tra percentuale dichiarata e
    numero di trade, e soglia di pareggio (la percentuale di vincite non dice nulla senza il rapporto
    guadagno medio / perdita media);
  * costi: quanto margine resta dopo commissioni e slippage per trade.

Non dimostra che una strategia funziona: dice solo se i numeri dichiarati bastano a escludere la fortuna.
"""
from __future__ import annotations

import math

from scipy.stats import binom, norm

from . import stats as QS


def wilson(k: int, n: int, z: float = 1.6449) -> tuple[float, float]:
    """Intervallo di Wilson (90% di default) per una proporzione: corretto anche con pochi trade."""
    if n <= 0:
        return 0.0, 1.0
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, c - h), min(1.0, c + h)


def _null_var(n_obs: int, skew: float, kurt: float) -> float:
    """Varianza degli Sharpe (per periodo) di strategie senza abilita': quella dello stimatore sotto H0."""
    m = QS.Moments(sr=0.0, n=n_obs, skew=skew, kurt=kurt)
    return QS.sharpe_se(m) ** 2


def trials_to_explain(sr_period: float, n_obs: int, skew: float = 0.0, kurt: float = 3.0,
                      var_trials: float | None = None) -> float:
    """Numero di tentativi indipendenti senza abilita' il cui MIGLIORE ci si aspetta arrivi a questo Sharpe."""
    v = var_trials if var_trials is not None else _null_var(n_obs, skew, kurt)
    if sr_period <= 0:
        return 1.0
    lo, hi = 1, 2
    while QS.expected_max_sr(hi, v) < sr_period:
        hi *= 2
        if hi > 1e15:
            return math.inf
    while hi - lo > max(1, lo // 100):                    # 1% di precisione basta
        mid = (lo + hi) // 2
        if QS.expected_max_sr(mid, v) < sr_period:
            lo = mid
        else:
            hi = mid
    return float(hi)


def check(*, sharpe_annual: float | None = None, n_obs: int | None = None, periods: int = 252,
          n_trials: int = 1, var_trials: float | None = None, skew: float = 0.0, kurt: float = 3.0,
          wins: int | None = None, trades: int | None = None, claimed_hit_rate: float | None = None,
          payoff_ratio: float | None = None, edge_per_trade: float | None = None,
          cost_per_trade: float | None = None) -> dict:
    """Tutti gli argomenti sono facoltativi: si valuta cio' che e' dichiarato.
    sharpe_annual + n_obs (osservazioni alla frequenza `periods` per anno);
    wins/trades (o claimed_hit_rate + trades); payoff_ratio = guadagno medio / perdita media;
    edge_per_trade e cost_per_trade come frazioni del controvalore."""
    out: dict = {"giudizio": []}
    say = out["giudizio"].append

    if sharpe_annual is not None and n_obs:
        sr = sharpe_annual / math.sqrt(periods)
        m = QS.Moments(sr=sr, n=int(n_obs), skew=skew, kurt=kurt)
        v = var_trials if var_trials is not None else _null_var(int(n_obs), skew, kurt)
        sr0 = QS.expected_max_sr(int(n_trials), v)
        if var_trials is None and sr > 0:
            # tentativi indipendenti senza abilita': la soglia della fortuna scende come 1/sqrt(n) mentre la storia
            # si allunga. DSR >= 1-alpha  <=>  SR*sqrt(n-1)/sqrt(V) >= z + E[max N(0,1) su N]
            # => n* = 1 + V * ((z + E[max]) / SR)^2   (MinTRL "deflazionata")
            e_max = QS.expected_max_sr(int(n_trials), 1.0)
            mtrl = 1.0 + QS._var_term(m) * ((norm.ppf(0.95) + e_max) / sr) ** 2
        else:
            mtrl = QS.min_trl(m, sr0)                     # soglia fissa data dalla dispersione dichiarata
        need = trials_to_explain(sr, int(n_obs), skew, kurt, var_trials)
        out["sharpe"] = dict(
            sharpe_annuo=sharpe_annual, osservazioni=int(n_obs), anni=round(n_obs / periods, 2),
            psr=QS.psr(m, 0.0), tentativi_dichiarati=int(n_trials),
            sharpe_fortuna_annuo=sr0 * math.sqrt(periods), dsr=QS.psr(m, sr0),
            min_trl_osservazioni=mtrl, min_trl_anni=mtrl / periods if math.isfinite(mtrl) else math.inf,
            tentativi_per_spiegarlo_col_caso=need)
        s = out["sharpe"]
        if s["dsr"] >= 0.95:
            say(f"Sharpe {sharpe_annual:.2f} su {s['anni']} anni: regge anche contando {n_trials} tentativi "
                f"(DSR {s['dsr']:.2f}). Basterebbero circa {need:,.0f} varianti provate e non dichiarate per spiegarlo col caso.")
        else:
            more = (f"a questo Sharpe servirebbero {s['min_trl_anni']:.1f} anni di storia"
                    if math.isfinite(s["min_trl_anni"]) else "nessuna storia basta: e' sotto la soglia della fortuna")
            say(f"Sharpe {sharpe_annual:.2f} su {s['anni']} anni: NON basta a escludere la fortuna "
                f"(DSR {s['dsr']:.2f} con {n_trials} tentativi; {more}). "
                f"Bastano circa {need:,.0f} varianti provate per ottenerlo per caso.")
        if sharpe_annual > 3:
            say("Uno Sharpe annuo sopra 3 e' rarissimo dopo i costi su strategie con capacita' reale: "
                "di solito segnala costi omessi, look-ahead, sopravvivenza o un periodo molto corto.")

    if trades:
        if wins is None and claimed_hit_rate is not None:
            # alla precisione dichiarata (percentuale intera): esiste un k/n che si arrotonda a quel numero?
            target = round(claimed_hit_rate * 100)
            ok = [k for k in range(int(trades) + 1) if round(100 * k / trades) == target]
            wins = ok[0] if ok else round(claimed_hit_rate * trades)
            out["coerenza"] = dict(dichiarata=claimed_hit_rate, coerente=bool(ok),
                                   vicine=[f"{k}/{trades} = {k / trades:.0%}" for k in
                                           sorted({max(0, math.floor(claimed_hit_rate * trades)),
                                                   min(int(trades), math.ceil(claimed_hit_rate * trades))})])
            if not ok:
                say(f"Incoerenza: con {trades} trade il {target}% non e' ottenibile "
                    f"(le piu' vicine sono {', '.join(out['coerenza']['vicine'])}). I numeri non vengono da un registro.")
        if wins is not None:
            lo, hi = wilson(int(wins), int(trades))
            p = float(binom.sf(int(wins) - 1, int(trades), 0.5))
            out["vincite"] = dict(vinti=int(wins), trade=int(trades), percentuale=wins / trades,
                                  intervallo_90=(lo, hi), p_value_contro_50=p)
            say(f"Vincite {wins}/{trades} = {wins / trades:.0%}: intervallo al 90% {lo:.0%}-{hi:.0%}; "
                f"probabilita' di farlo a caso con una moneta {p:.1%}.")
            if payoff_ratio:
                be = 1 / (1 + payoff_ratio)
                out["vincite"]["pareggio"] = be
                verdict = "sopra" if lo > be else "non chiaramente sopra"
                say(f"Con guadagno medio / perdita media = {payoff_ratio:.2f} il pareggio e' {be:.0%}: "
                    f"l'intervallo e' {verdict} la soglia.")
            else:
                say("Senza il rapporto guadagno medio / perdita media la percentuale di vincite non dice nulla: "
                    "comprare a 0,80 un contratto che paga 1 richiede l'80% di vincite solo per pareggiare.")

    if edge_per_trade is not None and cost_per_trade is not None:
        net = edge_per_trade - cost_per_trade
        out["costi"] = dict(margine_lordo=edge_per_trade, costo=cost_per_trade, margine_netto=net)
        say(f"Margine per trade {edge_per_trade:.2%} meno costi {cost_per_trade:.2%} = {net:.2%}: "
            + ("sopravvive ai costi." if net > 0 else "i costi lo annullano."))

    if not out["giudizio"]:
        say("Niente da valutare: servono almeno Sharpe + osservazioni, oppure vincite + trade.")
    return out


def normal_sharpe_from_tstat(t: float, n_obs: int, periods: int = 252) -> float:
    """Utility: Sharpe annuo implicito in una t-statistic dichiarata (t = SR_periodo * sqrt(n))."""
    return t / math.sqrt(n_obs) * math.sqrt(periods)

