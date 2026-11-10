"""Research-only cost/uncertainty-aware allocation; never submits orders.

Inputs are annualized excess return/covariance estimates. Linear transaction costs
are charged per unit of one-way turnover and amortized over the holding horizon.
Uncertainty is a penalty on expected alpha, NOT a claimed confidence interval.
"""
import numpy as np
from scipy.optimize import minimize


def allocate(mu, cov, previous, *, cost_bps=10., uncertainty=None,
             risk_aversion=4., holding_days=21, max_weight=.25, max_gross=1.):
    mu, cov, previous = np.asarray(mu, float), np.asarray(cov, float), np.asarray(previous, float)
    n = len(mu)
    if n == 0 or mu.shape != (n,) or cov.shape != (n,n) or previous.shape != (n,):
        raise ValueError('incompatible dimensions')
    cost = np.broadcast_to(np.asarray(cost_bps, float), (n,)) / 10000
    unc = np.zeros(n) if uncertainty is None else np.broadcast_to(np.asarray(uncertainty, float), (n,))
    if not all(np.isfinite(x).all() for x in (mu,cov,previous,cost,unc)):
        raise ValueError('non-finite inputs')
    if not np.isfinite([risk_aversion,holding_days,max_weight,max_gross]).all() or risk_aversion <= 0 or holding_days <= 0 or not 0 < max_weight <= 1 or not 0 < max_gross <= 1:
        raise ValueError('invalid research limits')
    if (cost < 0).any() or (unc < 0).any() or (previous < 0).any() or previous.sum() > 1 + 1e-9:
        raise ValueError('invalid costs, uncertainty or previous weights')
    if not np.allclose(cov,cov.T,atol=1e-10) or np.linalg.eigvalsh(cov).min() < -1e-10:
        raise ValueError('covariance must be symmetric positive semidefinite')
    cov = (cov+cov.T)/2
    annual_cost = cost * 252 / holding_days
    # Auxiliary variables z >= |w - previous| make the cost function smooth.
    def objective(x):
        w,z = x[:n],x[n:]
        return float(.5*risk_aversion*w@cov@w - (mu-unc)@w + annual_cost@z)
    def jac(x):
        return np.r_[risk_aversion*cov@x[:n]-(mu-unc),annual_cost]
    start = np.minimum(previous,max_weight)
    start *= min(1.,max_gross/max(start.sum(),1e-12))
    result = minimize(objective,np.r_[start,np.abs(start-previous)],jac=jac,method='SLSQP',
        bounds=[(0,max_weight)]*n+[(0,None)]*n,
        constraints=[{'type':'ineq','fun':lambda x:max_gross-x[:n].sum()},
                     {'type':'ineq','fun':lambda x:x[n:]-(x[:n]-previous)},
                     {'type':'ineq','fun':lambda x:x[n:]+(x[:n]-previous)}],
        options={'ftol':1e-12,'maxiter':1000})
    w=result.x[:n]
    if not result.success or not np.isfinite(w).all() or w.min() < -1e-7 or w.max() > max_weight+1e-7 or w.sum() > max_gross+1e-7:
        raise RuntimeError('allocation failed: '+result.message)
    w=np.clip(w,0,max_weight)
    delta=np.abs(w-previous)
    return dict(weights=w,cash=max(0.,1-w.sum()),turnover=float(delta.sum()),
                estimated_cost=float(cost@delta),annualized_utility=-objective(np.r_[w,delta]))
