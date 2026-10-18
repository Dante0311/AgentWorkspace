from pathlib import Path
import pytest
from agent_workspace.app import App
from agent_workspace import layout
from agent_workspace.gitstore import GitStore
from agent_workspace.util import encode

@pytest.fixture
def app(tmp_path):
    instance = App(tmp_path / 'home')
    # Historical protocol/layout tests deliberately keep their single-entry v1 fixtures.
    # New user-facing Workspaces use the message branch layout with Workers enabled.
    remote = tmp_path / 'sea.git'
    GitStore.initialize(remote)
    store = GitStore(str(remote), instance.home)
    store.branch('main', {layout.MARKER: layout.marker('workspace'),
                         '.agentworkspace/workspace.json': encode({'schema': 1, 'name': 'sea',
                             'locator': 'local:sea', 'friends': {}, 'projects': {}})})
    instance.workspace_connect('sea', str(remote))
    return instance

@pytest.fixture
def pair(app):
    bindings = {}
    for name in ('alice', 'bob'):
        app.create('sea', name)
        bindings[name] = app.reserve('sea', name)['binding']
        app.bind('sea', name, bindings[name], 'native-' + name)
    return app, bindings
