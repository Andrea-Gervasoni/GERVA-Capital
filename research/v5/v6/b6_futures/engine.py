"""B6 - motore: segnali -> pesi scalati per volatilita' -> portafoglio a volatilita' obiettivo, con costi e ritardo."""
import numpy as np, pandas as pd, warnings
warnings.filterwarnings("ignore")
from lib import *

START = "2001-01-02"   # prima i mercati disponibili sono troppo pochi

class Book:
    def __init__(self, end=None, only_micro=False):
        self.P, R, C = load_panel()
        if only_micro:
            keep = [k for k, v in UNI.items() if v[0] not in ("SOFT", "MEAT")]
            R = R[keep]; C = C[keep]
        if end is not None: R = R.loc[:end]; C = C.loc[:end]
        self.R, self.C = R, C
        self.spec = specs(self.P).loc[R.columns]
        self.cost = (self.spec.costo_bp.astype(float) / 1e4)
        self.rolls = self.spec.roll_anno.astype(float)
        self.sec = self.spec.settore
        v = R.ewm(span=60, min_periods=40).std() * np.sqrt(252)
        floor = v.expanding(min_periods=40).median() * 0.5
        self.vol = np.maximum(v, floor)
        self.active = self.vol.notna()
        # peso di rischio: uguale per settore attivo, uguale per mercato dentro il settore
        rw = pd.DataFrame(0.0, index=R.index, columns=R.columns)
        nsec = pd.DataFrame({s: self.active.loc[:, self.sec[self.sec == s].index].sum(axis=1) for s in SECTORS})
        nact = (nsec > 0).sum(axis=1)
        for k in R.columns:
            rw[k] = (self.active[k] / nsec[self.sec[k]].replace(0, np.nan) / nact).fillna(0.0)
        self.rw = rw

    # ---------- segnali (tutti usano solo dati fino alla chiusura t) ----------
    def sig_tsmom(self, k):
        lr = np.log1p(self.R.fillna(0)).cumsum()
        s = np.sign(lr - lr.shift(k)); return s.where(self.active & self.R.shift(k).notna())
    def sig_ewmac(self, f):
        P = np.log1p(self.R.fillna(0)).cumsum()
        sd = self.R.ewm(span=36, min_periods=20).std()
        x = (P.ewm(span=f).mean() - P.ewm(span=4 * f).mean()) / sd
        sc = {2: 10.6, 4: 7.5, 8: 5.3, 16: 3.75, 32: 2.65, 64: 1.87}[f] / 10.0
        return (x * sc).clip(-2, 2).where(self.active & self.R.shift(2 * f).notna())
    def sig_donchian(self, n):
        P = np.log1p(self.R.fillna(0)).cumsum()
        hi = P.shift(1).rolling(n).max(); lo = P.shift(1).rolling(n).min()
        s = pd.DataFrame(np.nan, index=P.index, columns=P.columns)
        s[P >= hi] = 1.0; s[P <= lo] = -1.0
        return s.ffill().where(self.active & self.R.shift(n).notna())

    # ---------- portafoglio ----------
    def weights(self, sig, mask=None, rw=None):
        """peso (nozionale/capitale) per un obiettivo unitario: segnale * peso di rischio * 10% / vol del mercato"""
        rw = self.rw if rw is None else rw
        w = sig * rw * (0.10 / self.vol)
        if mask is not None: w = w[mask].reindex(columns=self.R.columns)
        return w.fillna(0.0)

    def run(self, W, target=0.10, lag=2, cmult=1.0, voltarget=True, buffer=0.0, kcap=None):
        """W: pesi decisi alla chiusura t; eseguiti alla chiusura t+lag-1; guadagnano dal giorno t+lag.
        scala a volatilita' obiettivo con la vol realizzata EWMA del portafoglio unitario (nota a t)."""
        R = self.R.fillna(0.0)
        unit = (W.shift(lag) * R).sum(axis=1)
        if voltarget:
            pv = unit.ewm(span=60, min_periods=40).std() * np.sqrt(252)
            pv = np.maximum(pv, pv.expanding(min_periods=40).median() * 0.5)
            k = (target / pv).where(pv > 1e-4)
            if kcap: k = np.minimum(k, kcap)
            k = k.fillna(0.0)
        else:
            k = pd.Series(target / 0.10, index=W.index)
        Wf = W.mul(k, axis=0)
        if buffer > 0:   # zona di non intervento: si scambia solo se lo scostamento supera buffer * |peso obiettivo medio|
            A = Wf.values; H = np.zeros_like(A); avg = Wf.abs().ewm(span=250, min_periods=1).mean().values
            for t in range(1, len(A)):
                d = A[t] - H[t - 1]; tr = np.abs(d) > buffer * avg[t]
                H[t] = np.where(tr, A[t], H[t - 1])
            Wf = pd.DataFrame(H, index=Wf.index, columns=Wf.columns)
        gross = (Wf.shift(lag) * R).sum(axis=1)
        trade = (Wf - Wf.shift(1)).abs().fillna(0.0)
        cost_tr = (trade * self.cost).sum(axis=1).shift(lag).fillna(0.0)
        cost_roll = (Wf.abs() * (2 * self.cost * self.rolls / 252.0)).sum(axis=1).shift(lag).fillna(0.0)
        net = gross - cmult * (cost_tr + cost_roll)
        start = max(Wf.abs().sum(axis=1).gt(0).idxmax(), pd.Timestamp(START))
        info = dict(turnover_anno=trade.sum(axis=1).loc[start:].mean() * 252, leva_lorda=Wf.abs().sum(axis=1).loc[start:].mean(),
                    costo_anno=(cost_tr + cost_roll).loc[start:].mean() * 252 * cmult)
        return net.loc[start:], gross.loc[start:], Wf, info

def line(name, net, gross=None, info=None):
    d = {"strategia": name}
    for k, (a, b) in PERIODS.items():
        s = stats(net.loc[a:b]); d[f"S_{k}"] = s.get("sharpe", np.nan)
    s = stats(net); d.update(cagr=s["cagr"] * 100, vol=s["vol"] * 100, mdd=s["mdd"] * 100, skew_m=s["skew_m"])
    if gross is not None: d["S_lordo"] = stats(gross)["sharpe"]
    if info: d.update(turn=info["turnover_anno"], leva=info["leva_lorda"], costo=info["costo_anno"] * 100)
    return d
