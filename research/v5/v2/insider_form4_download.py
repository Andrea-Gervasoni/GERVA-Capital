import io, zipfile, urllib.request, time, sys
import pandas as pd
out=[]
qs=[f"{y}q{q}" for y in range(2016,2027) for q in (1,2,3,4)]
for q in qs:
    url=f"https://www.sec.gov/files/structureddata/data/insider-transactions-data-sets/{q}_form345.zip"
    try:
        req=urllib.request.Request(url,headers={"User-Agent":"research-client admin@example.org"})
        raw=urllib.request.urlopen(req,timeout=120).read()
    except Exception as e:
        print(q,'mancante',type(e).__name__,flush=True); continue
    z=zipfile.ZipFile(io.BytesIO(raw))
    rd=lambda n: pd.read_csv(z.open(n),sep='\t',dtype=str,low_memory=False)
    sub=rd('SUBMISSION.tsv'); own=rd('REPORTINGOWNER.tsv'); tr=rd('NONDERIV_TRANS.tsv')
    tr=tr[(tr.TRANS_CODE=='P')&(tr.TRANS_ACQUIRED_DISP_CD=='A')].copy()
    tr['val']=pd.to_numeric(tr.TRANS_SHARES,errors='coerce')*pd.to_numeric(tr.TRANS_PRICEPERSHARE,errors='coerce')
    v=tr.groupby('ACCESSION_NUMBER').val.sum().rename('val')
    s=sub[sub.DOCUMENT_TYPE=='4'][['ACCESSION_NUMBER','FILING_DATE','ISSUERTRADINGSYMBOL','ISSUERCIK']]
    o=own.groupby('ACCESSION_NUMBER').agg(title=('RPTOWNER_TITLE',lambda x:' | '.join(x.dropna().astype(str))),rel=('RPTOWNER_RELATIONSHIP',lambda x:' '.join(x.dropna().astype(str))),owner=('RPTOWNERCIK','first'))
    d=s.join(v,on='ACCESSION_NUMBER',how='inner').join(o,on='ACCESSION_NUMBER')
    out.append(d); print(q,len(d),flush=True); time.sleep(0.3)
D=pd.concat(out); D['FILING_DATE']=pd.to_datetime(D.FILING_DATE,format='mixed',errors='coerce'); D.to_pickle('research/v5/v2/_cache/sec/purchases.pkl'); print(len(D))
