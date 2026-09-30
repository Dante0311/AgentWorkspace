import concurrent.futures
from pathlib import Path
import pytest
from agent_workspace.app import App
from agent_workspace.commands import execute
from agent_workspace.util import Conflict, Error, read_json


def test_creation_without_definition_or_work(app):
    result = app.create('sea', '构建助手')
    root = Path(result['directory'])
    assert root.joinpath('AGENTS.md').is_file()
    assert len(list(root.glob('.agents/skills/*/SKILL.md'))) == 7
    assert not root.joinpath('source.json').exists()
    assert app.agent('sea', result['id'])['current'] is None
    assert app.work_list('sea') == []
    assert not root.joinpath('.aw-local/runtime.json').exists()


def test_connect_multiple_copies(app, tmp_path):
    app.create('sea', 'alice')
    second = tmp_path / 'copy2'
    app.connect_agent('sea', 'alice', str(second))
    other = App(tmp_path / 'otherhome')
    other.workspace_connect('sea', app.store('sea').address)
    other.connect_agent('sea', 'alice', str(second))
    assert other.root('sea', 'alice') == second
    assert len(app.show('sea', 'alice')['directories']) == 2
    assert app.agent('sea', 'alice')['current'] is None


def test_entry_lifecycle_never_reuses_session(app):
    app.create('sea', 'alice')
    binding = app.reserve('sea', 'alice')['binding']
    with pytest.raises(Conflict):
        app.require_binding('sea', 'alice', binding)
    app.bind('sea', 'alice', binding, 'real-1')
    with pytest.raises(Conflict):
        app.reserve('sea', 'alice')
    cp = app.checkpoint('sea', 'alice', 'done', binding=binding)
    app.stop('sea', 'alice', binding, cp['id'])
    with pytest.raises(Conflict):
        app.finish_stop('sea', 'alice', binding, observed_idle=False)
    app.finish_stop('sea', 'alice', binding, observed_idle=True)
    new = app.reserve('sea', 'alice')['binding']
    with pytest.raises(Conflict):
        app.bind('sea', 'alice', new, 'real-1')
    app.bind('sea', 'alice', new, 'real-2')
    with pytest.raises(Conflict):
        app.require_binding('sea', 'alice', binding)


def test_concurrent_handoff_claim(pair, tmp_path):
    app, ids = pair; binding = ids['alice']
    cp = app.checkpoint('sea', 'alice', 'handoff', binding=binding)
    app.stop('sea', 'alice', binding, cp['id'])
    point = app.finish_stop('sea', 'alice', binding, observed_idle=True)
    other = App(tmp_path / 'second-home')
    other.workspace_connect('sea', app.store('sea').address)
    other.connect_agent('sea', 'alice', str(tmp_path / 'copy'))
    def claim(instance):
        try:
            return instance.reserve('sea', 'alice')['binding']
        except Conflict:
            return None
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        claims = list(pool.map(claim, [app, other]))
    assert len([v for v in claims if v]) == 1
    assert app.store('sea').snapshot().json(f"handoffs/{point['id']}.json")['consumed_by'] in claims


def test_checkpoint_fork_preserves_exact_asset_version(pair):
    app, ids = pair; root = app.root('sea', 'alice')
    root.joinpath('notes.md').write_text('sender alice; send outcome unknown')
    root.joinpath('.env').write_text('SECRET=hidden')
    cp = app.checkpoint('sea', 'alice', 'facts', binding=ids['alice'], checkpoint_id='c1')
    assert '.env' in cp['excluded']
    assert '.env' not in app.checkpoint_show('sea', 'alice', 'c1')['files']
    assert app.checkpoint('sea', 'alice', 'facts', binding=ids['alice'], checkpoint_id='c1') == cp
    with pytest.raises(Conflict):
        app.checkpoint('sea', 'alice', 'changed', binding=ids['alice'], checkpoint_id='c1')
    root.joinpath('notes.md').write_text('later')
    app.checkpoint('sea', 'alice', 'later', binding=ids['alice'])
    fork = app.fork('sea', 'alice', 'c1', 'child')
    assert Path(fork['directory'], 'notes.md').read_text().startswith('sender alice')
    assert fork['current'] is None and not fork['has_run']
    assert app.agent('sea', 'alice')['current'] == ids['alice']
    assert app.work_list('sea') == []


def test_snapshot_refuses_symlink(app, tmp_path):
    app.create('sea', 'alice')
    external = tmp_path / 'private.txt'; external.write_text('not implicit')
    app.root('sea', 'alice').joinpath('link').symlink_to(external)
    with pytest.raises(Error, match='symlink'):
        app.checkpoint('sea', 'alice', 'snapshot')


def test_checkpoint_partial_registration(app, monkeypatch):
    app.create('sea', 'alice'); store = app.store('sea'); original = store.change
    def offline(branch, *args, **kwargs):
        if branch == 'main':
            raise Error('simulated unavailable main')
        return original(branch, *args, **kwargs)
    monkeypatch.setattr(store, 'change', offline)
    with pytest.raises(Error):
        app.checkpoint('sea', 'alice', 'summary', checkpoint_id='cp')
    receipt = read_json(app.root('sea', 'alice') / '.aw-local/checkpoint-operations/cp.json')
    monkeypatch.setattr(store, 'change', original)
    app.root('sea', 'alice').joinpath('new.txt').write_text('later')
    cp = app.checkpoint('sea', 'alice', 'summary', checkpoint_id='cp')
    assert cp['revision'] == receipt['revision']
    assert 'new.txt' not in app.checkpoint_show('sea', 'alice', 'cp')['files']


def test_sync_protects_local_edits(app, tmp_path):
    app.create('sea', 'alice'); root = app.root('sea', 'alice')
    root.joinpath('notes').write_text('base'); app.checkpoint('sea', 'alice', 'base')
    other = App(tmp_path / 'other'); other.workspace_connect('sea', app.store('sea').address)
    other.connect_agent('sea', 'alice', str(tmp_path / 'copy'))
    root.joinpath('notes').write_text('first'); app.checkpoint('sea', 'alice', 'first')
    copy = other.root('sea', 'alice'); copy.joinpath('notes').write_text('second')
    with pytest.raises(Conflict):
        other.sync_agent('sea', 'alice')
    assert copy.joinpath('notes').read_text() == 'second'


def test_source_updates_only_relevant_assets(app):
    store = app.store('sea')
    store.change('main', {'definitions/helper/definition.md': b'# helper v1',
        'definitions/helper/skills/helper/SKILL.md': b'helper skill'}, {}, 'definition')
    app.create('sea', 'alice', definition='definitions/helper'); root = app.root('sea', 'alice')
    root.joinpath('notes.txt').write_text('my work')
    store.change('main', {'unrelated.md': b'not a definition'}, {}, 'unrelated')
    assert not any(f['upstream_changed'] for f in app.versions('sea', 'alice')['files'])
    store.change('main', {'definitions/helper/definition.md': b'# helper v2'}, {}, 'update')
    assert any(f['upstream_changed'] for f in app.versions('sea', 'alice')['files'])
    app.update('sea', 'alice')
    assert root.joinpath('AGENTS.md').read_text() == '# helper v2'
    assert root.joinpath('notes.txt').read_text() == 'my work'
    root.joinpath('AGENTS.md').write_text('# custom')
    with pytest.raises(Conflict):
        app.update('sea', 'alice')


def test_import_and_promote_selected_files(app, tmp_path):
    external = tmp_path / 'legacy'; external.mkdir(); external.joinpath('.git').mkdir()
    external.joinpath('AGENTS.md').write_text('# existing'); external.joinpath('.env').write_text('SECRET')
    app.create('sea', 'alice', import_directory=str(external), assets=['AGENTS.md'])
    assert external.joinpath('.git').is_dir()
    assert not app.root('sea', 'alice').joinpath('.env').exists()
    app.promote('sea', 'alice', ['AGENTS.md'], 'definitions/published')
    assert app.store('sea').snapshot().bytes('definitions/published/definition.md') == b'# existing'
    assert app.root('sea', 'alice').joinpath('AGENTS.md').read_text() == '# existing'
    assert not app.root('sea', 'alice').joinpath('source.json').exists()


def test_archive_keeps_assets(pair):
    app, ids = pair
    with pytest.raises(Conflict):
        app.archive('sea', 'alice')
    cp = app.checkpoint('sea', 'alice', 'stop', binding=ids['alice'])
    app.stop('sea', 'alice', ids['alice'], cp['id']); app.finish_stop('sea', 'alice', ids['alice'], observed_idle=True)
    app.archive('sea', 'alice')
    with pytest.raises(Conflict):
        app.reserve('sea', 'alice')
    app.archive('sea', 'alice', False)
    assert app.agent('sea', 'alice')['current'] is None and app.checkpoints('sea', 'alice')


def test_work_revision_and_sealing(app):
    app.create('sea', 'alice')
    work = execute(app, 'work.create', {'workspace': 'sea', 'owner': 'alice', 'content': 'job'})
    changed = app.work_update('sea', work['id'], work['revision'], content='new job')
    with pytest.raises(Conflict):
        app.work_update('sea', work['id'], work['revision'], content='stale')
    app.work_deliver('sea', work['id'], changed['revision'], 'user determined completion', ['repo@commit:file'])
    with pytest.raises(Conflict):
        app.work_update('sea', work['id'], changed['revision'], content='reopen')
    with pytest.raises(Conflict):
        app.work_deliver('sea', work['id'], changed['revision'], 'again', ['x'])


def test_work_parent_cycle(app):
    app.create('sea', 'alice')
    parent = app.work_create('sea', 'alice', 'parent')
    child = app.work_create('sea', 'alice', 'child', parent['id'])
    with pytest.raises(Conflict):
        app.work_update('sea', parent['id'], parent['revision'], parent_id=child['id'])


def test_actor_cannot_impersonate(pair):
    app, ids = pair
    with pytest.raises(Conflict):
        execute(app, 'message.send', {'agent_id':'bob','binding':ids['bob'],'to':'alice','content':'bad'}, actor=('sea','alice',ids['alice']))
    with pytest.raises(Error):
        execute(app, 'agent.start', {'agent_id':'bob'}, actor=('sea','alice',ids['alice']))


@pytest.mark.parametrize('path', ['../escape', '/etc/passwd', '.git/config', '.aw-local/runtime.json', 'x/../../x'])
def test_asset_path_boundary(app, path):
    app.create('sea', 'alice')
    with pytest.raises(Error):
        execute(app, 'asset.read', {'workspace':'sea','agent_id':'alice','path':path})


def test_work_tree_is_derived(app):
    app.create('sea','alice')
    root=app.work_create('sea','alice','root')
    child=app.work_create('sea','alice','child',root['id'])
    assert app.work_list('sea',tree=True)[0]['children'][0]['id']==child['id']
