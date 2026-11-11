"""B8 - scarica (cache data_cache, chiavi v6_b8_y_*) le serie giornaliere Yahoo che servono a riesprimere il sistema
originale e che la cache non ha: EMB e le 90 azioni di S4 (quantlab/gervaq4.STOCKS). Idempotente."""
import sys, time; sys.path.insert(0, '/home/user/GERVA-Capital')
from gerva.data import sources as DS
from quantlab import gervaq4 as G4
st = DS.Store('/home/user/GERVA-Capital/data_cache')
ok, bad = 0, []
for s in ['EMB'] + G4.STOCKS:
    k = f'v6_b8_y_{s}'
    if st.has(k): ok += 1; continue
    try:
        df = DS.yahoo(s, '1d'); st.put(k, df, 'yahoo'); ok += 1; time.sleep(0.4)
    except Exception as e:
        bad.append((s, str(e)[:80])); time.sleep(2)
print('ok', ok, 'mancanti', bad)
