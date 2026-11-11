import lib,numpy as np,pandas as pd,time
D=lib.load()
for n in ('A30','C11'):
    X=D[n]; print(n, X.score.describe().round(3).to_dict()); print(X.groupby('entry').size().value_counts().to_dict())
    T=lib.tensors(X); print(T[0].shape, (T[1].sum((1,2))==0).sum(),'mesi vuoti')
    t=time.time(); print(lib.sim(T,0.01)); print(time.time()-t)
    print('kelly seq',lib.kelly_seq(X.R,X.cap),'coh',lib.kelly_coh(X))
