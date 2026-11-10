import numpy as np
import pytest
from quantlab.implementation import allocate


def test_costs_create_no_trade_region():
    x=allocate([.08],[[.04]],[.5],cost_bps=100,holding_days=5,max_weight=1)
    assert x['weights'][0]==pytest.approx(.5,abs=1e-6)
    assert x['estimated_cost']==pytest.approx(0,abs=1e-8)


def test_zero_cost_matches_analytic_solution():
    x=allocate([.08],[[.04]],[0],cost_bps=0,max_weight=1)
    assert x['weights'][0]==pytest.approx(.5,abs=1e-5)


def test_uncertainty_and_limits():
    x=allocate([.1,.2],np.eye(2)*.04,[0,0],uncertainty=[.2,0],cost_bps=0,max_weight=.3,max_gross=.4)
    assert x['weights'][0]==pytest.approx(0,abs=1e-7)
    assert x['weights'].sum()<=.4+1e-7
    assert x['weights'].max()<=.3+1e-7


@pytest.mark.parametrize('cov', [[[float('nan')]], [[-.1]]])
def test_invalid_covariance_rejected(cov):
    with pytest.raises(ValueError): allocate([.1],cov,[0])
