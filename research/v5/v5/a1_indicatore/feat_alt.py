"""A1 - pannello esteso: 18 altre monete (comprese LUNA, FTT, EOS: morte), percorso a 1 ora sui perpetual USDT-M Binance (v4_um_1h_*),
componenti dalle candele giornaliere spot (storia piu' lunga). Stessa convenzione di trade. SIMULATO."""
import lib, numpy as np, pandas as pd
from gerva import ensemble as E
import feat
ALT = "BNB XRP DOGE ADA LTC LINK AVAX DOT BCH ETC ATOM TRX XLM UNI AAVE EOS LUNA FTT".split()
def load(c):
    b = lib.st.get(f'v4_um_1h_{c}USDT'); tk = lib.st.get(f'v5_spot_1d_tk_{c}')
    if c == 'LUNA': tk = tk[tk.index < '2022-05-14']; b = b[b.index < '2022-05-14']      # LUNA: il vecchio contratto muore a maggio 2022
    b = b.loc[:b.index[b['quote_volume'] > 0][-1]]                                       # la cache riempie di barre piatte dopo il delisting (FTT): tagliate
    return b, tk
def panel(coins=ALT, probe_kw=dict(atr_k=1.0, trail=2.0, maxhold=7)):
    rows = []; btc = feat.PATH['BTC'].d['close']
    for c in coins:
        b, tk = load(c); f = lib.fund_daily(c); P = lib.Path(b, f)
        d = tk[['open', 'high', 'low', 'close']]
        X = feat.components(d, tk, f, b, btc).shift(1)
        cv = E.conviction(E.crypto_signals(d, btc, f), 'crypto').shift(1)
        T = P.probes(i0=15, **probe_kw).set_index('entry')
        Z = T[['R', 's', 'why', 'days']].join(X).join(cv[['score', 'tier']]); Z['coin'] = c
        rows.append(Z.reset_index().rename(columns={'index': 'entry'}))
    return pd.concat(rows, ignore_index=True)
if __name__ == '__main__':
    Z = panel(); Z.to_parquet('_panel_alt_C.parquet'); print(Z.shape); print(Z.groupby('coin').agg(n=('R', 'size'), da=('entry', 'min'), a=('entry', 'max'), R=('R', 'mean')).round(3).to_string())
    Z = panel(feat.COINS); Z.to_parquet('_panel_big3_1h_C.parquet'); print('BTC/ETH/SOL su percorso perp 1h:', Z.groupby('coin').R.agg(['size', 'mean']).round(3).to_dict('index'))
