from pathlib import Path
import pytest
from agent_workspace.app import App

@pytest.fixture
def app(tmp_path):
    instance = App(tmp_path / 'home')
    # Historical protocol/layout tests deliberately keep their single-entry v1 fixtures.
    # New user-facing Workspace creation defaults to the Worker version.
    instance.workspace_init('sea', str(tmp_path / 'sea.git'), worker_support=False)
    return instance

@pytest.fixture
def pair(app):
    bindings = {}
    for name in ('alice', 'bob'):
        app.create('sea', name)
        bindings[name] = app.reserve('sea', name)['binding']
        app.bind('sea', name, bindings[name], 'native-' + name)
    return app, bindings
