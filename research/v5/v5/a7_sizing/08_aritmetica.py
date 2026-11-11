"""A7 - cosa aggiunge il sizing per conviction nei termini dell'aritmetica del brief: N*SR^2 del flusso pesato (x = w*R), per periodo. SIMULATO."""
import lib,numpy as np,pandas as pd,pickle
P=pickle.load(open(lib.HERE+'pesi.pkl','rb')); D=P['D']; WC=P['W']
for n in ('A30','C11'):
    X=D[n]; print(n,'pesi score (stimati sulla scelta, normalizzati a media 1):',dict(pd.Series(WC[n]['score']/WC[n]['score'].mean()).groupby(X.sb.values).first().round(2)),' quota trade per classe:',X.sb.value_counts(normalize=True).round(2).to_dict())
    for fam,w in (('piatto',np.ones(len(X))),('livelli_v4 (1x / 2x sopra 0,75)',np.where(X.score>0.75,2.,1.)),('score (Kelly di classe)',WC[n]['score']/WC[n]['score'].mean()),('senza score 0,67',np.where(X.score>0.70,1.,0.))):
        out=[]
        for sc,m in (('intero',X.entry>'1900'),('scelta',X.entry<lib.SPLIT),('verifica',X.entry>=lib.SPLIT)):
            x=(w*X.R.values)[m.values]; y=(X.entry[m].max()-X.entry[m].min()).days/365.25; N=len(x)/y; sr=x.mean()/x.std(); out.append(f'{sc}: SR={sr:.3f} t={sr*np.sqrt(len(x)):.2f} N*SR^2={N*sr*sr:.2f} -> Kelly pieno gauss. {np.expm1(N*sr*sr/24)*100:.1f}%/mese')
        print(f'  {fam:34s}',' | '.join(out))
