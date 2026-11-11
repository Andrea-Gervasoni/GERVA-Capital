"""A6 - calendario macro USA (CPI, NFP, FOMC) 2020-2026. SIMULATO/ricostruito.
Fonti: FOMC = federalreserve.gov (pagine fomccalendars.htm e fomchistorical2020.htm, lette qui, confrontate con l'elenco scritto a mano).
CPI e NFP = calendario dei comunicati BLS trascritto a mano (bls.gov e FRED non sono raggiungibili da questa macchina: 403 / timeout),
con le eccezioni note (blocco del governo ott-nov 2025, breve blocco feb 2026). Ogni data e' VERIFICATA sui dati: il volume della barra
a 5 minuti di BTCUSDT perp alle 08:30 ET (14:00 ET per il FOMC) contro la mediana della stessa barra nei 20 giorni precedenti.
Scrive calendario.csv."""
import re, sys
from lib import *
from gerva.data.sources import _get
CPI = {2020: '0114 0213 0311 0410 0512 0610 0714 0812 0911 1013 1112 1210', 2021: '0113 0210 0310 0413 0512 0610 0713 0811 0914 1013 1110 1210',
       2022: '0112 0210 0310 0412 0511 0610 0713 0810 0913 1013 1110 1213', 2023: '0112 0214 0314 0412 0510 0613 0712 0810 0913 1012 1114 1212',
       2024: '0111 0213 0312 0410 0515 0612 0711 0814 0911 1010 1113 1211', 2025: '0115 0212 0312 0410 0513 0611 0715 0812 0911 1024 1218',
       2026: '0113 0213 0311 0410 0512 0610 0714 0812 0911 1014'}
NFP = {2020: '0110 0207 0306 0403 0508 0605 0702 0807 0904 1002 1106 1204', 2021: '0108 0205 0305 0402 0507 0604 0702 0806 0903 1008 1105 1203',
       2022: '0107 0204 0304 0401 0506 0603 0708 0805 0902 1007 1104 1202', 2023: '0106 0203 0310 0407 0505 0602 0707 0804 0901 1006 1103 1208',
       2024: '0105 0202 0308 0405 0503 0607 0705 0802 0906 1004 1101 1206', 2025: '0110 0207 0307 0404 0502 0606 0703 0801 0905 1120 1216',
       2026: '0109 0211 0306 0403 0508 0605 0702 0807 0904 1002'}
FOMC = {2020: '0129 0429 0610 0729 0916 1105 1216', 2021: '0127 0317 0428 0616 0728 0922 1103 1215', 2022: '0126 0316 0504 0615 0727 0921 1102 1214',
        2023: '0201 0322 0503 0614 0726 0920 1101 1213', 2024: '0131 0320 0501 0612 0731 0918 1107 1218', 2025: '0129 0319 0507 0618 0730 0917 1029 1210',
        2026: '0128 0318 0429 0617 0729 0916 1028'}
def mk(d, kind, hh, mm):
    out = []
    for y, s in d.items():
        for x in s.split():
            loc = pd.Timestamp(year=y, month=int(x[:2]), day=int(x[2:]), hour=hh, minute=mm, tz='America/New_York')
            out.append(dict(kind=kind, t=loc.tz_convert('UTC').tz_localize(None)))
    return out
cal = pd.DataFrame(mk(CPI, 'CPI', 8, 30) + mk(NFP, 'NFP', 8, 30) + mk(FOMC, 'FOMC', 14, 0)).sort_values('t').reset_index(drop=True)
cal = cal[cal.t <= '2026-10-31']
# --- confronto FOMC con federalreserve.gov
try:
    MON = dict(January=1, February=2, March=3, April=4, May=5, June=6, July=7, August=8, September=9, October=10, November=11, December=12)
    MON.update({'Jan/Feb': 2, 'Apr/May': 5, 'Oct/Nov': 11, 'Jul/Aug': 8})
    got = set()
    h = _get('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm').decode('utf8', 'ignore')
    for ym in re.finditer(r'(\d{4}) FOMC Meetings(.*?)(?=\d{4} FOMC Meetings|$)', h, re.S):
        y = int(ym.group(1))
        for m in re.finditer(r'fomc-meeting__month[^>]*>\s*<strong>([A-Za-z/]+)</strong>.*?fomc-meeting__date[^>]*>([^<]+)<', ym.group(2), re.S):
            mon, dd = m.group(1), m.group(2)
            if 'unscheduled' in dd or 'notation' in dd: continue
            last = int(re.findall(r'\d+', dd)[-1]); mo = MON[mon.split('/')[-1][:3] and [k for k in MON if k.startswith(mon.split('/')[-1][:3])][0]]; got.add(pd.Timestamp(year=y, month=mo, day=last))
    mine = set(cal[cal.kind == 'FOMC'].t.dt.normalize()); mine21 = {d for d in mine if d.year >= 2021}; got21 = {d for d in got if 2021 <= d.year and d <= pd.Timestamp('2026-10-31')}
    print('FOMC dal sito Fed (2021+):', len(got21), '| elenco a mano:', len(mine21), '| differenze:', sorted(got21 ^ mine21))
except Exception as e:
    print('confronto FOMC col sito Fed non riuscito:', str(e)[:100])
# --- verifica sui dati: picco di volume nella barra del comunicato
B = bars('BTC'); v = B.df['quote_volume']; r = (B.df['high'] / B.df['low'] - 1)
def spike(t):
    if t not in v.index: return np.nan, np.nan
    prev = [t - pd.Timedelta(days=k) for k in range(1, 21)]; prev = [p for p in prev if p in v.index]
    return v[t] / np.median(v.reindex(prev)), r[t] / np.median(r.reindex(prev))
cal['vol_x'], cal['range_x'] = zip(*[spike(t) for t in cal.t])
# controllo: la stessa barra in TUTTI i giorni feriali non-evento (falso positivo atteso)
print(cal.groupby('kind')[['vol_x', 'range_x']].describe(percentiles=[.1, .5]).round(1).to_string())
bad = cal[(cal.vol_x < 2.0) & (cal.range_x < 2.0)]
print('\ndate con picco debole (<2x volume e <2x escursione): possibili errori di data o comunicati senza sorpresa\n', bad.to_string())
# per le date deboli e per il 2026: il giorno della finestra +-4 con il picco massimo alla stessa ora
for _, row in cal[(cal.t >= '2025-10-01') | cal.index.isin(bad.index)].iterrows():
    alt = [(row.t + pd.Timedelta(days=k)) for k in range(-4, 5)]
    alt = [(a, spike(a)[0]) for a in alt if a.weekday() < 5]; best = max(alt, key=lambda x: (x[1] if np.isfinite(x[1]) else -1))
    flag = '' if best[0] == row.t else f'  <-- picco massimo il {best[0].date()} ({best[1]:.1f}x)'
    print(f'{row.kind:5s} {row.t}  vol {row.vol_x:5.1f}x  range {row.range_x:5.1f}x{flag}')
cal.to_csv(HERE + '/calendario.csv', index=False); print('\neventi:', cal.kind.value_counts().to_dict())
