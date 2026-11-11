"""Date delle riunioni FOMC programmate (giorno dell'annuncio = ultimo giorno della riunione), dal sito della Federal Reserve.
Solo riunioni programmate: niente conference call ne' riunioni straordinarie. Scrive fomc_dates.csv. FATTO (fonte ufficiale)."""
import re, sys, time, urllib.request
import pandas as pd
sys.path.insert(0, '/home/user/GERVA-Capital')
from gerva.data.sources import _get

MONTHS = {m: i + 1 for i, m in enumerate(['January', 'February', 'March', 'April', 'May', 'June', 'July', 'August',
                                          'September', 'October', 'November', 'December'])}
SHORT = {m[:3]: i for m, i in MONTHS.items()}


def last_day(year, mon_txt, day_txt):
    """'January 27-28' -> 28 gen; 'Jan/Feb 31-1' o 'April/May 30-1' -> 1 del secondo mese."""
    mons = [x.strip() for x in mon_txt.replace('.', '').split('/')]
    days = [int(x) for x in re.findall(r'\d+', day_txt)]
    m = mons[-1]
    mi = MONTHS.get(m) or SHORT.get(m[:3])
    return pd.Timestamp(year=year, month=mi, day=days[-1])


out = []
for y in range(1994, 2021):
    html = _get(f'https://www.federalreserve.gov/monetarypolicy/fomchistorical{y}.htm').decode('utf8', 'ignore')
    for h in re.findall(r'<h5[^>]*>([^<]*)</h5>', html):
        h = h.strip()
        m = re.match(r'([A-Za-z/\.]+)\s+([\d\-– ]+?)\s*(?:,\s*\d{4}\s*)?Meeting\s*-\s*(\d{4})', h)
        if not m or 'unscheduled' in h.lower() or 'Conference' in h:
            continue
        out.append(last_day(int(m.group(3)), m.group(1), m.group(2)))
    time.sleep(0.3)
html = _get('https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm').decode('utf8', 'ignore')
parts = re.split(r'>(\d{4}) FOMC Meetings', html)
for k in range(1, len(parts), 2):
    y = int(parts[k]); body = parts[k + 1]
    for mon, day in re.findall(r'fomc-meeting__month[^>]*>\s*<strong>([^<]*)</strong>.*?fomc-meeting__date[^>]*>([^<]*)<', body, flags=re.S):
        if 'unscheduled' in day.lower() or 'notation' in day.lower():
            continue
        if y >= 2021:
            out.append(last_day(y, mon.strip(), day))
d = pd.Series(sorted(set(out)), name='date')
d.to_csv('/home/user/GERVA-Capital/research/v5/v5/a5_indici/fomc_dates.csv', index=False)
print(len(d), 'riunioni', d.iloc[0].date(), d.iloc[-1].date())
print(d.dt.year.value_counts().sort_index().to_string())
