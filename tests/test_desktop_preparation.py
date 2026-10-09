"""Native catalog schema fixtures, not a claim that Desktop was controlled here."""
from copy import deepcopy

import pytest

from agent_workspace import desktop_projects as projects, runtime
from agent_workspace.util import Conflict, Uncertain, Error, read_json


@pytest.fixture
def native(app, monkeypatch):
    app.create('sea', 'a'); root = app.root('sea', 'a')
    app.configure('sea', 'a', {'kind': 'desktop', 'command': ['fixture'], 'pipe_path': 'fixture', 'caller_thread': 'fixture'})
    state = {'projects': [{'projectId': 'p1', 'label': 'User-renamed project', 'projectKind': 'local',
                          'hostId': 'local', 'path': str(root)}], 'sections': [], 'calls': []}
    schema = lambda fields: {'type': 'object', 'required': fields, 'properties': {k: {'type': 'string'} for k in fields}}
    class Adapter:
        tools = {'list_projects', 'list_sidebar_sections', 'create_sidebar_section', 'move_project_to_sidebar_section'}
        tool_schemas = {'list_sidebar_sections': schema([]), 'create_sidebar_section': schema(['name']),
                        'move_project_to_sidebar_section': schema(['projectId', 'sectionId'])}
        def __init__(self, *args): pass
        def close(self): state['closed'] = True
        def call(self, name, args):
            state['calls'].append((name, args))
            if name == 'list_projects': return {'projects': deepcopy(state['projects'])}
            if name == 'list_sidebar_sections':
                if state.get('section_error'): raise Error('section lookup failed')
                return {'sections': deepcopy(state['sections'])}
            if name == 'create_sidebar_section':
                if state.get('lost_create'): raise OSError('response lost')
                state['sections'].append({'sectionId': 's1', 'name': args['name'], 'itemKeys': []})
                return {'sectionId': 's1'}
            if name == 'move_project_to_sidebar_section':
                state['sections'][0]['itemKeys'] = ['codex:project:' + args['projectId']]
                return {'moved': True}
            raise AssertionError(name)
    monkeypatch.setattr(runtime, 'Desktop', Adapter)
    return state, Adapter


def test_discovery_matches_folder_and_reuses_id_without_native_creation(app, native):
    state, _ = native
    found = projects.discover(app, 'sea', 'a')
    assert found['selected_project']['projectId'] == 'p1'
    result = projects.prepare(app, 'sea', 'a', 'request', revision=found['revision'])
    assert result['state'] == 'ready' and result['native_project_verified']
    assert result['section_state'] == 'skipped' and not result['session_created']
    assert read_json(app.root('sea', 'a') / '.aw-local/runtime.json')['project_id'] == 'p1'
    calls = list(state['calls'])
    state['projects'][0]['label'] = 'User renamed again'
    assert projects.prepare(app, 'sea', 'a', 'request', revision=found['revision']) == result
    assert state['calls'] == calls
    assert projects.discover(app, 'sea', 'a')['selected_project']['label'] == 'User renamed again'


def test_missing_project_or_ambiguous_folder_does_not_create_or_reserve(app, native):
    state, _ = native
    state['projects'][0]['path'] += '/other'
    result = projects.prepare(app, 'sea', 'a', 'missing')
    assert result['state'] == 'manual_setup_required' and not result['saved']
    assert app.agent('sea', 'a')['current'] is None
    state['projects'][0]['path'] = str(app.root('sea', 'a'))
    state['projects'].append({**state['projects'][0], 'projectId': 'p2'})
    assert projects.discover(app, 'sea', 'a')['state'] == 'selection_required'
    result = projects.prepare(app, 'sea', 'a', 'chosen', project_id='p2')
    assert result['native_project_id'] == 'p2'


def test_section_create_verify_and_repeat_does_not_move_user_layout_back(app, native):
    state, _ = native
    result = projects.prepare(app, 'sea', 'a', 'one', create_section=True)
    assert result['section_state'] == 'verified'
    assert sum(name == 'create_sidebar_section' for name, _ in state['calls']) == 1
    state['sections'][0]['itemKeys'] = []  # User's later organization.
    assert projects.prepare(app, 'sea', 'a', 'one', create_section=True) == result
    assert state['sections'][0]['itemKeys'] == []


def test_unverified_schema_degrades_to_manual_but_project_is_ready(app, native):
    state, adapter = native
    adapter.tool_schemas = {}
    result = projects.prepare(app, 'sea', 'a', 'manual', create_section=True)
    assert result['state'] == 'ready' and result['section_state'] == 'manual_setup_required'
    assert [n for n, _ in state['calls']] == ['list_projects']


def test_section_lookup_failure_does_not_block_core_project_reuse(app, native):
    state, _ = native; state['section_error'] = True
    found = projects.discover(app, 'sea', 'a')
    assert found['state'] == 'ready' and found['section_state'] == 'lookup_failed'
    assert projects.prepare(app, 'sea', 'a', 'core')['state'] == 'ready'


def test_unknown_creation_does_not_create_another_section(app, native):
    state, _ = native; state['lost_create'] = True
    result = projects.prepare(app, 'sea', 'a', 'unknown', create_section=True)
    assert result['state'] == 'ready' and result['section_state'] == 'outcome_unknown'
    assert projects.prepare(app, 'sea', 'a', 'unknown', create_section=True) == result
    current = projects.plan(app, 'sea', 'a')
    again = projects.prepare(app, 'sea', 'a', 'new-id', create_section=True, revision=current['revision'])
    assert again['section_state'] == 'outcome_unknown'
    assert read_json(app.root('sea', 'a') / '.aw-local/runtime.json')['project_id'] == 'p1'
    assert sum(n == 'create_sidebar_section' for n, _ in state['calls']) == 1
    assert app.agent('sea', 'a')['current'] is None


def test_preparation_refuses_active_or_stale_preferences(app, native):
    found = projects.plan(app, 'sea', 'a')
    projects.save(app, 'sea', 'a', 'codex', 'different', revision=found['revision'])
    with pytest.raises(Conflict): projects.prepare(app, 'sea', 'a', 'stale')
    found = projects.plan(app, 'sea', 'a')
    app.reserve('sea', 'a')
    with pytest.raises(Conflict): projects.prepare(app, 'sea', 'a', 'active', revision=found['revision'])


def test_display_rename_preserves_saved_native_id(app, native):
    projects.prepare(app, 'sea', 'a', 'adopt')
    current = projects.plan(app, 'sea', 'a')
    saved = projects.save(app, 'sea', 'a', 'codex', 'preference-only', revision=current['revision'])
    assert saved['project']['native_project_id'] == 'p1'


def test_already_correct_section_membership_needs_no_native_write(app, native):
    state, _ = native
    state['sections'] = [{'sectionId': 's1', 'name': 'AW · sea', 'itemKeys': ['codex:project:p1']}]
    result = projects.prepare(app, 'sea', 'a', 'reuse', create_section=True)
    assert result['section_state'] == 'verified'
    assert not any(n in ('create_sidebar_section', 'move_project_to_sidebar_section') for n, _ in state['calls'])


def test_ambiguous_section_is_preflight_failure_without_a_write_receipt(app, native):
    state, _ = native
    state['sections'] = [{'sectionId': f's{i}', 'name': 'AW · sea', 'itemKeys': []} for i in (1, 2)]
    with pytest.raises(Conflict): projects.prepare(app, 'sea', 'a', 'ambiguous', create_section=True)
    assert not (app.root('sea', 'a') / '.aw-local/desktop-preparations/ambiguous.json').exists()
