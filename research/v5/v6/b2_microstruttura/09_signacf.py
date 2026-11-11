"""Autocorrelazione del segno dei trade (aggTrades Binance USDT-M) e cio' che vale in bp: rendimento medio del trade successivo
condizionato al segno; e test 'segui il segno': dopo k trade consecutivi dello stesso segno, rendimento (ultimo prezzo) a 1s/5s."""
import glob, zipfile, io, numpy as np, pandas as pd, pyarrow.csv as pc
RAW = "/home/user/GERVA-Capital/data_cache/v6_raw"
def rd(f):
    z = zipfile.ZipFile(f); raw = z.read(z.namelist()[0]); hh = not raw[:1].isdigit()
    t = pc.read_csv(io.BytesIO(raw), read_options=pc.ReadOptions(column_names=["id", "p", "q", "f", "l", "T", "m"], skip_rows=1 if hh else 0))
    m = t["m"].to_numpy(); m = m if m.dtype == bool else np.char.lower(m.astype(str)) == "true"
    return t["T"].to_numpy().astype(np.int64), t["p"].to_numpy().astype(float), np.where(m, -1.0, 1.0)
for sym in ("BTCUSDT", "ETHUSDT"):
    acc = {"sel": [], "ver": []}
    for f in sorted(glob.glob(f"{RAW}/um_ag_{sym}_*.zip"))[::2]:
        d = f[-14:-4]; T, p, s = rd(f); per = "sel" if d < "2023" else "ver"
        r = {}
        for lag in (1, 10, 100, 1000): r[f"acf{lag}"] = np.corrcoef(s[:-lag], s[lag:])[0, 1]
        # serie di >=k segni uguali -> rendimento firmato dall'ultimo prezzo a +1s e +5s
        run = np.ones(len(s)); 
        for i in range(1, 6): run[i:] += (s[i:] == s[:-i]) & (run[i:] == i)
        for h in (1000, 5000):
            j = np.searchsorted(T, T + h, side="right") - 1
            fwd = s * (p[j] / p - 1) * 1e4
            r[f"dopo5uguali_{h//1000}s_bp"] = fwd[run >= 6].mean(); r[f"tutti_{h//1000}s_bp"] = fwd.mean()
        acc[per].append(r)
    for per in acc:
        print(sym, per, "giorni", len(acc[per]), pd.DataFrame(acc[per]).mean().round(3).to_dict())
