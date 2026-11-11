"""01 - Validazione delle serie sintetiche k x contro prodotti reali (Yahoo). SIMULATO vs FATTO."""
from lab import *
U = underlying()
def real(sym, clean=0.45):
    d = y(sym); r = d["adj"].pct_change()
    bad = r.abs() > clean
    return r.where(~bad), int(bad.sum())
print("=== A. Prodotti USA (stessa chiusura del sottostante): differenza di CAGR sintetico - reale, tracking giornaliero")
print(f"{'prodotto':8s} {'k':>2s} {'dal':>10s} {'CAGR reale':>10s} {'sint(spread 0)':>14s} {'spread che pareggia':>20s} {'corr g.':>8s} {'TE annuo':>8s}")
for sym, und, k, ter in [("SSO","SPX",2,0.0089),("QLD","NDX",2,0.0095),("UPRO","SPX",3,0.0091),("SPXL","SPX",3,0.0091),("TQQQ","NDX",3,0.0084),("TMF","BOND",3,0.0106),("RYOCX","NDX",1,0.0130)]:
    rr, nb = real(sym); rr = rr.dropna()
    ix = rr.index.intersection(U.index)[1:]
    def cg(sp):
        s = lev(U[und], U["cash"], U["dc"], k, ter, sp).reindex(ix)
        return (1 + s).prod() ** (252 / len(ix)) - 1, s
    c_real = (1 + rr.reindex(ix)).prod() ** (252 / len(ix)) - 1
    c0, s0 = cg(0.0)
    # spread che pareggia (bisezione)
    lo, hi = -0.03, 0.06
    for _ in range(40):
        mid = (lo + hi) / 2
        if cg(mid)[0] > c_real: lo = mid
        else: hi = mid
    sp = (lo + hi) / 2
    te = (s0 - rr.reindex(ix)).std() * np.sqrt(252)
    print(f"{sym:8s} {k:2d} {str(ix[0].date()):>10s} {c_real*100:9.2f}% {c0*100:13.2f}% {sp*100:19.2f}% {s0.corr(rr.reindex(ix)):8.4f} {te*100:7.2f}%")

print("\n=== B. Prodotti UCITS (linee USD/EUR; chiusura europea != chiusura USA -> confronto su rendimenti MENSILI e CAGR)")
fx = y("EURUSD=X")["close"]; gb = y("GBPUSD=X")["close"]
print(f"{'prodotto':9s} {'val':>4s} {'k':>2s} {'dal':>10s} {'CAGR reale$':>11s} {'sint(TER,sp0)':>13s} {'spread pareggio':>15s} {'corr mens.':>10s} {'salti tolti':>10s}")
for sym, und, k, ter, cur in [("QQQ3.L","NDX",3,0.0075,"USD"),("QQQ3.MI","NDX",3,0.0075,"EUR"),("3USL.L","SPX",3,0.0075,"USD"),("3USL.MI","SPX",3,0.0075,"EUR"),
                              ("LQQ.PA","NDX",2,0.0060,"EUR"),("CL2.PA","SPX",2,0.0050,"EUR"),("DBPG.DE","SPX",2,0.0060,"EUR"),("5QQQ.L","NDX",5,0.0075,"USD"),("5SPY.L","SPX",5,0.0075,"USD"),
                              ("3DEL.MI","DAX",3,0.0075,"EUR"),("LVE.PA","DAX",2,0.0040,"EUR")]:
    try:
        d = y(sym); p = d["close"].copy()
        if cur == "EUR" and und != "DAX": p = p * fx.reindex(p.index).ffill()
        r = p.pct_change(); bad = r.abs() > 0.45; r = r.where(~bad).dropna()
        ix = r.index.intersection(U.index)[1:]
        if sym.startswith("5"): ix = ix[ix >= "2022-01-03"]
        c_real = (1 + r.reindex(ix)).prod() ** (252 / len(ix)) - 1
        def cg(sp):
            s = lev(U[und], U["cash"], U["dc"], k, ter, sp).reindex(ix)
            return (1 + s).prod() ** (252 / len(ix)) - 1, s
        c0, s0 = cg(0.0)
        lo, hi = -0.10, 0.25
        for _ in range(40):
            mid = (lo + hi) / 2
            if cg(mid)[0] > c_real: lo = mid
            else: hi = mid
        mr = (1 + r.reindex(ix)).groupby([ix.year, ix.month]).prod() - 1
        ms = (1 + s0).groupby([ix.year, ix.month]).prod() - 1
        print(f"{sym:9s} {cur:>4s} {k:2d} {str(ix[0].date()):>10s} {c_real*100:10.2f}% {c0*100:12.2f}% {(lo+hi)/2*100:14.2f}% {mr.corr(ms):10.4f} {int(bad.sum()):10d}")
    except Exception as e:
        print(sym, "ERRORE", str(e)[:100])
print("\nNota: 'spread pareggio' = spread annuo sopra il T-bill, applicato a (k-1) di debito, che rende il CAGR sintetico uguale al reale.")
print("Per le linee EUR del DAX il tasso usato e' quello USA (errore noto: i tassi euro erano piu' bassi -> spread negativo atteso).")
