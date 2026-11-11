"""A1 - costruzione del pannello (moneta, giorno): trade-sonda + componenti note la sera prima + conviction attuale. SIMULATO."""
import lib, numpy as np, pandas as pd
import leva_trade_isolato as L
COINS = ('BTC', 'ETH', 'SOL')
PATH = {c: lib.Path(L.B[c], L.fund(c)) for c in COINS}
def components(d, tk, f, bars, btc_close):
    """Tutte le componenti, valore alla chiusura di t (NON ancora spostate)."""
    vol = tk['volume'].reindex(d.index)
    X = pd.DataFrame(index=d.index)
    X['tq'] = lib.trend_quality(d['close'])
    X['r2'] = sum(lib.r2_signed(d['close'], lb) for lb in (30, 60, 120)) / 3
    X['comp'] = lib.compression(d)
    X['vwm'] = lib.avwap_month(d, vol)
    X['vws'] = lib.avwap_swing(d, vol)
    X['flow'] = lib.flow(tk.reindex(d.index))
    X['fund'] = lib.funding_state(f, d.index)
    X['rpos'] = lib.range_pos(d)
    X['mtf'] = lib.mtf(bars).reindex(d.index)
    X['btc'] = lib.trend_quality(btc_close).reindex(d.index)
    return X
def _unused():
    pass
def panel(probe_kw=dict(atr_k=1.0, trail=2.0, maxhold=7), tag='C'):
    rows = []
    for c in COINS:
        P = PATH[c]; d = P.d; tk = lib.st.get(f'v5_spot_1d_tk_{c}')
        X = components(d, tk, L.fund(c), L.B[c], PATH['BTC'].d['close']).shift(1)       # noto la sera prima
        T = P.probes(**probe_kw).set_index('entry')
        Z = T[['R', 's', 'why', 'days']].join(X).join(L.CONV[c][['score', 'tier']])
        Z['coin'] = c; rows.append(Z.reset_index().rename(columns={'index': 'entry'}))
    return pd.concat(rows, ignore_index=True)
if __name__ == '__main__':
    Z = panel(); Z.to_parquet('_panel_C.parquet'); print(Z.shape, Z.entry.min(), Z.entry.max()); print(Z.describe().round(3).T.to_string())
    Z = panel(dict(s=0.017, atr_k=None, trail=None, maxhold=7), 'A'); Z.to_parquet('_panel_A.parquet')
