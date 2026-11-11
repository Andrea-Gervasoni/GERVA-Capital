"""B5 - copertura dell'universo: quanti membri (nominali, da Wikipedia) hanno prezzi, per anno; ticker riusati."""
from lab import *
P = load()
mem = pd.read_csv(D + 'membership.csv', parse_dates=['start', 'end'])
cal = P['member'].index
have = set(P['member'].columns)
print('ticker con prezzi', len(have), ' ticker nelle tabelle', mem.ticker.nunique())
rem = mem[mem.end.notna()]
print('intervalli chiusi (rimossi):', len(rem), ' con prezzi:', rem.ticker.isin(have).sum())
# ticker riusato: dati che iniziano dopo la fine dell'appartenenza, o finiscono prima dell'inizio
fv = P['ac'].apply(lambda s: s.first_valid_index()); lv = P['ac'].apply(lambda s: s.last_valid_index())
print('settori:', P['sector'].value_counts().to_dict())
rows = []
for y in range(2005, 2027):
    d = cal[cal >= f'{y}-01-01'][0]
    for nm, tgt in (('SP500', 500), ('NDX', 100)):
        x = mem[(mem['index'] == nm) & (mem.start <= d) & (mem.end.isna() | (mem.end > d))]
        n_nom = len(x); n_px = sum((t in have) and pd.notna(P['ac'].at[d, t]) for t in x.ticker)
        n_today = x.end.isna().sum()
        rows.append((y, nm, tgt, n_nom, n_px, n_today))
df = pd.DataFrame(rows, columns=['anno', 'indice', 'veri', 'in_tabella', 'con_prezzi', 'di_cui_membri_oggi'])
df['copertura%'] = (df.con_prezzi / df.veri * 100).round(0)
df['rimossi_con_prezzi'] = df.con_prezzi - df.di_cui_membri_oggi
print(df.to_string(index=False))
u = P['member'].sum(axis=1); print('membri unici con prezzi per data (unione):'); print(u.groupby(u.index.year).mean().round(0).to_string())
# rendimenti medi: membri PIT vs membri di oggi (stessa data) -> stima del bias sul rendimento medio equipesato
r = P['ret']
a = r.where(P['member'].shift(1)).mean(axis=1); b = r.where(P['today'].shift(1)).mean(axis=1)
for lab_, sl in (('2005-2014', slice('2005', '2014')), ('2015-2022', slice('2015', '2022')), ('2023-2026', slice('2023', '2026'))):
    print(lab_, 'equipesato membri PIT %.1f%%/anno' % (a.loc[sl].mean() * 25200), ' membri di oggi (sopravvissuti) %.1f%%/anno' % (b.loc[sl].mean() * 25200),
          ' SPY %.1f%%' % (P['spy_ret'].loc[sl].mean() * 25200))
