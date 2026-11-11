"""A1 - indicatore GQ ("qualita' del trend"), CONGELATO dopo il periodo di scelta. SIMULATO.

GQ(t) = [ TQ_moneta(t)/0,20 + TQ_BTC(t)/0,20 + VWM_moneta(t)/0,40 ] / 3      (valore alla chiusura di t; si usa dal giorno t+1)

  TQ  = media degli efficiency ratio con segno a 10, 30, 60, 120 giorni: (ln C_t - ln C_{t-n}) / somma |variazioni giornaliere di ln C|.
        Misura QUANTO PULITO e' il movimento (1 = linea retta in salita, 0 = rumore), non solo il suo segno.
  TQ_BTC = lo stesso su BTC: nelle crypto il regime lo fa il capofila (per BTC conta doppio il proprio trend).
  VWM = (C / VWAP ancorato all'apertura del mese - 1) / ATR%14, limitato a +-3 e diviso 3: chi ha comprato nel mese e' in guadagno o in perdita?
  0,20 / 0,20 / 0,40 = deviazioni standard arrotondate delle tre componenti nel periodo di scelta (pesi uguali, niente stime).
Orizzonti (10/30/60/120) e ATR a 14 giorni sono quelli gia' usati dalla conviction: nessun parametro nuovo cercato.
"""
import numpy as np, pandas as pd, lib
SD = dict(tq=0.20, btc=0.20, vwm=0.40)
def gq(d, vol, btc_close):
    """d: barre giornaliere (open, high, low, close); vol: volume giornaliero; btc_close: chiusure BTC. Ritorna GQ alla chiusura di t."""
    tq = lib.trend_quality(d['close']); b = lib.trend_quality(btc_close).reindex(d.index); v = lib.avwap_month(d, vol.reindex(d.index))
    return (tq / SD['tq'] + b / SD['btc'] + v / SD['vwm']) / 3
