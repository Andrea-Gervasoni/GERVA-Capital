"""Regressioni dei tre rilievi dell'audit del 10/11 su quantlab/ rimasti aperti (docs/archivio_RIFONDAZIONE_v2.md, righe 9-12 della
tabella dei rilievi). Ogni test fallisce sul codice di prima e passa su quello corretto.

  1. Sharpe sui rendimenti grezzi: il tasso a breve incassato dalla liquidita' contava come abilita'.
  2. Ritardo di esecuzione: senza prezzi di apertura il motore esegue sulla stessa chiusura del segnale; il docstring diceva t+1.
  3. Test anti look-ahead aggirabile: un segnale che guarda domani solo a fine mese passava con 3-5 tagli; in firm/strategies
     l'esito era scritto a mano (lookahead_ok=True).
  + la regola di adozione a 40 giorni del portafoglio ombra, che approvava un terzo delle volte senza alcun vantaggio."""
import math

import numpy as np
import pandas as pd
import pytest

from quantlab import backtest as BT, crypto4 as C4, gervaq4 as G4, lookahead as LA, stats as QS, strategies as QST

from test_gervaq4 import synth


def _with_rate(d: dict, pct: float) -> dict:
    close = d["close"].copy()
    close["^IRX"] = pct
    return dict(d, close=close)


# =============================================================================================== 1. Sharpe in eccesso del tasso
def test_a_tbill_only_series_has_no_sharpe_once_the_rate_is_subtracted():
    """Una serie di soli T-bill (4% l'anno, rumore minuscolo): grezza ha PSR e DSR pari a 1; in eccesso del tasso non ha nulla."""
    rng = np.random.default_rng(0)
    rate = np.full(1500, 0.04 / 252)
    r = rate + rng.normal(0, 1e-5, 1500)
    raw = QS.moments(r)
    assert QS.psr(raw) > 0.999 and QS.dsr(raw, 100, 0.001 ** 2) > 0.999          # il difetto: il tasso sembra abilita'
    for rf in (rate, 0.04 / 252):                                                # serie giornaliera oppure scalare per periodo
        m = QS.moments(r, rf=rf)
        assert abs(m.sr) < 0.1 and 0.01 < QS.psr(m) < 0.99
        assert QS.dsr(m, 100, 0.001 ** 2) < 0.5
        p = QS.performance(r, rf=rf)
        assert abs(p["Sharpe"]) < 1.5 and p["CAGR"] == pytest.approx(0.04, abs=0.002)     # il conto cresce al 4%, ma non e' premio
        assert p["Tasso"] == pytest.approx(0.04)
    lo, hi = QS.sharpe_ci_bootstrap(r, n_boot=200, rf=rate)
    assert lo < 0 < hi


def test_rf_is_optional_and_none_keeps_the_old_numbers():
    r = np.random.default_rng(1).normal(0.0004, 0.01, 800)
    assert QS.moments(r) == QS.moments(r, rf=None) == QS.moments(r, rf=0.0)
    a, b = QS.performance(r), QS.performance(r, rf=None)
    assert all(a[k] == b[k] for k in a) and a["Tasso"] == 0.0
    assert QS.performance(r, rf=0.0002)["Sharpe"] < a["Sharpe"]                  # sottrarre un tasso positivo abbassa lo Sharpe
    with pytest.raises(ValueError):
        QS.moments(r, rf=np.zeros(10))                                           # una serie non allineata e' un errore, non un taglio silenzioso


def test_trial_registry_does_not_give_dsr_one_to_tbills(firm_env):
    """Il registro delle prove (da cui esce il DSR dei cancelli) accetta il tasso: con rf una serie di T-bill non passa."""
    from firm import trials
    rate = np.full(1500, 0.04 / 252)
    r = rate + np.random.default_rng(0).normal(0, 1e-5, 1500)
    t1 = trials.register("head_research", "audit:tbill:grezzo", "audit", dict(a=1), "solo T-bill, rendimenti grezzi")
    assert trials.record_result(t1, r)["dsr"] > 0.999                            # senza tasso: il difetto dell'audit
    t2 = trials.register("head_research", "audit:tbill:eccesso", "audit", dict(a=2), "solo T-bill, in eccesso del tasso")
    d = trials.record_result(t2, r, rf=rate)
    assert d["dsr"] < 0.95 and abs(d["sharpe_annuo"]) < 1.5


def test_cash_is_treasury_for_every_variant_reference_included():
    """'Cassa' non e' piu' una variante: nessuna variante ha il campo, e riferimento e candidate ricevono lo stesso accredito."""
    for mod in (G4, C4):
        assert "cash" not in [v.name for v in mod.VARIANTS]
        assert all("cash" not in v.params() for v in mod.VARIANTS)
    d = _with_rate(synth(1, years=4), 5.0)
    for v in G4.VARIANTS[:1] + [x for x in G4.VARIANTS if x.name == "tutto"]:
        on, res = G4.run_variant(d, v, return_result=True)
        off = G4.run_variant(dict(d, tesoreria=False), v)
        idle = (1 - res.daily["gross"]).clip(lower=0)
        assert np.allclose((on - off).values, (idle * (0.05 - 0.001) / 252).values)      # tasso meno 0,10% sulla quota ferma, a tutti
        assert (on - off).mean() > 0


def test_holding_more_remunerated_cash_is_not_an_improvement():
    """Il caso piu' semplice del difetto: una 'variante' che e' la v3 con META' esposizione e il resto in liquidita' remunerata.
    Non contiene alcuna idea. Sui rendimenti grezzi, con il tasso al 5%, aveva uno Sharpe molto piu' alto (stesso premio dimezzato,
    volatilita' dimezzata, piu' tasso incassato); in eccesso del tasso vale quanto la v3, meno lo 0,10% dell'ETF monetario."""
    d = _with_rate(synth(3, years=6), 5.0)
    ref, half = G4.Variant("v3_riferimento"), G4.Variant("meta_esposizione")
    runner = lambda data, v, lag=0: G4.run_variant(data, ref, scale=0.5 if v.name == "meta_esposizione" else 1.0, lag=lag)
    res = G4.bench(d, variants=[ref, half], runner=runner)
    assert res.tasso_medio == pytest.approx(0.05)
    assert res.scelta == "v3_riferimento" and res.confronti["meta_esposizione"] < 0.90
    assert abs(res.tabella.loc["meta_esposizione", "Sharpe"] - res.tabella.loc["v3_riferimento", "Sharpe"]) < 0.25
    # la stessa coppia giudicata come prima (rendimenti grezzi): la mezza esposizione "batte" la v3 quasi con certezza
    r_ref, r_half = (runner(d, v).iloc[300:] for v in (ref, half))
    assert G4.paired_sharpe_prob(r_half.values, r_ref.values) > 0.95
    assert QS.performance(r_half.values)["Sharpe"] > QS.performance(r_ref.values)["Sharpe"] + 0.5


def test_bench_on_pure_noise_with_a_high_rate_keeps_the_reference():
    """Mercati di puro rumore, tasso al 5%: prima il banco promuoveva la variante con la cassa 9-12 volte su 12."""
    variants = [v for v in G4.VARIANTS if v.name in ("v3_riferimento", "cash", "band5", "tutto")]
    promosse = [G4.bench(_with_rate(synth(seed, years=6), 5.0), variants=variants).scelta for seed in range(4)]
    assert promosse.count("v3_riferimento") >= 3, promosse


def test_crypto_bench_uses_excess_returns_and_common_treasury():
    from test_crypto_longterm import synth_crypto
    close = synth_crypto(2, days=1300)
    variants = [v for v in C4.VARIANTS if v.name in ("v3_crypto", "slow", "tutto")]
    lo = C4.bench(dict(close=close.assign(**{"^IRX": 0.1})), variants=variants, start_skip=200, with_lag=False)
    hi = C4.bench(dict(close=close.assign(**{"^IRX": 8.0})), variants=variants, start_skip=200, with_lag=False)
    assert lo.tasso_medio == pytest.approx(0.001) and hi.tasso_medio == pytest.approx(0.08)
    for res in (lo, hi):
        assert "cash" not in res.tabella.index and "v3_crypto" in res.tabella.index
    # a prezzi uguali un tasso piu' alto ABBASSA lo Sharpe di tutte (il premio delle monete e' minore), riferimento compreso:
    # sui rendimenti grezzi lo alzava, e di piu' a chi teneva piu' liquidita'
    assert (hi.tabella["Sharpe"] < lo.tabella["Sharpe"]).all()


# =============================================================================================== 2. ritardo di esecuzione
def _jump_market():
    idx = pd.bdate_range("2024-01-01", periods=12)
    px = np.full(12, 100.0)
    px[6:] = 110.0                                           # +10% tra la chiusura della riga 5 e quella della riga 6
    close = pd.DataFrame({"A": px}, index=idx)
    W = pd.DataFrame({"A": 0.0}, index=idx)
    W.iloc[5] = 1.0                                          # segnale alla chiusura della riga 5: "compra", poi di nuovo zero
    return close, W


def test_default_executes_on_the_signal_close_and_lag_one_does_not():
    """Senza open, lag=0 (default) compra alla chiusura che genera il segnale e incassa il salto del giorno dopo;
    con lag=1 l'ordine parte alla chiusura successiva, a salto gia' avvenuto."""
    close, W = _jump_market()
    same_close = BT.run(W, close, cost_rate=0.0)
    assert same_close.returns.iloc[6] == pytest.approx(0.10)                    # comportamento attuale, ora dichiarato nel docstring
    assert BT.run(W, close, cost_rate=0.0, lag=0).returns.equals(same_close.returns)
    late = BT.run(W, close, cost_rate=0.0, lag=1)
    assert late.returns.abs().max() == pytest.approx(0.0)                       # un giorno dopo il salto non c'e' piu'
    assert late.daily["gross"].iloc[7] == pytest.approx(1.0) and late.daily["gross"].iloc[6] == 0.0
    assert "STESSA chiusura" in BT.__doc__ and "lag" in BT.run.__doc__


def test_lag_is_a_pure_delay_of_the_decision():
    _, close = QST.synthetic_market(n_days=500, n_assets=4, seed=5)
    opn = close.shift(1).bfill() * 1.001
    W = QST.tsmom(close, lookback=60)
    mask = pd.Series(np.arange(len(close)) % 5 == 0, index=close.index)
    for kw in (dict(), dict(open_=opn), dict(rebalance_mask=mask)):
        a = BT.run(W, close, band=0.02, lag=2, **kw)
        kw2 = dict(kw)
        if "rebalance_mask" in kw2:
            kw2["rebalance_mask"] = mask.shift(2, fill_value=False)
        b = BT.run(W.shift(2).fillna(0.0), close, band=0.02, **kw2)
        assert np.allclose(a.returns.values, b.returns.values) and np.allclose(a.weights.values, b.weights.values)
    with pytest.raises(ValueError):
        BT.run(W, close, lag=-1)                                                # un ritardo negativo sarebbe guardare il futuro


def test_same_close_execution_flatters_a_one_day_signal():
    """Un segnale che vale un giorno solo (inversione a 1 giorno su un mercato che la contiene): tutto il guadagno sta
    nell'eseguire sulla chiusura del segnale. Con un giorno di ritardo sparisce: per questo i banchi stampano entrambi."""
    rng = np.random.default_rng(3)
    e = rng.normal(0, 0.01, (1500, 6))
    r = e - 0.3 * np.vstack([np.zeros((1, 6)), e[:-1]])                         # autocorrelazione negativa a un giorno
    close = pd.DataFrame(100 * np.cumprod(1 + r, axis=0), index=pd.bdate_range("2015-01-01", periods=1500),
                         columns=[f"A{i}" for i in range(6)])
    W = (close.pct_change() < 0).astype(float) / 6                              # compra chi oggi e' sceso
    sharpe = lambda x: x.mean() / x.std() * math.sqrt(252)
    assert sharpe(BT.run(W, close, cost_rate=0.0).returns) > 2.0
    assert abs(sharpe(BT.run(W, close, cost_rate=0.0, lag=1).returns)) < 1.0


def test_benches_report_the_one_day_lag_result():
    res = G4.bench(synth(3, years=5), variants=[v for v in G4.VARIANTS if v.name in ("v3_riferimento", "band5")])
    assert res.ritardo is not None and set(res.ritardo.index) == {"v3_riferimento", "band5"}
    assert {"Sharpe", "CAGR", "P_v3"} <= set(res.ritardo.columns)
    md = res.to_markdown()
    assert "un giorno di ritardo" in md and "in eccesso del tasso a breve" in md
    d = synth(3, years=5)
    v = G4.VARIANTS[0]
    assert not np.allclose(G4.run_variant(d, v).values, G4.run_variant(d, v, lag=1).values)
    from test_crypto_longterm import synth_crypto
    cres = C4.bench(dict(close=synth_crypto(2, days=1100)), variants=C4.VARIANTS[:2], start_skip=200)
    assert cres.ritardo is not None and "un giorno di ritardo" in cres.to_markdown()
    # un motore esterno che non conosce `lag` continua a funzionare: semplicemente non ha la tabella del ritardo
    plain = G4.bench(d, variants=G4.VARIANTS[:2], runner=lambda data, v: G4.run_variant(data, v))
    assert plain.ritardo is None


# =============================================================================================== 3. test anti look-ahead
_, CLOSE = QST.synthetic_market(n_days=900, n_assets=5, seed=11, trend_strength=0.01)


def _month_end(index) -> np.ndarray:
    return np.append(index.month[1:] != index.month[:-1], False)


def leaky_at_month_end(c: pd.DataFrame) -> pd.DataFrame:
    """Momentum onesto ogni giorno, tranne l'ultima riga di ogni mese: li' usa la chiusura di DOMANI."""
    honest = (c > c.shift(20)).astype(float)
    cheat = (c.shift(-1) > c).astype(float)
    return honest.where(~pd.Series(_month_end(c.index), index=c.index), cheat)


def test_a_leak_only_on_month_end_rows_is_caught():
    """Con 3-5 tagli equispaziati questo segnale passava: nessun taglio cadeva su una riga di fine mese."""
    for k in (3, 4, 5):
        res = LA.truncation_test(leaky_at_month_end, CLOSE, cut_points=k)
        assert not res["ok"], f"passa con cut_points={k}"
        assert res["tagli"] >= 60 and res["violazioni"]
    honest = LA.truncation_test(lambda c: (c > c.shift(20)).astype(float), CLOSE, cut_points=3)
    assert honest["ok"] and honest["tagli"] >= 60 + 2 * 20                      # 60 a caso piu' tutte le righe di fine e inizio mese


def test_cuts_cover_every_rebalance_row_and_are_reproducible():
    seen = []

    def spy(c):
        seen.append(len(c) - 1)
        return (c > c.shift(5)).astype(float)
    idx = CLOSE.index
    mask = pd.Series(np.arange(len(idx)) % 7 == 0, index=idx)                    # ribilanciamento ogni 7 righe, dichiarato da chi chiama
    r1 = LA.truncation_test(spy, CLOSE, cut_points=3, min_history=300, rebalance_mask=mask)
    first = sorted(set(seen[1:]))
    wanted = {i for i in range(300, len(idx) - 1) if mask.iloc[i] or _month_end(idx)[i]}
    assert wanted <= set(first)                                                  # ogni riga di ribilanciamento e ogni fine mese
    seen.clear()
    r2 = LA.truncation_test(spy, CLOSE, cut_points=3, min_history=300, rebalance_mask=mask)
    assert sorted(set(seen[1:])) == first and r1["tagli"] == r2["tagli"]         # seme fisso: stessi tagli a ogni esecuzione
    seen.clear()
    LA.truncation_test(spy, CLOSE, cut_points=3, min_history=300, rebalance_mask=mask, seed=8)
    assert sorted(set(seen[1:])) != first                                        # il campione casuale c'e' davvero


def test_extra_inputs_are_truncated_with_the_prices():
    """Tutti gli ingressi passano dal taglio: una serie di mercato data in `extra` che contiene il futuro viene scoperta,
    mentre la stessa serie catturata dalla funzione no (per questo va passata in `extra`)."""
    mkt = CLOSE.mean(axis=1)
    tomorrow = mkt.shift(-1)                                                     # "dato esterno" che in realta' e' il mercato di domani
    fn = lambda c, mercato: c.gt(c.shift(5)).astype(float).mul((mercato > mercato.shift(1)).astype(float), axis=0)
    assert LA.truncation_test(fn, CLOSE, extra=dict(mercato=mkt))["ok"]
    captured = lambda c: fn(c, tomorrow.reindex(c.index))                        # il vecchio modo: il test non puo' vederlo
    assert LA.truncation_test(captured, CLOSE)["ok"]
    assert not LA.truncation_test(lambda c, mercato: fn(c, mercato.shift(-1)), CLOSE, extra=dict(mercato=mkt))["ok"]


def test_series_output_and_no_cuts_is_not_a_pass():
    res = LA.truncation_test(lambda c: c.mean(axis=1).pct_change(), CLOSE)       # un segnale puo' restituire una Serie
    assert res["ok"]
    assert not LA.truncation_test(lambda c: c.mean(axis=1).pct_change().shift(-1), CLOSE)["ok"]
    never = pd.Series(False, index=CLOSE.index)
    assert not LA.truncation_test(lambda c: c, CLOSE, allowed_mask=never)["ok"]  # nessun taglio eseguito = test non superato


def test_strategy_backtest_really_runs_the_lookahead_test(firm_env, monkeypatch):
    """firm/strategies.backtest passava lookahead_ok=True scritto a mano: un backtest che guarda il futuro superava il controllo."""
    from firm import org_seed, registry, strategies as ST
    from test_strategies import _crypto, _spy
    org_seed.seed(); registry.sync()
    c = _crypto(n=24 * 120)
    monkeypatch.setitem(ST.STRATS["crypto_tsmom"]["params"], "coins", list(c))
    ok = ST.backtest("crypto_tsmom", data=c, propose=False)
    assert ok["look_ahead"]["ok"] and ok["look_ahead"]["tagli"] >= 60
    assert ok["cancello"]["controlli"]["look_ahead"]["ok"] is True
    honest = ST.tsmom_weights

    def leaky(close, p):                                                         # pesi onesti, ma a fine mese decisi con l'ora successiva
        w = honest(close, p)
        last = pd.Series(np.append(close.index.month[1:] != close.index.month[:-1], False), index=close.index)
        return w.where(~last, w.shift(-1))
    monkeypatch.setattr(ST, "tsmom_weights", leaky)
    bad = ST.backtest("crypto_tsmom", data=c, propose=False)
    assert bad["look_ahead"]["ok"] is False and bad["look_ahead"]["violazioni"]
    assert bad["cancello"]["controlli"]["look_ahead"]["ok"] is False and bad["cancello"]["passa"] is False
    monkeypatch.setattr(ST, "tsmom_weights", honest)
    spy = ST.backtest("spy_intraday_momentum", data=_spy(days=60), propose=False)
    assert spy["look_ahead"]["ok"] and spy["look_ahead"]["tagli"] >= 30          # si taglia solo a giornata finita: al piu' una riga per giorno


def test_band_loop_rewrite_gives_the_same_backtest():
    """Il ciclo della banda in bt_crypto_tsmom e' stato riscritto senza iterrows (il test di troncamento lo ricalcola ~100 volte)."""
    from firm import strategies as ST
    from test_strategies import _crypto
    c = _crypto(n=24 * 60)
    p = ST.STRATS["crypto_tsmom"]["params"] | dict(coins=list(c))
    w = ST.tsmom_weights(c, p)
    prev, rows = pd.Series(0.0, index=w.columns), []
    for _, row in w.iterrows():                                                  # la versione di prima, copiata qui come riferimento
        new = row.where((row - prev).abs() > p["band"], prev)
        rows.append(new); prev = new
    held = pd.DataFrame(rows, index=w.index)
    r = c.pct_change(fill_method=None).fillna(0.0)
    old = (held.shift(1).fillna(0.0) * r).sum(axis=1) - held.diff().abs().sum(axis=1).fillna(0.0) * p["cost_bps"] / 1e4
    assert np.allclose(ST.bt_crypto_tsmom(c, p).values, old.values, atol=1e-15)


# =============================================================================================== regola di adozione a 40 giorni
def _old_rule(v4, v3) -> bool:
    """La regola del 5/11, copiata com'era: P(Sharpe v4 > v3) >= 0,80 e drawdown della v4 non peggiore."""
    dd = lambda x: float((np.cumprod(1 + x) / np.maximum.accumulate(np.cumprod(1 + x)) - 1).min())
    return G4.paired_sharpe_prob(v4, v3) >= 0.80 and dd(v4) >= dd(v3)


def _null_pair(seed: int, days: int = 40):
    """Due serie SENZA alcun vantaggio (rendimento atteso zero per entrambe), la 'v4' con meta' della volatilita' come quella vera."""
    rng = np.random.default_rng(seed)
    common = rng.normal(0, 0.005, days)
    return 0.5 * common + rng.normal(0, 0.0015, days), common + rng.normal(0, 0.003, days)       # (v4, v3)


def test_forty_day_rule_approved_without_any_edge_and_is_now_suspended():
    from firm import shadow
    pairs = [_null_pair(s) for s in range(120)]
    old = np.mean([_old_rule(a, b) for a, b in pairs])
    assert old > 0.15, old                                    # il difetto: approva spesso anche se non c'e' nulla da approvare
    new = [shadow.decide(a, b) for a, b in pairs]
    assert not any(d["adozione_proposta"] for d in new)       # ora: mai
    assert all("SOSPESA" in d["verdetto"] for d in new) and shadow.ADOZIONE_SOSPESA
    assert shadow.decide(*_null_pair(0, days=25))["verdetto"].startswith("in osservazione")


def test_shadow_summary_never_proposes_adoption(firm_env):
    """Un caso in cui la regola di prima proponeva l'adozione: la sintesi del portafoglio ombra non la propone piu'."""
    from firm import db, shadow
    seed = next(s for s in range(200) if _old_rule(*_null_pair(s, days=45)))
    v4, v3 = _null_pair(seed, days=45)
    days = pd.bdate_range("2026-11-06", periods=45)
    for d, a, b in zip(days, v4, v3):
        for name, x in (("tutto", a), ("v3_riferimento", b)):
            db.ex("INSERT INTO shadow_returns(day,variant,ret,recorded_ts,data_fp) VALUES(?,?,?,?,?)",
                  (str(d.date()), name, float(x), db.now_iso(), "prova"))
    s = shadow.summary()
    assert s["giorni"] == 45 and s["p_v4_meglio"] >= 0.80     # i numeri restano, come informazione
    assert "proporre l'adozione" not in s["verdetto"] and "SOSPESA" in s["verdetto"]
    assert s["adozione_proposta"] is False and s["regola_sospesa"] is True
    assert "prima della correzione" in s["nota"]              # righe scritte dal codice di prima: v4 con la cassa, v3 senza


def test_shadow_records_both_variants_with_the_same_treasury(firm_env):
    from firm import db, shadow
    d = _with_rate(synth(4, years=4), 5.0)
    close = d["close"]
    r = shadow.update(close, start=str(close.index[-31].date()))
    assert r["nuovi"] == 60 and "nota" not in r               # database nuovo: tesoreria uguale dall'inizio
    rf = db.runtime_get(shadow.RF_KEY)
    assert len(rf) == 30 and all(v == pytest.approx(0.05 / 252) for v in rf.values())
    rows = {x["day"]: x["ret"] for x in db.q("SELECT day, ret FROM shadow_returns WHERE variant='v3_riferimento'")}
    ref = G4.run_variant(dict(shadow._data(close), tesoreria=False), G4.VARIANTS[0])
    extra = np.mean([rows[str(t.date())] - ref[t] for t in close.index[-30:]])
    assert extra > 0                                          # anche il riferimento incassa il tasso sulla quota ferma
