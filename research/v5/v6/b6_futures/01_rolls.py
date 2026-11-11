"""B6 - calibrazione e verifica del calendario dei roll; costruzione del pannello pulito.
Output: panel (data_cache v5_b6_panel_*.parquet) + diagnostica."""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from lib import *
pd.set_option("display.width", 250)
rows = []; PANEL = {}; GAPS = {}
print("== A. Mercati con calendario dei roll (regola LTD + offset calibrato sul salto notturno mediano) ==")
for sym in RULES:
    if sym in ("ES=F", "NQ=F", "YM=F", "RTY=F") and sym != "ES=F": pass
    d = raw(sym)
    gapall = (d.open / d.close.shift(1) - 1)
    base = gapall.abs().median()
    best = None
    for off in range(-3, 4):
        rd = roll_days(sym, d, off)
        sc = gapall.reindex(rd).abs().median()
        if best is None or sc > best[1]: best = (off, sc)
    off = best[0]
    rd = roll_days_final(sym, d)
    # qualita': nel giorno scelto il salto e' il maggiore della finestra +-3?
    pos = d.index.get_indexer(rd); g = gapall.abs().values; ok = 0; n = 0
    for p in pos:
        if p - 3 < 1 or p + 4 > len(g): continue
        n += 1; ok += int(np.nanargmax(g[p - 3:p + 4]) == 3)
    adj, gaps = adjust(d, rd)
    PANEL[sym] = adj; GAPS[sym] = gaps
    yrs = (d.index[-1] - d.index[0]).days / 365.25
    rows.append(dict(sym=sym, offset=off, roll_anno=len(rd) / yrs, salto_med_abs_bp=gapall.reindex(rd).abs().median() * 1e4, adattivo=sym in ADAPT, notte_normale_bp=base * 1e4,
                     salto_medio_bp=gaps.mean() * 1e4, picco_in_finestra=ok / max(n, 1),
                     carry_annuo_pct=-gaps.mean() * len(rd) / yrs * 100,
                     rend_grezzo_annuo=d.close.pct_change().mean() * 252 * 100, rend_pulito_annuo=adj.ret.mean() * 252 * 100))
print(pd.DataFrame(rows).set_index("sym").round(2).to_string())

print("\n== B. Mercati 'cash and carry' senza date di roll affidabili: grezzo ~ spot, eccesso = grezzo + carry (STIMA) ==")
idx_all = pd.bdate_range("1999-01-01", raw("ES=F").index[-1])
FXR = {"6E=F": "IR3TIB01EZM156N", "6J=F": "IR3TIB01JPM156N", "6B=F": "IR3TIB01GBM156N", "6A=F": "IR3TIB01AUM156N", "6C=F": "IR3TIB01CAM156N", "6S=F": "IR3TIB01CHM156N"}
for sym, fr in FXR.items():
    d = raw(sym); c = daily_rate(fr, d.index) - daily_rate("DTB3", d.index)
    PANEL[sym] = carry_adjust(d, c)
    print(f"{sym}: carry medio annuo {c.mean()*252*100:+.2f}%  grezzo {d.close.pct_change().mean()*252*100:+.2f}%  eccesso {PANEL[sym].ret.mean()*252*100:+.2f}%")
for sym in ["GC=F", "SI=F", "HG=F", "PL=F", "PA=F"]:
    d = raw(sym); c = -daily_rate("DTB3", d.index)
    PANEL[sym] = carry_adjust(d, c)
    print(f"{sym}: carry medio annuo {c.mean()*252*100:+.2f}%  grezzo {d.close.pct_change().mean()*252*100:+.2f}%  eccesso {PANEL[sym].ret.mean()*252*100:+.2f}%")
# azionario USA: ETF total return - T-bill (piu' pulito), barre ETF
for sym, etf in [("ES", "SPY"), ("NQ", "QQQ"), ("YM", "DIA"), ("RTY", "IWM")]:
    d = raw(etf); d = d[d.index >= "2000-06-01"]
    f = d.adj / d.close
    b = pd.DataFrame({"open": d.open * f, "high": d.high * f, "low": d.low * f, "close": d.adj, "volume": d.volume, "raw_close": d.close})
    c = -daily_rate("DTB3", d.index)
    PANEL[sym + "_etf"] = carry_adjust(b.assign(close=b.close), c)
# indici esteri: N225 (prezzo + div 1.7% - tasso JPY), DAX (total return - tasso EUR), STOXX50 (prezzo + div 3.2% - tasso EUR)
for sym, fr, dv in [("^N225", "IR3TIB01JPM156N", 0.017), ("^GDAXI", "IR3TIB01EZM156N", 0.0), ("^STOXX50E", "IR3TIB01EZM156N", 0.032)]:
    d = raw(sym); d = d[d.index >= "2000-01-01"]
    days = pd.Series(d.index, index=d.index).diff().dt.days.fillna(1)
    c = dv * days / 365.0 - daily_rate(fr, d.index)
    PANEL[sym] = carry_adjust(d, c)
    print(f"{sym}: carry medio annuo {c.mean()*252*100:+.2f}%")

print("\n== C. Controllo incrociato: future ripulito contro ETF/spot (rendimento in eccesso annuo %, correlazione giornaliera, periodo comune) ==")
def exc_etf(e):
    d = raw(e); return d.adj.pct_change() - daily_rate("DTB3", d.index)
chk = [("ES=F", "SPY"), ("NQ=F", "QQQ"), ("YM=F", "DIA"), ("RTY=F", "IWM"), ("ZN=F", "IEF"), ("ZB=F", "TLT"), ("ZT=F", "SHY"), ("ZF=F", "IEI"),
       ("GC=F", "GLD"), ("SI=F", "SLV"), ("6E=F", "FXE"), ("6J=F", "FXY"), ("6B=F", "FXB"), ("6A=F", "FXA"), ("6C=F", "FXC"), ("6S=F", "FXF"),
       ("CL=F", "USO"), ("NG=F", "UNG"), ("ZC=F", "CORN"), ("ZW=F", "WEAT"), ("ZS=F", "SOYB"), ("HG=F", "CPER")]
cr = []
for f, e in chk:
    a = PANEL[f].ret; b = exc_etf(e); rw = raw(f).close.pct_change()
    j = pd.concat([a, b, rw], axis=1, keys=["fut", "etf", "raw"]).dropna()
    j = j[j.index >= j.index[0] + pd.Timedelta(days=5)]
    w = j.resample("W").sum()
    cr.append(dict(fut=f, etf=e, dal=j.index[0].date(), fut_pulito=j.fut.mean() * 252 * 100, etf_ecc=j.etf.mean() * 252 * 100, fut_grezzo=j.raw.mean() * 252 * 100,
                   corr_sett=w.fut.corr(w.etf), vol_fut=j.fut.std() * 16 * 100, vol_etf=j.etf.std() * 16 * 100))
print(pd.DataFrame(cr).round(2).to_string())
# BTC
for f, e in [("BTC=F", "BTC-USD"), ("ETH=F", "ETH-USD")]:
    a = PANEL[f].ret; s = raw(e).close.pct_change(); j = pd.concat([a, s.reindex(a.index), raw(f).close.pct_change()], axis=1, keys=["fut", "spot", "raw"]).dropna()
    print(f, "pulito %.1f%%  spot(giorni CME) %.1f%%  grezzo %.1f%%" % (j.fut.mean() * 252 * 100, np.log(raw(e).close.reindex(j.index).iloc[-1]/raw(e).close.reindex(j.index).iloc[0])/len(j)*252*100, j.raw.mean() * 252 * 100))

# valori anomali
print("\n== D. Rendimenti giornalieri anomali rimasti (|r| > 8 sigma EWMA) ==")
for s, p in PANEL.items():
    z = p.ret / p.ret.ewm(span=60, min_periods=30).std().shift(1)
    bad = z[z.abs() > 8]
    if len(bad): print(s, [(str(i.date()), round(p.ret[i] * 100, 1)) for i in bad.index][:12])
for s, p in PANEL.items():
    p.to_parquet(f"{CACHE}/v5_b6_panel_{s}.parquet")
pd.concat(GAPS, axis=0).rename("gap").to_frame().to_parquet(f"{CACHE}/v5_b6_rollgaps.parquet")
print("\nmercati nel pannello:", len(PANEL))
