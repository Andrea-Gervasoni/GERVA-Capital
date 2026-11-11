"""B5 - universo point-in-time: S&P 500 + Nasdaq-100 da Wikipedia (pagine salvate in raw/).
Ricostruisce l'appartenenza all'indietro partendo dai componenti di oggi e invertendo le tabelle di ingressi/uscite."""
import pandas as pd, numpy as np, io, re, warnings, json
warnings.filterwarnings('ignore')
R = 'raw/'
def rd(f): return pd.read_html(io.StringIO(open(R + f, encoding='utf8').read()))
def tk(x):
    if not isinstance(x, str): return None
    x = re.sub(r'\[.*?\]', '', x).strip().upper().replace('.', '-')
    return x if re.fullmatch(r'[A-Z][A-Z0-9\-]{0,6}', x) else None

sp_now = rd('List_of_S%26P_500_companies.html')[0]
sp_now['t'] = sp_now['Symbol'].map(tk)
ndx_now = rd('List_of_NASDAQ-100_companies.html')[0]
ndx_now['t'] = ndx_now['Ticker'].map(tk)

def changes(f, datecol):
    t = rd(f)[0]
    t.columns = ['date', 'add', 'add_name', 'rem', 'rem_name', 'reason'] + list(t.columns[6:])
    t['date'] = pd.to_datetime(t['date'].astype(str).str.replace(r'\[.*?\]', '', regex=True), errors='coerce').ffill()
    t['add'] = t['add'].map(tk); t['rem'] = t['rem'].map(tk)
    return t.dropna(subset=['date'])[['date', 'add', 'add_name', 'rem', 'rem_name', 'reason']]
sp_ch = changes('Historical_components_of_the_S%26P_500.html', 0)
ndx_ch = changes('Historical_components_of_the_Nasdaq-100.html', 0)
print('S&P changes', len(sp_ch), sp_ch.date.min(), sp_ch.date.max(), 'adds', sp_ch['add'].notna().sum(), 'rem', sp_ch['rem'].notna().sum())
print(sp_ch.groupby(sp_ch.date.dt.year).size().to_string())
print('NDX changes', len(ndx_ch), ndx_ch.date.min(), ndx_ch.date.max(), 'adds', ndx_ch['add'].notna().sum(), 'rem', ndx_ch['rem'].notna().sum())
print(ndx_ch.groupby(ndx_ch.date.dt.year).size().to_string())

def intervals(now, ch, name):
    """ritorna righe (ticker, start, end) ; end=NaT se ancora membro"""
    ch = ch.sort_values('date', ascending=False)
    cur = {t: pd.NaT for t in now}          # ticker -> end
    out = []; anomalies = 0
    for d, g in ch.groupby('date', sort=False):
        for a in g['add'].dropna():
            if a in cur: out.append((a, d, cur.pop(a)))
            else: anomalies += 1
        for r in g['rem'].dropna():
            if r in cur: anomalies += 1
            else: cur[r] = d
    first = ch.date.min()
    for t, e in cur.items(): out.append((t, pd.Timestamp('1900-01-01'), e))
    df = pd.DataFrame(out, columns=['ticker', 'start', 'end']); df['index'] = name
    print(name, 'intervalli', len(df), 'ticker', df.ticker.nunique(), 'anomalie', anomalies, 'membri al', first.date(), len(cur))
    return df
iv = pd.concat([intervals(set(sp_now.t.dropna()), sp_ch, 'SP500'), intervals(set(ndx_now.t.dropna()), ndx_ch, 'NDX')])
# data di ingresso esatta dei membri attuali (colonna 'Date added'): toglie il look-ahead per gli ingressi non in tabella
da = dict(zip(sp_now.t, pd.to_datetime(sp_now['Date added'].astype(str).str[:10], errors='coerce')))
m = (iv['index'] == 'SP500') & (iv.start == pd.Timestamp('1900-01-01')) & iv.ticker.map(lambda t: t in da and pd.notna(da[t]))
iv.loc[m, 'start'] = iv.loc[m, 'ticker'].map(da)
print('ingressi S&P corretti con Date added:', int(m.sum()))
iv.to_csv('membership.csv', index=False)
# conteggio membri nel tempo
for nm in ['SP500', 'NDX']:
    x = iv[iv['index'] == nm]
    for d in ['2000-01-03', '2005-01-03', '2008-01-02', '2012-01-03', '2016-01-04', '2020-01-02', '2024-01-02', '2026-11-01']:
        d = pd.Timestamp(d); n = ((x.start <= d) & (x.end.isna() | (x.end > d))).sum()
        print(nm, d.date(), n)
# settori
sec = dict(zip(sp_now.t, sp_now['GICS Sector']))
icb = {'Technology': 'Information Technology', 'Consumer Discretionary': 'Consumer Discretionary', 'Health Care': 'Health Care',
       'Industrials': 'Industrials', 'Telecommunications': 'Communication Services', 'Consumer Staples': 'Consumer Staples',
       'Utilities': 'Utilities', 'Energy': 'Energy', 'Basic Materials': 'Materials', 'Financials': 'Financials', 'Real Estate': 'Real Estate'}
for t, s in zip(ndx_now.t, ndx_now.iloc[:, 3]):
    sec.setdefault(t, icb.get(s, None))
json.dump(sec, open('sectors_known.json', 'w'))
allt = sorted(iv.ticker.unique())
print('ticker totali', len(allt), 'di cui oggi membri', iv[iv.end.isna()].ticker.nunique(), 'con settore noto', sum(t in sec and sec[t] is not None for t in allt))
open('tickers_all.txt', 'w').write('\n'.join(allt))
