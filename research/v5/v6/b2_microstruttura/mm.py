import numpy as np, numba as nb
@nb.njit(cache=True)
def mm_sim(bid, ask, thi, tlo, sig, d_bp, R, L, inv_max, skew_bp, sig_thr, start):
    """Market maker su griglia 100 ms. Riempimento SOLO se un trade stampa OLTRE il prezzo quotato
    (strettamente attraverso = coda in fondo). Decisione con informazione vecchia di L celle, ordini post-only.
    Ritorna: fills (cella, lato, prezzo), inventario finale, cassa."""
    n = len(bid); fi = np.empty(n, np.int64); fs = np.empty(n, np.int8); fp = np.empty(n, np.float64); nf = 0
    inv = 0; cash = 0.0; lb = 0.0; la = 0.0
    for i in range(start, n - 1):
        if lb > 0.0 and tlo[i] < lb:
            inv += 1; cash -= lb; fi[nf] = i; fs[nf] = 1; fp[nf] = lb; nf += 1; lb = 0.0
        if la > 0.0 and thi[i] > la:
            inv -= 1; cash += la; fi[nf] = i; fs[nf] = -1; fp[nf] = la; nf += 1; la = 0.0
        if i % R == 0:
            j = i - L; m = 0.5 * (bid[j] + ask[j])
            if m != m: lb = 0.0; la = 0.0; continue
            if d_bp <= 0.0:
                b = bid[j]; a = ask[j]
            else:
                c = m * (1.0 - inv * skew_bp * 1e-4)
                b = min(c * (1.0 - d_bp * 1e-4), bid[j]); a = max(c * (1.0 + d_bp * 1e-4), ask[j])
            if b >= ask[i]: b = 0.0          # post-only respinto
            if a <= bid[i]: a = 0.0
            if inv >= inv_max: b = 0.0
            if inv <= -inv_max: a = 0.0
            if sig_thr > 0.0:
                if sig[j] > sig_thr: a = 0.0
                if sig[j] < -sig_thr: b = 0.0
            lb = b; la = a
    return fi[:nf], fs[:nf], fp[:nf], inv, cash

def summarize(fi, fs, fp, inv, cash, mid, fee_bp=1.5):
    n = len(mid); out = {"fills": len(fi)}
    if len(fi) == 0: return out
    last = mid[n - 2]
    ntl = fp.sum(); pnl = cash + inv * last
    out["pnl_gross_bp_per_fill$"] = pnl / ntl * 1e4
    out["pnl_net_bp_per_fill$"] = pnl / ntl * 1e4 - fee_bp
    out["pnl_gross_$"] = pnl; out["ntl"] = ntl
    out["capt_bp"] = np.mean(fs * (mid[fi - 1] - fp) / fp) * 1e4           # semispread incassato rispetto al mid prima del fill
    for k, h in (("0.1s", 1), ("1s", 10), ("10s", 100), ("60s", 600), ("300s", 3000)):
        j = np.minimum(fi + h, n - 2); out["mo_" + k] = np.mean(fs * (mid[j] - fp) / fp) * 1e4   # markout: >0 = guadagno
    return out
