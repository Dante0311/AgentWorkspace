"""Repair effects and later observations have separate durable outcomes."""
from unittest.mock import Mock

import pytest

from agent_workspace import maintenance
from agent_workspace.util import Conflict, Error, read_json


@pytest.fixture
def idle_instance(app):
    app.create('sea', 'alice')
    return app


def repair(app, request_id='repair-one'):
    return maintenance.repair(app, 'sea', 'alice', 'sync-idle', request_id)


def receipt(app):
    return read_json(maintenance.folder(app, 'sea') / 'repairs/repair-one.json')


def test_failed_verification_preserves_effect_and_retries_only_observation(idle_instance, monkeypatch):
    app = idle_instance
    sync = Mock(return_value={'revision': 'saved-effect'})
    doctor = Mock(side_effect=[Error('health read failed'), {'state': 'healthy', 'issues': []}])
    monkeypatch.setattr(app, 'sync_agent', sync)
    monkeypatch.setattr(maintenance, 'doctor', doctor)
    first = repair(app)
    assert first['state'] == 'applied'
    assert first['result'] == {'revision': 'saved-effect'}
    assert first['verification']['state'] == 'unavailable'
    assert receipt(app) == first
    second = repair(app)
    assert second['verification']['state'] == 'healthy'
    assert sync.call_count == 1 and doctor.call_count == 2
    assert repair(app) == second
    assert sync.call_count == 1 and doctor.call_count == 2


def test_process_exit_during_verification_does_not_lose_effect(idle_instance, monkeypatch):
    app = idle_instance
    sync = Mock(return_value={'revision': 'saved-effect'})
    monkeypatch.setattr(app, 'sync_agent', sync)

    def interrupted(*args):
        assert receipt(app)['result'] == {'revision': 'saved-effect'}
        raise KeyboardInterrupt

    monkeypatch.setattr(maintenance, 'doctor', interrupted)
    with pytest.raises(KeyboardInterrupt):
        repair(app)
    assert receipt(app)['state'] == 'applied'
    assert 'verification' not in receipt(app)
    monkeypatch.setattr(maintenance, 'doctor', lambda *args: {'state': 'healthy', 'issues': []})
    assert repair(app)['verification']['state'] == 'healthy'
    sync.assert_called_once()


def test_verification_save_failure_never_reexecutes_effect(idle_instance, monkeypatch):
    app = idle_instance
    sync = Mock(return_value={'revision': 'saved-effect'})
    monkeypatch.setattr(app, 'sync_agent', sync)
    monkeypatch.setattr(maintenance, 'doctor', lambda *args: {'state': 'healthy', 'issues': []})
    write = maintenance.write_json

    def fail_observation(path, value):
        if 'verification' in value:
            raise OSError('observation save failed')
        write(path, value)

    monkeypatch.setattr(maintenance, 'write_json', fail_observation)
    with pytest.raises(OSError):
        repair(app)
    assert receipt(app)['state'] == 'applied'
    assert receipt(app)['result'] == {'revision': 'saved-effect'}
    monkeypatch.setattr(maintenance, 'write_json', write)
    assert repair(app)['verification']['state'] == 'healthy'
    sync.assert_called_once()


def test_uncertain_effect_remains_uncertain_and_is_never_replayed(idle_instance, monkeypatch):
    app = idle_instance
    sync = Mock(side_effect=OSError('write may have succeeded'))
    doctor = Mock()
    monkeypatch.setattr(app, 'sync_agent', sync)
    monkeypatch.setattr(maintenance, 'doctor', doctor)
    with pytest.raises(OSError):
        repair(app)
    assert receipt(app)['state'] == 'outcome_unknown'
    assert repair(app)['state'] == 'outcome_unknown'
    sync.assert_called_once()
    doctor.assert_not_called()
    with pytest.raises(Conflict):
        maintenance.repair(app, 'sea', 'alice', 'publication-reconcile', 'repair-one', operation_id='different')


def test_doctor_isolates_unreadable_instance_state(app):
    app.create('sea', 'broken')
    app.create('sea', 'other')
    damaged = app.root('sea', 'broken') / '.aw-local/status.json'
    damaged.write_text('{not JSON', encoding='utf-8')
    from agent_workspace.util import write_json
    write_json(app.root('sea', 'other') / '.aw-local/inputs/unresolved.json',
               {'id': 'unresolved', 'state': 'outcome_unknown'})
    report = maintenance.doctor(app, 'sea')
    assert report['state'] == 'degraded'
    assert any(i['code'] == 'local_observation_failed' and i['agent'] == 'broken' for i in report['issues'])
    assert any(i['code'] == 'input_outcome_unknown' and i['agent'] == 'other' for i in report['issues'])
    assert damaged.read_text() == '{not JSON'


def test_doctor_reports_unreadable_publication_without_discarding_it(app):
    path = app.home / 'operations/unreadable.json'
    path.parent.mkdir(exist_ok=True)
    path.write_text('{broken', encoding='utf-8')
    report = maintenance.doctor(app, 'sea')
    assert report['state'] == 'degraded'
    assert any(i['code'] == 'publication_record_unreadable' and i['operation'] == 'unreadable'
               for i in report['issues'])
    assert path.read_text() == '{broken'
