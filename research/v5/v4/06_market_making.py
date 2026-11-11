"""Famiglia 6 - market making: IPOTESI, non un backtest. Senza il book (L2) e la coda degli ordini non si puo' simulare
onestamente; qui c'e' solo un limite dai dati a barre (Binance USDT-M reali, 5m per BTC/ETH/SOL e 1h per 7 alt):
a ogni barra si quota denaro e lettera a +-d dalla chiusura precedente; si considera eseguito l'ordine se il minimo/massimo
della barra lo tocca (ottimistico: primi in coda) oppure lo supera di 1 pb (meno ottimistico); la posizione si chiude alla
chiusura della barra. Guadagno per esecuzione = d - selezione avversa - commissioni.
Commissioni Hyperliquid (fonte: documentazione ufficiale, novembre 2026): livello base maker +1,5 pb (si PAGA), taker 4,5 pb;
lo sconto maker (-0,1/-0,2/-0,3 pb) richiede >0,5% / 1,5% / 3% del volume maker dell'intera piattaforma: fuori portata."""
from lab import *
F = Fam('mm')
def mm(b, d, through=0.0, fm=0.00015, exit_fee=0.00015, size=0.10):
    m = b['close'].shift(1); bid = m * (1 - d); ask = m * (1 + d)
    fb = b['low'] <= bid * (1 - through); fs = b['high'] >= ask * (1 + through)
    pb = (b['close'] / bid - 1 - fm - exit_fee).where(fb, 0.0); ps = (1 - b['close'] / ask - fm - exit_fee).where(fs, 0.0)
    gb = (b['close'] / bid - 1).where(fb); gs = (1 - b['close'] / ask).where(fs)
    g = pd.concat([gb.dropna(), gs.dropna()])
    return daily((pb + ps).fillna(0.0) * size), float((fb.mean() + fs.mean()) / 2), float(g.mean() * 1e4), g
print('== 6a. BTC/ETH/SOL, barre da 5 minuti. Guadagno LORDO medio per esecuzione (pb) = distanza d - selezione avversa')
rows = []
B = {c: get(f'v4_um_5m_{c}USDT').loc['2021-01-01':'2026-10-31'] for c in ('BTC', 'ETH', 'SOL')}
for d in (0.0001, 0.0002, 0.0005, 0.0010, 0.0020, 0.0040):
    for thr, lab in ((0.0, 'tocco'), (0.0001, 'superato di 1 pb')):
        res = [mm(B[c], d, thr) for c in B]; fill = np.mean([x[1] for x in res]); gross = np.mean([x[2] for x in res])
        gs_, gv = [np.mean([mm(B[c].loc[sl], d, thr)[2] for c in B]) for sl in (slice(None, SEL_END), slice(SPL, None))]
        net_m = gross - 1.5 - 1.5; net_t = gross - 1.5 - 4.5 - 0.5; net_r = gross + 0.3 + 0.3
        r = pd.concat([x[0] for x in res], axis=1).mean(axis=1); F.trial(f'mm 5m d{d} {lab} maker+maker', r)
        rows.append(dict(d_pb=d * 1e4, esecuzione=lab, quota_barre_eseguite=round(fill, 3), lordo_pb=round(gross, 2), lordo_scelta=round(gs_, 2), lordo_verifica=round(gv, 2),
                         selezione_avversa_pb=round(d * 1e4 - gross, 2), netto_uscita_maker_base=round(net_m, 2), netto_uscita_taker=round(net_t, 2), netto_con_sconto_massimo=round(net_r, 2),
                         sharpe_netto_maker=round(three(r)['sh_tot'], 2)))
print(pd.DataFrame(rows).to_string(index=False))
print('\n== 6b. Sette alt (XRP DOGE ADA LINK AVAX LTC BNB), barre da 1 ora')
rows = []
A = {c: get(f'v4_um_1h_{c}USDT').loc['2021-01-01':'2026-10-31'] for c in 'XRP DOGE ADA LINK AVAX LTC BNB'.split()}
for d in (0.0010, 0.0025, 0.0050, 0.0100, 0.0200):
    for thr, lab in ((0.0, 'tocco'), (0.0001, 'superato di 1 pb')):
        res = [mm(A[c], d, thr) for c in A]; fill = np.mean([x[1] for x in res]); gross = np.mean([x[2] for x in res])
        gs_, gv = [np.mean([mm(A[c].loc[sl], d, thr)[2] for c in A]) for sl in (slice(None, SEL_END), slice(SPL, None))]
        r = pd.concat([x[0] for x in res], axis=1).mean(axis=1); t = F.trial(f'mm 1h alt d{d} {lab} maker+maker', r)
        rows.append(dict(d_pb=d * 1e4, esecuzione=lab, quota_barre_eseguite=round(fill, 3), lordo_pb=round(gross, 2), lordo_scelta=round(gs_, 2), lordo_verifica=round(gv, 2),
                         netto_uscita_maker_base=round(gross - 3.0, 2), netto_uscita_taker=round(gross - 6.5, 2), sharpe_tot=round(t['sh_tot'], 2), sharpe_scelta=round(t['sh_sel'], 2), sharpe_verifica=round(t['sh_ver'], 2)))
print(pd.DataFrame(rows).to_string(index=False))
print('''\nLettura: il "lordo" a barre e' un LIMITE SUPERIORE (priorita' di coda perfetta, nessuna latenza, uscita al prezzo di chiusura senza impatto).
Lo spread reale su BTC/ETH in Hyperliquid e' di circa 0,1-0,3 pb (1 tick): un retail al livello base paga 1,5 pb per lato da maker, cioe' piu' dello spread che incassa.
Con d ampi (>= 20 pb) si diventa di fatto una strategia di ritorno alla media intrabarra: l'eventuale margine viene dall'inversione, non dallo spread, e va giudicato come tale.''')
F.save()
