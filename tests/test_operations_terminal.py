import datetime as dt
import json
import subprocess
import pytest
from firm import db, health, ibkr
from firm.process_lock import exclusive


def test_lock_rejects_second_reader_and_releases(tmp_path):
    p=str(tmp_path/'reader.lock')
    with exclusive(p):
        with pytest.raises(RuntimeError):
            with exclusive(p): pass
    with exclusive(p): pass


def test_health_fallback_future_and_error(firm_env):
    now=dt.datetime(2026,11,10,12,tzinfo=dt.timezone.utc)
    for k in ('heartbeat.alive','free.alive'):
        db.runtime_set(k,now.isoformat())
    db.runtime_set('ibkr.live',dict(ts=now.isoformat(),nav=100))
    assert next(p for p in health.status(now)['parti'] if p['nome']=='IBKR')['ok']
    db.runtime_set('ibkr.live',dict(ts=now.isoformat(),nav=100,errore='down'))
    assert not next(p for p in health.status(now)['parti'] if p['nome']=='IBKR')['ok']
    db.runtime_set('heartbeat.alive',(now+dt.timedelta(days=1)).isoformat())
    assert not next(p for p in health.status(now)['parti'] if p['nome']=='Battito')['ok']


def test_nav_error_is_never_live(firm_env):
    from portal.app import _live_state
    db.runtime_set('ibkr.live',dict(ts=db.now_iso(),nav=100,errore='disconnected'))
    assert not _live_state()['fresca']


def test_terminal_does_not_filter_a_real_loss(firm_env):
    from firm.terminal import snapshot
    for i,v in enumerate([100.,80.,90.]):
        db.ex('INSERT INTO nav_ticks(ts,nav) VALUES(?,?)',(f'2026-11-{i+1:02d}T12:00:00Z',v))
    s=snapshot()
    assert s['observations']==3
    assert s['max_drawdown']==pytest.approx(-.2)
    assert s['change']==pytest.approx(-.1)
    assert 'versamenti' in s['note']


def test_scheduler_records_failure_and_does_not_replay(tmp_path,monkeypatch):
    from deploy import gervaq_scheduler as s
    monkeypatch.setattr(s,'STATE',str(tmp_path/'state.json'))
    calls=[]
    def fail(*args):
        calls.append(1)
        raise subprocess.TimeoutExpired('cmd',1)
    monkeypatch.setattr(s,'run',fail)
    done=set()
    s.run_slot(done,'eq:2026-11-10',['cmd'],'daily')
    s.run_slot(done,'eq:2026-11-10',['cmd'],'daily')
    assert len(calls)==1
    assert json.loads((tmp_path/'state.json.status.json').read_text())['eq:2026-11-10']['state']=='reconciliation_required'


def test_scheduler_success_is_explicit(tmp_path,monkeypatch):
    from deploy import gervaq_scheduler as s
    monkeypatch.setattr(s,'STATE',str(tmp_path/'state.json'))
    monkeypatch.setattr(s,'run',lambda *args:0)
    s.run_slot(set(),'eq:x',['cmd'],'daily')
    assert json.loads((tmp_path/'state.json.status.json').read_text())['eq:x']['state']=='succeeded'


def test_terminal_endpoint_empty_is_not_fabricated(firm_env):
    from fastapi.testclient import TestClient
    from portal.app import app
    r=TestClient(app).get('/api/terminal')
    assert r.status_code==200
    assert r.json()['nav'] is None and r.json()['curve']==[]


def test_failed_heartbeat_is_not_reported_as_completed(firm_env,monkeypatch):
    from firm import heartbeat
    def fail(*args): raise ValueError('fixture')
    monkeypatch.setattr(heartbeat,'_beat',fail)
    with pytest.raises(ValueError): heartbeat.beat()
    assert db.runtime_get('heartbeat.alive') is None
    assert db.runtime_get('heartbeat.error')['kind']=='ValueError'
    monkeypatch.setattr(heartbeat,'_beat',lambda *args: {'ok':True})
    heartbeat.beat()
    assert db.runtime_get('heartbeat.alive') and not db.runtime_get('heartbeat.error')
